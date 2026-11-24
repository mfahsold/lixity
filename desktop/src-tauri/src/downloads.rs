//! Atomic local artifact exports (blob + streaming loopback) and reveal allowlist.

use crate::security::{is_valid_workspace_path, random_token_hex};
use crate::sidecar::PythonSidecar;
use base64::Engine;
use reqwest::blocking::Response;
use reqwest::header::CONTENT_TYPE;
use reqwest::{Method, StatusCode};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashSet;
use std::fs::{self, File};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::Duration;

const MAX_BLOB_BYTES: usize = 128 * 1024 * 1024;
const MAX_ERROR_BODY_BYTES: u64 = 8 * 1024;

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
        let canonical =
            fs::canonicalize(candidate).map_err(|_| "Requested path does not exist".to_string())?;
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
    pub filename: Option<String>,
    pub bytes: u64,
    pub sha256: Option<String>,
}

impl SaveOutcome {
    pub fn cancelled() -> Self {
        Self {
            saved: false,
            path: None,
            filename: None,
            bytes: 0,
            sha256: None,
        }
    }

    fn written(destination: &Path, bytes: u64, sha256: String) -> Self {
        Self {
            saved: true,
            path: Some(destination.display().to_string()),
            filename: destination
                .file_name()
                .map(|name| name.to_string_lossy().into_owned()),
            bytes,
            sha256: Some(sha256),
        }
    }
}

#[derive(Debug, Deserialize)]
pub struct ExportRequestSpec {
    pub path: String,
    #[serde(default = "default_get")]
    pub method: String,
    pub payload: Option<serde_json::Value>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ExportArtifact {
    ManuscriptPdf,
    DossierPdf,
    WebsiteZip,
    Canvas,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ExportError {
    message: String,
    status: Option<u16>,
    server_code: Option<&'static str>,
    server_message: Option<String>,
}

impl From<String> for ExportError {
    fn from(message: String) -> Self {
        Self {
            message,
            status: None,
            server_code: None,
            server_message: None,
        }
    }
}

impl ExportRequestSpec {
    pub fn artifact(&self) -> Result<ExportArtifact, ExportError> {
        let (path, query) = match self.path.split_once('?') {
            Some((path, query)) => (path, Some(query)),
            None => (self.path.as_str(), None),
        };
        let route = if let Some(scope) = path.strip_prefix("/w/") {
            scope.split_once('/').and_then(|(workspace, _)| {
                let (workspace_path, suffix) = path.split_at("/w/".len() + workspace.len() + 1);
                if is_valid_workspace_path(workspace_path) {
                    suffix.strip_prefix("api/")
                } else {
                    None
                }
            })
        } else {
            path.strip_prefix("/api/")
        };
        let invalid = || ExportError::from("Invalid desktop export route".to_string());
        if self
            .path
            .bytes()
            .any(|byte| byte.is_ascii_control() || matches!(byte, b' ' | b'#' | b'\\'))
        {
            return Err(invalid());
        }
        match (self.method.to_ascii_uppercase().as_str(), route, query) {
            ("POST", Some("manuscript-pdf"), None) => Ok(ExportArtifact::ManuscriptPdf),
            ("GET", Some("research/dossier-pdf"), Some(query)) if !query.is_empty() => {
                Ok(ExportArtifact::DossierPdf)
            }
            ("POST", Some("site-export"), None) => Ok(ExportArtifact::WebsiteZip),
            ("GET", Some("canvas"), None) => Ok(ExportArtifact::Canvas),
            _ => Err(invalid()),
        }
    }
}

impl ExportArtifact {
    fn mime(self) -> &'static str {
        match self {
            Self::ManuscriptPdf | Self::DossierPdf => "application/pdf",
            Self::WebsiteZip => "application/zip",
            Self::Canvas => "application/json",
        }
    }

    fn validated_prefix(
        self,
        response: &mut Response,
        expected: u64,
    ) -> Result<&'static [u8], String> {
        match self {
            Self::ManuscriptPdf | Self::DossierPdf => {
                let mut prefix = [0; 5];
                response
                    .read_exact(&mut prefix)
                    .map_err(|_| "Incomplete PDF response".to_string())?;
                if &prefix != b"%PDF-" {
                    return Err("Invalid PDF response".to_string());
                }
                Ok(b"%PDF-")
            }
            Self::WebsiteZip => {
                if expected < 22 {
                    return Err("Incomplete ZIP response".to_string());
                }
                let mut prefix = [0; 4];
                response
                    .read_exact(&mut prefix)
                    .map_err(|_| "Incomplete ZIP response".to_string())?;
                match &prefix {
                    b"PK\x03\x04" => Ok(b"PK\x03\x04"),
                    b"PK\x05\x06" => Ok(b"PK\x05\x06"),
                    _ => Err("Invalid ZIP response".to_string()),
                }
            }
            Self::Canvas => Ok(b""),
        }
    }
}

