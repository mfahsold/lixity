//! Persistent desktop display preferences (never retains manuscript or research content).

use crate::desktop_state::StateFile;
use serde::{Deserialize, Deserializer, Serialize};
use std::collections::BTreeMap;

static PREFERENCES: StateFile = StateFile::new("preferences.json", "desktop preferences");

pub const MIN_ZOOM: f64 = 0.8;
pub const MAX_ZOOM: f64 = 1.6;
pub const DEFAULT_ZOOM: f64 = 1.0;
pub const ZOOM_STEP: f64 = 0.1;

/// Clamp and quantize a WebView zoom factor to the audited `[0.80, 1.60]` range.
pub fn clamp_zoom(factor: f64) -> f64 {
    if factor.is_finite() {
        ((factor.clamp(MIN_ZOOM, MAX_ZOOM)) * 100.0).round() / 100.0
    } else {
        DEFAULT_ZOOM
    }
}

/// Apply an incremental zoom delta (e.g. `+0.1` or `-0.1`) without floating-point drift.
pub fn step_zoom(current: f64, delta: f64) -> f64 {
    clamp_zoom(clamp_zoom(current) + delta)
}

const READER_SIZE_MIN: u8 = 16;
const READER_SIZE_MAX: u8 = 28;
const MAX_METRIC_ID: usize = 32;
const MAX_READER_METRICS: usize = 32;

#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
enum ReaderWidth {
    Narrow,
    Standard,
    Wide,
}

#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
enum ReaderSpacing {
    Compact,
    Standard,
    Relaxed,
}

/// The reader sends only changed fields. Rust merges them under the store lock
/// so an edit in one window does not replace another window's unrelated choices.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields, rename_all = "camelCase")]
pub struct ReaderPreferences {
    #[serde(skip_serializing_if = "Option::is_none")]
    size: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    width: Option<ReaderWidth>,
    #[serde(skip_serializing_if = "Option::is_none")]
    spacing: Option<ReaderSpacing>,
    #[serde(skip_serializing_if = "Option::is_none")]
    metric: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    comparison: Option<bool>,
    #[serde(skip_serializing_if = "BTreeMap::is_empty")]
    evidence_by_metric: BTreeMap<String, bool>,
}

fn valid_metric_id(id: &str) -> bool {
    // The renderer decides which measurements exist for the current document.
    // The host stores only bounded, language-neutral identifiers.
    id.len() <= MAX_METRIC_ID
        && id.as_bytes().first().is_some_and(u8::is_ascii_lowercase)
        && id
            .bytes()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'_')
}

impl ReaderPreferences {
    fn validated(mut self) -> Result<Self, String> {
        if self
            .metric
            .as_deref()
            .is_some_and(|id| !id.is_empty() && !valid_metric_id(id))
            || self.evidence_by_metric.len() > MAX_READER_METRICS
            || !self.evidence_by_metric.keys().all(|id| valid_metric_id(id))
        {
            return Err("Invalid reader measurement identifiers".to_string());
        }
        self.size = self
            .size
            .map(|size| size.clamp(READER_SIZE_MIN, READER_SIZE_MAX));
        Ok(self)
    }

    fn merged(mut self, changes: Self) -> Result<Self, String> {
        self.size = changes.size.or(self.size);
        self.width = changes.width.or(self.width);
        self.spacing = changes.spacing.or(self.spacing);
        self.metric = changes.metric.or(self.metric);
        self.comparison = changes.comparison.or(self.comparison);
        self.evidence_by_metric.extend(changes.evidence_by_metric);
        self.validated()
    }
}

