"""Project-specific voice probes use synthetic manuscript data only."""
# ruff: noqa: RUF001 -- IPA symbols are intentionally different from Latin letters.
from __future__ import annotations

import hashlib
import io
import json
import wave
from array import array

import pytest

from lixity.api import about
from lixity.cli import main
from lixity.cli_completions import build_completion_scripts
from lixity.speech_controls import apply_pronunciation_spans
from lixity.speech_probe import (
    MAX_PROBE_SECONDS,
    MIN_PROBE_SECONDS,
    PROBE_METHOD_VERSION,
    PROBE_SCHEMA,
    build_voice_probe_script,
    voice_probe_sha256,
)


def _german_manuscript() -> str:
    lines = ["## Erstes Kapitel", ""]
    for index in range(1, 31):
        lines.extend([
            f"Mara besucht den alten Leuchtturm in Travemünde Nummer {index}.",
            f"Hansen prüft den Frachtbrief von Kowalski am Hafen von Lübeck Nummer {index}.",
            f"Die Latente Steuern belastet die Rechnung aus Rotterdam Nummer {index}.",
            "",
        ])
    return "\n".join(lines)


def _settings() -> dict[str, object]:
    return {
        "language": "de",
        "characters": {
            "Mara": {"aliases": []},
            "Hansen": {"aliases": []},
            "Kowalski": {"aliases": []},
        },
        "audio": {
            "schema_version": "lixity-audio-settings/5",
            "selected": "narrator",
            "pronunciation_lexicon": {
                "schema_version": "lixity-pronunciation-lexicon/1",
                "entries": {
                    "Travemünde": {"ipa": "tʁaːvəmʏndə"},
                    "Latente Steuern": {"respelling": "Latente Schteuern"},
                },
            },
            "profiles": {
                "narrator": {
                    "engine": "ims-toucan", "language": "de", "voice": "reference",
                    "reference_id": "a" * 64,
                },
            },
        },
    }


def _english_manuscript() -> str:
    return "\n\n".join(
        f"Mara meets Hansen at harbour number {index}. "
        f"Kowalski reads the freight manifest for Rotterdam station {index}."
        for index in range(1, 31)
    )


def _configured_manuscript() -> str:
    lines = ["## Kapitel 1", ""]
    for index in range(1, 32):
        lines.extend([
            f"RM prüft den Kupferkompass am Hafen {index}.",
            f"Compass zeigt Mara die Kupferkompassnadel {index}.",
            f"Silva zeichnet die Karte {index}.",
            f"rm notiert den Frachtbrief RM-CURIA-084 {index}.",
            "",
        ])
    lines.extend(["## Kapitel 2", ""])
    for index in range(1, 12):
        lines.extend([f"Silva öffnet die Karte {index}.", ""])
    return "\n".join(lines)


def _provenance(probe) -> dict[str, dict[str, object]]:
    return {entry["term"]: entry for entry in probe.to_dict()["term_provenance"]}


def _silent_wav(seconds: int) -> bytes:
    rate = 24_000
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(array("h", [0]).tobytes() * (seconds * rate))
    return output.getvalue()


def test_probe_covers_project_terms_with_bounded_parts_and_duration():
    text = _german_manuscript()
    probe = build_voice_probe_script(text, language="de", project_config=_settings())
    data = probe.to_dict()
    assert data["schema_version"] == PROBE_SCHEMA
    assert data["status"] == "ready"
    assert MIN_PROBE_SECONDS <= probe.estimated_seconds <= MAX_PROBE_SECONDS
    assert 3 <= len(probe.parts) <= 6
    assert all(43 <= part.words <= 87 for part in probe.parts)
    assert all(20 <= part.estimated_seconds <= 40 for part in probe.parts)
    assert probe.estimated_seconds == sum(part.estimated_seconds for part in probe.parts)
    assert all(part.to_dict()["estimated_seconds"] == part.estimated_seconds for part in probe.parts)
    assert {"Mara", "Hansen", "Kowalski", "Travemünde", "Latente Steuern"} <= set(probe.covered_terms)
    assert not {"der", "die", "das", "ein", "eine", "den"} & {
        term.casefold() for term in probe.selected_terms
    }
    assert len({sentence.text for part in probe.parts for sentence in part.sentences}) == sum(
        len(part.sentences) for part in probe.parts
    )
    provenance = _provenance(probe)
    assert provenance["Mara"]["kind"] == "character"
    assert provenance["Mara"]["count"] == 30
    assert provenance["Travemünde"]["kind"] == "lexicon"
    assert provenance["Travemünde"]["ipa"] == "tʁaːvəmʏndə"
    assert provenance["Latente Steuern"]["respelling"] == "Latente Schteuern"
    assert probe.warnings == ()


