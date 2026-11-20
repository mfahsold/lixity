"""Narration overviews preserve coverage and provide reversible measurement access."""

from xml.etree import ElementTree

import pytest

from lixity.analyzer import CorpusAnalyzer
from lixity.dialogue import dialogue_report
from lixity.format import pct
from lixity.language import get_language_profile
from lixity.models import CorpusConfig, CorpusMetrics
from lixity.pacing import pacing_report
from lixity.scenes import scene_report
from lixity.showing import showing_report
from lixity.style_fingerprint import FEATURE_UNITS
from lixity.ui.narration import (
    render_dialogue_panel,
    render_pacing_panel,
    render_scenes_panel,
    render_sentence_dist_panel,
    render_showing_panel,
)
from tests.locales import LOCALES


def synthetic_scenes():
    text = "\n\n".join(
        f"## Synthetic chapter {chapter}\n\n"
        + "\n\n---\n\n".join("A quiet garden waits. " * 30 for _ in range(2 if chapter <= 5 else 1))
        for chapter in range(1, 15)
    )
    return scene_report(text, CorpusConfig(language="en"), {
        "assignments": {"1:1": "voice", "1:2": "voice", "15:1": "voice"},
        "groups": {"voice": {"targets": {"asl": [2, 8]}}}, "planned": ["15:1"],
    })


@pytest.mark.parametrize("locale", LOCALES)
def test_scene_overview_links_reach_all_measurements_inside_one_closed_disclosure(locale):
    labels = get_language_profile(locale).labels
    panel = ElementTree.fromstring(render_scenes_panel(synthetic_scenes(), labels, locale))  # noqa: S314
    measurements = panel.find("./details[@class='panel-disclosure scene-measurements']")
    assert measurements is not None, "One disclosure keeps the repeated measurement catalogue out of the overview"
    assert "open" not in measurements.attrib
    assert measurements.findtext("summary") == labels["scene_measurements"] + " (19)"
    overview = panel.find("./div[@class='table-wrap scene-overview']/table/tbody")
    details = measurements.findall("./details[@class='scene-detail']")
    assert len(overview) == len(details) == 19
    for row, detail in zip(overview, details, strict=True):
        identifier = detail.attrib["data-scene"].replace(":", "-")
        link = row.find("th/a")
        target = f"scene-metrics-{identifier}"
        assert link.attrib["href"] == link.attrib["data-jump"] == "#" + target
        assert detail.find(f"./div[@id='{target}']/table") is not None
        assert "open" not in detail.attrib and "name" not in detail.attrib
        assert len(detail.findall(".//tbody/tr")) == 16
    # Plans stay outside the measured catalogue and never acquire fabricated values.
    planned = panel.find("./details[@class='scene-planned']")
    assert planned is not None and planned.find(".//table") is None
    assert "15:1" in "".join(planned.itertext())


def test_scene_panel_explains_chapter_fallback_when_no_separators_are_present():
    config = CorpusConfig()
    labels = get_language_profile("en").labels
    text = "## Chapter\n\nThe door opens.\n\nThe wind rises."
    with_chapters = scene_report(text, config)
    with_scenes = scene_report(text.replace("\n\nThe wind", "\n\n---\n\nThe wind"), config)
    assert labels["pacing_units_note"] in render_scenes_panel(with_chapters, labels)
    assert labels["pacing_units_note"] not in render_scenes_panel(with_scenes, labels)


@pytest.mark.parametrize("count", (16, 17))
def test_dialogue_keeps_every_chapter_in_manuscript_order_including_zero_turns(count):
    text = "\n\n".join(
        f"## Synthetic chapter {number}\n\n"
        + ('"Come here." ' * number if number < count else "The garden was silent.")
        for number in range(1, count + 1)
    )
    report = dialogue_report(text, CorpusConfig(language="en")).to_dict()
    panel = ElementTree.fromstring(render_dialogue_panel(report))  # noqa: S314
    chart = panel.find("./div[@class='dist scrollable']")
    assert chart is not None, "Complete chapter coverage uses the existing bounded chart"
    assert "Counted text" not in "".join(panel.itertext())
    assert [row.attrib["data-jump"] for row in chart] == [f"#ch-{number}" for number in range(1, count + 1)]
    for row in chart:
        assert row.attrib["data-layer"] == "dialogue"
        link = row.find("a")
        assert link.attrib["href"] == row.attrib["data-jump"]
        assert link.attrib["data-layer"] == "dialogue"
    assert chart[0].findtext("./span[@class='val']").endswith(" · 1 Recognized span")
    assert chart[-1].findtext("./span[@class='val']") == "0.0% · 0 Recognized spans"
    details = panel.find("./details[@class='panel-disclosure dialogue-measurements']")
    assert details is not None and "open" not in details.attrib
    assert len(details.findall(".//tbody/tr")) == count


