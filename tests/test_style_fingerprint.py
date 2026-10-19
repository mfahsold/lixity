"""
tests/test_style_fingerprint.py
===============================
Tests for the self-calibrating style fingerprint: robust statistics
(median/MAD/z), the consistency heuristic, the Jensen-Shannon chapter
divergence with driver words, HD-D, the style passport and the
heatmap/layer rendering of the dashboard.
"""

import html as html_module
import itertools
import json
import math
import os
import re
import sys
import unittest
from fractions import Fraction

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity import api  # noqa: E402
from lixity.analyzer import CorpusAnalyzer  # noqa: E402
from lixity.markdown_parser import parse_markdown_blocks  # noqa: E402
from lixity.models import CorpusConfig  # noqa: E402
from lixity.style_fingerprint import (  # noqa: E402
    FEATURES,
    FingerprintThresholds,
    StyleFingerprint,
    layer_stats,
    lexical_structural_diagnostics,
    z_color,
)
from lixity.style_profile import ParagraphProfiler  # noqa: E402
from lixity.ui import render_dashboard  # noqa: E402

SAMPLE = (
    "## Kap 1\n\n"
    "Ich trinke Kaffee. Ich gehe zum Fenster. Ich sehe den Regen. Ich trinke Tee. "
    "Ich höre die Straße. Ich sehe die Lichter. Ich trinke noch einen Schluck.\n\n"
    "Ich gehe zur Tür. Ich sehe die Stadt. Ich trinke Wasser an der Theke. "
    "Ich sehe den Abend über den Dächern. Ich höre ein fernes Lied. Ich trinke "
    "schnell. Ich gehe nach Hause.\n\n"
    "Ich sehe den Mond. Ich trinke noch einmal. Ich gehe zu Bett. Ich höre den "
    "Wind. Ich trinke den letzten Schluck und ich sehe nichts mehr.\n\n"
    "Ich höre den Regen. Ich sehe die Tropfen an der Scheibe. Ich trinke Tee und "
    "ich warte auf den Morgen über der Stadt.\n\n"
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
    "Die Zeitung wurde gelesen und der Kaffee war getrunken worden. Die Rechnung "
    "wurde geprüft und der Betrag war überwiesen worden. Die Schlüssel wurden "
    "übergeben und die Übergabe war protokolliert worden.\n"
)

DIMENSION_SAMPLE = (
    SAMPLE + "\n## Kap 3\n\nDie Straße glänzt im Licht. Regen fällt auf das Pflaster. "
    "Vor dem Fenster wartet jemand mit einem roten Schirm. Der Wind dreht über den "
    "Dächern. Eine Tür fällt ins Schloss. Die Laternen gehen an. Ein Hund bellt im "
    "Hof. Der Abend zieht über die Stadt. Die Schatten werden länger. Ein Wagen "
    "hält an der Ecke. Die Fenster flackern blau. Der Regen lässt nach. "
    "Die Straße glänzt weiter. Ein Moped knattert durch die Gasse. Die Markisen "
    "flattern im Wind. Eine Katze schleicht über die Mauer. Der Bäcker schließt "
    "seine Tür. Zwei Kinder laufen nach Hause. Die Ampel springt auf Rot. "
    "Ein Mann wartet unter dem Vordach.\n"
)


