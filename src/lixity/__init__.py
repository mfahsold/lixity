"""
scripts/engine
==============
Generic, modular and reusable core engine for quantitative
corpus linguistics, stylometry and documentation audits of literary manuscripts.
"""

from .models import (
    CorpusConfig,
    SentenceDistribution,
    ChapterMetrics,
    CorpusMetrics,
    DossierStatus,
    CorpusAuditReport,
)
from .io import FileUtils
from .analyzer import CorpusAnalyzer
from .formatters import ReportFormatter

__all__ = [
    "CorpusConfig",
    "SentenceDistribution",
    "ChapterMetrics",
    "CorpusMetrics",
    "DossierStatus",
    "CorpusAuditReport",
    "FileUtils",
    "CorpusAnalyzer",
    "ReportFormatter",
]

__version__ = "1.0.0"
