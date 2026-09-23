"""lixity.status – Single source of truth for status codes, contract keys and enums.

Centralises every enum-like string that used to be scattered as literals across
the codebase: UI component states, narrative tense codes, paragraph severity
levels, NDA workflow statuses, and the JSON contract keys of the style passport
(structural diagnostics). Multilingual *labels* stay in ``language_data`` /
``PASSPORT_TEXTS`` — only the stable machine codes live here.
"""

from __future__ import annotations

from enum import Enum, IntEnum

__all__ = [
    "FLAG_MIN_SEVERITY",
    "PASSPORT_LABEL_SEGMENTED",
    "PASSPORT_LABEL_SHIFTED",
    "PASSPORT_LABEL_STRUCTURAL",
    "PASSPORT_LABEL_TRENDING",
    "SCHEMA_VERSION_ANALYZE",
    "SCHEMA_VERSION_STYLE",
    "STRUCTURAL_DIAGNOSTICS_KEY",
    "STYLE_SCHEMA_VERSION",
    "TENSE_MIXED",
    "TENSE_NEUTRAL",
    "TENSE_PAST",
    "TENSE_PRESENT",
    "ContractKeys",
    "NdaStatus",
    "Severity",
    "Status",
    "Tense",
]


# ---------------------------------------------------------------------------
# Schema versions (public JSON contracts)
# ---------------------------------------------------------------------------

SCHEMA_VERSION_ANALYZE = 2
"""analyze / profile contracts (language-neutral tense values)."""

SCHEMA_VERSION_STYLE = 4
"""style passport contract.

v4 exposes the structural diagnostics block under ``structural_diagnostics``
(PELT changepoints, Mann–Kendall trends, robust scales, tail index,
distribution shift, co-occurrence, keyness) with passport text label
``structural``.
"""

# Alias for call sites that treat the style schema as "the" passport version.
STYLE_SCHEMA_VERSION = SCHEMA_VERSION_STYLE


# ---------------------------------------------------------------------------
# JSON contract keys (style passport)
# ---------------------------------------------------------------------------

STRUCTURAL_DIAGNOSTICS_KEY = "structural_diagnostics"
"""Top-level passport key for the structural diagnostics block."""

# Passport *text* label keys (PASSPORT_TEXTS[lang][key]).
PASSPORT_LABEL_STRUCTURAL = "structural"
PASSPORT_LABEL_SEGMENTED = "segmented"
PASSPORT_LABEL_TRENDING = "trending"
PASSPORT_LABEL_SHIFTED = "shifted"


class ContractKeys:
    """Sub-keys of ``structural_diagnostics`` (stable JSON contract)."""

    CHANGEPOINTS = "changepoints"
    TRENDS = "trends"
    ROBUST_SCALES = "robust_scales"
    TAIL_INDEX = "tail_index"
    DISTRIBUTION_SHIFT = "distribution_shift"
    TRENDING_FEATURES = "trending_features"
    SEGMENTED_FEATURES = "segmented_features"
    SHIFTED_FEATURES = "shifted_features"
    COOCCURRENCE = "cooccurrence"
    KEYNESS = "keyness"


# ---------------------------------------------------------------------------
# UI component states (status_strip, CSS classes)
# ---------------------------------------------------------------------------


class Status(str, Enum):
    """Component health state used by ``status_strip`` and CSS."""

    OK = "ok"
    WARN = "warn"
    ERROR = "error"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Narrative tense (language-neutral codes; labels live in language_data)
# ---------------------------------------------------------------------------


class Tense(str, Enum):
    """Language-neutral tense codes (schema v2+)."""

    PRESENT = "present"
    PAST = "past"
    MIXED = "mixed"
    NEUTRAL = "neutral"


# Flat aliases for call sites that predate the Enum (same string values).
TENSE_PRESENT = Tense.PRESENT.value
TENSE_PAST = Tense.PAST.value
TENSE_MIXED = Tense.MIXED.value
TENSE_NEUTRAL = Tense.NEUTRAL.value


# ---------------------------------------------------------------------------
# Paragraph severity (0–3 friction scale)
# ---------------------------------------------------------------------------


class Severity(IntEnum):
    """Tense-friction severity of a paragraph (0–3)."""

    NEUTRAL = 0
    WATCH = 1
    NOTABLE = 2
    STRONG = 3


FLAG_MIN_SEVERITY = Severity.NOTABLE
"""Default editorial cut: severity ≥ 2 counts as flagged (1 = watch only)."""


# ---------------------------------------------------------------------------
# NDA workflow statuses (canonical wire values)
# ---------------------------------------------------------------------------


class NdaStatus(str, Enum):
    """Canonical NDA workflow status (stored value; labels in language_data)."""

    DRAFT = "entwurf"
    SENT = "versendet"
    CONFIRMED = "bestaetigt"
    SIGNED = "unterschrieben"

    @classmethod
    def all_values(cls) -> list[str]:
        """Ordered list of wire values for <select> population."""
        return [member.value for member in cls]