class TestRobustStatistics(unittest.TestCase):
    def test_unmeasured_consistency_is_explicit(self):
        for text in ("", "## One\n\n## Two\n", "## One\n\nThe rain fell."):
            with self.subTest(text=text):
                fp = StyleFingerprint.from_metrics(CorpusAnalyzer(CorpusConfig(language="en", chapter_regex=r"(?m)^##\s+")).analyze_text(text))
                self.assertEqual(fp.measured_cells, 0)
                self.assertEqual(fp.passport()["measured_cells"], 0)
                self.assertIsInstance(fp.passport()["consistency"], float)
                self.assertIn("Consistency: –", fp.passport_text())

    def test_measured_consistency_and_custom_minimum(self):
        metrics = CorpusAnalyzer(CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+")).analyze_text(SAMPLE)
        fp = StyleFingerprint.from_metrics(metrics)
        self.assertGreater(fp.measured_cells, 0)
        self.assertNotIn("Consistency: –", fp.passport_text())
        below = StyleFingerprint.from_metrics(metrics, FingerprintThresholds(min_chapters=3))
        self.assertEqual(below.measured_cells, 0)

    def test_z_color_is_deterministic_and_clamped(self):
        self.assertEqual(z_color(0.0), z_color(0.0))
        self.assertRegex(z_color(0.0), r"^#[0-9a-f]{6}$")
        self.assertEqual(z_color(100.0), z_color(2.5))
        self.assertEqual(z_color(-100.0), z_color(-2.5))


class TestRegisterProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Twenty sentences per chapter keep every chapter above the data floor.
        cls.text = "\n\n".join(
            f"## Chapter {number}\n\n" + (("moss " * length).strip() + ". ") * 20
            for number, length in enumerate((8, 9, 10, 11, 70), 1)
        )
        cls.metrics = CorpusAnalyzer(CorpusConfig(language="en")).analyze_text(cls.text)

    def test_register_exempts_real_fdr_outlier_but_preserves_descriptive_z(self):
        plain = StyleFingerprint.from_metrics(self.metrics)
        self.assertIn("asl", plain.fdr_flagged[5])
        config = CorpusConfig(
            chapter_registers={"5": "formal"}, register_profiles={"formal": {"asl": [65, 75]}},
        )
        registered = StyleFingerprint.from_metrics(self.metrics, config=config)
        self.assertNotIn(5, registered.fdr_flagged)
        self.assertNotIn(5, registered.deviations)
        self.assertEqual(registered.z_scores[5], plain.z_scores[5])
        self.assertEqual(registered.baseline, plain.baseline)

    def test_register_targets_compare_author_ranges_without_changing_book_z(self):
        config = CorpusConfig(
            chapter_registers={"5": "formal"},
            register_profiles={"formal": {"asl": [65, 75], "dialog_pct": 0, "hd_d": {"lower": 0.1}}},
        )
        registered = StyleFingerprint.from_metrics(self.metrics, config=config)
        self.assertEqual(getattr(registered, "register_profiles", {}), {
            "formal": {"asl": [65.0, 75.0], "dialog_pct": [0.0, 0.0], "hd_d": [0.1, None]},
        })
        targets = getattr(registered, "register_targets", {})
        self.assertEqual(targets.get(5, {}).get("asl"), {
            "lower": 65.0, "upper": 75.0, "value": 70.0, "position": "within",
        })
        self.assertEqual(targets[5]["hd_d"]["position"], "below")
        passport = registered.passport()
        self.assertEqual(passport.get("register_targets", {}).get("5"), targets[5])
        self.assertEqual(passport["meta"]["schema_version"], 4)

    def test_target_positions_include_above_below_and_unavailable(self):
        for bounds, expected in (([71, 80], "below"), ([1, 69], "above")):
            config = CorpusConfig(chapter_registers={"5": "voice"}, register_profiles={"voice": {"asl": bounds}})
            fingerprint = StyleFingerprint.from_metrics(self.metrics, config=config)
            self.assertEqual(getattr(fingerprint, "register_targets", {}).get(5, {}).get("asl", {}).get("position"), expected)
        tiny = CorpusAnalyzer(CorpusConfig()).analyze_text("## Small\n\nMoss grows.")
        config = CorpusConfig(chapter_registers={"1": "voice"}, register_profiles={"voice": {"asl": [1, 20]}})
        fingerprint = StyleFingerprint.from_metrics(tiny, config=config)
        self.assertEqual(getattr(fingerprint, "register_targets", {}).get(1, {}).get("asl"), {
            "lower": 1.0, "upper": 20.0, "value": None, "position": "unavailable",
        })

    def test_numeric_selectors_do_not_match_other_chapter_titles(self):
        metrics = self.metrics.model_copy(deep=True)
        metrics.chapters[1].title = "Chapter 10"
        config = CorpusConfig(chapter_registers={"1": "voice"}, register_profiles={"voice": {}})
        fingerprint = StyleFingerprint.from_metrics(metrics, config=config)
        self.assertEqual(fingerprint.chapter_registers, {1: "voice"})

    def test_exact_title_precedes_partial_match_independent_of_config_order(self):
        for assignments in ({"Chapter 5": "exact", "Chapter": "partial"}, {"Chapter": "partial", "Chapter 5": "exact"}):
            config = CorpusConfig(chapter_registers=assignments, register_profiles={"exact": {}, "partial": {}})
            fingerprint = StyleFingerprint.from_metrics(self.metrics, config=config)
            self.assertEqual(fingerprint.chapter_registers[5], "exact")
            self.assertEqual(fingerprint.chapter_registers[2], "partial")

    def test_unknown_profiles_and_invalid_ranges_fail_before_analysis(self):
        invalid = [
            {"chapter_registers": {"1": "missing"}},
            {"register_profiles": {" ": {}}},
            {"register_profiles": {"voice": {"unknown_metric": [1, 2]}}},
            {"register_profiles": {"voice": {"asl": [10, 2]}}},
            {"register_profiles": {"voice": {"asl": [True, 2]}}},
            {"register_profiles": {"voice": {"asl": [0, float("inf")]}}},
            {"register_profiles": {"voice": {"asl": float("nan")}}},
            {"register_profiles": {"voice": {"asl": [-1, 2]}}},
            {"register_profiles": {"voice": {"hd_d": [0, 1.1]}}},
            {"register_profiles": {"voice": {"dialog_pct": [0, 101]}}},
            {"register_profiles": {"voice": {"asl": [None, None]}}},
            {"register_profiles": {"voice": {}}, "chapter_registers": {"": "voice"}},
        ]
        for settings in invalid:
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                CorpusConfig(**settings)

    def test_stale_selectors_are_reported(self):
        config = CorpusConfig(chapter_registers={"Missing chapter": "voice"}, register_profiles={"voice": {}})
        with self.assertRaisesRegex(ValueError, "Missing chapter"):
            StyleFingerprint.from_metrics(self.metrics, config=config)

    def test_empty_metrics_preserve_profiles_without_resolving_assignments(self):
        config = CorpusConfig(chapter_registers={"1": "voice"}, register_profiles={"voice": {"asl": [3, 12]}})
        empty = CorpusAnalyzer(config).analyze_text("")
        fingerprint = StyleFingerprint.from_metrics(empty, config=config)
        self.assertEqual(fingerprint.register_profiles, {"voice": {"asl": [3.0, 12.0]}})
        self.assertEqual(fingerprint.chapter_registers, {})
        self.assertEqual(fingerprint.register_targets, {})
        self.assertEqual(fingerprint.measured_cells, 0)


class TestAnalyzerStyleFeatures(unittest.TestCase):
    def setUp(self):
        self.config = CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+")
        self.analyzer = CorpusAnalyzer(self.config)

    def test_house_style_features_are_computed(self):
        m = self.analyzer.analyze_text(SAMPLE)
        self.assertEqual(len(m.chapters), 2)
        for c in m.chapters:
            self.assertGreaterEqual(c.staccato_pct, 0.0)
            self.assertGreaterEqual(c.kaskade_pct, 0.0)
            self.assertGreaterEqual(c.sentence_cv, 0.0)
            self.assertGreaterEqual(c.start_entropy, 0.0)
            self.assertGreaterEqual(c.first_person_start_rate, 0.0)
            self.assertGreater(c.guiraud_r, 0.0)
            self.assertGreater(c.function_word_pct, 0.0)
            self.assertGreaterEqual(c.jsd, 0.0)
            self.assertIsInstance(c.jsd_top_words, list)

    def test_chapter_styles_differ_as_designed(self):
        # Kap 1: Ich-heavy staccato; Kap 2: passive, nominal, no first person
        m = self.analyzer.analyze_text(SAMPLE)
        c1, c2 = m.chapters
        self.assertGreater(c1.first_person_start_rate, c2.first_person_start_rate)
        self.assertGreater(c2.passive_density, c1.passive_density)
        self.assertGreater(c2.nominalization_density, c1.nominalization_density)
        self.assertGreater(c1.staccato_pct, c2.staccato_pct)

    def test_jsd_driver_words_belong_to_chapter(self):
        m = self.analyzer.analyze_text(SAMPLE)
        for c in m.chapters:
            for word in c.jsd_top_words:
                self.assertRegex(word, r"[a-zäöüß]")

class TestStyleFingerprint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+")
        cls.metrics = CorpusAnalyzer(cls.config).analyze_text(SAMPLE)

    def setUp(self):
        self.fp = StyleFingerprint.from_metrics(self.metrics)

    def test_self_calibration_baseline(self):
        self.assertEqual(self.fp.n_chapters, 2)
        for field_name, _label, _unit in FEATURES:
            self.assertIn(field_name, self.fp.baseline)
            self.assertIn(field_name, self.fp.values)

    def test_deviations_are_symmetric(self):
        # Ich-start-Rate: Kap 1 must deviate upward, Kap 2 downward (own style)
        z1 = self.fp.z_scores[1].get("first_person_start_rate")
        z2 = self.fp.z_scores[2].get("first_person_start_rate")
        self.assertIsNotNone(z1)
        self.assertIsNotNone(z2)
        if z1 is None or z2 is None:
            self.fail("First-person deviation should be measurable")
        self.assertGreater(z1, 0.0)
        self.assertLess(z2, 0.0)

    def test_consistency_between_zero_and_one(self):
        self.assertGreaterEqual(self.fp.consistency, 0.0)
        self.assertLessEqual(self.fp.consistency, 1.0)

    def test_top_deviants(self):
        drifters = self.fp.top_deviants(3)
        self.assertTrue(drifters)
        for num, mean_abs in drifters:
            self.assertIn(num, (1, 2))
            self.assertGreaterEqual(mean_abs, 0.0)

    def test_passport_json_structure(self):
        passport = self.fp.passport()
        json.dumps(passport)
        self.assertIn("features", passport)
        self.assertIn("consistency", passport)
        self.assertIn("deviations", passport)
        self.assertEqual(len(passport["features"]), len(FEATURES))
        band = passport["features"][0]["band"]
        self.assertLessEqual(band[0], band[1])

    def test_passport_text(self):
        text = self.fp.passport_text(labels={"feat_asl": "ASL"})
        self.assertIn("STYLE REFERENCE", text)
        self.assertIn("ASL", text)
        self.assertIn("band", text)
        self.assertIn("nominal FDR selection", text)
        self.assertIn("normal-model reference", text)
        self.assertNotIn("FDR-confirmed", text)
        german = self.fp.passport_text(labels={"feat_asl": "ASL"}, language_key="de")
        self.assertIn("STILREFERENZ", german)
        self.assertIn("Korridor", german)
        self.assertIn("nominale FDR-Auswahl", german)
        self.assertIn("Referenz des Normalmodells", german)
        self.assertNotIn("FDR-bestätigt", german)

    def test_comparability_floors_withhold_unstable_comparisons(self):
        long_sentence = " ".join(["Der lange Satz zieht sich über die ganze Zeile"] * 6)
        metrics = CorpusAnalyzer(self.config).analyze_text(
            "## Lang\n\n"
            f"{long_sentence}. {long_sentence} und weiter. {long_sentence} am Ende.\n\n"
            "## Kurz\n\nEr ging nach Hause. Sie blieb am Fenster. Der Regen fiel.\n"
        )
        fp = StyleFingerprint.from_metrics(metrics)
        # The long chapter clears the word floor but not the sentence floor:
        # distribution features stay unavailable, the mean stays measurable.
        self.assertIsNone(fp.values["staccato_pct"][1])
        self.assertIsNone(fp.values["sentence_cv"][1])
        self.assertIsNotNone(fp.values["asl"][1])
        # The short chapter clears neither floor.
        self.assertIsNone(fp.values["asl"][2])
        self.assertIsNone(fp.values["dialog_pct"][2])
        self.assertEqual(fp.z_scores.get(2, {}), {})

    def test_single_chapter_no_deviations(self):
        one = CorpusAnalyzer(self.config).analyze_text(
            "## Kap 1\n\nIch trinke Kaffee. Ich gehe zum Fenster. Ich sehe den Regen.\n"
        )
        fp = StyleFingerprint.from_metrics(one)
        self.assertEqual(fp.deviations, {})


class TestParagraphLayers(unittest.TestCase):
    def test_inline_code_only_paragraph_retains_anchor_without_contributing_to_layers(self):
        config = CorpusConfig(language="en")
        text = "## Main\n\nDoor opens.\n\nThe door closes.\n\n`OnlyCode`\n"
        paragraphs, _ = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text, config))
        self.assertEqual([paragraph.words for paragraph in paragraphs], [2, 3, 0])
        self.assertEqual((paragraphs[2].text, paragraphs[2].start_line, paragraphs[2].end_line),
                         ("`OnlyCode`", 7, 7))
        self.assertEqual(layer_stats(paragraphs, "asl"), {})

        text = text.replace("`OnlyCode`", "A window opens slowly.\n\n`OnlyCode`")
        paragraphs, _ = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text, config))
        measured = layer_stats(paragraphs[:3], "asl")
        self.assertEqual(set(measured), {0, 1, 2})
        self.assertEqual(layer_stats(paragraphs, "asl"), measured)
        self.assertEqual((paragraphs[3].text, paragraphs[3].start_line, paragraphs[3].end_line),
                         ("`OnlyCode`", 9, 9))

    def test_layer_stats_within_chapter(self):
        md = (
            "## Kap 1\n\n"
            "Ich trinke Kaffee und gehe los. Ich sehe den Regen und ich gehe weiter. "
            "Ich trinke Tee und gehe nach Hause.\n\n"
            "Ich spüre die Kälte und ich fühle den Wind. Ich merke den Regen auf der Haut. "
            "Ich glaube, es wird kalt und ich spüre das Zittern.\n\n"
            "Die Straße liegt still und die Stadt schweigt.\n\n"
            "Ich spüre die Müdigkeit. Ich merke den Morgen und ich fühle die Sonne.\n"
        )
        config = CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+")
        paragraphs, _ = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(md))
        stats = layer_stats(paragraphs, "filter")
        self.assertTrue(stats)
        for value, z in stats.values():
            self.assertGreaterEqual(value, 0.0)
            self.assertIsInstance(z, float)
        self.assertNotEqual(stats[0][1], stats[1][1])

    def test_layer_stats_values_and_directions(self):
        md = (
            "## Kap 1\n\n"
            "Ich trinke Kaffee und gehe los. Ich sehe den Regen und ich gehe weiter. "
            "Ich trinke Tee und gehe nach Hause.\n\n"
            "Ich spüre die Kälte und ich fühle den Wind. Ich merke den Regen auf der Haut. "
            "Ich glaube, es wird kalt und ich spüre das Zittern.\n\n"
            "Die Straße liegt still und die Stadt schweigt.\n\n"
            "Ich spüre die Müdigkeit. Ich merke den Morgen und ich fühle die Sonne.\n"
        )
        config = CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+")
        paragraphs, _ = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(md))
        stats = layer_stats(paragraphs, "filter")
        self.assertTrue(stats)
        for value, _z in stats.values():
            self.assertGreaterEqual(value, 0.0)
        # Filter-density outliers sit above the chapter median -> positive z
        self.assertGreater(max(z for _v, z in stats.values()), 0.0)
        self.assertLess(min(z for _v, z in stats.values()), 0.0)
        self.assertEqual(layer_stats(paragraphs, "unknown"), {})


