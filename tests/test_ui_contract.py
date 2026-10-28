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

import json
import os
import re
import sys
import unittest
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from dashboard_fixtures import SAMPLE  # noqa: E402
from dashboard_fixtures import full_dashboard as _full_dashboard  # noqa: E402

from lixity import CorpusAnalyzer, CorpusConfig  # noqa: E402
from lixity.language import get_language_profile  # noqa: E402
from lixity.language_data import HELP_TEXTS  # noqa: E402
from lixity.markdown_parser import parse_markdown_blocks  # noqa: E402
from lixity.style_profile import ParagraphProfiler  # noqa: E402
from lixity.ui import render_dashboard  # noqa: E402
from lixity.workspace_labels import WORKSPACE_LABELS  # noqa: E402

UI_DIR = Path(BASE_DIR) / "src" / "lixity" / "ui"
LANGUAGES = ("de", "en", "fr", "es", "it", "pt", "nl")

class _StructureBalance(HTMLParser):
    """Track explicitly closed structural elements across a rendered page.

    Optional-tag elements (li, p, tr, td) are skipped: HTML allows their end
    tags to be omitted, so only elements the renderer must close explicitly
    are checked. Script/style bodies are CDATA for HTMLParser.
    """

    TRACKED = frozenset(
        {
            "div",
            "section",
            "details",
            "aside",
            "figure",
            "form",
            "main",
            "nav",
            "dialog",
            "header",
            "footer",
            "article",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.TRACKED:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag not in self.TRACKED:
            return
        if tag not in self.stack:
            self.errors.append(f"unexpected </{tag}>")
            return
        while self.stack and self.stack[-1] != tag:
            self.errors.append(f"<{self.stack[-1]}> not closed before </{tag}>")
            self.stack.pop()
        self.stack.pop()


class _PaneOwnership(HTMLParser):
    """Record which workspace pane holds each key element, plus the pane order."""

    TRACKED = frozenset(
        {
            "div",
            "section",
            "details",
            "aside",
            "figure",
            "form",
            "main",
            "nav",
            "dialog",
            "header",
            "footer",
            "article",
        }
    )
    KEYS = frozenset(
        {
            "research-manager",
            "analysis-review",
            "analysis-sections",
            "settings-form",
            "controls",
            "chapters",
            "nda-draft",
            "welcome-hero",
            "workspace-reader",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.pane: str | None = None
        self.order: list[str] = []
        self.owners: dict[str, str | None] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in self.TRACKED:
            return
        attributes = dict(attrs)
        element_id = attributes.get("id", "")
        if element_id.startswith("view-pane-"):
            self.pane = element_id.removeprefix("view-pane-")
            self.order.append(self.pane)
        if element_id in self.KEYS:
            self.owners[element_id] = self.pane
        self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag not in self.TRACKED or tag not in self.stack:
            return
        while self.stack and self.stack[-1] != tag:
            self.stack.pop()
        self.stack.pop()


class TestJsDomContract(unittest.TestCase):
    def test_optional_diagram_library_stays_inert_and_preserves_raw_text_delimiters(self):
        import json
        from unittest.mock import patch

        from lixity.ui.dashboard import _bundle

        program = "window.syntheticLibrary = '</script><b id=unexpected-library-markup> & \\n';\n"
        paragraphs, chapters = ParagraphProfiler(CorpusConfig(language="en")).profile_blocks(
            parse_markdown_blocks("## Opening\n\nRain falls.\n"))

        def asset(files):
            return program if any(name.startswith("vendor/mermaid-") for name in files) else _bundle(files)

        with patch("lixity.ui.dashboard._bundle", side_effect=asset):
            document = render_dashboard(chapters, paragraphs, controls=True)
            plain_report = render_dashboard(chapters, paragraphs, controls=False)
        payload = re.search(r'<script type="application/json" id="research-diagram-library">(.*?)</script>',
                            document, re.DOTALL)
        self.assertIsNotNone(payload)
        self.assertEqual(json.loads(payload[1]), program)
        self.assertNotIn("<b id=unexpected-library-markup>", document)
        self.assertNotIn('id="research-diagram-library"', plain_report)

    """Every id the script touches must exist in the markup (no silent breakage)."""

    def test_character_panel_separates_declared_pov_in_all_locales(self):
        from lixity.language import resolve_language
        from lixity.ui.narration import render_characters_panel

        report = {"chapters": 2, "figures": [{"name": "Mara", "mentions": 0,
                  "chapters_present": [], "declared_pov_chapters": [2]}]}
        for language in ("en", "de", "fr", "es", "it", "pt", "nl"):
            with self.subTest(language=language):
                labels = resolve_language(CorpusConfig(language=language)).labels
                panel = render_characters_panel(report, [], labels)
                self.assertIn(labels["chr_pov"], panel)
                self.assertIn(labels["panel_characters"], panel)
                self.assertIn('<td>2</td>', panel)
                self.assertIn('tabindex="0" role="region"', panel)
                self.assertNotIn('data-jump=', panel)

    def test_review_routes_only_offer_existing_analysis_targets(self):
        config = CorpusConfig(language="en")
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
            parse_markdown_blocks("## Opening\n\nA bird crosses the garden. Rain falls.\n")
        )
        html = render_dashboard(chapters, paragraphs)
        review = html.split('id="analysis-review"', 1)[1].split("</section>", 1)[0]
        self.assertIn('aria-describedby="review-passage-reason"', review)
        self.assertIn('id="review-passage-reason"', review)
        self.assertIn("No tense flags at the selected threshold.", review)
        for target in re.findall(r'href="#([^"]+)"', review):
            self.assertTrue(f'id="{target}"' in html, f"Review route has no target: {target}")

    def test_shared_control_components_are_used(self):
        """Retired one-off control classes must not slip back into markup."""
        html = _full_dashboard() + render_dashboard([], [], controls=True)
        for retired in ('class="research-check', "ctl-primary", 'class="ctl secondary"'):
            self.assertFalse(retired in html, f"retired control class: {retired}")
        self.assertIn('class="form-checkbox"', html)

    def test_review_passage_follows_source_order_among_flagged_candidates(self):
        paragraphs, chapters = ParagraphProfiler(CorpusConfig(language="en")).profile_blocks(
            parse_markdown_blocks("## Opening\n\nA bird crosses the garden.\n\nRain falls.\n")
        )
        paragraphs[0].severity = 2
        paragraphs[1].severity = 3
        chapters[0].flagged = 2
        html = render_dashboard(chapters, paragraphs)
        review = html.split('id="analysis-review"', 1)[1].split("</section>", 1)[0]
        self.assertIn('data-target="p-0"', review)
        self.assertIn(WORKSPACE_LABELS["en"]["review_passage_flagged"], review)

    def test_analysis_section_nav_only_links_existing_panels(self):
        """Section links retain real panel anchors without becoming tabs."""
        html = _full_dashboard()
        self.assertIn('id="analysis-sections"', html)
        nav = html.split('id="analysis-sections"', 1)[1].split("</nav>", 1)[0]
        targets = re.findall(r'data-section-link="([^"]+)"', nav)
        self.assertGreaterEqual(len(targets), 4)
        self.assertEqual(len(targets), len(set(targets)), "section links must be unique")
        for target in targets:
            self.assertIn(f'id="{target}"', html, f"Section nav has no target: {target}")
            self.assertRegex(nav, rf'<a href="\#{target}" data-jump="\#{target}" '
                             rf'data-section-link="{target}">[^<]+</a>')
        self.assertNotIn('role="tab', nav)
        self.assertIn('data-section-nav="analysis"', nav)

    def test_analysis_navigation_precedes_review_and_search(self):
        """Overview orientation follows the reader controls, before task details."""
        html = _full_dashboard()
        self.assertLess(html.index('id="manuscript-reader-controls"'), html.index('id="analysis-sections"'))
        self.assertLess(html.index('id="analysis-sections"'), html.index('id="analysis-review"'))
        self.assertLess(html.index('id="analysis-sections"'), html.index('id="text-search"'))


    def test_analysis_section_nav_follows_the_registry(self):
        """The nav order and labels come from the central registry."""
        from lixity.ui.components import ANALYSIS_SECTIONS

        html = _full_dashboard()
        nav = html.split('id="analysis-sections"', 1)[1].split("</nav>", 1)[0]
        targets = re.findall(r'data-section-link="([^"]+)"', nav)
        expected = [panel for panel, _key in ANALYSIS_SECTIONS if panel in set(targets)]
        self.assertEqual(targets, expected)

    def test_checkbox_controls_use_the_shared_component(self):
        """Every rendered checkbox row uses the one form-checkbox component."""
        html = _full_dashboard()
        for control_id in (
            "filter-flags",
            "heatmap-fdr-only",
            "set-publication-enabled",
            "r-ingest-retention",
            "r-zotero-retention",
            "r-relation-retracted",
            "r-decision-deviation",
            "import-proj-research",
            "new-proj-research",
        ):
            pattern = re.compile(
                r'<label class="form-checkbox"[^>]*>(?:(?!</label>).)*?id="'
                + re.escape(control_id)
                + r'"',
                re.DOTALL,
            )
            self.assertRegex(html, pattern, f"#{control_id} must use the form-checkbox component")

    def test_review_tab_hosts_manuscript_link_section(self):
        """The Review tab owns the manuscript-link review surface."""
        html = _full_dashboard()
        self.assertIn('<section id="research-manuscript-review-section" hidden>', html)
        self.assertIn('id="research-manuscript-review"', html)
        self.assertIn('id="research-editorial-review"', html)

    def test_view_panes_own_their_sections(self):
        """Each workspace view owns exactly its sections.

        String slicing is not enough here: section ids and CSS classes appear
        in the embedded stylesheet and script, so a slice can match them by
        accident. The parser tracks the nearest ancestor pane instead, which
        is what the browser actually uses for show/hide.
        """
        parser = _PaneOwnership()
        parser.feed(_full_dashboard())
        self.assertEqual(parser.order, ["research", "project", "analysis"])
        expected = {
            "research-manager": "research",
            "analysis-review": "analysis",
            "analysis-sections": "analysis",
            "chapters": "analysis",
            "settings-form": "project",
            "controls": "project",
        }
        # The confidentiality agreement needs the native capability; the default
        # variant must not render it at all.
        self.assertNotIn("nda-draft", parser.owners)
        for key, pane in expected.items():
            self.assertEqual(
                parser.owners.get(key),
                pane,
                f"#{key} must live in the {pane} pane, found {parser.owners.get(key)!r}",
            )

    def test_rendered_documents_have_balanced_structure(self):
        """All rendered variants close the structural tags they open."""
        from lixity.language import LANGUAGE_PROFILES
        from lixity.ui import render_dashboard

        labels = LANGUAGE_PROFILES["en"].labels
        variants = {
            "full": _full_dashboard(),
            "limited": _full_dashboard(("manuscript-pdf", "research-reader")),
            "empty": render_dashboard([], [], controls=True, labels=labels, language_key="en"),
        }
        for name, html in variants.items():
            parser = _StructureBalance()
            parser.feed(html)
            self.assertEqual(
                [], parser.errors, f"{name} document has unbalanced structure: {parser.errors[:4]}"
            )
            self.assertEqual(
                [], parser.stack, f"{name} document leaves tags open: {parser.stack[-6:]}"
            )

    def test_native_refresh_and_filter_reset(self):
        """Native controls expose one refresh and an explicit filter escape."""
        from lixity.server import build_server_dashboard

        html, _ = build_server_dashboard(None)
        self.assertEqual(html.count('data-action="analyze"'), 1)
        self.assertNotIn('data-action="rebuild"', html)
        self.assertIn('id="paragraph-filter-reset"', _full_dashboard())
        embedding = render_dashboard([], [], controls=True, enabled_actions=("analyze", "rebuild"))
        self.assertIn('data-action="analyze"', embedding)
        self.assertIn('data-action="rebuild"', embedding)

    def test_optional_research_metadata_disclosures(self):
        """Optional metadata does not compete with authored content fields."""
        html = _full_dashboard()
        for identifier in (
            "r-ingest-options",
            "r-dos-options",
            "r-claim-options",
            "r-decision-options",
            "import-project-options",
        ):
            self.assertRegex(html, rf'<details[^>]*id="{identifier}"')

    def test_minimal_workflow_labels_cover_every_locale(self):
        """New native controls have translated labels in every label pack."""
        from lixity.workspace_labels import WORKSPACE_LABELS

        for language, labels in WORKSPACE_LABELS.items():
            for key in (
                "optional_details",
                "marker_save",
                "marker_saving",
                "marker_saved",
                "marker_save_failed",
                "paragraph_filter_reset",
                "scene_containing_chapter",
                "settings_bound_error",
                "wizard_research_required",
                "manuscript_link_review_help",
                "manuscript_link_review_count",
                "manuscript_link_review_empty",
            ):
                with self.subTest(language=language, key=key):
                    self.assertTrue(labels.get(key), f"Missing {language} label: {key}")
                    self.assertNotEqual(labels[key], key)

    def test_scene_links_use_containing_chapters(self):
        """Scene reports know their containing chapter, not source offsets."""
        from lixity.scenes import scene_report
        from lixity.ui.narration import render_scenes_panel

        report = scene_report(
            "## Synthetic chapter\n\nA door shuts.\n\n---\n\nA window opens.",
            CorpusConfig(language="en"),
        )
        html = render_scenes_panel(report, None, "en")
        self.assertIn('href="#ch-1"', html)
        self.assertNotIn("data-line=", html)

    def test_script_ids_are_rendered(self):
        script = "\n".join(
            asset.read_text(encoding="utf-8") for asset in sorted((UI_DIR / "assets").glob("*.js"))
        )
        ids = set(re.findall(r'getElementById\("([^"]+)"\)', script))
        ids.discard("lixity-tooltip")  # created by the script itself
        ids.discard("research-evidence-draft")  # created beside the existing evidence form
        ids.discard("r-dos-geography")  # mounted by the shared optional geography editor
        ids.discard("workbench-thread")  # mounted once by the shared reading-thread owner
        ids.discard("lixity-site-data")  # injected only by the prepared website exporter
        ids.discard("speech-chapter")  # created dynamically by the speech dialog
        self.assertTrue(ids)
        # Onboarding controls exist only in the empty/research-only state.
        html = (
            _full_dashboard()
            + _full_dashboard(("manuscript-pdf", "research-reader"))
            + _full_dashboard(("analysis-review",))
            + render_dashboard([], [], controls=True)
            + render_dashboard([], [], controls=True, enabled_actions=("analyze", "rebuild"))
            + render_dashboard([], [], controls=True, enabled_actions=("nda-draft",))
            + render_dashboard([], [], controls=True, enabled_actions=("site-export",))
            + render_dashboard([], [], controls=True, project_overview_enabled=True)
        )
        # Declared chapter groups add conditional comparison controls.
        from lixity.api import dashboard

        scope_text = "\n\n".join(
            f"## Chapter {number}\n\n" + (("moss " * length).strip() + ". ") * 30
            for number, length in enumerate((5, 8, 12), 1)
        )
        html += dashboard(scope_text, project_config={
            "register_profiles": {"Letters": {}}, "chapter_registers": {"2": "Letters"},
            "characters": {"Alex": {"pov_in_chapters": [1, 3]}},
        })
        from lixity.ui.publication import render_publication

        html += render_publication({"mode":"companion", "title":"Synthetic context", "max_chapter":0})
        missing = sorted(dom_id for dom_id in ids if f'id="{dom_id}"' not in html)
        self.assertEqual(missing, [], f"dashboard.js looks up missing ids: {missing}")

    def test_readability_caption_uses_measured_variant_not_interface_language(self):
        text = "## Synthetic\n\nEin Vogel wartet am Fluss. Der Regen fällt leise.\n"
        config = CorpusConfig(language="de")
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text))
        metrics = CorpusAnalyzer(config).analyze_text(text)
        self.assertEqual(metrics.flesch_variant, "Flesch Reading Ease (Amstad)")
        rendered = render_dashboard(chapters, paragraphs, metrics=metrics,
                                    labels=get_language_profile("en").labels, language_key="en")
        self.assertTrue('>Flesch Reading Ease (Amstad)</span>' in rendered,
                        "The visible caption must use the measured formula identity")

    def test_marker_actions_are_distinct_from_stored_marker_categories(self):
        paragraphs, chapters = ParagraphProfiler(CorpusConfig(language="en")).profile_blocks(
            parse_markdown_blocks("## Synthetic\n\nA bird waits beside the river.\n")
        )
        for locale in ("en", "de", "fr", "es", "it", "pt", "nl"):
            labels = get_language_profile(locale).labels
            rendered = render_dashboard(chapters, paragraphs, controls=True, labels=labels, language_key=locale)
            for kind in ("pruefen", "sachcheck", "todo", "achtung"):
                with self.subTest(locale=locale, kind=kind):
                    button = re.search(r'data-marker-kind="' + kind + r'"[^>]*>([^<]+)</button>', rendered)
                    self.assertIsNotNone(button)
                    self.assertEqual(unescape(button.group(1)), labels["marker_action_" + kind])
                    self.assertNotEqual(labels["marker_action_" + kind], labels["marker_" + kind])

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
        # jumpToLine opens the target paragraph (data-target / line span) and
        # expands it synchronously, so the scroll measures the final layout
        self.assertIn('getAttribute("data-target")', script)
        self.assertIn(".ptext[data-start]", script)
        self.assertIn("toggleParagraph(chip, true, true)", script)

    def test_unified_interaction_contract(self):
        """All content drill-downs are keyboard reachable with one vocabulary."""
        script = (UI_DIR / "assets" / "dashboard.js").read_text(encoding="utf-8")
        css = "\n".join(
            (UI_DIR / "assets" / name).read_text(encoding="utf-8")
            for name in ("design-tokens.css", "components.css", "dashboard.css")
        )
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
        rendered = render_dashboard(
            [],
            [],
            title=title,
            controls=True,
            nda_project_name=title,
            enabled_actions=("nda-draft",),
        )
        form = re.search(r'<form[^>]*id="nda-draft-form".*?</form>', rendered, re.DOTALL)
        self.assertIsNotNone(form)
        fields = re.findall(r'<(?:input|textarea)[^>]*name="([a-z_]+)"', form.group())
        self.assertEqual(fields, ["name", "address", "project_name", "date", "place"])
        self.assertIn('type="date"', form.group())
        self.assertIn(
            'value="&lt;img src=x onerror=&quot;window.ndaInjected=true&quot;&gt;"', form.group()
        )
        for legacy in ("nda-manager", "nda-table", "nda-passphrase"):
            self.assertNotIn(f'id="{legacy}"', rendered)
        self.assertNotIn("data-nda-statuses=", rendered)

    def test_nda_project_name_does_not_copy_a_placeholder_title(self):
        rendered = render_dashboard(
            [], [], title="No Project Loaded", controls=True, enabled_actions=("nda-draft",)
        )
        field = re.search(r'<input[^>]*id="nda-project-name"[^>]*>', rendered).group()
        self.assertNotIn('value="No Project Loaded"', field)
        self.assertIn('value=""', field)

    def test_nda_draft_requires_an_explicit_live_capability(self):
        for options in (
            {},
            {"controls": True},
            {"controls": True, "enabled_actions": ("nda",)},
            {"controls": False, "enabled_actions": ("nda-draft",)},
        ):
            with self.subTest(options=options):
                rendered = render_dashboard([], [], **options)
                self.assertNotIn('id="nda-draft-form"', rendered)
        self.assertTrue(
            'id="nda-draft-form"'
            in render_dashboard([], [], controls=True, enabled_actions=("nda-draft",)),
            "Explicit NDA capability renders the form",
        )


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
            "long_words",
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
        keys = (
            "nda_draft_title",
            "nda_draft_hint",
            "nda_draft_name",
            "nda_draft_address",
            "nda_draft_project",
            "nda_draft_date",
            "nda_draft_place",
            "nda_draft_preview",
            "nda_draft_pdf",
            "nda_draft_text",
            "nda_draft_working",
            "nda_draft_ready",
            "nda_draft_downloaded",
            "nda_draft_failed",
            "nda_draft_required",
            "nda_draft_javascript",
        )
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assertFalse([key for key in keys if not WORKSPACE_LABELS[language].get(key)])


class TestShowDontTellComponents(unittest.TestCase):
    """The visual (data-ink) components are part of the render."""

    def test_metric_context_preserves_canonical_values_missingness_and_units(self):
        from lixity.format import num
        from lixity.style_fingerprint import (
            FEATURE_UNITS,
            FEATURES,
            LAYER_FEATURES,
            StyleFingerprint,
        )
        from lixity.ui.heatmap import render_metric_context

        config = CorpusConfig(language="en")
        text = '## <img src=x onerror="alert(1)">\n\n' + "The garden waits. " * 90
        text += "\n\n## Brief\n\nRain."
        metrics = CorpusAnalyzer(config).analyze_text(text)
        fingerprint = StyleFingerprint.from_metrics(metrics)
        for locale in LANGUAGES:
            with self.subTest(locale=locale):
                rendered = render_metric_context(
                    fingerprint, metrics.chapters, WORKSPACE_LABELS[locale], locale
                )
                match = re.search(r'data-metric-context="([^"]*)"', rendered)
                self.assertIsNotNone(match)
                payload = json.loads(unescape(match[1]))
                self.assertEqual(set(payload["features"]), {field for field, _, _ in FEATURES})
                self.assertEqual(len(payload["chapters"]), 2)
                self.assertNotIn('<img src=x', rendered)
                self.assertEqual(payload["chapters"]["1"]["title"], f"1. {metrics.chapters[0].title}")
                for field, _label_key, _unit in FEATURES:
                    meta = payload["features"][field]
                    self.assertEqual(meta["unit"], FEATURE_UNITS[locale][field])
                    self.assertEqual(meta["median"], "–", "An insufficient reference is not a zero median")
                    self.assertEqual(meta["layer"], next((layer for layer, name in LAYER_FEATURES.items()
                                                         if name == field), ""))
                    self.assertTrue(meta["help"])
                    for chapter in metrics.chapters:
                        raw = fingerprint.values[field][chapter.num]
                        self.assertEqual(payload["chapters"][str(chapter.num)]["values"][field]["value"],
                                         num(raw, locale, 2) if raw is not None else "–")
                self.assertEqual(payload["chapters"]["1"]["values"]["dialog_pct"]["value"], num(0, locale, 2))
                self.assertEqual(payload["chapters"]["2"]["values"]["hd_d"]["value"], "–")

        complete = "\n\n".join(f"## Chapter {index}\n\n" + "The garden waits. " * 90
                               for index in range(1, 4))
        metrics = CorpusAnalyzer(config).analyze_text(complete)
        fingerprint = StyleFingerprint.from_metrics(metrics)
        rendered = render_metric_context(fingerprint, metrics.chapters, language_key="en")
        payload = json.loads(unescape(re.search(r'data-metric-context="([^"]*)"', rendered)[1]))
        for field, _key, _unit in FEATURES:
            base = fingerprint.baseline[field]
            self.assertEqual(payload["features"][field]["median"], num(base["median"], "en", 2))
            self.assertEqual(payload["features"][field]["n"], base["n"])
            score = fingerprint.z_scores[1].get(field)
            self.assertEqual(payload["chapters"]["1"]["values"][field]["z"],
                             num(score, "en", 2, signed=True) if score is not None else "–")
            if base["comparison_status"] in ("zero_mad_varying", "zero_mad_constant"):
                self.assertTrue(payload["chapters"]["1"]["values"][field]["reason"])

    def test_metric_context_is_rendered_once_and_empty_workspace_remains_valid(self):
        rendered = _full_dashboard()
        self.assertEqual(rendered.count('id="analysis-metric-context"'), 1)
        self.assertIn('data-metric-feature="hd_d"', rendered)
        self.assertNotIn('id="analysis-metric-context"', render_dashboard([], []))

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

        explicit = pacing_report(
            "## One\n\nDer Regen fiel.\n\n---\n\nDie Stadt schwieg.", config
        ).to_dict()
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
                self.assertNotIn('class="kpi-row"', rendered)
                self.assertNotIn('class="dist scrollable"', rendered)
                self.assertNotIn('<i style="width:', rendered)
                for note in labels.values():
                    self.assertIn(f'<p class="ctl-note">{note}</p>', rendered)

        long_neutral = (neutral + " ") * 14
        varying = SAMPLE + "\n".join(f"## {number}\n\n{long_neutral}" for number in range(3, 6))
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
        self.assertNotIn('<p class="microhint"', html)  # Continuous prose needs no click-to-read hint
        self.assertNotIn('<p class="sub">Stil- &amp; Tempusanalyse', html)

    def test_passport_numbers_live_in_tooltips(self):
        html = _full_dashboard()
        # the numeric band/median/outlier text is available on demand, not printed
        self.assertRegex(html, r'class="band" title="[^"]*(Median|median)[^"]*"')
        self.assertNotIn('class="num">…', html)

    def test_structural_panel_contract(self):
        """Structural diagnostics panel renders changepoints, trends and shifts."""
        from lixity.api import analyze_document
        from lixity.style_fingerprint import FingerprintThresholds

        filler_a = "Ich trinke Kaffee und höre die Stadt im Regen. " * 12
        filler_b = "Ich trinke Tee und sehe die Straße im Licht. " * 12
        filler_c = "Das Haus wurde verkauft und die Tür war verschlossen worden. " * 9
        filler_d = "Die Entscheidung fiel schwer und die Miete war bezahlt worden. " * 9
        multi_sample = (
            f"## Kap 1\n\nIch trinke Kaffee. Der Morgen dämmert. Ich gehe zur Tür. {filler_a}\n\n"
            f"## Kap 2\n\nIch trinke Tee. Die Straße schweigt. Ich sehe den Regen. {filler_b}\n\n"
            f"## Kap 3\n\nDas Haus wurde verkauft. Die Tür war verschlossen worden. "
            f"Die Entscheidung fiel schwer. {filler_c}\n\n"
            f"## Kap 4\n\nDas Haus wurde besichtigt und die Miete war bezahlt worden. "
            f"Die Beschreibung der Wohnung wirkte sachlich. {filler_d}\n\n"
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
