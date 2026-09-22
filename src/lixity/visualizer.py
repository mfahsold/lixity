"""
scripts/engine/visualizer.py
============================
Radically simple, self-contained HTML analysis (single-file dashboard).

One document combines:
- corpus metrics (words, sentences, ASL, TTR, Yule's K, Flesch, LIX, dialogue,
  function word ratio),
- the sentence-length architecture,
- a chapter map with colour-coded paragraph strip (tense dominance),
- flagged paragraphs (tense switch/mixture) with click for text + line anchor,
- the publication artefacts (PDF/EPUB/NDA) with size, page count and link.

Properties: no external dependencies (no CDN, no framework),
deterministic (no timestamps), idempotently writable, dual light/dark,
fully localised via the labels of the language profile.
"""

import html
from typing import Any, Mapping, Optional, Sequence

from .language_data import EN_LABELS, METRIC_LABELS
from .style_profile import (
    ChapterProfile,
    ParagraphProfile,
    TENSE_MIXED,
    TENSE_PAST,
    TENSE_PRESENT,
)

_CSS = """\
:root {
  --bg: #f6f7f9; --surface: #ffffff; --fg: #16181d; --muted: #6b7280;
  --line: #e5e7eb; --accent: #3b6ea5;
  --present: #2f8f6f; --past: #b07a3f; --mixed: #7a6f9b; --neutral: #cbd5e1;
  --flag: #b3402f; --radius: 12px;
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
body {
  margin: 0; padding: 2rem 1.25rem 3rem; background: var(--bg); color: var(--fg);
  font: 15px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
}
.page { max-width: 68rem; margin: 0 auto; }
h1 { font-size: 1.5rem; margin: 0 0 .2rem; letter-spacing: -.01em; }
h2 { font-size: 1rem; margin: 0; }
.sub, .hint { color: var(--muted); font-size: .85rem; margin: 0; }
.panel {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
  padding: 1rem 1.1rem; margin: 1rem 0; box-shadow: 0 1px 2px rgba(16,24,40,.04);
}
.panel > h2 { margin-bottom: .6rem; }
.kpis { display: grid; grid-template-columns: repeat(auto-fill, minmax(9.5rem, 1fr)); gap: .75rem; margin: 1.25rem 0; }
.kpi {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
  padding: .7rem .8rem; box-shadow: 0 1px 2px rgba(16,24,40,.04);
}
.kpi b { display: block; font-size: 1.35rem; font-variant-numeric: tabular-nums; letter-spacing: -.02em; }
.kpi span { color: var(--muted); font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; }
.dist { display: grid; gap: .45rem; }
.dist .row { display: grid; grid-template-columns: 8rem 1fr 7.5rem; align-items: center; gap: .6rem; font-size: .85rem; }
.dist .bar { height: 8px; background: var(--line); border-radius: 999px; overflow: hidden; }
.dist .bar i { display: block; height: 100%; background: var(--accent); }
.dist .val { text-align: right; color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
.toolbar {
  position: sticky; top: 0; z-index: 5; display: flex; flex-wrap: wrap; gap: 1rem;
  align-items: center; margin: 1rem 0; padding: .6rem .2rem; background: var(--bg);
  border-bottom: 1px solid var(--line);
}
.toolbar label { font-size: .85rem; display: inline-flex; gap: .4rem; align-items: center; cursor: pointer; }
.legend { display: flex; flex-wrap: wrap; gap: .75rem; font-size: .8rem; color: var(--muted); }
.swatch { display: inline-block; width: .7rem; height: .7rem; border-radius: 3px; margin-right: .3rem; vertical-align: -1px; }
.totop { margin-left: auto; font-size: .8rem; color: var(--muted); text-decoration: none; }
.totop:hover { color: var(--fg); }
.chapter { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: .85rem 1rem; margin: .6rem 0; }
.chapter-head { display: flex; flex-wrap: wrap; gap: .5rem 1rem; align-items: baseline; justify-content: space-between; }
.chapter-head .meta { color: var(--muted); font-size: .8rem; font-variant-numeric: tabular-nums; }
.strip { display: flex; gap: 2px; margin: .6rem 0 0; }
.chip {
  border: 0; padding: 0; height: 20px; min-width: 8px; border-radius: 3px;
  background: var(--neutral); cursor: pointer; opacity: .9; touch-action: manipulation;
}
.chip:hover, .chip:focus-visible, .chip.active { opacity: 1; outline: 2px solid var(--fg); outline-offset: 1px; }
.chip.tense-present { background: var(--present); }
.chip.tense-past { background: var(--past); }
.chip.tense-mixed { background: var(--mixed); }
.chip.sev-2 { box-shadow: inset 0 -3px 0 var(--flag); }
.chip.sev-3 { box-shadow: inset 0 0 0 2px var(--flag); }
.ptext { display: none; margin: .7rem 0 0; padding: .8rem .9rem; border-left: 3px solid var(--accent); background: var(--bg); border-radius: 0 8px 8px 0; }
.ptext.open { display: block; }
.ptext .anchor { color: var(--muted); font-size: .78rem; font-variant-numeric: tabular-nums; }
.ptext .stats { color: var(--muted); font-size: .78rem; margin: .15rem 0 .4rem; }
.ptext p { margin: 0; }
table { width: 100%; border-collapse: collapse; font-size: .85rem; }
th, td { text-align: left; padding: .35rem .5rem; border-bottom: 1px solid var(--line); }
th { color: var(--muted); font-weight: 500; text-transform: uppercase; font-size: .7rem; letter-spacing: .06em; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.artifacts { display: grid; gap: .5rem; }
.artifact { display: flex; flex-wrap: wrap; gap: .5rem 1rem; align-items: baseline; justify-content: space-between; padding: .55rem .7rem; border: 1px solid var(--line); border-radius: 10px; }
.artifact .name { font-weight: 600; }
.artifact .meta { color: var(--muted); font-size: .8rem; font-variant-numeric: tabular-nums; }
.artifact a { color: var(--accent); text-decoration: none; font-size: .85rem; }
.artifact a:hover { text-decoration: underline; }
footer { max-width: 68rem; margin: 2rem auto 0; color: var(--muted); font-size: .78rem; display: flex; justify-content: space-between; }
.help { border-bottom: 1px dotted var(--muted); cursor: help; position: relative; }
.help:hover::after, .help:focus::after {
  content: attr(data-help); position: absolute; left: 0; top: 1.5em; z-index: 30;
  width: max-content; max-width: 24rem; padding: .55rem .7rem; border-radius: 9px;
  background: var(--fg); color: var(--bg); font-size: .78rem; line-height: 1.45;
  box-shadow: 0 8px 24px rgba(0,0,0,.2); white-space: normal; text-transform: none; letter-spacing: 0;
}
.controls .row { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
.ctl-group { display: grid; gap: .35rem; padding: .55rem 0; border-bottom: 1px solid var(--line); }
.ctl-group:last-of-type { border-bottom: 0; }
.ctl-label { font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
.ctl-note { color: var(--muted); font-size: .8rem; }
button.ctl, select.ctl, input.ctl {
  font: inherit; font-size: .85rem; padding: .45rem .7rem; border-radius: 9px;
  border: 1px solid var(--line); background: var(--surface); color: var(--fg); cursor: pointer;
}
button.ctl:hover, select.ctl:hover { border-color: var(--accent); color: var(--accent); }
button.ctl.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button.ctl.primary:hover { color: #fff; opacity: .92; }
details.nda { border: 1px solid var(--line); border-radius: 10px; padding: .5rem .7rem; margin-top: .6rem; }
details.nda summary { cursor: pointer; font-size: .85rem; }
details.nda .row { margin-top: .5rem; }
.ctl-status { color: var(--muted); font-size: .8rem; min-height: 1.2em; margin-top: .5rem; }
.ctl-status.ok { color: var(--present); }
.ctl-status.err { color: var(--flag); }
body.only-flags .chapter { display: none; }
body.only-flags .chapter.has-flags { display: block; }
body.only-flags .chip:not(.sev-2):not(.sev-3) { display: none; }
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #111318; --surface: #191c23; --fg: #e8eaf0; --muted: #9aa1ae;
    --line: #272b35; --neutral: #3a4050;
  }
  .kpi, .panel, .chapter, .artifact { box-shadow: none; }
  .ptext { background: #14161c; }
}
"""

