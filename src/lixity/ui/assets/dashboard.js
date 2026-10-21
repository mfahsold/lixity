function setFilter(input, bodyClass, on) {
  if (!input) return;
  input.checked = on;
  document.body.classList.toggle(bodyClass, on);
}

function activate(el) {
  // drill-down: carry the context filters on the way to the deeper level
  if (el.hasAttribute("data-review-passage")) {
    var clearSearch = document.getElementById("text-search-clear");
    var searchInput = document.getElementById("text-search");
    var resetFilters = document.getElementById("paragraph-filter-reset");
    if (clearSearch && searchInput && searchInput.value) clearSearch.click();
    if (resetFilters) resetFilters.click();
  }
  if (el.getAttribute("data-only") && layerOnly) setFilter(layerOnly, "layer-only", true);
  if (el.getAttribute("data-flags")) setFilter(document.getElementById("filter-flags"), "only-flags", true);
  if (el.matches("td.z[data-chapter]")) { jumpToChapter(el); return; }
  if (el.hasAttribute("data-line")) { jumpToLine(el); return; }
  var key = el.getAttribute("data-layer");
  if (key && layer) { layer.value = key; applyLayer(); }
  var jump = el.getAttribute("data-jump");
  var target = jump ? document.querySelector(jump) : null;
  if (target) scrollAndFlash(target);
}

function jumpToLine(row) {
  var line = parseInt(row.getAttribute("data-line"), 10);
  var targetId = row.getAttribute("data-target");
  var panel = targetId ? document.getElementById(targetId) : null;
  if (!panel) {
    var panels = document.querySelectorAll(".ptext[data-start]");
    for (var i = 0; i < panels.length; i++) {
      var start = parseInt(panels[i].getAttribute("data-start"), 10);
      var end = parseInt(panels[i].getAttribute("data-end"), 10);
      if (line >= start && line <= end) { panel = panels[i]; break; }
    }
  }
  if (panel) {
    var chip = document.querySelector('.chip[data-target="' + panel.id + '"]');
    if (chip) toggleParagraph(chip, true, true);
    scrollAndFlash(panel);
    if (row.hasAttribute("data-review-passage")) {
      panel.tabIndex = -1;
      panel.focus({preventScroll: true});
    }
    return;
  }
  var chapters = document.querySelectorAll(".chapter[data-start]");
  for (var j = 0; j < chapters.length; j++) {
    var cstart = parseInt(chapters[j].getAttribute("data-start"), 10);
    var cend = parseInt(chapters[j].getAttribute("data-end"), 10);
    if (line >= cstart && line <= cend) { scrollAndFlash(chapters[j]); return; }
  }
}

// Marker controls (add/resolve/note) live inside jumpable rows; activating
// them must open the note field only – never also scroll the page.
function isMarkerControl(el) {
  return !!el.closest("[data-marker-kind], [data-marker-resolve], .marker-note, .marker-note-slot");
}

// Unified interaction contract: every content drill-down is a [role="button"]
// (KPI tile, band row, loading bar, table row, heatmap cell) or carries
// data-jump / data-line. Native controls use <button>/<select>.
var INTERACTIVE = "[data-jump], [data-line], [role='button'], td.z[data-chapter]";

