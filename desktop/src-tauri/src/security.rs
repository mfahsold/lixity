//! Loopback authentication tokens, navigation allowlist and frozen JS bridge injection.

use rand::rngs::OsRng;
use rand::RngCore;
use url::Url;
use zeroize::Zeroizing;

pub const DESKTOP_SECRET_HEADER: &str = "X-Lixity-Desktop-Secret";

/// Generate a 256-bit URL-safe hex token suitable for stdin secret or handshake nonce.
pub fn random_token_hex() -> Zeroizing<String> {
    let mut bytes = [0u8; 32];
    OsRng.fill_bytes(&mut bytes);
    Zeroizing::new(hex::encode(bytes))
}

/// Allow webview navigation strictly to the exact launched loopback origin.
pub fn is_allowed_app_url(candidate: &Url, exact_port: u16) -> bool {
    candidate.scheme() == "http"
        && matches!(candidate.host_str(), Some("127.0.0.1"))
        && candidate.port() == Some(exact_port)
        && candidate.username().is_empty()
        && candidate.password().is_none()
}

/// External links opened in the user's system browser are restricted to https/mailto.
pub fn is_allowed_external_url(raw: &str) -> Result<Url, String> {
    let parsed = Url::parse(raw).map_err(|_| "Invalid external URL".to_string())?;
    match parsed.scheme() {
        "https" | "mailto" => Ok(parsed),
        _ => Err("Only https:// and mailto: external links are allowed".to_string()),
    }
}

/// Validate a relative workspace URL ("/" or "/w/<32 lowercase hex>/").
pub fn is_valid_workspace_path(path: &str) -> bool {
    if path == "/" {
        return true;
    }
    let Some(rest) = path.strip_prefix("/w/") else {
        return false;
    };
    let Some(token) = rest.strip_suffix('/') else {
        return false;
    };
    token.len() == 32 && token.bytes().all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f'))
}

/// Build the initial single-use handshake URL for one desktop window.
pub fn handshake_url(port: u16, nonce: &str, next_path: &str) -> Result<Url, String> {
    if !is_valid_workspace_path(next_path) {
        return Err("Invalid workspace path for desktop handshake".to_string());
    }
    let mut url = Url::parse(&format!("http://127.0.0.1:{port}/_desktop/handshake"))
        .map_err(|e| e.to_string())?;
    url.query_pairs_mut()
        .append_pair("nonce", nonce)
        .append_pair("next", next_path);
    Ok(url)
}

