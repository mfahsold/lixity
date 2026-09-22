"""
scripts/engine
==============
Generische, modulare und wiederverwendbare Core-Engine für quantitative
Korpuslinguistik, Stilometrie und Dokumentations-Audits literarischer Manuskripte.
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
