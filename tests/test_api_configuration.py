"""Public API and CLI expose the core calibration settings consistently."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from lixity import api
from lixity.cli import main
from lixity.pipeline import analyze_document

TEXT = "## One\n\nI walk in the rain.\n\n## Two\n\nThe door was closed.\n"


class TestApiConfiguration(unittest.TestCase):
    def test_invalid_baseline_sample_size_is_rejected(self):
        for minimum in (0, 1, 2.5, True):
            with self.subTest(minimum=minimum), self.assertRaises(ValueError):
                api.fingerprint(TEXT, min_chapters=minimum, project_config={})

    def test_explicit_threshold_mapping_isolates_the_api(self):
        with patch("lixity.config.load_project_config", return_value={"z_mild": 5.0}):
            result = api.fingerprint(TEXT, project_config={}, min_chapters=4)
        self.assertEqual(result["meta"]["z_mild"], 2.5)
        self.assertEqual(result["meta"]["min_chapters"], 4)
        self.assertFalse(result["deviations"])

    def test_alias_and_dashboard_accept_core_calibration_settings(self):
        result = api.passport(TEXT, min_chapters=4, project_config={"fdr_method": "by"})
        self.assertEqual(result["meta"]["min_chapters"], 4)
        self.assertEqual(result["meta"]["fdr_method"], "by")
        with patch("lixity.api.analyze_document", wraps=analyze_document) as analyze:
            api.dashboard(TEXT, min_chapters=4, project_config={})
        self.assertEqual(analyze.call_args.args[2].min_chapters, 4)

    def test_cli_exposes_minimum_calibration_sample_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manuscript.md"
            path.write_text(TEXT, encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["style", str(path), "--json", "--min-chapters", "4"]), 0)
            self.assertEqual(json.loads(output.getvalue())["meta"]["min_chapters"], 4)

    def test_malformed_project_config_warns_and_names_the_file(self) -> None:
        """A broken config must not silently revert the analysis to defaults.

        An unparseable lixity.toml used to be treated as absent, so a run
        reported the default language and thresholds while exiting 0 -- the
        numbers looked authoritative and matched nothing the project asked for.
        """
        from lixity.config import load_project_config

        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            (project / "lixity.toml").write_text('title = "Unclosed\nlanguage = de\n', encoding="utf-8")
            with self.assertWarns(UserWarning) as caught:
                self.assertEqual(load_project_config(project), {})
            message = str(caught.warning)
            self.assertIn("lixity.toml", message)
            self.assertIn("Could not parse", message)
            # The message has to say the consequence, not just the cause.
            self.assertIn("language and thresholds", message)

    def test_unreadable_project_config_warns(self) -> None:
        """An unreadable config is also not the same as an absent one."""
        from lixity.config import _load_toml

        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "lixity.toml"
            target.write_text('title = "Fine"\n', encoding="utf-8")
            with patch("pathlib.Path.open", side_effect=PermissionError("denied")), \
                 self.assertWarns(UserWarning) as caught:
                self.assertEqual(_load_toml(target), {})
            self.assertIn("Could not read", str(caught.warning))

    def test_valid_project_config_stays_silent(self) -> None:
        """The whole suite runs under -W error, so a valid config must not warn."""
        from lixity.config import load_project_config

        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            (project / "lixity.toml").write_text('title = "My Book"\nlanguage = "de"\n', encoding="utf-8")
            self.assertEqual(
                load_project_config(project),
                {"title": "My Book", "language": "de"},
            )
