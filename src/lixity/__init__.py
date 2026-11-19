"""Lixity – Quantitative text linguistics, stylometry and self-calibrating style passports."""
from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from ._version import __version__

if TYPE_CHECKING:
    from .analyzer import CorpusAnalyzer
    from .formatters import ReportFormatter
    from .io import FileUtils
    from .models import (
        ChapterMetrics,
        CorpusAuditReport,
        CorpusConfig,
        CorpusMetrics,
        DossierStatus,
        SentenceDistribution,
    )
    from .style_fingerprint import StyleFingerprint

_EXPORTS: dict[str, tuple[str, str]] = {
    "ChapterMetrics": (".models", "ChapterMetrics"),
    "CorpusAnalyzer": (".analyzer", "CorpusAnalyzer"),
    "CorpusAuditReport": (".models", "CorpusAuditReport"),
    "CorpusConfig": (".models", "CorpusConfig"),
    "CorpusMetrics": (".models", "CorpusMetrics"),
    "DossierStatus": (".models", "DossierStatus"),
    "FileUtils": (".io", "FileUtils"),
    "ReportFormatter": (".formatters", "ReportFormatter"),
    "SentenceDistribution": (".models", "SentenceDistribution"),
    "StyleFingerprint": (".style_fingerprint", "StyleFingerprint"),
}

__all__ = [
    "ChapterMetrics",
    "CorpusAnalyzer",
    "CorpusAuditReport",
    "CorpusConfig",
    "CorpusMetrics",
    "DossierStatus",
    "FileUtils",
    "ReportFormatter",
    "SentenceDistribution",
    "StyleFingerprint",
    "__version__",
]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    value = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
