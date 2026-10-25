function setFilter(input, bodyClass, on) {
  if (!input) return;
  input.checked = on;
  document.body.classList.toggle(bodyClass, on);
}

function selectAnalysisMetric(key) {
  if (!layer) return;
  // Chapter-only measurements intentionally clear a previous paragraph layer.
  layer.value = key || "";
  layer.dispatchEvent(new Event("change", {bubbles: true}));
}

function activate(el) {
  if (el.hasAttribute("data-metric-feature") && window.LixityMetricContext &&
      window.LixityMetricContext.open(el)) return;
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
  if (el.hasAttribute("data-layer")) selectAnalysisMetric(key);
  var jump = el.getAttribute("data-jump");
  var target = jump ? document.querySelector(jump) : null;
  if (target && key && target.closest("#chapters")) rememberPassageLocation(target);
  if (target) scrollAndFlash(target, {analysisVisible: el.hasAttribute("data-layer") ? true : undefined});
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
var layerPrevious = document.getElementById("layer-prev");
var layerNext = document.getElementById("layer-next");
var layerPosition = document.getElementById("layer-position");
var layerCount = document.getElementById("layer-legend-count");
var comparisonToggle = document.getElementById("analysis-comparison-enabled");
var layerOutliers = [];

function outlierChips() {
  return layerOutliers;
}

function currentOutlierPassage() {
  var selection = window.getSelection();
  var node = selection && !selection.isCollapsed && selection.focusNode;
  var element = node && (node.nodeType === 1 ? node : node.parentElement);
  var selected = element && element.closest("#chapters .ptext");
  if (selected) return selected;
  var focused = document.activeElement && document.activeElement.closest("#chapters .ptext");
  if (focused) {
    var bounds = focused.getBoundingClientRect();
    var controls = document.getElementById("manuscript-reader-controls");
    var boundary = controls ? controls.getBoundingClientRect().bottom : 0;
    if (bounds.height > 0 && bounds.bottom > boundary && bounds.top < innerHeight) return focused;
  }
  var anchor = window.LixityReader && window.LixityReader.capture();
  if (anchor) return anchor.panel;
  // Standalone reports use the same navigation without the continuous reader.
  return Array.prototype.find.call(document.querySelectorAll("#chapters .ptext.open"), function(panel) {
    var bounds = panel.getBoundingClientRect();
    return bounds.height > 0 && bounds.bottom > 0 && bounds.top < innerHeight;
  }) || null;
}

function syncOutlierNavigation() {
  var chips = outlierChips(), panel = chips.length ? currentOutlierPassage() : null;
  var position = panel ? chips.findIndex(function(chip) { return chip.dataset.target === panel.id; }) + 1 : 0;
  if (layerPosition) {
    var text = position + " / " + chips.length;
    if (layerPosition.textContent !== text) layerPosition.textContent = text;
    if (UI_LABELS) {
      var description = uiFormat("layer_position", {current: position, total: chips.length});
      if (layerPosition.getAttribute("aria-label") !== description) {
        layerPosition.setAttribute("aria-label", description);
        layerPosition.title = description;
      }
    }
  }
  var disabled = !chips.length || !layer || !layer.value || Boolean(comparisonToggle && !comparisonToggle.checked);
  if (layerPrevious) layerPrevious.disabled = disabled;
  if (layerNext) layerNext.disabled = disabled;
}

function stepOutlier(direction) {
  var chips = outlierChips();
  if (!chips.length) return;
  var panel = currentOutlierPassage();
  var candidates = direction < 0 ? chips.slice().reverse() : chips;
  var chip = panel && candidates.find(function(candidate) {
    var target = document.getElementById(candidate.dataset.target);
    return target && Boolean(panel.compareDocumentPosition(target) & (direction < 0 ? 2 : 4));
  });
  chip = chip || candidates[0];
  var target = document.getElementById(chip.dataset.target);
  // A selection supplies the first origin, then the new passage owns later steps.
  var selection = window.getSelection();
  if (selection && !selection.isCollapsed) selection.removeAllRanges();
  toggleParagraph(chip, true, true);
  rememberPassageLocation(target);
  scrollAndFlash(target || chip, {analysisVisible: true});
  syncOutlierNavigation();
}

function paintLayerAction(panel, info) {
  var actions = panel.querySelector(".reader-paragraph-actions");
  if (!actions) return;
  var shown = document.body.classList.contains("workbench-analysis") && !document.body.classList.contains("workbench-overview") &&
    !document.body.classList.contains("reader-focus") && (!comparisonToggle || comparisonToggle.checked);
  var notable = Boolean(shown && info && Math.abs(info[2]) >= layerCutoff);
  if (!actions._metricBase) actions._metricBase = {label: actions.getAttribute("aria-label"), help: actions.dataset.help};
  actions.setAttribute("aria-label", notable ? info[1] + " · " + actions._metricBase.label : actions._metricBase.label);
  actions.dataset.help = notable ? info[1] + " · " + actions._metricBase.help : actions._metricBase.help;
  if (notable) actions.dataset.layerSymbol = info[2] < 0 ? "↓" : "↑";
  else delete actions.dataset.layerSymbol;
  var marker = panel.querySelector(":scope > .reader-comparison-value");
  if (!marker && notable && info[3] !== undefined) {
    marker = document.createElement("button"); marker.type = "button";
    marker.className = "reader-comparison-value";
    marker.addEventListener("click", function() {
      if (window.LixityAnalysisEvidence && LixityAnalysisEvidence.available()) LixityAnalysisEvidence.inspect(panel, marker);
      else actions.click();
    });
    panel.prepend(marker);
  }
  if (marker) {
    marker.hidden = !notable;
    if (notable) {
      marker.textContent = actions.dataset.layerSymbol + " " + info[3];
      marker.setAttribute("aria-label", info[1] + ". " + uiLabel("evidence_inspect"));
      marker.title = info[1];
    }
  }
}

function syncEvidenceLegend() {
  var legend = document.getElementById("layer-evidence-legend");
  var toggle = document.getElementById("analysis-evidence-enabled");
  if (legend) legend.hidden = !toggle || !toggle.checked;
  var comparison = document.getElementById("layer-comparison-legend");
  if (comparison) comparison.hidden = comparisonToggle && !comparisonToggle.checked;
  if (layerLegend) layerLegend.hidden = !layer || !layer.value || Boolean(legend && legend.hidden && comparison && comparison.hidden);
}

function applyLayer() {
  var key = layer ? layer.value : "";
  var comparing = !!key && (!comparisonToggle || comparisonToggle.checked);
  document.body.classList.toggle("layer-on", !!key);
  document.body.classList.toggle("comparison-on", comparing);
  document.querySelectorAll(".chip").forEach(function (chip) {
    var info = key ? chipLayers(chip)[key] : null;
    var panel = document.getElementById(chip.dataset.target);
    var notable = Boolean(info && Math.abs(info[2]) >= layerCutoff);
    if (info && comparing) {
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
  layerOutliers = Array.prototype.slice.call(document.querySelectorAll(".chip.outlier"));
  if (layerLegend) {
    layerLegend.hidden = !key;
    if (key && layer) {
      var option = layer.options[layer.selectedIndex];
      var title = document.getElementById("layer-legend-title");
      var hint = option.getAttribute("data-hint") || "";
      if (title) {
        title.textContent = option.dataset.unit ? option.textContent + " · " + option.dataset.unit : option.textContent;
        if (hint) title.setAttribute("data-tip", hint);
        else title.removeAttribute("data-tip");
      }
      var comparisonHint = document.getElementById("layer-comparison-hint");
      if (comparisonHint) comparisonHint.textContent = hint;
      var evidenceHint = document.getElementById("layer-evidence-hint");
      if (evidenceHint) evidenceHint.textContent = uiFormat("legend_counted_text_hint", {metric: option.textContent});
      var comparable = Number(option.dataset.comparable);
      var count = outlierChips().length;
      if (layerCount) {
        layerCount.textContent = comparable ? uiFormat("layer_coverage", {
          notable: count, comparable: comparable, total: layerLegend.dataset.profiled
        }) : uiLabel("layer_unavailable");
      }
      if (layerOnly) layerOnly.disabled = comparable === 0 || !comparing;
      if (comparable === 0 || !comparing) setFilter(layerOnly, "layer-only", false);
    }
  }
  syncOutlierNavigation();
  syncEvidenceLegend();
  document.dispatchEvent(new CustomEvent("lixity:analysis-layer-change"));
}

var evidenceLegendToggle = document.getElementById("analysis-evidence-enabled");
if (evidenceLegendToggle) evidenceLegendToggle.addEventListener("change", syncEvidenceLegend);
if (comparisonToggle) comparisonToggle.addEventListener("change", applyLayer);

if (layerOnly) {
  layerOnly.addEventListener("change", function () {
    document.body.classList.toggle("layer-only", layerOnly.checked);
  });
}
if (layerPrevious) layerPrevious.addEventListener("click", function() { stepOutlier(-1); });
if (layerNext) layerNext.addEventListener("click", function() { stepOutlier(1); });
var outlierFrame = null;
function scheduleOutlierNavigation() {
  if (outlierFrame !== null) return;
  outlierFrame = requestAnimationFrame(function() { outlierFrame = null; syncOutlierNavigation(); });
}
var outlierScrollTimer = null;
document.addEventListener("scroll", function() {
  clearTimeout(outlierScrollTimer);
  outlierScrollTimer = setTimeout(scheduleOutlierNavigation, 120);
}, {capture: true, passive: true});
document.addEventListener("scrollend", function() {
  clearTimeout(outlierScrollTimer); scheduleOutlierNavigation();
}, {capture: true, passive: true});
document.addEventListener("selectionchange", scheduleOutlierNavigation);
document.addEventListener("focusin", scheduleOutlierNavigation);

function jumpToChapter(cell) {
  var key = cell.getAttribute("data-layer");
  if (cell.hasAttribute("data-layer")) selectAnalysisMetric(key);
  var section = document.getElementById("ch-" + cell.getAttribute("data-chapter"));
  if (!section) return;
  rememberPassageLocation(section);
  scrollAndFlash(section, {analysisVisible: cell.hasAttribute("data-layer") ? true : undefined});
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
  syncOutlierNavigation();
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
function reportSiteExport(stage, details) {
  details = details || {};
  var receipt = {export_id:details.export_id || null, stage:stage, error_name:details.error_name || null};
  if (details.profile_count != null) receipt.profile_count = details.profile_count;
  if (details.http_status != null) receipt.http_status = details.http_status;
  if (receipt.error_name && window.LixityLog) window.LixityLog.error("Website export", receipt);
  fetch(API + "/site-export-report", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body:JSON.stringify(receipt), keepalive:true,
  }).then(function(response) {
    if (!response.ok && window.LixityLog) window.LixityLog.warn("Export receipt rejected", response.status);
  }).catch(function() {
    if (window.LixityLog) window.LixityLog.warn("Export receipt could not reach the application");
  });
}
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
document.addEventListener("lixity:reader-ready", function initAnalysisGuide() {
  var guide = document.getElementById("reader-analysis-guide");
  var status = document.getElementById("reader-analysis-guide-state");
  var metric = document.getElementById("style-layer");
  if (!guide || !status || !metric || !window.LixityWorkbench) return;
  function update() {
    var state = LixityWorkbench.state();
    guide.hidden = state.surface !== "document" || state.focus;
    var key = !state.analysisVisible ? "analysis_guide_off" :
      !metric.value ? "analysis_guide_none" : "analysis_guide_selected";
    var option = metric.options[metric.selectedIndex];
    status.textContent = uiFormat(key, {metric:option.textContent, unit:option.dataset.unit || ""});
  }
  document.addEventListener("lixity:workbench-change", update);
  document.addEventListener("lixity:analysis-layer-change", update);
  update();
}, {once:true});
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
(function initSiteExport() {
  var open = document.getElementById("btn-site-export");
  var dialog = document.getElementById("modal-site-export");
  if (!open || !dialog || window.LixitySite.readOnly) return;
  var form = document.getElementById("site-export-form");
  var research = document.getElementById("site-export-research");
  var sources = document.getElementById("site-export-sources");
  var mode = document.getElementById("site-export-mode");
  var profile = document.getElementById("site-export-profile");
  var profileState = document.getElementById("site-export-profile-state");
  var profileDraft = document.getElementById("site-export-profile-draft");
  var editProfiles = document.getElementById("site-export-edit-profiles");
  var cap = document.getElementById("site-export-max-chapter");
  var downloadButton = document.getElementById("site-export-download");
  var checkButton = document.getElementById("site-export-check");
  var preflightResult = document.getElementById("site-export-preflight");
  var selectionSerial = 0;
  function invalidatePreflight() {
    selectionSerial++; preflightResult.hidden = true; preflightResult.replaceChildren();
  }
  form.addEventListener("change", invalidatePreflight);
  var status = document.getElementById("site-export-status");
  var token = document.body.dataset.manuscriptProjectToken;
  var busy = false;
  function savedProfiles() {
    return window.LixityPublicationSettings ? window.LixityPublicationSettings.savedProfiles() : {};
  }
  function updateProfiles() {
    var current = profile.value;
    profile.replaceChildren(new Option(uiLabel("publication_export_choose_profile"), ""));
    Object.entries(savedProfiles()).forEach(function(entry) { profile.add(new Option(entry[1].title, entry[0])); });
    if (Object.prototype.hasOwnProperty.call(savedProfiles(), current)) profile.value = current;
    sync();
  }
  cap.add(new Option(uiLabel("analysis_scope_all"), ""));
  cap.add(new Option(uiLabel("publication_before"), "0"));
  var chapters = document.getElementById("reader-chapter");
  if (chapters) Array.from(chapters.options).forEach(function(option) {
    var match = /^ch-(\d+)$/.exec(option.value);
    if (match) cap.add(new Option(uiFormat("publication_chapter", {number:Number(match[1])}), match[1]));
  });
  function sync() {
    var curated = mode.value !== "review";
    var saved = savedProfiles(), count = Object.keys(saved).length;
    var editor = document.getElementById("site-publication-editor");
    var state = window.LixityPublicationSettings ? window.LixityPublicationSettings.state() : {invalid:true};
    var selected = Object.prototype.hasOwnProperty.call(saved, profile.value);
    var key = state.invalid ? "publication_export_invalid_profiles" :
      !count ? "publication_export_no_profiles" : selected ? "publication_export_profile_hint" : "publication_export_choose_profile";
    profileState.textContent = uiLabel(key);
    profileDraft.textContent = uiLabel("publication_export_unsaved_profiles");
    profileDraft.hidden = !state.unsaved;
    mode.disabled = busy || !token;
    profile.disabled = busy || !token || !curated || !count || state.invalid;
    cap.disabled = busy || !token || !curated || !selected;
    editProfiles.disabled = busy || !editor || editor.disabled;
    editProfiles.textContent = uiLabel(!count ? "publication_export_create_profile" : "publication_export_edit_profiles");
    research.disabled = busy || !token || curated;
    downloadButton.disabled = busy || !token || (curated && !selected);
    checkButton.disabled = downloadButton.disabled;
    sources.disabled = busy || (curated ? !selected : !research.checked);
    if (!curated && !research.checked) sources.checked = false;
    document.getElementById("site-export-publication-options").hidden = !curated;
    document.getElementById("site-export-research-option").hidden = curated;
    document.getElementById("site-export-scope").textContent = uiLabel("publication_export_scope_" + mode.value);
    form.setAttribute("aria-busy", String(busy));
  }
  function message(key, failed, reason) {
    status.className = "ctl-status " + (failed ? "err" : "ok");
    status.textContent = uiLabel(key) + (reason ? " " + reason : "");
  }
  function localizedLimitFailure(body) {
    var report = body && body.preflight;
    var categories = {
      research_record_bytes:"research", research_authored_revision_count:"research",
      research_response_count:"research", research_response_bytes:"research",
      prepared_data_bytes:"research", publication_bytes:"publication", bundle_bytes:"bundle"
    };
    if (!report || report.schema_version !== "lixity-site-preflight-error/1" ||
        report.ok !== false || report.complete !== false || report.files_written !== false ||
        !Object.prototype.hasOwnProperty.call(categories, report.limit)) return "";
    var category = categories[report.limit];
    var recovery = report.limit === "research_record_bytes" ? "site_export_limit_record_scope" :
      category === "research" ? "site_export_limit_scope" : "site_export_limit_" + category + "_scope";
    var details = document.createElement("details"), summary = document.createElement("summary");
    summary.textContent = uiLabel("site_export_limit_details");
    var diagnostic = document.createElement("pre");
    diagnostic.textContent = JSON.stringify(Object.assign({}, report, {
      message:typeof body.message === "string" ? body.message : report.message
    }), null, 2);
    details.append(summary, diagnostic);
    preflightResult.replaceChildren(details); preflightResult.hidden = false;
    return uiLabel("site_export_limit_" + category) + " " + uiLabel(recovery) + " " + uiLabel("site_export_limit_incomplete");
  }
  function reportExport(exportId, stage, error) {
    var errorName = error ? (["AbortError", "NetworkError", "TypeError", "Error"].includes(error.name)
      ? error.name : "Other") : null;
    reportSiteExport(stage, {export_id:/^[0-9a-f]{32}$/.test(exportId) ? exportId : null, error_name:errorName});
  }
  function reportProfiles() {
    if (mode.value === "review") return;
    var state = window.LixityPublicationSettings ? window.LixityPublicationSettings.state() : {invalid:true};
    var count = Object.keys(savedProfiles()).length;
    reportSiteExport(state.invalid ? "profiles_invalid" : !count ? "profiles_empty" :
      state.unsaved ? "profiles_unsaved" : "profiles_available", {profile_count:count});
  }
  open.addEventListener("click", function() {
    if (open.disabled) return;
    invalidatePreflight();
    mode.value = "review"; research.checked = sources.checked = false;
    profile.value = cap.value = ""; status.textContent = ""; status.className = "ctl-status";
    updateProfiles(); dialog.showModal();
  });
  mode.addEventListener("change", function() { research.checked = sources.checked = false; sync(); reportProfiles(); });
  profile.addEventListener("change", sync);
  document.addEventListener("lixity:site-publications-saved", function() { invalidatePreflight(); updateProfiles(); });
  editProfiles.addEventListener("click", function() {
    dialog.close(); switchActiveView("project");
    var editor = document.getElementById("settings-site-publications");
    if (editor) {
      editor.open = true;
      var target = Object.keys(savedProfiles()).length ? editor.querySelector("summary") :
        editor.querySelector("[data-site-publication-add-profile]");
      target.focus(); target.scrollIntoView({block:"nearest"});
    }
  });
  research.addEventListener("change", sync);
  form.addEventListener("submit", async function(event) {
    event.preventDefault();
    if (busy || !token) return;
    var curated = mode.value !== "review";
    if (curated && !Object.prototype.hasOwnProperty.call(savedProfiles(), profile.value)) return;
    var payload = {project_token:token, include_research:!curated && research.checked,
      include_source_files:(curated || research.checked) && sources.checked};
    if (curated) {
      payload.mode = mode.value; payload.publication_profile = profile.value;
      payload.max_chapter = cap.value === "" ? null : Number(cap.value);
    }
    var checking = event.submitter === checkButton;
    var selectedSerial = selectionSerial;
    invalidatePreflight(); selectedSerial = selectionSerial;
    busy = true; sync(); message("site_export_busy");
    var reason = "";
    var failureKey = "site_export_network_error";
    var exportId = "", stage = "response_read";
    try {
      var response = await fetch(API + (checking ? "/site-preflight" : "/site-export"), {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });
      exportId = response.headers.get("X-Lixity-Export-ID") || "";
      if (!response.ok) {
        reason = "HTTP " + response.status;
        try {
          var body = await response.json();
          if (body && typeof body.message === "string" && body.message.trim()) reason = body.message;
          reason = localizedLimitFailure(body) || reason;
        }
        catch (_) { /* Preserve the HTTP status for non-JSON errors. */ }
        throw new Error("Website export unavailable");
      }
      if (checking) {
        var checked = await response.json(), report = checked && checked.preflight;
        if (!checked.ok || !report || report.schema_version !== "lixity-site-preflight/1" ||
            !report.sizes || !report.media || !Array.isArray(report.warnings)) throw new Error("Invalid export check");
        if (selectedSerial !== selectionSerial) return;
        function line(text) {
          var p = document.createElement("p"); p.className = "ctl-note"; p.textContent = text; preflightResult.appendChild(p);
        }
        function size(bytes) { return (bytes / (1024 * 1024)).toFixed(2) + " MiB"; }
        line(uiFormat("site_preflight_sizes", {html:size(report.sizes.html_bytes), zip:size(report.sizes.zip_bytes), total:size(report.sizes.total_bytes)}));
        line(uiFormat("site_preflight_media", {references:report.media.references, unavailable:report.media.unavailable,
          omitted:report.media.not_packaged, credits:report.media.missing_attribution, ordinary:report.media.ordinary_image_references}));
        if (report.warnings.includes("large_html") || report.warnings.includes("large_zip")) line(uiLabel("site_preflight_large"));
        line(uiLabel("site_preflight_note")); preflightResult.hidden = false; status.textContent = "";
        return;
      }
      failureKey = "site_export_response_error";
      if ((response.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase() !== "application/zip") {
        reason = uiLabel(failureKey) + " (HTTP " + response.status + "; Content-Type: " +
          (response.headers.get("Content-Type") || "\u2014") + ")";
        throw new Error("Expected a ZIP response");
      }
      failureKey = "site_export_transfer_error";
      var blob = await response.blob();
      stage = "zip_check";
      failureKey = "site_export_response_error";
      var magic = new Uint8Array(await blob.slice(0, 4).arrayBuffer());
      if (blob.size < 22 || magic[0] !== 0x50 || magic[1] !== 0x4b ||
          !((magic[2] === 3 && magic[3] === 4) || (magic[2] === 5 && magic[3] === 6))) {
        reason = uiLabel(failureKey);
        throw new Error("Invalid ZIP response");
      }
      stage = "download_start";
      failureKey = "site_export_download_error";
      var url = URL.createObjectURL(blob), download = document.createElement("a");
      download.href = url; download.download = "lixity-reading-website.zip";
      document.body.appendChild(download); download.click(); download.remove();
      setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
      reportExport(exportId, "download_started");
      message("site_export_success");
    } catch (error) {
      reportExport(exportId, stage, error);
      if (!reason) {
        reason = uiLabel(failureKey);
        if (error instanceof Error) reason += " (" + error.name + ": " + error.message + ")";
      }
      message("site_export_error", true, reason);
    }
    finally {
      busy = false; sync();
      if (checking && selectedSerial === selectionSerial && dialog.open &&
          (document.activeElement === document.body || document.activeElement === dialog)) checkButton.focus();
    }
  });
  updateProfiles();
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
  if (window.LixityPublicationSettings) Object.assign(payload, window.LixityPublicationSettings.readChanges());
  if (!settings.checkValidity()) {
    if (Object.prototype.hasOwnProperty.call(payload, "site_publications")) {
      reportSiteExport("profiles_invalid", {error_name:"Error"});
    }
    var invalid = settings.querySelector("input:invalid, select:invalid, textarea:invalid");
    for (var ancestor = invalid && invalid.parentElement; ancestor && ancestor !== settings; ancestor = ancestor.parentElement) {
      if (ancestor.tagName === "DETAILS") ancestor.open = true;
    }
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
      if (Object.prototype.hasOwnProperty.call(payload, "site_publications") && window.LixityPublicationSettings) {
        window.LixityPublicationSettings.accepted(payload.site_publications);
      }
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