@pytest.mark.parametrize("locale", LOCALES)
def test_dialogue_summary_names_and_counts_the_words_in_marked_speech(locale):
    labels = get_language_profile(locale).labels
    report = dialogue_report("—Ven aquí.\nLa puerta se cerró.", CorpusConfig(language="es")).to_dict()
    panel = ElementTree.fromstring(render_dialogue_panel(report, labels, locale))  # noqa: S314
    summary = panel.findall("./div[@class='kpi-row']/div")
    assert summary[1].findtext("b") == "2"
    assert summary[1].findtext("span") == labels["measurement_quoted_words"] == labels["dialogue"]
    assert summary[2].findtext("span/span") == labels["analysis_dialogue_share"]


@pytest.mark.parametrize("locale", LOCALES)
def test_pacing_names_the_bar_measurement_and_explains_the_existing_hook_heuristic(locale):
    labels = get_language_profile(locale).labels
    report = pacing_report('## Synthetic chapter\n\nThe garden was still.\n\n"Why?"', CorpusConfig(language="en")).to_dict()
    assert report["chapter_list"][0]["hook_score"] == 3
    panel = ElementTree.fromstring(render_pacing_panel(report, labels, locale))  # noqa: S314
    help_texts = [span.attrib["data-help"] for span in panel.findall(".//span[@class='help']")]
    assert labels.get("help_pacing_hook") and labels["help_pacing_hook"].replace("{max_words}", "8") in help_texts
    assert labels.get("help_pacing_cohesion") in help_texts
    assert labels["help_pacing_monotony"].replace("{min_run}", "3") in help_texts
    details = panel.find("./details[@class='panel-disclosure pacing-measurements']")
    assert details is not None and "open" not in details.attrib
    assert len(details.findall(".//tbody/tr")) == 1
    guide = panel.find("./p[@class='panel-guide']")
    assert guide is not None
    assert labels["pacing_scale"] in "".join(guide.itertext())
    value = panel.find("./div[@class='dist scrollable']/div/span[@class='val']")
    assert FEATURE_UNITS[locale]["asl"] in "".join(value.itertext())
    assert panel.find("./div[@class='kpi-row']") is None
    assert details.find("./div[@class='kpi-row']") is not None
    assert details.find(".//tbody/tr").findall("td")[2].text == "3"
    sparkline = details.find(".//span[@class='sparkline']")
    assert sparkline is not None and sparkline.text


def test_narration_explains_the_configured_quotation_and_closing_lengths():
    from lixity.pipeline import analyze_document, supplementary_reports
    from lixity.style_fingerprint import FingerprintThresholds

    text = '## Chapter\n\n"Stay here." She watched the room. She felt cold. She waited. "I will return when the rain stops."'
    config = CorpusConfig(short_turn_max_words=3, long_turn_min_words=7, hook_short_sentence=5, monotony_min_run=4)
    analysis = analyze_document(text, config, FingerprintThresholds())
    reports = supplementary_reports(text, config, analysis)
    assert reports["dialogue"]["short_turns"] == reports["dialogue"]["long_turns"] == 1
    assert reports["pacing"]["chapter_list"][0]["hook_score"] == 1
    assert reports["pacing"]["repeated_start_runs"] == 0
    labels = get_language_profile("en").labels
    dialogue = render_dialogue_panel(reports["dialogue"], labels, "en")
    pacing = render_pacing_panel(reports["pacing"], labels, "en")
    assert "Short spans (≤ 3 words)" in dialogue
    assert "Long spans (≥ 7 words)" in dialogue
    assert "1–3 words" in dialogue
    assert "1–5 words" in pacing
    assert "4 or more consecutive sentences" in pacing
    assert "≥ 3" not in pacing
    assert "≤ 12 words" not in dialogue
    assert "1–8 words" not in pacing


