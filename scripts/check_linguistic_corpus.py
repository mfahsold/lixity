"""Check local parser token features against an explicitly supplied UD test file.

No downloads occur. This is a bounded feature check, not a verb-group tense
accuracy benchmark. Corpus provenance labels are caller-supplied assertions;
the SHA256 identifies the actual bytes. Unknown predictions, parser failures
and alignment misses remain in eligible-feature denominators.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Any

from lixity.linguistic_models import model_identity, parse_tokens


@dataclass(frozen=True)
class GoldWord:
    identifier: int
    form: str
    lemma: str
    pos: str
    features: dict[str, str]
    start: int
    end: int


@dataclass(frozen=True)
class GoldSentence:
    sent_id: str
    text: str
    words: tuple[GoldWord, ...]
    source_error: str = ""


def _features(value: str) -> dict[str, str]:
    return dict(item.split("=", 1) for item in value.split("|") if "=" in item)


def _sentence(lines: list[str], number: int) -> GoldSentence:
    metadata: dict[str, str] = {}
    rows: list[list[str]] = []
    for line in lines:
        if line.startswith("#"):
            if " = " in line:
                key, value = line[1:].strip().split(" = ", 1)
                metadata[key] = value
            continue
        fields = line.split("\t")
        if len(fields) != 10:
            raise ValueError("CoNLL-U records require 10 tab-separated fields")
        if "." in fields[0]:
            continue  # Empty nodes do not occur in the original surface text.
        rows.append(fields)
    surfaces: list[tuple[list[int], str, bool]] = []
    covered: set[int] = set()
    words: list[list[str]] = []
    for fields in rows:
        identifier = fields[0]
        if "-" in identifier:
            first, last = map(int, identifier.split("-"))
            if first >= last or first < 1:
                raise ValueError("Invalid multiword token range")
            ids = list(range(first, last + 1))
            surfaces.append((ids, fields[1], "SpaceAfter=No" in fields[9].split("|")))
            covered.update(ids)
        else:
            i = int(identifier)
            words.append(fields)
            if i not in covered:
                surfaces.append(([i], fields[1], "SpaceAfter=No" in fields[9].split("|")))
    ids = [int(row[0]) for row in words]
    if len(set(ids)) != len(ids) or any(i < 1 for i in ids):
        raise ValueError("Invalid or duplicate word identifiers")
    if any(i not in ids for i in covered):
        raise ValueError("Multiword token range has missing word records")
    text = metadata.get("text")
    if text is None:
        text = "".join(surface + ("" if no_space else " ")
                       for _, surface, no_space in surfaces).rstrip()
    cursor = 0
    spans: dict[int, tuple[int, int]] = {}
    source_error = ""
    for indices, surface, _ in surfaces:
        start = text.find(surface, cursor)
        if start < 0 or text[cursor:start].strip():
            source_error = "surface_text_mismatch"
            break
        end = start + len(surface)
        for i in indices:
            spans[i] = start, end
        cursor = end
    if text[cursor:].strip():
        source_error = "surface_text_mismatch"
    gold = tuple(GoldWord(int(row[0]), row[1], row[2], row[3], _features(row[5]),
                          *spans.get(int(row[0]), (-1, -1))) for row in words)
    return GoldSentence(metadata.get("sent_id", f"generated-{number}"), text, gold, source_error)


def read_conllu(text: str) -> Iterator[GoldSentence]:
    """Read surface spans without normalizing the authoritative # text field."""
    lines: list[str] = []
    number = 0
    for line in [*text.splitlines(), ""]:
        if line.strip():
            lines.append(line)
        elif lines:
            number += 1
            yield _sentence(lines, number)
            lines = []


