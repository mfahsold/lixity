"""Narration overviews preserve coverage and provide reversible measurement access."""

from xml.etree import ElementTree

import pytest

from lixity.dialogue import dialogue_report
from lixity.language import get_language_profile
from lixity.models import CorpusConfig
from lixity.pacing import pacing_report
from lixity.scenes import scene_report
from lixity.showing import showing_report
from lixity.ui.narration import (
    render_dialogue_panel,
    render_pacing_panel,
    render_scenes_panel,
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
    measurements = panel.find("./details[@class='scene-measurements']")
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
    assert [row.attrib["data-jump"] for row in chart] == [f"#ch-{number}" for number in range(1, count + 1)]
    assert chart[0].findtext("./span[@class='val']").endswith(" · 1 Quoted span")
    assert chart[-1].findtext("./span[@class='val']") == "0.0% · 0 Quoted spans"
    details = panel.find("./details[@class='dialogue-measurements']")
    assert details is not None and "open" not in details.attrib
    assert len(details.findall(".//tbody/tr")) == count


@pytest.mark.parametrize("locale", LOCALES)
def test_pacing_names_the_bar_measurement_and_explains_the_existing_hook_heuristic(locale):
    labels = get_language_profile(locale).labels
    report = pacing_report('## Synthetic chapter\n\nThe garden was still.\n\n"Why?"', CorpusConfig(language="en")).to_dict()
    assert report["chapter_list"][0]["hook_score"] == 3
    panel = ElementTree.fromstring(render_pacing_panel(report, labels, locale))  # noqa: S314
    help_texts = [span.attrib["data-help"] for span in panel.findall(".//span[@class='help']")]
    assert labels.get("help_pacing_hook") and labels["help_pacing_hook"].replace("{max_words}", "8") in help_texts
    assert labels.get("help_pacing_cohesion") in help_texts
    assert labels.get("help_pacing_monotony") in help_texts
    details = panel.find("./details[@class='pacing-measurements']")
    assert details is not None and "open" not in details.attrib
    assert len(details.findall(".//tbody/tr")) == 1
    guide = panel.find("./p[@class='panel-guide']")
    assert guide is not None and "ASL" in "".join(guide.itertext())
    assert labels["pacing_scale"] in "".join(guide.itertext())
    value = panel.find("./div[@class='dist scrollable']/div/span[@class='val']")
    assert "ASL" in "".join(value.itertext())
    assert "3" in "".join(value.itertext())
    sparkline = panel.find(".//span[@class='sparkline']")
    assert sparkline is not None and sparkline.text


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
    text = "".join(panel.itertext())
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
def test_inline_evidence_layers_includes_indirect_speech(locale):
    from lixity.ui.manuscript_reader import INLINE_EVIDENCE_LAYERS, inline_evidence_controls

    assert "indirect_speech" in INLINE_EVIDENCE_LAYERS
    labels = get_language_profile(locale).labels
    assert labels["evidence_layer_indirect_speech"]
    assert labels["reading_help_evidence_indirect_speech"]
    html = inline_evidence_controls(labels)
    assert 'data-evidence-layer="indirect_speech"' in html
    assert labels["evidence_layer_indirect_speech"] in html


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




