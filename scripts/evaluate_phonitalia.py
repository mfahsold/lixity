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

from lixity.syllables import count_it


def evaluate(path: Path) -> dict[str, int | float | str | None]:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)

    rows = exact = errors = excluded = 0
    spellings: set[str] = set()
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        if not {"word", "SumSylls"}.issubset(reader.fieldnames or ()):
            raise ValueError("Expected PhonItalia TSV fields word and SumSylls")
        for row in reader:
            word = (row.get("word") or "").lower()
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
    return {
        "source_sha256": digest.hexdigest(),
        "evaluated_rows": rows,
        "unique_spellings": len(spellings),
        "excluded_rows": excluded,
        "exact_rows": exact,
        "absolute_error_sum": errors,
        "exact_fraction": exact / rows if rows else None,
        "mean_absolute_error": errors / rows if rows else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wordforms", type=Path, help="Local PhonItalia 1.10 wordforms TSV")
    args = parser.parse_args()
    print(json.dumps(evaluate(args.wordforms), indent=2))


if __name__ == "__main__":
    main()
