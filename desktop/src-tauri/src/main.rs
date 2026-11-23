// Prevents a stray console window on Windows release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

/// Mitigate WebKitGTK 4.1 blank-window / Wayland protocol error 71 regressions
/// on Linux systems running Wayland with the proprietary NVIDIA driver.
/// Users can still override explicitly by setting `WEBKIT_DISABLE_DMABUF_RENDERER`.
#[cfg(target_os = "linux")]
fn apply_linux_webkit_workarounds() {
    let on_wayland = std::env::var_os("WAYLAND_DISPLAY").is_some()
        || std::env::var("XDG_SESSION_TYPE")
            .map(|v| v.eq_ignore_ascii_case("wayland"))
            .unwrap_or(false);
    let has_nvidia = std::path::Path::new("/proc/driver/nvidia/version").exists();
    if on_wayland && has_nvidia && std::env::var_os("WEBKIT_DISABLE_DMABUF_RENDERER").is_none() {
        std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");
    }
}

fn main() {
    #[cfg(target_os = "linux")]
    apply_linux_webkit_workarounds();

    lixity_desktop_lib::run();
}
