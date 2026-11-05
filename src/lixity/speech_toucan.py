"""Optional IMS Toucan worker with explicit local assets and strict controls.

The model stack is imported only inside the worker. Normal application imports
need no torch, phonemizer, SpeechBrain or upstream checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import io
import os
import sys
from collections.abc import Callable, Collection, Mapping
from pathlib import Path
from typing import Any

from .log import get_logger
from .speech_controls import phoneme_spans
from .speech_engines import TOUCAN_MODEL
from .speech_profiles import AudioProfile
from .speech_references import SpeechReference
from .speech_worker import SAMPLE_RATE, _decode_reference, synthesize_native, worker_server

UPSTREAM_REVISION = "3cc2094d9c7123336eda7e299ac0bc90319ca9ff"
_LANGUAGES = {"de": ("deu", "de"), "en": ("eng", "en-us")}
_SPEAKER_FILES = ("hyperparams.yaml", "embedding_model.ckpt", "classifier.ckpt",
                  "mean_var_norm_emb.ckpt", "label_encoder.txt")
_SUFFIX_MODIFIERS = frozenset("\u02d0\u02d1\u0306\u0303\u0327\u02b7\u02b0\u02e0\u02c1\u02c0\u02bc"
                              "\u0339\u031e\u032a\u032c\u031d\u0330\u0308\u031c\u0325"
                              "\u02e5\u02e6\u02e7\u02e8\u02e9\u2b67\u2b68\u2b81\u2b83")


def synthesize_toucan(text: str, profile: AudioProfile, *, target: str = "local", opener: Any = None,
                      reference: SpeechReference | None = None) -> bytes:
    """Use the shared transport without changing an unavailable execution target."""
    if profile.engine != "ims-toucan" or profile.instructions:
        raise ValueError("IMS Toucan requires structured controls, not free-text direction")
    return synthesize_native(text, profile, target=target, opener=opener, reference=reference)


def prepare_phones(text: str, overrides: Mapping[str, str], *, phonemize: Callable[[str], str],
                   validate: Callable[[str], None]) -> str:
    """Phonemize plain gaps; preserve each explicit, validated IPA replacement."""
    pieces: list[str] = []
    previous = 0
    for start, end, replacement in phoneme_spans(text, overrides):
        if any(char in replacement for char in "~#.!?"):
            raise ValueError("Reserved control token in IMS Toucan pronunciation")
        validate(replacement)
        if start > previous:
            pieces.append(phonemize(text[previous:start]))
        pieces.append(replacement)
        previous = end
    if previous < len(text):
        pieces.append(phonemize(text[previous:]))
    phones = "~" + "".join(pieces) + "~#"
    validate(phones)
    return phones


def _validate_phone_order(phones: str, base_phones: Collection[str]) -> None:
    """Prevent upstream modifiers from targeting silence or disappearing."""
    preceding_phone = False
    modifiers: set[str] = set()
    for index, char in enumerate(phones):
        if char == "\u02c8":
            if index + 1 == len(phones) or phones[index + 1] not in base_phones:
                raise ValueError("Unsupported phoneme modifier order in IMS Toucan pronunciation")
            preceding_phone = False
        elif char in _SUFFIX_MODIFIERS:
            if not preceding_phone or char in modifiers:
                raise ValueError("Unsupported phoneme modifier order in IMS Toucan pronunciation")
            modifiers.add(char)
        else:
            preceding_phone = char in base_phones
            modifiers.clear()


def _normalize_gap(raw: str, postprocess: Callable[[str], str]) -> str:
    """Normalize G2P output without trimming punctuation pauses inside a sentence."""
    # The pinned frontend strips edge silence and prepends one leading silence.
    # Temporary phones keep meaningful gap-edge pauses away from those edges.
    normalized = postprocess("a" + raw + "a")
    if not isinstance(normalized, str) or not normalized.startswith("~a") or not normalized.endswith("a"):
        raise ValueError("IMS Toucan phonemization returned invalid data")
    return normalized[2:-1]


def _local_files(directory: Path, names: tuple[str, ...]) -> Path:
    try:
        root = directory.expanduser().resolve(strict=True)
    except OSError as exc:
        raise ValueError("IMS Toucan requires complete local assets") from exc
    if not root.is_dir() or any(not (root / name).is_file() or (root / name).stat().st_size == 0 for name in names):
        raise ValueError("IMS Toucan requires complete local assets: " + ", ".join(names))
    return root


def load_renderer(source_dir: Path, model_dir: Path, speaker_dir: Path, *, device: str = "cpu",
                  threads: int = 4) -> Callable[[dict[str, Any]], bytes]:
    """Load only supplied checkpoints; never request missing model resources."""
    if type(threads) is not int or not 1 <= threads <= 64:
        raise ValueError("Threads must be between 1 and 64")
    if device not in ("cpu", "cuda"):
        raise ValueError("Device must be cpu or cuda")
    source = _local_files(source_dir, ("Modules/ToucanTTS/InferenceToucanTTS.py",
                                      "Modules/Vocoder/HiFiGAN_Generator.py",
                                      "Preprocessing/TextFrontend.py", "Preprocessing/multilinguality/iso_lookup.json"))
    model = _local_files(model_dir, ("ToucanTTS.pt", "Vocoder.pt"))
    speaker = _local_files(speaker_dir, _SPEAKER_FILES)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ.setdefault("MPLBACKEND", "Agg")
    sys.path.insert(0, str(source))
    return _load_runtime(model, speaker, device=device, threads=threads)


def _load_runtime(model_dir: Path, speaker_dir: Path, *, device: str, threads: int) -> Callable[[dict[str, Any]], bytes]:
    torch = importlib.import_module("torch")
    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but is unavailable")
    torch.set_num_threads(threads)
    soundfile = importlib.import_module("soundfile")
    numpy = importlib.import_module("numpy")
    resample = importlib.import_module("torchaudio.transforms").Resample
    frontend_module = importlib.import_module("Preprocessing.TextFrontend")
    features = importlib.import_module("Preprocessing.articulatory_features")
    backend_class = importlib.import_module("phonemizer.backend").EspeakBackend
    # Initialize eSpeak explicitly. Do not use upstream's constructor or G2P
    # fallback: missing eSpeak must not download Transphone or print prose.
    backends = {language: backend_class(language=codes[1], preserve_punctuation=True, with_stress=True,
                                        language_switch="remove-flags") for language, codes in _LANGUAGES.items()}
    frontend = frontend_module.ArticulatoryCombinedTextFrontend.__new__(frontend_module.ArticulatoryCombinedTextFrontend)
    frontend.phone_to_vector = features.generate_feature_table()
    base_phones = set(frontend.phone_to_vector) - set("~#.!? ")
    frontend.add_silence_to_end = False
    frontend.use_word_boundaries = True
    frontend.peaking_perms = []
    frontend.dipping_perms = []
    frontend.rising_perms = []
    frontend.falling_perms = []
    if not callable(getattr(frontend, "postprocess_phoneme_string", None)):
        raise ValueError("Unsupported IMS Toucan checkout; use the documented pinned revision")

    checkpoint = torch.load(model_dir / "ToucanTTS.pt", map_location="cpu", weights_only=True)
    acoustic = importlib.import_module("Modules.ToucanTTS.InferenceToucanTTS").ToucanTTS(
        weights=checkpoint["model"], config=checkpoint["config"])
    with torch.no_grad():
        acoustic.store_inverse_all()
    acoustic = acoustic.to(device).eval()
    vocoder = importlib.import_module("Modules.Vocoder.HiFiGAN_Generator").HiFiGAN()
    vocoder.load_state_dict(torch.load(model_dir / "Vocoder.pt", map_location="cpu", weights_only=True))
    vocoder = vocoder.to(device).eval()
    vocoder.remove_weight_norm()
    encoder = importlib.import_module("speechbrain.pretrained").EncoderClassifier.from_hparams(
        source=str(speaker_dir), savedir=str(speaker_dir), overrides={"pretrained_path": str(speaker_dir)},
        run_opts={"device": device})
    language_ids = {language: frontend_module.get_language_id(codes[0]) for language, codes in _LANGUAGES.items()}
    if any(value is None for value in language_ids.values()):
        raise ValueError("IMS Toucan checkout lacks a configured language")
    reference_key: str | None = None
    reference_embedding: Any = None

    def validate(phones: str) -> None:
        # Upstream normalizes these two symbols even with input_phonemes=True.
        # Explicit pronunciations must not be silently rewritten.
        if any(char in phones for char in "ɚᵻ"):
            raise ValueError("Unsupported phoneme in IMS Toucan pronunciation")
        _validate_phone_order(phones, base_phones)
        try:
            frontend.string_to_tensor(phones, input_phonemes=True, handle_missing=False)
        except (KeyError, IndexError, ValueError) as exc:
            raise ValueError("Unsupported phoneme or modifier order in IMS Toucan pronunciation") from exc

    def render(request: dict[str, Any]) -> bytes:
        nonlocal reference_key, reference_embedding
        language = request["language"]
        if language not in _LANGUAGES or request.get("instructions"):
            raise ValueError("Unsupported IMS Toucan language or free-text direction")

        def phonemize(text: str) -> str:
            if not text.strip():
                return " "
            try:
                raw = backends[language].phonemize([text], strip=True)[0]
            except Exception as exc:
                raise ValueError("IMS Toucan phonemization failed; no fallback was used") from exc
            if not isinstance(raw, str):
                raise ValueError("IMS Toucan phonemization returned invalid data")
            normalized = _normalize_gap(raw, lambda phones: frontend.postprocess_phoneme_string(phones, True, False, False))
            return (" " if text[0].isspace() else "") + normalized + (" " if text[-1].isspace() else "")

        phones = prepare_phones(request["input"], request["phonemes"], phonemize=phonemize, validate=validate)
        reference_audio, frames = _decode_reference(request["reference_audio"], request["reference_text"])
        key = hashlib.sha256(reference_audio).hexdigest()
        with torch.inference_mode():
            if key != reference_key:
                waveform = numpy.frombuffer(frames, dtype="<i2").astype(numpy.float32) / 32768.0
                waveform = torch.tensor(waveform, device=device)
                waveform = resample(orig_freq=SAMPLE_RATE, new_freq=16000).to(device)(waveform)
                reference_embedding = encoder.encode_batch(wavs=waveform.unsqueeze(0)).squeeze()
                reference_key = key
            vectors = frontend.string_to_tensor(phones, input_phonemes=True, handle_missing=False).to(device)
            mel, _durations, _pitch, _energy = acoustic(
                vectors, return_duration_pitch_energy=True, utterance_embedding=reference_embedding,
                lang_id=language_ids[language].to(device), **request["prosody"])
            waveform = vocoder(mel.unsqueeze(0)).squeeze().cpu().numpy()
        if waveform.ndim != 1 or not waveform.size or not numpy.isfinite(waveform).all():
            raise ValueError("IMS Toucan returned invalid audio")
        output = io.BytesIO()
        soundfile.write(output, waveform, SAMPLE_RATE, format="WAV", subtype="PCM_16")
        return output.getvalue()

    return render


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Local pinned IMS Toucan checkout")
    parser.add_argument("--model", required=True, type=Path, help="Local ToucanTTS.pt and Vocoder.pt directory")
    parser.add_argument("--speaker", required=True, type=Path, help="Local SpeechBrain ECAPA checkpoint directory")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    logger = get_logger("speech.worker")
    logger.info("event=worker_model_load engine=ims-toucan device=%s status=started", args.device)
    try:
        renderer = load_renderer(args.source, args.model, args.speaker, device=args.device, threads=args.threads)
    except Exception:
        logger.warning("event=worker_model_load engine=ims-toucan status=failed")
        raise
    logger.info("event=worker_model_load engine=ims-toucan device=%s status=ready", args.device)
    server = worker_server(renderer, port=8772, model=TOUCAN_MODEL)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
