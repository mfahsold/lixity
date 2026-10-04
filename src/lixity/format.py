"""lixity.format – Locale-aware numbers and literal text for reports and dashboards.

One source of truth for decimal and thousands separators: German-style
comma decimals for de/es/it/pt/nl, narrow-space grouping for French,
Anglo-American defaults for English/generic.
"""

from __future__ import annotations

import unicodedata

# (thousands separator, decimal separator) per language profile.
NUMBER_STYLES: dict[str, tuple[str, str]] = {
    "de": (".", ","),
    "es": (".", ","),
    "it": (".", ","),
    "pt": (".", ","),
    "nl": (".", ","),
    "fr": ("\u202f", ","),
    "en": (",", "."),
    "generic": (",", "."),
}


def safe_text(value: object) -> str:
    """Show data literally, with terminal and Unicode formatting controls escaped."""
    return "".join(
        char.encode("unicode_escape").decode("ascii")
        if unicodedata.category(char) in ("Cc", "Cf") else char
        for char in str(value)
    )


def num(value: float, language_key: str = "en", decimals: int = 1, signed: bool = False) -> str:
    """Formats a number with the separators of the active language profile."""
    thousands, decimal = NUMBER_STYLES.get(language_key, NUMBER_STYLES["generic"])
    text = f"{value:+,.{decimals}f}" if signed else f"{value:,.{decimals}f}"
    return text.replace(",", "\x00").replace(".", decimal).replace("\x00", thousands)


def pct(value: float, language_key: str = "en", decimals: int = 1) -> str:
    """Percentage with typographic spacing (space before % outside English)."""
    suffix = "%" if language_key in ("en", "generic") else " %"
    return num(value, language_key, decimals) + suffix
