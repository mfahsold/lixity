"""lixity.visualizer – Minimalist, self-contained single-file HTML dashboard.

Renders an interactive stylometric report combining KPI cards, sentence rhythm bars,
diverging z-score heatmap, style passport, latent dimensions, chapter map,
and editor-visible work markers with floating tooltips.
"""

import html
from collections.abc import Mapping, Sequence
from typing import Any

from .language_data import EN_LABELS, HELP_TEXTS, METRIC_LABELS
from .style_fingerprint import FEATURES, LAYER_FEATURES, layer_colors, z_color
from .style_profile import (
    TENSE_MIXED,
    TENSE_PAST,
    TENSE_PRESENT,
    ChapterProfile,
    ParagraphProfile,
)

_CSS = """\
:root {
  --bg: #f8f9fa;
  --surface: #ffffff;
  --fg: #1d2129;
  --muted: #656d78;
  --line: #e6e9ee;
  --accent: #2b5c8f;
  --accent-light: #eef3f9;
  --present: #2d8664;
  --past: #b57635;
  --mixed: #70638e;
  --neutral: #d8dee6;
  --flag: #c0392b;
  --radius: 8px;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
body {
  margin: 0;
  padding: 2.25rem 1.5rem 4rem;
  background: var(--bg);
  color: var(--fg);
  font: 14.5px/1.55 var(--font);
  -webkit-font-smoothing: antialiased;
}
.page { max-width: 72rem; margin: 0 auto; }
h1 {
  font-size: 1.45rem;
  font-weight: 650;
  margin: 0 0 .25rem;
  letter-spacing: -.02em;
}
h2 {
  font-size: .92rem;
  font-weight: 650;
  letter-spacing: -.01em;
  margin: 0;
}
.sub, .hint { color: var(--muted); font-size: .82rem; margin: 0; }
.sub { margin-bottom: .15rem; }

/* --- Panels & Cards --------------------------------------------------- */
.panel {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.25rem 1.45rem;
  margin: 1rem 0;
  box-shadow: 0 1px 2px rgba(0, 0, 0, .02);
}
.panel h2 {
  font-size: .92rem;
  font-weight: 650;
  letter-spacing: -.01em;
  margin: 0 0 .85rem;
  color: var(--fg);
}
.panel .hint { margin: -.35rem 0 .85rem; }

/* --- Key figures (KPI grid) ------------------------------------------- */
.kpis {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(8.8rem, 1fr));
  gap: .55rem;
  margin: 1.15rem 0;
}
.kpi {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: .65rem .85rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 4.2rem;
  transition: border-color .15s ease;
}
.kpi:hover { border-color: var(--accent); }
.kpi b {
  display: block;
  font-size: 1.25rem;
  font-weight: 650;
  letter-spacing: -.02em;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.kpi span {
  color: var(--muted);
  font-size: .72rem;
  line-height: 1.35;
  margin-top: .25rem;
}

/* --- Sentence-length architecture ------------------------------------- */
.dist { display: grid; gap: .5rem; }
.dist .row {
  display: grid;
  grid-template-columns: 8.5rem 1fr 7.5rem;
  align-items: center;
  gap: .75rem;
  font-size: .83rem;
}
.dist .bar { height: 6px; background: var(--line); border-radius: 999px; overflow: hidden; }
.dist .bar i { display: block; height: 100%; background: var(--accent); }
.dist .val { text-align: right; color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }

/* --- Toolbar ---------------------------------------------------------- */
.toolbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  flex-wrap: wrap;
  gap: 1.25rem;
  align-items: center;
  margin: 1.25rem 0 .5rem;
  padding: .6rem .25rem;
  background: var(--bg);
  border-bottom: 1px solid var(--line);
  font-size: .83rem;
}
.toolbar label { display: inline-flex; gap: .45rem; align-items: center; cursor: pointer; }
.legend { display: inline-flex; flex-wrap: wrap; gap: 1rem; color: var(--muted); font-size: .78rem; }
.swatch { display: inline-block; width: .6rem; height: .6rem; border-radius: 2px; margin-right: .3rem; vertical-align: -1px; }
.totop { margin-left: auto; font-size: .8rem; color: var(--muted); text-decoration: none; }
.totop:hover { color: var(--fg); }

/* --- Chapter map ------------------------------------------------------ */
.chapter {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: .85rem 1.15rem;
  margin: .65rem 0;
  transition: border-color .15s ease;
}
.chapter-head {
  display: flex;
  flex-wrap: wrap;
  gap: .4rem 1rem;
  align-items: baseline;
  justify-content: space-between;
}
.chapter-head h2 { font-size: .92rem; font-weight: 650; margin: 0; }
.chapter-head .meta { color: var(--muted); font-size: .78rem; font-variant-numeric: tabular-nums; }
.strip { display: flex; gap: 2px; margin: .65rem 0 0; }
.chip {
  border: 0;
  padding: 0;
  height: 18px;
  min-width: 7px;
  border-radius: 3px;
  background: var(--neutral);
  cursor: pointer;
  opacity: .9;
  touch-action: manipulation;
  transition: opacity .1s ease;
}
.chip:hover, .chip:focus-visible, .chip.active {
  opacity: 1;
  outline: 2px solid var(--fg);
  outline-offset: 1px;
}
.chip.tense-present { background: var(--present); }
.chip.tense-past { background: var(--past); }
.chip.tense-mixed { background: var(--mixed); }
.chip.sev-2 { box-shadow: inset 0 -3px 0 var(--flag); }
.chip.sev-3 { box-shadow: inset 0 0 0 2px var(--flag); }

/* --- Expandable paragraph preview ------------------------------------- */
.ptext {
  display: none;
  margin: .65rem 0 0;
  padding: .8rem 1rem;
  border-left: 3px solid var(--accent);
  background: var(--bg);
  border-radius: 0 var(--radius) var(--radius) 0;
}
.ptext.open { display: block; }
.ptext .anchor { color: var(--muted); font-size: .76rem; font-weight: 600; font-variant-numeric: tabular-nums; }
.ptext .stats { color: var(--muted); font-size: .75rem; margin: .1rem 0 .45rem; line-height: 1.4; }
.ptext p { margin: .4rem 0 0; font-size: .88rem; line-height: 1.6; }
.ptext .row { display: flex; flex-wrap: wrap; gap: .35rem; margin-top: .45rem; }

/* --- Tables ----------------------------------------------------------- */
table { width: 100%; border-collapse: collapse; font-size: .82rem; }
th, td { text-align: left; padding: .45rem .6rem; border-bottom: 1px solid var(--line); vertical-align: top; }
th {
  color: var(--muted);
  font-weight: 600;
  text-transform: uppercase;
  font-size: .67rem;
  letter-spacing: .06em;
  background: var(--surface);
}
tbody tr:hover { background: rgba(0, 0, 0, .015); }
tbody tr:last-child td { border-bottom: 0; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }

/* --- Style heatmap ---------------------------------------------------- */
.heatmap-wrap {
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  margin: .65rem 0;
  background: var(--surface);
}
table.heatmap { border-collapse: separate; border-spacing: 1.5px; font-size: .71rem; }
table.heatmap th, table.heatmap td { border: 0; padding: .32rem .42rem; text-align: center; }
table.heatmap th {
  position: sticky;
  top: 0;
  background: var(--surface);
  z-index: 2;
  border-bottom: 1px solid var(--line);
  white-space: nowrap;
}
table.heatmap td.z {
  font-variant-numeric: tabular-nums;
  border-radius: 3px;
  cursor: default;
}
table.heatmap td.z:hover { outline: 1.5px solid var(--fg); }
table.heatmap th.ch, table.heatmap td.ch {
  text-align: left;
  white-space: nowrap;
  max-width: 12rem;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-left: .65rem;
  background: var(--surface);
  position: sticky;
  left: 0;
  z-index: 1;
}
table.heatmap th.ch { z-index: 3; }
.z-legend { display: inline-flex; align-items: center; gap: .4rem; font-size: .78rem; color: var(--muted); margin-bottom: .6rem; }
.z-gradient {
  display: inline-block;
  width: 7rem;
  height: .55rem;
  border-radius: 3px;
  background: linear-gradient(90deg, #2b6cb0, #7ba7d0, #e4e6ea, #e8b07a, #c05621);
}

/* --- Badges & Dimension cards ----------------------------------------- */
.badge {
  display: inline-block;
  font-size: .68rem;
  font-weight: 600;
  padding: .15rem .45rem;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: .04em;
  background: var(--neutral);
  color: var(--fg);
}
.badge.marker-pruefen { background: #e0f2fe; color: #0369a1; }
.badge.marker-sachcheck { background: #fef3c7; color: #92400e; }
.badge.marker-todo { background: #f3e8ff; color: #6b21a8; }
.badge.marker-achtung { background: #fee2e2; color: #991b1b; }
.dim-card {
  padding: .75rem 0;
  border-bottom: 1px solid var(--line);
  display: grid;
  gap: .35rem;
}
.dim-card:last-child { border-bottom: 0; }
.dim-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  font-size: .84rem;
}
.dim-title { font-weight: 650; }
.dim-meta { font-size: .78rem; color: var(--muted); }
.dim-loadings { font-size: .76rem; color: var(--muted); line-height: 1.45; }
.dim-loadings b { color: var(--fg); font-weight: 500; }

/* --- Rows (artifacts & publications) ---------------------------------- */
.artifacts { display: grid; }
.artifact {
  display: flex;
  flex-wrap: wrap;
  gap: .35rem 1rem;
  align-items: baseline;
  justify-content: space-between;
  padding: .55rem .15rem;
  border-bottom: 1px solid var(--line);
}
.artifact:last-child { border-bottom: 0; }
.artifact .name { font-weight: 600; }
.artifact .meta { color: var(--muted); font-size: .78rem; font-variant-numeric: tabular-nums; }
.artifact a { color: var(--accent); text-decoration: none; font-size: .82rem; }
.artifact a:hover { text-decoration: underline; }
footer {
  max-width: 72rem;
  margin: 3rem auto 0;
  padding-top: 1rem;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: .78rem;
  display: flex;
  justify-content: space-between;
}

/* --- Floating & Fallback Tooltips ------------------------------------- */
.help {
  border-bottom: 1px dotted var(--muted);
  cursor: help;
  position: relative;
  display: inline-block;
}
.tooltip-popup {
  position: fixed;
  z-index: 10000;
  pointer-events: none;
  max-width: min(24rem, 86vw);
  padding: .5rem .75rem;
  border-radius: 6px;
  background: #18181b;
  color: #f4f4f5;
  border: 1px solid rgba(255, 255, 255, .12);
  font-size: .75rem;
  line-height: 1.45;
  box-shadow: 0 8px 24px rgba(0, 0, 0, .22);
  opacity: 0;
  visibility: hidden;
  transition: opacity .12s ease, visibility .12s ease;
  white-space: normal;
  text-transform: none;
  letter-spacing: normal;
  font-weight: 400;
}
.tooltip-popup.visible {
  opacity: 1;
  visibility: visible;
}

/* Fallback pure CSS tooltip when JS is disabled */
body:not(.has-js-tooltips) .help:hover::after,
body:not(.has-js-tooltips) .help:focus::after {
  content: attr(data-help);
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  z-index: 9999;
  width: max-content;
  max-width: min(22rem, 80vw);
  padding: .45rem .65rem;
  border-radius: 6px;
  background: #18181b;
  color: #f4f4f5;
  font-size: .74rem;
  line-height: 1.4;
  box-shadow: 0 4px 14px rgba(0, 0, 0, .2);
  white-space: normal;
  text-transform: none;
  letter-spacing: 0;
  font-weight: 400;
  pointer-events: none;
}

/* --- Controls (local server mode) ------------------------------------- */
.controls .row { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
.ctl-group { display: grid; gap: .3rem; padding: .65rem 0; border-bottom: 1px solid var(--line); }
.ctl-group:last-of-type { border-bottom: 0; }
.ctl-label { font-size: .68rem; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
.ctl-note { color: var(--muted); font-size: .8rem; }
button.ctl, select.ctl, input.ctl {
  font: inherit;
  font-size: .8rem;
  padding: .38rem .72rem;
  border-radius: 6px;
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--fg);
  cursor: pointer;
  transition: all .12s ease;
}
button.ctl:hover, select.ctl:hover { border-color: var(--accent); color: var(--accent); }
button.ctl.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button.ctl.primary:hover { opacity: .92; color: #fff; }
details.nda { border: 1px solid var(--line); border-radius: 8px; padding: .5rem .7rem; margin-top: .6rem; }
details.nda summary { cursor: pointer; font-size: .84rem; }
details.nda .row { margin-top: .5rem; }
.ctl-status { color: var(--muted); font-size: .8rem; min-height: 1.2em; margin-top: .5rem; }
.ctl-status.ok { color: var(--present); }
.ctl-status.err { color: var(--flag); }
body.only-flags .chapter { display: none; }
body.only-flags .chapter.has-flags { display: block; }
body.only-flags .chip:not(.sev-2):not(.sev-3) { display: none; }

/* --- Dark mode -------------------------------------------------------- */
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0e1013;
    --surface: #15181d;
    --fg: #e4e7ec;
    --muted: #88919e;
    --line: #21252d;
    --accent: #4a8ad4;
    --accent-light: #182230;
    --neutral: #2c323d;
  }
  .ptext { background: #181b22; }
  table.heatmap th, table.heatmap th.ch, table.heatmap td.ch { background: var(--surface); }
  tbody tr:hover { background: rgba(255, 255, 255, .02); }
  .tooltip-popup {
    background: #202024;
    border-color: #38383e;
    box-shadow: 0 8px 24px rgba(0, 0, 0, .45);
  }
  body:not(.has-js-tooltips) .help:hover::after,
  body:not(.has-js-tooltips) .help:focus::after {
    background: #202024;
    border: 1px solid #38383e;
  }
  .badge.marker-pruefen { background: #082f49; color: #7dd3fc; }
  .badge.marker-sachcheck { background: #451a03; color: #fde68a; }
  .badge.marker-todo { background: #3b0764; color: #d8b4fe; }
  .badge.marker-achtung { background: #450a0a; color: #fca5a5; }
}
"""

