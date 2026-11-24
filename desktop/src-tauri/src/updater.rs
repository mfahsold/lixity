//! User-triggered check against the reviewed desktop download catalog.

use crate::sidecar::log_desktop_event;
use semver::Version;
use serde::{Deserialize, Serialize};
use std::io::Read;
use std::time::Duration;

const CATALOG_URL: &str = "https://mfahsold.github.io/lixity/desktop-downloads.json";
const GUIDE_URL: &str = "https://mfahsold.github.io/lixity/guides/installation.html#desktop";
const SCHEMA: &str = "lixity-desktop-downloads/1";
const CATALOG_MAX_BYTES: u64 = 64 * 1024;

#[derive(Debug, Serialize)]
pub struct UpdateCheckResult {
    pub current_version: String,
    pub latest_tag: Option<String>,
    pub status: UpdateStatus,
    pub guide_url: &'static str,
}

#[derive(Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum UpdateStatus {
    NoPublicInstaller,
    NoMatchingInstaller,
    Current,
    Available,
    InstalledAhead,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct DesktopCatalog {
    schema_version: String,
    #[serde(deserialize_with = "Deserialize::deserialize")]
    tag: Option<String>,
    installers: Vec<Installer>,
}

#[derive(Deserialize)]
struct Installer {
    target: String,
}

#[derive(Debug, PartialEq, Eq)]
enum CheckFailure {
    Connection,
    HttpStatus,
    Catalog,
    InstalledVersion,
}

impl CheckFailure {
    fn code(&self) -> &'static str {
        match self {
            Self::Connection => "connection",
            Self::HttpStatus => "http_status",
            Self::Catalog => "catalog",
            Self::InstalledVersion => "installed_version",
        }
    }
}

fn parse_catalog(bytes: &[u8]) -> Result<DesktopCatalog, CheckFailure> {
    serde_json::from_slice(bytes).map_err(|_| CheckFailure::Catalog)
}

fn fetch_catalog() -> Result<DesktopCatalog, CheckFailure> {
    let client = reqwest::blocking::Client::builder()
        .https_only(true)
        .redirect(reqwest::redirect::Policy::none())
        .timeout(Duration::from_secs(10))
        .user_agent("Lixity-Desktop")
        .build()
        .map_err(|_| CheckFailure::Connection)?;
    let response = client
        .get(CATALOG_URL)
        .header(reqwest::header::ACCEPT, "application/json")
        .header(reqwest::header::CACHE_CONTROL, "no-cache")
        .send()
        .map_err(|_| CheckFailure::Connection)?;
    if response.status() != reqwest::StatusCode::OK {
        return Err(CheckFailure::HttpStatus);
    }
    let mut bytes = Vec::new();
    response
        .take(CATALOG_MAX_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| CheckFailure::Connection)?;
    if bytes.len() as u64 > CATALOG_MAX_BYTES {
        return Err(CheckFailure::Catalog);
    }
    parse_catalog(&bytes)
}

fn installer_target(os: &str, arch: &str) -> Option<String> {
    let suffix = match os {
        "macos" => "apple-darwin",
        "windows" => "pc-windows-msvc",
        "linux" => "unknown-linux-gnu",
        _ => return None,
    };
    Some(format!("{arch}-{suffix}"))
}

