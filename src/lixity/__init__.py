"""
scripts/engine
==============
Generic, modular and reusable core engine for quantitative
corpus linguistics, stylometry and documentation audits of literary manuscripts.
"""

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
]

__version__ = "1.2.0"