class TestFingerprintDashboard(unittest.TestCase):
    def _build(self):
        config = CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+")
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
            parse_markdown_blocks(DIMENSION_SAMPLE)
        )
        metrics = CorpusAnalyzer(config).analyze_text(DIMENSION_SAMPLE)
        fingerprint = StyleFingerprint.from_metrics(metrics)
        return render_dashboard(
            chapters,
            paragraphs,
            metrics=metrics,
            fingerprint=fingerprint,
            title="Testroman",
        )

    def test_fingerprint_dashboard_is_deterministic_and_contains_analysis_panels(self):
        html = self._build()
        self.assertEqual(html, self._build())
        self.assertIn('<table class="heatmap">', html)
        self.assertIn("style-layer", html)
        self.assertIn("data-layers=", html)
        self.assertIn("layer-legend", html)
        self.assertIn("z-gradient", html)
        self.assertIn("Consistency", html)

    def test_dashboard_without_fingerprint_still_works(self):
        config = CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+")
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
            parse_markdown_blocks(SAMPLE)
        )
        metrics = CorpusAnalyzer(config).analyze_text(SAMPLE)
        html = render_dashboard(chapters, paragraphs, metrics=metrics, title="X")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertNotIn('<table class="heatmap">', html)

    def test_dimension_payload_preserves_untrusted_titles_as_data(self):
        title = '<img src=x onerror="window.injected=true"> & heading'
        rendered = api.dashboard(DIMENSION_SAMPLE.replace("Kap 1", title), language="de")
        match = re.search(r'data-dim3d="([^"]*)"', rendered)
        self.assertIsNotNone(match)
        payload = json.loads(html_module.unescape(match.group(1)))
        self.assertEqual(payload["points"][0]["title"], title)
        self.assertEqual(payload["labels"]["flagged"], "auffällige Kapitel")
        self.assertNotIn(title, rendered)

    def test_dimension_controls_expose_initial_state(self):
        rendered = self._build()
        self.assertIsNotNone(re.search(r'id="dim-ctl-traj"[^>]*aria-pressed="true"', rendered))
        self.assertIsNotNone(re.search(r'id="dim-ctl-spin"[^>]*aria-pressed="false"', rendered))

    def test_dimension_loadings_do_not_repeat_features(self):
        groups = re.findall(r'<div class="loadings">(.*?)</div>', self._build())
        self.assertTrue(groups)
        for group in groups:
            names = re.findall(r'<b>(.*?)</b>', group)
            self.assertEqual(len(names), len(set(names)))

    def test_dimension_canvas_omits_unmeasured_chapters(self):
        from lixity.ui.dimensions import style_dimensions

        config = CorpusConfig(language="de")
        _paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(SAMPLE))
        fp = StyleFingerprint(dimensions=[{
            "index": 1, "variance": 1.0, "loadings": {"asl": 1.0},
            "scores": {1: 0.5}, "flagged": [],
        }])
        rendered = style_dimensions(chapters, fp)
        match = re.search(r'data-dim3d="([^"]*)"', rendered)
        payload = json.loads(html_module.unescape(match.group(1)))
        self.assertEqual([point["ch"] for point in payload["points"]], [1])
        self.assertIn("1 / 2", rendered)

    def test_dimension_score_table_preserves_measured_scores_and_safe_titles(self):
        from lixity.language import get_language_profile
        from lixity.ui.dimensions import style_dimensions

        title = '<img src=x onerror="window.injected=true"> & heading'
        config = CorpusConfig(language="de")
        _paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
            parse_markdown_blocks(SAMPLE.replace("Kap 1", title))
        )
        fp = StyleFingerprint(dimensions=[
            {"index": 1, "variance": 0.6, "loadings": {"asl": 1.0},
             "scores": {1: 0.5, 2: 2.0}, "flagged": []},
            {"index": 2, "variance": 0.4, "loadings": {"ttr": -1.0},
             "scores": {1: -1.25}, "flagged": [1]},
        ])
        rendered = style_dimensions(chapters, fp, get_language_profile("de").labels, "de")
        table = re.search(r'<table id="dim-scores".*?</table>', rendered)
        self.assertIsNotNone(table, "chapter scores must be available without JavaScript")
        markup = table.group()
        self.assertIn('scope="col">D1</th>', markup)
        self.assertIn('scope="col">D2</th>', markup)
        self.assertNotIn('scope="col">D3</th>', markup)
        self.assertIn('href="#ch-1"', markup)
        self.assertNotIn('href="#ch-2"', markup)
        self.assertIn("+0,50", markup)
        self.assertIn("-1,25", markup)
        self.assertIn("Auffällig", markup)
        self.assertIn(html_module.escape(title, quote=True), markup)
        self.assertNotIn("<img", markup)

    def test_dimension_accessibility_labels_are_localized(self):
        from lixity.language import get_language_profile

        required = (
            "dim_scores", "dim_not_flagged", "dim_ctl_navigation",
            "dim_ctl_left", "dim_ctl_right", "dim_ctl_up", "dim_ctl_down",
            "dim_ctl_zoom_in", "dim_ctl_zoom_out",
        )
        for language in ("de", "en", "fr", "es", "it", "pt", "nl"):
            with self.subTest(language=language):
                labels = get_language_profile(language).labels
                self.assertFalse([key for key in required if not labels.get(key)])

    def test_changepoint_links_follow_measured_chapter_indices(self):
        from lixity.ui.structural import style_structural

        _paragraphs, chapters = ParagraphProfiler(CorpusConfig(language="de")).profile_blocks(
            parse_markdown_blocks(DIMENSION_SAMPLE)
        )
        fp = StyleFingerprint(
            values={"asl": {1: 5.0, 2: None, 3: 10.0}},
            structural_diagnostics={"changepoints": {"asl": [1]}},
        )
        rendered = style_structural(chapters, fp)
        self.assertIn('data-jump="#ch-3"', rendered)
        self.assertNotIn('data-jump="#ch-2"', rendered)


