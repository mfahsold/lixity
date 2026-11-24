//! Managed local Python 3.12 runtime supervisor for Lixity Desktop.
//!
//! Starts the bundled relocatable `python-build-standalone` runtime on an
//! OS-assigned loopback port (`127.0.0.1:0`), sends the per-launch secret and
//! initial single-use handshake nonce over stdin (never CLI argv), and waits for
//! the structured readiness line. The Python server watches the desktop
//! process and Windows also ties the child's lifetime to a Job Object.

use crate::security::{random_token_hex, DESKTOP_SECRET_HEADER};
use crate::StartupFailure;
use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::{BufRead, BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{mpsc, Mutex};
use std::thread;
use std::time::Duration;
use zeroize::Zeroizing;

const MAX_LOG_BYTES: u64 = 2 * 1024 * 1024;
const MAX_READY_BYTES: usize = 4096;
// Loading the project supplied at launch can include a full analysis before readiness.
const STARTUP_TIMEOUT: Duration = Duration::from_secs(120);
const LOOPBACK_HOST: &str = "127.0.0.1";

#[derive(Debug, Deserialize)]
struct ReadyEnvelope {
    schema_version: String,
    ready: bool,
    host: String,
    port: u16,
    version: String,
}

#[derive(Serialize)]
struct BootstrapPayload<'a> {
    secret: &'a str,
    handshake_nonce: &'a str,
    parent_pid: u32,
}

fn stop_child(child: &mut Child) {
    let _ = child.kill();
    let _ = child.wait();
}

fn read_ready_envelope(stdout: impl Read) -> Result<ReadyEnvelope, String> {
    let mut reader = BufReader::new(stdout.take((MAX_READY_BYTES + 1) as u64));
    let mut line = Vec::new();
    let bytes = reader
        .read_until(b'\n', &mut line)
        .map_err(|error| format!("Failed reading Lixity readiness line: {error}"))?;
    if bytes == 0 {
        return Err("Lixity runtime exited before signaling readiness".to_string());
    }
    if bytes > MAX_READY_BYTES {
        return Err("Lixity runtime readiness response exceeds the size limit".to_string());
    }
    if line.last() != Some(&b'\n') {
        return Err("Incomplete readiness response from Lixity runtime".to_string());
    }
    let ready: ReadyEnvelope = serde_json::from_slice(&line)
        .map_err(|_| "Malformed readiness envelope from Lixity runtime".to_string())?;
    if !ready.ready
        || ready.port == 0
        || ready.schema_version != "lixity-desktop-ready/1"
        || ready.host != LOOPBACK_HOST
        || ready.version.trim().is_empty()
    {
        return Err("Unexpected readiness response from Lixity runtime".to_string());
    }
    Ok(ready)
}

fn bootstrap_child(
    child: &mut Child,
    payload: &BootstrapPayload<'_>,
    timeout: Duration,
) -> Result<ReadyEnvelope, String> {
    // Close stdin after the bootstrap frame. Keep its serialized secrets out of diagnostics.
    {
        let mut stdin = child
            .stdin
            .take()
            .ok_or_else(|| "Sidecar stdin pipe unavailable".to_string())?;
        let line = Zeroizing::new(serde_json::to_string(payload).map_err(|e| e.to_string())?);
        stdin
            .write_all(line.as_bytes())
            .and_then(|_| stdin.write_all(b"\n"))
            .and_then(|_| stdin.flush())
            .map_err(|e| format!("Failed writing desktop bootstrap payload: {e}"))?;
    }
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "Sidecar stdout pipe unavailable".to_string())?;
    let (sender, receiver) = mpsc::sync_channel(1);
    thread::Builder::new()
        .name("lixity-runtime-ready".into())
        .spawn(move || {
            let _ = sender.send(read_ready_envelope(stdout));
        })
        .map_err(|e| format!("Failed starting Lixity readiness reader: {e}"))?;
    match receiver.recv_timeout(timeout) {
        Ok(result) => result,
        Err(mpsc::RecvTimeoutError::Timeout) => {
            Err("Timed out waiting for Lixity runtime readiness".to_string())
        }
        Err(mpsc::RecvTimeoutError::Disconnected) => {
            Err("Lixity runtime readiness reader stopped unexpectedly".to_string())
        }
    }
}

