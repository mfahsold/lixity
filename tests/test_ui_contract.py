"""
tests/test_ui_contract.py
=========================
Contracts of the centralised dashboard UI (`lixity.ui`):

- every DOM id the micro-interaction script looks up exists in the render,
- every help key the renderer uses is translated in all seven languages,
- every core UI label key exists in all seven languages,
- the "show, don't tell" components (band chart, loading bars, KPI bars)
  are actually rendered.
"""

import os
import re
import sys
import unittest
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity import CorpusAnalyzer, CorpusConfig  # noqa: E402
from lixity.language import get_language_profile  # noqa: E402
from lixity.language_data import HELP_TEXTS  # noqa: E402
from lixity.markdown_parser import parse_markdown_blocks  # noqa: E402
from lixity.markers import add_marker  # noqa: E402
from lixity.style_fingerprint import StyleFingerprint  # noqa: E402
from lixity.style_profile import ParagraphProfiler  # noqa: E402
from lixity.ui import render_dashboard  # noqa: E402

UI_DIR = Path(BASE_DIR) / "src" / "lixity" / "ui"
LANGUAGES = ("de", "en", "fr", "es", "it", "pt", "nl")

SAMPLE = (
    "## Kap 1\n\n"
    "Ich trinke Kaffee. Ich gehe zum Fenster. Ich sehe den Regen. Ich trinke Tee.\n\n"
    "Ich trinke noch einen Schluck. Ich gehe zur Tür. Ich sehe die Straße und den "
    "Regen auf dem Asphalt, der glänzt.\n\n"
    "Ich spüre die Kälte. Ich merke den Wind. Ich fühle den Regen auf der Haut und "
    "ich glaube, es wird kalt. Ich spüre das Zittern.\n\n"
    "Die Straße liegt still. Die Stadt schweigt. Der Abend kommt.\n\n"
    "## Kap 2\n\n"
    "Das Haus wurde verkauft und die Tür war verschlossen worden. Die Zeitung lag "
    "auf dem Tisch. Die Entscheidung fiel schwer. Die Beschreibung der Wohnung "
    "war ausführlich. Das Haus wurde besichtigt und die Miete war bezahlt worden. "
    "Die Zeitung lag auf dem Boden und die Entscheidung war gefallen. Die "
    "Beschreibung der Wohnung wirkte sachlich und die Miete war hoch.\n\n"
    "Ich trinke Kaffee und ich sehe den Regen. Ich gehe zum Fenster und ich spüre "
    "die Kälte. Ich merke den Wind und ich fühle die Sonne.\n"
)


def _full_dashboard() -> str:
    text, _marker = add_marker(SAMPLE, kind="todo", note="Prüfen", target_line=3)
    config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text))
    metrics = CorpusAnalyzer(config).analyze_text(text)
    fingerprint = StyleFingerprint.from_metrics(metrics)
    from lixity.markers import list_markers

    return render_dashboard(
        chapters,
        paragraphs,
        metrics=metrics,
        fingerprint=fingerprint,
        markers=list_markers(text),
        artifacts=[{"name": "buch.pdf", "size_kb": 1200.0, "href": "buch.pdf", "pages": 184}],
        title="Testroman",
        controls=True,
    )


class TestJsDomContract(unittest.TestCase):
    """Every id the script touches must exist in the markup (no silent breakage)."""

    def test_script_ids_are_rendered(self):
        script = (UI_DIR / "assets" / "dashboard.js").read_text(encoding="utf-8")
        ids = set(re.findall(r'getElementById\("([^"]+)"\)', script))
        ids.discard("lixity-tooltip")  # created by the script itself
        self.assertTrue(ids)
        html = _full_dashboard()
        missing = sorted(dom_id for dom_id in ids if f'id="{dom_id}"' not in html)
        self.assertEqual(missing, [], f"dashboard.js looks up missing ids: {missing}")

    def test_interaction_hooks_are_rendered(self):
        html = _full_dashboard()
        for hook in (
            'class="chip ',
            'data-target="p-',
            "data-layers=",
            'data-chapter="',
            'tabindex="0"',
            'aria-expanded="false"',
            'data-action="load"',
            'data-marker-kind="pruefen"',
            'class="marker-note-slot"',
            'class="kpi kpi-link"',
            'data-jump="#heatmap"',
            'data-jump="#bands"',
            'data-jump="#ch-1"',
            'data-line="3"',
            'data-start="',
            'data-outliers="',
            'data-outliers-one="',
            'id="layer-only"',
            'id="layer-next"',
            'id="layer-legend-count"',
            'role="button"',
        ):
            self.assertIn(hook, html, hook)

    def test_unified_interaction_contract(self):
        """All content drill-downs are keyboard reachable with one vocabulary."""
        script = (UI_DIR / "assets" / "dashboard.js").read_text(encoding="utf-8")
        css = (UI_DIR / "assets" / "dashboard.css").read_text(encoding="utf-8")
        html = _full_dashboard()
        # One selector drives click and keyboard activation.
        self.assertIn('var INTERACTIVE = "[data-jump], [data-line], [role=\'button\']', script)
        self.assertIn("event.target.closest(INTERACTIVE)", script)
        # Focus visibility covers every [role="button"] target.
        self.assertIn('[role=\"button\"]):focus-visible', css)
        # Rows and band rows are announced as buttons and focusable.
        self.assertIn('class="row-link" data-line=', html)
        self.assertIn('role="button" tabindex="0"', html)
        self.assertRegex(html, r'<div class="band"[^>]*role="button" tabindex="0"')


