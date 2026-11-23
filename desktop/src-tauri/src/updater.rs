//! Explicit, user-triggered release check (never runs automatically on startup).
//!
//! Lixity makes zero silent network requests. Only when the author clicks
//! "Check for Updates…" does this module query the GitHub Releases API once,
//! returning the published tag, URL, and current version for manual review.

use serde::{Deserialize, Serialize};
use std::time::Duration;

const RELEASES_LATEST_URL: &str = "https://api.github.com/repos/mfahsold/lixity/releases/latest";

#[derive(Debug, Serialize)]
pub struct UpdateCheckResult {
    pub current_version: String,
    pub latest_tag: String,
    pub update_available: bool,
    pub release_url: String,
    pub note: String,
}

#[derive(Deserialize)]
struct GithubRelease {
    tag_name: String,
    html_url: String,
}

pub fn check_latest_release(current_version: &str) -> Result<UpdateCheckResult, String> {
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(10))
        .user_agent(format!("Lixity-Desktop/{current_version}"))
        .build()
        .map_err(|e| format!("HTTP client error: {e}"))?;

    let response = client
        .get(RELEASES_LATEST_URL)
        .header("Accept", "application/vnd.github+json")
        .send()
        .map_err(|e| format!("Could not reach GitHub Releases: {e}"))?;

    if !response.status().is_success() {
        return Err(format!(
            "GitHub Releases returned HTTP {}",
            response.status().as_u16()
        ));
    }

    let release: GithubRelease = response
        .json()
        .map_err(|e| format!("Malformed release metadata: {e}"))?;
    let latest_clean = release.tag_name.trim_start_matches('v');
    let current_clean = current_version.trim_start_matches('v');

    Ok(UpdateCheckResult {
        current_version: current_version.to_string(),
        latest_tag: release.tag_name.clone(),
        update_available: latest_clean != current_clean,
        release_url: release.html_url,
        note: "Review release notes and back up research archives before upgrading.".to_string(),
    })
}