fn bootstrap_or_stop(
    child: &mut Child,
    payload: &BootstrapPayload<'_>,
    timeout: Duration,
) -> Result<ReadyEnvelope, String> {
    let ready = bootstrap_child(child, payload, timeout);
    if ready.is_err() {
        stop_child(child);
    }
    ready
}

#[derive(Deserialize)]
struct NonceResponse {
    ok: bool,
    nonce: String,
}

#[derive(Deserialize)]
struct RuntimeOverview {
    ok: bool,
    schema_version: String,
    audio: AudioOverview,
}

#[derive(Deserialize)]
struct AudioOverview {
    jobs: Vec<AudioJob>,
}

#[derive(Deserialize)]
struct AudioJob {
    state: String,
}

impl RuntimeOverview {
    fn active_audio(&self) -> Option<bool> {
        (self.ok && self.schema_version == "lixity-runtime-local/1").then(|| {
            self.audio
                .jobs
                .iter()
                .any(|job| matches!(job.state.as_str(), "pending" | "running"))
        })
    }
}

/// Owns a Windows Job Object handle stored as `usize` so `PythonSidecar` stays
/// naturally `Send + Sync` across Tauri commands without manual `unsafe impl`.
#[cfg(target_os = "windows")]
struct WindowsJobGuard {
    raw_handle: usize,
}

#[cfg(target_os = "windows")]
impl Drop for WindowsJobGuard {
    fn drop(&mut self) {
        if self.raw_handle != 0 {
            unsafe {
                windows_sys::Win32::Foundation::CloseHandle(
                    self.raw_handle as windows_sys::Win32::Foundation::HANDLE,
                );
            }
        }
    }
}

pub fn sidecar_log_dir() -> Option<PathBuf> {
    let base = dirs::state_dir().or_else(dirs::data_local_dir)?;
    let dir = base.join("lixity").join("service");
    fs::create_dir_all(&dir).ok()?;
    Some(dir)
}

fn sidecar_log_path() -> Option<PathBuf> {
    let dir = sidecar_log_dir()?;
    let log_path = dir.join("desktop-sidecar.log");
    if let Ok(meta) = fs::metadata(&log_path) {
        if meta.len() > MAX_LOG_BYTES {
            let rotated = dir.join("desktop-sidecar.log.1");
            let _ = fs::rename(&log_path, rotated);
        }
    }
    Some(log_path)
}

/// Append a host diagnostic line to `desktop-sidecar.log` (never records manuscript data).
pub fn log_desktop_event(level: &str, message: &str) {
    let Some(log_path) = sidecar_log_path() else {
        return;
    };
    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(&log_path) {
        let _ = writeln!(file, "[{ts}] [{level}] {message}");
    }
}

fn open_sidecar_stderr() -> Stdio {
    if std::env::var("LIXITY_DESKTOP_STDERR_INHERIT")
        .ok()
        .as_deref()
        == Some("1")
    {
        return Stdio::inherit();
    }
    let Some(log_path) = sidecar_log_path() else {
        return Stdio::inherit();
    };
    match OpenOptions::new().create(true).append(true).open(&log_path) {
        Ok(file) => Stdio::from(file),
        Err(_) => Stdio::inherit(),
    }
}

pub struct PythonSidecar {
    pub port: u16,
    pub version: String,
    pub initial_nonce: Zeroizing<String>,
    secret: Zeroizing<String>,
    child: Mutex<Option<Child>>,
    #[cfg(target_os = "windows")]
    _job_guard: Option<WindowsJobGuard>,
}