def test_pacing_sticky_examples_explain_measured_counts_without_guessing_a_rule():
    sentence = "In the garden she said that it was in the way and that it would be there."
    config = CorpusConfig(language="en", sticky_min_words=9, sticky_glue_pct=55.125)
    report = pacing_report("## Synthetic chapter\n\n" + (sentence + " ") * 24, config).to_dict()
    assert "sticky_rule" not in report
    report["sticky_rule"] = {"min_words": config.sticky_min_words, "min_pct": config.sticky_glue_pct}
    panel = ElementTree.fromstring(render_pacing_panel(report, language_key="en"))  # noqa: S314
    detail = panel.find("./details[@class='panel-disclosure pacing-sticky-items']")
    assert detail is not None and "open" not in detail.attrib
    assert "at least 9 words and at least 55.125% function words" in "".join(detail.itertext())
    assert "Showing 20 of 24 matching sentences." in "".join(detail.itertext())
    assert len(detail.findall("./ul/li")) == 20
    first = detail.find("./ul/li")
    assert first.findtext("p") == sentence
    assert "13 of 17 words are function words (76.47%)" in "".join(first.itertext())
    assert first.find("./p/a").attrib["href"] == "#ch-1"

    del report["sticky_rule"]
    legacy = render_pacing_panel(report, language_key="en")
    assert "The thresholds are unavailable in this report." in legacy
    assert "13 of 17 words are function words (76.47%)" in legacy


def test_sentence_distribution_names_the_effective_word_ranges():
    config = CorpusConfig(language="en", short_sentence_max=3, medium_sentence_max=5, long_sentence_max=7)
    metrics = CorpusAnalyzer(config).analyze_text("This is short. These sentences now differ. How many words are there now? This sentence has more words than the others.")
    panel = ElementTree.fromstring(render_sentence_dist_panel(metrics))  # noqa: S314
    assert [node.text for node in panel.findall(".//div[@class='row']/span[@class='label']")] == [
        "Short (≤ 3 words)", "Medium (4–5 words)", "Long (6–7 words)", "Very long (> 7 words)",
    ]
    assert [node.text for node in panel.findall(".//div[@class='row']/span[@class='val']")] == ["1 · 25.0%"] * 4
    assert "_word_bounds" not in metrics.sentence_dist.model_dump()
    restored = CorpusMetrics.model_validate(metrics.model_dump())
    legacy = ElementTree.fromstring(render_sentence_dist_panel(restored))  # noqa: S314
    assert "The word limits for these groups are unavailable in this report." in "".join(legacy.itertext())
    assert [node.text for node in legacy.findall(".//div[@class='row']/span[@class='label']")] == [
        "Short", "Medium", "Long", "Very long",
    ]
    assert [node.text for node in legacy.findall(".//div[@class='row']/span[@class='val']")] == ["1 · 25.0%"] * 4


@pytest.mark.parametrize("locale", LOCALES)
def test_showing_panel_renders_immersion_pills_in_all_locales(locale):
    labels = get_language_profile(locale).labels
    text = (
        "## Chapter 1\n\n"
        + "He felt the bitter cold smoke and heard the whisper in the dark night. " * 20
        + "\n\n## Chapter 2\n\n"
        + '"Stop!" she shouted in fear. ' * 20
        + "\n\n## Chapter 3\n\n"
        + "He sensed the sweet fragrance and saw the flash. " * 20
    )
    report = showing_report(text, CorpusConfig(language="en")).to_dict()
    panel = ElementTree.fromstring(render_showing_panel(report, labels, locale))  # noqa: S314
    pills = panel.findall(".//span[@class='immersion-pill']")
    assert len(pills) == 2
    assert any(labels["show_sensory"] in "".join(p.itertext()) for p in pills)
    assert any(labels["show_immersion"] in "".join(p.itertext()) for p in pills)


