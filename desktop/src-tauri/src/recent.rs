//! Cross-platform recent-project metadata store (never retains manuscript text).

use crate::desktop_state::StateFile;
use serde::{Deserialize, Serialize};
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

const MAX_RECENT_PROJECTS: usize = 16;
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
}

impl Default for RecentFile {
    fn default() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.to_string(),
            projects: Vec::new(),
        }
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

fn update_recent(
    apply: impl FnOnce(&mut Vec<RecentProject>),
) -> Result<Vec<RecentProject>, String> {
    let file = RECENT.update(|mut file: RecentFile| {
        file.schema_version = SCHEMA_VERSION.to_string();
        refresh_availability(&mut file.projects);
        apply(&mut file.projects);
        Ok(file)
    })?;
    Ok(file.projects)
}

pub fn list_recent() -> Vec<RecentProject> {
    let mut file: RecentFile = RECENT.read();
    refresh_availability(&mut file.projects);
    file.projects
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
    update_recent(|items| {
        items.retain(|entry| entry.path != trimmed);
        items.insert(
            0,
            RecentProject {
                path: trimmed.to_string(),
                title: title.map(|t| t.trim().chars().take(200).collect()),
                language: language.map(|l| l.trim().chars().take(16).collect()),
                last_opened_unix: unix_now(),
                exists: Path::new(trimmed).exists(),
            },
        );
        items.truncate(MAX_RECENT_PROJECTS);
    })
}

pub fn remove_recent(path: &str) -> Result<Vec<RecentProject>, String> {
    let trimmed = path.trim();
    update_recent(|items| items.retain(|entry| entry.path != trimmed))
}

pub fn clear_recent() -> Result<(), String> {
    RECENT.write(&RecentFile::default())
}