def test_probe_is_deterministic_and_keeps_manuscript_text_out_of_repr():
    text = _german_manuscript()
    first = build_voice_probe_script(text, language="de", project_config=_settings())
    second = build_voice_probe_script(text, language="de", project_config=_settings())
    assert first == second
    assert first.to_dict() == second.to_dict()
    assert "Travemünde" not in repr(first)
    assert "Travemünde" not in repr(first.parts[0])
    assert "Travemünde" not in repr(first.parts[0].sentences[0])
    assert "Travemünde" not in repr(first.term_provenance)
    assert any("Travemünde" in part.text for part in first.parts)


def test_probe_hashes_exact_source_and_canonical_settings_and_script():
    text = _german_manuscript().replace("\n", "\r\n")
    settings = _settings()
    probe = build_voice_probe_script(text, language="de", project_config=settings)
    data = probe.to_dict()
    assert data["source_sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert data["method_version"] == PROBE_METHOD_VERSION
    assert data["duration_method"] == "word_count_at_130_wpm"

    reordered = dict(reversed(list(settings.items())))
    reordered["audio"] = dict(reversed(list(settings["audio"].items())))  # type: ignore[arg-type]
    same = build_voice_probe_script(text, language="de", project_config=reordered)
    assert same.settings_sha256 == probe.settings_sha256
    assert "/Users/" not in json.dumps(data, ensure_ascii=False)

    path_one = {**settings, "manuscript": "/private/one/draft.md"}
    path_two = {**settings, "manuscript": "/restored/two/draft.md"}
    first_path = build_voice_probe_script(text, language="de", project_config=path_one)
    second_path = build_voice_probe_script(text, language="de", project_config=path_two)
    assert first_path.settings_sha256 == second_path.settings_sha256
    assert first_path.probe_sha256 == second_path.probe_sha256
    changed_audio = {**settings, "audio": {
        **settings["audio"],  # type: ignore[dict-item]
        "pronunciations": {"Travemünde": "Travemunde"},
    }}
    changed_settings = build_voice_probe_script(text, language="de", project_config=changed_audio)
    assert changed_settings.settings_sha256 != probe.settings_sha256
    assert changed_settings.probe_sha256 != probe.probe_sha256

    without_self_hash = {key: value for key, value in data.items() if key != "probe_sha256"}
    canonical = json.dumps(
        without_self_hash, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    assert data["probe_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert voice_probe_sha256(data) == data["probe_sha256"]
    assert voice_probe_sha256({**data, "probe_sha256": "0" * 64}) == data["probe_sha256"]
    changed = {**data, "target_seconds": 151}
    assert voice_probe_sha256(changed) != data["probe_sha256"]


def test_source_digest_override_binds_original_bytes_and_is_validated():
    normalized = _german_manuscript()
    original_bytes = normalized.replace("\n", "\r\n").encode("utf-8")
    original_digest = hashlib.sha256(original_bytes).hexdigest()
    probe = build_voice_probe_script(
        normalized, language="de", project_config=_settings(), source_sha256=original_digest,
    )
    assert probe.source_sha256 == original_digest
    assert probe.to_dict()["source_sha256"] == original_digest
    assert probe.probe_sha256 != build_voice_probe_script(
        normalized, language="de", project_config=_settings(),
    ).probe_sha256


@pytest.mark.parametrize("digest", ["A" * 64, "a" * 63, "g" * 64, ""])
def test_probe_rejects_invalid_source_digest_override(digest):
    with pytest.raises(ValueError, match="source_sha256"):
        build_voice_probe_script("Mara wartete am Hafen.", language="de", source_sha256=digest)


def test_configured_terms_use_aliases_scoping_compounds_and_strict_boundaries():
    settings = {
        "language": "de",
        "terms": {
            "Kupferkompass": {"aliases": ["Compass"], "match_compounds": True},
            "Karte": {
                "scoped_alternatives": [{"term": "Silva", "chapters": [2]}],
            },
            "RM": {"case_sensitive": True, "strict_boundaries": True},
        },
    }
    probe = build_voice_probe_script(_configured_manuscript(), language="de", project_config=settings)
    assert probe.status == "ready"
    provenance = _provenance(probe)
    assert provenance["Kupferkompass"] == {
        "term": "Kupferkompass", "kind": "configured_term", "count": 93,
    }
    # Forty-two canonical Karte hits plus eleven in-scope Silva alternatives;
    # the thirty chapter-one Silva forms are deliberately out of scope.
    assert provenance["Karte"]["count"] == 53
    assert provenance["RM"]["count"] == 31
    assert {"Kupferkompass", "Karte", "RM"} <= set(probe.covered_terms)
    assert not {"Compass", "Silva", "rm"} & set(probe.selected_terms)
    assert "RM-CURIA-084" in probe.selected_terms
    assert "084" not in probe.selected_terms
    assert any(
        "Kupferkompassnadel" in part.text and "Kupferkompass" in part.terms
        for part in probe.parts
    )


def test_selected_audio_profile_isolates_terms_and_emits_part_relative_spans():
    settings = _settings()
    settings.pop("characters")
    audio = settings["audio"]
    assert isinstance(audio, dict)
    audio["pronunciations"] = {"Travemünde": "Travemunde"}
    audio["pronunciation_matching"] = {"case_sensitive": False}
    audio["profiles"] = {
        "narrator": {
            "engine": "ims-toucan", "language": "de", "voice": "reference",
            "reference_id": "a" * 64,
            "phonemes": {"Mara": "ˈmaːʁa", "Sena": "ˈzeːna"},
            "pronunciations": {"Hansen": "Hahnsen"},
        },
        "alternate": {
            "engine": "ims-toucan", "language": "de", "voice": "reference",
            "reference_id": "b" * 64,
            "phonemes": {"Mara": "WRONG_MARA", "Borana": "WRONG_BORANA"},
            "pronunciations": {"Kowalski": "WRONG_KOWALSKI"},
        },
    }
    text = _german_manuscript() + "\n\n" + "\n\n".join(
        f"Sena und Borana prüfen den Frachtbrief {index}." for index in range(1, 16)
    ) + "\n\n" + "\n\n".join(
        f"hansen prüft den Frachtbrief von Kowalski {index}." for index in range(1, 6)
    )
    probe = build_voice_probe_script(text, language="de", project_config=settings)
    data = probe.to_dict()
    serialized = json.dumps(data, ensure_ascii=False)
    assert probe.status == "ready"
    assert {"Mara", "Hansen", "Sena", "Travemünde", "Latente Steuern"} <= set(probe.covered_terms)
    assert not {"Borana", "Kowalski"} & set(probe.selected_terms)
    assert "WRONG_" not in serialized
    provenance = _provenance(probe)
    assert provenance["Mara"]["ipa"] == "ˈmaːʁa"
    assert provenance["Hansen"]["respelling"] == "Hahnsen"

    saw_hansen = saw_mara = saw_lexicon_respelling = False
    for part in probe.parts:
        for span in (*part.substitutions, *part.phonemes):
            assert 0 <= span.start < span.end <= len(part.text)
            assert part.text[span.start:span.end] == span.source
            assert span.to_dict()["kind"] in {"substitution", "phoneme"}
        spoken = apply_pronunciation_spans(
            part.text, [(span.start, span.end, span.replacement) for span in part.substitutions],
        )
        saw_hansen |= any(
            span.source.casefold() == "hansen" and span.replacement == "Hahnsen" for span in part.substitutions
        ) and "Hahnsen" in spoken
        saw_mara |= any(
            span.source == "Mara" and span.replacement == "ˈmaːʁa" for span in part.phonemes
        )
        saw_lexicon_respelling |= any(
            span.source == "Latente Steuern" and span.replacement == "Latente Schteuern"
            for span in part.substitutions
        )
        assert not any(span.source == "Travemünde" for span in part.substitutions)
    assert saw_hansen
    assert saw_mara
    assert saw_lexicon_respelling


@pytest.mark.parametrize("target", [120, 180])
def test_ready_probe_respects_duration_boundaries_and_part_balance(target):
    probe = build_voice_probe_script(
        _german_manuscript(), language="de", project_config=_settings(), target_seconds=target,
    )
    assert probe.status == "ready"
    assert probe.target_seconds == target
    assert MIN_PROBE_SECONDS <= probe.estimated_seconds <= MAX_PROBE_SECONDS
    assert 3 <= len(probe.parts) <= 6
    assert all(43 <= part.words <= 87 for part in probe.parts)
    assert all(20 <= part.estimated_seconds <= 40 for part in probe.parts)
    assert probe.estimated_seconds == sum(part.estimated_seconds for part in probe.parts)
    assert all(part.to_dict()["estimated_seconds"] == part.estimated_seconds for part in probe.parts)


def test_short_manuscript_reports_explicit_unsavable_status_without_padding():
    probe = build_voice_probe_script(
        "Mara wartete am Hafen. Hansen las den Frachtbrief. Kowalski öffnete die Tür.",
        language="de", project_config=_settings(),
    )
    assert probe.status == "insufficient_source"
    assert probe.estimated_seconds < MIN_PROBE_SECONDS
    assert [warning.to_dict() for warning in probe.warnings] == [{
        "code": "insufficient_source",
        "message": probe.warnings[0].message,
    }]
    assert "not savable" in probe.warnings[0].message
    assert sum(len(part.sentences) for part in probe.parts) == 3
    assert len({sentence.text for part in probe.parts for sentence in part.sentences}) == 3


def test_english_probe_uses_manuscript_sentences_and_character_names():
    probe = build_voice_probe_script(
        _english_manuscript(), language="en",
        project_config={"characters": {"Mara": {"aliases": []}, "Hansen": {"aliases": []}, "Kowalski": {"aliases": []}}},
    )
    assert probe.status == "ready"
    assert {"Mara", "Hansen", "Kowalski"} <= set(probe.covered_terms)
    assert "The" not in probe.selected_terms
    assert any("harbour number" in part.text for part in probe.parts)


def test_repeated_sentences_are_deduplicated_by_text_and_source_order():
    unique = [f"Mara visits the old harbour near station {index}." for index in range(1, 41)]
    text = "\n\n".join([unique[0]] * 8 + unique)
    probe = build_voice_probe_script(text, language="en")
    assert probe.status == "ready"
    selected = [sentence.text for part in probe.parts for sentence in part.sentences]
    assert selected.count(unique[0]) == 1
    assert len(selected) == len(set(selected))


def test_probe_balances_dialogue_and_narration_when_both_are_available():
    lines: list[str] = []
    for index in range(1, 31):
        lines.extend([
            f"Mara records the harbour measurement number {index}.",
            f"\"Hansen reads the freight manifest aloud {index}.\"",
        ])
    probe = build_voice_probe_script("\n\n".join(lines), language="en")
    assert probe.status == "ready"
    sentences = [sentence for part in probe.parts for sentence in part.sentences]
    dialogue_words = sum(sentence.words for sentence in sentences if sentence.dialogue)
    total_words = sum(sentence.words for sentence in sentences)
    assert any(sentence.dialogue for sentence in sentences)
    assert any(not sentence.dialogue for sentence in sentences)
    assert 0.3 <= dialogue_words / total_words <= 0.7


def test_invalid_configuration_is_structured_private_and_unsavable():
    settings = _settings()
    settings["terms"] = {"RM": {"strict_boundaries": "not-a-boolean"}}
    probe = build_voice_probe_script(_german_manuscript(), language="de", project_config=settings)
    assert probe.status == "invalid_configuration"
    assert probe.parts == ()
    assert probe.selected_terms == ()
    assert probe.warnings[0].code == "invalid_configuration"
    assert "not-a-boolean" not in repr(probe)
    assert "not-a-boolean" not in probe.warnings[0].message
    assert len(probe.source_sha256) == 64
    assert len(probe.settings_sha256) == 64
    assert voice_probe_sha256(probe.to_dict()) == probe.probe_sha256


@pytest.mark.parametrize("target", [119, 181, 150.0, True])
def test_probe_rejects_invalid_target_duration(target):
    with pytest.raises(ValueError, match="120 and 180"):
        build_voice_probe_script("Mara wartete am Hafen.", language="de", target_seconds=target)


def test_probe_cli_reads_exact_snapshot_and_project_language(tmp_path, capsys):
    (tmp_path / "lixity.toml").write_text('language = "de"\nmanuscript = "draft.md"\n', encoding="utf-8")
    source = _german_manuscript().replace("\n", "\r\n")
    (tmp_path / "draft.md").write_bytes(source.encode("utf-8"))
    assert main(["audio-reference", "probe-script", "--project", str(tmp_path), "--target-seconds", "150"]) == 0
    output = capsys.readouterr().out
    data = json.loads(output)
    assert data["schema_version"] == PROBE_SCHEMA
    assert data["status"] == "ready"
    assert data["language"] == "de"
    assert data["source_sha256"] == hashlib.sha256(source.encode("utf-8")).hexdigest()
    assert "Travemünde" in output
    assert voice_probe_sha256(data) == data["probe_sha256"]
    assert main(["audio-reference", "probe-script", "--project", str(tmp_path), "--target-seconds", "181"]) == 1
    assert "120 and 180" in capsys.readouterr().err


def test_probe_cli_resolves_auto_without_german_fallback_and_has_no_root_paths(tmp_path, capsys):
    hashes = []
    for name in ("first", "second"):
        root = tmp_path / name
        root.mkdir()
        (root / "lixity.toml").write_text(
            'language = "auto"\nmanuscript = "draft.md"\n', encoding="utf-8",
        )
        (root / "draft.md").write_text(_english_manuscript(), encoding="utf-8")
        assert main(["audio-reference", "probe-script", "--project", str(root)]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "ready"
        assert data["language"] == "en"
        hashes.append((data["source_sha256"], data["settings_sha256"], data["probe_sha256"]))
        assert str(root) not in json.dumps(data)
    assert hashes[0] == hashes[1]


def test_probe_cli_explicit_language_overrides_project_auto(tmp_path, capsys):
    (tmp_path / "lixity.toml").write_text(
        'language = "auto"\nmanuscript = "draft.md"\n', encoding="utf-8",
    )
    (tmp_path / "draft.md").write_text(_english_manuscript(), encoding="utf-8")
    assert main([
        "audio-reference", "probe-script", "--project", str(tmp_path), "--language", "de",
    ]) == 0
    assert json.loads(capsys.readouterr().out)["language"] == "de"


def test_probe_cli_inspects_reference_sets_without_audio_bytes(tmp_path, capsys):
    from lixity.speech_references import prepare_reference, save_reference_set

    probe = build_voice_probe_script(
        _german_manuscript(), language="de", project_config=_settings(), target_seconds=120,
    )
    data = probe.to_dict()
    parts = [
        prepare_reference(_silent_wav(part.estimated_seconds), part.text)
        for part in probe.parts
    ]
    reference = save_reference_set(
        tmp_path,
        parts,
        source_sha256=probe.source_sha256,
        settings_sha256=probe.settings_sha256,
        probe_sha256=probe.probe_sha256,
        language=probe.language,
        terms=probe.covered_terms,
        fallback_part_index=2,
        probe=data,
    )
    assert main([
        "audio-reference", "inspect", "--project", str(tmp_path),
        "--reference-id", reference.id,
    ]) == 0
    output = capsys.readouterr().out
    inspected = json.loads(output)
    assert inspected["schema_version"] == "lixity-audio-reference-set-inspection/1"
    assert inspected["id"] == reference.id
    assert inspected["kind"] == "set"
    assert inspected["part_count"] == len(parts)
    assert 120 <= inspected["duration_seconds"] <= 180
    assert inspected["language"] == probe.language
    assert inspected["source_sha256"] == probe.source_sha256
    assert inspected["settings_sha256"] == probe.settings_sha256
    assert inspected["probe_sha256"] == probe.probe_sha256
    assert inspected["fallback_part_index"] == 2
    assert inspected["terms"] == list(probe.covered_terms)
    assert [part["id"] for part in inspected["parts"]] == [part.id for part in parts]
    assert [part["fallback"] for part in inspected["parts"]] == [
        index == 2 for index in range(1, len(parts) + 1)
    ]
    assert [part["transcript"] for part in inspected["parts"]] == [part.text for part in probe.parts]
    assert all(part["quality"]["schema_version"] == "lixity-audio-reference-quality/1"
               for part in inspected["parts"])
    assert "audio_bytes" not in inspected
    assert "embedding" not in output


def test_read_aloud_render_snapshot_accepts_a_reference_set(tmp_path, monkeypatch):
    from lixity.speech_references import SpeechReferenceSet, prepare_reference, save_reference_set

    source = tmp_path / "draft.md"
    source.write_text(_german_manuscript(), encoding="utf-8")
    settings = {"language": "de", "characters": _settings()["characters"]}
    probe = build_voice_probe_script(
        source.read_text(encoding="utf-8"), language="de", project_config=settings, target_seconds=120,
    )
    parts = [prepare_reference(_silent_wav(part.estimated_seconds), part.text) for part in probe.parts]
    reference = save_reference_set(
        tmp_path, parts,
        source_sha256=probe.source_sha256, settings_sha256=probe.settings_sha256,
        probe_sha256=probe.probe_sha256, language=probe.language,
        terms=probe.covered_terms, probe=probe.to_dict(),
    )
    (tmp_path / "lixity.toml").write_text(
        'language = "de"\nmanuscript = "draft.md"\n'
        '[audio]\nschema_version = "lixity-audio-settings/5"\nselected = "narrator"\n'
        '[audio.profiles.narrator]\nengine = "qwen3-base"\nlanguage = "de"\n'
        f'voice = "reference"\nreference_id = "{reference.id}"\n',
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_render(**kwargs):
        captured.update(kwargs)
        return kwargs["output_path"]

    monkeypatch.setattr("lixity.speech.render_speech_audio", fake_render)
    output = tmp_path / "result.wav"
    assert main([
        "read-aloud", "--project", str(tmp_path), "--no-direction", "--no-audio-cache",
        "-o", str(output),
    ]) == 0
    references = captured["references"]
    assert isinstance(references, dict)
    assert isinstance(references[reference.id], SpeechReferenceSet)


def test_probe_cli_preserves_single_reference_inspection_output(tmp_path, capsys):
    from lixity.speech_references import save_reference

    reference = save_reference(tmp_path, _silent_wav(1), "Mara waits at the harbour.")
    assert main([
        "audio-reference", "inspect", "--project", str(tmp_path),
        "--reference-id", reference.id,
    ]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["schema_version"] == "lixity-audio-reference-quality/1"
    assert inspected["reference_id"] == reference.id
    assert inspected["duration_seconds"] == 1.0
    assert "parts" not in inspected


def test_probe_help_completions_and_api_advertise_the_contract(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["audio-reference", "--help"])
    assert exit_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "probe-script" in help_text
    assert "--target-seconds" in help_text
    assert "120 to 180" in help_text
    bash, zsh = build_completion_scripts([], [])
    assert "probe-script" in bash and "--target-seconds" in bash
    assert "probe-script" in zsh and "--target-seconds" in zsh
    commands = about(section="commands")["commands"]
    reference = next(command for command in commands if command["name"] == "audio-reference")
    assert reference["probe_action"] == "probe-script"
    assert reference["probe_schema_version"] == PROBE_SCHEMA
    assert reference["probe_target_seconds"] == {"minimum": 120, "maximum": 180, "default": 150}


def test_probe_requires_manuscript_prose_and_reports_unsavable_status():
    empty = build_voice_probe_script("", language="de")
    code_only = build_voice_probe_script("```\nMara\n```", language="de")
    assert empty.status == "insufficient_source"
    assert code_only.status == "insufficient_source"
    assert empty.source_sha256 == hashlib.sha256(b"").hexdigest()
    for probe in (empty, code_only):
        assert probe.parts == ()
        assert probe.warnings[0].code == "insufficient_source"
        assert "not savable" in probe.warnings[0].message