class TestSignificanceAdjustment(unittest.TestCase):
    """Measurement uncertainty shrinks deviations of noisy (small) chapters."""

    def test_analyzer_provides_style_se(self):
        config = CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+")
        metrics = CorpusAnalyzer(config).analyze_text(SAMPLE)
        for chapter in metrics.chapters:
            self.assertIn("asl", chapter.style_se)
            self.assertGreaterEqual(chapter.style_se["asl"], 0.0)
            self.assertIn("filter_density", chapter.style_se)

    def test_small_chapter_has_larger_se(self):
        config = CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+")
        long_chapter = (
            "## Lang\n\n"
            + (
                "Der Kater schlief. "
                + "Die Sonne schien über den leeren Platz am Bahnhof und die Stadt war still. "
            )
            * 20
        )
        short_chapter = "## Kurz\n\nDer Kater schlief. Die Sonne schien über den Bahnhof.\n"
        metrics = CorpusAnalyzer(config).analyze_text(long_chapter + "\n\n" + short_chapter)
        se_long = metrics.chapters[0].style_se["asl"]
        se_short = metrics.chapters[1].style_se["asl"]
        self.assertGreater(se_short, se_long)


class TestStyleDimensions(unittest.TestCase):
    """Self-calibrated principal dimensions from the feature correlation."""

    @classmethod
    def setUpClass(cls):
        cls.config = CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+")
        cls.metrics = CorpusAnalyzer(cls.config).analyze_text(DIMENSION_SAMPLE)

    def setUp(self):
        self.fp = StyleFingerprint.from_metrics(self.metrics)

    def test_dimensions_are_derived(self):
        self.assertTrue(self.fp.dimensions)
        dim = self.fp.dimensions[0]
        self.assertIn("variance", dim)
        self.assertIn("loadings", dim)
        self.assertIn("scores", dim)
        self.assertIn("flagged", dim)
        self.assertLessEqual(dim["variance"], 1.0)

    def test_dimensions_are_deterministic(self):
        again = StyleFingerprint.from_metrics(self.metrics)
        self.assertEqual(self.fp.dimensions, again.dimensions)
        self.assertEqual(self.fp.redundant_features, again.redundant_features)

    def test_dimension_flags_use_complete_scores_and_are_unique(self):
        fields = ["asl", "staccato_pct", "hd_d"]
        self.fp.baseline = {
            field: {"n": 6, "median": 0.0, "sigma": 1.0} for field in fields
        }
        self.fp.values = {
            fields[0]: dict(enumerate([40.0, 50.0, 60.0, 10.0, 20.0, 30.0], 1)),
            fields[1]: dict(enumerate([10.0, 20.0, 30.0, 40.0, 50.0, 60.0], 1)),
            fields[2]: dict(enumerate([None, None, None, 0.6, 0.7, 0.8], 1)),
        }
        self.fp.z_scores = {i: {} for i in range(1, 7)}
        dimensions = self.fp._derive_dimensions()
        self.assertTrue(dimensions)
        for dimension in dimensions:
            self.assertEqual(set(dimension["scores"]), {4, 5, 6})
            self.assertGreaterEqual(dimension["variance"], 0.0)
            self.assertLessEqual(dimension["variance"], 1.0)
            self.assertEqual(len(dimension["flagged"]), len(set(dimension["flagged"])))
        self.assertAlmostEqual(sum(dim["variance"] for dim in dimensions), 1.0, places=4)
        self.assertEqual(dimensions[0]["scores"], {4: -1.73, 5: 0.0, 6: 1.73})

    def test_dimension_scores_and_variance_use_same_rank_space(self):
        fields = ["asl", "staccato_pct", "kaskade_pct"]
        self.fp.baseline = {
            field: {"n": 4, "median": 0.0, "sigma": 1.0} for field in fields
        }
        self.fp.values = {
            field: dict(enumerate(values, 1))
            for field, values in zip(
                fields, ([1.0, 1.0, 8.0, 1000.0], [4.0, 3.0, 2.0, 1.0], [1.0, 9.0, 2.0, 3.0]),
                strict=True,
            )
        }
        self.fp.z_scores = {i: {} for i in range(1, 5)}
        for dimension in self.fp._derive_dimensions():
            scores = list(dimension["scores"].values())
            mean = sum(scores) / len(scores)
            sample_variance = sum((score - mean) ** 2 for score in scores) / (len(scores) - 1)
            self.assertAlmostEqual(sample_variance / len(fields), dimension["variance"], delta=0.01)
            self.assertAlmostEqual(mean, 0.0, delta=0.01)

    def test_dimensions_require_three_complete_nonconstant_features(self):
        for field in self.fp.values:
            self.fp.values[field][3] = None
        self.assertEqual(self.fp._derive_dimensions(), [])

    def test_passport_meta_v2(self):
        passport = self.fp.passport()
        self.assertEqual(passport["meta"]["schema_version"], 4)
        self.assertIn("expected_false_positives", passport["meta"])
        self.assertIn("dimensions", passport)
        self.assertIn("fdr_flagged", passport)
        self.assertIn("redundant_features", passport)
        self.assertGreaterEqual(passport["meta"]["expected_false_positives"], 0.0)
        # thresholds are stored on the fingerprint (not hardcoded in passport)
        self.assertEqual(passport["meta"]["z_mild"], self.fp.thresholds.z_mild)
        self.assertEqual(passport["meta"]["z_strong"], self.fp.thresholds.z_strong)
        self.assertEqual(passport["meta"]["fdr_q"], self.fp.thresholds.fdr_q)

    def test_injected_thresholds_reach_passport_and_dashboard(self):
        """z_mild/fdr_q travel from from_metrics into passport meta and heatmap legend."""
        from lixity.analyzer import CorpusAnalyzer
        from lixity.language import resolve_language
        from lixity.models import CorpusConfig
        from lixity.style_fingerprint import FingerprintThresholds

        text = "## A\n\nKurzer Satz. Zweiter Satz.\n\n## B\n\nEtwas längerer Satz mit Komma.\n\n## C\n\nNoch einmal anders geschrieben.\n"
        config = CorpusConfig(language="de")
        resolved = resolve_language(config, sample_text=text)
        config = CorpusConfig(language=resolved.key)
        metrics = CorpusAnalyzer(config).analyze_text(text)
        custom = FingerprintThresholds(z_mild=1.5, fdr_q=0.1)
        fp = StyleFingerprint.from_metrics(metrics, thresholds=custom)
        meta = fp.passport()["meta"]
        self.assertEqual(meta["z_mild"], 1.5)
        self.assertEqual(meta["fdr_q"], 0.1)
        self.assertEqual(fp.thresholds.z_strong, 3.5)  # untouched default

    def test_passport_text_lists_dimensions(self):
        text = self.fp.passport_text(labels={"feat_asl": "ASL"})
        self.assertIn("STYLE REFERENCE", text)
        self.assertIn("normal-model reference hits", text)


