"""
tests/test_style_fingerprint.py
===============================
Tests for the self-calibrating style fingerprint: robust statistics
(median/MAD/z), the consistency heuristic, the Jensen-Shannon chapter
divergence with driver words, HD-D, the style passport and the
heatmap/layer rendering of the dashboard.
"""

import json
import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity.analyzer import CorpusAnalyzer  # noqa: E402
from lixity.markdown_parser import parse_markdown_blocks  # noqa: E402
from lixity.models import CorpusConfig  # noqa: E402
from lixity.style_fingerprint import (  # noqa: E402
    FEATURES,
    StyleFingerprint,
    benjamini_hochberg,
    jacobi_eigh,
    layer_colors,
    layer_stats,
    mad,
    median,
    robust_z,
    significance_z,
    spearman_rho,
    z_color,
)
from lixity.style_profile import ParagraphProfiler  # noqa: E402
from lixity.visualizer import render_dashboard  # noqa: E402

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


class TestRobustStatistics(unittest.TestCase):
    def test_median(self):
        self.assertEqual(median([1.0, 2.0, 3.0]), 2.0)
        self.assertEqual(median([1.0, 2.0, 3.0, 4.0]), 2.5)

    def test_mad(self):
        self.assertAlmostEqual(mad([1.0, 2.0, 3.0], 2.0), 1.0)
        self.assertEqual(mad([5.0], 5.0), 0.0)
        self.assertEqual(mad([], 0.0), 0.0)

    def test_robust_z(self):
        self.assertAlmostEqual(robust_z(3.0, 2.0, 1.0), 0.6745)
        self.assertAlmostEqual(robust_z(1.0, 2.0, 1.0), -0.6745)
        self.assertEqual(robust_z(9.0, 2.0, 0.0), 0.0)

    def test_z_color_is_deterministic_and_clamped(self):
        self.assertEqual(z_color(0.0), z_color(0.0))
        self.assertRegex(z_color(0.0), r"^#[0-9a-f]{6}$")
        self.assertEqual(z_color(100.0), z_color(2.5))
        self.assertEqual(z_color(-100.0), z_color(-2.5))


class TestAnalyzerStyleFeatures(unittest.TestCase):
    def setUp(self):
        self.config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
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

    def test_hd_d_deterministic_and_none_for_short_texts(self):
        tokens = ["a", "b", "c"]
        self.assertIsNone(CorpusAnalyzer.hd_d(tokens))
        longer = [f"wort{i % 50}" for i in range(1000)]
        hd1 = CorpusAnalyzer.hd_d(longer)
        hd2 = CorpusAnalyzer.hd_d(longer)
        self.assertIsNotNone(hd1)
        self.assertIsNotNone(hd2)
        if hd1 is None or hd2 is None:
            self.fail("HD-D should be measurable for 1000 tokens")
        self.assertAlmostEqual(hd1, hd2)
        self.assertGreaterEqual(hd1, 0.0)
        self.assertLessEqual(hd1, 1.0)


class TestStyleFingerprint(unittest.TestCase):
    def setUp(self):
        self.config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
        self.metrics = CorpusAnalyzer(self.config).analyze_text(SAMPLE)
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
        self.assertIn("STILPASS", text)
        self.assertIn("ASL", text)
        self.assertIn("Korridor", text)

    def test_single_chapter_no_deviations(self):
        one = CorpusAnalyzer(self.config).analyze_text(
            "## Kap 1\n\nIch trinke Kaffee. Ich gehe zum Fenster. Ich sehe den Regen.\n"
        )
        fp = StyleFingerprint.from_metrics(one)
        self.assertEqual(fp.deviations, {})


class TestParagraphLayers(unittest.TestCase):
    def test_layer_colors_within_chapter(self):
        md = (
            "## Kap 1\n\n"
            "Ich trinke Kaffee und gehe los. Ich sehe den Regen und ich gehe weiter. "
            "Ich trinke Tee und gehe nach Hause.\n\n"
            "Ich spüre die Kälte und ich fühle den Wind. Ich merke den Regen auf der Haut. "
            "Ich glaube, es wird kalt und ich spüre das Zittern.\n\n"
            "Die Straße liegt still und die Stadt schweigt.\n\n"
            "Ich spüre die Müdigkeit. Ich merke den Morgen und ich fühle die Sonne.\n"
        )
        config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
        paragraphs, _ = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(md))
        colors = layer_colors(paragraphs, "filter")
        self.assertTrue(any(v is not None for v in colors.values()))
        for color in colors.values():
            if color:
                self.assertRegex(color, r"^#[0-9a-f]{6}$")
        self.assertIsNotNone(colors.get(0))
        self.assertIsNotNone(colors.get(1))
        self.assertNotEqual(colors[0], colors[1])

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
        config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
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
        config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
            parse_markdown_blocks(SAMPLE)
        )
        metrics = CorpusAnalyzer(config).analyze_text(SAMPLE)
        fingerprint = StyleFingerprint.from_metrics(metrics)
        return render_dashboard(
            chapters,
            paragraphs,
            metrics=metrics,
            fingerprint=fingerprint,
            title="Testroman",
        )

    def test_heatmap_and_passport_panels(self):
        html = self._build()
        self.assertIn('<table class="heatmap">', html)
        self.assertIn("style-layer", html)
        self.assertIn("data-layers=", html)
        self.assertIn("layer-legend", html)
        self.assertIn("z-gradient", html)
        self.assertIn("Consistency", html)

    def test_dashboard_without_fingerprint_still_works(self):
        config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
            parse_markdown_blocks(SAMPLE)
        )
        metrics = CorpusAnalyzer(config).analyze_text(SAMPLE)
        html = render_dashboard(chapters, paragraphs, metrics=metrics, title="X")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertNotIn('<table class="heatmap">', html)

    def test_dashboard_is_deterministic_with_fingerprint(self):
        self.assertEqual(self._build(), self._build())


