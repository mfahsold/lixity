// Prevents a stray console window on Windows release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    lixity_desktop_lib::run();
}
