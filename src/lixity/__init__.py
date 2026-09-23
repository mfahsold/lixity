"""Lixity – Quantitative text linguistics, stylometry and self-calibrating style passports."""

from ._version import __version__
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