def check_corpus(path: Path, language: str, model: str, *, limit: int,
                 provenance: dict[str, str]) -> dict[str, Any]:
    """Compare exact aligned finite-word features, keeping exclusions visible."""
    if limit < 1:
        raise ValueError("Sentence limit must be positive")
    identity = model_identity(model)
    if identity.get("language") != language:
        raise ValueError("Selected model language does not match the corpus language")
    data = path.read_bytes()
    sentences = list(islice(read_conllu(data.decode("utf-8")), limit))
    if not sentences:
        raise ValueError("Corpus contains no sentences")
    metrics: dict[str, dict[str, Any]] = {
        name: {"eligible": 0, "compared": 0, "correct": 0, "missing_prediction": 0}
               for name in ("POS", "Lemma", "VerbForm", "Mood", "Tense")}
    report: dict[str, Any] = {
        "schema_version": "linguistic-corpus-check/1",
        "benchmark_kind": "token_features_not_verb_group_tense",
        "selection": "first_n_sentences_in_file_order",
        "provenance": dict(provenance), "provenance_status": "caller_supplied",
        "corpus_sha256": hashlib.sha256(data).hexdigest(), "language": language,
        "model_identity": identity, "sentence_limit": limit,
        "sentences_selected": len(sentences), "sentences_parsed": 0,
        "source_alignment_failures": 0, "parse_failures": 0, "alignment_misses": 0,
        "gold_verb_tokens": 0, "gold_finite_tokens": 0, "gold_nonfinite_tokens": 0,
        "gold_nonindicative_or_unknown_mood": 0, "missing_gold_finiteness": 0,
        "metrics": metrics, "issues": [],
        "limitations": [
            "UD morphology is token-level; no gold verb-group tense score is inferred.",
            "POS and lemma are compared on gold finite verbs; Tense requires gold Mood=Ind.",
            "Many-to-many source spans, including expanded MWTs, are unscored alignment misses.",
            "Domain, annotation conversion and training overlap limit interpretation.",
        ],
    }
    missing: Counter[str] = Counter()
    for sentence in sentences:
        eligible: list[tuple[GoldWord, dict[str, str]]] = []
        for word in sentence.words:
            if word.pos not in ("VERB", "AUX"):
                continue
            report["gold_verb_tokens"] += 1
            for feature in ("VerbForm", "Mood", "Tense"):
                if not word.features.get(feature) or "," in word.features[feature]:
                    missing[feature] += 1
            form = word.features.get("VerbForm", "")
            if form != "Fin":
                report["gold_nonfinite_tokens" if form and "," not in form
                       else "missing_gold_finiteness"] += 1
                continue
            report["gold_finite_tokens"] += 1
            wanted = {"POS": word.pos, "VerbForm": "Fin"}
            if word.lemma != "_":
                wanted["Lemma"] = word.lemma
            else:
                missing["Lemma"] += 1
            mood = word.features.get("Mood", "")
            if mood and "," not in mood:
                wanted["Mood"] = mood
            if mood == "Ind":
                tense = word.features.get("Tense", "")
                if tense and "," not in tense:
                    wanted["Tense"] = tense
            else:
                report["gold_nonindicative_or_unknown_mood"] += 1
            for name in wanted:
                metrics[name]["eligible"] += 1
            eligible.append((word, wanted))
        if sentence.source_error:
            report["source_alignment_failures"] += 1
            report["issues"].append({"sent_id": sentence.sent_id, "kind": sentence.source_error})
            continue
        try:
            predicted = parse_tokens(sentence.text, model)
        except ValueError as exc:
            report["parse_failures"] += 1
            report["issues"].append({"sent_id": sentence.sent_id, "kind": "parse_failure",
                                     "exception": type(exc).__name__})
            continue
        report["sentences_parsed"] += 1
        by_span: dict[tuple[int, int], list[Any]] = defaultdict(list)
        gold_counts = Counter((word.start, word.end) for word in sentence.words)
        for token in predicted:
            by_span[token.start, token.end].append(token)
        for word, wanted in eligible:
            span = word.start, word.end
            aligned = by_span[span]
            if len(aligned) != 1 or gold_counts[span] != 1:
                report["alignment_misses"] += 1
                report["issues"].append({"sent_id": sentence.sent_id, "kind": "alignment_miss",
                                         "word_id": word.identifier})
                continue
            token = aligned[0]
            actual = {"POS": token.pos, "Lemma": token.lemma, "VerbForm": token.form,
                      "Mood": token.mood, "Tense": token.tense}
            for name, value in wanted.items():
                metrics[name]["compared"] += 1
                if not actual[name]:
                    metrics[name]["missing_prediction"] += 1
                elif actual[name] == value:
                    metrics[name]["correct"] += 1
    for metric in metrics.values():
        metric["match_rate_all_eligible"] = (metric["correct"] / metric["eligible"]
                                             if metric["eligible"] else None)
    report["missing_gold_features"] = dict(missing)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conllu", type=Path, required=True)
    parser.add_argument("--language", choices=("de", "en", "fr", "es", "it", "pt", "nl"), required=True)
    parser.add_argument("--model", required=True, help="Explicit installed local model; never downloaded")
    parser.add_argument("--limit", type=int, default=100)
    for label in ("corpus", "release", "license", "source"):
        parser.add_argument(f"--{label}", required=True, help="Caller-verified provenance label")
    args = parser.parse_args()
    try:
        report = check_corpus(args.conllu, args.language, args.model, limit=args.limit,
                              provenance={label: getattr(args, label)
                                          for label in ("corpus", "release", "license", "source")})
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
