//! Disposable macOS test of the real workspace WebView and IPC capability.

use crate::commands::DesktopState;
use crate::security::{
    bridge_init_script, is_allowed_external_url, random_token_hex, route_webview_navigation,
    DESKTOP_SECRET_HEADER,
};
use crate::sidecar::PythonSidecar;
use std::collections::HashSet;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpListener;
use std::sync::mpsc::{self, Sender};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tauri::webview::NewWindowResponse;
use tauri::{ActivationPolicy, Manager, Url, WebviewUrl, WebviewWindowBuilder};

const PAGE: &str = include_str!("../test-fixtures/webview-smoke.html");
const ENVIRONMENT: &str = concat!(
    r#"{"ok":true,"schema_version":"lixity-desktop-env/1","#,
    r#""app":{"version":"0.0.0-smoke","desktop_mode":true}}"#
);
const TIMEOUT: Duration = Duration::from_secs(15);

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
enum Observation {
    Bridge,
    SameWindowLink,
    LicenseLink,
    CommercialLicenseLink,
    Failure,
}

#[tauri::command]
fn get_preferences() -> &'static str {
    "Rust IPC reached"
}

#[tauri::command]
fn open_external_url(url: String) -> Result<(), String> {
    is_allowed_external_url(&url).map(|_| ())
}

fn serve_fixture(listener: TcpListener, secret: &str, observed: Sender<Observation>) {
    for mut stream in listener.incoming().map_while(Result::ok) {
        if stream
            .set_read_timeout(Some(Duration::from_secs(2)))
            .is_err()
        {
            continue;
        }
        let mut first_line = String::new();
        let mut request = BufReader::new(&mut stream).take(4096);
        if request.read_line(&mut first_line).is_err() {
            continue;
        }
        let mut parts = first_line.split_whitespace();
        if parts.next() != Some("GET") {
            continue;
        }
        let (status, content_type, body, result) = match parts.next() {
            Some("/") => ("200 OK", "text/html", PAGE, None),
            Some("/bridge-ok") => ("200 OK", "text/html", "", Some(Observation::Bridge)),
            Some("/bridge-failed") => ("200 OK", "text/html", "", Some(Observation::Failure)),
            Some("/api/desktop/environment?probe_zotero=1") => {
                let authenticated = request
                    .lines()
                    .map_while(Result::ok)
                    .take_while(|line| !line.is_empty())
                    .any(|line| {
                        line.split_once(':').is_some_and(|(name, value)| {
                            name.eq_ignore_ascii_case(DESKTOP_SECRET_HEADER)
                                && value.trim() == secret
                        })
                    });
                if authenticated {
                    ("200 OK", "application/json", ENVIRONMENT, None)
                } else {
                    ("403 Forbidden", "text/html", "", None)
                }
            }
            _ => ("404 Not Found", "text/html", "", None),
        };
        let _ = write!(
            stream,
            "HTTP/1.1 {status}\r\nConnection: close\r\nContent-Type: {content_type}; charset=utf-8\r\n\
             Content-Security-Policy: default-src 'none'; script-src 'nonce-ipc-smoke'; \
             connect-src 'self' ipc: http://ipc.localhost https://ipc.localhost\r\n\
             Content-Length: {}\r\n\r\n{body}",
            body.len(),
        );
        if let Some(observation) = result {
            let _ = observed.send(observation);
        }
    }
}

fn record_link(url: &Url, observed: &Sender<Observation>) {
    let observation = match url.as_str() {
        "https://github.com/mfahsold/lixity/blob/main/LICENSE" => Observation::LicenseLink,
        "https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md#when-to-talk-to-the-maintainer" => {
            Observation::CommercialLicenseLink
        }
        "https://example.org/contact" => Observation::SameWindowLink,
        _ => Observation::Failure,
    };
    let _ = observed.send(observation);
}

/// Exercise production navigation and runtime IPC against synthetic loopback data.
pub fn run() -> Result<(), Box<dyn std::error::Error>> {
    let listener = TcpListener::bind("127.0.0.1:0")?;
    let port = listener.local_addr()?.port();
    let origin = Url::parse(&format!("http://127.0.0.1:{port}/"))?;
    let (sender, receiver) = mpsc::channel();
    let fixture_sender = sender.clone();
    let secret = random_token_hex();
    let sidecar = Arc::new(PythonSidecar::fixture(port, &secret));
    std::thread::spawn(move || serve_fixture(listener, &secret, fixture_sender));

    tauri::Builder::default()
        .plugin(crate::desktop_opener_plugin())
        .manage(DesktopState {
            sidecar,
            dirty: Default::default(),
            reveal: Default::default(),
            recorder: Default::default(),
            app_version: "smoke".to_string(),
            locale: "en".to_string(),
        })
        .invoke_handler(tauri::generate_handler![
            get_preferences,
            open_external_url,
            crate::commands::get_runtime_environment,
            crate::commands::read_sample_manuscript,
            crate::commands::set_workspace_title,
        ])
        .setup(move |app| {
            app.set_activation_policy(ActivationPolicy::Accessory);
            let navigation = sender.clone();
            let popup = sender.clone();
            crate::window_chrome::native_title_bar(WebviewWindowBuilder::new(app, "main", WebviewUrl::External(origin)))
                .visible(false)
                .incognito(true)
                .initialization_script(bridge_init_script("macos", "smoke"))
                .on_navigation(move |url| {
                    route_webview_navigation(url, port, |external| {
                        record_link(external, &navigation)
                    })
                })
                .on_new_window(move |url, _| {
                    if route_webview_navigation(&url, port, |external| {
                        record_link(external, &popup)
                    }) {
                        NewWindowResponse::Allow
                    } else {
                        NewWindowResponse::Deny
                    }
                })
                .build()?;
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                let required = HashSet::from([
                    Observation::Bridge,
                    Observation::LicenseLink,
                    Observation::CommercialLicenseLink,
                    Observation::SameWindowLink,
                ]);
                let mut observed = HashSet::new();
                let deadline = Instant::now() + TIMEOUT;
                while let Ok(event) =
                    receiver.recv_timeout(deadline.saturating_duration_since(Instant::now()))
                {
                    if !observed.insert(event) {
                        observed.insert(Observation::Failure);
                        break;
                    }
                    if event == Observation::Failure || observed == required {
                        break;
                    }
                }
                let title_matches = handle.get_webview_window("main").and_then(|window| window.title().ok())
                    .as_deref() == Some("A synthetic project — Lixity");
                if observed == required && title_matches {
                    println!(
                        "Native WebView smoke passed: authenticated runtime IPC, bundled sample, license popups and same-window external links."
                    );
                    handle.exit(0);
                } else {
                    eprintln!("Native WebView smoke failed: observed {observed:?}");
                    handle.exit(1);
                }
            });
            Ok(())
        })
        .run(crate::desktop_context())?;
    Ok(())
}