_JS = """\
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


_DEFAULT_LABELS = {**EN_LABELS, **METRIC_LABELS["en"]}


def _label(labels: Optional[Mapping[str, str]], key: str) -> str:
    source = labels if labels else _DEFAULT_LABELS
    return source.get(key, _DEFAULT_LABELS.get(key, key))


def _tense_class(dominant: str) -> str:
    if dominant == TENSE_PRESENT:
        return "tense-present"
    if dominant == TENSE_PAST:
        return "tense-past"
    if dominant == TENSE_MIXED:
        return "tense-mixed"
    return "tense-neutral"


def _help(labels: Optional[Mapping[str, str]], key: str, text: str) -> str:
    """Wraps a term with a tooltip (help text from the language profile)."""
    tip = _label(labels, f"help_{key}")
    return f'<span class="help" data-help="{html.escape(tip, quote=True)}" tabindex="0">{text}</span>'


def _kpi(value: str, label: str) -> str:
    return f'<div class="kpi"><b>{value}</b><span>{label}</span></div>'


def render_dashboard(
    chapters: Sequence[ChapterProfile],
    paragraphs: Sequence[ParagraphProfile],
    metrics: Optional[Any] = None,
    artifacts: Optional[Sequence[Mapping[str, Any]]] = None,
    title: str = "Manuskript",
    labels: Optional[Mapping[str, str]] = None,
    language_name: str = "",
    tense_available: bool = True,
    engine_name: str = "Lixity",
    controls: bool = False,
    api_base: str = "/api",
    manuscript_name: str = "",
    current_language: str = "auto",
    language_options: Optional[Sequence] = None,
) -> str:
    """Renders the complete, deterministic single-file dashboard.

    ``controls=True`` adds the local control panel (buttons/dropdown/NDA),
    which triggers the CLI functions via the UI server (``scripts/ui_server.py``).
    """
    esc = html.escape
    L = lambda key: esc(_label(labels, key))  # noqa: E731
    if not language_options:
        language_options = [
            ("auto", "auto"), ("de", "Deutsch"), ("en", "English"), ("fr", "Français"),
            ("es", "Español"), ("it", "Italiano"), ("pt", "Português"), ("nl", "Nederlands"),
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
        parts.append(f'<input class="ctl" id="set-title" value="{esc(title)}" placeholder="{L("title")}"/>')
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
            f'{_help(labels, "export", L("export"))}</button>'
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
        parts.append(f'<input class="ctl" type="password" id="nda-passphrase" placeholder="{L("passphrase")}"/>')
        parts.append(
            f'<button class="ctl" id="nda-unlock-btn">{L("unlock")}</button>'
        )
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
        parts.append(_kpi(f"{metrics.dialog_ratio:.1f} %", _help(labels, "dialogue", L("dialogue"))))
    parts.append(_kpi(f"{function_pct:.1f} %", _help(labels, "function_words", L("function_words"))))
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

    # --- Toolbar ----------------------------------------------------------
    parts.append('<div class="toolbar">')
    parts.append(f'<label><input type="checkbox" id="filter-flags"/> {L("filter_flags")}</label>')
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
                tooltip = (
                    f"{p.line_label} · {p.dominant} · "
                    f"{_label(labels, 'present')} {p.present_hits} / "
                    f"{_label(labels, 'past')} {p.past_hits} · {p.severity_label}"
                )
                parts.append(
                    f'<button class="chip {_tense_class(p.dominant)}{sev}" '
                    f'style="flex:{width:.2f} 0 auto" data-target="p-{idx}" '
                    f'title="{esc(tooltip)}" aria-label="{esc(tooltip)}" aria-expanded="false"></button>'
                )
            parts.append("</div>")

            for idx, p in chapter_paras:
                parts.append(f'<div class="ptext" id="p-{idx}">')
                parts.append(
                    f'<div class="anchor">{L("line")} {p.start_line}–{p.end_line} · '
                    f"{esc(p.dominant)} · {esc(p.severity_label)}</div>"
                )
                parts.append(
                    f'<div class="stats">{L("present")} {p.present_hits} · {L("past")} {p.past_hits} · '
                    f"ASL {p.asl:.1f} · {L('dialogue')} {p.dialogue_pct:.1f} % · "
                    f"{L('function_words')} {p.function_word_pct:.1f} % · {p.words} {L('words')}</div>"
                )
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
        parts.append("</tr></thead><tbody>")
        for c in chapters:
            parts.append(
                f"<tr><td>{c.num}</td><td>{esc(c.title)}</td>"
                f'<td class="num">{c.words:,}</td><td class="num">{c.asl:.1f}</td>'
                f'<td class="num">{c.dialog_pct:.1f} %</td><td class="num">{c.function_word_pct:.1f} %</td>'
                f'<td>{esc(c.dominant)}</td><td class="num">{c.flagged}</td></tr>'
            )
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
