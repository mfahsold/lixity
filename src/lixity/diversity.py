"""lixity.diversity – length-robust lexical-diversity indices.

Pure, deterministic implementations of the established indices:

- **HD-D** (McCarthy & Jarvis 2010): hypergeometric expected type-token ratio
  of a 42-token draw without replacement from the whole text.
- **MTLD** (McCarthy & Jarvis 2010): mean segment length until TTR drops below
  0.72, forward and backward averaged.
- **MATTR** (Covington & McFall 2010): moving-average TTR over a 50-token window.
- **Maas a²** (Maas 1972): (log N − log V) / (log N)².
- **Yule's K** (Yule 1944): 10^4 · (Σ m² V_m − N) / N².

HD-D, MTLD and Maas use a local short-text policy of at least
:data:`MIN_TOKENS_LD` tokens. MATTR requires a full window; Yule's K returns
zero for empty input. These guards do not establish estimator reliability.
"""

from __future__ import annotations

import math
from collections import Counter

# Local minimum length for HD-D, MTLD and Maas; not a universal validity boundary.
MIN_TOKENS_LD = 100
HD_D_DRAW_SIZE = 42


def hd_d(tokens: list[str], seed: int = 42, min_samples: int = 5) -> float | None:
    """
    HD-D: expected TTR of a 42-token hypergeometric draw (McCarthy & Jarvis 2010).

    Each type contributes its probability of occurring at least once in a draw
    without replacement, divided by 42. Return None below MIN_TOKENS_LD.
    ``seed`` and ``min_samples`` remain accepted for caller compatibility but
    have no effect on this exact calculation.
    """
    value, _ = hd_d_stats(tokens, seed=seed, min_samples=min_samples)
    return value

def hd_d_stats(
    tokens: list[str], seed: int = 42, min_samples: int = 5
) -> tuple[float | None, float]:
    """
    Return (exact HD-D expectation, computational standard error).

    The expectation has no Monte Carlo sampling error, hence the second value
    is zero. It does not estimate uncertainty about a larger population.
    ``seed`` and ``min_samples`` are legacy no-op parameters.
    """
    n = len(tokens)
    if n < MIN_TOKENS_LD:
        return None, 0.0
    # Types with the same frequency have identical draw-presence probabilities.
    frequency_counts = Counter(Counter(tokens).values())
    presence = []
    for frequency, type_count in frequency_counts.items():
        if n - frequency < HD_D_DRAW_SIZE:
            probability = 1.0
        else:
            # P(type absent) = product((N - f - i) / (N - i)), i=0..41.
            # log1p/expm1 retain precision for rare types in long texts.
            log_absence = math.fsum(
                math.log1p(-frequency / (n - i)) for i in range(HD_D_DRAW_SIZE)
            )
            probability = -math.expm1(log_absence)
        presence.append(type_count * probability)
    return math.fsum(presence) / HD_D_DRAW_SIZE, 0.0
def mtld(tokens: list[str], threshold: float = 0.72) -> float | None:
    """
    MTLD: length-invariant lexical diversity (McCarthy & Jarvis 2010).

    Mean length of sequential token runs that maintain TTR >= threshold;
    computed forward and backward then averaged. Returns None below
    ``MIN_TOKENS_LD`` (100) tokens under the local short-text policy and
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

    Mean TTR over sliding windows of ``window`` tokens. None if text is shorter
    than the window. O(N) via an incremental type counter. Comparisons require
    the same window and tokenization; the result is not independent of these choices.
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