document.addEventListener("click", function (event) {
  var fold = event.target.closest("[data-chapter-toggle]");
  if (fold) { toggleChapter(fold); return; }
  var chip = event.target.closest(".chip");
  if (chip) { toggleParagraph(chip); return; }
  var target = event.target.closest(INTERACTIVE);
  if (target && !target.closest(".controls") && !isMarkerControl(event.target)) {
    activate(target);
  }
});
document.addEventListener("keydown", function (event) {
  if (event.defaultPrevented) return;
  if (event.key === "Escape") {
    // Dialogs and other workspace views own Escape while analysis is hidden.
    if (document.querySelector("dialog[open]")) return;
    var analysisPane = document.getElementById("view-pane-analysis");
    if (analysisPane && !analysisPane.classList.contains("active")) return;
    closeNoteField();
    document.querySelectorAll(".ptext.open").forEach(function (panel) {
      var chip = document.querySelector('.chip[data-target="' + panel.id + '"]');
      if (chip) toggleParagraph(chip, false);
      else panel.classList.remove("open");
    });
    return;
  }
  if (event.key !== "Enter" && event.key !== " ") return;
  var el = event.target.closest ? event.target.closest(INTERACTIVE) : null;
  if (el && el.tagName !== "BUTTON" && !el.closest(".controls") && !isMarkerControl(event.target)) {
    event.preventDefault();
    activate(el);
  }
});
var filter = document.getElementById("filter-flags");
if (filter) {
  filter.addEventListener("change", function () {
    document.body.classList.toggle("only-flags", filter.checked);
  });
}
// --- Manuscript search -------------------------------------------------
// The author could not search the manuscript itself, only the research
// archive. This filters the paragraph blocks in place: chapters without a
// match collapse away, matches are marked, and the arrows step through them.
(function () {
  var input = document.getElementById("text-search");
  if (!input) return;
  var status = document.getElementById("text-search-status");
  var prev = document.getElementById("text-search-prev");
  var next = document.getElementById("text-search-next");
  var clear = document.getElementById("text-search-clear");
  var hits = [];
  var cursor = -1;
  var restored = null;
  var query = "";

  var structuralText = new WeakMap();
  function unmark(paragraph) {
    if (paragraph.matches(".reader-structural")) {
      if (!structuralText.has(paragraph)) structuralText.set(paragraph, paragraph.textContent);
      paragraph.textContent = structuralText.get(paragraph);
    } else renderParagraphText(paragraph, "");
  }
  function mark(paragraph, query) {
    if (!paragraph.matches(".reader-structural")) { renderParagraphText(paragraph, query); return; }
    var text = structuralText.get(paragraph);
    var pattern = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i"), match = pattern.exec(text);
    if (!match) return;
    var index = match.index;
    var hit = document.createElement("mark"); hit.className = "text-hit"; hit.textContent = match[0];
    paragraph.replaceChildren(document.createTextNode(text.slice(0, index)), hit, document.createTextNode(text.slice(index + match[0].length)));
  }

  function apply(direction) {
    query = input.value.trim();
    hits = [];
    cursor = -1;
    var blocks = Array.prototype.slice.call(
      document.querySelectorAll("#chapters .ptext, #chapters .reader-structural")
    );
    if (query && restored === null) {
      restored = blocks.filter(function(block) { return block.classList.contains("open"); });
    }
    blocks.forEach(function (block) {
      var structural = block.matches(".reader-structural");
      var paragraph = structural ? block : block.querySelector("p");
      if (paragraph) unmark(paragraph);
      var content = structural ? [structuralText.get(block)] : paragraphContent[block.id];
      var match = Boolean(content) && Boolean(query)
        && new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i").test(content[0]);
      block.classList.toggle("text-miss", Boolean(query) && !match);
      var chip = paragraphChips[block.id];
      if (restored !== null && chip) {
        toggleParagraph(chip, !query && restored.indexOf(block) >= 0);
      }
      if (match) hits.push(block);
    });
    if (!query) restored = null;
    document.querySelectorAll("#chapters .chapter").forEach(function (chapter) {
      var any = chapter.querySelectorAll(".ptext:not(.text-miss), .reader-structural:not(.text-miss)").length > 0;
      chapter.classList.toggle("text-miss", Boolean(query) && !any);
    });
    document.body.classList.toggle("text-search-active", Boolean(query));
    if (prev) prev.hidden = !query;
    if (next) next.hidden = !query;
    if (clear) clear.hidden = !query;
    if (status) {
      if (!query) status.textContent = "";
      else if (!hits.length) status.textContent = uiLabel("text_search_none");
      else status.textContent = uiFormat("text_search_count", {
        matches: hits.length,
        paragraphs: blocks.length
      });
    }
    if (hits.length) {
      if (direction === -1) cursor = 0;
      step(direction === -1 ? -1 : 1);
    }
  }

  function step(direction) {
    if (!hits.length) return;
    if (window.LixityWorkbench && window.LixityWorkbench.state().surface === "overview") {
      window.LixityWorkbench.dispatch({type: "surface", value: "document"});
    }
    cursor = (cursor + direction + hits.length) % hits.length;
    var block = hits[cursor];
    rememberPassageLocation(block);
    var chip = paragraphChips[block.id];
    if (chip) toggleParagraph(chip, true, true);
    var paragraph = block.matches(".reader-structural") ? block : block.querySelector("p");
    if (paragraph) { unmark(paragraph); mark(paragraph, query); }
    scrollAndFlash(block, {block: "center"});
  }

  var pending = null;
  input.addEventListener("input", function () {
    if (pending) clearTimeout(pending);
    pending = setTimeout(function() { pending = null; apply(); }, 120);
  });
  input.addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
      event.preventDefault();
      if (pending) { clearTimeout(pending); pending = null; apply(event.shiftKey ? -1 : 1); }
      else step(event.shiftKey ? -1 : 1);
    }
    if (event.key === "Escape") { event.preventDefault(); clearTimeout(pending); pending = null; input.value = ""; apply(); }
  });
  if (next) next.addEventListener("click", function () { step(1); });
  if (prev) prev.addEventListener("click", function () { step(-1); });
  if (clear) clear.addEventListener("click", function () { clearTimeout(pending); pending = null; input.value = ""; apply(); input.focus(); });
})();

