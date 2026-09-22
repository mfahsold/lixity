"""lixity.diversity – length-robust lexical-diversity indices.

Pure, deterministic implementations of the established indices:

- **HD-D** (McCarthy & Jarvis 2010): mean type-variety of 42 random samples of
  35 consecutive tokens (fixed seed), with a plug-in standard error.
- **MTLD** (McCarthy & Jarvis 2010): mean segment length until TTR drops below
  0.72, forward and backward averaged.
- **MATTR** (Covington & McFall 2010): moving-average TTR over a 50-token window.
- **Maas a²** (Maas 1972): (log N − log V) / (log N)².
- **Yule's K** (Yule 1944): 10^4 · (Σ m² V_m − N) / N².

Short-text guards follow Bestgen (2024/2025): every index returns ``None``
below :data:`MIN_TOKENS_LD` tokens instead of an unreliable value.
"""

from __future__ import annotations

import math
import random
from collections import Counter

# Minimum token count for length-sensitive lexical-diversity indices
# (Bestgen 2024/2025: all LD indices are unreliable on very short texts).
MIN_TOKENS_LD = 100


def hd_d(tokens: list[str], seed: int = 42, min_samples: int = 5) -> float | None:
    """
    HD-D: length-robust lexical diversity (McCarthy & Jarvis 2010).

    Mean of the type-variety of 42 random samples of 35 consecutive tokens;
    variety per sample = 1 - sum(c_t*(c_t-1)) / (n*(n-1)).
    Deterministic via fixed seed; returns None for texts too short for
    ``min_samples`` disjoint windows (no reliable statement).
    """
    value, _ = hd_d_stats(tokens, seed=seed, min_samples=min_samples)
    return value

def hd_d_stats(
    tokens: list[str], seed: int = 42, min_samples: int = 5
) -> tuple[float | None, float]:
    """
    HD-D with its estimation uncertainty: returns (value, standard error).

    The standard error is the sample standard deviation of the up to 42
    sample diversities divided by sqrt(#samples) – the documented plug-in
    estimator of the HD-D mean.
    """
    n = len(tokens)
    sample_size = 35
    if n < sample_size * min_samples:
        return None, 0.0
    max_samples = min(42, n // sample_size)
    rng = random.Random(seed)  # noqa: S311 – deterministic sampling, not cryptography
    starts = sorted(rng.sample(range(n - sample_size + 1), max_samples))
    diversities = []
    for s in starts:
        sample = tokens[s : s + sample_size]
        repeat = sum(c * (c - 1) for c in Counter(sample).values())
        diversities.append(1.0 - repeat / (sample_size * (sample_size - 1)))
    mean = sum(diversities) / len(diversities)
    if len(diversities) < 2:
        return mean, 0.0
    variance = sum((d - mean) ** 2 for d in diversities) / (len(diversities) - 1)
    return mean, math.sqrt(variance) / math.sqrt(len(diversities))
def mtld(tokens: list[str], threshold: float = 0.72) -> float | None:
    """
    MTLD: length-invariant lexical diversity (McCarthy & Jarvis 2010).

    Mean length of sequential token runs that maintain TTR >= threshold;
    computed forward and backward then averaged. Returns None below
    ``MIN_TOKENS_LD`` (100) tokens – Bestgen (2024/2025) shows that all
    lexical-diversity indices are unreliable on very short texts – and
    when no factor completes (all-unique token sequences).
    """
    n = len(tokens)
    if n < MIN_TOKENS_LD:
        return None

    def _factors(seq: list[str]) -> float:
        factors = 0.0
        types: set[str] = set()
        seg_len = 0
        for tok in seq:
            types.add(tok)
            seg_len += 1
            ttr = len(types) / seg_len
            if ttr <= threshold:
                factors += 1.0
                types.clear()
                seg_len = 0
        if seg_len > 0:
            ttr = len(types) / seg_len
            factors += (1.0 - ttr) / (1.0 - threshold)
        return factors

    fwd = _factors(tokens)
    bwd = _factors(tokens[::-1])
    total_factors = (fwd + bwd) / 2.0
    if total_factors <= 0.0:
        return None
    return n / total_factors
def mattr(tokens: list[str], window: int = 50) -> float | None:
    """
    MATTR: moving-average type-token ratio (Covington & McFall 2010).

    Mean TTR over sliding windows of ``window`` tokens – the only index
    shown to be stable across all text lengths. None if text is shorter
    than the window. O(N) via an incremental type counter.
    """
    n = len(tokens)
    if n < window:
        return None
    counts: Counter[str] = Counter(tokens[:window])
    distinct = len(counts)
    total = distinct
    for i in range(window, n):
        leaving = tokens[i - window]
        counts[leaving] -= 1
        if counts[leaving] == 0:
            del counts[leaving]
            distinct -= 1
        entering = tokens[i]
        if counts[entering] == 0:
            distinct += 1
        counts[entering] += 1
        total += distinct
    windows = n - window + 1
    return total / (window * windows)
def yules_k(tokens: list[str]) -> float:
    """Yule's characteristic K = 10^4 * (Σ m² V_m − N) / N² (Yule 1944).

    0.0 for empty input or all-unique tokens (no repetition).
    """
    n = len(tokens)
    if n == 0:
        return 0.0
    counts = Counter(tokens)
    m2 = sum(c * c for c in counts.values())
    return 10000.0 * (m2 - n) / (n * n)
def maas_a2(n_tokens: int, v_types: int) -> float | None:
    """Maas a² = (log N − log V) / (log N)² – lower = more diverse (Maas 1972).

    Requires ``MIN_TOKENS_LD`` tokens; shorter texts return None.
    """
    if n_tokens < MIN_TOKENS_LD or v_types <= 1:
        return None
    log_n = math.log10(n_tokens)
    log_v = math.log10(v_types)
    return (log_n - log_v) / (log_n**2)
