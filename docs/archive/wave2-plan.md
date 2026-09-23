# Wave-2 Implementation Plan

> **Status: completed (2026-09-23).** Archived after integration into
> `style_fingerprint` (`wave2_diagnostics`, schema v3), methods/stability
> docs and the full test suite. Kept for provenance.

## Overview
7 new pure-stdlib statistical functions in `style_fingerprint.py`, following the Wave-1 blueprint:
pure function → types → edge-case defaults → optional FingerprintThresholds field → passport/Config/CLI/UI (where threshold-relevant) → unittest class → METHODS/STABILITY/CHANGELOG.

## Features

### 1. PELT (Pruned Exact Linear Time) – Changepoint Segmentation
- **Purpose**: Detect structural breaks (phase shifts) in chapter-level metric series
- **Function**: `pelt_changepoints(values: list[float], penalty: float | None = None) -> list[int]`
- **Algorithm**: O(n²) exact segmentation with BIC penalty (stdlib-only). Finds indices where the statistical properties of the series change.
- **Edge cases**: n < 3 → [], constant series → [], penalty=None → BIC default (2·log(n))
- **Threshold**: `pelt_penalty` on FingerprintThresholds (optional override of BIC default)

### 2. Mann-Kendall Trend Test
- **Purpose**: Detect monotonic trends in chapter-level metric series
- **Function**: `mann_kendall(values: list[float]) -> tuple[float, float, float] | None`
- **Returns**: (tau, S, p_value) or None if n < 3
- **Algorithm**: Kendall's tau with exact variance (corrected for ties), normal approximation for p
- **Edge cases**: n < 3 → None, constant → (0.0, 0, 1.0)

### 3. Wasserstein + KS Distance
- **Purpose**: Distribution distance of paragraph metrics vs. baseline
- **Functions**:
  - `wasserstein_1d(x: list[float], y: list[float]) -> float` (earth mover's distance, sorted)
  - `ks_2sample(x: list[float], y: list[float]) -> tuple[float, float]` (D statistic, p-value)
- **Edge cases**: empty → 0.0 / (0.0, 1.0)

### 4. Dunning G² (Log-Likelihood Ratio / Keyness)
- **Purpose**: Which words/terms are over-/under-represented in a chapter vs. rest
- **Function**: `dunning_g2(obs_a: int, obs_b: int, total_a: int, total_b: int) -> float`
- **Returns**: G² statistic (chi² 1df, signed for direction)
- **Edge cases**: zeros → 0.0

### 5. Hill Estimator
- **Purpose**: Tail index (power-law exponent) of metric distributions
- **Function**: `hill_estimator(values: list[float], k: int | None = None) -> float | None`
- **Returns**: α̂ (tail index) or None if insufficient data
- **Edge cases**: n < 5 → None, k default = floor(sqrt(n))

### 6. Sn / Qn Robust Scale Estimators
- **Purpose**: Alternative to 1.4826·MAD (Rousseeuw & Croux 1993)
- **Functions**:
  - `sn_estimator(values: list[float]) -> float` (median of medians of |xi - xj|)
  - `qn_estimator(values: list[float]) -> float` (first quartile of |xi - xj|)
- **Edge cases**: n < 2 → 0.0

### 7. Goh–Barabási (Degree Distribution Fitness)
- **Purpose**: Test whether an observed degree sequence fits a power-law / scale-free model
- **Function**: `goh_barabasi_fitness(degrees: list[int]) -> dict[str, float] | None`
- **Returns**: {"exponent": α, "ks_distance": D, "p_value": p} or None
- **Edge cases**: empty / all-same → None

## Integration Points
- All functions: pure, typed, no numpy/scipy
- passport(): new `wave2_diagnostics` section
- passport_text(): summary line for changepoints + trends
- Tests: one TestClass per function with edge cases
- METHODS.md: §11–§17
- STABILITY.md: entries #35–#41
- CHANGELOG: [Unreleased] Added section

## Order of Implementation
1. All 7 functions in style_fingerprint.py
2. Integration into StyleFingerprint (from_metrics, passport)
3. All tests in test_style_fingerprint.py
4. METHODS.md updates
5. STABILITY.md entries
6. CHANGELOG entry