# ---------------------------------------------------------------------------
#  Structural diagnostics tests
# ---------------------------------------------------------------------------


class TestPELT(unittest.TestCase):

    def test_segmentation_minimizes_guarded_cost_over_all_partitions(self):
        """An exhaustive rational oracle is independent of candidate pruning."""
        from lixity.style_fingerprint import pelt_changepoints

        def cost(segment):
            numbers = [Fraction(value) for value in segment]
            mean = sum(numbers) / len(numbers)
            variance = sum((value - mean) ** 2 for value in numbers) / len(numbers)
            return len(numbers) * math.log(float(variance)) if variance else 0.0

        def objective(values, cuts, penalty):
            edges = (0, *cuts, len(values))
            return math.fsum(
                cost(values[a:b]) + penalty for a, b in itertools.pairwise(edges)
            )

        # Small exhaustive domains expose invalid pruning, including ties.
        cases = itertools.chain(
            itertools.product((0.0, 0.5, 2.0), repeat=4),
            ((-1e16, 1e16, 1e16 + 2.0, 1e16 + 4.0),
             (0.0, 1e16, 1e16 + 2.0, 1e16 + 4.0)),
        )
        for values in cases:
            for penalty in (0.0, 1.0, 4.0, 2.0 * math.log(len(values))):
                cuts = pelt_changepoints(list(values), penalty)
                alternatives = (
                    candidate for count in range(len(values))
                    for candidate in itertools.combinations(range(1, len(values)), count)
                )
                expected = min(objective(values, candidate, penalty) for candidate in alternatives)
                with self.subTest(values=values, penalty=penalty):
                    self.assertAlmostEqual(objective(values, cuts, penalty), expected, places=10)

    def test_segment_cost_is_stable_under_large_translation(self):
        from lixity.style_fingerprint import _segment_cost

        values = [0.0, 0.125, 0.25, 0.375, 0.125]
        translated = [value + 2.0**45 for value in values]
        self.assertAlmostEqual(
            _segment_cost(values, 0, len(values)),
            _segment_cost(translated, 0, len(values)), places=12,
        )
    """Changepoint segmentation via PELT."""

    def test_too_short_returns_empty(self):
        from lixity.style_fingerprint import pelt_changepoints

        self.assertEqual(pelt_changepoints([]), [])
        self.assertEqual(pelt_changepoints([1.0]), [])
        self.assertEqual(pelt_changepoints([1.0, 2.0]), [])

    def test_constant_series_no_changepoint(self):
        from lixity.style_fingerprint import pelt_changepoints

        self.assertEqual(pelt_changepoints([5.0] * 10), [])

    def test_obvious_step_change(self):
        from lixity.style_fingerprint import pelt_changepoints

        # Clear mean shift at index 5
        series = [1.0] * 5 + [10.0] * 5
        cps = pelt_changepoints(series)
        self.assertTrue(len(cps) >= 1)
        # The changepoint should be near index 5
        self.assertTrue(any(4 <= cp <= 6 for cp in cps))

    def test_custom_penalty(self):
        from lixity.style_fingerprint import pelt_changepoints

        series = [1.0] * 5 + [10.0] * 5
        # Very high penalty → no changepoints
        self.assertEqual(pelt_changepoints(series, penalty=1e6), [])

    def test_deterministic(self):
        from lixity.style_fingerprint import pelt_changepoints

        series = [1.0, 2.0, 1.5, 10.0, 11.0, 9.5, 3.0, 2.5]
        self.assertEqual(pelt_changepoints(series), pelt_changepoints(series))


