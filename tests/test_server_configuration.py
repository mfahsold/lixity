"""Server defaults and CLI configuration use the shared project contract."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lixity.cli import main
from lixity.server import build_server_dashboard


class TestServerConfiguration(unittest.TestCase):
    def test_invalid_character_settings_are_visible_instead_of_falling_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manuscript = root / "manuscript.md"
            manuscript.write_text("## One\n\nMara waits.\n")
            (root / "lixity.toml").write_text('names = ["Legacy"]\n[characters.Mara]\npov_in_chapters = [2]\n')
            html, _ = build_server_dashboard(str(manuscript), project_root=root)
            panel = html.split('id="characters"', 1)[1].split('</section>', 1)[0]
            self.assertIn('role="status"', panel)
            self.assertIn('Declared POV chapters no longer match', panel)
            self.assertNotIn('Legacy', panel)

    def test_character_profiles_belong_to_selected_root_and_second_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            imported = root / "exports"
            imported.mkdir()
            manuscript = imported / "manuscript.md"
            manuscript.write_text("## One\n\nMara waits.\n\n## Two\n\nShe leaves.\n")
            (root / "lixity.toml").write_text('[characters.Mara]\npov_in_chapters = [2]\n')
            (imported / "lixity.toml").write_text('[characters.Other]\n')
            html, _ = build_server_dashboard(str(manuscript), project_root=root)
            panel = html.split('id="characters"', 1)[1].split('</section>', 1)[0]
            self.assertIn('Mara', panel)
            self.assertNotIn('Other', panel)
            self.assertIn('Declared POV', panel)
            second = root / "second"
            second.mkdir()
            (second / "lixity.toml").write_text('names = ["Legacy"]\n[characters]\n')
            html, _ = build_server_dashboard(str(manuscript), project_root=second)
            self.assertNotIn('id="characters"', html)

    def test_dashboard_defaults_to_english_with_explicit_detection_available(self):
        with tempfile.TemporaryDirectory() as directory:
            manuscript = Path(directory) / "manuscript.md"
            manuscript.write_text(
                "## Eins\n\nIch gehe und ich sehe das Haus. Die Tür ist offen. "
                "Der Regen fällt auf die Straße und ich warte auf den Zug.\n",
                encoding="utf-8",
            )
            _, default_info = build_server_dashboard(str(manuscript))
            _, detected_info = build_server_dashboard(str(manuscript), language="auto")
            self.assertEqual(default_info["language_key"], "en")
            self.assertEqual(detected_info["language_key"], "de")

    def test_serve_without_a_project_uses_english_unless_requested(self):
        for flags, expected in (([], "en"), (["--language", "de"], "de"), (["--language", "auto"], "auto")):
            with self.subTest(flags=flags):
                with patch("lixity.server.run_server") as run:
                    self.assertEqual(main(["serve", "--no-project", *flags]), 0)
                self.assertEqual(run.call_args.kwargs["language"], expected)

    def test_serve_resolves_configuration_from_the_explicit_project(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "lixity.toml").write_text(
                'language = "fr"\ntitle = "Project settings"\nfdr_q = 0.02\n', encoding="utf-8",
            )
            for flags, expected in (([], "fr"), (["--language", "en"], "en"), (["--language", "auto"], "auto")):
                with self.subTest(flags=flags):
                    with patch("lixity.server.run_server") as run:
                        self.assertEqual(main(["serve", str(project), *flags]), 0)
                    self.assertEqual(run.call_args.kwargs["language"], expected)
                    self.assertEqual(run.call_args.kwargs["title"], "Project settings")
                    self.assertEqual(run.call_args.kwargs["thresholds"].fdr_q, 0.02)

    def test_serve_passes_only_explicit_flags_as_project_open_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "lixity.toml").write_text(
                'language = "fr"\ntitle = "Project settings"\nfdr_q = 0.12\n',
                encoding="utf-8",
            )
            with patch("lixity.server.run_server") as run:
                self.assertEqual(main(["serve", str(project)]), 0)
            self.assertEqual(run.call_args.kwargs["project_open_overrides"], {})

            with patch("lixity.server.run_server") as run:
                self.assertEqual(main([
                    "serve", str(project), "--language", "de", "--title", "Override",
                    "--fdr-q", "0.03",
                ]), 0)
            self.assertEqual(run.call_args.kwargs["project_open_overrides"], {
                "language": "de", "title": "Override", "fdr_q": 0.03,
            })

    def test_serve_passes_debug_flag(self):
        with patch("lixity.server.run_server") as run:
            self.assertEqual(main(["serve", "--no-project", "--debug"]), 0)
        self.assertTrue(run.call_args.kwargs["debug"])

        with patch("lixity.server.run_server") as run:
            self.assertEqual(main(["serve", "--no-project"]), 0)
        self.assertFalse(run.call_args.kwargs["debug"])