fn evaluate_catalog(
    current_version: &str,
    catalog: DesktopCatalog,
    target: Option<&str>,
) -> Result<UpdateCheckResult, CheckFailure> {
    if catalog.schema_version != SCHEMA || catalog.tag.is_none() != catalog.installers.is_empty() {
        return Err(CheckFailure::Catalog);
    }
    let current = Version::parse(current_version).map_err(|_| CheckFailure::InstalledVersion)?;
    let status = match catalog.tag.as_deref() {
        None => UpdateStatus::NoPublicInstaller,
        Some(tag) => {
            let published = tag
                .strip_prefix('v')
                .and_then(|version| Version::parse(version).ok())
                .filter(|version| version.pre.is_empty() && version.build.is_empty())
                .ok_or(CheckFailure::Catalog)?;
            if !catalog
                .installers
                .iter()
                .any(|entry| Some(entry.target.as_str()) == target)
            {
                UpdateStatus::NoMatchingInstaller
            } else {
                match published.cmp_precedence(&current) {
                    std::cmp::Ordering::Greater => UpdateStatus::Available,
                    std::cmp::Ordering::Equal => UpdateStatus::Current,
                    std::cmp::Ordering::Less => UpdateStatus::InstalledAhead,
                }
            }
        }
    };
    Ok(UpdateCheckResult {
        current_version: current_version.to_owned(),
        latest_tag: catalog.tag,
        status,
        guide_url: GUIDE_URL,
    })
}

pub fn check_latest_release(current_version: &str) -> Result<UpdateCheckResult, String> {
    let target = installer_target(std::env::consts::OS, std::env::consts::ARCH);
    fetch_catalog()
        .and_then(|catalog| evaluate_catalog(current_version, catalog, target.as_deref()))
        .map_err(|error| {
            let code = error.code();
            log_desktop_event(
                "WARN",
                &format!("event=desktop_update_check_failed reason={code}"),
            );
            code.to_owned()
        })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn check(tag: &str, installed: &str, target: &str) -> Result<UpdateStatus, CheckFailure> {
        let catalog = parse_catalog(format!(r#"{{"schema_version":"{SCHEMA}","tag":"{tag}","installers":[{{"target":"aarch64-apple-darwin"}}]}}"#).as_bytes())?;
        evaluate_catalog(installed, catalog, Some(target)).map(|result| result.status)
    }

    #[test]
    fn compares_only_stable_desktop_releases_for_the_current_target() {
        let mac = "aarch64-apple-darwin";
        assert_eq!(check("v0.10.0", "0.9.1", mac), Ok(UpdateStatus::Available));
        assert_eq!(
            check("v0.10.0", "0.10.0-rc.1", mac),
            Ok(UpdateStatus::Available)
        );
        assert_eq!(
            check("v0.10.0", "0.10.0+local", mac),
            Ok(UpdateStatus::Current)
        );
        assert_eq!(
            check("v0.10.0", "0.10.1", mac),
            Ok(UpdateStatus::InstalledAhead)
        );
        assert_eq!(
            check("v0.10.0", "0.9.1", "x86_64-apple-darwin"),
            Ok(UpdateStatus::NoMatchingInstaller)
        );
        assert_eq!(
            check("v0.10.0-rc.1", "0.9.1", mac),
            Err(CheckFailure::Catalog)
        );
        assert_eq!(check("0.10.0", "0.9.1", mac), Err(CheckFailure::Catalog));
    }

    #[test]
    fn expects_a_versioned_catalog_and_explicit_empty_state() {
        let catalog = parse_catalog(
            br#"{"schema_version":"lixity-desktop-downloads/1","tag":null,"installers":[]}"#,
        )
        .unwrap();
        let result = evaluate_catalog("0.9.1", catalog, None).unwrap();
        assert_eq!(result.status, UpdateStatus::NoPublicInstaller);
        assert_eq!(result.latest_tag, None);
        assert_eq!(result.guide_url, GUIDE_URL);
        for invalid in [
            r#"{"schema_version":"unknown","tag":null,"installers":[]}"#,
            r#"{"schema_version":"lixity-desktop-downloads/1","installers":[]}"#,
            r#"{"schema_version":"lixity-desktop-downloads/1","tag":"v0.10.0","installers":[]}"#,
        ] {
            assert_eq!(
                parse_catalog(invalid.as_bytes())
                    .and_then(|catalog| evaluate_catalog("0.9.1", catalog, None))
                    .unwrap_err(),
                CheckFailure::Catalog
            );
        }
    }
}
