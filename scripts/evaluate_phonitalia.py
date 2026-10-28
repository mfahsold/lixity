"""Compare Italian syllable estimates with an explicitly supplied PhonItalia TSV.

This reports row-level agreement with the lexicon, not phonetic accuracy for
literary text. It does not download or redistribute the source data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from unicodedata import normalize

from lixity.syllables import IT_CLEAN, IT_VOWELS, IT_WEAK, count_it


def experimental_rising_diphthongs(word: str) -> int:
    """Research comparator only; unmarked stress makes this unsafe to deploy.

    Merge an unaccented i/u followed by a/e/o, retaining the production
    counter's existing treatment of other vowel sequences. This improves many
    forms but undercounts common hiatuses; see the aggregate regression count.
    """
    word = IT_CLEAN.sub("", normalize("NFC", word).lower())
    if not word:
        return 0
    count = 0
    i = 0
    while i < len(word):
        if word[i] not in IT_VOWELS:
            i += 1
            continue
        count += 1
        if word[i] in IT_WEAK and i + 1 < len(word) and word[i + 1] in "aeoàèéòó":
            i += 2
        else:
            i += 1
        while i < len(word) and word[i] in IT_WEAK:
            i += 1
    return max(1, count)


def compare_spellings(spellings: dict[str, set[int]]) -> dict[str, object]:
    """Report unique unambiguous word types, partitioned by stable word hash."""
    partitions: dict[str, list[tuple[int, int]]] = {"development": [], "holdout": []}
    ambiguous = 0
    for word, counts in spellings.items():
        if len(counts) != 1:
            ambiguous += 1
            continue
        expected = next(iter(counts))
        digest = hashlib.sha256(word.encode("utf-8")).digest()
        name = "holdout" if int.from_bytes(digest, "big") % 5 == 0 else "development"
        partitions[name].append((abs(count_it(word) - expected),
                                 abs(experimental_rising_diphthongs(word) - expected)))

    def summarize(errors: list[tuple[int, int]]) -> dict[str, object]:
        size = len(errors)
        def measure(index: int) -> dict[str, int | float | None]:
            exact = sum(error[index] == 0 for error in errors)
            absolute_error = sum(error[index] for error in errors)
            return {"exact": exact, "absolute_error_sum": absolute_error,
                    "exact_fraction": exact / size if size else None,
                    "mean_absolute_error": absolute_error / size if size else None}
        return {"forms": size, "baseline": measure(0), "candidate": measure(1),
                "improved": sum(candidate < baseline for baseline, candidate in errors),
                "regressed": sum(candidate > baseline for baseline, candidate in errors)}

    return {
        "partition": "sha256-nfc-lowercase-utf8-modulo-5; zero=holdout",
        "ambiguous_spellings_excluded": ambiguous,
        **{name: summarize(errors) for name, errors in partitions.items()},
    }


def evaluate(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)

    rows = exact = errors = excluded = 0
    spellings: set[str] = set()
    spelling_counts: dict[str, set[int]] = {}
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        if not {"word", "SumSylls"}.issubset(reader.fieldnames or ()):
            raise ValueError("Expected PhonItalia TSV fields word and SumSylls")
        for row in reader:
            word = normalize("NFC", (row.get("word") or "").lower())
            try:
                expected = int(row.get("SumSylls") or "")
            except ValueError:
                excluded += 1
                continue
            if not word.isalpha() or expected < 1:
                excluded += 1
                continue
            difference = abs(count_it(word) - expected)
            rows += 1
            exact += difference == 0
            errors += difference
            spellings.add(word)
            spelling_counts.setdefault(word, set()).add(expected)
    return {
        "source_sha256": digest.hexdigest(),
        "evaluated_rows": rows,
        "unique_spellings": len(spellings),
        "excluded_rows": excluded,
        "exact_rows": exact,
        "absolute_error_sum": errors,
        "exact_fraction": exact / rows if rows else None,
        "mean_absolute_error": errors / rows if rows else None,
        "candidate_comparison": compare_spellings(spelling_counts),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wordforms", type=Path, help="Local PhonItalia 1.10 wordforms TSV")
    args = parser.parse_args()
    print(json.dumps(evaluate(args.wordforms), indent=2))


if __name__ == "__main__":
    main()