def test_word_patterns_keep_supported_examples_when_comparison_is_unavailable():
    labels = get_language_profile("de").labels
    report = {"chapter_list": [{"chapter_num": 1, "title": "Ankunft", "comparable": False}]}
    panel = ElementTree.fromstring(render_showing_panel(  # noqa: S314
        report, labels, "de", available_layers=frozenset({"asl", "dialogue", "echo"}),
    ))
    assert labels["layer_language_unavailable"] in "".join(panel.itertext())
    assert [button.attrib["data-layer"] for button in panel.findall(".//button[@data-pattern-jump]")] == ["dialogue"]


@pytest.mark.parametrize("locale", LOCALES)
def test_dialogue_panel_surfaces_voice_separation_and_adverbial_tags(locale):
    labels = get_language_profile(locale).labels
    report = {
        "turns": 4,
        "dialogue_pct": 35.0,
        "avg_turn_words": 8.5,
        "turns_per_1000": 40.0,
        "dialogue_tag_available": True,
        "dialogue_tags": 3,
        "dialogue_tag_pct": 75.0,
        "dialogue_tags_per_1000": 30.0,
        "adverbial_tag_available": True,
        "adverbial_tags": 2,
        "adverbial_tag_pct": 66.7,
        "voice_separation": {
            "available": True,
            "dialogue_words": 40,
            "narrative_words": 80,
            "dialogue_asl": 6.5,
            "narrative_asl": 14.2,
            "asl_delta": -7.7,
            "cosine_similarity": 0.42,
            "separation_label": "distinct",
        },
        "chapters": [],
    }
    html = render_dialogue_panel(report, labels, locale)
    panel = ElementTree.fromstring(html)  # noqa: S314
    headline = panel.find("./div[@class='kpi-row']")
    assert headline is not None
    assert [node.findtext("b") for node in headline] == ["4", pct(35, locale)]
    assert labels["analysis_dialogue_share"] in "".join(headline.itertext())
    extra = panel.find("./details[@id='dialogue-corpus-details']")
    assert extra is not None and "open" not in extra.attrib
    assert extra.findtext("summary") == labels["analysis_dialogue_corpus_details"]
    text = "".join(extra.itertext())
    assert labels["dlg_adverbial_tags"] in text
    assert labels["dlg_voice_separation"] in text
    assert labels["dlg_voice_sep_distinct"] in text
    assert "6" in text and "14" in text


@pytest.mark.parametrize("locale", LOCALES)
def test_scenes_panel_surfaces_dynamics_showing_rates_and_plateaus(locale):
    from lixity.ui.narration import FEATURES

    labels = get_language_profile(locale).labels
    features = {field: 0.0 for field, _, _ in FEATURES}
    features.update({"asl": 12.5, "dialog_pct": 20.0})
    scenes = {
        "items": [
            {
                "id": "1:1",
                "chapter": 1,
                "scene": 1,
                "chapter_title": "Chapter 1",
                "group": "",
                "words": 150,
                "sentences": 12,
                "features": features,
                "standard_errors": {},
                "targets": {},
                "scene_dynamic": "accelerating",
                "filter_per_1000": 6.67,
                "sensory_per_1000": 13.33,
            }
        ],
        "baselines": {},
        "pacing_plateaus": [
            {
                "start_id": "1:1",
                "end_id": "1:3",
                "scene_count": 3,
                "mean_asl": 12.5,
                "reason": "low_exit_hooks",
            }
        ],
    }
    html = render_scenes_panel(scenes, labels, locale)
    panel = ElementTree.fromstring(html)  # noqa: S314
    text = "".join(panel.itertext())
    assert labels["scene_dynamic"] in text
    assert labels["scene_dynamic_accelerating"] in text
    assert labels["scene_filter_per_1000"] in text
    assert labels["scene_sensory_per_1000"] in text
    assert labels["scene_pacing_plateaus"] in text
    assert labels["scene_plateau_low_exit_hooks"] in text


