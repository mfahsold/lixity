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
from lixity.workspace_labels import WORKSPACE_LABELS  # noqa: E402

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
    "Ich trinke Kaffee und ich ging zum Laden. Ich sehe den Regen und ich kaufte Brot. "
    "Ich gehe nach Hause und ich trank den Tee.\n\n"
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
    # Three complete, varying chapters exercise the optional rank-space panel.
    complete = SAMPLE.replace(
        "## Kap 2", "Ich schaue hinaus. Vor dem Fenster ziehen dunkle Wolken vorbei. " * 3 + "\n\n## Kap 2"
    )
    complete += "\n" + "Im Zimmer wartet eine Frau neben dem Fenster. " * 8
    complete += "\n\n## Kap 3\n\n" + "Der Morgen beginnt. Regen fällt auf die Straße. " * 15
    text, _marker = add_marker(complete, kind="todo", note="Prüfen", target_line=3)
    config = CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+")
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text))
    metrics = CorpusAnalyzer(config).analyze_text(text)
    fingerprint = StyleFingerprint.from_metrics(metrics)
    from lixity.characters import presence_report
    from lixity.dialogue import dialogue_report
    from lixity.markers import list_markers
    from lixity.motifs import motif_report
    from lixity.pacing import pacing_report
    from lixity.showing import showing_report

    return render_dashboard(
        chapters,
        paragraphs,
        metrics=metrics,
        fingerprint=fingerprint,
        markers=list_markers(text),
        artifacts=[{"name": "buch.pdf", "size_kb": 1200.0, "href": "buch.pdf", "pages": 184}],
        dialogue=dialogue_report(text, config).to_dict(),
        characters=presence_report(text, ["Ich"], config),
        pacing=pacing_report(text, config).to_dict(),
        motifs=motif_report(text, {"Ich": r"\bIch\b"}, config).to_dict(),
        showing=showing_report(text, config, metrics=metrics).to_dict(),
        title="Testroman",
        controls=True,
    )