class TestLabelCompleteness(unittest.TestCase):
    """The renderer's label and help keys must exist in every language."""

    @staticmethod
    def _renderer_help_keys() -> set[str]:
        source = (UI_DIR / "dashboard.py").read_text(encoding="utf-8")
        keys = set(re.findall(r"help_term\(\s*labels,\s*[\"']([a-z_]+)[\"']", source))
        keys |= {
            "asl",
            "staccato",
            "kaskade",
            "cv",
            "dialogue",
            "function_words",
            "perception",
            "modal",
            "passive",
            "nominal",
            "adjective",
            "lix",
            "start_entropy",
            "first_start",
            "guiraud",
            "hd_d",
            "mtld",
            "mattr",
            "maas",
        }  # values of _FEATURE_HELP (used dynamically)
        keys.discard("action")  # loop variable, resolved per action key
        return keys

    def test_help_keys_translated_in_all_languages(self):
        keys = self._renderer_help_keys()
        self.assertGreater(len(keys), 20)
        for language in LANGUAGES:
            pack = HELP_TEXTS.get(language, {})
            missing = sorted(k for k in keys if f"help_{k}" not in pack)
            self.assertEqual(missing, [], f"{language}: missing help texts {missing}")

    def test_core_label_keys_in_all_languages(self):
        required = (
            "present",
            "past",
            "mixed",
            "neutral",
            "severity_0",
            "severity_1",
            "severity_2",
            "severity_3",
            "chapter",
            "paragraphs",
            "words",
            "flagged",
            "line",
            "top",
            "hint",
            "legend",
            "no_tense",
            "app_suffix",
            "layer_off",
            "layer_asl",
            "layer_dialogue",
            "layer_function",
            "layer_filter",
            "layer_modal",
            "layer_nominal",
            "layer_passive",
            "click_hint",
            "load_hint",
            "group_scope",
            "group_rhythm",
            "group_language",
            "group_lexis",
            "group_style",
            "marker_pruefen",
            "marker_sachcheck",
            "marker_todo",
            "marker_achtung",
        )
        for language in LANGUAGES:
            labels = get_language_profile(language).labels
            missing = sorted(key for key in required if key not in labels)
            self.assertEqual(missing, [], f"{language}: missing labels {missing}")


class TestShowDontTellComponents(unittest.TestCase):
    """The visual (data-ink) components are part of the render."""

    def test_status_strip_renders_component_states(self):
        text = SAMPLE
        config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text))
        metrics = CorpusAnalyzer(config).analyze_text(text)
        html = render_dashboard(
            chapters,
            paragraphs,
            metrics=metrics,
            title="Status",
            status=[
                {"key": "manuscript", "state": "ok", "detail": "roman.md"},
                {"key": "dossiers", "state": "warn", "detail": "1 Dossier · älter"},
            ],
        )
        self.assertIn('class="status-strip"', html)
        self.assertIn('class="status-item ok"', html)
        self.assertIn('class="status-item warn"', html)
        self.assertIn('class="status-detail">roman.md<', html)
        self.assertIn("Dossiers", html)

    def test_visual_components_rendered(self):
        html = _full_dashboard()
        self.assertIn('class="band-row"', html)  # passport band chart
        self.assertIn('class="band-median"', html)
        self.assertIn('class="loadings"', html)  # dimension loading bars
        self.assertIn('class="kpi-bar"', html)  # KPI proportion bars
        self.assertIn('class="num bar-cell"', html)  # matrix micro-bars
        self.assertIn('class="microhint"', html)  # self-dismissing hint

    def test_passport_numbers_live_in_tooltips(self):
        html = _full_dashboard()
        # the numeric band/median/outlier text is available on demand, not printed
        self.assertRegex(html, r'class="band" title="[^"]*(Median|median)[^"]*"')
        self.assertNotIn('class="num">…', html)


if __name__ == "__main__":
    unittest.main()
