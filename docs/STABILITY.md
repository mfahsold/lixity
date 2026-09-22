# Stability & known limitations

Research basis, known limitations and every documented trade-off in one
place — kept in the present tense, no session logs.

Severity: 🔴 high (can mislead users) · 🟠 medium (can break silently) ·
🟡 low (cosmetic or documented trade-off).

## 1. Research findings (state of the art)

**Lexical diversity.**
- McCarthy & Jarvis (2010, *Behavior Research Methods* 42:381–392) recommend
  using **MTLD + vocd-D/HD-D + Maas together** – not a single index; each
  captures unique lexical information. The corpus report follows exactly this
  combination.
- Bestgen (2024/2025, *The Twofold Length Problem*): **all** LD indices are
  sensitive to very short texts; reliable measurement requires minimum text
  lengths (their analyses use a 60-word floor). Kyle et al. (2024) confirm:
  Root TTR and D are not length-reliable; **optimized MATTR and MTLD** are.
- MATTR and MTLD correlate only weakly (≈0.07 in one corpus) – they measure
  different things (local repetition vs. global variation); the UI shows
  both, side by side.

**Stylometry.**
- Burrows' Delta remains the standard baseline; 2026 work generalises it to
  **Jensen–Shannon Delta** and Rank-Turbulence Delta and stresses
  *interpretability*. The chapter divergence is a Jensen–Shannon distance
  with interpretable driver words – in line with this direction, but not an
  authorship-attribution instrument (documented).
- Stylometry is best used as a "complementary, explainable diagnostic"
  (2026), not as a verdict – the self-calibrating, author-centred design
  matches this guidance.

**Accessibility / data visualisation (WCAG 2.2).**
- Colour must never be the only channel (SC 1.4.1, 1.3.3): the heatmap
  prints the numeric z* values, the band chart encodes band/median/outliers
  by position and shape, every chip reveals tense + value as text on click.
- Non-text contrast ≥ 3:1 (SC 1.4.11), text ≥ 4.5:1 (SC 1.4.3): palette kept
  (blue/orange diverging = colour-blind-safe canonical pair, grey midpoint).
- Target size ≥ 24×24 px (SC 2.5.8): paragraph chips are deliberately dense
  (18 px) – documented exception with keyboard access and click-to-read.
- Diverging scales only with a meaningful midpoint (the chapter mean).

## 2. Stability register

| # | Component | Instability | Evidence | Mitigation |
| :-- | :--- | :--- | :--- | :--- |
| 1 | Dashboard JS | no automated JS test; DOM hooks (ids/classes) are an implicit contract | renaming a class breaks interactions silently | 🟠 → **fixed**: UI-contract test asserts every hook used by `dashboard.js` exists in the rendered HTML |
| 2 | Label packs | missing translations fall back to English silently | untranslated UI goes unnoticed | 🟠 → **fixed**: completeness test over the 7 languages for a required key set |
| 3 | LD indices on short texts | literature shows unreliability below ~60 words | Bestgen 2024; Kyle et al. 2024 | 🔴 → **fixed**: MTLD ≥ 100 tokens, Maas ≥ 100, MATTR ≥ window (50); otherwise `null` + help texts updated |
| 4 | Style fingerprint with few chapters | median/MAD unstable for n < 5; dimensions need spread | baseline sigma = 0 for single chapters | 🟠 → **fixed** (v1.3.0): panels hidden when no measurable spread; **documented** minimum chapters |
| 5 | Heuristic syllable counting | ±5–10 % error, language-specific rules | no gold-standard corpus in-repo | 🟡 **documented**; used only as a relative signal, formula names shown |
| 6 | Tense patterns | curated alternations + productive `-te`/`-ed` have FP/FN on ambiguous forms | stoplists documented; `read` fix in v1.3.0 | 🟡 **documented**; dominance is a heuristic, not ground truth |
| 7 | Packaging | a wheel could miss `ui/assets/*` or `py.typed` | config exists, never verified in CI | 🟠 → **fixed**: CI job builds a wheel and asserts assets + typing marker are inside |
| 8 | Book hook / venv | fallback `python3` without lixity breaks the hook | `pyproject` pin + `.venv` | 🟡 **documented** in book `docs/ARCHITECTURE.md`; hook prefers `.venv/bin/python` |
| 9 | PDF/EPUB exports | depend on system Cairo/Pango; not unit-tested | tests deliberately renderer-free | 🟡 mitigated by the pre-push hook running `export_all.py` (smoke) |
| 10 | Dashboard size | ~2 MB HTML for 95k words, linear growth | per-paragraph payload | 🟡 **documented**; future option: JSON payload + client render |
| 11 | Cross-machine determinism | float last bits may differ across platforms/Python versions | `math.log` summation order | 🟡 **documented**: byte-identical on the same interpreter; in-process determinism is tested |
| 12 | NDA store | `nda/` is gitignored; only the off-site backup covers it | data loss if backup fails | 🟡 **documented**; backup includes `nda/`; hook warns when backup is skipped |
| 13 | Chip target size | 18 px strips below WCAG 2.5.8 (24 px) | deliberate density | 🟡 **documented** exception (keyboard + click-to-read + hover growth) |
| 14 | UI labels architecture | label packs merged at runtime (base → metric → help → group → layer → ui) | fallback chain is implicit | 🟠 → **fixed**: merge order documented in `docs/AGENTS.md` §3.3 + completeness test |
| 15 | Status strip | states derive from file presence/mtime – a restored or clock-skewed file can read "stale" although it is current | no content hash in the status path | 🟡 **documented**: state is advisory; undeterminable components render `unknown`, not a fake `ok` |
| 16 | Marker notes | notes live in an HTML-comment attribute: quotes/newlines must be escaped; very long notes bloat the comment line | `note="…"` in the marker line | 🟠 → **fixed**: escaping on write (round-trip test); **documented** guidance: one short sentence |
| 17 | Drill-down filters | `data-flags` / `data-only` preselect a view filter; users may wonder why rows are hidden | UI state only, data untouched | 🟡 **documented**; the active filter is visible and one click clears it |
| 18 | orjson serialisation | `orjson` rejects non-string dict keys by default – chapter keys are ints in `deviations` | `OPT_NON_STR_KEYS` required | 🟠 → **fixed**: one `_json()` helper used everywhere; round-trip test covers integer chapter keys |
| 19 | Busy states | server actions have latency; without feedback users click twice | action buttons | 🟡 **mitigated**: buttons disable + spinner while running; server-side idempotence remains the actual guard |
| 20 | Layer colour semantics | colour encodes the absolute value span (min–max per dimension), not deviation sign alone | narrow bands would wash out | 🟡 **documented** in the legend (min/max values) + `USAGE.md`; the ring (|z| ≥ 1.5) is the second, deviation-specific channel |