class TestMannKendall(unittest.TestCase):
    """Mann-Kendall monotonic trend test."""

    def test_too_short_returns_none(self):
        from lixity.style_fingerprint import mann_kendall

        self.assertIsNone(mann_kendall([]))
        self.assertIsNone(mann_kendall([1.0]))
        self.assertIsNone(mann_kendall([1.0, 2.0]))

    def test_perfect_upward_trend(self):
        from lixity.style_fingerprint import mann_kendall

        result = mann_kendall([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertIsNotNone(result)
        if result is None:
            return
        tau, s, p = result
        self.assertAlmostEqual(tau, 1.0)
        self.assertGreater(s, 0.0)
        self.assertLess(p, 0.05)

    def test_perfect_downward_trend(self):
        from lixity.style_fingerprint import mann_kendall

        result = mann_kendall([5.0, 4.0, 3.0, 2.0, 1.0])
        self.assertIsNotNone(result)
        if result is None:
            return
        tau, s, _p = result
        self.assertAlmostEqual(tau, -1.0)
        self.assertLess(s, 0.0)

    def test_constant_series(self):
        from lixity.style_fingerprint import mann_kendall

        result = mann_kendall([3.0, 3.0, 3.0, 3.0])
        self.assertIsNotNone(result)
        if result is None:
            return
        tau, s, _p = result
        self.assertAlmostEqual(tau, 0.0)
        self.assertAlmostEqual(s, 0.0)

    def test_deterministic(self):
        from lixity.style_fingerprint import mann_kendall

        data = [2.0, 3.0, 1.0, 5.0, 4.0]
        self.assertEqual(mann_kendall(data), mann_kendall(data))


class TestWassersteinKS(unittest.TestCase):

    def test_wasserstein_matches_exact_cdf_integral_with_unequal_sizes(self):
        from lixity.style_fingerprint import wasserstein_1d

        samples = ([0.0], [0.0, 10.0], [-2.0, 0.0, 0.0], [1.0, 2.0, 5.0, 9.0])
        for x, y in itertools.product(samples, repeat=2):
            knots = sorted(set(x) | set(y))
            expected = sum(
                abs(Fraction(sum(v <= a for v in x), len(x))
                    - Fraction(sum(v <= a for v in y), len(y))) * Fraction(b - a)
                for a, b in itertools.pairwise(knots)
            )
            with self.subTest(x=x, y=y):
                self.assertAlmostEqual(wasserstein_1d(x, y), float(expected), places=12)

    def test_identical_distributions_have_ks_probability_one(self):
        from lixity.style_fingerprint import ks_2sample

        for x in ([1.0], [1.0, 1.0, 2.0], [float(i) for i in range(200)]):
            self.assertEqual(ks_2sample(x, x * 2), (0.0, 1.0))

    def test_ks_small_distance_tail_is_stable(self):
        from lixity.style_fingerprint import ks_2sample

        x = [float(i) for i in range(1000)]
        d, p = ks_2sample(x, [value + 0.5 for value in x])
        self.assertAlmostEqual(d, 0.001, places=12)
        self.assertGreater(p, 0.999999)

    def test_wasserstein_handles_extreme_finite_knots(self):
        from lixity.style_fingerprint import wasserstein_1d

        x = [-1e308, 1e308]
        self.assertEqual(wasserstein_1d(x, list(reversed(x))), 0.0)
        self.assertEqual(wasserstein_1d(x, [-1e308, -1e308]), 1e308)

    def test_distribution_comparisons_reject_nonfinite_samples(self):
        from lixity.style_fingerprint import ks_2sample, wasserstein_1d

        for compare in (ks_2sample, wasserstein_1d):
            for value in (math.nan, math.inf, -math.inf):
                for x, y in (([value], [0.0]), ([0.0], [value])):
                    with self.subTest(compare=compare.__name__, value=value, x=x), self.assertRaisesRegex(ValueError, "finite"):
                        compare(x, y)
    """Wasserstein distance and KS two-sample test."""

    def test_wasserstein_empty(self):
        from lixity.style_fingerprint import wasserstein_1d

        self.assertAlmostEqual(wasserstein_1d([], [1.0, 2.0]), 0.0)
        self.assertAlmostEqual(wasserstein_1d([1.0], []), 0.0)

    def test_wasserstein_identical(self):
        from lixity.style_fingerprint import wasserstein_1d

        x = [1.0, 2.0, 3.0]
        self.assertAlmostEqual(wasserstein_1d(x, x), 0.0)

    def test_wasserstein_shift(self):
        from lixity.style_fingerprint import wasserstein_1d

        x = [0.0, 1.0, 2.0]
        y = [10.0, 11.0, 12.0]
        w = wasserstein_1d(x, y)
        self.assertGreater(w, 0.0)
        self.assertAlmostEqual(w, 10.0, places=1)

    def test_ks_empty(self):
        from lixity.style_fingerprint import ks_2sample

        d, p = ks_2sample([], [1.0])
        self.assertAlmostEqual(d, 0.0)
        self.assertAlmostEqual(p, 1.0)

    def test_ks_identical(self):
        from lixity.style_fingerprint import ks_2sample

        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        d, _p = ks_2sample(x, x)
        self.assertAlmostEqual(d, 0.0)

    def test_ks_different(self):
        from lixity.style_fingerprint import ks_2sample

        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [100.0, 200.0, 300.0, 400.0, 500.0]
        d, p = ks_2sample(x, y)
        self.assertAlmostEqual(d, 1.0)
        self.assertLess(p, 0.05)


class TestDunningG2(unittest.TestCase):
    """Dunning G² keyness test."""

    def test_zero_totals(self):
        from lixity.style_fingerprint import dunning_g2

        self.assertAlmostEqual(dunning_g2(5, 3, 0, 100), 0.0)
        self.assertAlmostEqual(dunning_g2(5, 3, 100, 0), 0.0)

    def test_absent_term(self):
        from lixity.style_fingerprint import dunning_g2

        self.assertAlmostEqual(dunning_g2(0, 0, 100, 100), 0.0)

    def test_overrepresented(self):
        from lixity.style_fingerprint import dunning_g2

        # Term appears 10 times in A (100 words), 1 time in B (100 words)
        g2 = dunning_g2(10, 1, 100, 100)
        self.assertGreater(g2, 0.0)

    def test_underrepresented(self):
        from lixity.style_fingerprint import dunning_g2

        # Term appears 1 time in A (100 words), 10 times in B (100 words)
        g2 = dunning_g2(1, 10, 100, 100)
        self.assertLess(g2, 0.0)

    def test_symmetric(self):
        from lixity.style_fingerprint import dunning_g2

        g_over = dunning_g2(10, 1, 100, 100)
        g_under = dunning_g2(1, 10, 100, 100)
        self.assertAlmostEqual(abs(g_over), abs(g_under))


class TestHillEstimator(unittest.TestCase):
    """Hill tail index estimator."""

    def test_too_short(self):
        from lixity.style_fingerprint import hill_estimator

        self.assertIsNone(hill_estimator([1.0, 2.0, 3.0]))
        self.assertIsNone(hill_estimator([]))

    def test_positive_values(self):
        from lixity.style_fingerprint import hill_estimator

        # Exponential-like tail: alpha should be finite and positive
        data = [float(i) for i in range(1, 101)]
        alpha = hill_estimator(data)
        self.assertIsNotNone(alpha)
        if alpha is not None:
            self.assertGreater(alpha, 0.0)

    def test_custom_k(self):
        from lixity.style_fingerprint import hill_estimator

        data = [float(i) for i in range(1, 51)]
        self.assertIsNotNone(hill_estimator(data, k=5))
        self.assertIsNone(hill_estimator(data, k=1))  # k < 2

    def test_negative_values_return_none(self):
        from lixity.style_fingerprint import hill_estimator

        # All non-positive → None
        self.assertIsNone(hill_estimator([-1.0, -2.0, -3.0, -4.0, -5.0]))

    def test_deterministic(self):
        from lixity.style_fingerprint import hill_estimator

        data = [float(i) for i in range(1, 30)]
        self.assertEqual(hill_estimator(data), hill_estimator(data))


class TestSnQn(unittest.TestCase):

    def test_sn_uses_low_outer_and_high_inner_order_statistics(self):
        from lixity.style_fingerprint import sn_estimator

        for n in (2, 3, 4, 5, 6):
            for values in itertools.combinations_with_replacement((0.0, 1.0, 4.0), n):
                inner = [sorted(abs(a - b) for b in values)[n // 2] for a in values]
                expected = 1.1926 * sorted(inner)[(n - 1) // 2]
                with self.subTest(values=values):
                    self.assertEqual(sn_estimator(list(values)), expected)

    def test_qn_uses_modern_asymptotic_factor_and_pair_rank(self):
        from lixity.style_fingerprint import qn_estimator

        for n in (2, 3, 4, 5, 6):
            values = [float(i * i) for i in range(n)]
            distances = sorted(abs(a - b) for a, b in itertools.combinations(values, 2))
            expected = 2.21914 * distances[math.comb(n // 2 + 1, 2) - 1]
            self.assertEqual(qn_estimator(values), expected)
    """Sn and Qn robust scale estimators (Rousseeuw & Croux)."""

    def test_too_short(self):
        from lixity.style_fingerprint import qn_estimator, sn_estimator

        self.assertAlmostEqual(sn_estimator([]), 0.0)
        self.assertAlmostEqual(sn_estimator([1.0]), 0.0)
        self.assertAlmostEqual(qn_estimator([]), 0.0)
        self.assertAlmostEqual(qn_estimator([1.0]), 0.0)

    def test_constant_returns_zero(self):
        from lixity.style_fingerprint import qn_estimator, sn_estimator

        self.assertAlmostEqual(sn_estimator([5.0] * 5), 0.0)
        self.assertAlmostEqual(qn_estimator([5.0] * 5), 0.0)

    def test_positive_for_spread(self):
        from lixity.style_fingerprint import qn_estimator, sn_estimator

        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertGreater(sn_estimator(data), 0.0)
        self.assertGreater(qn_estimator(data), 0.0)

    def test_sn_qn_comparable_to_mad(self):
        from lixity.style_fingerprint import mad, median, qn_estimator, sn_estimator

        # For Gaussian-ish data, Sn ≈ Qn ≈ 1.4826·MAD (order of magnitude)
        data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        centre = median(data)
        sigma_mad = 1.4826 * mad(data, centre)
        sn = sn_estimator(data)
        qn = qn_estimator(data)
        # Within a factor of 3 for this small sample
        self.assertGreater(sn, sigma_mad * 0.3)
        self.assertLess(sn, sigma_mad * 3.0)
        self.assertGreater(qn, sigma_mad * 0.3)
        self.assertLess(qn, sigma_mad * 3.0)

    def test_deterministic(self):
        from lixity.style_fingerprint import qn_estimator, sn_estimator

        data = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0]
        self.assertEqual(sn_estimator(data), sn_estimator(data))
        self.assertEqual(qn_estimator(data), qn_estimator(data))


class TestStructuralIntegration(unittest.TestCase):
    """Nonempty structural measurements survive passport export and text views."""

    @classmethod
    def setUpClass(cls):
        text = "\n\n".join(
            f"## Chapter {number}\n\n" + (("moss " * length).strip() + ". ") * 20
            for number, length in enumerate((8, 9, 10, 11, 30, 31, 32, 33), 1)
        )
        cls.metrics = CorpusAnalyzer(CorpusConfig(language="en")).analyze_text(text)

    def setUp(self):
        self.fp = StyleFingerprint.from_metrics(self.metrics)

    def test_structural_payload_contains_measured_statistics(self):
        diagnostics = self.fp.structural_diagnostics
        self.assertEqual(set(diagnostics), {
            "changepoints", "trends", "robust_scales", "tail_index", "distribution_shift",
            "trending_features", "segmented_features", "shifted_features",
        })
        # Each half contains four measured chapters; these checks cannot pass
        # vacuously when the distribution-shift implementation returns {}.
        shift = diagnostics["distribution_shift"]["asl"]
        self.assertEqual(shift["wasserstein"], 22.0)
        self.assertEqual(shift["ks_d"], 1.0)
        self.assertGreaterEqual(shift["ks_p"], 0.0)
        self.assertLess(shift["ks_p"], 0.05)
        trend = diagnostics["trends"]["asl"]
        self.assertEqual(trend["tau"], 1.0)
        self.assertEqual(trend["S"], 28.0)
        self.assertLess(trend["p"], 0.05)
        for key in ("trending_features", "segmented_features", "shifted_features"):
            self.assertIn("asl", diagnostics[key])
        scales = diagnostics["robust_scales"]["asl"]
        self.assertEqual(set(scales), {"sn", "qn", "sigma_mad"})
        for value in scales.values():
            self.assertGreater(value, 0.0)
        self.assertGreater(diagnostics["tail_index"]["asl"], 0.0)

    def test_passport_serializes_structural_payload_and_thresholds(self):
        passport = json.loads(json.dumps(self.fp.passport()))
        self.assertEqual(passport["structural_diagnostics"], self.fp.structural_diagnostics)
        self.assertEqual(passport["meta"]["schema_version"], 4)
        self.assertEqual(passport["meta"]["flag_min_severity"], self.fp.thresholds.flag_min_severity)
        self.assertEqual(passport["meta"]["min_chapters"], self.fp.thresholds.min_chapters)

    def test_structural_diagnostics_are_deterministic(self):
        again = StyleFingerprint.from_metrics(self.metrics)
        self.assertEqual(self.fp.structural_diagnostics, again.structural_diagnostics)

    def test_passport_text_describes_actual_shifts_in_both_languages(self):
        for language, shifted in (("en", "shifted features"), ("de", "verschobene Merkmale")):
            with self.subTest(language=language):
                text = self.fp.passport_text(language_key=language)
                self.assertIn(shifted, text)
                if language == "en":
                    self.assertIn("Structural diagnostics", text)



class TestLexicalStructural(unittest.TestCase):

    def test_nonprose_blocks_do_not_change_lexical_diagnostics(self):
        text = "## A\n\n" + "bright birds cross quiet fields. " * 20
        text += "\n\n## B\n\n" + "dark water covers empty streets. " * 20
        decorated = text.replace("## B", "```python\n" + "invented values " * 80 + "\n```\n\n## B")
        self.assertEqual(
            lexical_structural_diagnostics(text), lexical_structural_diagnostics(decorated)
        )
    """Token-level structural: co-occurrence fitness + Dunning keyness halves."""

    @classmethod
    def setUpClass(cls):
        cls.config = CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+")
        # Multi-chapter German prose long enough for keyness (≥ 20 content
        # tokens per half) and co-occurrence (≥ 50 content tokens).
        paragraphs = [
            "Das alte Haus stand am Ende der stillen Straße und der Wind "
            "bewegte die Blätter der Bäume. Die Bewohner sprachen leise "
            "über die kommenden Veränderungen und ihre gemeinsamen Sorgen. "
            "Jeder Morgen begann mit dem Klang der Glocken und dem Duft "
            "von frischem Brot aus der Bäckerei gegenüber. Niemand wusste "
            "genau, wie lange diese Ruhe noch dauern würde in der kleinen "
            "Stadt am Flussufer mit ihren vielen Gassen und Höfen. "
            "Am Nachmittag sammelten sich die Kinder auf dem Markt und "
            "spielten laut, während die Erwachsenen ihre Einkäufe trugen. "
            "Der Lehrer erklärte die neue Ordnung der Dinge und die "
            "Bürger hörten aufmerksam zu, denn niemand wollte den "
            "Frieden gefährden, den man sich über Jahre erarbeitet hatte. "
            "Abends leuchteten die Fenster warm und man hörte Musik aus "
            "den offenen Türen der Gasthäuser am Hafen. Die Fischer "
            "kamen mit ihren Netzen zurück und erzählten von Stürmen, "
            "die niemand am Ufer gesehen hatte. Am nächsten Tag wieder "
            "derselbe Rhythmus: Arbeit, Gespräch und das leise Geheimnis "
            "der Stadt, das jeder für sich behielt und doch mit allen teilte."
        ]
        blocks = [f"## Kap {i + 1}\n\n" + paragraphs[i % len(paragraphs)] + "\n" for i in range(4)]
        cls.text = "\n".join(blocks)
        cls.lexical = lexical_structural_diagnostics(cls.text, cls.config)

    def test_cooccurrence_block(self):
        cooc = self.lexical.get("cooccurrence")
        self.assertIsInstance(cooc, dict)
        if not isinstance(cooc, dict):
            return
        self.assertIn("window", cooc)
        self.assertIn("n_tokens", cooc)
        self.assertIn("mean_degree", cooc)
        self.assertGreaterEqual(cooc["n_tokens"], 50)
        self.assertGreaterEqual(cooc["mean_degree"], 0.0)
        if "fitness" in cooc:
            fitness = cooc["fitness"]
            self.assertIsInstance(fitness, dict)
            if isinstance(fitness, dict):
                self.assertIn("exponent", fitness)
                self.assertIn("ks_distance", fitness)
                self.assertIn("p_value", fitness)

    def test_keyness_block_halves(self):
        keyness = self.lexical.get("keyness")
        self.assertIsInstance(keyness, dict)
        if not isinstance(keyness, dict):
            return
        self.assertEqual(keyness["split"], "first_half_vs_second_half")
        self.assertEqual(keyness["n_early_chapters"], 2)
        self.assertEqual(keyness["n_late_chapters"], 2)
        early = keyness["early_over"]
        late = keyness["late_over"]
        self.assertIsInstance(early, list)
        self.assertIsInstance(late, list)
        for item in early:
            self.assertGreater(item["g2"], 0.0)
            self.assertIn("word", item)
        for item in late:
            self.assertLess(item["g2"], 0.0)

    def test_lexical_is_deterministic(self):
        again = lexical_structural_diagnostics(self.text, self.config)
        self.assertEqual(self.lexical, again)

    def test_empty_text_returns_empty(self):
        self.assertEqual(lexical_structural_diagnostics("", self.config), {})

    def test_single_chapter_skips_keyness_but_may_keep_cooccurrence(self):
        one = "## Kap 1\n\n" + ("Wort " * 80) + "\n"
        out = lexical_structural_diagnostics(one, self.config)
        self.assertNotIn("keyness", out)

    def test_api_fingerprint_merges_lexical_structural(self):
        passport = api.fingerprint(self.text, language="de")
        w2 = passport["structural_diagnostics"]
        self.assertIn("distribution_shift", w2)
        self.assertIn("shifted_features", w2)
        # 4 chapters with enough content -> keyness + cooccurrence both present
        self.assertIn("cooccurrence", w2)
        self.assertIn("keyness", w2)
        json.dumps(passport)


class TestGohBarabasi(unittest.TestCase):
    """Goh–Barabási degree-sequence fitness."""

    def test_empty_and_short_return_none(self):
        from lixity.style_fingerprint import goh_barabasi_fitness

        self.assertIsNone(goh_barabasi_fitness([]))
        self.assertIsNone(goh_barabasi_fitness([1, 2, 3]))
        self.assertIsNone(goh_barabasi_fitness([0, 0, 0, 0, 0, 0]))

    def test_constant_positive_degrees_return_none(self):
        from lixity.style_fingerprint import goh_barabasi_fitness

        self.assertIsNone(goh_barabasi_fitness([3] * 10))

    def test_power_law_like_sequence_fits(self):
        from lixity.style_fingerprint import goh_barabasi_fitness

        # Heavy-tailed degree sequence (scale-free-like)
        degrees = [1] * 40 + [2] * 20 + [3] * 10 + [5] * 5 + [10] * 3 + [20] * 2
        result = goh_barabasi_fitness(degrees)
        self.assertIsNotNone(result)
        if result is None:
            return
        self.assertIn("exponent", result)
        self.assertIn("ks_distance", result)
        self.assertIn("p_value", result)
        self.assertGreater(result["exponent"], 1.0)
        self.assertGreaterEqual(result["ks_distance"], 0.0)
        self.assertLessEqual(result["ks_distance"], 1.0)
        self.assertGreaterEqual(result["p_value"], 0.0)
        self.assertLessEqual(result["p_value"], 1.0)

    def test_deterministic(self):
        from lixity.style_fingerprint import goh_barabasi_fitness

        degrees = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        self.assertEqual(goh_barabasi_fitness(degrees), goh_barabasi_fitness(degrees))


class TestCooccurrenceDegrees(unittest.TestCase):
    """Word co-occurrence degree sequence."""

    def test_empty_and_bad_window(self):
        from lixity.style_fingerprint import cooccurrence_degrees

        self.assertEqual(cooccurrence_degrees([]), [])
        self.assertEqual(cooccurrence_degrees(["a", "b"], window=0), [])

    def test_one_degree_per_token_type(self):
        from lixity.style_fingerprint import cooccurrence_degrees

        tokens = ["a", "b", "c", "a", "b"]
        degrees = cooccurrence_degrees(tokens, window=2)
        self.assertEqual(len(degrees), 3)  # a, b, c
        self.assertTrue(all(d >= 0 for d in degrees))

    def test_isolated_token_has_degree_zero(self):
        from lixity.style_fingerprint import cooccurrence_degrees

        # window=1: edges are only (a,b) and (b,z); every distinct type gets degree >= 1
        tokens = ["a", "b", "z"]
        degrees = cooccurrence_degrees(tokens, window=1)
        self.assertEqual(len(degrees), 3)
        self.assertTrue(all(d >= 1 for d in degrees))

        # One repeated type never co-occurs with a *different* type → degree 0
        alone = cooccurrence_degrees(["q", "q", "q"], window=1)
        self.assertEqual(alone, [0])

    def test_deterministic(self):
        from lixity.style_fingerprint import cooccurrence_degrees

        tokens = ["x", "y", "z", "x", "y"]
        self.assertEqual(cooccurrence_degrees(tokens), cooccurrence_degrees(tokens))


if __name__ == "__main__":
    unittest.main()
