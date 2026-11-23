//! Cross-platform recent-project metadata store (never retains manuscript text).

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

const MAX_RECENT_PROJECTS: usize = 16;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RecentProject {
    pub path: String,
    pub title: Option<String>,
    pub language: Option<String>,
    pub last_opened_unix: u64,
    pub exists: bool,
}

#[derive(Default, Serialize, Deserialize)]
struct RecentFile {
    schema_version: String,
    projects: Vec<RecentProject>,
}

fn state_file_path() -> Result<PathBuf, String> {
    let base = dirs::data_local_dir()
        .or_else(dirs::config_dir)
        .ok_or_else(|| "Unable to resolve local application state directory".to_string())?;
    let dir = base.join("lixity").join("desktop");
    fs::create_dir_all(&dir).map_err(|e| format!("Failed to create desktop state dir: {e}"))?;
    Ok(dir.join("recent-projects.json"))
}

fn unix_now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

pub fn list_recent() -> Vec<RecentProject> {
    let Ok(file) = state_file_path() else {
        return Vec::new();
    };
    let Ok(raw) = fs::read_to_string(file) else {
        return Vec::new();
    };
    let Ok(mut parsed) = serde_json::from_str::<RecentFile>(&raw) else {
        return Vec::new();
    };
    for item in &mut parsed.projects {
        item.exists = Path::new(&item.path).exists();
    }
    parsed.projects
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
    let mut items = list_recent();
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

    let dest = state_file_path()?;
    let payload = RecentFile {
        schema_version: "lixity-desktop-recent/1".to_string(),
        projects: items.clone(),
    };
    let serialized = serde_json::to_string_pretty(&payload).map_err(|e| e.to_string())?;
    let tmp = dest.with_extension("json.tmp");
    fs::write(&tmp, serialized).map_err(|e| format!("Failed writing recent projects: {e}"))?;
    fs::rename(&tmp, &dest).map_err(|e| format!("Failed replacing recent projects: {e}"))?;
    Ok(items)
}
