//! Persistent desktop display preferences (never retains manuscript or research content).

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

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
            _ => return Err(format!("Unsupported desktop preference key: {key}")),
        }
        Ok(())
    }
}

fn state_file_path() -> Result<PathBuf, String> {
    let base = dirs::data_local_dir()
        .or_else(dirs::config_dir)
        .ok_or_else(|| "Unable to resolve local application state directory".to_string())?;
    let dir = base.join("lixity").join("desktop");
    fs::create_dir_all(&dir).map_err(|e| format!("Failed creating desktop state dir: {e}"))?;
    Ok(dir.join("preferences.json"))
}

pub fn load_preferences() -> DesktopPreferences {
    let Ok(path) = state_file_path() else {
        return DesktopPreferences::default();
    };
    let Ok(raw) = fs::read_to_string(path) else {
        return DesktopPreferences::default();
    };
    serde_json::from_str::<DesktopPreferences>(&raw)
        .map(DesktopPreferences::sanitized)
        .unwrap_or_default()
}

pub fn update_preference(key: &str, value: serde_json::Value) -> Result<DesktopPreferences, String> {
    let mut prefs = load_preferences();
    prefs.apply_update(key, value)?;
    let clean = prefs.sanitized();
    let dest = state_file_path()?;
    let serialized = serde_json::to_string_pretty(&clean).map_err(|e| e.to_string())?;
    let tmp = dest.with_extension("json.tmp");
    fs::write(&tmp, serialized).map_err(|e| format!("Failed writing desktop preferences: {e}"))?;
    fs::rename(&tmp, &dest).map_err(|e| format!("Failed replacing desktop preferences: {e}"))?;
    Ok(clean)
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
}
