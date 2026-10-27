"""Optional local syntax parsers with bounded, serialized model reuse.

Models must be installed explicitly. Neither loading nor inference downloads
resources, and unavailable or incomplete annotations never select a fallback.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import version
from threading import RLock
from typing import Any

_LOCK = RLock()
_LANGUAGES = frozenset({"de", "en", "fr", "es", "it", "pt", "nl"})
_STANZA_PROCESSORS = {
    "tokenize": "markit_nocharlm", "mwt": "markit", "pos": "markit_nocharlm",
    "lemma": "markit_nocharlm", "depparse": "markit_nocharlm",
}
_STANZA_PROFILES = {
    "stanza:it_markit": ("it", _STANZA_PROCESSORS),
    "stanza:fr_gsd": ("fr", {"tokenize": "gsd_nocharlm", "mwt": "gsd", "pos": "gsd_nocharlm",
                            "lemma": "gsd_nocharlm", "depparse": "gsd_nocharlm"}),
}


@dataclass(frozen=True)
class SyntaxToken:
    i: int
    start: int
    end: int
    text: str
    lemma: str
    pos: str
    tag: str
    form: str
    mood: str
    tense: str
    head: int
    dep: str
    aspect: str = ""


@dataclass(frozen=True)
class _Parser:
    pipeline: Any
    runtime: str
    runtime_version: str
    model_version: str
    language: str


@lru_cache(maxsize=2)
def _model(name: str) -> _Parser:
    """Only called under _LOCK: load an explicitly selected local model."""
    try:
        if name.startswith("stanza:"):
            if name not in _STANZA_PROFILES:
                raise ValueError(f"Unsupported local Stanza profile {name!r}")
            import stanza

            language, processors = _STANZA_PROFILES[name]
            options: dict[str, Any] = {}
            if directory := os.environ.get("STANZA_RESOURCES_DIR"):
                options["dir"] = directory
            pipeline = stanza.Pipeline(
                lang=language, package=None, processors=dict(processors),
                use_gpu=False, download_method=None, verbose=False, **options,
            )
            return _Parser(pipeline, "stanza", version("stanza"),
                           str(getattr(stanza, "__resources_version__", "unknown")), language)

        import spacy

        pipeline = spacy.load(name, exclude=["ner"])
        if pipeline.lang not in _LANGUAGES:
            raise ValueError(f"Unsupported parser language {pipeline.lang!r}")
        if pipeline.lang != name.split("_", 1)[0]:
            raise ValueError("Installed model language does not match its selected language prefix")
        pipes = set(pipeline.pipe_names)
        if "parser" not in pipes or not pipes.intersection({"tagger", "morphologizer"}):
            raise ValueError("A parser and tagger or morphologizer are required")
        return _Parser(pipeline, "spacy", version("spacy"),
                       str(pipeline.meta.get("version", "unknown")), pipeline.lang)
    except Exception as exc:
        raise ValueError(
            f"Linguistic model {name!r} unavailable or invalid: {exc}; "
            "install the optional runtime and model explicitly; no fallback was used"
        ) from exc


def model_identity(model_name: str) -> dict[str, str]:
    """Describe the selected local pipeline without reading manuscript text."""
    with _LOCK:
        model = _model(model_name)
        result = {
            "model": model_name, "version": model.model_version,
            "runtime": model.runtime, "runtime_version": model.runtime_version,
            "language": model.language,
        }
        if model.runtime == "spacy":
            result["spacy_version"] = model.runtime_version
        return result


def parser_language(model_name: str) -> str:
    """Return the loaded pipeline's supported language, never infer from text."""
    with _LOCK:
        return _model(model_name).language


def _spacy_tokens(doc: Any, text: str) -> tuple[SyntaxToken, ...]:
    if text.strip() and not all(doc.has_annotation(name) for name in ("POS", "MORPH", "DEP")):
        raise ValueError("Missing POS, morphology or dependency annotation")

    def feature(token: Any, name: str) -> str:
        values = token.morph.get(name)
        return str(values[0]) if len(values) == 1 else ""

    return tuple(SyntaxToken(
        token.i, token.idx, token.idx + len(token.text), token.text,
        token.lemma_, token.pos_, token.tag_, feature(token, "VerbForm"),
        feature(token, "Mood"), feature(token, "Tense"), token.head.i,
        token.dep_, feature(token, "Aspect"),
    ) for token in doc)


def _stanza_tokens(doc: Any, text: str) -> tuple[SyntaxToken, ...]:
    def feature(features: dict[str, str], name: str) -> str:
        value = features.get(name, "")
        return value if "," not in value else ""

    result: list[SyntaxToken] = []
    for sentence in doc.sentences:
        offset = len(result)
        indices = {word.id: offset + i for i, word in enumerate(sentence.words)}
        spans = {word.id: (token.start_char, token.end_char)
                 for token in sentence.tokens for word in token.words}
        for word in sentence.words:
            start, end = word.start_char, word.end_char
            if start is None or end is None:
                start, end = spans[word.id]
            if not isinstance(start, int) or not isinstance(end, int):
                raise ValueError("Missing original token offsets")
            features = dict(item.split("=", 1) for item in (word.feats or "").split("|") if "=" in item)

            if not word.upos or not word.deprel or word.head is None:
                raise ValueError("Missing POS or dependency annotation")
            result.append(SyntaxToken(
                indices[word.id], start, end, text[start:end], word.lemma or "",
                word.upos, word.xpos or "", feature(features, "VerbForm"), feature(features, "Mood"),
                feature(features, "Tense"), indices[word.id] if word.head == 0 else indices[word.head],
                word.deprel, feature(features, "Aspect"),
            ))
    if text.strip() and not result:
        raise ValueError("Missing token annotation")
    return tuple(result)


def validate_tokens(text: str, tokens: tuple[SyntaxToken, ...]) -> None:
    """Require an exact-span dependency forest, allowing sentence-local roots."""
    indexed = {token.i: token for token in tokens}
    if len(indexed) != len(tokens) or any(token.head not in indexed for token in tokens):
        raise ValueError("Invalid dependency token indices")
    for token in tokens:
        if not 0 <= token.start < token.end <= len(text) or text[token.start:token.end] != token.text:
            raise ValueError("Parser token offsets do not match the input")
    complete: set[int] = set()
    for token in tokens:
        chain: set[int] = set()
        current = token.i
        while current not in complete:
            if current in chain:
                raise ValueError("Invalid dependency cycle")
            chain.add(current)
            head = indexed[current].head
            if head == current:
                break
            current = head
        complete.update(chain)


def parse_tokens(text: str, model_name: str) -> tuple[SyntaxToken, ...]:
    """Parse locally, preserving exact source spans even for expanded words."""
    with _LOCK:
        model = _model(model_name)
        try:
            doc = model.pipeline(text)
            tokens = (_stanza_tokens(doc, text) if model.runtime == "stanza"
                      else _spacy_tokens(doc, text))
            validate_tokens(text, tokens)
            return tokens
        except Exception as exc:
            raise ValueError(
                f"Local linguistic analysis failed for {model_name!r}: {exc}; no fallback was used"
            ) from exc
