"""Heatmap labels must remain readable across the entire fixed data palette."""

import unittest

from lixity.style_fingerprint import z_color
from lixity.ui.components import contrast_text


class TestHeatmapText(unittest.TestCase):
    def test_palette_contrast_including_extremes(self):
        for step in range(-250, 251):
            background = z_color(step / 100)
            channels = [int(background[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            linear = [v / 12.92 if v <= 0.04045 else ((v + .055) / 1.055) ** 2.4
                      for v in channels]
            luminance = sum(c * w for c, w in zip(linear, (.2126, .7152, .0722), strict=True))
            foreground = contrast_text(background)
            self.assertIn(foreground, ("#000000", "#ffffff"))
            ratio = (luminance + .05) / .05 if foreground == "#000000" else 1.05 / (luminance + .05)
            with self.subTest(background=background):
                self.assertGreaterEqual(ratio, 4.5)
