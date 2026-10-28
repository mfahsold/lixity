"""Compare French -ent estimates with an explicitly supplied Lexique 4 TSV.

This emits aggregate agreement, not words. Lexique syllable counts follow its
own conventions and are not independent annotations of literary speech.
The candidate that keeps final -ent is experimental and is not shipped.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from unicodedata import normalize

from lixity.syllables import FR_CLEAN, FR_VOWEL_GROUP, count_fr


def evaluate(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    counts: dict[str, set[int]] = {}
    excluded = 0
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        if not {"1_Mot", "26_SyllNb"}.issubset(reader.fieldnames or ()):
            raise ValueError("Expected Lexique 4 TSV fields 1_Mot and 26_SyllNb")
        for row in reader:
            word = normalize("NFC", (row.get("1_Mot") or "").lower())
            try:
                expected = int(row.get("26_SyllNb") or "")
            except ValueError:
                excluded += 1
                continue
            if not word.isalpha() or expected < 1:
                excluded += 1
                continue
            if word.endswith("ent"):
                counts.setdefault(word, set()).add(expected)

    forms = baseline_exact = candidate_exact = baseline_error = candidate_error = 0
    improved = regressed = ambiguous = 0
    for word, values in counts.items():
        if len(values) != 1:
            ambiguous += 1
            continue
        expected = next(iter(values))
        baseline = count_fr(word)
        clean_word = FR_CLEAN.sub("", word)
        # Removing only the existing -ent deduction leaves all other rules as-is.
        candidate = baseline + (len(FR_VOWEL_GROUP.findall(clean_word)) > 1)
        old_error, new_error = abs(baseline - expected), abs(candidate - expected)
        forms += 1
        baseline_exact += old_error == 0
        candidate_exact += new_error == 0
        baseline_error += old_error
        candidate_error += new_error
        improved += new_error < old_error
        regressed += new_error > old_error
    return {
        "source_sha256": digest.hexdigest(),
        "forms": forms,
        "ambiguous_spellings_excluded": ambiguous,
        "excluded_rows": excluded,
        "baseline_exact": baseline_exact,
        "candidate_exact": candidate_exact,
        "baseline_mean_absolute_error": baseline_error / forms if forms else None,
        "candidate_mean_absolute_error": candidate_error / forms if forms else None,
        "improved": improved,
        "regressed": regressed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wordforms", type=Path, help="Local Lexique 4 TSV")
    args = parser.parse_args()
    print(json.dumps(evaluate(args.wordforms), indent=2))


if __name__ == "__main__":
    main()