var paragraphReset = document.getElementById("paragraph-filter-reset");
if (paragraphReset) paragraphReset.addEventListener("click", function() {
  setFilter(filter, "only-flags", false);
  setFilter(layerOnly, "layer-only", false);
  if (layer) { layer.value = ""; applyLayer(); }
});
var microhint = document.getElementById("microhint");
if (microhint) {
  var dismissHint = function () {
    microhint.classList.add("gone");
    document.removeEventListener("click", dismissHint);
    window.clearTimeout(hintTimer);
  };
  var hintTimer = window.setTimeout(dismissHint, 9000);
  document.addEventListener("click", dismissHint);
}

var layer = document.getElementById("style-layer");
var layerLegend = document.getElementById("layer-legend");
var layerCutoff = layerLegend ? Number(layerLegend.dataset.cutoff) : Infinity;

function chipLayers(chip) {
  if (!chip._layers) {
    var raw = chip.getAttribute("data-layers");
    try { chip._layers = raw ? JSON.parse(raw) : {}; } catch (err) { chip._layers = {}; }
  }
  return chip._layers;
}

var layerOnly = document.getElementById("layer-only");
var layerNext = document.getElementById("layer-next");
var layerCount = document.getElementById("layer-legend-count");
var outlierCursor = 0;

function outlierChips() {
  return Array.prototype.slice.call(document.querySelectorAll(".chip.outlier"));
}

function paintLayerAction(panel, info) {
  var actions = panel.querySelector(".reader-paragraph-actions");
  if (!actions) return;
  var shown = document.body.classList.contains("workbench-analysis") && !document.body.classList.contains("workbench-overview");
  var notable = Boolean(shown && info && Math.abs(info[2]) >= layerCutoff);
  if (!actions._metricBase) actions._metricBase = {label: actions.getAttribute("aria-label"), help: actions.dataset.help};
  actions.setAttribute("aria-label", notable ? info[1] + " · " + actions._metricBase.label : actions._metricBase.label);
  actions.dataset.help = notable ? info[1] + " · " + actions._metricBase.help : actions._metricBase.help;
  if (notable) actions.dataset.layerSymbol = info[2] < 0 ? "↓" : "↑";
  else delete actions.dataset.layerSymbol;
}

function applyLayer() {
  var key = layer ? layer.value : "";
  document.body.classList.toggle("layer-on", !!key);
  document.querySelectorAll(".chip").forEach(function (chip) {
    var info = key ? chipLayers(chip)[key] : null;
    var panel = document.getElementById(chip.dataset.target);
    var notable = Boolean(info && Math.abs(info[2]) >= layerCutoff);
    if (info) {
      chip.style.setProperty("--layer-color", info[0]);
      chip.classList.add("has-layer");
      chip.setAttribute("data-tip", info[1]);
      chip.removeAttribute("title");
      chip.classList.toggle("outlier", notable);
      chip.setAttribute("aria-label", info[1]);
    } else {
      chip.style.removeProperty("--layer-color");
      chip.classList.remove("has-layer");
      chip.classList.remove("outlier");
      chip.removeAttribute("data-tip");
      var base = chip.getAttribute("data-tip-base");
      if (base) { chip.setAttribute("title", base); chip.setAttribute("aria-label", base); }
    }
    if (panel) {
      panel.classList.toggle("metric-notable", notable);
      if (notable) panel.style.setProperty("--paragraph-layer-color", info[0]);
      else panel.style.removeProperty("--paragraph-layer-color");
      paintLayerAction(panel, info);
    }
  });
  outlierCursor = 0;
  if (layerLegend) {
    layerLegend.hidden = !key;
    if (key && layer) {
      var option = layer.options[layer.selectedIndex];
      var title = document.getElementById("layer-legend-title");
      if (title) {
        title.textContent = option.textContent;
        var hint = option.getAttribute("data-hint") || "";
        if (hint) title.setAttribute("data-tip", hint);
        else title.removeAttribute("data-tip");
      }
      var comparable = Number(option.dataset.comparable);
      var count = outlierChips().length;
      if (layerCount) {
        layerCount.textContent = comparable ? uiFormat("layer_coverage", {
          notable: count, comparable: comparable, total: layerLegend.dataset.profiled
        }) : uiLabel("layer_unavailable");
      }
      if (layerNext) layerNext.disabled = count === 0;
      if (layerOnly) layerOnly.disabled = comparable === 0;
      if (comparable === 0) setFilter(layerOnly, "layer-only", false);
    }
  }
  document.dispatchEvent(new CustomEvent("lixity:analysis-layer-change"));
}