impl PythonSidecar {
    /// Locate the bundled Python interpreter relative to Tauri's resource directory,
    /// with an explicit developer override (`LIXITY_DESKTOP_PYTHON`) for local testing.
    pub fn resolve_python(resource_dir: Option<&Path>) -> Result<PathBuf, String> {
        if let Ok(override_path) = std::env::var("LIXITY_DESKTOP_PYTHON") {
            let candidate = PathBuf::from(override_path);
            if candidate.is_file() {
                return Ok(candidate);
            }
            return Err(format!(
                "LIXITY_DESKTOP_PYTHON points to missing interpreter: {}",
                candidate.display()
            ));
        }

        let mut runtime_roots: Vec<PathBuf> = Vec::new();
        if let Some(res) = resource_dir {
            runtime_roots.push(res.join("runtime"));
        }
        if let Ok(exe) = std::env::current_exe() {
            if let Some(dir) = exe.parent() {
                runtime_roots.push(dir.join("runtime"));
                if let Some(parent) = dir.parent() {
                    // macOS .app bundle: Contents/MacOS/lixity-desktop -> Contents/Resources/runtime
                    runtime_roots.push(parent.join("Resources").join("runtime"));
                    // Linux .deb/.rpm/.AppImage: usr/bin/lixity-desktop -> usr/lib/Lixity/runtime
                    runtime_roots.push(parent.join("lib").join("Lixity").join("runtime"));
                    runtime_roots.push(parent.join("lib").join("lixity-desktop").join("runtime"));
                }
            }
        }
        for root in runtime_roots {
            for rel in [
                Path::new("python").join("bin").join("python3.12"),
                Path::new("python").join("bin").join("python3"),
                Path::new("python").join("python.exe"),
            ] {
                let path = root.join(rel);
                if path.is_file() {
                    return Ok(path);
                }
            }
        }
        Err(
            "Bundled Lixity Python runtime not found. Build it with desktop/scripts/build_runtime_bundle.py \
             or set LIXITY_DESKTOP_PYTHON for development."
                .to_string(),
        )
    }

    pub(crate) fn spawn(
        resource_dir: Option<&Path>,
        startup_project: Option<&Path>,
    ) -> Result<Self, StartupFailure> {
        let python = Self::resolve_python(resource_dir).map_err(|_| StartupFailure::RuntimeMissing)?;
        let secret = random_token_hex();
        let initial_nonce = random_token_hex();

        let mut cmd = Command::new(&python);
        // Isolated mode ignores PYTHON* variables. Pass -B explicitly so a
        // writable installation cannot add bytecode to its signed resources.
        cmd.arg("-I")
            .arg("-B")
            .arg("-m")
            .arg("lixity")
            .arg("serve")
            .arg("--_desktop-mode")
            .arg("--host")
            .arg(LOOPBACK_HOST)
            .arg("--port")
            .arg("0");
        if let Some(project) = startup_project {
            cmd.arg(project);
        } else {
            cmd.arg("--no-project");
        }

        cmd.stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(open_sidecar_stderr());

        #[cfg(target_os = "windows")]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            cmd.creation_flags(CREATE_NO_WINDOW);
        }

        // Python watches the parent process identified in the bootstrap frame.
        // Linux PR_SET_PDEATHSIG would also fire when this startup thread returns.
        let mut child = cmd
            .spawn()
            .map_err(|error| StartupFailure::RuntimeLaunch(error.kind()))?;

        #[cfg(target_os = "windows")]
        let job_guard = attach_kill_on_close_job(&child);

        let payload = BootstrapPayload {
            secret: &secret,
            handshake_nonce: &initial_nonce,
            parent_pid: std::process::id(),
        };
        let ready = bootstrap_or_stop(&mut child, &payload, STARTUP_TIMEOUT)
            .map_err(|_| StartupFailure::RuntimeReadiness)?;

