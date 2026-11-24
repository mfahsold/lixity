//! Cross-platform recent-project metadata store (never retains manuscript text).

use crate::desktop_state::StateFile;
use serde::{Deserialize, Serialize};
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

const MAX_RECENT_PROJECTS: usize = 16;
const MAX_LEGACY_PATHS: usize = 8;
const MAX_LEGACY_PATH_BYTES: usize = 8192;
const SCHEMA_VERSION: &str = "lixity-desktop-recent/1";
static RECENT: StateFile = StateFile::new("recent-projects.json", "recent projects");

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RecentProject {
    pub path: String,
    pub title: Option<String>,
    pub language: Option<String>,
    pub last_opened_unix: u64,
    pub exists: bool,
}

#[derive(Serialize, Deserialize)]
struct RecentFile {
    schema_version: String,
    projects: Vec<RecentProject>,
    #[serde(default)]
    legacy_imported: bool,
}

impl Default for RecentFile {
    fn default() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.to_string(),
            projects: Vec::new(),
            legacy_imported: false,
        }
    }
}

impl RecentFile {
    fn remove(&mut self, path: &str) {
        self.legacy_imported = true;
        self.projects.retain(|entry| entry.path != path);
    }

    fn clear(&mut self) {
        self.legacy_imported = true;
        self.projects.clear();
    }
}

fn unix_now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn refresh_availability(items: &mut [RecentProject]) {
    for item in items {
        item.exists = Path::new(&item.path).exists();
    }
}

fn update_recent(apply: impl FnOnce(&mut RecentFile)) -> Result<Vec<RecentProject>, String> {
    let file = RECENT.update(|mut file: RecentFile| {
        file.schema_version = SCHEMA_VERSION.to_string();
        refresh_availability(&mut file.projects);
        apply(&mut file);
        Ok(file)
    })?;
    Ok(file.projects)
}

pub fn list_recent() -> Vec<RecentProject> {
    let mut file: RecentFile = RECENT.read();
    refresh_availability(&mut file.projects);
    file.projects
}

fn manuscript_in_project(manuscript: &Path, project: &Path) -> bool {
    manuscript.parent() == Some(project) && manuscript.is_file()
}

fn merge_legacy(file: &mut RecentFile, paths: &[String]) -> bool {
    if file.legacy_imported {
        return false;
    }
    // A previously used WebView origin may have copied stale entries from the
    // desktop store. That snapshot must never restore an explicitly removed entry.
    file.legacy_imported = true;
    let before = file.projects.len();
    for path in paths.iter().take(MAX_LEGACY_PATHS) {
        if file.projects.len() >= MAX_RECENT_PROJECTS {
            break;
        }
        let clean = path.trim();
        let path = Path::new(clean);
        if !path.is_absolute()
            || clean.len() > MAX_LEGACY_PATH_BYTES
            || clean.contains('\0')
            || file.projects.iter().any(|entry| {
                let existing = Path::new(&entry.path);
                path == existing || manuscript_in_project(path, existing)
            })
        {
            continue;
        }
        file.projects.push(RecentProject {
            path: clean.to_owned(),
            title: None,
            language: None,
            last_opened_unix: 0,
            exists: path.exists(),
        });
    }
    file.projects.len() != before
}

pub fn import_legacy_recent(paths: &[String]) -> Result<(Vec<RecentProject>, bool), String> {
    if paths.is_empty() {
        return Ok((list_recent(), false));
    }
    let mut imported = false;
    let entries = update_recent(|file| imported = merge_legacy(file, paths))?;
    Ok((entries, imported))
}

pub fn record_recent(
    path: &str,
    title: Option<String>,
    language: Option<String>,
) -> Result<Vec<RecentProject>, String> {
    let trimmed = path.trim();
    if trimmed.is_empty() || trimmed.contains('\0') {
        return Err("Invalid project path".to_string());
    }
    update_recent(|file| {
        file.projects.retain(|entry| {
            entry.path != trimmed
                && (entry.last_opened_unix != 0
                    || !manuscript_in_project(Path::new(&entry.path), Path::new(trimmed)))
        });
        file.projects.insert(
            0,
            RecentProject {
                path: trimmed.to_string(),
                title: title.map(|t| t.trim().chars().take(200).collect()),
                language: language.map(|l| l.trim().chars().take(16).collect()),
                last_opened_unix: unix_now(),
                exists: Path::new(trimmed).exists(),
            },
        );
        file.projects.truncate(MAX_RECENT_PROJECTS);
    })
}

pub fn remove_recent(path: &str) -> Result<Vec<RecentProject>, String> {
    update_recent(|file| file.remove(path.trim()))
}

pub fn clear_recent() -> Result<Vec<RecentProject>, String> {
    update_recent(RecentFile::clear)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::security::random_token_hex;

    fn test_path(name: &str) -> String {
        std::env::temp_dir()
            .join(format!(
                "lixity-recent-{}-{name}",
                random_token_hex().as_str()
            ))
            .to_string_lossy()
            .into_owned()
    }

    #[test]
    fn old_state_imports_only_once_and_retains_native_metadata() {
        let native = test_path("native");
        let legacy = test_path("legacy");
        let mut file: RecentFile = serde_json::from_value(serde_json::json!({
            "schema_version": SCHEMA_VERSION,
            "projects": [{
                "path": native, "title": "Preserved title", "language": "de",
                "last_opened_unix": 42, "exists": false,
            }],
        }))
        .unwrap();
        let paths = [
            native,
            "relative".to_owned(),
            legacy.clone(),
            legacy.clone(),
        ];
        assert!(merge_legacy(&mut file, &paths));
        assert_eq!(file.projects.len(), 2);
        assert_eq!(file.projects[0].title.as_deref(), Some("Preserved title"));
        assert_eq!(file.projects[0].last_opened_unix, 42);
        assert_eq!(file.projects[1].path, legacy);
        assert!(!file.projects[1].exists);

        file.remove(&legacy);
        let mut reloaded: RecentFile =
            serde_json::from_slice(&serde_json::to_vec(&file).unwrap()).unwrap();
        assert!(!merge_legacy(&mut reloaded, &paths));
        assert_eq!(reloaded.projects.len(), 1);
    }

    #[test]
    fn remove_and_clear_prevent_import_from_stale_windows() {
        let paths = [test_path("stale")];
        let mut cleared = RecentFile::default();
        cleared.clear();
        assert!(!merge_legacy(&mut cleared, &paths));
        assert!(cleared.projects.is_empty());

        let mut removed = RecentFile::default();
        removed.remove(&paths[0]);
        assert!(!merge_legacy(&mut removed, &paths));
        assert!(removed.projects.is_empty());
    }
}
