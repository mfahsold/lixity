//! Audited Tauri IPC commands exposed through the frozen `window.lixityDesktop` bridge.

use crate::audio_capture::{
    calibrate_microphone, list_input_devices, record_wav_take, CalibrationReport,
    CaptureDeviceInfo, RecordedTakeResult,
};
use crate::dirty_state::DirtyRegistry;
use crate::downloads::{
    sanitize_suggested_filename, stream_loopback_export, write_base64_blob, ExportRequestSpec,
    RevealAllowlist, SaveOutcome,
};
use crate::recent::{list_recent, record_recent, RecentProject};
use crate::security::{
    bridge_init_script, handshake_url, is_allowed_app_url, is_allowed_external_url,
    is_valid_workspace_path,
};
use crate::sidecar::PythonSidecar;
use crate::updater::{check_latest_release, UpdateCheckResult};
use serde::Serialize;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use tauri::{AppHandle, State, WebviewUrl, WebviewWindow, WebviewWindowBuilder};
use tauri_plugin_dialog::{DialogExt, FilePath};
use tauri_plugin_opener::OpenerExt;

static WINDOW_COUNTER: AtomicU64 = AtomicU64::new(1);

pub struct DesktopState {
    pub sidecar: Arc<PythonSidecar>,
    pub dirty: Arc<DirtyRegistry>,
    pub reveal: Arc<RevealAllowlist>,
    pub app_version: String,
    pub locale: String,
}

#[derive(Debug, Serialize)]
pub struct PickedPath {
    pub path: String,
}

fn file_path_to_pathbuf(fp: FilePath) -> Result<PathBuf, String> {
    fp.into_path()
        .map_err(|_| "Selected OS path could not be converted to a local filesystem path".to_string())
}

#[tauri::command]
pub async fn pick_project_directory(
    app: AppHandle,
    state: State<'_, DesktopState>,
) -> Result<Option<PickedPath>, String> {
    let picked = app.dialog().file().blocking_pick_folder();
    match picked {
        Some(fp) => {
            let path = file_path_to_pathbuf(fp)?;
            state.reveal.allow(&path);
            Ok(Some(PickedPath {
                path: path.display().to_string(),
            }))
        }
        None => Ok(None),
    }
}

#[tauri::command]
pub async fn pick_import_file(
    app: AppHandle,
    kind: String,
) -> Result<Option<PickedPath>, String> {
    let (filter_name, extensions): (&str, &[&str]) = match kind.as_str() {
        "pdf" => ("PDF Document", &["pdf"]),
        "audio" => ("WAV Audio", &["wav"]),
        "notes" => ("Lixity Reader Notes", &["json"]),
        _ => ("Manuscript Files", &["md", "markdown", "txt", "docx"]),
    };
    let picked = app
        .dialog()
        .file()
        .add_filter(filter_name, extensions)
        .blocking_pick_file();
    match picked {
        Some(fp) => {
            let path = file_path_to_pathbuf(fp)?;
            Ok(Some(PickedPath {
                path: path.display().to_string(),
            }))
        }
        None => Ok(None),
    }
}

#[tauri::command]
pub async fn save_blob(
    app: AppHandle,
    state: State<'_, DesktopState>,
    filename: String,
    payload_base64: String,
) -> Result<SaveOutcome, String> {
    let suggested = sanitize_suggested_filename(&filename);
    let chosen = app.dialog().file().set_file_name(&suggested).blocking_save_file();
    let Some(fp) = chosen else {
        return Ok(SaveOutcome {
            saved: false,
            path: None,
            bytes: 0,
            sha256: None,
        });
    };
    let dest = file_path_to_pathbuf(fp)?;
    let outcome = write_base64_blob(&payload_base64, &dest)?;
    state.reveal.allow(&dest);
    Ok(outcome)
}

#[tauri::command]
pub async fn save_export_stream(
    app: AppHandle,
    state: State<'_, DesktopState>,
    request: ExportRequestSpec,
    filename: String,
) -> Result<SaveOutcome, String> {
    let suggested = sanitize_suggested_filename(&filename);
    let chosen = app.dialog().file().set_file_name(&suggested).blocking_save_file();
    let Some(fp) = chosen else {
        return Ok(SaveOutcome {
            saved: false,
            path: None,
            bytes: 0,
            sha256: None,
        });
    };
    let dest = file_path_to_pathbuf(fp)?;
    let port = state.sidecar.port;
    let secret = state.sidecar.secret().to_string();
    let outcome = tauri::async_runtime::spawn_blocking(move || {
        stream_loopback_export(port, &secret, &request, &dest)
    })
    .await
    .map_err(|e| format!("Export task failed: {e}"))??;
    if let Some(ref saved_path) = outcome.path {
        state.reveal.allow(std::path::Path::new(saved_path));
    }
    Ok(outcome)
}

