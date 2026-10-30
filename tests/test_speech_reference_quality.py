"""Signal diagnostics for voice references use synthetic signals only."""

import array
import io
import json
import math
import random
import wave

from lixity.cli import main
from lixity.speech import generate_silence_wav
from lixity.speech_coqui import unexpected_discards
from lixity.speech_reference_quality import SCHEMA, assess_reference

RATE = 24000


def _wav(samples: list[int]) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        writer.writeframes(array.array("h", samples).tobytes())
    return output.getvalue()


def _tone(seconds: float, frequencies: list[float], amplitude: float) -> list[int]:
    count = int(RATE * seconds)
    scale = amplitude / len(frequencies)
    return [round(scale * sum(math.sin(2 * math.pi * f * n / RATE) for f in frequencies)) for n in range(count)]


def _codes(result: dict[str, object]) -> set[str]:
    notes = result["notes"]
    assert isinstance(notes, list)
    return {note["code"] for note in notes}


def test_silence_is_reported_as_unmeasurable() -> None:
    result = assess_reference(generate_silence_wav(2))
    assert result["schema_version"] == SCHEMA
    assert result["bandwidth_hz"] is None and result["speech_level_dbfs"] is None
    assert _codes(result) == {"silent"}


def test_band_limited_signal_is_flagged_and_wideband_noise_is_not() -> None:
    narrow = assess_reference(_wav(_tone(3, [200, 700, 1500, 3000], 12000)))
    assert narrow["bandwidth_hz"] is not None and narrow["bandwidth_hz"] <= 4000
    assert "band_limited" in _codes(narrow)
    generator = random.Random(7)
    wide = assess_reference(_wav([round(generator.gauss(0, 4000)) for _ in range(RATE * 3)]))
    assert wide["bandwidth_hz"] is not None and wide["bandwidth_hz"] >= 11000
    assert "band_limited" not in _codes(wide)


def test_clipping_and_digitally_silent_pauses_are_reported() -> None:
    loud = _tone(2, [300, 900], 60000)
    clipped = [max(-32768, min(32767, value)) for value in loud]
    result = assess_reference(_wav(clipped + [0] * RATE))
    assert {"clipping", "digitally_silent_pauses"} <= _codes(result)
    assert result["peak_dbfs"] is not None and result["peak_dbfs"] > -0.5


def test_assessment_is_deterministic_and_rejects_other_formats() -> None:
    audio = _wav(_tone(1, [440], 8000))
    assert assess_reference(audio) == assess_reference(audio)
    stereo = io.BytesIO()
    with wave.open(stereo, "wb") as writer:
        writer.setparams((2, 2, RATE, 0, "NONE", "not compressed"))
        writer.writeframes(bytes(RATE * 4))
    try:
        assess_reference(stereo.getvalue())
    except ValueError:
        return
    raise AssertionError("stereo audio must be rejected")


def test_reference_cli_reports_quality_without_private_content(tmp_path, capsys) -> None:
    audio = tmp_path / "voice.wav"
    transcript = tmp_path / "voice.txt"
    audio.write_bytes(_wav(_tone(2, [200, 1000, 3000], 12000)))
    transcript.write_text("Private synthetic transcript.", encoding="utf-8")
    assert main(["audio-reference", "create", "--project", str(tmp_path), "--audio", str(audio),
                 "--transcript-file", str(transcript)]) == 0
    output = capsys.readouterr().out
    created = json.loads(output)
    assert created["schema_version"] == "lixity-audio-reference-created/1"
    assert created["quality"]["schema_version"] == SCHEMA and "Private synthetic" not in output
    assert main(["audio-reference", "inspect", "--project", str(tmp_path), "--reference-id", created["id"]]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["reference_id"] == created["id"]
    assert {key: value for key, value in inspected.items() if key != "reference_id"} == created["quality"]


def test_reference_cli_requires_the_inputs_of_each_action(tmp_path, capsys) -> None:
    assert main(["audio-reference", "create", "--project", str(tmp_path)]) == 1
    assert "--audio" in capsys.readouterr().err
    assert main(["audio-reference", "inspect", "--project", str(tmp_path)]) == 1
    assert "--reference-id" in capsys.readouterr().err


def test_expected_tokenizer_discards_stay_silent_and_others_are_listed_by_code_point() -> None:
    assert unexpected_discards(["\u0361", "\u032f", "\u201e", "\u201c"]) == ""
    assert unexpected_discards(["\u0361", "\u0283", "\u0101", "\u0283"]) == "U+0101 U+0283"
