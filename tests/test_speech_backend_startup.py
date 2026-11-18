"""Native backend entrypoints validate local settings and remain cold."""
from __future__ import annotations

import pickle
import sys
from functools import partial
from pathlib import Path

import pytest

from lixity import speech_coqui, speech_toucan
from lixity.speech_profiles import COQUI_MODEL, COQUI_REFERENCE_MODEL
from lixity.speech_toucan import TOUCAN_MODEL


def _assets(root: Path, names: tuple[str, ...]) -> Path:
    for name in names:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("synthetic", encoding="utf-8")
    return root


def _arguments(tmp_path: Path, engine: str) -> tuple[object, list[str], str, int]:
    if engine.startswith("coqui"):
        model = _assets(tmp_path / "model", ("model_file.pth", "config.json"))
        arguments = ["--model", str(model)]
        if engine == "coqui-reference":
            converter = _assets(tmp_path / "converter", ("checkpoint.pth", "config.json"))
            arguments += ["--converter", str(converter)]
        return speech_coqui, arguments, COQUI_REFERENCE_MODEL if engine == "coqui-reference" else COQUI_MODEL, 8769
    source = _assets(tmp_path / "source", ("Modules/ToucanTTS/InferenceToucanTTS.py",
                     "Modules/Vocoder/HiFiGAN_Generator.py", "Preprocessing/TextFrontend.py",
                     "Preprocessing/multilinguality/iso_lookup.json"))
    model = _assets(tmp_path / "model", ("ToucanTTS.pt", "Vocoder.pt"))
    speaker = _assets(tmp_path / "speaker", speech_toucan._SPEAKER_FILES)
    return speech_toucan, ["--source", str(source), "--model", str(model), "--speaker", str(speaker)], TOUCAN_MODEL, 8772


@pytest.mark.parametrize("engine", ["coqui", "coqui-reference", "toucan"])
@pytest.mark.parametrize("timeout", [None, "17.5"])
def test_backend_main_stays_cold_and_forwards_lifecycle_settings(tmp_path, monkeypatch, engine, timeout):
    module, arguments, model, port = _arguments(tmp_path, engine)
    calls = []
    monkeypatch.setattr(module, "serve_worker", lambda loader, **settings: calls.append((loader, settings)), raising=False)
    monkeypatch.setattr(module.importlib, "import_module", lambda _: pytest.fail("optional import during startup"))
    arguments += ["--threads", "3"]
    if engine == "toucan":
        arguments += ["--device", "cuda"]
    if timeout is not None:
        arguments += ["--idle-timeout-seconds", timeout]
    monkeypatch.setattr(sys, "argv", ["worker", *arguments])
    module.main()
    assert len(calls) == 1
    loader, settings = calls[0]
    assert isinstance(loader, partial)
    assert loader.func is module.load_renderer
    expected_paths = ((tmp_path / "model", tmp_path / "converter" if engine == "coqui-reference" else None)
                      if engine.startswith("coqui") else (tmp_path / "source", tmp_path / "model", tmp_path / "speaker"))
    assert loader.args == expected_paths
    assert pickle.loads(pickle.dumps(loader)).args == loader.args  # noqa: S301 - locally constructed loader
    assert loader.keywords == ({"device": "cuda", "threads": 3} if engine == "toucan" else {"threads": 3})
    assert settings == {"model": model, "port": port, "idle_timeout_seconds": 300.0 if timeout is None else 17.5}
    assert all(isinstance(path, Path) and path.is_absolute() for path in loader.args if path is not None)


@pytest.mark.parametrize("engine", ["coqui", "coqui-reference", "toucan"])
@pytest.mark.parametrize("invalid", ["threads", "assets", "timeout"])
def test_backend_main_rejects_invalid_settings_before_serving(tmp_path, monkeypatch, engine, invalid):
    module, arguments, _model, _port = _arguments(tmp_path, engine)
    monkeypatch.setattr(module, "serve_worker", lambda *_args, **_kwargs: pytest.fail("invalid settings served"), raising=False)
    monkeypatch.setattr(module.importlib, "import_module", lambda _: pytest.fail("optional import during validation"))
    if invalid == "threads":
        arguments += ["--threads", "0"]
    elif invalid == "assets":
        arguments[arguments.index("--model") + 1] = str(tmp_path / "missing")
    else:
        arguments += ["--idle-timeout-seconds", "nan"]
    monkeypatch.setattr(sys, "argv", ["worker", *arguments])
    with pytest.raises((ValueError, OSError, SystemExit)):
        module.main()
