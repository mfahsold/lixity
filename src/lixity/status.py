"""lixity.status – Single source of truth for status codes, contract keys and enums.

Centralises every enum-like string that used to be scattered as literals across
the codebase: UI component states, narrative tense codes, paragraph severity
levels, and the JSON contract keys of the style passport
(structural diagnostics). Multilingual *labels* stay in ``language_data``; the
passport text table ``PASSPORT_TEXTS`` lives in ``style_fingerprint`` — only the
stable machine codes live here.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum, IntEnum
from types import MappingProxyType

__all__ = [
    "DEFAULT_FDR_METHOD",
    "DEFAULT_FDR_Q",
    "DEFAULT_HOST",
    "DEFAULT_MIN_CHAPTERS",
    "DEFAULT_PORT",
    "DEFAULT_Z_MILD",
    "DEFAULT_Z_STRONG",
    "DIM_SCORE_THRESHOLD",
    "FEATURE_LAYERS",
    "FLAG_MIN_SEVERITY",
    "LANGUAGE_CHOICES",
    "LANGUAGE_CODES",
    "LAYER_FEATURES",
    "PASSPORT_LABEL_SEGMENTED",
    "PASSPORT_LABEL_SHIFTED",
    "PASSPORT_LABEL_STRUCTURAL",
    "PASSPORT_LABEL_TRENDING",
    "SCHEMA_VERSION_ANALYZE",
    "SCHEMA_VERSION_STYLE",
    "STRUCTURAL_DIAGNOSTICS_KEY",
    "TENSE_MIXED",
    "TENSE_NEUTRAL",
    "TENSE_PAST",
    "TENSE_PRESENT",
    "THRESHOLD_DEFAULTS",
    "ContractKeys",
    "ManuscriptFlag",
    "ManuscriptState",
    "Severity",
    "Status",
    "Tense",
]


# ---------------------------------------------------------------------------
# Schema versions (public JSON contracts)
# ---------------------------------------------------------------------------

SCHEMA_VERSION_ANALYZE = 2
"""analyze / profile contracts (language-neutral tense values)."""

SCHEMA_VERSION_STYLE = 5
"""style passport contract.

v5 replaces the exchangeability claim and averaged lag in
``baseline_diagnostics`` with per-feature exploratory order indicators and
explicit coverage. v4 exposed ``structural_diagnostics`` (guarded-cost
changepoints, Mann–Kendall trends, robust scales, tail index, distribution
shift, co-occurrence, keyness) with passport text label ``structural``.
"""


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
    SEGMENTATION_UNAVAILABLE = "segmentation_unavailable"
    DISTRIBUTION_UNAVAILABLE = "distribution_unavailable"
    DISTRIBUTION_INCOMPLETE = "distribution_incomplete"
    TREND_INCOMPLETE = "trend_incomplete"
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
# Manuscript review (research anchors; labels live in workspace_labels)
# ---------------------------------------------------------------------------


class ManuscriptState(str, Enum):
    """Anchor resolution state of a saved manuscript association.

    ``resolved`` keeps the pinned identity; ``moved`` and ``adjusted`` stay
    resolvable but unpinned (moved paragraph, or edited paragraph with an
    unchanged quote); ``ambiguous`` and ``changed`` need review before any
    re-pin; ``unavailable`` means the source cannot be read.
    """

    RESOLVED = "resolved"
    MOVED = "moved"
    ADJUSTED = "adjusted"
    AMBIGUOUS = "ambiguous"
    CHANGED = "changed"
    UNAVAILABLE = "unavailable"


class ManuscriptFlag(str, Enum):
    """Structural review flags on a saved manuscript association."""

    SOURCE_CHANGED = "source_changed"
    SOURCE_MISSING = "source_missing"
    SOURCE_UNREADABLE = "source_unreadable"
    CLAIM_CHANGED = "claim_changed"
    CLAIM_WITHDRAWN = "claim_withdrawn"
    ANCHOR_MOVED = "anchor_moved"
    ANCHOR_ADJUSTED = "anchor_adjusted"
    ANCHOR_AMBIGUOUS = "anchor_ambiguous"
    ANCHOR_CHANGED = "anchor_changed"


#: Local dashboard bind defaults shared by CLI, config and server.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

#: Ordered language codes with a complete profile (without "auto").
LANGUAGE_CODES: tuple[str, ...] = ("de", "en", "fr", "es", "it", "pt", "nl", "generic")
#: Accepted language selectors, including explicit detection.
LANGUAGE_CHOICES: tuple[str, ...] = ("auto", *LANGUAGE_CODES)

#: Built-in heuristic threshold defaults shared by CLI, service and style_fingerprint.
DEFAULT_Z_MILD: float = 2.5
DEFAULT_Z_STRONG: float = 3.5
DEFAULT_FDR_Q: float = 0.05
DEFAULT_FDR_METHOD: str = "bh"
DEFAULT_MIN_CHAPTERS: int = 2
DIM_SCORE_THRESHOLD: float = 2.5

THRESHOLD_DEFAULTS: Mapping[str, float | int | str] = MappingProxyType({
    "z_mild": DEFAULT_Z_MILD,
    "z_strong": DEFAULT_Z_STRONG,
    "fdr_q": DEFAULT_FDR_Q,
    "fdr_method": DEFAULT_FDR_METHOD,
    "min_chapters": DEFAULT_MIN_CHAPTERS,
    "dim_score_threshold": DIM_SCORE_THRESHOLD,
    "flag_min_severity": int(FLAG_MIN_SEVERITY),
})

#: Paragraph layer CLI/UI keys mapped to chapter-level style feature names.
LAYER_FEATURES: dict[str, str] = {
    "asl": "asl",
    "function": "function_word_pct",
    "dialogue": "dialog_pct",
    "filter": "filter_density",
    "sensory": "sensory_density",
    "modal": "modal_density",
    "nominal": "nominalization_density",
    "passive": "passive_density",
}

#: Chapter-level style features with a corresponding paragraph layer.
FEATURE_LAYERS: Mapping[str, str] = MappingProxyType({field: layer for layer, field in LAYER_FEATURES.items()})