@pytest.mark.parametrize("locale", LOCALES)
def test_scenes_panel_surfaces_implicit_breaks(locale):
    from lixity.ui.narration import FEATURES

    labels = get_language_profile(locale).labels
    features = {field: 0.0 for field, _, _ in FEATURES}
    scenes = {
        "items": [
            {
                "id": "1:1",
                "chapter": 1,
                "scene": 1,
                "chapter_title": "Chapter 1",
                "group": "",
                "words": 150,
                "sentences": 12,
                "features": features,
                "standard_errors": {},
                "targets": {},
            }
        ],
        "baselines": {},
        "implicit_breaks": [
            {
                "chapter": 1,
                "scene": 1,
                "paragraph_index": 4,
                "cue_type": "time+place+cohesion_drop",
                "cohesion_similarity": 0.03,
                "snippet": "Am nächsten Morgen am Bahnhof...",
            }
        ],
    }
    html = render_scenes_panel(scenes, labels, locale)
    panel = ElementTree.fromstring(html)  # noqa: S314
    text = "".join(panel.itertext())
    assert labels["scene_implicit_breaks"] in text
    assert labels["scene_implicit_breaks_hint"] in text
    assert labels["scene_cue_time"] in text
    assert labels["scene_cue_place"] in text
    assert labels["scene_cue_cohesion_drop"] in text
    assert labels["scene_cohesion_similarity"] in text
    assert "Am nächsten Morgen am Bahnhof..." in text


@pytest.mark.parametrize("locale", LOCALES)
def test_pacing_panel_surfaces_rhythm_profile(locale):
    labels = get_language_profile(locale).labels
    report = {
        "scenes": 2,
        "avg_scene_words": 200.0,
        "hook_score_mean": 1.5,
        "rhythm_profile": {
            "available": True,
            "sentences": 24,
            "asl_cv": 0.45,
            "asl_iqr": 8.5,
            "length_entropy": 1.42,
            "normalized_entropy": 0.90,
            "bucket_shares": {"short": 0.25, "medium": 0.50, "long": 0.25},
        },
        "chapter_list": [
            {"chapter_num": 1, "title": "Kapitel 1", "asl": 12.0, "hook_score": 2}
        ],
    }
    html = render_pacing_panel(report, labels, locale)
    panel = ElementTree.fromstring(html)  # noqa: S314
    text = "".join(panel.itertext())
    assert labels["pac_asl_cv"] in text
    assert labels["pac_asl_iqr"] in text
    assert labels["pac_length_entropy"] in text
    assert labels["pac_rhythm_profile"] in text
    assert labels["pac_rhythm_hint"] in text
    assert labels["sentence_group_bounds_unavailable"] in text
    assert [
        node.text for node in panel.findall(".//div[@id='pacing-rhythm-buckets']/div/span")
    ] == [labels["sentence_group_" + key] for key in ("short", "medium", "long")]


def test_pacing_uses_effective_ranges_when_the_middle_group_is_empty():
    report = pacing_report(
        "## Synthetic\n\nA quiet morning. The river crossed the field beside the trees, "
        "passed the old gate and ran towards the village along a narrow muddy path.",
        CorpusConfig(short_sentence_max=21, medium_sentence_max=24, long_sentence_max=30),
    ).to_dict()
    assert "rhythm_word_bounds" not in report
    report["rhythm_word_bounds"] = (21, 20)
    panel = ElementTree.fromstring(render_pacing_panel(report))  # noqa: S314
    groups = panel.findall(".//div[@id='pacing-rhythm-buckets']/div")
    assert [group.findtext("span") for group in groups] == [
        "Short (≤ 21 words)", "Medium (empty range)", "Long (> 21 words)",
    ]
    assert [group.findtext("b") for group in groups] == ["50.0%", "0.0%", "50.0%"]


@pytest.mark.parametrize("locale", LOCALES)
def test_dialogue_panel_surfaces_indirect_speech(locale):
    labels = get_language_profile(locale).labels
    report = {
        "turns": 4,
        "dialogue_pct": 15.0,
        "avg_turn_words": 8.0,
        "turns_per_1000": 10.0,
        "indirect_speech_available": True,
        "indirect_speech": 7,
        "indirect_speech_per_1000": 17.5,
        "chapters": [
            {
                "chapter_num": 1,
                "title": "Kapitel 1",
                "turns": 4,
                "dialogue_pct": 15.0,
                "short_turns": 2,
                "short_turn_pct": 50.0,
                "long_turns": 0,
                "dialogue_asl": 8.0,
                "narration_asl": 14.0,
                "asl_contrast": -6.0,
                "indirect_speech_per_1000": 17.5,
            }
        ],
    }
    html = render_dialogue_panel(report, labels, locale)
    panel = ElementTree.fromstring(html)  # noqa: S314
    text = "".join(panel.itertext())
    assert labels["dlg_indirect_speech"] in text
    assert labels["dlg_indirect_speech_per_1000"] in text
    assert "7" in text


