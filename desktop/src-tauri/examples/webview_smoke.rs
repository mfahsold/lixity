#[cfg(target_os = "macos")]
fn main() -> Result<(), Box<dyn std::error::Error>> {
    lixity_desktop_lib::webview_smoke::run()
}

#[cfg(not(target_os = "macos"))]
fn main() {
    eprintln!("The hidden native WebView smoke test currently requires macOS.");
    std::process::exit(1);
}
