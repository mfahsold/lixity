#!/usr/bin/env python3
"""Benchmark pipeline stages on book-scale sample manuscripts.

Measures wall-clock per stage, peak RSS, and deterministic result SHA-256
in support of docs/RUST_EVALUATION_RFC.md.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import platform
import resource
import statistics
import time
from pathlib import Path
from typing import Any

import orjson

from lixity.analyzer import CorpusAnalyzer
from lixity.dialogue import dialogue_report
from lixity.motifs import motif_report
from lixity.pacing import pacing_report
from lixity.pipeline import (
    fingerprint_document,
    profile_document,
    resolve_document_config,
)
from lixity.scenes import scene_report_for_display
from lixity.showing import showing_report
from lixity.style_fingerprint import FingerprintThresholds

DEFAULT_CORPUS = (
    ("samples/pride-and-prejudice.md", "en"),
    ("samples/effi-briest.md", "de"),
)


def _digest(payload: Any) -> str:
    raw = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS | orjson.OPT_NON_STR_KEYS, default=str)
    return hashlib.sha256(raw).hexdigest()[:16]


def benchmark_manuscript(path: Path, language: str, iterations: int) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    config, _ = resolve_document_config(text, language=language)
    thresholds = FingerprintThresholds()

    stage_names = (
        "analyzer",
        "profile",
        "fingerprint",
        "dialogue",
        "pacing",
        "motifs",
        "showing",
        "scenes",
        "total",
    )
    timings: dict[str, list[float]] = {name: [] for name in stage_names}
    digests: dict[str, str] = {}
    word_count = 0

    for _ in range(iterations):
        t0 = time.perf_counter()
        metrics = CorpusAnalyzer(config, sample_text=text).analyze_text(text)
        t1 = time.perf_counter()

        evidence: dict[int, Any] = {}
        paragraphs, chapters = profile_document(text, config, thresholds, evidence=evidence)
        t2 = time.perf_counter()

        fp = fingerprint_document(text, config, thresholds, metrics)
        t3 = time.perf_counter()

        dlg = dialogue_report(text, config).to_dict()
        t4 = time.perf_counter()

        pac = pacing_report(text, config).to_dict()
        t5 = time.perf_counter()

        mot = motif_report(text, config=config).to_dict()
        t6 = time.perf_counter()

        shw = showing_report(text, config, metrics=metrics).to_dict()
        t7 = time.perf_counter()

        scn = scene_report_for_display(text, config, None, premeasured_chapters=metrics.chapters)
        t8 = time.perf_counter()

        timings["analyzer"].append((t1 - t0) * 1000.0)
        timings["profile"].append((t2 - t1) * 1000.0)
        timings["fingerprint"].append((t3 - t2) * 1000.0)
        timings["dialogue"].append((t4 - t3) * 1000.0)
        timings["pacing"].append((t5 - t4) * 1000.0)
        timings["motifs"].append((t6 - t5) * 1000.0)
        timings["showing"].append((t7 - t6) * 1000.0)
        timings["scenes"].append((t8 - t7) * 1000.0)
        timings["total"].append((t8 - t0) * 1000.0)

        word_count = metrics.raw_words
        if not digests:
            digests = {
                "metrics": _digest(metrics.model_dump()),
                "paragraphs": _digest([dataclasses.asdict(p) for p in paragraphs]),
                "chapters": _digest([dataclasses.asdict(c) for c in chapters]),
                "fingerprint": _digest(dataclasses.asdict(fp)),
                "evidence": _digest(evidence),
                "dialogue": _digest(dlg),
                "pacing": _digest(pac),
                "motifs": _digest(mot),
                "showing": _digest(shw),
                "scenes": _digest(scn),
            }

    return {
        "file": str(path),
        "language": language,
        "chars": len(text),
        "words": word_count,
        "median_ms": {name: round(statistics.median(vals), 2) for name, vals in timings.items()},
        "digests": digests,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Lixity pipeline stages.")
    parser.add_argument("--iterations", type=int, default=3, help="Runs per manuscript")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    results = [
        benchmark_manuscript(Path(rel_path), lang, max(1, args.iterations))
        for rel_path, lang in DEFAULT_CORPUS
        if Path(rel_path).exists()
    ]
    rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    payload = {
        "python": platform.python_version(),
        "machine": platform.machine(),
        "peak_rss_mb": round(rss_kb / 1024.0, 2),
        "iterations": max(1, args.iterations),
        "results": results,
    }
    if args.json:
        print(orjson.dumps(payload, option=orjson.OPT_INDENT_2).decode("utf-8"))
        return 0

    print(f"Python {payload['python']} ({payload['machine']}), peak RSS {payload['peak_rss_mb']} MB")
    for item in results:
        print(f"\n=== {item['file']} ({item['chars']} chars, {item['words']} words) ===")
        for stage, ms in item["median_ms"].items():
            print(f"  {stage:<12} {ms:7.2f} ms")
        print("  digests:", " ".join(f"{k}={v}" for k, v in item["digests"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
