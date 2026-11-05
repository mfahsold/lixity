"""Single registry for native speech identities and fixed local transports."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

QWEN_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
QWEN_DESIGN_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
QWEN_BASE_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
COQUI_MODEL = "coqui/tts_models/de/thorsten/vits"
COQUI_REFERENCE_MODEL = "coqui/tts_models/de/thorsten/vits+openvoice-v2"
F5_MODEL = "SWivid/F5-TTS"
TOUCAN_MODEL = "Flux9665/ToucanTTS"


@dataclass(frozen=True)
class NativeSpeechEngine:
    """Protocol identity, independent of optional checkpoint installation."""

    model: str
    endpoints: Mapping[str, str]
    service_name: str
    reference_required: bool = False


_QWEN_ENDPOINTS = MappingProxyType({
    "local": "http://127.0.0.1:8769/v1/audio/speech",
    "jetson": "http://127.0.0.1:8770/v1/audio/speech",
})
_COQUI_ENDPOINTS = MappingProxyType({"local": _QWEN_ENDPOINTS["local"]})
NATIVE_ENGINES: Mapping[str, NativeSpeechEngine] = MappingProxyType({
    "qwen3": NativeSpeechEngine(QWEN_MODEL, _QWEN_ENDPOINTS, "Qwen3-TTS"),
    "qwen3-design": NativeSpeechEngine(QWEN_DESIGN_MODEL, _QWEN_ENDPOINTS, "Qwen3-TTS"),
    "qwen3-base": NativeSpeechEngine(QWEN_BASE_MODEL, _QWEN_ENDPOINTS, "Qwen3-TTS", True),
    "coqui": NativeSpeechEngine(COQUI_MODEL, _COQUI_ENDPOINTS, "Coqui"),
    "coqui-reference": NativeSpeechEngine(COQUI_REFERENCE_MODEL, _COQUI_ENDPOINTS, "Coqui", True),
    "f5-tts": NativeSpeechEngine(F5_MODEL, MappingProxyType({
        "local": "http://127.0.0.1:8771/v1/audio/speech",
    }), "F5-TTS", True),
    "ims-toucan": NativeSpeechEngine(TOUCAN_MODEL, MappingProxyType({
        "local": "http://127.0.0.1:8772/v1/audio/speech",
    }), "IMS-Toucan", True),
})


def native_engine(engine: str) -> NativeSpeechEngine:
    """Reject unknown engines instead of falling through to a Qwen worker."""
    try:
        return NATIVE_ENGINES[engine]
    except KeyError:
        raise ValueError("Unknown native speech engine") from None


def native_endpoint(engine: str, target: str = "local") -> str:
    """Resolve only supported fixed loopback destinations."""
    try:
        return native_engine(engine).endpoints[target]
    except KeyError:
        raise ValueError("Unsupported speech execution target for this engine") from None


def engine_for_model(model: str) -> str:
    """Map a worker's declared model to its validated engine."""
    for engine, spec in NATIVE_ENGINES.items():
        if spec.model == model:
            return engine
    raise ValueError("Unknown native speech model")