@pytest.mark.parametrize("locale", LOCALES)
def test_characters_panel_surfaces_character_voices(locale):
    from lixity.ui.narration import render_characters_panel

    labels = get_language_profile(locale).labels
    report = {
        "chapters": 2,
        "figures": [
            {
                "name": "Effi",
                "mentions": 12,
                "chapters_present": [1, 2],
                "first_chapter": 1,
                "last_chapter": 2,
                "longest_gap": 0,
                "presence_ratio": 1.0,
            }
        ],
        "character_voices": {
            "min_turns": 3,
            "narrator": {
                "words": 500,
                "asl": 16.0,
                "question_excl_rate": 4.0,
                "function_word_share": 48.0,
            },
            "characters": [
                {
                    "name": "Effi",
                    "status": "available",
                    "turns": 5,
                    "min_turns": 3,
                    "words": 60,
                    "dialogue_asl": 7.5,
                    "question_excl_rate": 40.0,
                    "function_word_share": 52.0,
                    "narrator_asl_delta": -8.5,
                    "narrator_question_excl_delta": 36.0,
                    "narrator_function_word_delta": 4.0,
                },
                {
                    "name": "Innstetten",
                    "status": "insufficient_turns",
                    "turns": 1,
                    "min_turns": 3,
                    "words": 10,
                    "dialogue_asl": None,
                    "question_excl_rate": None,
                    "function_word_share": None,
                    "narrator_asl_delta": None,
                    "narrator_question_excl_delta": None,
                    "narrator_function_word_delta": None,
                },
            ],
        },
    }
    html = render_characters_panel(report, [], labels, locale)
    panel = ElementTree.fromstring(html)  # noqa: S314
    text = "".join(panel.itertext())
    assert labels["chr_voices_title"] in text
    assert labels["chr_voices_hint"] in text
    assert labels["chr_voice_narrator"] in text
    assert labels["chr_voice_insufficient"] in text
    assert "Effi" in text
    assert "Innstetten" in text


@pytest.mark.parametrize("locale", LOCALES)
def test_reader_metric_options_match_available_measurements_and_reference(locale):
    from lixity.ui.manuscript_reader import reading_metric_control
    from lixity.ui.metric_reference import METRIC_REFERENCE_ENTRIES

    labels = get_language_profile(locale).labels
    control = reading_metric_control(labels, locale, {}, include_evidence=True, report=False)
    select = ElementTree.fromstring(control).find("select")  # noqa: S314
    options = {item.attrib["value"]: item for item in select.findall(".//option")}
    assert list(options) == ["", "asl", "function", "sticky", "dialogue", "dialogue_tag", "indirect_speech",
                             "filter", "sensory", "echo", "passive", "modal", "nominal"]
    for key, item in options.items():
        if key:
            assert item.attrib["data-reference"] == f"measure-{key}"
            assert item.attrib["data-reference"] in METRIC_REFERENCE_ENTRIES
            inline = item.attrib.get("data-inline-evidence") == "1"
            assert item.text == labels[("evidence_layer_" if inline else "layer_") + key]
            assert item.attrib["data-hint"] == labels[("reading_help_evidence_" if inline else "layer_hint_") + key]

    report = reading_metric_control(labels, locale, {}, include_evidence=False, report=True)
    assert 'data-inline-evidence="1"' not in report