if (layerOnly) {
  layerOnly.addEventListener("change", function () {
    document.body.classList.toggle("layer-only", layerOnly.checked);
  });
}
if (layerNext) {
  layerNext.addEventListener("click", function () {
    var chips = outlierChips();
    if (!chips.length) return;
    if (outlierCursor >= chips.length) outlierCursor = 0;
    var chip = chips[outlierCursor++];
    toggleParagraph(chip, true, true);
    scrollAndFlash(document.getElementById(chip.dataset.target) || chip);
  });
}

function jumpToChapter(cell) {
  var key = cell.getAttribute("data-layer");
  if (key && layer) {
    layer.value = key;
    applyLayer();
  }
  var section = document.getElementById("ch-" + cell.getAttribute("data-chapter"));
  if (!section) return;
  scrollAndFlash(section);
}

if (layer) {
  layer.addEventListener("change", applyLayer);
  applyLayer();
}
var layerClear = document.getElementById("layer-clear");
if (layerClear) layerClear.addEventListener("click", function() {
  if (layer) layer.value = "";
  setFilter(layerOnly, "layer-only", false);
  applyLayer();
  if (layer) layer.focus({preventScroll: true});
});
document.addEventListener("lixity:reader-ready", applyLayer);
document.addEventListener("lixity:workbench-change", function() {
  document.querySelectorAll("#chapters .ptext.metric-notable").forEach(function(panel) {
    var chip = paragraphChips[panel.id];
    paintLayerAction(panel, chip && layer ? chipLayers(chip)[layer.value] : null);
  });
});
async function jsonApi(url, options, responseType) {
  var t0 = performance.now();
  try {
    var response = await fetch(url, options);
    var data;
    if (response.ok && responseType === "markdown") {
      if (!/^text\/(markdown|plain)\b/i.test(response.headers.get("Content-Type") || "")) {
        throw new Error(uiLabel("research_matrix_failed"));
      }
      data = {ok: true, text: await response.text()};
    } else data = await response.json();
    if (!data || typeof data !== "object" || Array.isArray(data)) data = {ok: false};
    if (!response.ok) data.ok = false;
    data.http_status = response.status;
    LixityLog.api(options && options.method || "GET", url, performance.now() - t0, response.status, data);
    return data;
  } catch (error) {
    return {ok: false, message: String(error), http_status: 0};
  }
}

