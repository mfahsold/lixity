"""
tests/test_api.py
=================
Tests for the agent-facing interface: the stable `lixity.api` facade,
self-describing JSON meta blocks and the CLI helper surfaces
(completion scripts, about, exit codes).
"""

import json
import os
import sys
import tempfile
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity import api  # noqa: E402
from lixity.cli import _BASH_COMPLETION, _ZSH_COMPLETION, main  # noqa: E402

SAMPLE = (
    "## Kap 1\n\n"
    "Ich trinke Kaffee. Ich gehe zum Fenster. Ich sehe den Regen. Ich trinke Tee.\n\n"
    "Ich trinke noch einen Schluck. Ich gehe zur Tür. Ich sehe die Straße.\n\n"
    "Ich trinke Wasser. Ich gehe zur Theke und ich sehe den Abend über der Stadt.\n\n"
    "## Kap 2\n\n"
    "Das Haus wurde verkauft und die Tür war verschlossen worden. Die Zeitung lag "
    "auf dem Tisch. Die Entscheidung fiel schwer. Die Beschreibung der Wohnung "
    "war ausführlich. Das Haus wurde besichtigt und die Miete war bezahlt worden. "
    "Die Zeitung lag auf dem Boden und die Entscheidung war gefallen. Die "
    "Beschreibung der Wohnung wirkte sachlich und die Miete war hoch.\n"
)


class TestApiFacade(unittest.TestCase):
    def test_analyze_returns_meta_and_metrics(self):
        result = api.analyze(SAMPLE, language="de")
        self.assertEqual(result["meta"]["tool"], "lixity")
        self.assertEqual(result["meta"]["language"], "de")
        self.assertIn("asl", result["metrics"])
        self.assertTrue(result["metrics"]["chapters"])

    def test_profile_returns_meta_chapters_paragraphs(self):
        result = api.profile(SAMPLE, language="de")
        self.assertEqual(result["meta"]["schema_version"], 2)
        self.assertTrue(result["chapters"])
        self.assertTrue(result["paragraphs"])
        self.assertNotIn("text", result["paragraphs"][0])

    def test_interaction_facade_surfaces(self):
        dialogue = api.dialogue(SAMPLE, language="de")
        self.assertIn("dialogue", dialogue)
        self.assertEqual(dialogue["meta"]["tool"], "lixity")
        characters = api.characters(SAMPLE, ["Ich"], language="de")
        self.assertIn("figures", characters)
        pacing = api.pacing(SAMPLE, language="de")
        self.assertIn("pacing", pacing)
        motifs = api.motifs(SAMPLE, {"Ich": r"\bIch\b"}, language="de")
        self.assertIn("motifs", motifs)
        self.assertIn("top_words", motifs)

    def test_fingerprint_is_the_passport(self):
        passport = api.fingerprint(SAMPLE, language="de")
        self.assertEqual(passport["meta"]["schema_version"], 3)
        self.assertIn("features", passport)
        self.assertIn("dimensions", passport)
        self.assertIn("fdr_flagged", passport)
        self.assertIn("wave2_diagnostics", passport)
        self.assertIn("flag_min_severity", passport["meta"])
        alias = api.passport(SAMPLE, language="de")
        self.assertEqual(passport, alias)

    def test_profile_flag_min_severity_injectable(self):
        base = api.profile(SAMPLE, language="de")
        raised = api.profile(SAMPLE, language="de", flag_min_severity=3)
        # Raising the floor can only flag fewer or equal paragraphs
        self.assertLessEqual(
            sum(1 for p in raised["paragraphs"] if p["severity"] >= 3),
            sum(1 for p in base["paragraphs"] if p["severity"] >= 3),
        )
        # Paragraphs with flag_min stamped reflect the resolved cut
        flagged_cut = {p["flag_min"] for p in raised["paragraphs"]}
        self.assertEqual(flagged_cut, {3})

    def test_thresholds_resolve_from_explicit_kwargs(self):
        passport = api.fingerprint(SAMPLE, language="de", z_mild=1.5, fdr_q=0.1)
        self.assertEqual(passport["meta"]["z_mild"], 1.5)
        self.assertEqual(passport["meta"]["fdr_q"], 0.1)

    def test_dashboard_returns_self_contained_html(self):
        html = api.dashboard(SAMPLE, language="de", title="Test")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn('<table class="heatmap">', html)
        self.assertNotIn("http://", html)

    def test_dashboard_flag_min_severity_selectable(self):
        from lixity.analyzer import CorpusAnalyzer
        from lixity.markdown_parser import parse_markdown_blocks
        from lixity.models import CorpusConfig
        from lixity.style_fingerprint import StyleFingerprint
        from lixity.style_profile import ParagraphProfiler
        from lixity.ui import render_dashboard

        config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
            parse_markdown_blocks(SAMPLE)
        )
        metrics = CorpusAnalyzer(config).analyze_text(SAMPLE)
        fingerprint = StyleFingerprint.from_metrics(metrics)
        html = render_dashboard(
            chapters,
            paragraphs,
            metrics=metrics,
            fingerprint=fingerprint,
            title="T",
            controls=True,
            flag_min_severity=3,
        )
        self.assertIn('id="set-flag-min-sev"', html)
        self.assertIn('value="3" selected', html)

    def test_about_lists_features_and_heuristics(self):
        info = api.about()
        self.assertIn("languages", info)
        self.assertIn("de", info["languages"])
        self.assertTrue(info["features"])
        self.assertGreater(info["heuristics"]["z_mild"], 0.0)

    def test_facade_is_deterministic(self):
        self.assertEqual(api.analyze(SAMPLE), api.analyze(SAMPLE))
        self.assertEqual(api.fingerprint(SAMPLE), api.fingerprint(SAMPLE))


