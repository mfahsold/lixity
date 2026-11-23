//! Atomic local artifact exports (blob + streaming loopback) and reveal allowlist.

use crate::security::DESKTOP_SECRET_HEADER;
use base64::Engine;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashSet;
use std::fs::{self, File};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::Duration;

const MAX_BLOB_BYTES: usize = 128 * 1024 * 1024;

#[derive(Default)]
pub struct RevealAllowlist {
    paths: Mutex<HashSet<PathBuf>>,
}

impl RevealAllowlist {
    pub fn allow(&self, path: &Path) {
        if let Ok(canonical) = fs::canonicalize(path) {
            if let Ok(mut set) = self.paths.lock() {
                set.insert(canonical);
            }
        }
    }

    pub fn is_allowed(&self, candidate: &Path) -> Result<PathBuf, String> {
        let canonical = fs::canonicalize(candidate)
            .map_err(|_| "Requested path does not exist".to_string())?;
        let ok = self
            .paths
            .lock()
            .map(|set| set.contains(&canonical))
            .unwrap_or(false);
        if ok {
            Ok(canonical)
        } else {
            Err("Path was not opened or exported in this desktop session".to_string())
        }
    }
}

#[derive(Debug, Serialize)]
pub struct SaveOutcome {
    pub saved: bool,
    pub path: Option<String>,
    pub bytes: u64,
    pub sha256: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct ExportRequestSpec {
    pub path: String,
    #[serde(default = "default_get")]
    pub method: String,
    pub payload: Option<serde_json::Value>,
}

fn default_get() -> String {
    "GET".to_string()
}

pub fn sanitize_suggested_filename(name: &str) -> String {
    let cleaned: String = name
        .chars()
        .filter(|c| !matches!(c, '/' | '\\' | '\0'..='\x1f' | '\x7f'))
        .take(180)
        .collect();
    let trimmed = cleaned.trim();
    if trimmed.is_empty() || trimmed == "." || trimmed == ".." {
        "lixity-export".to_string()
    } else {
        trimmed.to_string()
    }
}

fn atomic_write_reader<R: Read>(mut reader: R, destination: &Path) -> Result<(u64, String), String> {
    let parent = destination
        .parent()
        .ok_or_else(|| "Destination has no parent folder".to_string())?;
    let stem = destination
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("lixity-export");
    let staging = parent.join(format!(".{stem}.{}.part", std::process::id()));

    let mut file = File::create(&staging)
        .map_err(|e| format!("Unable to create staging file: {e}"))?;
    let mut hasher = Sha256::new();
    let mut buf = [0u8; 64 * 1024];
    let mut total: u64 = 0;

    let write_res: Result<(), String> = (|| {
        loop {
            let n = reader
                .read(&mut buf)
                .map_err(|e| format!("Failed reading export stream: {e}"))?;
            if n == 0 {
                break;
            }
            file.write_all(&buf[..n])
                .map_err(|e| format!("Failed writing export file: {e}"))?;
            hasher.update(&buf[..n]);
            total += n as u64;
        }
        file.sync_all()
            .map_err(|e| format!("Failed flushing export file: {e}"))?;
        Ok(())
    })();

    if let Err(err) = write_res {
        drop(file);
        let _ = fs::remove_file(&staging);
        return Err(err);
    }
    drop(file);

    fs::rename(&staging, destination).map_err(|e| {
        let _ = fs::remove_file(&staging);
        format!("Failed replacing destination file: {e}")
    })?;

    Ok((total, hex::encode(hasher.finalize())))
}

pub fn write_base64_blob(payload_base64: &str, destination: &Path) -> Result<SaveOutcome, String> {
    let decoded = base64::engine::general_purpose::STANDARD
        .decode(payload_base64)
        .map_err(|_| "Invalid base64 export payload".to_string())?;
    if decoded.len() > MAX_BLOB_BYTES {
        return Err("Export payload exceeds maximum desktop blob size".to_string());
    }
    let (bytes, sha256) = atomic_write_reader(&decoded[..], destination)?;
    Ok(SaveOutcome {
        saved: true,
        path: Some(destination.display().to_string()),
        bytes,
        sha256: Some(sha256),
    })
}

pub fn stream_loopback_export(
    port: u16,
    secret: &str,
    spec: &ExportRequestSpec,
    destination: &Path,
) -> Result<SaveOutcome, String> {
    if !spec.path.starts_with("/api/") && !spec.path.starts_with("/w/") {
        return Err("Export path must target a Lixity workspace API endpoint".to_string());
    }
    if spec.path.contains("://") || spec.path.contains("..") {
        return Err("Invalid export route".to_string());
    }
    let url = format!("http://127.0.0.1:{port}{}", spec.path);
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(300))
        .build()
        .map_err(|e| format!("Loopback client error: {e}"))?;

    let method = spec.method.to_ascii_uppercase();
    let req = match method.as_str() {
        "GET" => client.get(&url),
        "POST" => {
            let builder = client.post(&url);
            if let Some(payload) = &spec.payload {
                builder.json(payload)
            } else {
                builder.json(&serde_json::json!({}))
            }
        }
        _ => return Err("Only GET and POST export routes are supported".to_string()),
    };

    let response = req
        .header(DESKTOP_SECRET_HEADER, secret)
        .send()
        .map_err(|e| format!("Failed fetching export from local Lixity server: {e}"))?;
    if !response.status().is_success() {
        return Err(format!(
            "Export failed with HTTP {}",
            response.status().as_u16()
        ));
    }
    let (bytes, sha256) = atomic_write_reader(response, destination)?;
    Ok(SaveOutcome {
        saved: true,
        path: Some(destination.display().to_string()),
        bytes,
        sha256: Some(sha256),
    })
}
