"""
tests/test_api.py
=================
Tests for the agent-facing interface: the stable `lixity.api` facade,
self-describing JSON meta blocks and the CLI helper surfaces
(completion scripts, about, exit codes).
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity import api  # noqa: E402
from lixity.cli import main  # noqa: E402

SAMPLE = (
    "## Kap 1\n\n"
    "Ich trinke Kaffee. Ich gehe zum Fenster. Ich sehe den Regen. Ich trinke Tee. "
    "Ich höre die Straße. Ich sehe die Lichter. Ich trinke noch einen Schluck.\n\n"
    "Ich trinke noch einen Schluck. Ich gehe zur Tür. Ich sehe die Straße und den "
    "Regen auf dem Asphalt, der glänzt. Ich höre ein fernes Lied.\n\n"
    "Ich trinke Wasser. Ich gehe zur Theke und ich sehe den Abend über der Stadt. "
    "Ich höre den Wind und ich sehe die Tropfen an der Scheibe. Ich trinke den "
    "letzten Schluck und ich sehe die Lichter an der Straße.\n\n"
    "Ich gehe nach Hause. Ich sehe den Mond über den Dächern. Ich höre den Regen "
    "und ich trinke noch einen Tee. Ich sehe die Tropfen an der Scheibe und ich "
    "warte auf den Morgen.\n\n"
    "## Kap 2\n\n"
    "Das Haus wurde verkauft und die Tür war verschlossen worden. Die Zeitung lag "
    "auf dem Tisch. Die Entscheidung fiel schwer. Die Beschreibung der Wohnung "
    "war ausführlich. Das Haus wurde besichtigt und die Miete war bezahlt worden. "
    "Die Zeitung lag auf dem Boden und die Entscheidung war gefallen. Die "
    "Beschreibung der Wohnung wirkte sachlich und die Miete war hoch.\n\n"
    "Die Wohnung wurde gestrichen und die Fenster waren geputzt worden. Die Kaution "
    "wurde überwiesen und der Vertrag war unterschrieben worden. Die Nachbarn wurden "
    "gefragt und die Antwort war freundlich gewesen. Die Möbel wurden geliefert und "
    "die Kartons waren ausgepackt worden.\n\n"
    "Die Rechnung wurde geprüft und der Betrag war überwiesen worden. Die Schlüssel "
    "wurden übergeben und die Übergabe war protokolliert worden. Die Fenster wurden "
    "geöffnet und die Räume waren gelüftet worden.\n"
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
        self.assertIn("explicit_scene_breaks", pacing["pacing"])
        self.assertIn("scenes_are_chapters", pacing["pacing"])
        motifs = api.motifs(SAMPLE, {"Ich": r"\bIch\b"}, language="de")
        self.assertIn("motifs", motifs)
        self.assertIn("top_words", motifs)

    def test_characters_requires_names(self):
        with self.assertRaises(ValueError):
            api.characters(SAMPLE, [], language="de")
        with self.assertRaises(ValueError):
            api.characters(SAMPLE, {}, language="de")

    def test_fingerprint_is_the_passport(self):
        passport = api.fingerprint(SAMPLE, language="de")
        self.assertEqual(passport["meta"]["schema_version"], 4)
        self.assertIn("features", passport)
        self.assertIn("dimensions", passport)
        self.assertIn("fdr_flagged", passport)
        self.assertIn("structural_diagnostics", passport)
        w2 = passport["structural_diagnostics"]
        self.assertIn("distribution_shift", w2)
        self.assertIn("shifted_features", w2)
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
        # Vendored libraries embed XML namespace constants inside their code;
        # the markup itself must stay free of insecure remote references.
        markup = re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.S)
        self.assertNotIn("http://", markup)

    def test_static_dashboard_does_not_advertise_native_evidence_controls(self):
        document = api.dashboard("## Example\n\nI think I can wait.", project_config={})
        self.assertNotIn('id="analysis-evidence-enabled"', document)
        self.assertNotIn('"schema_version":"paragraph-evidence/1"', document)

    def test_dashboard_flag_min_severity_selectable(self):
        from lixity.analyzer import CorpusAnalyzer
        from lixity.markdown_parser import parse_markdown_blocks
        from lixity.models import CorpusConfig
        from lixity.style_fingerprint import StyleFingerprint
        from lixity.style_profile import ParagraphProfiler
        from lixity.ui import render_dashboard

        config = CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+")
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
        self.assertEqual(info["heuristics"]["hd_d_method"], "hypergeometric_expected_ttr")
        self.assertEqual(info["heuristics"]["hd_d_sample_size"], 42)
        self.assertEqual(info["heuristics"]["hd_d_samples"], 0)
        self.assertEqual(info["heuristics"]["hd_d_min_tokens"], 100)

    def test_about_discovers_the_pdf_artifact_command(self):
        commands = {command["name"]: command for command in api.about()["commands"]}
        self.assertIn("pdf", commands)
        self.assertEqual(commands["pdf"]["output"], "pdf")
        for purpose in ("report", "editorial", "A5", "sheet", "document"):
            self.assertIn(purpose, commands["pdf"]["purpose"])

    def test_about_distinguishes_default_profile_from_opt_in_layer_contract(self):
        from lixity.style_fingerprint import LAYER_FEATURES

        profile = next(command for command in api.about()["commands"] if command["name"] == "profile")
        self.assertEqual((profile["output"], profile["schema_version"]), ("json", 2))
        projection = profile["layer_projection"]
        self.assertEqual(projection["choices"], list(LAYER_FEATURES))
        self.assertEqual(projection["schema_version"], "paragraph-layer/1")
        self.assertEqual(projection["only_notable_requires"], "--layer")
        self.assertEqual(projection["evidence_requires"], "--layer")
        self.assertEqual(projection["evidence_schema_version"], "paragraph-layer-evidence/1")
        self.assertEqual(projection["span_schema_version"], "paragraph-evidence/1")
        self.assertEqual(projection["offset_unit"], "unicode_codepoint")

    def test_exact_hd_d_matches_chapter_and_corpus_without_invented_se(self):
        text = "## Chapter\n\n" + "echo " * 100
        result = api.analyze(text, chapter_regex=r"(?m)^##\s+", project_config={})
        metrics = result["metrics"]
        self.assertAlmostEqual(metrics["hd_d"], 1 / 42)
        self.assertAlmostEqual(metrics["chapters"][0]["hd_d"], 1 / 42)
        self.assertNotIn("hd_d", metrics["chapters"][0]["style_se"])

    def test_facade_is_deterministic(self):
        self.assertEqual(api.analyze(SAMPLE), api.analyze(SAMPLE))
        self.assertEqual(api.fingerprint(SAMPLE), api.fingerprint(SAMPLE))

    def test_fingerprint_includes_lexical_structural_on_multi_chapter_text(self):
        sentence = (
            "Das alte Haus stand am Ende der stillen Straße und der Wind "
            "bewegte die Blätter der Bäume. Die Bewohner sprachen leise "
            "über die kommenden Veränderungen und ihre gemeinsamen Sorgen. "
            "Jeder Morgen begann mit dem Klang der Glocken und dem Duft "
            "von frischem Brot aus der Bäckerei gegenüber am Markt. "
            "Niemand wusste genau, wie lange diese Ruhe noch dauern würde "
            "in der kleinen Stadt am Flussufer mit ihren vielen Gassen.\n"
        )
        text = "\n".join(f"## Kap {i + 1}\n\n{sentence}" for i in range(4))
        passport = api.fingerprint(text, language="de")
        w2 = passport["structural_diagnostics"]
        self.assertIn("cooccurrence", w2)
        self.assertIn("keyness", w2)
        self.assertEqual(w2["keyness"]["n_early_chapters"], 2)
        json.dumps(passport)


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


    @unittest.skipUnless(shutil.which("bash"), "requires Bash")
    def test_bash_completion_executes_command_and_style_flag_candidates(self):
        import io
        from contextlib import redirect_stdout

        script = io.StringIO()
        with redirect_stdout(script):
            self.assertEqual(main(["completion", "bash"]), 0)
        bash = shutil.which("bash")
        for words, expected in (
            (("lixity", "pd"), ["pdf"]),
            (("lixity", "style", "--fdr-m"), ["--fdr-method"]),
            (("lixity", "style", "--flag-min"), ["--flag-min-severity"]),
            (("lixity", "about", "--sec"), ["--section"]),
            (("lixity", "schema", "--section", "conf"), ["configuration"]),
            (("lixity", "research", "dossier", "--section", "conf"), []),
        ):
            with self.subTest(words=words):
                result = subprocess.run(  # noqa: S603 - resolved Bash and fixed synthetic words
                    [bash, "--noprofile", "--norc"],
                    input=script.getvalue() + f"\nCOMP_WORDS=({shlex.join(words)})\nCOMP_CWORD={len(words)-1}\n"
                    '_lixity_complete\nprintf "%s\\n" "${COMPREPLY[@]}"\n',
                    text=True, capture_output=True, check=True,
                )
                self.assertFalse(result.stderr)
                self.assertEqual(result.stdout.split(), expected)


    def test_completion_scripts_cover_every_parser_command(self):
        import io
        from contextlib import redirect_stdout

        from lixity.cli import _COMMANDS

        for shell in ("bash", "zsh"):
            with self.subTest(shell=shell):
                script = io.StringIO()
                with redirect_stdout(script):
                    self.assertEqual(main(["completion", shell]), 0)
                emitted = script.getvalue()
                self.assertNotIn("__LIXITY_", emitted, "completion placeholder left unfilled")
                for name, _help_text in _COMMANDS:
                    needle = f"'{name}:" if shell == "zsh" else f" {name} "
                    self.assertIn(needle, emitted, f"{shell} completion misses {name}")

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
        self.assertEqual(payload["meta"]["language"], "en")

    def test_missing_file_exits_1(self):
        self.assertEqual(main(["analyze", os.path.join(self.tmp.name, "missing.md")]), 1)


if __name__ == "__main__":
    unittest.main()
