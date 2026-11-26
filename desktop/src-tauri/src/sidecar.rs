//! Managed local Python 3.12 runtime supervisor for Lixity Desktop.
//!
//! Starts the bundled relocatable `python-build-standalone` runtime on an
//! OS-assigned loopback port (`127.0.0.1:0`), sends the per-launch secret and
//! initial single-use handshake nonce over stdin (never CLI argv), and waits for
//! the structured readiness line. The Python server watches the desktop
//! process and Windows also ties the child's lifetime to a Job Object.

use crate::security::{random_token_hex, DESKTOP_SECRET_HEADER};
use crate::StartupFailure;
use reqwest::blocking::{Client, RequestBuilder, Response};
use reqwest::{redirect, Method};
use serde::{de::DeserializeOwned, Deserialize, Serialize};
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
const MAX_NONCE_BYTES: usize = 4096;
const MAX_RUNTIME_STATUS_BYTES: usize = 1024 * 1024;
const MAX_ENVIRONMENT_BYTES: usize = 64 * 1024;
// Loading the project supplied at launch can include a full analysis before readiness.
const STARTUP_TIMEOUT: Duration = Duration::from_secs(120);
const LOOPBACK_HOST: &str = "127.0.0.1";

fn build_loopback_client() -> reqwest::Result<Client> {
    Client::builder()
        .redirect(redirect::Policy::none())
        .no_proxy()
        .build()
}

fn read_runtime_json<T: DeserializeOwned>(
    response: Response,
    maximum_bytes: usize,
    invalid_message: &str,
) -> Result<T, String> {
    let mut body = Vec::new();
    response
        .take((maximum_bytes + 1) as u64)
        .read_to_end(&mut body)
        .map_err(|_| "Could not read the desktop runtime response".to_string())?;
    if body.len() > maximum_bytes {
        return Err("Desktop runtime exceeded the response limit".to_string());
    }
    serde_json::from_slice(&body).map_err(|_| invalid_message.to_string())
}

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

fn stop_child(child: &mut Child) -> bool {
    let _ = child.kill();
    child.wait().is_ok()
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
    create_sidecar_log_dir(&dir).ok()?;
    Some(dir)
}

fn create_sidecar_log_dir(dir: &Path) -> std::io::Result<()> {
    let mut builder = fs::DirBuilder::new();
    builder.recursive(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::DirBuilderExt;

        // Managed browser services require private access to this shared directory.
        builder.mode(0o700);
    }
    builder.create(dir)
}

fn sidecar_log_path() -> Option<PathBuf> {
    Some(sidecar_log_dir()?.join("desktop-sidecar.log"))
}

fn rotate_sidecar_log(path: &Path) {
    if fs::metadata(path).is_ok_and(|meta| meta.len() > MAX_LOG_BYTES) {
        let _ = fs::rename(path, path.with_extension("log.1"));
    }
}

fn open_sidecar_log(path: &Path) -> std::io::Result<fs::File> {
    let mut options = OpenOptions::new();
    options.create(true).append(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;

        options.mode(0o600);
    }
    options.open(path)
}

/// Append a host diagnostic line to `desktop-sidecar.log` (never records manuscript data).
pub fn log_desktop_event(level: &str, message: &str) {
    if let Some(path) = sidecar_log_path() {
        append_desktop_event(&path, level, message);
    }
}