_JS = """\
(function () {
  var tip = document.createElement("div");
  tip.id = "lixity-tooltip";
  tip.className = "tooltip-popup";
  document.body.appendChild(tip);
  document.body.classList.add("has-js-tooltips");

  var activeEl = null;

  function show(el) {
    var text = el.getAttribute("data-help") || el.getAttribute("data-tip") || el.getAttribute("title");
    if (!text || !text.trim()) return;
    if (el.hasAttribute("title")) {
      el.setAttribute("data-tip", text);
      el.removeAttribute("title");
    }
    activeEl = el;
    tip.textContent = text;
    tip.classList.add("visible");
    updatePos(el);
  }

  function hide() {
    activeEl = null;
    tip.classList.remove("visible");
  }

  function updatePos(el) {
    if (!el || !tip.classList.contains("visible")) return;
    var rect = el.getBoundingClientRect();
    var tipW = tip.offsetWidth;
    var tipH = tip.offsetHeight;
    var left = rect.left + (rect.width - tipW) / 2;
    left = Math.max(10, Math.min(window.innerWidth - tipW - 10, left));
    var top = rect.top - tipH - 8;
    if (top < 10) {
      top = rect.bottom + 8;
    }
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }

  document.addEventListener("mouseover", function (e) {
    var el = e.target.closest("[data-help], [data-tip], [title]");
    if (el && !el.closest(".tooltip-popup")) show(el);
  }, { passive: true });

  document.addEventListener("mouseout", function (e) {
    var el = e.target.closest("[data-help], [data-tip]");
    if (el) hide();
  }, { passive: true });

  window.addEventListener("scroll", function () {
    if (activeEl) updatePos(activeEl);
  }, { passive: true });

  window.addEventListener("resize", function () {
    if (activeEl) updatePos(activeEl);
  }, { passive: true });
})();

document.addEventListener("click", function (event) {
  var chip = event.target.closest(".chip");
  if (chip) {
    var panel = document.getElementById(chip.dataset.target);
    if (panel) {
      var open = panel.classList.toggle("open");
      chip.classList.toggle("active", open);
      chip.setAttribute("aria-expanded", open ? "true" : "false");
    }
    return;
  }
});
var filter = document.getElementById("filter-flags");
if (filter) {
  filter.addEventListener("change", function () {
    document.body.classList.toggle("only-flags", filter.checked);
  });
}
var layer = document.getElementById("style-layer");
if (layer) {
  layer.addEventListener("change", function () {
    document.querySelectorAll(".chip").forEach(function (chip) {
      var color = layer.value ? chip.getAttribute("data-layer-" + layer.value) : null;
      chip.style.borderBottom = color ? "3px solid " + color : "";
    });
  });
}
async function markerApi(payload) {
  try {
    var res = await fetch(API + "/marker-" + payload._action, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    var data = await res.json();
    if (data.ok) { setTimeout(function () { location.reload(); }, 800); }
    return data;
  } catch (err) {
    return { ok: false, message: String(err) };
  }
}
document.addEventListener("click", async function (event) {
  var add = event.target.closest("[data-marker-add]");
  if (add) {
    markerApi({
      _action: "add",
      kind: add.dataset.markerAdd,
      line: parseInt(add.dataset.line, 10),
      note: ""
    });
    return;
  }
  var resolve = event.target.closest("[data-marker-resolve]");
  if (resolve) {
    markerApi({ _action: "resolve", id: resolve.dataset.markerResolve });
    return;
  }
});
var API = document.body.dataset.api || "";
var NDA_STATUSES = ["entwurf", "versendet", "bestaetigt", "unterschrieben"];
function ndaStatus(message, ok) {
  var el = document.getElementById("nda-status");
  if (!el) return;
  el.className = "ctl-status " + (ok ? "ok" : "err");
  el.textContent = (ok ? "✓ " : "✗ ") + (message || "");
}
async function ndaApi(path, payload) {
  try {
    var res = await fetch(API + "/" + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {})
    });
    return await res.json();
  } catch (err) {
    return { ok: false, message: String(err) };
  }
}
function ndaRender(records) {
  var host = document.getElementById("nda-table");
  var hint = document.getElementById("nda-hint");
  var unlockRow = document.getElementById("nda-unlock-row");
  var addRow = document.getElementById("nda-add-row");
  if (!host) return;
  if (unlockRow) unlockRow.hidden = true;
  if (addRow) addRow.hidden = false;
  if (hint) hint.textContent = records.length + " Einträge";
  var rows = records.map(function (r) {
    var options = NDA_STATUSES.map(function (s) {
      return '<option value="' + s + '"' + (s === r.status ? " selected" : "") + ">" + s + "</option>";
    }).join("");
    return "<tr><td><b>" + r.id + "</b></td><td>" + r.name + "</td><td>" + (r.contact || "–") +
      '</td><td><select class="ctl" data-nda-status="' + r.id + '">' + options + "</select></td>" +
      "<td>" + (r.pdf || "–") + "</td><td>" +
      '<button class="ctl" data-nda-export="' + r.id + '">PDF</button> ' +
      '<button class="ctl" data-nda-delete="' + r.id + '">✕</button></td></tr>';
  }).join("");
  host.innerHTML = records.length
    ? "<table><thead><tr><th>ID</th><th>Name</th><th>Kontakt</th><th>Status</th><th>PDF</th><th></th></tr></thead><tbody>" + rows + "</tbody></table>"
    : "";
}
async function ndaRefresh() {
  var data = await ndaApi("nda-list", {});
  if (!data.ok) {
    var hint = document.getElementById("nda-hint");
    if (hint) hint.textContent = data.message || "";
    var unlockRow = document.getElementById("nda-unlock-row");
    if (unlockRow) unlockRow.hidden = false;
    return;
  }
  ndaRender(data.records || []);
}
document.addEventListener("click", async function (event) {
  var unlock = event.target.closest("#nda-unlock-btn");
  if (unlock) {
    var pass = document.getElementById("nda-passphrase");
    var data = await ndaApi("nda-unlock", { passphrase: pass ? pass.value : "" });
    ndaStatus(data.message, data.ok);
    if (data.ok) { if (pass) pass.value = ""; ndaRender(data.records || []); }
    return;
  }
  var add = event.target.closest("#nda-add-btn");
  if (add) {
    var payload = {
      name: document.getElementById("nda-new-name").value,
      contact: document.getElementById("nda-new-contact").value,
      notes: document.getElementById("nda-new-notes").value
    };
    var res = await ndaApi("nda-add", payload);
    ndaStatus(res.message, res.ok);
    if (res.ok) ndaRefresh();
    return;
  }
  var exp = event.target.closest("[data-nda-export]");
  if (exp) {
    var res2 = await ndaApi("nda-export", { id: exp.dataset.ndaExport });
    ndaStatus(res2.message, res2.ok);
    if (res2.ok) ndaRefresh();
    return;
  }
  var del = event.target.closest("[data-nda-delete]");
  if (del) {
    var res3 = await ndaApi("nda-delete", { id: del.dataset.ndaDelete });
    ndaStatus(res3.message, res3.ok);
    if (res3.ok) ndaRefresh();
    return;
  }
});
document.addEventListener("change", async function (event) {
  var sel = event.target.closest("[data-nda-status]");
  if (sel) {
    var res = await ndaApi("nda-update", { id: sel.dataset.ndaStatus, status: sel.value });
    ndaStatus(res.message, res.ok);
  }
});
if (document.getElementById("nda-manager")) { ndaRefresh(); }
async function runAction(action, payload) {
  var status = document.getElementById("ctl-status");
  if (!status) return;
  status.className = "ctl-status";
  status.textContent = "…";
  try {
    var res = await fetch(API + "/" + action, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {})
    });
    var data = await res.json();
    status.className = "ctl-status " + (data.ok ? "ok" : "err");
    status.textContent = (data.ok ? "✓ " : "✗ ") + (data.message || "");
    if (data.reload) { setTimeout(function () { location.reload(); }, 1200); }
  } catch (err) {
    status.className = "ctl-status err";
    status.textContent = "✗ " + err;
  }
}
document.querySelectorAll("[data-action]").forEach(function (btn) {
  btn.addEventListener("click", function () {
    var payload = {};
    if (btn.dataset.payload === "format") {
      payload.format = document.getElementById("fmt").value;
    }
    if (btn.dataset.payload === "nda") {
      payload.name = document.getElementById("nda-name").value;
      payload.contact = document.getElementById("nda-contact").value;
    }
    if (btn.dataset.payload === "settings") {
      payload.language = document.getElementById("set-language").value;
      payload.title = document.getElementById("set-title").value;
    }
    if (btn.dataset.payload === "load") {
      var input = document.getElementById("ms-file");
      if (!input.files || !input.files.length) {
        var status = document.getElementById("ctl-status");
        status.className = "ctl-status err";
        status.textContent = "✗ " + (input.getAttribute("accept") || "Datei");
        return;
      }
      var file = input.files[0];
      var reader = new FileReader();
      reader.onload = function () {
        runAction("load", { name: file.name, content: reader.result });
      };
      reader.readAsText(file);
      return;
    }
    runAction(btn.dataset.action, payload);
  });
});
"""