class TestCliAgentSurface(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "sample.md")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(SAMPLE)

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, *argv):
        return main([*argv, self.path])

    def test_version_flag(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["--version"])
        self.assertEqual(ctx.exception.code, 0)

    def test_completion_bash_and_zsh(self):
        for script in (_BASH_COMPLETION, _ZSH_COMPLETION):
            self.assertIn("lixity", script)
        self.assertIn(
            "analyze profile dialogue characters pacing motifs showing dashboard style build about completion",
            _BASH_COMPLETION,
        )
        self.assertIn("--fdr-method", _BASH_COMPLETION)
        self.assertIn("--flag-min-severity", _BASH_COMPLETION)
        self.assertIn("_lixity_style_flags", _ZSH_COMPLETION)
        self.assertIn("characters", _ZSH_COMPLETION)

    def test_about_json_flag(self):
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(main(["about", "--json"]), 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["meta"]["tool"], "lixity")
        self.assertIn("languages", payload)
        self.assertIn("features", payload)

    def test_cli_messages_follow_lixity_lang(self):
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(main(["about"]), 0)
        self.assertIn("Languages:", buffer.getvalue())

        os.environ["LIXITY_LANG"] = "de"
        try:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                self.assertEqual(main(["about"]), 0)
            self.assertIn("Sprachen:", buffer.getvalue())
        finally:
            os.environ.pop("LIXITY_LANG", None)

    def test_cli_exit_codes(self):
        self.assertEqual(self._run("analyze"), 0)
        self.assertEqual(self._run("analyze", "--json"), 0)
        self.assertEqual(self._run("profile"), 0)
        self.assertEqual(self._run("style"), 0)
        self.assertEqual(self._run("style", "--json"), 0)

    def test_json_has_self_describing_meta(self):
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self._run("analyze", "--json")
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["meta"]["tool"], "lixity")
        self.assertIn("metrics", payload)
        self.assertEqual(payload["meta"]["language"], "de")

    def test_missing_file_exits_1(self):
        self.assertEqual(main(["analyze", "/definitiv/nicht/da.md"]), 1)


if __name__ == "__main__":
    unittest.main()
