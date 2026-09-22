"""lixity.ui – Centralised dashboard UI (markup, styles, scripts, components).

Everything the single-file dashboard needs lives in this package:

- ``dashboard``  – the renderer (``render_dashboard`` / ``render_style_report``)
- ``components`` – reusable markup builders (KPI tiles, band chart, loadings)
- ``assets``     – the stylesheet and the micro-interaction script

``lixity.visualizer`` remains as a thin compatibility shim.
"""

from .dashboard import render_dashboard, render_style_report

__all__ = ["render_dashboard", "render_style_report"]
