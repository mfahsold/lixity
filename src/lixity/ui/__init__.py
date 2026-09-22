"""lixity.ui – Centralised dashboard UI (markup, styles, scripts, components).

Everything the single-file dashboard needs lives in this package:

- ``dashboard``  – the renderer (``render_dashboard``)
- ``components`` – reusable markup builders (KPI tiles, band chart, loadings)
- ``assets``     – the stylesheet and the micro-interaction script
"""

from .dashboard import render_dashboard

__all__ = ["render_dashboard"]
