"""Installation recipes must target an isolated, verified environment."""

import unittest
from pathlib import Path


class TestInstallation(unittest.TestCase):
    def test_install_recipes_create_and_verify_the_selected_environment(self):
        root = Path(__file__).resolve().parents[1]
        for target in ("install", "install-dev"):
            with self.subTest(target=target):
                recipe = (root / "Makefile").read_text(encoding="utf-8").split(
                    f"\n{target}:", 1
                )[1].split("\n\n", 1)[0]
                self.assertIn('-m venv "$(VENV)"', recipe)
                self.assertIn('"$(VPY)" -m pip install', recipe)
                self.assertIn('-m pip check', recipe)
                self.assertIn('-m lixity.cli --version', recipe)