function markerApi(payload) {
  return jsonApi(API + "/marker-" + payload._action, {method: "POST",
    headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
}
function closeNoteField() {
  var editor = document.querySelector("[data-marker-editor]");
  if (!editor || editor.dataset.pending === "1") return;
  var trigger = editor._markerTrigger;
  editor.remove();
  if (trigger && trigger.isConnected) trigger.focus();
}

function openNoteField(button) {
  var previous = document.querySelector("[data-marker-editor]");
  if (previous) {
    var draft = previous.querySelector(".marker-note");
    if (previous.dataset.pending === "1" || draft.value || previous._markerTrigger === button) {
      if (!draft.disabled) draft.focus();
      return;
    }
    closeNoteField();
  }
  var row = button.closest(".marker-row");
  var slot = row && row.querySelector(".marker-note-slot");
  if (!slot) return;
  var editor = document.createElement("span");
  editor.dataset.markerEditor = "1";
  editor._markerTrigger = button;
  var input = document.createElement("input");
  input.className = "ctl marker-note visible";
  input.type = "text";
  input.placeholder = slot.dataset.placeholder || "";
  input.setAttribute("aria-label", input.placeholder);
  var save = document.createElement("button");
  save.type = "button";
  save.className = "ctl";
  save.dataset.markerSave = "1";
  save.textContent = uiLabel("marker_save");
  var cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "ctl";
  cancel.dataset.markerCancel = "1";
  cancel.textContent = uiLabel("modal_cancel");
  var feedback = document.createElement("span");
  feedback.className = "ctl-status";
  feedback.dataset.markerFeedback = "1";
  feedback.setAttribute("role", "status");
  feedback.setAttribute("aria-live", "polite");
  feedback.hidden = true;
  editor.append(input, save, cancel, feedback);
  slot.appendChild(editor);
  input.focus();
  async function submit() {
    if (editor.dataset.pending === "1") return;
    editor.dataset.pending = "1";
    save.disabled = input.disabled = cancel.disabled = true;
    save.setAttribute("aria-busy", "true");
    feedback.hidden = false;
    feedback.className = "ctl-status";
    feedback.textContent = uiLabel("marker_saving");
    var data = await markerApi({_action: "add", kind: button.dataset.markerKind,
      line: parseInt(button.dataset.line, 10), note: input.value.trim()});
    if (!editor.isConnected) return;
    delete editor.dataset.pending;
    save.disabled = input.disabled = cancel.disabled = false;
    save.removeAttribute("aria-busy");
    feedback.className = "ctl-status " + (data.ok ? "ok" : "err");
    feedback.textContent = data.ok ? uiLabel("marker_saved") :
      uiFormat("marker_save_failed", {reason: data.message || uiLabel("wizard_unknown_error")});
    if (data.ok) { save.disabled = true; input.disabled = true; }
    else input.focus();
  }
  save.addEventListener("click", submit);
  cancel.addEventListener("click", closeNoteField);
  input.addEventListener("keydown", function(event) {
    if (event.key === "Escape") { event.preventDefault(); closeNoteField(); }
    if (event.key === "Enter") { event.preventDefault(); submit(); }
  });
}

document.addEventListener("click", async function(event) {
  var add = event.target.closest("[data-marker-kind]");
  if (add) { openNoteField(add); return; }
  var resolve = event.target.closest("[data-marker-resolve]");
  if (!resolve || resolve.disabled) return;
  resolve.disabled = true;
  resolve.setAttribute("aria-busy", "true");
  var feedback = resolve.parentElement.querySelector("[data-marker-resolve-feedback]");
  if (!feedback) {
    feedback = document.createElement("span");
    feedback.dataset.markerResolveFeedback = "1";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    resolve.after(feedback);
  }
  feedback.textContent = uiLabel("marker_saving");
  var data = await markerApi({_action: "resolve", id: resolve.dataset.markerResolve});
  resolve.removeAttribute("aria-busy");
  resolve.disabled = Boolean(data.ok);
  feedback.className = "ctl-status " + (data.ok ? "ok" : "err");
  feedback.textContent = data.ok ? uiLabel("marker_saved") :
    uiFormat("marker_save_failed", {reason: data.message || uiLabel("wizard_unknown_error")});
});
var API = document.body.dataset.api || "";
var UI_LABELS = {};
try { UI_LABELS = JSON.parse(document.body.dataset.uiLabels || "{}"); } catch (_) { UI_LABELS = {}; }
function uiLabel(key) { return UI_LABELS[key] || key; }
function uiFormat(key, values) {
  return uiLabel(key).replace(/\{([a-z_]+)\}/g, function(match, name) {
    return Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match;
  });
}
function uiCountFormat(key, count, values) {
  // A count of one picks the "<key>_one" row when the pack provides it.
  var singular = key + "_one";
  var chosen = count === 1 && Object.prototype.hasOwnProperty.call(UI_LABELS, singular) ? singular : key;
  var payload = values || {};
  if (!Object.prototype.hasOwnProperty.call(payload, "count")) payload.count = count;
  return uiFormat(chosen, payload);
}
var welcomeHero = document.getElementById("welcome-hero");
var welcomeDismiss = document.getElementById("welcome-dismiss");
var welcomeShow = document.getElementById("welcome-show");
if (welcomeHero && welcomeDismiss && welcomeShow) {
  var welcomeStorageKey = "lixity:welcome-dismissed";
  var welcomeWasDismissed = false;
  var welcomeInitiallyVisible = !welcomeHero.hidden;
  try { welcomeWasDismissed = localStorage.getItem(welcomeStorageKey) === "1"; } catch (_) { /* Storage may be unavailable. */ }
  function setWelcomeVisible(visible, focusTarget) {
    welcomeHero.hidden = !visible;
    welcomeShow.hidden = visible;
    welcomeShow.setAttribute("aria-expanded", String(visible));
    if (focusTarget) (visible ? welcomeDismiss : welcomeShow).focus();
  }
  setWelcomeVisible(welcomeInitiallyVisible && !welcomeWasDismissed, false);
  welcomeDismiss.addEventListener("click", function() {
    setWelcomeVisible(false, true);
    try { localStorage.setItem(welcomeStorageKey, "1"); } catch (_) { /* Keep this page usable without storage. */ }
  });
  welcomeShow.addEventListener("click", function() {
    setWelcomeVisible(true, true);
    try { localStorage.removeItem(welcomeStorageKey); } catch (_) { /* Keep this page usable without storage. */ }
  });
}
(function initManuscriptPdf() {
  var form = document.getElementById("manuscript-pdf-form");
  if (!form) return;
  var layout = document.getElementById("manuscript-pdf-layout");
  var button = document.getElementById("manuscript-pdf-download");
  var status = document.getElementById("manuscript-pdf-status");
  var available = form.dataset.available === "true" && !!form.dataset.projectToken;
  var busy = false;
  function message(key, failed) {
    status.className = "ctl-status " + (failed ? "err" : "ok");
    status.textContent = uiLabel(key);
  }
  function pending(value) {
    busy = value;
    form.setAttribute("aria-busy", String(value));
    button.setAttribute("aria-busy", String(value));
    layout.disabled = button.disabled = value || !available;
  }
  form.addEventListener("submit", async function(event) {
    event.preventDefault();
    if (busy || !available) return;
    var selected = layout.value;
    if (!Array.from(layout.options).some(function(option) { return option.value === selected && !option.disabled; })) return;
    pending(true);
    message("manuscript_pdf_busy", false);
    var reason = "";
    try {
      var response = await fetch(API + "/manuscript-pdf", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({layout: selected, project_token: form.dataset.projectToken})
      });
      if (!response.ok) {
        try {
          var errorBody = await response.json();
          if (typeof errorBody.message === "string") reason = errorBody.message;
        } catch (_) { /* Keep the localized failure message. */ }
        throw new Error("Manuscript PDF unavailable");
      }
      if ((response.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase() !== "application/pdf") {
        throw new Error("Manuscript PDF unavailable");
      }
      var blob = await response.blob();
      if ((await blob.slice(0, 5).text()) !== "%PDF-") throw new Error("Manuscript PDF unavailable");
      var url = URL.createObjectURL(blob);
      var download = document.createElement("a");
      download.href = url;
      download.download = "manuscript-" + selected + ".pdf";
      document.body.appendChild(download);
      download.click();
      download.remove();
      setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
      message("manuscript_pdf_success", false);
    } catch (_) {
      message("manuscript_pdf_error", true);
      if (reason) status.textContent += " " + reason;
    } finally { pending(false); }
  });
  pending(false);
})();
(function initNdaDraft() {
  var form = document.getElementById("nda-draft-form");
  if (!form) return;
  var preview = document.getElementById("nda-draft-preview");
  var previewWrap = document.getElementById("nda-preview-wrap");
  var status = document.getElementById("nda-draft-status");
  var pdfButton = document.getElementById("nda-pdf-btn");
  var textButton = document.getElementById("nda-text-btn");
  var busy = false;
  var fields = ["name", "address", "project_name", "date", "place"];
  var dateInput = form.elements.namedItem("date");
  if (dateInput && !dateInput.value) {
    var today = new Date();
    dateInput.value = today.getFullYear() + "-" + String(today.getMonth() + 1).padStart(2, "0")
      + "-" + String(today.getDate()).padStart(2, "0");
  }

  function message(key, failed) {
    status.className = "ctl-status " + (failed ? "err" : "ok");
    status.textContent = uiLabel(key);
  }
  function pending(value) {
    busy = value;
    form.setAttribute("aria-busy", String(value));
    form.querySelectorAll("input, textarea, button").forEach(function(control) { control.disabled = value; });
  }
  async function generate(format, showPreview) {
    if (busy || !form.reportValidity()) return;
    var payload = {format: format};
    fields.forEach(function(key) { payload[key] = form.elements.namedItem(key).value.trim(); });
    var missing = fields.find(function(key) { return key !== "address" && !payload[key]; });
    if (missing) {
      message("nda_draft_required", true);
      form.elements.namedItem(missing).focus();
      return;
    }
    pending(true);
    message("nda_draft_working", false);
    var reason = "";
    try {
      var response = await fetch(API + "/nda-draft", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        try {
          var errorBody = await response.json();
          if (typeof errorBody.message === "string") reason = errorBody.message;
        } catch (_) { /* Keep the localized failure message. */ }
        throw new Error("NDA draft unavailable");
      }
      var contentType = response.headers.get("Content-Type") || "";
      if (!contentType.startsWith(format === "pdf" ? "application/pdf" : "text/plain")) {
        throw new Error("NDA draft unavailable");
      }
      if (showPreview) {
        preview.textContent = await response.text();
        previewWrap.hidden = false;
        message("nda_draft_ready", false);
      } else {
        var url = URL.createObjectURL(await response.blob());
        var download = document.createElement("a");
        download.href = url;
        download.download = format === "pdf" ? "nda.pdf" : "nda.txt";
        document.body.appendChild(download);
        download.click();
        download.remove();
        setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
        message("nda_draft_downloaded", false);
      }
    } catch (_) {
      // Neither submitted personal details nor returned agreement text are logged.
      message("nda_draft_failed", true);
      if (reason) status.textContent += " " + reason;
    } finally { pending(false); }
  }
  form.addEventListener("submit", function(event) {
    event.preventDefault();
    generate("text", true);
  });
  form.addEventListener("input", function() {
    preview.textContent = "";
    previewWrap.hidden = true;
    status.textContent = "";
  });
  pdfButton.addEventListener("click", function() { generate("pdf", false); });
  textButton.addEventListener("click", function() { generate("text", false); });
  pending(false);
})();
var settingsForm = document.getElementById("settings-form");
if (settingsForm) {
  settingsForm.addEventListener("input", function() {
    settingsForm.querySelectorAll("input").forEach(function(input) { input.setCustomValidity(""); });
  });
  settingsForm.addEventListener("submit", function(event) {
    event.preventDefault();
    submitSettings();
  });
  document.getElementById("settings-reset").addEventListener("click", function() {
    settingsForm.querySelectorAll("[data-default]").forEach(function(input) {
      input.value = input.dataset.default;
      input.setCustomValidity("");
    });
    document.getElementById("settings-thresholds").open = true;
  });
}
var fdrFilter = document.getElementById("heatmap-fdr-only");
if (fdrFilter) {
  fdrFilter.addEventListener("change", function() {
    if (window.LixityAnalysisScope) { window.LixityAnalysisScope.apply(); return; }
    var visible = 0;
    document.querySelectorAll("#heatmap tbody tr[data-fdr-count]").forEach(function(row) {
      row.hidden = fdrFilter.checked && Number(row.dataset.fdrCount) === 0;
      if (!row.hidden) visible++;
    });
    document.getElementById("heatmap-empty").hidden = visible > 0;
  });
}
async function runAction(action, payload, button, canReload, acceptResponse) {
  var status = document.getElementById("ctl-status");
  if (status) {
    status.className = "ctl-status";
    status.textContent = "…";
  }
  if (button) { button.disabled = true; button.classList.add("busy"); button.setAttribute("aria-busy", "true"); }
  var t0 = performance.now();
  var url = API + "/" + action;
  try {
    var res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {})
    });
    var data = await res.json();
    if (!res.ok) data.ok = false;
    LixityLog.api("POST", url, performance.now() - t0, res.status, data);
    if (acceptResponse && !acceptResponse()) return data;
    if (status) {
      status.className = "ctl-status " + (data.ok ? "ok" : "err");
      status.textContent = (data.ok ? "✓ " : "✗ ") + (data.message || "");
    }
    if (data.ok && data.reload) {
      setTimeout(function () { if (!canReload || canReload()) location.reload(); }, 1200);
    }
    return data;
  } catch (err) {
    if (acceptResponse && !acceptResponse()) return {ok: false, message: String(err)};
    LixityLog.error("runAction (" + action + ") error:", err);
    if (status) {
      status.className = "ctl-status err";
      status.textContent = "✗ " + err;
    }
    return { ok: false, message: String(err) };
  } finally {
    if (button) { button.disabled = false; button.classList.remove("busy"); button.removeAttribute("aria-busy"); }
  }
}
async function submitSettings() {
  var settings = document.getElementById("settings-form");
  if (!settings) return;
  var button = settings.querySelector('[data-action="settings"]');
  if (button.disabled) return;
  var payload = {};
  var mild = document.getElementById("set-z-mild");
  var strong = document.getElementById("set-z-strong");
  settings.querySelectorAll("input[type=number]").forEach(function(input) {
    var value = input.valueAsNumber;
    var excluded = (input.dataset.minExclusive === "true" && value <= Number(input.min)) ||
      (input.dataset.maxExclusive === "true" && value >= Number(input.max));
    input.setCustomValidity(excluded ? input.dataset.boundError || input.title || uiLabel("settings_bound_error") : "");
  });
  strong.setCustomValidity(strong.valueAsNumber < mild.valueAsNumber
    ? document.getElementById("settings-order-error").textContent : "");
  if (window.LixityRegisterSettings) Object.assign(payload, window.LixityRegisterSettings.readChanges());
  if (!settings.checkValidity()) {
    var invalid = settings.querySelector(":invalid");
    var disclosure = invalid && invalid.closest("details");
    if (disclosure) disclosure.open = true;
    settings.reportValidity();
    return;
  }
  payload.language = document.getElementById("set-language").value;
  var title = document.getElementById("set-title");
  if (title.value !== settings.dataset.titleInitial) payload.title = title.value;
  var zm = document.getElementById("set-z-mild");
  var zs = document.getElementById("set-z-strong");
  var fq = document.getElementById("set-fdr-q");
  var fs = document.getElementById("set-flag-min-sev");
  var dt = document.getElementById("set-dim-threshold");
  if (zm) payload.z_mild = parseFloat(zm.value);
  if (zs) payload.z_strong = parseFloat(zs.value);
  if (fq) payload.fdr_q = parseFloat(fq.value);
  var fm = document.getElementById("set-fdr-method");
  if (fm) payload.fdr_method = fm.value;
  if (fs) payload.flag_min_severity = parseInt(fs.value, 10);
  if (dt) payload.dim_score_threshold = parseFloat(dt.value);
  var author = document.getElementById("set-author-name");
  var authorEnabled = author && author.dataset.authorSettingEnabled === "true";
  if (authorEnabled && author.value.trim() !== settings.dataset.authorInitial) {
    payload.author_name = author.value.trim();
    author.disabled = true;
  }
  var publication = {};
  settings.querySelectorAll("[data-publication-key]").forEach(function(field) {
    publication[field.dataset.publicationKey] = field.type === "checkbox" ? field.checked : field.value;
  });
  var initialPublication = JSON.parse(settings.dataset.publicationInitial || "{}");
  var samePublication = Object.keys(publication).every(function(key) { return publication[key] === initialPublication[key]; });
  if (settings.dataset.publicationEditable === "true" && !samePublication) payload.publication = publication;
  var submittedToken = settings.dataset.projectToken || "";
  var acceptedToken = submittedToken;
  if (submittedToken) payload.project_token = submittedToken;
  var saveDefaults = document.getElementById("set-save-analysis-defaults");
  if (saveDefaults && !saveDefaults.disabled && saveDefaults.checked) payload.save_analysis_defaults = true;
  var identifiers = Array.from(settings.querySelectorAll("input, textarea, select")).map(function(field) { return field.id; });
  var submitted = fieldSnapshot(identifiers);
  function sameContext() { return settings.isConnected && settings.dataset.projectToken === acceptedToken; }
  function unchanged() {
    var currentIds = Array.from(settings.querySelectorAll("input, textarea, select")).map(function(field) { return field.id; });
    return sameContext() && JSON.stringify(currentIds) === JSON.stringify(identifiers) &&
      JSON.stringify(fieldSnapshot(identifiers)) === JSON.stringify(submitted);
  }
  try {
    var result = await runAction("settings", payload, button, unchanged, sameContext);
    if (result.ok && sameContext()) {
      if (/^[a-f0-9]{64}$/.test(result.project_token || "")) {
        acceptedToken = result.project_token;
        settings.dataset.projectToken = acceptedToken;
      }
      if (Object.prototype.hasOwnProperty.call(payload, "title")) settings.dataset.titleInitial = payload.title;
      if (Object.prototype.hasOwnProperty.call(payload, "author_name")) settings.dataset.authorInitial = payload.author_name;
      if (payload.publication) settings.dataset.publicationInitial = JSON.stringify(payload.publication);
      if (payload.register_profiles && window.LixityRegisterSettings) window.LixityRegisterSettings.accepted({
        register_profiles: payload.register_profiles, chapter_registers: payload.chapter_registers
      });
    }
    return result;
  }
  finally { if (authorEnabled) author.disabled = false; }
}
document.querySelectorAll("[data-action]").forEach(function (btn) {
  btn.addEventListener("click", function () {
    if (btn.dataset.payload === "settings") return;
    var payload = {};
    if (btn.dataset.payload === "format") {
      payload.format = document.getElementById("fmt").value;
    }
    if (btn.dataset.payload === "load") {
      var input = document.getElementById("ms-file");
      if (!input.files || !input.files.length) {
        manuscriptFileError();
        return;
      }
      var file = input.files[0];
      if (!supportedManuscriptFile(file)) { manuscriptFileError(); return; }
      btn.disabled = true;
      btn.classList.add("busy");
      btn.setAttribute("aria-busy", "true");
      var reader = new FileReader();
      reader.onload = function () {
        runAction("load", { name: file.name, content: reader.result }, btn);
      };
      reader.onerror = function () {
        manuscriptFileError("manuscript_read_failed");
        btn.disabled = false;
        btn.classList.remove("busy");
        btn.removeAttribute("aria-busy");
      };
      reader.readAsText(file);
      return;
    }
    runAction(btn.dataset.action, payload, btn);
  });
});

