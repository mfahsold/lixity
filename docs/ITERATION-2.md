# Iteration 2 – Verification, Hardening, Finalisation

*Status: completed (v1.4.0, 2026-09-22) · Base: v1.3.1*

This document is the plan, the critical assessment and the stability register
for the second iteration. Every unstable factor is marked with severity,
evidence and mitigation status (fixed in this iteration · documented).

---

## 1. Scope of this iteration

| Area | Task | State |
| :--- | :--- | :--- |
| UI | Centralise all dashboard programming in `lixity.ui` (renderer, components, assets, shim) | done |
| UI | "Show, don't tell": band chart instead of passport table, loading bars, KPI micro-bars, matrix micro-bars, self-dismissing hint | done |
| UI | Micro-interactions: hover/press feedback, animated expand, tooltip fade, reduced-motion guard | done |
| Science | Minimum text length guards for lexical-diversity indices (Bestgen 2024/2025) | done |
| Tests | UI contract test (markup hooks) + label-completeness test (7 languages) | done |
| Packaging | CI job builds a wheel and asserts UI assets/`py.typed` are packaged | done |
| Docs | Stability register (this document) + "Known limitations" in `USAGE.md` | done |
| Release | Screenshots, version 1.4.0, GitHub release, book pin update | done |

---

## 2. Research findings (state of the art)

**Lexical diversity.**
- McCarthy & Jarvis (2010, *Behavior Research Methods* 42:381–392) recommend
  using **MTLD + vocd-D/HD-D + Maas together** – not a single index; each
  captures unique lexical information. Our corpus report follows exactly this
  combination.
- Bestgen (2024/2025, *The Twofold Length Problem*): **all** LD indices are
  sensitive to very short texts; reliable measurement requires minimum text
  lengths (their analyses use a 60-word floor and show instability below it).
  Kyle et al. (2024) confirm: Root TTR and D are not length-reliable;
  **optimized MATTR and MTLD** are. → Our guards (MTLD ≥ 10 tokens) are too
  permissive and are raised in this iteration.
- Recent validation work (2025) shows MATTR and MTLD correlate only weakly
  (≈0.07 in one corpus) – they measure different things (local repetition vs.
  global variation). The UI therefore shows both, side by side.

**Stylometry.**
- Burrows' Delta remains the standard baseline; 2026 work generalises it to
  **Jensen–Shannon Delta** and Rank-Turbulence Delta, and stresses
  *interpretability* of distance metrics. Our chapter divergence is a
  Jensen–Shannon distance with interpretable driver words – in line with this
  direction, but not an authorship-attribution instrument (documented).
- Stylometry is best used as a "complementary, explainable diagnostic"
  (2026), not as a verdict – our self-calibrating, author-centred design
  matches this guidance.

**Accessibility / data visualisation (WCAG 2.2).**
- Colour must never be the only channel (SC 1.4.1, 1.3.3): our heatmap prints
  the numeric z* values, the band chart encodes band/median/outliers by
  position and shape, and every chip reveals tense + value as text on click.
- Non-text contrast ≥ 3:1 (SC 1.4.11), text ≥ 4.5:1 (SC 1.4.3): palette kept
  (blue/orange diverging = colour-blind-safe canonical pair, grey midpoint).
- Target size ≥ 24×24 px (SC 2.5.8): paragraph chips are deliberately dense
  (18 px) – documented exception with keyboard access and click-to-read.
- Diverging scales only with a meaningful midpoint (our chapter mean) ✓.

---

## 3. Critical assessment – stability register

Severity: 🔴 high (can mislead users) · 🟠 medium (can break silently) ·
🟡 low (cosmetic or documented trade-off).

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
| 14 | UI labels architecture | five label packs merged at runtime (base → metric → help → group → layer → ui) | fallback chain is implicit | 🟠 → **fixed**: merge order documented in `docs/ARCHITECTURE.md` + completeness test |

---

## 4. Implementation plan (execution log)

1. **UI centralisation** – `lixity.ui` package (`dashboard.py`, `components.py`,
   `assets/`), `lixity.visualizer` as compatibility shim; imports in `api`,
   `cli` and the book adapter moved to `lixity.ui`. ✅
2. **Show, don't tell** – passport band chart, dimension loading bars, KPI
   proportion bars, matrix micro-bars, self-dismissing hint, heatmap
   explanation moved into tooltips. ✅ (markup + CSS)
3. **Micro-interactions (JS)** – micro-hint fade after first interaction,
   layer guidance as tooltip on the legend title, heatmap row/column
   highlight on hover, keep Escape/focus behaviour. ✅
4. **LD guards** – raise minimum token counts, update help texts (7 languages),
   tests. ✅
5. **Contract & completeness tests** – UI hooks + label packs. ✅
6. **Packaging CI** – wheel build + asset assertion. ✅
7. **Docs** – this register + "Known limitations" in `USAGE.md` + label merge
   order in `docs/AGENTS.md` §3.3. ✅
8. **Release** – screenshots, v1.4.0, GitHub release, book pin `v1.4.0`. ✅

---

## 5. Verification

- `ruff`, `mypy`, 117+ tests green; new tests for guards, contracts, labels.
- Determinism: two renders byte-identical; analysis hash unchanged for the
  reference corpus.
- Visual: screenshots regenerated (`scripts/make_screenshots.py`).
- Book project: 52 adapter tests, dossier audit 0 drift, dashboard idempotent.
