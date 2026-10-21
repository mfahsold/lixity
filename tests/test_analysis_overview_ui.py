"""Analysis overview disclosure and measurement-availability regressions."""

import re
import unittest

from lixity.models import CorpusConfig
from lixity.pipeline import analyze_document
from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui import render_dashboard


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
        for metric in ("ASL", "Flesch", "LIX", "TTR", "Guiraud R", "HD-D", "MTLD", "MATTR", "Maas a²"):
            self.assertIn(metric, contents)
        self.assertGreaterEqual(contents.count('class="kpi '), 20)
        self.assertIn('id="flags"', html[disclosure.end():])
        self.assertIn('id="matrix"', html[disclosure.end():])
        flags = html.split('id="flags"', 1)[1].split("</h2>", 1)[0]
        self.assertIn('class="badge"', flags)

    def test_standalone_report_keeps_measurements_open(self):
        html = self.render(controls=False)
        disclosure = re.search(r'<details\b([^>]*\bid="analysis-measurements"[^>]*)>', html)
        self.assertIsNotNone(disclosure)
        self.assertRegex(disclosure[1], r"\bopen\b")
        self.assertIn('id="matrix"', html)

    def test_scrollable_tables_have_named_keyboard_regions_and_column_scopes(self):
        html = self.render()
        for panel_id, name in (("flags", "Flagged passages"), ("matrix", "Chapter matrix"),
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
        self.assertIn('<details class="analysis-coverage">', panel)
        self.assertIn("What is counted", panel)
        self.assertIn("blockquotes", panel)


if __name__ == "__main__":
    unittest.main()