_DEFAULT_LABELS = {**EN_LABELS, **METRIC_LABELS["en"], **HELP_TEXTS["en"]}


def _label(labels: Mapping[str, str] | None, key: str) -> str:
    source = labels if labels else _DEFAULT_LABELS
    return source.get(key, _DEFAULT_LABELS.get(key, key))


# Help-key mapping: model field name (FEATURES) -> tooltip key (help_*).
_FEATURE_HELP = {
    "asl": "asl",
    "staccato_pct": "staccato",
    "kaskade_pct": "kaskade",
    "sentence_cv": "cv",
    "dialog_pct": "dialogue",
    "function_word_pct": "function_words",
    "filter_density": "perception",
    "modal_density": "modal",
    "passive_density": "passive",
    "nominalization_density": "nominal",
    "adjective_density": "adjective",
    "long_word_pct": "lix",
    "start_entropy": "start_entropy",
    "first_person_start_rate": "first_start",
    "guiraud_r": "guiraud",
    "hd_d": "hd_d",
}


def _tense_class(dominant: str) -> str:
    if dominant == TENSE_PRESENT:
        return "tense-present"
    if dominant == TENSE_PAST:
        return "tense-past"
    if dominant == TENSE_MIXED:
        return "tense-mixed"
    return "tense-neutral"