pub fn spawn_desktop_window(
    app: &AppHandle,
    port: u16,
    nonce: &str,
    workspace_url: &str,
    title: &str,
    app_version: &str,
    explicit_label: Option<&str>,
) -> Result<WebviewWindow, String> {
    let target = handshake_url(port, nonce, workspace_url)?;
    let label = match explicit_label {
        Some(fixed) => fixed.to_string(),
        None => format!("project-{}", WINDOW_COUNTER.fetch_add(1, Ordering::Relaxed)),
    };
    let safe_title: String = title.trim().chars().take(120).collect();
    let window_title = if safe_title.is_empty() || safe_title == "Lixity" {
        "Lixity".to_string()
    } else {
        format!("{safe_title} — Lixity")
    };
    let opener_app = app.clone();
    let init_script = bridge_init_script(std::env::consts::OS, app_version);

    WebviewWindowBuilder::new(app, label, WebviewUrl::External(target))
        .title(window_title)
        .inner_size(1340.0, 880.0)
        .min_inner_size(760.0, 560.0)
        .initialization_script(&init_script)
        .on_navigation(move |nav_url| {
            if is_allowed_app_url(nav_url, port) {
                true
            } else {
                if is_allowed_external_url(nav_url.as_str()).is_ok() {
                    let _ = opener_app.opener().open_url(nav_url.as_str(), None::<&str>);
                }
                false
            }
        })
        .build()
        .map_err(|e| format!("Failed opening desktop window: {e}"))
}

#[tauri::command]
pub async fn open_project_window(
    app: AppHandle,
    state: State<'_, DesktopState>,
    workspace_url: String,
    title: String,
) -> Result<(), String> {
    if !is_valid_workspace_path(&workspace_url) {
        return Err("Invalid workspace path".to_string());
    }
    let sidecar = Arc::clone(&state.sidecar);
    let nonce = tauri::async_runtime::spawn_blocking(move || sidecar.mint_handshake_nonce())
        .await
        .map_err(|e| format!("Failed minting desktop nonce: {e}"))??;
    spawn_desktop_window(
        &app,
        state.sidecar.port,
        &nonce,
        &workspace_url,
        &title,
        &state.app_version,
        None,
    )?;
    Ok(())
}

#[tauri::command]
pub fn open_logs_folder(app: AppHandle) -> Result<(), String> {
    let base = dirs::state_dir()
        .or_else(dirs::data_local_dir)
        .ok_or_else(|| "Unable to locate local Lixity state directory".to_string())?;
    let logs_dir = base.join("lixity").join("service");
    std::fs::create_dir_all(&logs_dir)
        .map_err(|e| format!("Unable to prepare Lixity logs folder: {e}"))?;
    app.opener()
        .open_path(logs_dir.to_string_lossy().as_ref(), None::<&str>)
        .map_err(|e| format!("Failed opening logs folder: {e}"))
}

#[tauri::command]
pub fn open_external_url(app: AppHandle, url: String) -> Result<(), String> {
    let validated = is_allowed_external_url(&url)?;
    app.opener()
        .open_url(validated.as_str(), None::<&str>)
        .map_err(|e| format!("Failed opening external URL: {e}"))
}

#[tauri::command]
pub fn reveal_in_file_manager(
    app: AppHandle,
    state: State<'_, DesktopState>,
    path: String,
) -> Result<(), String> {
    let allowed = state.reveal.is_allowed(std::path::Path::new(&path))?;
    app.opener()
        .reveal_item_in_dir(allowed)
        .map_err(|e| format!("Failed revealing file: {e}"))
}

#[tauri::command]
pub fn set_dirty_state(
    window: WebviewWindow,
    state: State<'_, DesktopState>,
    unsaved_editor: bool,
) {
    state.dirty.set_editor_dirty(window.label(), unsaved_editor);
}

#[tauri::command]
pub fn list_recent_projects() -> Vec<RecentProject> {
    list_recent()
}

#[tauri::command]
pub fn record_recent_project(
    state: State<'_, DesktopState>,
    path: String,
    title: Option<String>,
    language: Option<String>,
) -> Result<Vec<RecentProject>, String> {
    state.reveal.allow(std::path::Path::new(&path));
    record_recent(&path, title, language)
}

#[tauri::command]
pub async fn check_for_updates(state: State<'_, DesktopState>) -> Result<UpdateCheckResult, String> {
    let version = state.app_version.clone();
    tauri::async_runtime::spawn_blocking(move || check_latest_release(&version))
        .await
        .map_err(|e| format!("Update check task failed: {e}"))?
}

#[tauri::command]
pub fn audio_capture_list_devices() -> Result<Vec<CaptureDeviceInfo>, String> {
    list_input_devices()
}

#[tauri::command]
pub async fn audio_capture_calibrate(
    device_name: Option<String>,
    duration_seconds: f32,
) -> Result<CalibrationReport, String> {
    tauri::async_runtime::spawn_blocking(move || {
        calibrate_microphone(device_name.as_deref(), duration_seconds)
    })
    .await
    .map_err(|e| format!("Calibration task failed: {e}"))?
}

#[tauri::command]
pub async fn audio_capture_record_take(
    device_name: Option<String>,
    duration_seconds: f32,
    filename: String,
) -> Result<RecordedTakeResult, String> {
    tauri::async_runtime::spawn_blocking(move || {
        record_wav_take(device_name.as_deref(), duration_seconds, &filename)
    })
    .await
    .map_err(|e| format!("Recording task failed: {e}"))?
}