@pytest.mark.parametrize("locale", LOCALES)
def test_characters_panel_surfaces_character_interactions(locale):
    from lixity.ui.narration import render_characters_panel

    labels = get_language_profile(locale).labels
    report = {
        "chapters": 2,
        "figures": [
            {
                "name": "Alice",
                "mentions": 10,
                "chapters_present": [1, 2],
                "first_chapter": 1,
                "last_chapter": 2,
                "longest_gap": 0,
                "presence_ratio": 1.0,
            }
        ],
        "character_interactions": {
            "pairs": [
                {"a": "Alice", "b": "Bob", "turn_exchanges": 4, "co_chapters": 2}
            ],
            "turn_dominance": [
                {"name": "Alice", "turns": 5, "words": 40, "word_share": 66.7, "turn_share": 62.5},
                {"name": "Bob", "turns": 3, "words": 20, "word_share": 33.3, "turn_share": 37.5},
            ],
        },
    }
    html = render_characters_panel(report, [], labels, locale)
    panel = ElementTree.fromstring(html)  # noqa: S314
    text = "".join(panel.itertext())
    assert labels["chr_interactions_title"] in text
    assert labels["chr_interactions_hint"] in text
    assert labels["chr_interaction_pair"] in text
    assert labels["chr_turn_exchanges"] in text
    assert labels["chr_co_chapters"] in text
    assert labels["chr_turn_share"] in text
    assert labels["chr_word_share"] in text
    assert "Alice ↔ Bob" in text


def test_manuscript_editor_js_has_phase2_enriched_diff_and_write_nudge():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    editor_js = (root / "src" / "lixity" / "ui" / "assets" / "manuscript-editor.js").read_text(encoding="utf-8")
    reader_css = (root / "src" / "lixity" / "ui" / "assets" / "manuscript-reader.css").read_text(encoding="utf-8")
    for field in ("length_entropy", "sticky_pct", "indirect_speech_per_1000"):
        assert field in editor_js
    assert "write-nudge" in editor_js
    assert "write-nudge" in reader_css
    assert "prefers-reduced-motion: reduce" in reader_css


def test_pacing_merges_sentence_distribution_with_jump_intervals():
    import json

    text = "## Chapter 1\n\nShort one. Another short sentence here. The quiet river ran slowly across the wide stony meadow.\n"
    cfg = CorpusConfig(language="en", short_sentence_max=3, medium_sentence_max=6, long_sentence_max=10)
    metrics = CorpusAnalyzer(cfg).analyze_text(text)
    report = pacing_report(text, cfg).to_dict()
    report["sentence_group_matches"] = {
        "rhythm": {"short": [{"paragraph_id": "p-0", "span_index": 0}], "medium": [], "long": []},
        "distribution": {"short": [{"paragraph_id": "p-0", "span_index": 0}], "medium": [], "long": [], "very_long": []},
    }
    panel = ElementTree.fromstring(render_pacing_panel(report, metrics=metrics))  # noqa: S314
    assert json.loads(panel.attrib["data-sentence-group-matches"]) == report["sentence_group_matches"]
    dist = panel.find(".//div[@class='rhythm-sentence-dist']")
    assert dist is not None
    rows = dist.findall(".//div[@class='dist']/div[@class='row']")
    assert len(rows) == 4
    assert rows[0].attrib.get("data-rhythm-min-words") == "1"
    assert rows[0].attrib.get("data-rhythm-max-words") == "3"
    assert rows[0].attrib.get("data-rhythm-group") == "short"
    jump_buttons = dist.findall(".//button[@data-rhythm-min-words]")
    assert len(jump_buttons) == 3
    assert rows[3].find(".//button") is None


def test_motifs_panel_forwards_codepoint_unit_and_quotation_context():
    import json

    from lixity.ui.narration import render_motifs_panel

    motifs = {
        "chapters": 1,
        "repeated_phrases": [
            {
                "phrase": "es ist so, dass",
                "count": 1,
                "chapters": [1],
                "mapped_occurrence_count": 1,
                "occurrences": [
                    {
                        "paragraph_id": "p-0",
                        "chapter": 1,
                        "start_line": 3,
                        "start": 1,
                        "end": 16,
                        "offset_unit": "unicode_codepoint",
                        "quote": "es ist so, dass",
                        "excerpt": "„es ist so, dass…“",
                        "quotation_context": "in_quotation",
                    }
                ],
            }
        ],
    }
    panel = ElementTree.fromstring(render_motifs_panel(motifs))  # noqa: S314
    group = panel.find(".//div[@data-motif-group]")
    assert group is not None and group.find(".//button[@data-motif-select]") is not None
    payload = json.loads(group.attrib["data-motif-occurrences"])
    assert payload[0]["offset_unit"] == "unicode_codepoint"
    assert payload[0]["quotation_context"] == "in_quotation"