/// Initialization script injected before page scripts to expose a minimal frozen bridge.
///
/// The page never gets direct filesystem or shell plugin access; every capability routes
/// through the 8 audited Rust commands in `commands.rs`.
pub fn bridge_init_script(platform_name: &str, app_version: &str) -> String {
    format!(
        r#"(function () {{
  "use strict";
  if (window.lixityDesktop) return;
  function invoke(cmd, args) {{
    if (!window.__TAURI_INTERNALS__ || typeof window.__TAURI_INTERNALS__.invoke !== "function") {{
      return Promise.reject(new Error("Desktop IPC unavailable"));
    }}
    return window.__TAURI_INTERNALS__.invoke(cmd, args || {{}});
  }}
  async function blobToBase64(blob) {{
    const bytes = new Uint8Array(await blob.arrayBuffer());
    let binary = "";
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {{
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }}
    return btoa(binary);
  }}
  const bridge = Object.freeze({{
    version: 1,
    appVersion: {app_version:?},
    platform: {platform_name:?},
    pickProjectDirectory: function () {{
      return invoke("pick_project_directory");
    }},
    pickImportFile: function (kind) {{
      return invoke("pick_import_file", {{ kind: kind || "manuscript" }});
    }},
    saveBlob: async function (blob, filename) {{
      const payloadBase64 = await blobToBase64(blob);
      return invoke("save_blob", {{
        filename: String(filename || "download"),
        payloadBase64: payloadBase64
      }});
    }},
    saveExport: function (requestSpec, filename) {{
      return invoke("save_export_stream", {{
        request: requestSpec,
        filename: String(filename || "export")
      }});
    }},
    openProjectWindow: function (workspaceUrl, title) {{
      return invoke("open_project_window", {{
        workspaceUrl: String(workspaceUrl || "/"),
        title: String(title || "Lixity")
      }});
    }},
    openExternalUrl: function (url) {{
      return invoke("open_external_url", {{ url: String(url || "") }});
    }},
    revealInFileManager: function (path) {{
      return invoke("reveal_in_file_manager", {{ path: String(path || "") }});
    }},
    setDirtyState: function (state) {{
      return invoke("set_dirty_state", {{
        unsavedEditor: Boolean(state && state.unsavedEditor)
      }});
    }},
    recentProjects: function () {{
      return invoke("list_recent_projects");
    }},
    recordRecentProject: function (path, title, language) {{
      return invoke("record_recent_project", {{
        path: String(path || ""),
        title: title ? String(title) : null,
        language: language ? String(language) : null
      }});
    }},
    removeRecentProject: function (path) {{
      return invoke("remove_recent_project", {{ path: String(path || "") }});
    }},
    clearRecentProjects: function () {{
      return invoke("clear_recent_projects");
    }},
    getPreferences: function () {{
      return invoke("get_preferences");
    }},
    setPreference: function (key, value) {{
      return invoke("set_preference", {{ key: String(key || ""), value: value === undefined ? null : value }});
    }},
    checkForUpdates: function () {{
      return invoke("check_for_updates");
    }},
    openLogsFolder: function () {{
      return invoke("open_logs_folder");
    }},
    audioCapture: Object.freeze({{
      listDevices: function () {{
        return invoke("audio_capture_list_devices");
      }},
      calibrate: function (deviceName, durationSeconds) {{
        return invoke("audio_capture_calibrate", {{
          deviceName: deviceName || null,
          durationSeconds: typeof durationSeconds === "number" ? durationSeconds : 4.0
        }});
      }},
      recordTake: function (deviceName, durationSeconds, filename) {{
        return invoke("audio_capture_record_take", {{
          deviceName: deviceName || null,
          durationSeconds: typeof durationSeconds === "number" ? durationSeconds : 10.0,
          filename: filename ? String(filename) : "recording.wav"
        }});
      }},
      startRecording: function (deviceName, filename) {{
        return invoke("audio_capture_start_recording", {{
          deviceName: deviceName || null,
          filename: filename ? String(filename) : "author-voice.wav"
        }});
      }},
      recordingStatus: function () {{
        return invoke("audio_capture_status");
      }},
      stopRecording: function () {{
        return invoke("audio_capture_stop_recording");
      }},
      cancelRecording: function () {{
        return invoke("audio_capture_cancel_recording");
      }}
    }})
  }});
  Object.defineProperty(window, "lixityDesktop", {{
    value: bridge,
    writable: false,
    configurable: false,
    enumerable: true
  }});
}})();"#
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn allows_only_exact_loopback_port() {
        let ok = Url::parse("http://127.0.0.1:54321/w/0123456789abcdef0123456789abcdef/").unwrap();
        assert!(is_allowed_app_url(&ok, 54321));
        assert!(!is_allowed_app_url(&ok, 8765));

        let evil = Url::parse("http://127.0.0.1.evil.test:54321/").unwrap();
        assert!(!is_allowed_app_url(&evil, 54321));

        let external = Url::parse("https://example.org/").unwrap();
        assert!(!is_allowed_app_url(&external, 54321));
    }

    #[test]
    fn validates_workspace_paths_strictly() {
        assert!(is_valid_workspace_path("/"));
        assert!(is_valid_workspace_path("/w/0123456789abcdef0123456789abcdef/"));
        assert!(!is_valid_workspace_path("/w/SHORT/"));
        assert!(!is_valid_workspace_path("https://example.org/"));
        assert!(!is_valid_workspace_path("/api/settings"));
    }

    #[test]
    fn filters_external_urls() {
        assert!(is_allowed_external_url("https://mfahsold.github.io/lixity/").is_ok());
        assert!(is_allowed_external_url("mailto:mfahsold@googlemail.com").is_ok());
        assert!(is_allowed_external_url("file:///etc/passwd").is_err());
        assert!(is_allowed_external_url("javascript:alert(1)").is_err());
    }
}