def _help(labels: Mapping[str, str] | None, key: str, text: str) -> str:
    """Wraps a term with a tooltip (help text from the language profile)."""
    tip = _label(labels, f"help_{key}")
    if not tip or tip.startswith("help_"):
        tip = HELP_TEXTS["en"].get(f"help_{key}") or HELP_TEXTS["de"].get(f"help_{key}") or ""
    if not tip:
        return text
    return (
        f'<span class="help" data-help="{html.escape(tip, quote=True)}" tabindex="0">{text}</span>'
    )


def _kpi(value: str, label: str) -> str:
    return f'<div class="kpi"><b>{value}</b><span>{label}</span></div>'


def render_dashboard(
    chapters: Sequence[ChapterProfile],
    paragraphs: Sequence[ParagraphProfile],
    metrics: Any | None = None,
    fingerprint: Any | None = None,
    markers: Sequence[Any] | None = None,
    artifacts: Sequence[Mapping[str, Any]] | None = None,
    title: str = "Manuskript",
    labels: Mapping[str, str] | None = None,
    language_name: str = "",
    tense_available: bool = True,
    engine_name: str = "Lixity",
    controls: bool = False,
    api_base: str = "/api",
    manuscript_name: str = "",
    current_language: str = "auto",
    language_options: Sequence | None = None,
) -> str:
    """Renders the complete, deterministic single-file dashboard.

    ``controls=True`` adds the local control panel (buttons/dropdown/NDA),
    which triggers the CLI functions via the UI server (``scripts/ui_server.py``).
    """
    esc = html.escape
    L = lambda key: esc(_label(labels, key))  # noqa: E731
    if not language_options:
        language_options = [
            ("auto", "auto"),
            ("de", "Deutsch"),
            ("en", "English"),
            ("fr", "Français"),
            ("es", "Español"),
            ("it", "Italiano"),
            ("pt", "Português"),
            ("nl", "Nederlands"),
            ("generic", "generic"),
        ]

    total_words = sum(c.words for c in chapters)
    total_flagged = sum(1 for p in paragraphs if p.severity >= 2)
    scale = max((p.words for p in paragraphs), default=1)
    function_pct = (
        round(sum(p.function_word_pct for p in paragraphs) / len(paragraphs), 1)
        if paragraphs
        else 0.0
    )

    parts = [
        "<!DOCTYPE html>",
        '<html lang="de">',
        "<head>",
        '<meta charset="utf-8"/>',
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>',
        f"<title>{esc(title)} – {L('app_suffix')}</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        f'<body id="top" data-api="{esc(api_base)}">',
        '<div class="page">',
        "<header>",
        f"<h1>{esc(title)}</h1>",
        f'<p class="sub">{L("app_suffix")}'
        + (f" · {esc(language_name)}" if language_name else "")
        + "</p>",
        f'<p class="hint">{L("hint")}</p>',
        "</header>",
    ]

    if controls:
        parts.append('<section class="panel controls" id="controls">')
        parts.append(f"<h2>{L('controls')}</h2>")

        # Load manuscript
        parts.append('<div class="ctl-group">')
        parts.append(f'<span class="ctl-label">{L("manuscript")}</span>')
        parts.append('<div class="row">')
        parts.append('<input class="ctl" type="file" id="ms-file" accept=".md,.markdown,.txt"/>')
        parts.append(
            f'<button class="ctl" data-action="load" data-payload="load">{L("load")}</button>'
        )
        if manuscript_name:
            parts.append(
                f'<span class="ctl-note">{L("current_manuscript")}: {esc(manuscript_name)}</span>'
            )
        parts.append("</div></div>")

        # Settings (language, title)
        parts.append('<div class="ctl-group">')
        parts.append(f'<span class="ctl-label">{L("settings")}</span>')
        parts.append('<div class="row">')
        parts.append(
            f'<select class="ctl" id="set-language" aria-label="{L("language")}">'
            + "".join(
                f'<option value="{code}"{" selected" if code == current_language else ""}>{label}</option>'
                for code, label in language_options
            )
            + "</select>"
        )
        parts.append(
            f'<input class="ctl" id="set-title" value="{esc(title)}" placeholder="{L("title")}"/>'
        )
        parts.append(
            f'<button class="ctl" data-action="settings" data-payload="settings">{L("apply")}</button>'
        )
        parts.append("</div></div>")

        # Analyses & exports
        parts.append('<div class="ctl-group">')
        parts.append(f'<span class="ctl-label">{L("export")} · {L("run_analysis")}</span>')
        parts.append('<div class="row">')
        parts.append(
            f'<select class="ctl" id="fmt" aria-label="{esc(_label(labels, "help_format"))}">'
            f'<option value="all">{L("format_all")}</option>'
            f'<option value="a4">A4</option>'
            f'<option value="taschenbuch">{L("format_paperback")}</option>'
            f'<option value="mobile">Mobile</option>'
            f'<option value="epub">EPUB</option>'
            "</select>"
        )
        parts.append(
            f'<button class="ctl primary" data-action="export" data-payload="format">'
            f"{_help(labels, 'export', L('export'))}</button>"
        )
        parts.append(
            f'<button class="ctl" data-action="analyze">{_help(labels, "rebuild", L("run_analysis"))}</button>'
        )
        for action in ("sync", "audit", "prune", "gdrive", "rebuild"):
            parts.append(
                f'<button class="ctl" data-action="{action}">{_help(labels, action, L(action))}</button>'
            )
        parts.append("</div></div>")

        # NDA
        parts.append('<div class="ctl-group">')
        parts.append(f'<span class="ctl-label">{_help(labels, "nda", L("new_nda"))}</span>')
        parts.append('<div class="row">')
        parts.append(f'<input class="ctl" id="nda-name" placeholder="{L("name")}"/>')
        parts.append(f'<input class="ctl" id="nda-contact" placeholder="{L("contact")}"/>')
        parts.append(
            f'<button class="ctl" data-action="nda" data-payload="nda">{L("create")}</button>'
        )
        parts.append("</div></div>")

        parts.append(f'<div class="ctl-status" id="ctl-status">{L("server_hint")}</div>')
        parts.append("</section>")

        parts.append('<section class="panel controls" id="nda-manager">')
        parts.append(f"<h2>{L('nda_manager')}</h2>")
        parts.append(f'<p class="ctl-note" id="nda-hint">{L("locked_hint")}</p>')
        parts.append('<div class="row" id="nda-unlock-row">')
        parts.append(
            f'<input class="ctl" type="password" id="nda-passphrase" placeholder="{L("passphrase")}"/>'
        )
        parts.append(f'<button class="ctl" id="nda-unlock-btn">{L("unlock")}</button>')
        parts.append("</div>")
        parts.append('<div id="nda-table"></div>')
        parts.append('<div class="row" id="nda-add-row" hidden="hidden">')
        parts.append(f'<input class="ctl" id="nda-new-name" placeholder="{L("name")}"/>')
        parts.append(f'<input class="ctl" id="nda-new-contact" placeholder="{L("contact")}"/>')
        parts.append(f'<input class="ctl" id="nda-new-notes" placeholder="{L("notes")}"/>')
        parts.append(
            f'<button class="ctl primary" id="nda-add-btn">{L("create")} + {L("export_pdf")}</button>'
        )
        parts.append("</div>")
        parts.append('<div class="ctl-status" id="nda-status"></div>')
        parts.append("</section>")

    # --- Key metrics ------------------------------------------------------
    parts.append('<section class="kpis">')
    parts.append(_kpi(f"{total_words:,}", _help(labels, "words", L("words_prose"))))
    parts.append(_kpi(str(len(chapters)), L("chapter")))
    parts.append(_kpi(str(len(paragraphs)), L("paragraphs")))
    if metrics is not None:
        parts.append(_kpi(f"{metrics.total_sentences:,}", L("sentences")))
        parts.append(_kpi(f"{metrics.asl:.2f}", _help(labels, "asl", "ASL")))
        parts.append(_kpi(f"{metrics.ttr:.4f}", _help(labels, "ttr", "TTR")))
        parts.append(_kpi(f"{metrics.yules_k:.1f}", _help(labels, "yules", "Yule&#8217;s K")))
        parts.append(_kpi(f"{metrics.flesch_de:.1f}", _help(labels, "flesch", "Flesch")))
        parts.append(_kpi(f"{metrics.lix:.1f}", _help(labels, "lix", "LIX")))
        parts.append(
            _kpi(f"{metrics.dialog_ratio:.1f} %", _help(labels, "dialogue", L("dialogue")))
        )
        parts.append(_kpi(f"{metrics.guiraud_r:.2f}", _help(labels, "guiraud", "Guiraud R")))
        hd_d_value = f"{metrics.hd_d:.3f}" if getattr(metrics, "hd_d", None) is not None else "–"
        parts.append(_kpi(hd_d_value, _help(labels, "hd_d", "HD-D")))
        parts.append(
            _kpi(f"{metrics.staccato_pct:.1f} %", _help(labels, "staccato", L("feat_staccato")))
        )
        parts.append(
            _kpi(
                f"{metrics.first_person_start_rate:.1f} %",
                _help(labels, "first_start", L("feat_ich_start")),
            )
        )
    parts.append(
        _kpi(f"{function_pct:.1f} %", _help(labels, "function_words", L("function_words")))
    )
    if fingerprint is not None:
        parts.append(
            _kpi(
                f"{fingerprint.consistency * 100:.0f} %",
                _help(labels, "consistency", L("consistency")),
            )
        )
        drifters = fingerprint.top_deviants(1)
        if drifters:
            num, mean_abs = drifters[0]
            parts.append(
                _kpi(
                    f"K. {num} (Ø {mean_abs:.1f})",
                    _help(labels, "fingerprint", f"{L('deviation')} · Ø|z|"),
                )
            )
    parts.append(_kpi(str(total_flagged), _help(labels, "flagged", L("flagged"))))
    parts.append("</section>")

    # --- Sentence-length architecture -------------------------------------
    if metrics is not None:
        d = metrics.sentence_dist
        rows = [
            ("≤ 6", d.short_count, d.short_pct),
            ("7–15", d.medium_count, d.medium_pct),
            ("16–25", d.long_count, d.long_pct),
            ("> 25", d.complex_count, d.complex_pct),
        ]
        parts.append('<section class="panel">')
        parts.append(f"<h2>{L('sentence_dist')}</h2>")
        parts.append('<div class="dist">')
        for criterion, count, pct in rows:
            parts.append(
                f'<div class="row"><span>{criterion}</span>'
                f'<span class="bar"><i style="width:{max(0.0, min(100.0, pct)):.1f}%"></i></span>'
                f'<span class="val">{count:,} · {pct:.1f} %</span></div>'
            )
        parts.append("</div></section>")

    # --- Style heatmap & passport (self-calibrated house style) -----------
    if fingerprint is not None and metrics is not None and metrics.chapters:
        parts.append('<section class="panel">')
        parts.append(f"<h2>{_help(labels, 'heatmap', L('style_fingerprint'))}</h2>")
        parts.append('<p class="hint">' + esc(_label(labels, "help_heatmap")) + "</p>")
        parts.append(
            '<div class="z-legend">'
            + esc(_label(labels, "zscore"))
            + ' <span class="z-gradient"></span> −2.5 … +2.5</div>'
        )
        parts.append('<div class="heatmap-wrap"><table class="heatmap"><thead><tr>')
        parts.append(f'<th class="ch">{L("chapter")}</th>')
        for _field, label_key, _unit in FEATURES:
            parts.append(
                f"<th>{_help(labels, _FEATURE_HELP.get(_field, _field), esc(_label(labels, label_key)))}</th>"
            )
        parts.append("</tr></thead><tbody>")
        for chapter in metrics.chapters:
            if chapter.num not in fingerprint.z_scores:
                continue
            parts.append(f'<tr><td class="ch">{chapter.num}. {esc(chapter.title)}</td>')
            for field_name, label_key, _unit in FEATURES:
                z = fingerprint.z_scores[chapter.num].get(field_name)
                if z is None:
                    parts.append('<td class="z">–</td>')
                    continue
                raw = fingerprint.values[field_name].get(chapter.num)
                raw_text = f"{raw:.2f}" if isinstance(raw, float) else str(raw)
                effect = fingerprint.effect_sizes[chapter.num].get(field_name, 0.0)
                tooltip = (
                    f"{_label(labels, label_key)}: {raw_text} · "
                    f"z* {z:+.1f} · {_label(labels, 'effect_size')} {effect:+.1f}\u03c3"
                )
                parts.append(
                    f'<td class="z" style="background:{z_color(z)}" '
                    f'title="{esc(tooltip, quote=True)}">{z:+.1f}</td>'
                )
            parts.append("</tr>")
        parts.append("</tbody></table></div>")
        fdr_total = sum(len(v) for v in fingerprint.fdr_flagged.values())
        parts.append(
            f'<p class="hint">{_help(labels, "expected_false_positives", L("expected_false_positives"))}: '
            f"~{fingerprint.expected_false_positives:.1f} · "
            f"{_help(labels, 'fdr', L('fdr_flagged'))}: {fdr_total}</p>"
        )
        parts.append("</section>")

        parts.append('<section class="panel">')
        parts.append(f"<h2>{_help(labels, 'passport', L('style_passport'))}</h2>")
        parts.append("<table><thead><tr>")
        parts.append(
            f'<th>{L("metrics")}</th><th class="num">{L("median")}</th>'
            f'<th class="num">{L("band")} (±2σ)</th><th class="num">{L("outliers")}</th>'
        )
        parts.append("</tr></thead><tbody>")
        for field_name, label_key, _unit in FEATURES:
            base = fingerprint.baseline.get(field_name, {})
            if not base.get("n"):
                continue
            centre = float(base["median"])
            sigma = float(base["sigma"])
            band_text = f"{centre - 2 * sigma:.2f} … {centre + 2 * sigma:.2f}"
            n_out = sum(1 for cells in fingerprint.deviations.values() if field_name in cells)
            outlier_text = str(n_out) if n_out else "–"
            parts.append(
                f"<tr><td>{_help(labels, _FEATURE_HELP.get(field_name, field_name), esc(_label(labels, label_key)))}</td>"
                f'<td class="num">{centre:.2f}</td>'
                f'<td class="num">{esc(band_text)}</td>'
                f'<td class="num">{outlier_text}</td></tr>'
            )
        parts.append("</tbody></table></section>")

        # --- Style dimensions (self-calibrated principal axes) -------------
        if fingerprint.dimensions:
            parts.append('<section class="panel">')
            parts.append(f"<h2>{_help(labels, 'dimensions', L('style_dimensions'))}</h2>")
            field_labels = {f: label_key for f, label_key, _u in FEATURES}
            for dim in fingerprint.dimensions:
                loadings: dict[str, float] = dim["loadings"]
                top_pos = sorted(loadings.items(), key=lambda kv: kv[1], reverse=True)[:3]
                top_neg = sorted(loadings.items(), key=lambda kv: kv[1])[:3]
                pos_text = " · ".join(
                    f"{esc(_label(labels, field_labels.get(f, f)))} {v:+.2f}" for f, v in top_pos
                )
                neg_text = " · ".join(
                    f"{esc(_label(labels, field_labels.get(f, f)))} {v:+.2f}" for f, v in top_neg
                )
                flagged = dim.get("flagged", [])
                parts.append('<div class="dim-card">')
                parts.append(
                    f'<div class="dim-header"><span class="dim-title">{L("style_dimensions")} {dim["index"]}</span>'
                    f'<span class="badge">{dim["variance"] * 100:.0f}% {L("dim_variance")}</span></div>'
                )
                parts.append(
                    f'<div class="dim-loadings"><b>{L("dim_loadings_pos")}:</b> {pos_text}<br/>'
                    f'<b>{L("dim_loadings_neg")}:</b> {neg_text}</div>'
                )
                if flagged:
                    ch_label = L("chapter")
                    flagged_str = ", ".join(f"{ch_label} {ch}" for ch in flagged)
                    parts.append(
                        f'<div class="dim-meta">{L("dim_flagged")}: {flagged_str}</div>'
                    )
                parts.append("</div>")
            parts.append("</section>")

        # --- Work markers (editor-visible, set from the dashboard) -------
        if markers is not None:
            parts.append('<section class="panel">')
            parts.append(f"<h2>{_help(labels, 'markers', L('markers'))}</h2>")
            if markers:
                parts.append("<table><thead><tr>")
                parts.append(
                    f'<th>{L("status")}</th><th class="num">{L("line")}</th>'
                    f"<th>{L('notes')}</th>"
                )
                if controls:
                    parts.append("<th></th>")
                parts.append("</tr></thead><tbody>")
                for m in markers:
                    kind_label = _label(labels, "marker_" + m.kind)
                    note = esc(str(m.note or "")) or "–"
                    parts.append(
                        f'<tr><td><span class="badge marker-{m.kind}">{esc(kind_label)}</span></td>'
                        f'<td class="num">{L("line")} {m.line}</td><td>{note}</td>'
                    )
                    if controls:
                        parts.append(
                            f'<td><button class="ctl" data-marker-resolve="{esc(m.id, quote=True)}">'
                            f"{L('marker_resolve')}</button></td>"
                        )
                    parts.append("</tr>")
                parts.append("</tbody></table>")
            else:
                parts.append(f'<p class="hint">{L("markers_empty")}</p>')
            parts.append("</section>")

        # --- Toolbar ----------------------------------------------------------
    parts.append('<div class="toolbar">')
    parts.append(f'<label><input type="checkbox" id="filter-flags"/> {L("filter_flags")}</label>')
    if paragraphs:
        parts.append("<label>")
        parts.append(f"{_help(labels, 'layer', L('style_layer'))} ")
        parts.append('<select class="ctl" id="style-layer">')
        parts.append(f'<option value="">{L("layer_off")}</option>')
        for layer_key in LAYER_FEATURES:
            parts.append(
                f'<option value="{layer_key}">{esc(_label(labels, "layer_" + layer_key))}</option>'
            )
        parts.append("</select></label>")
    parts.append('<span class="legend">')
    for key, color in (
        ("present", "var(--present)"),
        ("past", "var(--past)"),
        ("mixed", "var(--mixed)"),
        ("neutral", "var(--neutral)"),
    ):
        parts.append(
            f'<span><span class="swatch" style="background:{color}"></span>{L(key)}</span>'
        )
    parts.append(
        f'<span><span class="swatch" style="background:var(--flag)"></span>'
        f"{L('severity_2')} / {L('severity_3')}</span>"
    )
    parts.append("</span>")
    parts.append(f'<a class="totop" href="#top">↑ {L("top")}</a>')
    parts.append("</div>")

    if not tense_available:
        parts.append(f'<p class="hint">{L("no_tense")}</p>')

    # --- Chapter map ------------------------------------------------------
    by_chapter: dict = {}
    for idx, p in enumerate(paragraphs):
        by_chapter.setdefault(p.chapter_num, []).append((idx, p))

    layer_data: dict[str, dict[int, str | None]] = {
        layer_key: layer_colors(paragraphs, layer_key) for layer_key in LAYER_FEATURES
    }

    parts.append("<main>")
    for chapter in chapters:
        chapter_paras = by_chapter.get(chapter.num, [])
        has_flags = any(p.severity >= 2 for _, p in chapter_paras)
        classes = "chapter has-flags" if has_flags else "chapter"
        parts.append(f'<section class="{classes}" id="ch-{chapter.num}">')
        parts.append('<div class="chapter-head">')
        parts.append(f"<h2>{chapter.num}. {esc(chapter.title)}</h2>")
        parts.append(
            f'<span class="meta">{chapter.words:,} {L("words")} · '
            f"{chapter.paragraphs} {L('paragraphs')} · {esc(chapter.dominant)} · "
            f"{chapter.flagged} {L('flagged')} · {L('line')} {chapter.start_line}–{chapter.end_line}</span>"
        )
        parts.append("</div>")

        if chapter_paras:
            parts.append('<div class="strip">')
            for idx, p in chapter_paras:
                sev = f" sev-{p.severity}" if p.severity >= 2 else ""
                width = max(1.0, p.words / scale * 100.0)
                dom_label = _label(labels, p.dominant)
                sev_label = _label(labels, f"severity_{p.severity}")
                tooltip = (
                    f"{p.line_label} · {dom_label} · "
                    f"{_label(labels, 'present')} {p.present_hits} / "
                    f"{_label(labels, 'past')} {p.past_hits} · {sev_label}"
                )
                layer_attrs = "".join(
                    f' data-layer-{key}="{color}"'
                    for key in LAYER_FEATURES
                    if (color := layer_data.get(key, {}).get(idx))
                )
                parts.append(
                    f'<button class="chip {_tense_class(p.dominant)}{sev}" '
                    f'style="flex:{width:.2f} 0 auto" data-target="p-{idx}"'
                    f"{layer_attrs} "
                    f'title="{esc(tooltip)}" aria-label="{esc(tooltip)}" aria-expanded="false"></button>'
                )
            parts.append("</div>")

            for idx, p in chapter_paras:
                parts.append(f'<div class="ptext" id="p-{idx}">')
                parts.append(
                    f'<div class="anchor">{p.line_label} · '
                    f"{esc(dom_label)} · {esc(sev_label)}</div>"
                )
                parts.append(
                    f'<div class="stats">{L("present")} {p.present_hits} · {L("past")} {p.past_hits} · '
                    f"ASL {p.asl:.1f} · {L('dialogue')} {p.dialogue_pct:.1f} % · "
                    f"{L('function_words')} {p.function_word_pct:.1f} % · "
                    f"{L('feat_filter')} {p.filter_density:.1f} · {L('feat_modal')} {p.modal_density:.1f} · "
                    f"{L('feat_nominal')} {p.nominal_density:.1f} · {L('feat_passive')} {p.passive_density:.1f} · "
                    f"{p.words} {L('words')}</div>"
                )
                if controls:
                    buttons = " ".join(
                        f'<button class="ctl" data-marker-add="{esc(kind, quote=True)}" '
                        f'data-line="{p.start_line}">+ {esc(_label(labels, "marker_" + kind))}</button>'
                        for kind in ("pruefen", "sachcheck", "todo", "achtung")
                    )
                    parts.append(f'<div class="row">{buttons}</div>')
                parts.append(f"<p>{esc(p.text)}</p>")
                parts.append("</div>")
        parts.append("</section>")
    parts.append("</main>")

    # --- Chapter matrix ---------------------------------------------------
    if chapters:
        parts.append('<section class="panel">')
        parts.append(f"<h2>{L('chapter_table')}</h2>")
        parts.append("<table><thead><tr>")
        parts.append(
            f'<th>#</th><th>{L("chapter")}</th><th class="num">{L("words")}</th>'
            f'<th class="num">ASL</th><th class="num">{L("dialogue")}</th>'
            f'<th class="num">{L("function_words")}</th><th>{L("past")}/{L("present")}</th>'
            f'<th class="num">{L("flagged")}</th>'
        )
        if fingerprint is not None:
            parts.append(f'<th class="num">{L("deviation")}</th>')
        parts.append("</tr></thead><tbody>")
        for c in chapters:
            parts.append(
                f"<tr><td>{c.num}</td><td>{esc(c.title)}</td>"
                f'<td class="num">{c.words:,}</td><td class="num">{c.asl:.1f}</td>'
                f'<td class="num">{c.dialog_pct:.1f} %</td><td class="num">{c.function_word_pct:.1f} %</td>'
                f'<td>{esc(c.dominant)}</td><td class="num">{c.flagged}</td>'
            )
            if fingerprint is not None:
                dev = fingerprint.deviations.get(c.num, {})
                if dev:
                    named = ", ".join(
                        f"{_label(labels, label_key)} {z:+.1f}σ"
                        for field_name, label_key, _unit in FEATURES
                        if (z := dev.get(field_name)) is not None
                    )
                    parts.append(
                        f'<td class="num" title="{esc(named, quote=True)}">{len(dev)}</td>'
                    )
                else:
                    parts.append('<td class="num">–</td>')
            parts.append("</tr>")
        parts.append("</tbody></table></section>")

    # --- Publications -----------------------------------------------------
    if artifacts:
        parts.append('<section class="panel">')
        parts.append(f"<h2>{_help(labels, 'artifacts', L('artifacts'))}</h2>")
        parts.append('<div class="artifacts">')
        for art in artifacts:
            name = esc(str(art.get("name", "")))
            meta_bits = []
            if art.get("size_kb") is not None:
                meta_bits.append(f"{art['size_kb']:.0f} KB")
            if art.get("pages"):
                meta_bits.append(f"{art['pages']} {_label(labels, 'pages')}")
            meta = " · ".join(meta_bits)
            href = art.get("href")
            link = (
                f'<a href="{esc(str(href))}" target="_blank" rel="noopener">{L("open")}</a>'
                if href
                else ""
            )
            parts.append(
                f'<div class="artifact"><span class="name">{name}</span>'
                f'<span class="meta">{esc(meta)}</span>{link}</div>'
            )
        parts.append("</div></section>")

    parts.extend(
        [
            "</div>",
            f"<footer><span>{esc(engine_name)} · {L('app_suffix')}</span><span>{esc(title)}</span></footer>",
            f"<script>{_JS}</script>",
            "</body>",
            "</html>",
        ]
    )
    return "\n".join(parts) + "\n"


# Backwards-compatible name (older calls/tests)
render_style_report = render_dashboard