        Ok(Self {
            port: ready.port,
            version: ready.version,
            initial_nonce,
            secret,
            child: Mutex::new(Some(child)),
            #[cfg(target_os = "windows")]
            _job_guard: job_guard,
        })
    }

    pub fn secret(&self) -> &str {
        &self.secret
    }

    /// Mint a fresh single-use handshake nonce for opening an additional window.
    pub fn mint_handshake_nonce(&self) -> Result<String, String> {
        let client = reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(5))
            .build()
            .map_err(|e| e.to_string())?;
        let url = format!("http://127.0.0.1:{}/_desktop/nonce", self.port);
        let resp = client
            .post(url)
            .header(DESKTOP_SECRET_HEADER, self.secret())
            .send()
            .map_err(|e| format!("Failed to request desktop nonce: {e}"))?;
        if !resp.status().is_success() {
            return Err(format!(
                "Desktop nonce request rejected (HTTP {})",
                resp.status().as_u16()
            ));
        }
        let parsed: NonceResponse = resp.json().map_err(|e| e.to_string())?;
        if !parsed.ok || parsed.nonce.is_empty() {
            return Err("Desktop nonce response missing nonce".to_string());
        }
        Ok(parsed.nonce)
    }

    /// Inspect pending/running audio jobs. An unreadable runtime status is unknown.
    pub(crate) fn has_active_audio_jobs(&self) -> Option<bool> {
        let client = reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(2))
            .redirect(reqwest::redirect::Policy::none())
            .no_proxy()
            .build()
            .ok()?;
        let url = format!("http://127.0.0.1:{}/api/runtime", self.port);
        let response = client
            .get(url)
            .header(DESKTOP_SECRET_HEADER, self.secret())
            .send()
            .ok()?;
        if !response.status().is_success() {
            return None;
        }
        response.json::<RuntimeOverview>().ok()?.active_audio()
    }

    pub fn shutdown(&self) {
        if let Ok(mut guard) = self.child.lock() {
            if let Some(mut child) = guard.take() {
                stop_child(&mut child);
            }
        }
    }
}

impl Drop for PythonSidecar {
    fn drop(&mut self) {
        self.shutdown();
    }
}

