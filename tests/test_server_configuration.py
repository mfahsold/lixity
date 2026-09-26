"""Server defaults and CLI configuration use the shared project contract."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lixity.cli import main
from lixity.server import build_server_dashboard


class TestServerConfiguration(unittest.TestCase):
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