class TestJsDomContract(unittest.TestCase):
    """Every id the script touches must exist in the markup (no silent breakage)."""

    def test_script_ids_are_rendered(self):
        script = "\n".join(
            asset.read_text(encoding="utf-8") for asset in sorted((UI_DIR / "assets").glob("*.js"))
        )
        ids = set(re.findall(r'getElementById\("([^"]+)"\)', script))
        ids.discard("lixity-tooltip")  # created by the script itself
        self.assertTrue(ids)
        # Onboarding controls exist only in the empty/research-only state.
        html = (
            _full_dashboard()
            + render_dashboard([], [], controls=True)
            + render_dashboard([], [], controls=True, enabled_actions=("analyze", "rebuild"))
            + render_dashboard([], [], controls=True, enabled_actions=("nda-draft",))
        )
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
            'data-jump="#ch-',
            'data-line="3"',
            'data-start="',
            'data-outliers="',
            'data-outliers-one="',
            'id="layer-only"',
            'id="layer-next"',
            'id="layer-legend-count"',
            'role="button"',
            'id="dialogue"',
            'id="characters"',
            'id="pacing"',
            'id="motifs"',
            'id="showing"',
            'id="structural"',
            'class="table-wrap"',
            "data-marker-resolve=",
            'data-jump="#ch-',
            'id="flags"',
            'class="row-link flag-row"',
            'data-target="p-',
            'class="ptext" id="p-',
            'data-start="',
            'data-end="',
            'data-marker-kind="todo"',
            'class="badge sev-',
        ):
            self.assertIn(hook, html, hook)

    def test_flags_panel_contract(self):
        """Flagged list: row → paragraph jump, filter context, marker quick-add."""
        html = _full_dashboard()
        self.assertIn('id="flags"', html)
        # rows carry line anchor + paragraph target + only-flags drill-down
        self.assertRegex(
            html,
            r'class="row-link flag-row" data-line="\d+" data-target="p-\d+" data-flags="1"',
        )
        # quick TODO button with its own note slot inside the row
        self.assertIn('data-marker-kind="todo"', html)
        # paragraph panels are addressable by line span
        self.assertRegex(html, r'class="ptext" id="p-\d+" data-start="\d+" data-end="\d+"')
        # KPI "flagged" jumps to the flags panel
        self.assertIn('data-jump="#flags"', html)

    def test_marker_controls_do_not_jump(self):
        """The JS guard keeps marker clicks from scrolling the page."""
        script = (UI_DIR / "assets" / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn("function isMarkerControl", script)
        self.assertIn("[data-marker-kind], [data-marker-resolve]", script)
        self.assertIn("!isMarkerControl(event.target)", script)
        # jumpToLine opens the target paragraph (data-target / line span)
        self.assertIn('getAttribute("data-target")', script)
        self.assertIn(".ptext[data-start]", script)
        self.assertIn("toggleParagraph(chip, true)", script)

    def test_unified_interaction_contract(self):
        """All content drill-downs are keyboard reachable with one vocabulary."""
        script = (UI_DIR / "assets" / "dashboard.js").read_text(encoding="utf-8")
        css = (UI_DIR / "assets" / "dashboard.css").read_text(encoding="utf-8")
        html = _full_dashboard()
        # One selector drives click and keyboard activation.
        self.assertIn("var INTERACTIVE = \"[data-jump], [data-line], [role='button']", script)
        self.assertIn("event.target.closest(INTERACTIVE)", script)
        # Focus visibility covers every [role="button"] target.
        self.assertIn('[role="button"]):focus-visible', css)
        # Rows and band rows are announced as buttons and focusable.
        self.assertIn('class="row-link" data-line=', html)
        self.assertIn('role="button" tabindex="0"', html)
        self.assertRegex(
            html, r'<div class="band-row"[^>]*data-jump="#feat-[^"]+"[^>]*role="button"'
        )
        self.assertRegex(html, r'<div class="band" title="[^"]*"')
        # Heatmap column anchors for every feature in the passport
        self.assertIn('id="feat-asl"', html)
        self.assertIn('id="feat-dialog_pct"', html)

    def test_style_reference_rows_are_clickable(self):
        """Passport rows jump to their heatmap column; outlier counts open a chapter."""
        html = _full_dashboard()
        # every band row carries a feat-* anchor and is a button
        rows = re.findall(r'<div class="band-row"([^>]*)>', html)
        self.assertTrue(rows, "no band rows rendered")
        for attrs in rows:
            self.assertRegex(attrs, r'data-jump="#feat-[^"]+"')
            self.assertIn('role="button"', attrs)
        # heatmap headers expose matching ids
        fields = re.findall(r'id="feat-([^"]+)"', html)
        self.assertIn("asl", fields)
        self.assertIn("dialog_pct", fields)
        # at least one row has a layer
        self.assertRegex(html, r'class="band-row"[^>]*data-layer="')
        # outlier counts (when present) open the strongest chapter
        if 'class="band-count band-outlier"' in html:
            self.assertRegex(
                html,
                r'class="band-count band-outlier"[^>]*data-jump="#ch-\d+"[^>]*role="button"',
            )

    def test_sensitivity_settings_render(self):
        """Statistical sensitivity inputs are in the settings group with labels."""
        html = _full_dashboard()
        self.assertIn('id="set-z-mild"', html)
        self.assertIn('id="set-z-strong"', html)
        self.assertIn('id="set-fdr-q"', html)
        self.assertIn('id="set-flag-min-sev"', html)
        self.assertIn('id="set-dim-threshold"', html)
        self.assertIn('value="2.5"', html)
        self.assertIn('value="3.5"', html)
        self.assertIn('value="0.05"', html)
        # JS posts all thresholds with the settings payload
        script = (UI_DIR / "assets" / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn("payload.z_mild = parseFloat(zm.value)", script)
        self.assertIn("payload.z_strong = parseFloat(zs.value)", script)
        self.assertIn("payload.fdr_q = parseFloat(fq.value)", script)
        self.assertIn("payload.flag_min_severity = parseInt(fs.value, 10)", script)
        self.assertIn("payload.dim_score_threshold = parseFloat(dt.value)", script)

    def test_nda_draft_has_only_the_five_authorized_fields(self):
        title = '<img src=x onerror="window.ndaInjected=true">'
        rendered = render_dashboard([], [], title=title, controls=True,
                                    nda_project_name=title,
                                    enabled_actions=("nda-draft",))
        form = re.search(r'<form[^>]*id="nda-draft-form".*?</form>', rendered, re.DOTALL)
        self.assertIsNotNone(form)
        fields = re.findall(r'<(?:input|textarea)[^>]*name="([a-z_]+)"', form.group())
        self.assertEqual(fields, ["name", "address", "project_name", "date", "place"])
        self.assertIn('type="date"', form.group())
        self.assertIn('value="&lt;img src=x onerror=&quot;window.ndaInjected=true&quot;&gt;"', form.group())
        for legacy in ("nda-manager", "nda-table", "nda-passphrase"):
            self.assertNotIn(f'id="{legacy}"', rendered)
        self.assertNotIn("data-nda-statuses=", rendered)

    def test_nda_project_name_does_not_copy_a_placeholder_title(self):
        rendered = render_dashboard([], [], title="No Project Loaded", controls=True,
                                    enabled_actions=("nda-draft",))
        field = re.search(r'<input[^>]*id="nda-project-name"[^>]*>', rendered).group()
        self.assertNotIn('value="No Project Loaded"', field)
        self.assertIn('value=""', field)

    def test_nda_draft_requires_an_explicit_live_capability(self):
        for options in ({}, {"controls": True}, {"controls": True, "enabled_actions": ("nda",)},
                        {"controls": False, "enabled_actions": ("nda-draft",)}):
            with self.subTest(options=options):
                rendered = render_dashboard([], [], **options)
                self.assertNotIn('id="nda-draft-form"', rendered)
        self.assertTrue('id="nda-draft-form"' in render_dashboard(
            [], [], controls=True, enabled_actions=("nda-draft",)), "Explicit NDA capability renders the form")


class TestLabelCompleteness(unittest.TestCase):
    """The renderer's label and help keys must exist in every language."""

    @staticmethod
    def _renderer_help_keys() -> set[str]:
        source = "\n".join(f.read_text(encoding="utf-8") for f in sorted(UI_DIR.glob("*.py")))
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
            pack = {**HELP_TEXTS.get(language, {}), **WORKSPACE_LABELS.get(language, {})}
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
            "panel_dialogue",
            "panel_characters",
            "dlg_turns",
            "dlg_avg_turn",
            "dlg_turns_per_1000",
            "chr_name",
            "chr_mentions",
            "chr_chapters",
            "chr_span",
            "chr_gap",
            "chr_share",
            "panel_pacing",
            "pac_scenes",
            "pac_avg_scene",
            "pac_hook",
            "pac_hook_mean",
            "pacing_units_note",
            "panel_motifs",
            "mot_phrase",
            "mot_count",
            "mot_chapters",
            "mot_name",
            "show_tell",
            "show_show",
            "panel_showing",
            "show_tell",
            "show_show",
            "show_balance",
            "showing_context_note",
            "showing_unavailable_note",
            "panel_flags",
            "flags_stage",
            "flags_excerpt",
            "flags_empty",
            "click_hint_para",
            "z_mild",
            "z_strong",
            "fdr_q",
            "flag_min_severity",
            "dim_score_threshold",
        )
        for language in LANGUAGES:
            labels = get_language_profile(language).labels
            missing = sorted(key for key in required if key not in labels)
            self.assertEqual(missing, [], f"{language}: missing labels {missing}")

    def test_minimal_nda_labels_are_translated(self):
        keys = ("nda_draft_title", "nda_draft_hint", "nda_draft_name", "nda_draft_address",
                "nda_draft_project", "nda_draft_date", "nda_draft_place", "nda_draft_preview",
                "nda_draft_pdf", "nda_draft_text", "nda_draft_working", "nda_draft_ready",
                "nda_draft_downloaded", "nda_draft_failed", "nda_draft_required",
                "nda_draft_javascript")
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assertFalse([key for key in keys if not WORKSPACE_LABELS[language].get(key)])


class TestShowDontTellComponents(unittest.TestCase):
    """The visual (data-ink) components are part of the render."""

    def test_pacing_explains_chapter_fallback_without_changing_legacy_exports(self):
        from lixity.pacing import pacing_report
        from lixity.ui.narration import render_pacing_panel

        config = CorpusConfig(language="de")
        note = "No explicit scene breaks: these units are chapters, not detected scenes."
        labels = {"pacing_units_note": note}
        fallback = pacing_report("## One\n\nDer Regen fiel. Die Stadt schwieg.", config).to_dict()
        self.assertTrue(fallback["scenes_are_chapters"])
        rendered = render_pacing_panel(fallback, labels, "en")
        self.assertIn(f'<p class="ctl-note">{note}</p>', rendered)
        self.assertIn('data-jump="#ch-1"', rendered)

        explicit = pacing_report("## One\n\nDer Regen fiel.\n\n---\n\nDie Stadt schwieg.", config).to_dict()
        self.assertFalse(explicit["scenes_are_chapters"])
        self.assertNotIn(note, render_pacing_panel(explicit, labels, "en"))
        legacy = {key: value for key, value in fallback.items() if key != "scenes_are_chapters"}
        self.assertNotIn(note, render_pacing_panel(legacy, labels, "en"))

    def test_showing_marks_unavailable_comparisons_and_preserves_measured_values(self):
        from lixity.showing import showing_report
        from lixity.ui.narration import render_showing_panel

        config = CorpusConfig(language="de")
        neutral = "Der Regen fiel. Die Stadt schwieg. Der Abend kam."
        labels = {
            "showing_unavailable_note": "No comparable chapter signals are available.",
            "showing_context_note": "These language signals are proxies; consider register and context.",
        }
        for text in (
            f"## One\n\n{neutral}",
            SAMPLE,
            "\n".join(f"## {number}\n\n{neutral}" for number in range(1, 4)),
        ):
            with self.subTest(text=text):
                report = showing_report(text, config).to_dict()
                rendered = render_showing_panel(report, labels, "en")
                self.assertEqual(re.findall(r'class="kpi"><b>([^<]+)</b>', rendered), ["–"] * 3)
                self.assertEqual(
                    re.findall(r'class="val">([^<]+)</span>', rendered),
                    ["–"] * len(report["chapter_list"]),
                )
                self.assertNotIn('<i style="width:', rendered)
                for note in labels.values():
                    self.assertIn(f'<p class="ctl-note">{note}</p>', rendered)

        varying = SAMPLE + "\n".join(f"## {number}\n\n{neutral}" for number in range(3, 6))
        report = showing_report(varying, config).to_dict()
        self.assertTrue(any(chapter["balance"] for chapter in report["chapter_list"]))
        rendered = render_showing_panel(report, labels, "en")
        values = re.findall(r'class="kpi"><b>([^<]+)</b>', rendered)
        self.assertEqual(len(values), 3)
        for value in values:
            self.assertRegex(value, r"^[+-]\d+\.\d{2}$")
        self.assertNotIn(labels["showing_unavailable_note"], rendered)
        self.assertIn(labels["showing_context_note"], rendered)
        self.assertIn('<i style="width:', rendered)

    def test_status_strip_renders_component_states(self):
        text = SAMPLE
        config = CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+")
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

    def test_structural_panel_contract(self):
        """Structural diagnostics panel renders changepoints, trends and shifts."""
        from lixity.api import analyze_document
        from lixity.style_fingerprint import FingerprintThresholds

        multi_sample = (
            "## Kap 1\n\nIch trinke Kaffee. Der Morgen dämmert. Ich gehe zur Tür.\n\n"
            "## Kap 2\n\nIch trinke Tee. Die Straße schweigt. Ich sehe den Regen.\n\n"
            "## Kap 3\n\nDas Haus wurde verkauft. Die Tür war verschlossen worden. Die Entscheidung fiel schwer.\n\n"
            "## Kap 4\n\nDas Haus wurde besichtigt und die Miete war bezahlt worden. Die Beschreibung der Wohnung wirkte sachlich.\n\n"
        )
        config = CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+")
        res = analyze_document(multi_sample, config, FingerprintThresholds())
        html = render_dashboard(
            res.chapters,
            res.paragraphs,
            metrics=res.metrics,
            fingerprint=res.fingerprint,
            title="Multi-Chapter Test",
        )
        self.assertIn('id="structural"', html)
        self.assertIn('class="structural-grid"', html)
        self.assertIn('class="structural-card"', html)
        self.assertIn('class="badge badge-jump"', html)
        self.assertIn('data-jump="#ch-', html)


if __name__ == "__main__":
    unittest.main()