fn deserialize_reader<'de, D: Deserializer<'de>>(
    deserializer: D,
) -> Result<Option<ReaderPreferences>, D::Error> {
    // A damaged reader entry must not discard theme, zoom and window choices.
    Ok(Option::<serde_json::Value>::deserialize(deserializer)?
        .and_then(|value| serde_json::from_value::<ReaderPreferences>(value).ok())
        .and_then(|reader| reader.validated().ok()))
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct DesktopPreferences {
    #[serde(default = "default_schema")]
    pub schema_version: String,
    #[serde(default)]
    pub theme: Option<String>,
    #[serde(default = "default_zoom")]
    pub zoom: f64,
    #[serde(default)]
    pub active_view: Option<String>,
    #[serde(default)]
    pub manuscript_split: Option<f64>,
    #[serde(
        default,
        deserialize_with = "deserialize_reader",
        skip_serializing_if = "Option::is_none"
    )]
    pub reader: Option<ReaderPreferences>,
}

fn default_schema() -> String {
    "lixity-desktop-preferences/1".to_string()
}

fn default_zoom() -> f64 {
    DEFAULT_ZOOM
}

impl Default for DesktopPreferences {
    fn default() -> Self {
        Self {
            schema_version: default_schema(),
            theme: None,
            zoom: DEFAULT_ZOOM,
            active_view: None,
            manuscript_split: None,
            reader: None,
        }
    }
}

impl DesktopPreferences {
    pub fn sanitized(mut self) -> Self {
        self.schema_version = default_schema();
        self.theme = self
            .theme
            .filter(|t| matches!(t.as_str(), "light" | "dark"));
        self.zoom = clamp_zoom(self.zoom);
        self.active_view = self
            .active_view
            .filter(|v| matches!(v.as_str(), "analysis" | "research" | "project"));
        self.manuscript_split = self
            .manuscript_split
            .filter(|v| v.is_finite())
            .map(|v| v.clamp(0.2, 0.8));
        self
    }

    pub fn apply_update(&mut self, key: &str, value: serde_json::Value) -> Result<(), String> {
        match key {
            "theme" => {
                if value.is_null() {
                    self.theme = None;
                } else if let Some(s) = value.as_str() {
                    if !matches!(s, "light" | "dark") {
                        return Err("Theme must be 'light' or 'dark'".to_string());
                    }
                    self.theme = Some(s.to_string());
                } else {
                    return Err("Theme must be a string or null".to_string());
                }
            }
            "zoom" => {
                let Some(num) = value.as_f64() else {
                    return Err("Zoom must be a finite number".to_string());
                };
                if !num.is_finite() {
                    return Err("Zoom must be a finite number".to_string());
                }
                self.zoom = clamp_zoom(num);
            }
            "active_view" => {
                if value.is_null() {
                    self.active_view = None;
                } else if let Some(s) = value.as_str() {
                    if !matches!(s, "analysis" | "research" | "project") {
                        return Err("Unknown workspace view".to_string());
                    }
                    self.active_view = Some(s.to_string());
                } else {
                    return Err("active_view must be a string or null".to_string());
                }
            }
            "manuscript_split" => {
                if value.is_null() {
                    self.manuscript_split = None;
                } else if let Some(num) = value.as_f64() {
                    if !num.is_finite() {
                        return Err("manuscript_split must be finite".to_string());
                    }
                    self.manuscript_split = Some(num.clamp(0.2, 0.8));
                } else {
                    return Err("manuscript_split must be a number or null".to_string());
                }
            }
            "reader" => {
                let changes: ReaderPreferences = serde_json::from_value(value)
                    .map_err(|_| "Invalid reader display preferences".to_string())?;
                self.reader = Some(self.reader.clone().unwrap_or_default().merged(changes)?);
            }
            _ => return Err(format!("Unsupported desktop preference key: {key}")),
        }
        Ok(())
    }
}

pub fn load_preferences() -> DesktopPreferences {
    PREFERENCES.read::<DesktopPreferences>().sanitized()
}

