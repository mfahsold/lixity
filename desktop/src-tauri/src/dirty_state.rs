//! Per-window dirty state and confirmed-close registry for the native CloseRequested guard.

use std::collections::{HashMap, HashSet};
use std::sync::Mutex;

#[derive(Default)]
pub struct DirtyRegistry {
    windows: Mutex<HashMap<String, bool>>,
    force_closing: Mutex<HashSet<String>>,
}

impl DirtyRegistry {
    pub fn set_editor_dirty(&self, window_label: &str, dirty: bool) {
        if let Ok(mut map) = self.windows.lock() {
            map.insert(window_label.to_string(), dirty);
        }
    }

    pub fn mark_force_closing(&self, window_label: &str) {
        if let Ok(mut set) = self.force_closing.lock() {
            set.insert(window_label.to_string());
        }
    }

    pub fn take_force_closing(&self, window_label: &str) -> bool {
        self.force_closing
            .lock()
            .ok()
            .map(|mut set| set.remove(window_label))
            .unwrap_or(false)
    }

    pub fn remove_window(&self, window_label: &str) {
        if let Ok(mut map) = self.windows.lock() {
            map.remove(window_label);
        }
        if let Ok(mut set) = self.force_closing.lock() {
            set.remove(window_label);
        }
    }

    pub fn is_window_dirty(&self, window_label: &str) -> bool {
        self.windows
            .lock()
            .ok()
            .and_then(|map| map.get(window_label).copied())
            .unwrap_or(false)
    }

    pub fn any_dirty(&self) -> bool {
        self.windows
            .lock()
            .ok()
            .map(|map| map.values().any(|&dirty| dirty))
            .unwrap_or(false)
    }
}
