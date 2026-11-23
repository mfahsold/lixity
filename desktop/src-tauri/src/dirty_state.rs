//! Per-window dirty state and confirmed-close registry for the native CloseRequested guard.

use std::collections::hash_map::Entry;
use std::collections::HashMap;
use std::sync::Mutex;

#[derive(Clone, Copy, PartialEq)]
enum CloseDecision {
    Pending,
    Confirmed,
}

#[derive(Default)]
pub struct DirtyRegistry {
    windows: Mutex<HashMap<String, bool>>,
    close_decisions: Mutex<HashMap<String, CloseDecision>>,
}

impl DirtyRegistry {
    pub fn set_editor_dirty(&self, window_label: &str, dirty: bool) {
        if let Ok(mut map) = self.windows.lock() {
            map.insert(window_label.to_string(), dirty);
        }
    }

    pub fn begin_close_confirmation(&self, window_label: &str) -> bool {
        let Ok(mut decisions) = self.close_decisions.lock() else {
            return false;
        };
        let Entry::Vacant(entry) = decisions.entry(window_label.to_string()) else {
            return false;
        };
        entry.insert(CloseDecision::Pending);
        true
    }

    pub fn finish_close_confirmation(&self, window_label: &str, confirmed: bool) {
        if let Ok(mut decisions) = self.close_decisions.lock() {
            if confirmed {
                if let Some(decision) = decisions.get_mut(window_label) {
                    *decision = CloseDecision::Confirmed;
                }
            } else {
                decisions.remove(window_label);
            }
        }
    }

    pub fn awaiting_close_confirmation(&self, window_label: &str) -> bool {
        self.close_decisions
            .lock()
            .is_ok_and(|decisions| decisions.get(window_label) == Some(&CloseDecision::Pending))
    }

    pub fn take_force_closing(&self, window_label: &str) -> bool {
        let Ok(mut decisions) = self.close_decisions.lock() else {
            return false;
        };
        let confirmed = decisions.get(window_label) == Some(&CloseDecision::Confirmed);
        if confirmed {
            decisions.remove(window_label);
        }
        confirmed
    }

    pub fn remove_window(&self, window_label: &str) {
        if let Ok(mut map) = self.windows.lock() {
            map.remove(window_label);
        }
        self.finish_close_confirmation(window_label, false);
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tracks_dirty_windows_and_one_shot_force_close() {
        let reg = DirtyRegistry::default();
        assert!(!reg.any_dirty());
        reg.set_editor_dirty("main", true);
        assert!(reg.is_window_dirty("main"));
        assert!(reg.any_dirty());

        assert!(reg.begin_close_confirmation("main"));
        assert!(reg.awaiting_close_confirmation("main"));
        assert!(!reg.begin_close_confirmation("main"));
        assert!(!reg.take_force_closing("main"));
        reg.finish_close_confirmation("main", false);
        assert!(!reg.awaiting_close_confirmation("main"));
        assert!(reg.begin_close_confirmation("main"));
        reg.finish_close_confirmation("main", true);
        assert!(!reg.awaiting_close_confirmation("main"));
        assert!(reg.take_force_closing("main"));
        assert!(!reg.take_force_closing("main"));

        reg.remove_window("main");
        assert!(!reg.is_window_dirty("main"));
        assert!(!reg.any_dirty());
    }
}
