//! Local window geometry persistence (never stores manuscript text or project paths).

use crate::desktop_state::StateFile;
use serde::{Deserialize, Serialize};

static GEOMETRY: StateFile = StateFile::new("window-state.json", "window geometry");

pub const DEFAULT_WIDTH: f64 = 1340.0;
pub const DEFAULT_HEIGHT: f64 = 880.0;
pub const MIN_WIDTH: f64 = 760.0;
pub const MIN_HEIGHT: f64 = 560.0;
const MAX_WIDTH: f64 = 3840.0;
const MAX_HEIGHT: f64 = 2160.0;
const MAX_COORD: f64 = 10_000.0;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct WindowGeometry {
    #[serde(default = "default_schema")]
    pub schema_version: String,
    pub width: f64,
    pub height: f64,
    pub x: Option<f64>,
    pub y: Option<f64>,
    #[serde(default)]
    pub maximized: bool,
}

fn default_schema() -> String {
    "lixity-desktop-window-state/1".to_string()
}

impl Default for WindowGeometry {
    fn default() -> Self {
        Self {
            schema_version: default_schema(),
            width: DEFAULT_WIDTH,
            height: DEFAULT_HEIGHT,
            x: None,
            y: None,
            maximized: false,
        }
    }
}

impl WindowGeometry {
    pub fn sanitized(mut self) -> Self {
        self.schema_version = default_schema();
        self.width = if self.width.is_finite() {
            self.width.clamp(MIN_WIDTH, MAX_WIDTH)
        } else {
            DEFAULT_WIDTH
        };
        self.height = if self.height.is_finite() {
            self.height.clamp(MIN_HEIGHT, MAX_HEIGHT)
        } else {
            DEFAULT_HEIGHT
        };
        let valid_coord = |v: f64| v.is_finite() && (-MAX_COORD..=MAX_COORD).contains(&v);
        match (self.x, self.y) {
            (Some(x), Some(y)) if valid_coord(x) && valid_coord(y) => {}
            _ => {
                self.x = None;
                self.y = None;
            }
        }
        self
    }
}

pub fn load_window_geometry() -> WindowGeometry {
    GEOMETRY.read::<WindowGeometry>().sanitized()
}

pub fn save_window_geometry(geometry: WindowGeometry) {
    let _ = GEOMETRY.write(&geometry.sanitized());
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clamps_extreme_dimensions_and_invalid_coords() {
        let raw = WindowGeometry {
            schema_version: String::new(),
            width: 120.0,
            height: 99_999.0,
            x: Some(f64::NAN),
            y: Some(100.0),
            maximized: false,
        };
        let clean = raw.sanitized();
        assert_eq!(clean.width, MIN_WIDTH);
        assert_eq!(clean.height, MAX_HEIGHT);
        assert_eq!(clean.x, None);
        assert_eq!(clean.y, None);
        assert_eq!(clean.schema_version, "lixity-desktop-window-state/1");
    }

    #[test]
    fn preserves_valid_window_geometry_roundtrip() {
        let original = WindowGeometry {
            schema_version: default_schema(),
            width: 1440.0,
            height: 920.0,
            x: Some(80.0),
            y: Some(60.0),
            maximized: true,
        };
        let json = serde_json::to_string(&original).unwrap();
        let parsed: WindowGeometry = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.sanitized(), original);
    }
}
