"""lixity.visualizer – Compatibility shim for the centralised UI package.

The dashboard implementation moved to :mod:`lixity.ui`; this module keeps
older imports working (``from lixity.visualizer import render_dashboard``).
"""

from .ui import render_dashboard, render_style_report

__all__ = ["render_dashboard", "render_style_report"]
