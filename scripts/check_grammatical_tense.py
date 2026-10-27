"""Compare explicitly installed language models on synthetic verb-group cases.

This bounded construction check is not a representative accuracy benchmark. No
resources are downloaded. Run with the optional linguistics extra and locally
installed models; the fixture contains only newly written synthetic text.
"""

import argparse
import json
import time
from pathlib import Path

from lixity.grammatical_tense import analyze_verbs, model_identity


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="+", help="Explicit installed local syntax model names")
    args = parser.parse_args()
    fixtures = Path(__file__).resolve().parents[1] / "tests/fixtures"
    reports = []
    for name in args.models:
        identity = model_identity(name)
        language = identity["language"]
        fixture = fixtures / ("german_verb_groups.json" if language == "de" else "multilingual_verb_groups.json")
        cases = [case for case in json.loads(fixture.read_text(encoding="utf-8"))["cases"]
                 if case.get("language", "de") == language]
        start = time.monotonic()
        outcomes = []
        for case in cases:
            groups = analyze_verbs(case["text"], name)
            finite = [g for g in groups if g.reason != "missing_finite"]
            actual = [[g.tense, g.mood] for g in finite] if language == "de" else [g.tense for g in finite]
            expected = case["groups"] if language == "de" else case["tenses"]
            outcomes.append({"text": case["text"], "expected": expected, "actual": actual,
                             "matches": actual == expected,
                             "unresolved": [g.reason for g in groups if g.reason]})
        reports.append({**identity, "comparison": "tense_and_mood" if language == "de" else "tense", "cases": len(cases),
                        "matching_cases": sum(row["matches"] for row in outcomes),
                        "seconds": time.monotonic() - start, "results": outcomes})
    print(json.dumps({"schema_version": "grammatical-tense-check/1", "models": reports}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
