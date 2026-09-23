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

from lixity import api  # noqa: E402
from lixity.analyzer import CorpusAnalyzer  # noqa: E402
from lixity.diversity import hd_d  # noqa: E402
from lixity.markdown_parser import parse_markdown_blocks  # noqa: E402
from lixity.models import CorpusConfig  # noqa: E402
from lixity.style_fingerprint import (  # noqa: E402
    FEATURES,
    StyleFingerprint,
    benjamini_hochberg,
    jacobi_eigh,
    layer_stats,
    lexical_structural_diagnostics,
    mad,
    median,
    robust_z,
    significance_z,
    spearman_rho,
    z_color,
)
from lixity.style_profile import ParagraphProfiler  # noqa: E402
from lixity.ui import render_dashboard  # noqa: E402

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
        self.assertIsNone(hd_d(tokens))
        longer = [f"wort{i % 50}" for i in range(1000)]
        hd1 = hd_d(longer)
        hd2 = hd_d(longer)
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
        self.assertIn("STYLE REFERENCE", text)
        self.assertIn("ASL", text)
        self.assertIn("band", text)
        german = self.fp.passport_text(labels={"feat_asl": "ASL"}, language_key="de")
        self.assertIn("STILREFERENZ", german)
        self.assertIn("Korridor", german)

    def test_single_chapter_no_deviations(self):
        one = CorpusAnalyzer(self.config).analyze_text(
            "## Kap 1\n\nIch trinke Kaffee. Ich gehe zum Fenster. Ich sehe den Regen.\n"
        )
        fp = StyleFingerprint.from_metrics(one)
        self.assertEqual(fp.deviations, {})


class TestParagraphLayers(unittest.TestCase):
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
        config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
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
        self.assertIn("expected hits", text)


# ---------------------------------------------------------------------------
#  Structural diagnostics tests
# ---------------------------------------------------------------------------


class TestPELT(unittest.TestCase):
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
    """Structural diagnostics integrated into the style fingerprint pipeline."""

    def setUp(self):
        self.config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
        self.metrics = CorpusAnalyzer(self.config).analyze_text(SAMPLE)
        self.fp = StyleFingerprint.from_metrics(self.metrics)

    def test_structural_diagnostics_exist(self):
        self.assertIsInstance(self.fp.structural_diagnostics, dict)
        self.assertIn("changepoints", self.fp.structural_diagnostics)
        self.assertIn("trends", self.fp.structural_diagnostics)
        self.assertIn("robust_scales", self.fp.structural_diagnostics)
        self.assertIn("distribution_shift", self.fp.structural_diagnostics)
        self.assertIn("trending_features", self.fp.structural_diagnostics)
        self.assertIn("segmented_features", self.fp.structural_diagnostics)
        self.assertIn("shifted_features", self.fp.structural_diagnostics)

    def test_structural_distribution_shift_structure(self):
        shift = self.fp.structural_diagnostics.get("distribution_shift", {})
        self.assertIsInstance(shift, dict)
        for entry in shift.values():
            self.assertIn("wasserstein", entry)
            self.assertIn("ks_d", entry)
            self.assertIn("ks_p", entry)
            self.assertGreaterEqual(entry["wasserstein"], 0.0)
            self.assertGreaterEqual(entry["ks_p"], 0.0)
            self.assertLessEqual(entry["ks_p"], 1.0)
        shifted = self.fp.structural_diagnostics.get("shifted_features", [])
        for field_name in shifted:
            self.assertIn(field_name, shift)
            self.assertLess(shift[field_name]["ks_p"], 0.05)

    def test_structural_in_passport(self):
        passport = self.fp.passport()
        self.assertIn("structural_diagnostics", passport)
        self.assertEqual(passport["meta"]["schema_version"], 4)

    def test_structural_json_serialisable(self):
        passport = self.fp.passport()
        json.dumps(passport)  # must not raise

    def test_structural_deterministic(self):
        fp2 = StyleFingerprint.from_metrics(self.metrics)
        self.assertEqual(self.fp.structural_diagnostics, fp2.structural_diagnostics)

    def test_trends_structure(self):
        for trend in self.fp.structural_diagnostics.get("trends", {}).values():
            self.assertIn("tau", trend)
            self.assertIn("S", trend)
            self.assertIn("p", trend)
            self.assertGreaterEqual(trend["p"], 0.0)
            self.assertLessEqual(trend["p"], 1.0)

    def test_robust_scales_structure(self):
        for scales in self.fp.structural_diagnostics.get("robust_scales", {}).values():
            self.assertIn("sn", scales)
            self.assertIn("qn", scales)
            self.assertIn("sigma_mad", scales)
            self.assertGreaterEqual(scales["sn"], 0.0)
            self.assertGreaterEqual(scales["qn"], 0.0)

    def test_tail_index_present_when_measurable(self):
        tail = self.fp.structural_diagnostics.get("tail_index", {})
        self.assertIsInstance(tail, dict)
        for alpha in tail.values():
            self.assertGreater(alpha, 0.0)

    def test_passport_meta_reports_all_thresholds(self):
        meta = self.fp.passport()["meta"]
        self.assertIn("flag_min_severity", meta)
        self.assertIn("min_chapters", meta)
        self.assertEqual(meta["flag_min_severity"], self.fp.thresholds.flag_min_severity)
        self.assertEqual(meta["min_chapters"], self.fp.thresholds.min_chapters)

    def test_passport_text_mentions_structural_when_present(self):
        text = self.fp.passport_text(language_key="en")
        w2 = self.fp.structural_diagnostics
        if (
            w2.get("segmented_features")
            or w2.get("trending_features")
            or w2.get("shifted_features")
        ):
            self.assertIn("Structural diagnostics", text)

    def test_passport_text_labels_shifted_in_de_and_en(self):
        fp = StyleFingerprint.from_metrics(self.metrics)
        fp.structural_diagnostics.setdefault("distribution_shift", {"asl": {"ks_p": 0.01}})
        fp.structural_diagnostics["shifted_features"] = ["asl"]
        self.assertIn("shifted features", fp.passport_text(language_key="en"))
        self.assertIn("verschobene Merkmale", fp.passport_text(language_key="de"))


class TestLexicalStructural(unittest.TestCase):
    """Token-level structural: co-occurrence fitness + Dunning keyness halves."""

    def setUp(self):
        self.config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
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
        self.text = "\n".join(blocks)
        self.lexical = lexical_structural_diagnostics(self.text, self.config)

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