fn append_desktop_event(path: &Path, level: &str, message: &str) {
    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    if let Ok(mut file) = open_sidecar_log(path) {
        let line = format!("[{ts}] [{level}] {message}\n");
        let _ = file.write_all(line.as_bytes());
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
    // Host events must leave the pathname attached to the child's open stderr.
    rotate_sidecar_log(&log_path);
    match open_sidecar_log(&log_path) {
        Ok(file) => Stdio::from(file),
        Err(_) => Stdio::inherit(),
    }
}

fn engine_version_for_log(version: &str) -> &str {
    if version.len() <= 32
        && version.split('.').count() == 3
        && version
            .split('.')
            .all(|part| !part.is_empty() && part.bytes().all(|byte| byte.is_ascii_digit()))
    {
        version
    } else {
        "unknown"
    }
}

pub struct PythonSidecar {
    pub port: u16,
    pub version: String,
    pub initial_nonce: Zeroizing<String>,
    secret: Zeroizing<String>,
    client: Client,
    child: Mutex<Option<Child>>,
    #[cfg(target_os = "windows")]
    _job_guard: Option<WindowsJobGuard>,
}

fn find_bundled_python(root: &Path) -> Option<PathBuf> {
    let resolved_root = root.canonicalize().ok()?;
    let python = root.join("python");
    let bin = python.join("bin");
    [
        bin.join("python3.12"),
        bin.join("python3"),
        python.join("python.exe"),
    ]
    .into_iter()
    .find(|path| {
        path.canonicalize()
            .is_ok_and(|resolved| resolved.starts_with(&resolved_root) && resolved.is_file())
    })
}

impl PythonSidecar {
    #[cfg(any(test, all(target_os = "macos", feature = "webview-smoke")))]
    pub(crate) fn fixture(port: u16, secret: &str) -> Self {
        Self {
            port,
            version: String::new(),
            initial_nonce: Zeroizing::new(String::new()),
            secret: Zeroizing::new(secret.to_string()),
            client: build_loopback_client().expect("could not build the loopback test client"),
            child: Mutex::new(None),
            #[cfg(target_os = "windows")]
            _job_guard: None,
        }
    }

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
        if let Some(path) = runtime_roots
            .iter()
            .find_map(|root| find_bundled_python(root))
        {
            return Ok(path);
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
        let python =
            Self::resolve_python(resource_dir).map_err(|_| StartupFailure::RuntimeMissing)?;
        let client = build_loopback_client().map_err(|_| StartupFailure::RuntimeClient)?;
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
        let revision = option_env!("LIXITY_DESKTOP_BUILD_REVISION")
            .filter(|sha| sha.len() == 40 && sha.bytes().all(|byte| byte.is_ascii_hexdigit()))
            .unwrap_or("unknown");
        log_desktop_event(
            "INFO",
            &format!(
                "event=desktop_engine_ready host_pid={} engine_pid={} app_version={} engine_version={} source_revision={revision}",
                payload.parent_pid,
                child.id(),
                env!("CARGO_PKG_VERSION"),
                engine_version_for_log(&ready.version),
            ),
        );

        Ok(Self {
            port: ready.port,
            version: ready.version,
            initial_nonce,
            secret,
            client,
            child: Mutex::new(Some(child)),
            #[cfg(target_os = "windows")]
            _job_guard: job_guard,
        })
    }

    pub(crate) fn loopback_request(
        &self,
        method: Method,
        path: &str,
        timeout: Duration,
    ) -> Result<RequestBuilder, String> {
        if !path.starts_with('/') || path.starts_with("//") {
            return Err("Desktop runtime requests require a local path".to_string());
        }
        let url = format!("http://{LOOPBACK_HOST}:{}{path}", self.port);
        Ok(self
            .client
            .request(method, url)
            .timeout(timeout)
            .header(DESKTOP_SECRET_HEADER, self.secret.as_str()))
    }

    fn request_runtime(
        &self,
        method: Method,
        path: &'static str,
        timeout: Duration,
    ) -> Result<Response, String> {
        let response = self
            .loopback_request(method, path, timeout)?
            .send()
            .map_err(|_| "Could not contact the desktop runtime".to_string())?;
        if !response.status().is_success() {
            return Err(format!(
                "Desktop runtime request rejected (HTTP {})",
                response.status().as_u16()
            ));
        }
        Ok(response)
    }

    /// Mint a fresh single-use handshake nonce for opening an additional window.
    pub fn mint_handshake_nonce(&self) -> Result<String, String> {
        let response =
            self.request_runtime(Method::POST, "/_desktop/nonce", Duration::from_secs(5))?;
        let parsed: NonceResponse =
            read_runtime_json(response, MAX_NONCE_BYTES, "Invalid desktop nonce response")?;
        if !parsed.ok || parsed.nonce.is_empty() {
            return Err("Desktop nonce response missing nonce".to_string());
        }
        Ok(parsed.nonce)
    }

    /// Inspect pending/running audio jobs. An unreadable runtime status is unknown.
    pub(crate) fn has_active_audio_jobs(&self) -> Option<bool> {
        let response = self
            .request_runtime(Method::GET, "/api/runtime", Duration::from_secs(2))
            .ok()?;
        read_runtime_json::<RuntimeOverview>(
            response,
            MAX_RUNTIME_STATUS_BYTES,
            "Invalid desktop runtime status",
        )
        .ok()?
        .active_audio()
    }

    /// Read the Python runtime's content-free inventory without forwarding browser inputs.
    pub(crate) fn runtime_environment(&self) -> Result<serde_json::Value, String> {
        // Leave time for the runtime's ten-second Zotero status probe.
        let response = self.request_runtime(
            Method::GET,
            "/api/desktop/environment?probe_zotero=1",
            Duration::from_secs(15),
        )?;
        const INVALID_ENVIRONMENT: &str = "Invalid desktop runtime environment";
        let inventory: serde_json::Value =
            read_runtime_json(response, MAX_ENVIRONMENT_BYTES, INVALID_ENVIRONMENT)?;
        if inventory["ok"].as_bool() != Some(true)
            || inventory["schema_version"].as_str() != Some("lixity-desktop-env/1")
            || !inventory["app"].is_object()
        {
            return Err(INVALID_ENVIRONMENT.to_string());
        }
        Ok(inventory)
    }

    pub fn shutdown(&self) {
        if let Ok(mut guard) = self.child.lock() {
            if let Some(mut child) = guard.take() {
                let (level, event) = if stop_child(&mut child) {
                    ("INFO", "desktop_engine_stopped")
                } else {
                    ("WARN", "desktop_engine_wait_failed")
                };
                log_desktop_event(
                    level,
                    &format!(
                        "event={event} host_pid={} engine_pid={}",
                        std::process::id(),
                        child.id(),
                    ),
                );
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

    struct RuntimeFixture(PathBuf);
    impl Drop for RuntimeFixture {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    const READY: &str = concat!(
        r#"{"schema_version":"lixity-desktop-ready/1","ready":true,"#,
        r#""host":"127.0.0.1","port":12345,"version":"0.9.1"}"#,
        "\n"
    );

    #[cfg(unix)]
    #[test]
    fn creates_private_sidecar_log_directories_and_preserves_existing_mode() {
        use std::os::unix::fs::PermissionsExt;

        let fixture = RuntimeFixture(std::env::temp_dir().join(random_token_hex()));
        let dir = fixture.0.join("lixity").join("service");
        create_sidecar_log_dir(&dir).unwrap();
        assert_eq!(fs::metadata(&dir).unwrap().permissions().mode() & 0o077, 0);

        fs::set_permissions(&dir, fs::Permissions::from_mode(0o755)).unwrap();
        create_sidecar_log_dir(&dir).unwrap();
        assert_eq!(
            fs::metadata(&dir).unwrap().permissions().mode() & 0o777,
            0o755
        );
    }

    #[cfg(unix)]
    #[test]
    fn creates_private_sidecar_log_files_and_preserves_existing_mode() {
        use std::os::unix::fs::PermissionsExt;

        let fixture = RuntimeFixture(std::env::temp_dir().join(random_token_hex()));
        create_sidecar_log_dir(&fixture.0).unwrap();
        let path = fixture.0.join("desktop-sidecar.log");
        drop(open_sidecar_log(&path).unwrap());
        assert_eq!(fs::metadata(&path).unwrap().permissions().mode() & 0o077, 0);

        fs::set_permissions(&path, fs::Permissions::from_mode(0o644)).unwrap();
        drop(open_sidecar_log(&path).unwrap());
        assert_eq!(
            fs::metadata(&path).unwrap().permissions().mode() & 0o777,
            0o644
        );
    }

    #[test]
    fn appends_host_events_to_the_active_log_and_rotates_before_a_new_child() {
        let fixture = RuntimeFixture(std::env::temp_dir().join(random_token_hex()));
        create_sidecar_log_dir(&fixture.0).unwrap();
        let path = fixture.0.join("desktop-sidecar.log");
        let previous = fixture.0.join("desktop-sidecar.log.1");
        let mut child_stderr = open_sidecar_log(&path).unwrap();
        child_stderr.set_len(MAX_LOG_BYTES + 1).unwrap();
        append_desktop_event(&path, "INFO", "event=fixture_host_ready");
        child_stderr.write_all(b"fixture child output\n").unwrap();
        assert!(!previous.exists());
        let current = fs::read(&path).unwrap();
        assert!(current.ends_with(b"event=fixture_host_ready\nfixture child output\n"));

        drop(child_stderr);
        rotate_sidecar_log(&path);
        assert!(!path.exists());
        assert_eq!(fs::read(&previous).unwrap(), current);
        append_desktop_event(&path, "INFO", "event=fixture_next_launch");
        assert!(fs::read(&path)
            .unwrap()
            .ends_with(b"event=fixture_next_launch\n"));
    }

    #[test]
    fn limits_sidecar_log_versions_to_a_numeric_release_version() {
        assert_eq!(engine_version_for_log("0.9.3"), "0.9.3");
        for version in ["", "0..3", "0.9.3\nuntrusted output", "0.9.3.4"] {
            assert_eq!(engine_version_for_log(version), "unknown");
        }
    }

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
    fn selects_regular_python_files_and_keeps_the_packaged_path() {
        let fixture = RuntimeFixture(std::env::temp_dir().join(random_token_hex()));
        let root = &fixture.0;
        let python = root.join("python");
        let primary = python.join("bin").join("python3.12");
        fs::create_dir_all(&primary).unwrap();
        assert_eq!(find_bundled_python(root), None);

        let windows_path = python.join("python.exe");
        fs::write(&windows_path, b"synthetic interpreter").unwrap();
        assert_eq!(find_bundled_python(root), Some(windows_path));

        #[cfg(unix)]
        {
            fs::remove_dir(&primary).unwrap();
            fs::write(
                primary.with_file_name("python3.12-real"),
                b"synthetic interpreter",
            )
            .unwrap();
            std::os::unix::fs::symlink("python3.12-real", &primary).unwrap();
            assert_eq!(find_bundled_python(root), Some(primary));
        }
    }

    fn runtime_response(
        request: &'static str,
        code: u16,
        body: String,
        assert_result: impl FnOnce(&PythonSidecar),
    ) {
        let listener = std::net::TcpListener::bind((LOOPBACK_HOST, 0)).unwrap();
        let port = listener.local_addr().unwrap().port();
        let fixture = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            stream
                .set_read_timeout(Some(Duration::from_secs(2)))
                .unwrap();
            let mut lines = BufReader::new(&mut stream).lines();
            assert_eq!(lines.next().unwrap().unwrap(), request);
            let headers = lines
                .map(Result::unwrap)
                .take_while(|line| !line.is_empty());
            let expected = format!("{DESKTOP_SECRET_HEADER}: fixture");
            let mut authenticated = false;
            for header in headers {
                authenticated |= header.eq_ignore_ascii_case(&expected);
            }
            assert!(authenticated);
            let redirect = if code == 302 {
                "Location: /followed\r\n"
            } else {
                ""
            };
            write!(
                stream,
                "HTTP/1.1 {code} Fixture\r\n{redirect}Content-Length: {}\r\nConnection: close\r\n\r\n{body}",
                body.len()
            )
            .unwrap();
        });

        let sidecar = PythonSidecar::fixture(port, "fixture");
        assert_result(&sidecar);
        fixture.join().unwrap();
    }

    #[test]
    fn loopback_client_preserves_authentication_and_independent_deadlines() {
        let sidecar = PythonSidecar::fixture(56789, "fixture");
        for (path, timeout) in [
            ("/api/runtime", Duration::from_secs(2)),
            (
                "/api/desktop/environment?probe_zotero=1",
                Duration::from_secs(15),
            ),
        ] {
            let request = sidecar
                .loopback_request(Method::GET, path, timeout)
                .unwrap()
                .build()
                .unwrap();
            assert_eq!(request.timeout(), Some(&timeout));
            assert_eq!(
                request.url().as_str(),
                format!("http://{LOOPBACK_HOST}:56789{path}")
            );
            assert_eq!(request.headers()[DESKTOP_SECRET_HEADER], "fixture");
        }
    }

    #[test]
    fn nonce_response_must_fit_the_control_message_limit() {
        const REQUEST: &str = "POST /_desktop/nonce HTTP/1.1";
        let nonce = r#"{"ok":true,"nonce":"fixture-nonce"}"#;
        runtime_response(REQUEST, 200, nonce.to_string(), |sidecar| {
            assert_eq!(sidecar.mint_handshake_nonce().unwrap(), "fixture-nonce");
        });
        runtime_response(
            REQUEST,
            200,
            format!("{nonce}{}", " ".repeat(MAX_NONCE_BYTES)),
            |sidecar| {
                assert!(sidecar
                    .mint_handshake_nonce()
                    .unwrap_err()
                    .contains("response limit"));
            },
        );
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
            (
                200,
                format!("{empty}{}", " ".repeat(MAX_RUNTIME_STATUS_BYTES)),
                None,
            ),
            (403, empty.to_string(), None),
        ] {
            runtime_response("GET /api/runtime HTTP/1.1", code, body, |sidecar| {
                assert_eq!(sidecar.has_active_audio_jobs(), expected);
            });
        }
    }

    #[test]
    fn runtime_environment_requires_a_bounded_inventory_from_the_loopback_route() {
        const REQUEST: &str = "GET /api/desktop/environment?probe_zotero=1 HTTP/1.1";
        let inventory =
            r#"{"ok":true,"schema_version":"lixity-desktop-env/1","app":{"version":"0.9.1"}}"#;
        runtime_response(REQUEST, 200, inventory.to_string(), |sidecar| {
            assert_eq!(
                sidecar.runtime_environment().unwrap()["app"]["version"],
                "0.9.1"
            );
        });
        for (status, body, error) in [
            (302, inventory.to_string(), "HTTP 302"),
            (200, inventory.replace("env/1", "env/2"), "Invalid"),
            (200, inventory.replace("true", "false"), "Invalid"),
            (200, " ".repeat(MAX_ENVIRONMENT_BYTES + 1), "response limit"),
        ] {
            runtime_response(REQUEST, status, body, |sidecar| {
                assert!(sidecar.runtime_environment().unwrap_err().contains(error));
            });
        }
    }
}
