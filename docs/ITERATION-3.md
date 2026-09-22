# Iteration 3 (v1.6.0) – status, notes, drill-down

Scope: coherent dashboard states (component status strip, busy feedback),
free-text work-marker notes, one-click drill-downs from every KPI, the
style-layer v2 colour/ring semantics, and the removal of legacy payload
(`layer_colors`, short layer labels) plus centralised `orjson` serialisation.

## Stability register (continuation of `docs/ITERATION-2.md`)

| # | Component | Instability | Evidence | Mitigation |
| :-- | :--- | :--- | :--- | :--- |
| 15 | Status strip | states derive from file presence/mtime – a restored or clock-skewed file can read "stale" although it is current | no content hash in the status path | 🟡 **documented**: state is advisory; undeterminable components render `unknown`, not a fake `ok` |
| 16 | Marker notes | notes live in an HTML-comment attribute: quotes/newlines must be escaped; very long notes bloat the comment line | `note="…"` in the marker line | 🟠 → **fixed**: escaping on write (round-trip test); **documented** guidance: one short sentence |
| 17 | Drill-down filters | `data-flags` / `data-only` preselect a view filter; users may wonder why rows are hidden | UI state only, data untouched | 🟡 **documented**; the active filter is visible and one click clears it |
| 18 | orjson serialisation | `orjson` rejects non-string dict keys by default – chapter keys are ints in `deviations` | `OPT_NON_STR_KEYS` required | 🟠 → **fixed**: one `_json()` helper used everywhere; round-trip test covers integer chapter keys |
| 19 | Busy states | server actions have latency; without feedback users click twice | action buttons | 🟡 **mitigated**: buttons disable + spinner while running; server-side idempotence remains the actual guard |
| 20 | Layer colour semantics v2 | colour encodes the absolute value span (min–max per dimension), not deviation sign alone | narrow bands would wash out | 🟡 **documented** in legend (min/max values) + `USAGE.md`; the ring (|z| ≥ 1.5) is the second, deviation-specific channel |

## Execution log

1. **Marker notes** – inline note field on marker kinds (`Enter` commits via
   `marker-add` with `note`, `Esc` cancels), labels in 7 languages,
   contract test extended. ✅
2. **Status strip & busy states** – `status_strip()` component, `status`
   parameter in `render_dashboard`, per-component states in the embedding
   UI server, busy spinner on action buttons, labels in 7 languages. ✅
3. **Cleanup** – `layer_colors` and short layer labels removed;
   `_DEFAULT_LABELS` now carries all six packs; zero-value heatmap cells use
   the neutral surface (dark-mode fix). ✅
4. **orjson** – CLI and artifact writers serialise through `_json()`
   (`OPT_NON_STR_KEYS`); dependency floor raised. ✅
5. **Dependencies** – pydantic 2.13.5, rich 15.0.0, orjson 3.12.0 in both
   environments; full test suites green. ✅
6. **Docs & release** – README, `USAGE.md`, `AGENTS.md` §3.4 (DOM hooks),
   GitHub Pages with SEO/JSON-LD, `robots.txt`, `sitemap.xml`, `llms.txt`,
   sample provenance; v1.6.0 release. ✅

## Verification

- `ruff`, `mypy`, **125 tests** green in lixity; **52 tests** green in the
  book project; analysis baseline hash unchanged (`32b91283…`).
- Determinism: dashboard renders byte-identical for unchanged input; book
  export/dashboard idempotent.
- Visual: all 8 screenshots regenerated from the public-domain sample,
  including a demonstration status strip.
- Packaging: wheel CI job unchanged and green.
