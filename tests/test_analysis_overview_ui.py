"""Analysis overview disclosure and measurement-availability regressions."""

import copy
import re
import unittest
from xml.etree import ElementTree

from lixity.models import CorpusConfig, CorpusMetrics
from lixity.pipeline import analyze_document
from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui import render_dashboard
from lixity.workspace_labels import WORKSPACE_LABELS
from tests.support import HtmlControls


class TestAnalysisOverview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prose = (
            "Mara walks to the gate. I see the light. I go to the house. "
            "I went to the house. I saw the tree. I heard the bell. I saw the light. "
        )
        cls.text = "\n\n".join(
            f"## Chapter {number}\n\n" + prose * (8 + number)
            for number in range(1, 4)
        ) + "\n\n## Short observation\n\nMara waits."
        cls.analysis = analyze_document(
            cls.text, CorpusConfig(language="en"),
            FingerprintThresholds(z_mild=100, z_strong=100),
        )

    def render(self, *, controls=True):
        analysis = self.analysis
        return render_dashboard(
            analysis.chapters, analysis.paragraphs, metrics=analysis.metrics,
            fingerprint=analysis.fingerprint, controls=controls,
            title="Synthetic overview",
        )

    def test_deviation_count_distinguishes_measured_zero_and_unavailable(self):
        html = self.render()
        panel = html.split('id="matrix"', 1)[1].split("</section>", 1)[0]
        body = panel.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", body, re.DOTALL)
        counts = [re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.DOTALL)[-1] for row in rows]
        self.assertEqual(counts, ["0", "0", "0", "–"])

    def test_measurements_start_collapsed_without_removing_values(self):
        html = self.render()
        disclosure = re.search(
            r'<details\b([^>]*\bid="analysis-measurements"[^>]*)>(.*?)</details>',
            html, re.DOTALL,
        )
        self.assertIsNotNone(disclosure)
        attributes, contents = disclosure.groups()
        self.assertNotRegex(attributes, r"\bopen\b")
        self.assertIn("<summary>", contents)
        for metric in ("Average words per sentence", "Share of short sentences", "Flesch", "LIX"):
            self.assertIn(metric, contents)
        vocabulary = contents.split('id="kpi-lexis-drawer"', 1)[1]
        for metric in ("TTR", "Guiraud R", "HD-D", "MTLD", "MATTR", "Maas a²"):
            self.assertIn(metric, vocabulary)
        self.assertIn('id="flags"', html[disclosure.end():])
        self.assertIn('id="matrix"', html[disclosure.end():])
        flags = html.split('id="flags"', 1)[1].split("</h2>", 1)[0]
        self.assertIn('class="badge"', flags)

    def test_readability_formulas_show_counted_inputs_once(self):
        text = "## Overwhelming chapter title\n\nA garden rests. A gardener works."
        analysis = analyze_document(text, CorpusConfig(language="en"), FingerprintThresholds())
        html = render_dashboard(analysis.chapters, analysis.paragraphs, metrics=analysis.metrics)
        measurements = html.split('id="analysis-measurements"', 1)[1].split("</details>", 1)[0]
        self.assertEqual(measurements.count("Flesch Reading Ease"), 1)
        self.assertEqual(measurements.count("LIX"), 1)
        self.assertIn("Readability formulas (heuristic)", measurements)
        self.assertIn("Analyzed word tokens 6 · Sentences 2 · 3.00 words per sentence", measurements)
        flesch, lix = measurements.split('>LIX</span>', 1)
        self.assertIn("<b>76.9</b>", flesch)
        self.assertIn("Estimated syllables 9 · 1.50 per word", flesch)
        self.assertIn("<b>19.7</b>", lix)
        self.assertIn("Long words (&gt;6 characters) 1 (16.7%)", lix)

        # Older payloads still render their formula values and known inputs.
        restored = CorpusMetrics.model_validate(analysis.metrics.model_dump())
        legacy_html = render_dashboard(analysis.chapters, analysis.paragraphs, metrics=restored)
        legacy = legacy_html.split('id="analysis-measurements"', 1)[1].split("</details>", 1)[0]
        self.assertIn("<b>76.9</b>", legacy)
        self.assertIn("<b>19.7</b>", legacy)
        self.assertIn("Estimated syllables · 1.50 per word", legacy)
        self.assertNotIn("Estimated syllables 9", legacy)
        self.assertNotIn("Long words (&gt;6 characters) 1", legacy)

    def test_standalone_report_keeps_measurements_open(self):
        html = self.render(controls=False)
        disclosure = re.search(r'<details\b([^>]*\bid="analysis-measurements"[^>]*)>', html)
        self.assertIsNotNone(disclosure)
        self.assertRegex(disclosure[1], r"\bopen\b")
        self.assertIn('id="matrix"', html)

    def test_measurement_links_resolve_for_every_style_availability(self):
        config = CorpusConfig(language="en")
        thresholds = FingerprintThresholds()
        short = analyze_document("## One\n\nMara waits at the gate. Tomas sees her.", config, thresholds)
        empty = analyze_document("", config, thresholds)
        for controls in (True, False):
            for case, analysis, has_fingerprint, expected in (
                ("calibrated", self.analysis, True, {"heatmap", "bands", "matrix", "chapters"}),
                ("short", short, True, {"style", "matrix", "chapters"}),
                ("without fingerprint", self.analysis, False, {"matrix", "chapters"}),
                ("empty", empty, True, set()),
            ):
                with self.subTest(controls=controls, case=case):
                    html = render_dashboard(
                        analysis.chapters, analysis.paragraphs, metrics=analysis.metrics,
                        fingerprint=analysis.fingerprint if has_fingerprint else None, controls=controls,
                    )
                    measurements = html.split('id="analysis-measurements"', 1)[1].split('id="flags"', 1)[0]
                    targets = set(re.findall(r'data-jump="#([^"]+)"', measurements))
                    self.assertTrue(expected <= targets)
                    self.assertTrue(targets <= HtmlControls(html).elements.keys())
                    if case != "calibrated":
                        self.assertFalse({"heatmap", "bands"} & targets)
                    if case == "short":
                        vocabulary = measurements.split('id="kpi-lexis-drawer"', 1)[1].split("</details>", 1)[0]
                        self.assertIn('<div class="kpi"><b>–</b>', vocabulary)
                        self.assertNotRegex(vocabulary, r'<div class="kpi kpi-link"[^>]*><b>–</b>')
                    if case == "empty":
                        self.assertFalse(targets)

    def test_style_space_review_route_requires_measured_chapter_scores(self):
        analysis = self.analysis
        for controls in (True, False):
            with self.subTest(controls=controls):
                html = self.render(controls=controls)
                route = html.split('id="analysis-review"', 1)[1].split('</section>', 1)[0]
                if controls:
                    self.assertIn('data-analysis-workflow="compare"', route)
                    self.assertNotIn('href="#dim-canvas"', route)
                else:
                    self.assertIn('href="#dim-canvas"', route)
                    self.assertIn('data-jump="#dim-canvas"', route)
                fingerprint = copy.deepcopy(analysis.fingerprint)
                fingerprint.dimensions[0]["scores"] = {}
                unavailable = render_dashboard(
                    analysis.chapters, analysis.paragraphs, metrics=analysis.metrics,
                    fingerprint=fingerprint, controls=controls, title="Synthetic overview",
                )
                route = unavailable.split('id="analysis-review"', 1)[1].split('</section>', 1)[0]
                self.assertNotIn('href="#dim-canvas"', route)

    def test_scrollable_tables_have_named_keyboard_regions_and_column_scopes(self):
        html = self.render()
        for panel_id, name in (("flags", "Tense findings"), ("matrix", "Chapter matrix"),
                               ("heatmap", "Style fingerprint")):
            with self.subTest(panel=panel_id):
                panel = html.split(f'id="{panel_id}"', 1)[1].split("</section>", 1)[0]
                self.assertRegex(panel, r'<div\b[^>]*tabindex="0"[^>]*role="region"')
                self.assertIn(f'aria-label="{name}"', panel)
                headings = re.findall(r"<th\b([^>]*)>", panel.split("</thead>", 1)[0])
                self.assertTrue(headings)
                self.assertTrue(all('scope="col"' in attributes for attributes in headings))

    def test_matrix_explains_its_distinct_measurement_coverage(self):
        html = self.render()
        panel = html.split('id="matrix"', 1)[1].split("</section>", 1)[0]
        self.assertIn('<details class="panel-disclosure analysis-coverage">', panel)
        self.assertIn("words per sentence", panel)
        self.assertIn("30 of every 100 words are in recognized quotes or marked speech", panel)
        self.assertIn("What is counted", panel)
        self.assertIn("blockquotes", panel)

    def test_style_layer_is_grouped_with_optgroups_and_preserves_attributes(self):
        html = self.render()
        controls = HtmlControls(html)
        self.assertEqual(controls.elements["style-layer"]["tag"], "select")
        self.assertTrue(controls.elements["style-layer"].get("data-help"))
        match = re.search(r'<select\b[^>]*\bid="style-layer"[^>]*>(.*?)</select>', html, re.DOTALL)
        self.assertIsNotNone(match, "Expected #style-layer select element")
        select_body = match.group(1)
        # Check first top-level option is the empty/off value
        first_option = re.search(r'^\s*<option value="">(.*?)</option>', select_body)
        self.assertIsNotNone(first_option)
        self.assertEqual(first_option.group(1), "None")

        optgroups = ElementTree.fromstring(f"<select>{select_body}</select>").findall("optgroup")  # noqa: S314
        self.assertEqual(len(optgroups), 3)
        expected_groups = [
            ("Sentence & Rhythm", ("asl", "function")),
            ("Voice & Dialogue", ("filter", "sensory")),
            ("Grammar & Style", ("passive", "modal", "nominal")),
        ]
        for (expected_label, expected_members), group in zip(expected_groups, optgroups, strict=True):
            self.assertEqual(group.attrib["label"], expected_label)
            options = group.findall("option")
            actual_keys = tuple(option.attrib["value"] for option in options)
            self.assertEqual(actual_keys, expected_members)
            for option in options:
                key = option.attrib["value"]
                self.assertTrue(option.attrib["data-hint"], f"Hint should not be empty for {key}")
                self.assertTrue(option.attrib["data-unit"])
                self.assertGreaterEqual(int(option.attrib["data-comparable"]), 0)
                self.assertEqual(option.attrib["data-reference"], f"measure-{key}")

    def test_reader_analysis_switches_render_pill_toggles_with_accessible_controls(self):
        html = self.render()
        self.assertIn('class="reader-analysis-switches"', html)
        self.assertIn('class="reader-evidence-toggle"', html)
        self.assertIn('id="analysis-evidence-enabled"', html)
        self.assertIn('class="reader-comparison-toggle"', html)
        self.assertIn('id="analysis-comparison-enabled"', html)
        # Sentence evidence can cover the entire manuscript, so opt in to it.
        controls = HtmlControls(html)
        evidence = controls.inputs["analysis-evidence-enabled"]
        comparison = controls.inputs["analysis-comparison-enabled"]
        self.assertNotIn("checked", evidence)
        self.assertIn("checked", comparison)
        for attributes, help_id in ((evidence, "reader-counted-help"), (comparison, "reader-comparison-help"),
                                    (controls.inputs["filter-flags"], "reader-tense-filter-help")):
            self.assertEqual(attributes["type"], "checkbox")
            self.assertEqual(attributes.get("aria-describedby"), help_id)
            self.assertIn(f'id="{help_id}"', html)

    def test_comparison_labels_describe_the_visible_effect(self):
        html = self.render()
        self.assertTrue("Emphasize deviations in chapter strips" in html)
        self.assertIn("Abweichungen", WORKSPACE_LABELS["de"]["layer_coverage"])


if __name__ == "__main__":
    unittest.main()
