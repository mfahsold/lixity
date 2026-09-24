"""Screenshot extraction selects panels, not incidental label text."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.make_screenshots import _extract_section


class TestScreenshotExtraction(unittest.TestCase):
    def test_selects_exact_panel_id(self):
        document = (
            '<html lang="en"><style>body { margin: 0; }</style>'
            '<section class="panel" id="heatmap">markers elsewhere</section>'
            '<section class="panel" id="markers">actual markers</section>'
            '<script>window.ready = true;</script></html>'
        )
        extracted = _extract_section(document, "markers")
        self.assertIn('id="markers"', extracted)
        self.assertNotIn('id="heatmap"', extracted)
        self.assertIn("window.ready = true", extracted)

    def test_missing_panel_fails_explicitly(self):
        with self.assertRaises(SystemExit):
            _extract_section('<html lang="en"><style></style></html>', "missing")