#[cfg(target_os = "windows")]
fn attach_kill_on_close_job(child: &Child) -> Option<WindowsJobGuard> {
    use std::mem::{size_of, zeroed};
    use std::os::windows::io::AsRawHandle;
    use windows_sys::Win32::System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
        SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    };

    unsafe {
        let job = CreateJobObjectW(std::ptr::null(), std::ptr::null());
        if job.is_null() {
            return None;
        }
        let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = zeroed();
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        let ok = SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            &info as *const _ as *const _,
            size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
        );
        if ok == 0 {
            windows_sys::Win32::Foundation::CloseHandle(job);
            return None;
        }
        let assigned = AssignProcessToJobObject(job, child.as_raw_handle() as _);
        if assigned == 0 {
            windows_sys::Win32::Foundation::CloseHandle(job);
            return None;
        }
        Some(WindowsJobGuard {
            raw_handle: job as usize,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const READY: &str = concat!(
        r#"{"schema_version":"lixity-desktop-ready/1","ready":true,"#,
        r#""host":"127.0.0.1","port":12345,"version":"0.9.1"}"#,
        "\n"
    );

    #[test]
    fn accepts_the_complete_loopback_readiness_frame() {
        let ready = read_ready_envelope(READY.as_bytes()).unwrap();
        assert_eq!(ready.port, 12345);
        assert_eq!(ready.version, "0.9.1");
    }

    #[test]
    fn rejects_incomplete_invalid_and_oversized_readiness_frames() {
        for (frame, error) in [
            (String::new(), "exited"),
            ("not-json\n".to_string(), "Malformed"),
            (READY.trim_end().to_string(), "Incomplete"),
            (READY.replace("127.0.0.1", "0.0.0.0"), "Unexpected"),
            (READY.replace("12345", "0"), "Unexpected"),
            (READY.replace("true", "false"), "Unexpected"),
            (READY.replace("ready/1", "ready/2"), "Unexpected"),
            (READY.replace("0.9.1", ""), "Unexpected"),
            (" ".repeat(MAX_READY_BYTES + 1), "size limit"),
        ] {
            assert!(read_ready_envelope(frame.as_bytes())
                .unwrap_err()
                .contains(error));
        }
    }

    #[cfg(unix)]
    #[test]
    fn stops_and_reaps_a_child_that_never_becomes_ready() {
        let mut child = Command::new("/bin/sh")
            .args(["-c", "IFS= read -r bootstrap; exec /bin/sleep 30"])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let payload = BootstrapPayload {
            secret: "fixture",
            handshake_nonce: "fixture",
            parent_pid: std::process::id(),
        };
        let error =
            bootstrap_or_stop(&mut child, &payload, Duration::from_millis(100)).unwrap_err();
        assert_eq!(error, "Timed out waiting for Lixity runtime readiness");
        assert!(child.try_wait().unwrap().is_some());
    }

    #[test]
    fn resolve_python_errors_cleanly_when_missing() {
        if std::env::var_os("LIXITY_DESKTOP_PYTHON").is_some() {
            return;
        }
        let err =
            PythonSidecar::resolve_python(Some(Path::new("/nonexistent/lixity-res"))).unwrap_err();
        assert!(err.contains("Bundled Lixity Python runtime not found"));
        assert!(matches!(
            PythonSidecar::spawn(Some(Path::new("/nonexistent/lixity-res")), None),
            Err(StartupFailure::RuntimeMissing)
        ));
    }

    #[test]
    fn runtime_audio_status_distinguishes_unavailable_from_idle() {
        let empty = r#"{"schema_version":"lixity-runtime-local/1","ok":true,"audio":{"jobs":[]}}"#;
        for (code, body, expected) in [
            (200, empty.to_string(), Some(false)),
            (
                200,
                empty.replace("[]", r#"[{"state":"ready"}]"#),
                Some(false),
            ),
            (
                200,
                empty.replace("[]", r#"[{"state":"pending"}]"#),
                Some(true),
            ),
            (
                200,
                empty.replace("[]", r#"[{"state":"running"}]"#),
                Some(true),
            ),
            (200, empty.replace("true", "false"), None),
            (200, empty.replace("local/1", "local/2"), None),
            (200, r#"{"ok":true}"#.to_string(), None),
            (403, empty.to_string(), None),
        ] {
            let listener = std::net::TcpListener::bind((LOOPBACK_HOST, 0)).unwrap();
            let port = listener.local_addr().unwrap().port();
            let fixture = thread::spawn(move || {
                let (mut stream, _) = listener.accept().unwrap();
                stream
                    .set_read_timeout(Some(Duration::from_secs(2)))
                    .unwrap();
                let mut lines = BufReader::new(&mut stream).lines();
                assert_eq!(lines.next().unwrap().unwrap(), "GET /api/runtime HTTP/1.1");
                let headers = lines
                    .map(Result::unwrap)
                    .take_while(|line| !line.is_empty());
                let expected = format!("{DESKTOP_SECRET_HEADER}: fixture");
                let mut authenticated = false;
                for header in headers {
                    authenticated |= header.eq_ignore_ascii_case(&expected);
                }
                assert!(authenticated);
                write!(
                    stream,
                    "HTTP/1.1 {code} Fixture\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                    body.len()
                )
                .unwrap();
            });

            let sidecar = PythonSidecar {
                port,
                version: String::new(),
                initial_nonce: Zeroizing::new(String::new()),
                secret: Zeroizing::new("fixture".to_string()),
                child: Mutex::new(None),
                #[cfg(target_os = "windows")]
                _job_guard: None,
            };
            assert_eq!(sidecar.has_active_audio_jobs(), expected);
            fixture.join().unwrap();
        }
    }
}
