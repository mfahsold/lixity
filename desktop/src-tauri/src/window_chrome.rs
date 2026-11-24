//! Native workspace title and appearance.

use tauri::Theme;

const PRODUCT: &str = "Lixity";

pub(crate) fn workspace_title(project: &str) -> String {
    let title = project
        .chars()
        .map(|character| {
            if character.is_control() {
                ' '
            } else {
                character
            }
        })
        .collect::<String>();
    let title: String = title.trim().chars().take(120).collect();
    if title.is_empty() || title == PRODUCT {
        PRODUCT.to_owned()
    } else {
        format!("{title} — {PRODUCT}")
    }
}

#[cfg(target_os = "macos")]
pub(crate) fn native_title_bar<'a, R: tauri::Runtime, M: tauri::Manager<R>>(
    builder: tauri::WebviewWindowBuilder<'a, R, M>,
) -> tauri::WebviewWindowBuilder<'a, R, M> {
    builder.title_bar_style(tauri::TitleBarStyle::Transparent)
}

pub(crate) fn preferred_theme(theme: Option<&str>) -> Option<Theme> {
    match theme {
        Some("light") => Some(Theme::Light),
        Some("dark") => Some(Theme::Dark),
        _ => None,
    }
}

#[cfg(target_os = "macos")]
pub(crate) fn backdrop(theme: Theme) -> Option<tauri::window::Color> {
    const TOKENS: &str = include_str!("../../../src/lixity/ui/assets/design-tokens.css");
    let token = if theme == Theme::Dark {
        "--bg-dark:"
    } else {
        "--bg-light:"
    };
    TOKENS.lines().find_map(|line| {
        line.trim_start()
            .strip_prefix(token)?
            .trim()
            .trim_end_matches(';')
            .parse()
            .ok()
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn titles_use_the_same_rules_for_new_and_reused_windows() {
        assert_eq!(workspace_title(" \n Lixity \t"), "Lixity");
        assert_eq!(
            workspace_title("  Über den Berg  "),
            "Über den Berg — Lixity"
        );
        assert_eq!(workspace_title("\0\r\t"), "Lixity");
        assert_eq!(
            workspace_title(&"é".repeat(140)),
            format!("{} — Lixity", "é".repeat(120))
        );
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn macos_backdrop_uses_opaque_workspace_tokens() {
        let light = backdrop(Theme::Light).expect("light background token");
        let dark = backdrop(Theme::Dark).expect("dark background token");
        assert_ne!(light, dark);
        assert_eq!(light.3, 255);
        assert_eq!(dark.3, 255);
    }
}