pub fn update_preference(
    key: &str,
    value: serde_json::Value,
) -> Result<DesktopPreferences, String> {
    PREFERENCES.update(|prefs: DesktopPreferences| {
        let mut prefs = prefs.sanitized();
        prefs.apply_update(key, value)?;
        Ok(prefs)
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sanitizes_and_validates_preference_updates() {
        let mut prefs = DesktopPreferences::default();
        prefs
            .apply_update("theme", serde_json::json!("dark"))
            .unwrap();
        prefs.apply_update("zoom", serde_json::json!(2.5)).unwrap();
        prefs
            .apply_update("active_view", serde_json::json!("research"))
            .unwrap();
        assert_eq!(prefs.theme.as_deref(), Some("dark"));
        assert_eq!(prefs.zoom, MAX_ZOOM);
        assert_eq!(prefs.active_view.as_deref(), Some("research"));

        assert!(prefs
            .apply_update("theme", serde_json::json!("neon"))
            .is_err());
        assert!(prefs
            .apply_update("unknown_key", serde_json::json!(1))
            .is_err());
    }

    #[test]
    fn clamps_and_steps_zoom_factors_without_drift() {
        assert_eq!(clamp_zoom(f64::NAN), DEFAULT_ZOOM);
        assert_eq!(clamp_zoom(f64::INFINITY), DEFAULT_ZOOM);
        assert_eq!(clamp_zoom(0.25), MIN_ZOOM);
        assert_eq!(clamp_zoom(3.5), MAX_ZOOM);
        assert_eq!(step_zoom(1.0, ZOOM_STEP), 1.1);
        assert_eq!(step_zoom(1.1, ZOOM_STEP), 1.2);
        assert_eq!(step_zoom(1.2, -ZOOM_STEP), 1.1);
        assert_eq!(step_zoom(MIN_ZOOM, -ZOOM_STEP), MIN_ZOOM);
        assert_eq!(step_zoom(MAX_ZOOM, ZOOM_STEP), MAX_ZOOM);
    }

    #[test]
    fn reader_updates_merge_apart_from_other_desktop_preferences() {
        let mut prefs: DesktopPreferences = serde_json::from_value(serde_json::json!({
            "schema_version": "lixity-desktop-preferences/1", "theme": "dark", "zoom": 1.2
        }))
        .unwrap();
        assert!(prefs.reader.is_none());
        prefs
            .apply_update(
                "reader",
                serde_json::json!({"size": 52, "metric": "asl", "evidenceByMetric": {"asl": true}}),
            )
            .unwrap();
        prefs
            .apply_update(
                "reader",
                serde_json::json!({
                    "metric": "", "width": "wide", "spacing": "relaxed", "comparison": false,
                    "evidenceByMetric": {"dialogue": false}
                }),
            )
            .unwrap();
        let persisted = serde_json::to_value(&prefs).unwrap();
        assert_eq!(
            persisted["reader"],
            serde_json::json!({
                "size": 28, "metric": "", "width": "wide", "spacing": "relaxed",
                "comparison": false, "evidenceByMetric": {"asl": true, "dialogue": false}
            })
        );
        assert_eq!(persisted["theme"], "dark");
        assert_eq!(persisted["zoom"], 1.2);
        assert_eq!(
            serde_json::from_value::<DesktopPreferences>(persisted).unwrap(),
            prefs
        );
    }

    #[test]
    fn malformed_reader_preferences_do_not_discard_valid_choices() {
        let mut prefs: DesktopPreferences = serde_json::from_value(serde_json::json!({
            "theme": "dark", "zoom": 1.2, "reader": {"width": "invalid"}
        }))
        .unwrap();
        assert_eq!(prefs.theme.as_deref(), Some("dark"));
        assert!(prefs.reader.is_none());
        prefs
            .apply_update("reader", serde_json::json!({"metric": "asl"}))
            .unwrap();
        let before = prefs.clone();
        for invalid in [
            serde_json::json!({"metric": "/private/manuscript.md"}),
            serde_json::json!({"evidenceByMetric": {"__proto__": true}}),
            serde_json::json!({"size": "19"}),
            serde_json::json!({"spacing": "wide"}),
            serde_json::json!({"source": "A sentence from the manuscript."}),
        ] {
            assert!(prefs.apply_update("reader", invalid).is_err());
            assert_eq!(prefs, before);
        }
    }
}
