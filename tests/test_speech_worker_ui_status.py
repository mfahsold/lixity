"""Exercise worker status presentation without loading the full audio dialog."""
from __future__ import annotations

import json
import shutil
import string
import subprocess
from pathlib import Path

import pytest

from lixity.workspace_labels import WORKSPACE_LABELS

SOURCE = Path(__file__).resolve().parents[1] / "src/lixity/ui/assets/speech.js"


def _status(worker: dict[str, object], *, engine: str = "qwen3", language: str = "en") -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required to exercise speech status JavaScript")
    source = SOURCE.read_text(encoding="utf-8")
    function = source.split("  function updateWorkerStatus() {", 1)[1].split("  function updateRuntimeHint()", 1)[0]
    script = r"""
const worker = WORKER, engine = ENGINE;
const labels = LABELS;
const document = {documentElement: {lang: LANGUAGE}};
const fields = {worker_status: {}, engine: {value: engine}, target: {value: "local"}, worker_guide: {}};
const settingsForm = {dataset: {}};
const capabilities = {qwen3: {model: "qwen", name: "Qwen"}, coqui: {model: "coqui", name: "Coqui"}};
const workers = [worker];
function profileCapability() { return capabilities[engine] || {}; }
function label(key) { return labels["speech_" + key] || key; }
function uiFormat(key, args) { return (labels[key] || key).replace(/\{(\w+)\}/g, (_, name) => args[name]); }
function updateWorkerStatus() { FUNCTION
updateWorkerStatus();
process.stdout.write(fields.worker_status.textContent);
"""
    for key, value in {"WORKER": json.dumps(worker), "ENGINE": json.dumps(engine),
                       "LABELS": json.dumps({key: value for key, value in WORKSPACE_LABELS[language].items()
                                             if key.startswith("speech_worker_") or key in
                                             ("speech_target_local", "speech_provider_status")}),
                       "LANGUAGE": json.dumps(language), "FUNCTION": function}.items():
        script = script.replace(key, value)
    # Execute only checked-in JavaScript with synthetic worker fixtures.
    return subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout  # noqa: S603


@pytest.mark.parametrize("state,phrase", [("unloaded", "loads when rendering starts"),
                                           ("loading", "model is loading"),
                                           ("loaded", "model is loaded"),
                                           ("failed", "model failed during loading or rendering")])
def test_matching_worker_reports_residency(state: str, phrase: str) -> None:
    assert phrase in _status({"target": "local", "state": "ready", "model": "qwen",
                              "model_state": state, "active": False, "idle_timeout_seconds": 125})


def test_busy_worker_and_actual_localized_idle_policy() -> None:
    worker: dict[str, object] = {"target": "local", "state": "ready", "model": "qwen",
                                 "model_state": "loaded", "active": True, "idle_timeout_seconds": 1.5}
    assert "rendering" in _status(worker)
    assert "1,5" in _status(worker, language="de")
    worker["idle_timeout_seconds"] = 0
    assert "0 s" in _status(worker)
    del worker["idle_timeout_seconds"]
    assert "idle" not in _status(worker)


def test_mismatched_worker_does_not_claim_selected_model_is_loaded() -> None:
    status = _status({"target": "local", "state": "ready", "model": "coqui",
                      "model_state": "unloaded", "active": False, "idle_timeout_seconds": 300})
    assert "not the selected model" in status
    assert "idle" not in status


def test_old_worker_and_external_provider_keep_existing_status() -> None:
    assert "matches the selected model" in _status({"target": "local", "state": "ready", "model": "qwen"})
    assert _status({}, engine="openai-compatible") == WORKSPACE_LABELS["en"]["speech_provider_status"]


@pytest.mark.parametrize("state", ["starting", "unavailable"])
def test_service_readiness_takes_precedence_over_model_residency(state: str) -> None:
    status = _status({"target": "local", "state": state, "model": "qwen",
                      "model_state": "loaded", "active": False, "idle_timeout_seconds": 300})
    assert "model is loaded" not in status
    assert "idle" not in status


def test_residency_labels_cover_every_locale_with_matching_placeholders() -> None:
    keys = ("model_unloaded", "model_loading", "model_loaded", "model_active", "model_failed", "idle_policy")
    for language, labels in WORKSPACE_LABELS.items():
        for key in keys:
            value = labels["speech_worker_" + key]
            assert value, (language, key)
            expected = {"seconds"} if key == "idle_policy" else {"target", "model"}
            actual = {field for _, field, _, _ in string.Formatter().parse(value) if field}
            assert actual == expected, (language, key)
