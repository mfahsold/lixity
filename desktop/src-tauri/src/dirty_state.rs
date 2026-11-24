//! Per-window editor and close-request state for the native close guard.

use std::collections::hash_map::Entry;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

/// Identity of one close attempt, independent of a reusable window label.
#[derive(Clone)]
pub(crate) struct CloseAttempt(Arc<()>);

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum AudioJobStatus {
    Idle,
    Active,
    Unavailable,
}

pub(crate) enum CloseRequest {
    Evaluate(CloseAttempt, Option<AudioJobStatus>),
    Authorized,
    KeepOpen,
}

#[derive(Clone, Copy)]
enum CloseDecision {
    Pending,
    AudioChecked(AudioJobStatus),
    Confirmed,
    Closing,
}

struct WindowCloseRequest {
    attempt: CloseAttempt,
    decision: CloseDecision,
}

#[derive(Default)]
pub struct DirtyRegistry {
    windows: Mutex<HashMap<String, bool>>,
    close_requests: Mutex<HashMap<String, WindowCloseRequest>>,
}

impl DirtyRegistry {
    pub fn set_editor_dirty(&self, window_label: &str, dirty: bool) {
        if let Ok(mut map) = self.windows.lock() {
            map.insert(window_label.to_string(), dirty);
        }
    }

    pub(crate) fn request_close(&self, window_label: &str) -> CloseRequest {
        let Ok(mut requests) = self.close_requests.lock() else {
            return CloseRequest::KeepOpen;
        };
        match requests.entry(window_label.to_string()) {
            Entry::Vacant(entry) => {
                let attempt = CloseAttempt(Arc::new(()));
                entry.insert(WindowCloseRequest {
                    attempt: attempt.clone(),
                    decision: CloseDecision::Pending,
                });
                CloseRequest::Evaluate(attempt, None)
            }
            Entry::Occupied(mut entry) => {
                let request = entry.get_mut();
                match request.decision {
                    CloseDecision::Pending | CloseDecision::Closing => CloseRequest::KeepOpen,
                    CloseDecision::AudioChecked(status) => {
                        request.decision = CloseDecision::Pending;
                        CloseRequest::Evaluate(request.attempt.clone(), Some(status))
                    }
                    CloseDecision::Confirmed => {
                        request.decision = CloseDecision::Closing;
                        CloseRequest::Authorized
                    }
                }
            }
        }
    }

    pub(crate) fn audio_checked(
        &self,
        window_label: &str,
        attempt: &CloseAttempt,
        status: AudioJobStatus,
    ) -> bool {
        self.resolve_pending(window_label, attempt, CloseDecision::AudioChecked(status))
    }

    pub(crate) fn confirm_close(&self, window_label: &str, attempt: &CloseAttempt) -> bool {
        self.resolve_pending(window_label, attempt, CloseDecision::Confirmed)
    }

    pub(crate) fn commit_close(&self, window_label: &str, attempt: &CloseAttempt) -> bool {
        self.resolve_pending(window_label, attempt, CloseDecision::Closing)
    }

    fn resolve_pending(
        &self,
        window_label: &str,
        attempt: &CloseAttempt,
        decision: CloseDecision,
    ) -> bool {
        let Ok(mut requests) = self.close_requests.lock() else {
            return false;
        };
        let Some(request) = requests.get_mut(window_label) else {
            return false;
        };
        if !Arc::ptr_eq(&request.attempt.0, &attempt.0)
            || !matches!(request.decision, CloseDecision::Pending)
        {
            return false;
        }
        request.decision = decision;
        true
    }

    pub(crate) fn cancel_close(&self, window_label: &str, attempt: &CloseAttempt) {
        if let Ok(mut requests) = self.close_requests.lock() {
            if requests.get(window_label).is_some_and(|request| {
                Arc::ptr_eq(&request.attempt.0, &attempt.0)
                    && !matches!(request.decision, CloseDecision::Closing)
            }) {
                requests.remove(window_label);
            }
        }
    }

    pub(crate) fn is_closing(&self, window_label: &str) -> bool {
        self.close_requests.lock().is_ok_and(|requests| {
            requests.get(window_label).is_some_and(|request| {
                matches!(
                    request.decision,
                    CloseDecision::Confirmed | CloseDecision::Closing
                )
            })
        })
    }

    pub fn remove_window(&self, window_label: &str) {
        if let Ok(mut map) = self.windows.lock() {
            map.remove(window_label);
        }
        if let Ok(mut requests) = self.close_requests.lock() {
            requests.remove(window_label);
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

#[cfg(test)]
mod tests {
    use super::*;

    fn request(reg: &DirtyRegistry, label: &str) -> CloseAttempt {
        let CloseRequest::Evaluate(attempt, None) = reg.request_close(label) else {
            panic!("expected a new close attempt");
        };
        attempt
    }

    #[test]
    fn tracks_dirty_windows_and_one_shot_force_close() {
        let reg = DirtyRegistry::default();
        assert!(!reg.any_dirty());
        reg.set_editor_dirty("main", true);
        assert!(reg.is_window_dirty("main"));
        assert!(reg.any_dirty());

        let first = request(&reg, "main");
        assert!(matches!(reg.request_close("main"), CloseRequest::KeepOpen));
        assert!(!reg.is_closing("main"));
        reg.cancel_close("main", &first);

        let retry = request(&reg, "main");
        assert!(reg.confirm_close("main", &retry));
        assert!(reg.is_closing("main"));
        assert!(matches!(
            reg.request_close("main"),
            CloseRequest::Authorized
        ));
        assert!(matches!(reg.request_close("main"), CloseRequest::KeepOpen));

        reg.remove_window("main");
        assert!(!reg.is_window_dirty("main"));
        assert!(!reg.any_dirty());
    }

    #[test]
    fn resumed_audio_check_carries_its_result_once() {
        let reg = DirtyRegistry::default();
        let attempt = request(&reg, "main");
        assert!(matches!(reg.request_close("main"), CloseRequest::KeepOpen));
        assert!(reg.audio_checked("main", &attempt, AudioJobStatus::Unavailable));

        let CloseRequest::Evaluate(resumed, Some(AudioJobStatus::Unavailable)) =
            reg.request_close("main")
        else {
            panic!("expected the unavailable audio status");
        };
        assert!(matches!(reg.request_close("main"), CloseRequest::KeepOpen));
        reg.cancel_close("main", &resumed);
        request(&reg, "main");
    }

    #[test]
    fn old_callbacks_cannot_resolve_or_cancel_a_reopened_window() {
        let reg = DirtyRegistry::default();
        let old = request(&reg, "main");
        assert!(reg.commit_close("main", &old));
        assert!(reg.is_closing("main"));
        assert!(!reg.is_closing("project-1"));
        reg.remove_window("main");

        let fresh = request(&reg, "main");
        reg.cancel_close("main", &old);
        assert!(!reg.audio_checked("main", &old, AudioJobStatus::Idle));
        assert!(!reg.confirm_close("main", &old));
        assert!(reg.confirm_close("main", &fresh));
    }
}
