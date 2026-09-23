"""Layout presets: page geometry and typographic leading defaults.

Renderer-free: asserts configuration values only (no Cairo/Pango in pytest).
"""

import unittest

from lixity.layout import BookLayoutConfig


class TestBookLayoutPresets(unittest.TestCase):
    """BookLayoutConfig.from_preset exposes stable publication defaults."""

    TARGET_LINE_SPACING = 0.94  # approx 1.50x leading (Palatino-class serifs)

    def test_taschenbuch_default_line_spacing(self) -> None:
        cfg = BookLayoutConfig.from_preset("taschenbuch")
        self.assertEqual(cfg.line_spacing, self.TARGET_LINE_SPACING)
        self.assertEqual(cfg.font_size_body, 8.5)
        self.assertTrue(cfg.justify_body)
        self.assertTrue(cfg.is_spread)

    def test_mobile_line_spacing(self) -> None:
        cfg = BookLayoutConfig.from_preset("mobile")
        self.assertEqual(cfg.line_spacing, self.TARGET_LINE_SPACING)
        self.assertEqual(cfg.font_size_body, 8.8)
        self.assertFalse(cfg.justify_body)

    def test_a4_line_spacing_is_explicit(self) -> None:
        cfg = BookLayoutConfig.from_preset("a4")
        self.assertEqual(cfg.line_spacing, self.TARGET_LINE_SPACING)
        self.assertEqual(cfg.font_size_body, 12.0)
        self.assertTrue(cfg.show_line_numbers)

    def test_unknown_preset_falls_back_to_taschenbuch(self) -> None:
        cfg = BookLayoutConfig.from_preset("does-not-exist")
        self.assertEqual(cfg.line_spacing, self.TARGET_LINE_SPACING)
        self.assertEqual(cfg.font_size_body, 8.5)

    def test_line_spacing_factor_targets_1_5x(self) -> None:
        # Empirically (Pango + Palatino): gap/font_size ~= factor * 1.6.
        # 0.94 * 1.6 = 1.504 ~= 1.50x leading across 12 / 8.8 / 8.5 pt.
        for preset in ("a4", "taschenbuch", "mobile"):
            cfg = BookLayoutConfig.from_preset(preset)
            self.assertIsNotNone(cfg.line_spacing)
            if cfg.line_spacing is None:  # pragma: no cover - guarded by assertIsNotNone
                continue
            effective = cfg.line_spacing * 1.6
            self.assertAlmostEqual(effective, 1.50, places=2)


if __name__ == "__main__":
    unittest.main()