#[derive(Deserialize)]
struct ServerError {
    code: Option<String>,
    message: Option<String>,
}

fn response_mime(response: &Response) -> &str {
    response
        .headers()
        .get(CONTENT_TYPE)
        .and_then(|value| value.to_str().ok())
        .unwrap_or_default()
        .split(';')
        .next()
        .unwrap_or_default()
        .trim()
}

fn response_error(response: Response, artifact: ExportArtifact) -> ExportError {
    let status = response.status();
    let mut error = ExportError::from(format!("Export failed with HTTP {}", status.as_u16()));
    error.status = Some(status.as_u16());
    if (artifact == ExportArtifact::ManuscriptPdf
        || (artifact == ExportArtifact::DossierPdf && status == StatusCode::CONFLICT))
        && response_mime(&response).eq_ignore_ascii_case("application/json")
    {
        let mut body = Vec::new();
        if response
            .take(MAX_ERROR_BODY_BYTES + 1)
            .read_to_end(&mut body)
            .is_ok()
            && body.len() as u64 <= MAX_ERROR_BODY_BYTES
        {
            if let Ok(details) = serde_json::from_slice::<ServerError>(&body) {
                if artifact == ExportArtifact::ManuscriptPdf {
                    error.server_message = details.message;
                } else if details.code.as_deref() == Some("stale-context") {
                    error.server_code = Some("stale-context");
                }
            }
        }
    }
    error
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

fn atomic_write_reader<R: Read>(
    mut reader: R,
    destination: &Path,
    expected: u64,
) -> Result<(u64, String), String> {
    let parent = destination
        .parent()
        .ok_or_else(|| "Destination has no parent folder".to_string())?;
    let staging = parent.join(format!(
        ".lixity-export-{}.part",
        random_token_hex().as_str()
    ));

    let mut file = File::options()
        .write(true)
        .create_new(true)
        .open(&staging)
        .map_err(|e| format!("Unable to create staging file: {e}"))?;
    let mut hasher = Sha256::new();
    let mut buf = [0u8; 64 * 1024];
    let mut remaining = expected;

    let write_res: Result<(), String> = (|| {
        loop {
            let n = reader
                .read(&mut buf)
                .map_err(|e| format!("Failed reading export stream: {e}"))?;
            if n == 0 {
                break;
            }
            remaining = remaining
                .checked_sub(n as u64)
                .ok_or_else(|| "Export response exceeds its declared size".to_string())?;
            file.write_all(&buf[..n])
                .map_err(|e| format!("Failed writing export file: {e}"))?;
            hasher.update(&buf[..n]);
        }
        if remaining != 0 {
            return Err("Export response ended before its declared size".to_string());
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

    Ok((expected, hex::encode(hasher.finalize())))
}

pub fn write_base64_blob(payload_base64: &str, destination: &Path) -> Result<SaveOutcome, String> {
    let decoded = base64::engine::general_purpose::STANDARD
        .decode(payload_base64)
        .map_err(|_| "Invalid base64 export payload".to_string())?;
    if decoded.len() > MAX_BLOB_BYTES {
        return Err("Export payload exceeds maximum desktop blob size".to_string());
    }
    let (bytes, sha256) = atomic_write_reader(&decoded[..], destination, decoded.len() as u64)?;
    Ok(SaveOutcome::written(destination, bytes, sha256))
}

pub fn stream_loopback_export(
    sidecar: &PythonSidecar,
    artifact: ExportArtifact,
    spec: &ExportRequestSpec,
    destination: &Path,
) -> Result<SaveOutcome, ExportError> {
    let posts_json = matches!(
        artifact,
        ExportArtifact::ManuscriptPdf | ExportArtifact::WebsiteZip
    );
    let method = if posts_json { Method::POST } else { Method::GET };
    let mut req = sidecar.loopback_request(method, &spec.path, Duration::from_secs(300))?;
    if posts_json {
        req = if let Some(payload) = &spec.payload {
            req.json(payload)
        } else {
            req.json(&serde_json::json!({}))
        };
    }

    let mut response = req
        .send()
        .map_err(|e| {
            format!(
                "Failed fetching export from local Lixity server: {}",
                e.without_url()
            )
        })?;
    if response.status() != StatusCode::OK {
        return Err(response_error(response, artifact));
    }
    if !response_mime(&response).eq_ignore_ascii_case(artifact.mime()) {
        return Err("Unexpected export response type".to_string().into());
    }
    let expected = response
        .content_length()
        .filter(|size| *size > 0)
        .ok_or_else(|| "Export response has no usable size".to_string())?;
    let prefix = artifact.validated_prefix(&mut response, expected)?;
    let (bytes, sha256) = atomic_write_reader(prefix.chain(response), destination, expected)?;
    Ok(SaveOutcome::written(destination, bytes, sha256))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::security::DESKTOP_SECRET_HEADER;
    use std::io::{BufRead, BufReader};
    use std::net::TcpListener;
    use std::thread;

    const WORKSPACE: &str = "0123456789abcdef0123456789abcdef";
    const DOSSIER: &str =
        "/api/research/dossier-pdf?id=synthetic&revision=2&research_token=synthetic";

    fn spec(method: &str, path: &str) -> ExportRequestSpec {
        ExportRequestSpec {
            path: path.to_string(),
            method: method.to_string(),
            payload: None,
        }
    }

    #[test]
    fn accepts_only_export_methods_and_routes() {
        for (method, path, artifact) in [
            ("POST", "/api/manuscript-pdf", ExportArtifact::ManuscriptPdf),
            ("GET", DOSSIER, ExportArtifact::DossierPdf),
            ("POST", "/api/site-export", ExportArtifact::WebsiteZip),
            ("GET", "/api/canvas", ExportArtifact::Canvas),
        ] {
            assert_eq!(spec(method, path).artifact().unwrap(), artifact);
            assert_eq!(
                spec(method, &format!("/w/{WORKSPACE}{path}"))
                    .artifact()
                    .unwrap(),
                artifact
            );
        }
        for (method, path) in [
            ("GET", "/api/manuscript-pdf"),
            ("POST", DOSSIER),
            ("POST", "/api/site-preflight"),
            ("GET", "/api/research/dossier-pdf"),
            ("GET", "/w/synthetic/api/canvas"),
            ("GET", "/api/canvas?mode=synthetic"),
            ("GET", "/api/canvas#synthetic"),
        ] {
            assert!(
                spec(method, path).artifact().is_err(),
                "accepted {method} {path}"
            );
        }
    }

    struct ExportFixture(PathBuf);

    impl ExportFixture {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!(
                "lixity-export-test-{}",
                random_token_hex().as_str()
            ));
            fs::create_dir(&path).unwrap();
            Self(path)
        }

        fn serve(
            &self,
            request: &ExportRequestSpec,
            headers: &str,
            body: &[u8],
        ) -> Result<SaveOutcome, ExportError> {
            let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
            let port = listener.local_addr().unwrap().port();
            let response = [headers.as_bytes(), b"\r\n\r\n", body].concat();
            let expected = format!("{} {} HTTP/1.1\r\n", request.method, request.path);
            let expected_payload = request.payload.clone();
            let handling = thread::spawn(move || {
                let (mut connection, _) = listener.accept().unwrap();
                let mut reader = BufReader::new(&mut connection);
                let mut line = String::new();
                reader.read_line(&mut line).unwrap();
                assert_eq!(line, expected);
                let mut length = 0;
                let mut authenticated = false;
                loop {
                    line.clear();
                    assert!(reader.read_line(&mut line).unwrap() > 0);
                    if line == "\r\n" {
                        break;
                    }
                    if let Some((name, value)) = line.split_once(':') {
                        if name.eq_ignore_ascii_case("Content-Length") {
                            length = value.trim().parse().unwrap();
                        }
                        if name.eq_ignore_ascii_case(DESKTOP_SECRET_HEADER) {
                            authenticated = value.trim() == "synthetic-secret";
                        }
                    }
                }
                assert!(authenticated);
                let mut request_body = vec![0; length];
                reader.read_exact(&mut request_body).unwrap();
                if let Some(payload) = expected_payload {
                    assert_eq!(
                        serde_json::from_slice::<serde_json::Value>(&request_body).unwrap(),
                        payload
                    );
                }
                connection.write_all(&response).unwrap();
            });
            let result = stream_loopback_export(
                &PythonSidecar::fixture(port, "synthetic-secret"),
                request.artifact().unwrap(),
                request,
                &self.0.join("saved"),
            );
            handling.join().unwrap();
            result
        }

        fn assert_saved(&self, expected: &[u8]) {
            assert_eq!(fs::read(self.0.join("saved")).unwrap(), expected);
            assert_eq!(fs::read_dir(&self.0).unwrap().count(), 1);
        }
    }

    impl Drop for ExportFixture {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn complete_stream_preserves_signature_and_replaces_destination() {
        let fixture = ExportFixture::new();
        let body = b"%PDF-1.4\n%%EOF\n";
        fs::write(fixture.0.join("saved"), b"original").unwrap();
        let saved = fixture
            .serve(
                &spec("POST", "/api/manuscript-pdf"),
                &format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/pdf\r\nContent-Length: {}",
                    body.len()
                ),
                body,
            )
            .unwrap();
        assert!(saved.saved);
        assert_eq!(saved.filename.as_deref(), Some("saved"));
        assert_eq!(saved.bytes, body.len() as u64);
        assert_eq!(saved.sha256.unwrap(), hex::encode(Sha256::digest(body)));
        fixture.assert_saved(body);
    }

    #[cfg(unix)]
    #[test]
    fn saved_blob_returns_the_native_filename() {
        let fixture = ExportFixture::new();
        let filename = r"Kapitel \ Rohfassung.pdf";
        let destination = fixture.0.join(filename);
        let saved = write_base64_blob("bGl4aXR5", &destination).unwrap();
        assert_eq!(saved.filename.as_deref(), Some(filename));
        assert_eq!(fs::read(destination).unwrap(), b"lixity");
        assert!(SaveOutcome::cancelled().filename.is_none());
    }

    #[test]
    fn streams_website_zip_with_the_selected_workspace_and_payload() {
        let fixture = ExportFixture::new();
        let mut request = spec("POST", &format!("/w/{WORKSPACE}/api/site-export"));
        request.payload = Some(serde_json::json!({
            "project_token": "synthetic",
            "include_research": true,
            "include_source_files": false,
        }));
        let mut zip = [0u8; 22];
        zip[..4].copy_from_slice(b"PK\x05\x06");
        let saved = fixture
            .serve(
                &request,
                "HTTP/1.1 200 OK\r\nContent-Type: application/zip\r\nContent-Length: 22",
                &zip,
            )
            .unwrap();
        assert!(saved.saved);
        assert_eq!(saved.bytes, zip.len() as u64);
        fixture.assert_saved(&zip);
    }

    #[test]
    fn incomplete_or_malformed_stream_keeps_existing_destination() {
        let fixture = ExportFixture::new();
        fs::write(fixture.0.join("saved"), b"original").unwrap();
        for (headers, body) in [
            (
                "HTTP/1.1 200 OK\r\nContent-Type: application/pdf\r\nContent-Length: 300",
                b"%PDF-1.4\n".as_slice(),
            ),
            (
                "HTTP/1.1 200 OK\r\nContent-Type: application/pdf\r\nContent-Length: 8",
                b"not pdf!".as_slice(),
            ),
            (
                "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 5",
                b"%PDF-".as_slice(),
            ),
            (
                "HTTP/1.1 302 Found\r\nLocation: /api/canvas\r\nContent-Length: 0",
                b"".as_slice(),
            ),
        ] {
            assert!(fixture.serve(&spec("GET", DOSSIER), headers, body).is_err());
            fixture.assert_saved(b"original");
        }
    }

    #[test]
    fn dossier_stale_code_is_scoped_to_the_bounded_conflict_body() {
        let fixture = ExportFixture::new();
        let evidence = br#"{"code":"stale-context","message":"Synthetic local detail"}"#;
        let oversized = [
            b" ".repeat(MAX_ERROR_BODY_BYTES as usize),
            evidence.to_vec(),
        ]
        .concat();
        for (status, body, code) in [
            (409, evidence.as_slice(), Some("stale-context")),
            (409, b"{}".as_slice(), None),
            (409, oversized.as_slice(), None),
            (404, evidence.as_slice(), None),
            (410, b"{}".as_slice(), None),
        ] {
            let headers = format!("HTTP/1.1 {status} Error\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {}", body.len());
            let error = fixture
                .serve(&spec("GET", DOSSIER), &headers, body)
                .unwrap_err();
            assert_eq!(error.status, Some(status));
            assert_eq!(error.server_code, code);
            assert!(error.server_message.is_none());
        }
        assert!(fs::read_dir(&fixture.0).unwrap().next().is_none());
    }
}