class TestJacobiEigendecomposition(unittest.TestCase):
    """Cyclic Jacobi rotations: correctness, orthogonality, determinism."""

    def test_eigenvalues_and_eigenvectors_of_known_matrix(self):
        matrix = [[2.0, 0.0], [0.0, 3.0]]
        eigenvalues, _ = jacobi_eigh(matrix)
        self.assertAlmostEqual(eigenvalues[0], 3.0)
        self.assertAlmostEqual(eigenvalues[1], 2.0)

    def test_orthonormal_eigenvectors(self):
        matrix = [
            [1.0, 0.5, 0.2],
            [0.5, 1.0, -0.3],
            [0.2, -0.3, 1.0],
        ]
        _, eigenvectors = jacobi_eigh(matrix)
        for i in range(3):
            for j in range(3):
                dot = sum(eigenvectors[i][k] * eigenvectors[j][k] for k in range(3))
                self.assertAlmostEqual(dot, 1.0 if i == j else 0.0, places=10)

    def test_reconstruction(self):
        matrix = [
            [1.0, 0.4, 0.1, -0.2],
            [0.4, 1.0, 0.3, 0.1],
            [0.1, 0.3, 1.0, -0.4],
            [-0.2, 0.1, -0.4, 1.0],
        ]
        eigenvalues, eigenvectors = jacobi_eigh(matrix)
        for i in range(4):
            lhs = [sum(matrix[i][k] * eigenvectors[1][k] for k in range(4))]
            rhs = [eigenvalues[1] * eigenvectors[1][i]]
            self.assertAlmostEqual(lhs[0], rhs[0], places=8)
        self.assertAlmostEqual(sum(eigenvalues), 4.0, places=8)

    def test_deterministic(self):
        matrix = [
            [1.0, 0.5, 0.2],
            [0.5, 1.0, -0.3],
            [0.2, -0.3, 1.0],
        ]
        self.assertEqual(jacobi_eigh(matrix), jacobi_eigh(matrix))


class TestSpearman(unittest.TestCase):
    def test_perfect_monotone(self):
        self.assertAlmostEqual(spearman_rho([1.0, 2.0, 3.0, 4.0], [10.0, 20.0, 30.0, 40.0]), 1.0)
        self.assertAlmostEqual(spearman_rho([1.0, 2.0, 3.0, 4.0], [40.0, 30.0, 20.0, 10.0]), -1.0)

    def test_ties_are_averaged(self):
        self.assertAlmostEqual(spearman_rho([1.0, 1.0, 2.0], [1.0, 2.0, 2.0]), 0.5, places=6)


class TestSignificanceAdjustment(unittest.TestCase):
    """Measurement uncertainty shrinks deviations of noisy (small) chapters."""

    def test_benjamini_hochberg(self):
        cells = [(1, "asl", 0.001), (2, "asl", 0.03), (3, "asl", 0.04), (4, "asl", 0.5)]
        flagged = benjamini_hochberg(cells, q=0.05)
        self.assertEqual(flagged, [(1, "asl")])

    def test_noise_shrinks_z(self):
        self.assertAlmostEqual(significance_z(5.0, 0.0, 2.0, 0.0), 2.5)
        self.assertLess(abs(significance_z(5.0, 0.0, 2.0, 1.5)), 2.5)

    def test_analyzer_provides_style_se(self):
        config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
        metrics = CorpusAnalyzer(config).analyze_text(SAMPLE)
        for chapter in metrics.chapters:
            self.assertIn("asl", chapter.style_se)
            self.assertGreaterEqual(chapter.style_se["asl"], 0.0)
            self.assertIn("filter_density", chapter.style_se)

    def test_small_chapter_has_larger_se(self):
        config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
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

    def setUp(self):
        self.config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
        self.metrics = CorpusAnalyzer(self.config).analyze_text(SAMPLE)
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

    def test_passport_meta_v2(self):
        passport = self.fp.passport()
        self.assertEqual(passport["meta"]["schema_version"], 2)
        self.assertIn("expected_false_positives", passport["meta"])
        self.assertIn("dimensions", passport)
        self.assertIn("fdr_flagged", passport)
        self.assertIn("redundant_features", passport)
        self.assertGreaterEqual(passport["meta"]["expected_false_positives"], 0.0)

    def test_passport_text_lists_dimensions(self):
        text = self.fp.passport_text(labels={"feat_asl": "ASL"})
        self.assertIn("STILPASS", text)
        self.assertIn("Zufallstreffer", text)


if __name__ == "__main__":
    unittest.main()
