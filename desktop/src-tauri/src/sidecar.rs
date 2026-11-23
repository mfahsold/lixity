//! Managed local Python 3.12 runtime supervisor for Lixity Desktop.
//!
//! Starts the bundled relocatable `python-build-standalone` runtime on an
//! OS-assigned loopback port (`127.0.0.1:0`), sends the per-launch secret and
//! initial single-use handshake nonce over stdin (never CLI argv), waits for
//! the structured readiness line, and guarantees crash-safe termination across
//! Linux (`PR_SET_PDEATHSIG`), Windows (Job Objects), and macOS (parent watchdog).

use crate::security::{random_token_hex, DESKTOP_SECRET_HEADER};
use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
use zeroize::Zeroizing;

#[derive(Debug, Deserialize)]
pub struct ReadyEnvelope {
    pub schema_version: String,
    pub ready: bool,
    pub host: String,
    pub port: u16,
    pub version: String,
}

#[derive(Serialize)]
struct BootstrapPayload<'a> {
    secret: &'a str,
    handshake_nonce: &'a str,
    parent_pid: u32,
}

#[derive(Deserialize)]
struct NonceResponse {
    ok: bool,
    nonce: String,
}

#[derive(Deserialize)]
struct RuntimeOverview {
    audio: Option<AudioOverview>,
}

#[derive(Deserialize)]
struct AudioOverview {
    jobs: Vec<AudioJob>,
}

#[derive(Deserialize)]
struct AudioJob {
    state: String,
}

#[cfg(target_os = "windows")]
struct WindowsJobGuard {
    handle: windows_sys::Win32::Foundation::HANDLE,
}

#[cfg(target_os = "windows")]
unsafe impl Send for WindowsJobGuard {}

#[cfg(target_os = "windows")]
impl Drop for WindowsJobGuard {
    fn drop(&mut self) {
        if !self.handle.is_null() {
            unsafe {
                windows_sys::Win32::Foundation::CloseHandle(self.handle);
            }
        }
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

        let mut candidates: Vec<PathBuf> = Vec::new();
        if let Some(res) = resource_dir {
            candidates.push(res.join("runtime").join("python").join("bin").join("python3"));
            candidates.push(res.join("runtime").join("python").join("python.exe"));
        }
        if let Ok(exe) = std::env::current_exe() {
            if let Some(dir) = exe.parent() {
                candidates.push(dir.join("runtime").join("python").join("bin").join("python3"));
                candidates.push(dir.join("runtime").join("python").join("python.exe"));
            }
        }
        for path in candidates {
            if path.is_file() {
                return Ok(path);
            }
        }
        Err(
            "Bundled Lixity Python runtime not found. Build it with desktop/scripts/build_runtime_bundle.py \
             or set LIXITY_DESKTOP_PYTHON for development."
                .to_string(),
        )
    }

    pub fn spawn(
        resource_dir: Option<&Path>,
        startup_project: Option<&Path>,
    ) -> Result<Self, String> {
        let python = Self::resolve_python(resource_dir)?;
        let secret = random_token_hex();
        let initial_nonce = random_token_hex();

        let mut cmd = Command::new(&python);
        cmd.arg("-I")
            .arg("-m")
            .arg("lixity")
            .arg("serve")
            .arg("--_desktop-mode")
            .arg("--host")
            .arg("127.0.0.1")
            .arg("--port")
            .arg("0");
        if let Some(project) = startup_project {
            cmd.arg(project);
        } else {
            cmd.arg("--no-project");
        }

        cmd.env("PYTHONNOUSERSITE", "1")
            .env("PYTHONSAFEPATH", "1")
            .env("PYTHONDONTWRITEBYTECODE", "1")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit());

        #[cfg(target_os = "windows")]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            cmd.creation_flags(CREATE_NO_WINDOW);
        }

        #[cfg(target_os = "linux")]
        {
            use std::os::unix::process::CommandExt;
            unsafe {
                cmd.pre_exec(|| {
                    if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGTERM) != 0 {
                        return Err(std::io::Error::last_os_error());
                    }
                    Ok(())
                });
            }
        }

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("Failed to spawn Lixity runtime ({}): {e}", python.display()))?;

        #[cfg(target_os = "windows")]
        let job_guard = attach_kill_on_close_job(&child);

        // Send bootstrap secret & single-use handshake nonce over stdin, then close stdin.
        {
            let mut stdin = child
                .stdin
                .take()
                .ok_or_else(|| "Sidecar stdin pipe unavailable".to_string())?;
            let payload = BootstrapPayload {
                secret: &secret,
                handshake_nonce: &initial_nonce,
                parent_pid: std::process::id(),
            };
            let line = serde_json::to_string(&payload).map_err(|e| e.to_string())?;
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
        let mut reader = BufReader::new(stdout);
        let mut ready_line = String::new();
        reader
            .read_line(&mut ready_line)
            .map_err(|e| format!("Failed reading Lixity readiness line: {e}"))?;
        if ready_line.trim().is_empty() {
            let _ = child.kill();
            return Err("Lixity runtime exited before signaling readiness".to_string());
        }
        let ready: ReadyEnvelope = serde_json::from_str(&ready_line)
            .map_err(|e| format!("Malformed readiness envelope from Lixity runtime: {e}"))?;
        if !ready.ready || ready.port == 0 || ready.schema_version != "lixity-desktop-ready/1" {
            let _ = child.kill();
            return Err("Unexpected readiness response from Lixity runtime".to_string());
        }

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

    /// Query the local server for pending/running audio jobs before closing the app.
    pub fn active_audio_jobs(&self) -> usize {
        let Ok(client) = reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(2))
            .build()
        else {
            return 0;
        };
        let url = format!("http://127.0.0.1:{}/api/runtime", self.port);
        let Ok(resp) = client
            .get(url)
            .header(DESKTOP_SECRET_HEADER, self.secret())
            .send()
        else {
            return 0;
        };
        let Ok(overview) = resp.json::<RuntimeOverview>() else {
            return 0;
        };
        overview
            .audio
            .map(|a| {
                a.jobs
                    .into_iter()
                    .filter(|j| j.state == "pending" || j.state == "running")
                    .count()
            })
            .unwrap_or(0)
    }

    pub fn shutdown(&self) {
        if let Ok(mut guard) = self.child.lock() {
            if let Some(mut child) = guard.take() {
                let _ = child.kill();
                let _ = child.wait();
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
        Some(WindowsJobGuard { handle: job })
    }
}
