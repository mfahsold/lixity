function tenseScopeEnabled() {
  var classes = document.body.classList;
  return classes.contains("only-flags") &&
    (!classes.contains("manuscript-reading") || classes.contains("workbench-analysis"));
}
function tenseScopeActive() {
  return tenseScopeEnabled() && !document.body.classList.contains("text-search-active");
}

// Results and direct drills follow the same visibility rules as the manuscript.
// A folded chapter remains reachable because a drill can expand it.
function passageBlocker(target) {
  if (target.closest(".text-miss")) return "search";
  var chapter = target.closest(".chapter");
  if (chapter && tenseScopeActive() && !chapter.classList.contains("has-flags")) return "tense";
  return null;
}

function setFilter(input, bodyClass, on) {
  if (!input) return;
  input.checked = on;
  document.body.classList.toggle(bodyClass, on);
  if (bodyClass === "only-flags") syncPassageScope();
}

var clearManuscriptSearch;
function revealPassageScope(target) {
  if (clearManuscriptSearch && passageBlocker(target) === "search") clearManuscriptSearch(false);
  if (passageBlocker(target) === "tense") setFilter(filter, "only-flags", false);
}

function selectAnalysisMetric(key) {
  // Chapter-only measurements intentionally clear a previous paragraph layer.
  window.LixityComponents.changeSelectOption(layer, key || "");
}

function activate(el) {
  if (el.hasAttribute("data-rhythm-min-words") && typeof window.LixityJumpToRhythmGroup === "function") {
    window.LixityJumpToRhythmGroup(el);
    return;
  }
  if (el.hasAttribute("data-metric-feature") && window.LixityMetricContext &&
      window.LixityMetricContext.open(el)) return;
  // drill-down: carry the context filters on the way to the deeper level
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
  var explicitTenseReview = row.hasAttribute("data-review-tense");
  var fromFlag = Boolean(
    explicitTenseReview || row.hasAttribute("data-flags") ||
    row.closest("#flags, [data-flags]")
  );
  var dock = fromFlag && document.getElementById("workspace-context-panel");
  // A requested review opens the explanation even when it is stacked above the text.
  // A table drill in that layout leaves the explanation available at the passage.
  var inspectFlag = fromFlag && (explicitTenseReview || !dock || getComputedStyle(dock).position === "sticky");
  var options = {
    analysisVisible: fromFlag ? true : undefined,
    contextTool: fromFlag ? (inspectFlag && !explicitTenseReview ? "analysis" : "none") : undefined,
    behavior: explicitTenseReview ? "instant" : undefined
  };
  if (panel) {
    // A standalone report restores open blocks when clearing a search.
    // Resolve that scope before opening the requested passage.
    if (!window.LixityReader) revealPassageScope(panel);
    var chip = document.querySelector('.chip[data-target="' + panel.id + '"]');
    if (chip) toggleParagraph(chip, true, true);
    if (row.hasAttribute("data-review-passage")) rememberPassageLocation(panel);
    scrollAndFlash(panel, options);
    if (inspectFlag && window.LixityReader && window.LixityReader.inspectPassage) {
      window.LixityReader.inspectPassage(panel, null, explicitTenseReview ?
        panel.querySelector("[data-reader-flag]") || panel : null);
    }
    if (row.hasAttribute("data-review-passage") && (!explicitTenseReview || !window.LixityReader)) {
      panel.tabIndex = -1;
      panel.focus({preventScroll: true});
    }
    return;
  }
  var chapters = document.querySelectorAll(".chapter[data-start]");
  for (var j = 0; j < chapters.length; j++) {
    var cstart = parseInt(chapters[j].getAttribute("data-start"), 10);
    var cend = parseInt(chapters[j].getAttribute("data-end"), 10);
    if (line >= cstart && line <= cend) {
      scrollAndFlash(chapters[j], options);
      return;
    }
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
    if (target.matches("a") && (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0)) return;
    // The scripted drill owns scrolling. A second native fragment navigation
    // also fires hashchange and can discard keyboard focus in Firefox.
    if (target.matches('a[href^="#"]')) {
      event.preventDefault();
      if (location.hash !== target.getAttribute("href")) history.pushState(null, "", target.getAttribute("href"));
    }
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
  filter.addEventListener("change", function() {
    var update = function() { setFilter(filter, "only-flags", filter.checked); };
    if (window.LixityReader) window.LixityReader.retain(update);
    else update();
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
  var group = input.closest(".text-search-group");
  var hits = [];
  var cursor = -1;
  var restored = null;
  var query = "";

  var structuralSearch = new WeakMap();
  function literalPattern(text) {
    return window.LixityComponents.literalWhitespaceRegex(text, "i");
  }
  function paintMatch(paragraph, query, structural, pattern) {
    if (!structural) {
      if ((paragraph.dataset.searchQuery || "") !== query) renderParagraphText(paragraph, query);
      return;
    }
    if (structural.query === query) return;
    structural.query = query;
    var text = structural.text;
    var regex = query && (pattern || literalPattern(query)), match = regex ? regex.exec(text) : null;
    if (!match) { paragraph.textContent = text; return; }
    var index = match.index;
    var hit = document.createElement("mark"); hit.className = "text-hit"; hit.textContent = match[0];
    paragraph.replaceChildren(document.createTextNode(text.slice(0, index)), hit, document.createTextNode(text.slice(index + match[0].length)));
  }

  function apply(direction) {
    var t0 = (window.performance && performance.now) ? performance.now() : Date.now();
    query = input.value.trim();
    hits = [];
    cursor = -1;
    var pattern = literalPattern(query);
    var blocks = Array.prototype.slice.call(
      document.querySelectorAll("#chapters .ptext, #chapters .reader-structural")
    );
    if (query && restored === null) {
      restored = new Set(blocks.filter(function(block) { return block.classList.contains("open"); }));
    }
    blocks.forEach(function (block) {
      var structural = structuralSearch.get(block);
      if (!structural && block.matches(".reader-structural")) {
        structural = {text: block.textContent, query: ""};
        structuralSearch.set(block, structural);
      }
      var text = structural ? structural.text : paragraphContent[block.id]?.[0];
      var match = Boolean(pattern) && text !== undefined && pattern.test(text);
      block.classList.toggle("text-miss", Boolean(query) && !match);
      var chip = paragraphChips[block.id];
      if (restored !== null && chip) {
        var open = !query && restored.has(block);
        if (block.classList.contains("open") !== open) toggleParagraph(chip, open);
      }
      var paragraph = structural ? block : block.querySelector("p");
      if (paragraph) paintMatch(paragraph, match ? query : "", structural, pattern);
      if (match) hits.push(block);
    });
    if (!query) restored = null;
    document.querySelectorAll("#chapters .chapter").forEach(function (chapter) {
      var miss = Boolean(query) && !chapter.querySelector(".ptext:not(.text-miss), .reader-structural:not(.text-miss)");
      chapter.classList.toggle("text-miss", miss);
    });
    document.body.classList.toggle("text-search-active", Boolean(query));
    syncPassageScope();
    [prev, next].forEach(function(button) {
      if (!button) return;
      button.hidden = !query;
      button.disabled = !hits.length;
    });
    if (clear) clear.hidden = !query;
    if (status) {
      if (!query) status.textContent = "";
      else if (!hits.length) status.textContent = uiLabel("text_search_none");
      else status.textContent = uiFormat("text_search_count", {
        matches: hits.length,
        paragraphs: blocks.length
      });
    }
    if (query && !hits.length && group && group.contains(document.activeElement)) {
      // Removing all chapter results can move the search feedback behind the
      // sticky reader. Keep the active field, its status and Clear available.
      var bounds = group.getBoundingClientRect(), toolbar = group.closest(".toolbar");
      var boundary = toolbar && getComputedStyle(toolbar).position === "sticky" ? 0 : readingViewportTop();
      if (bounds.top < boundary || bounds.bottom > innerHeight) {
        setPassageScrollMargin(group);
        window.LixityComponents.scrollIntoViewSafe(group, {block: "nearest", behavior: "instant"});
      }
    }
    var dur = ((window.performance && performance.now) ? performance.now() : Date.now()) - t0;
    if (window.LixityLog && query) {
      window.LixityLog.perf("search", dur, {queryLength: query.length, matches: hits.length, total: blocks.length});
    }
    if (hits.length && direction) {
      if (direction === -1) cursor = 0;
      step(direction === -1 ? -1 : 1);
    }
  }

  function step(direction) {
    if (!hits.length) return;
    if (window.LixityWorkbench && window.LixityWorkbench.state().surface === "overview") {
      window.LixityWorkbench.dispatch({type: "surface", value: "document"});
    }
    if (cursor < 0 && direction < 0) cursor = 0;
    cursor = (cursor + direction + hits.length) % hits.length;
    var block = hits[cursor];
    rememberPassageLocation(block);
    var chip = paragraphChips[block.id];
    if (chip) {
      if (block.classList.contains("open")) revealChapter(block);
      else toggleParagraph(chip, true, true);
    }
    var structural = structuralSearch.get(block);
    var paragraph = structural ? block : block.querySelector("p");
    if (paragraph) paintMatch(paragraph, query, structural);
    scrollAndFlash(paragraph && paragraph.querySelector("mark.text-hit") || block, {block: "center", behavior: "instant"});
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
  function navigate(direction) {
    if (pending) { clearTimeout(pending); pending = null; apply(direction); }
    else step(direction);
  }
  if (next) next.addEventListener("click", function () { navigate(1); });
  if (prev) prev.addEventListener("click", function () { navigate(-1); });
  clearManuscriptSearch = function(focus) {
    clearTimeout(pending); pending = null; input.value = ""; apply();
    if (focus) input.focus();
  };
  if (clear) clear.addEventListener("click", function() { clearManuscriptSearch(true); });
  window.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === "f" || e.key === "F")) {
      if (!e.defaultPrevented && input.getClientRects().length) {
        e.preventDefault();
        input.focus();
        input.select();
      }
    } else if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey) {
      var target = e.target;
      var isInput = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
      if (!isInput && input.getClientRects().length) {
        e.preventDefault();
        input.focus();
        input.select();
      }
    }
  });
})();

var paragraphReset = document.getElementById("paragraph-filter-reset");
var paragraphFilterEmpty = document.getElementById("paragraph-filter-empty");
var paragraphFilterSuspended = document.getElementById("paragraph-filter-suspended");
if (paragraphReset) paragraphReset.addEventListener("click", function() {
  var clear = function() {
    setFilter(filter, "only-flags", false);
    if (filter) filter.focus({preventScroll: true});
  };
  if (window.LixityReader) window.LixityReader.retain(clear);
  else clear();
});
// Do not advertise filters or chapter toggles in a static, uninitialized report.
document.body.classList.add("has-js-dashboard-controls");
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
var layerReference = document.getElementById("layer-metric-reference");

function selectedLayerOption() {
  return layer && layer.selectedIndex >= 0 ? layer.options[layer.selectedIndex] : null;
}

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
var comparisonCandidates = [], reachableOutliers = [];

function syncPassageScope() {
  reachableOutliers = comparisonCandidates.filter(function(chip) {
    return chip._panel && !passageBlocker(chip._panel);
  });
  var tenseEnabled = tenseScopeEnabled();
  var searching = document.body.classList.contains("text-search-active");
  if (paragraphReset) paragraphReset.hidden = !tenseEnabled;
  if (paragraphFilterEmpty) paragraphFilterEmpty.hidden = !tenseScopeActive() ||
    Boolean(document.querySelector("#chapters .chapter.has-flags"));
  if (paragraphFilterSuspended) paragraphFilterSuspended.hidden = !tenseEnabled || !searching;
  var option = selectedLayerOption();
  if (layerCount) {
    var comparable = Number(option?.dataset.comparable);
    var label = !layer?.value || option?.dataset.inlineEvidence === "1" ? "" :
      comparable ? uiFormat("layer_coverage", {
        notable: reachableOutliers.length, comparable: comparable, total: layerLegend.dataset.profiled
      }) : uiLabel("layer_unavailable");
    if (layerCount.textContent !== label) layerCount.textContent = label;
  }
  syncOutlierNavigation();
}

function currentOutlierPassage() {
  var selection = window.getSelection();
  var node = selection && !selection.isCollapsed && selection.focusNode;
  var element = node && (node.nodeType === 1 ? node : node.parentElement);
  var selected = element && element.closest("#chapters .ptext");
  if (selected && !passageBlocker(selected)) return selected;
  var focused = document.activeElement && document.activeElement.closest("#chapters .ptext");
  if (focused) {
    var bounds = focused.getBoundingClientRect();
    var boundary = readingViewportTop();
    if (bounds.height > 0 && bounds.bottom > boundary && bounds.top < innerHeight) return focused;
  }
  var pending = window.LixityReader && window.LixityReader.pendingComparisonPassage();
  if (pending) return pending;
  var anchor = window.LixityReader && window.LixityReader.capture();
  if (anchor) return anchor.panel;
  // Standalone reports use the same navigation without the continuous reader.
  return Array.prototype.find.call(document.querySelectorAll("#chapters .ptext.open"), function(panel) {
    var bounds = panel.getBoundingClientRect();
    return bounds.height > 0 && bounds.bottom > 0 && bounds.top < innerHeight;
  }) || null;
}

function syncOutlierNavigation() {
  var chips = reachableOutliers, panel = chips.length && layerPosition ? currentOutlierPassage() : null;
  var position = panel ? chips.findIndex(function(chip) { return chip.dataset.target === panel.id; }) + 1 : 0;
  if (layerPosition) {
    var text = uiFormat(position ? "layer_position" : "layer_position_pending", {current: position, total: chips.length});
    if (layerPosition.textContent !== text) layerPosition.textContent = text;
    if (layerPosition.getAttribute("aria-label") !== text) layerPosition.setAttribute("aria-label", text);
  }
  var option = selectedLayerOption();
  var comparing = Boolean(layer?.value) && option?.dataset.inlineEvidence !== "1" &&
    option?.dataset.available !== "0" && (!comparisonToggle || comparisonToggle.checked);
  var layerNav = layerPosition && layerPosition.closest(".layer-nav, .reader-outlier-navigation");
  if (layerNav) layerNav.hidden = !comparing;
  var disabled = !chips.length || !comparing;
  if (layerPrevious) layerPrevious.disabled = disabled;
  if (layerNext) layerNext.disabled = disabled;
}

function stepOutlier(direction) {
  var chips = reachableOutliers;
  if (!chips.length) return;
  var panel = currentOutlierPassage();
  var candidates = direction < 0 ? chips.slice().reverse() : chips;
  var chip = panel && candidates.find(function(candidate) {
    return Boolean(panel.compareDocumentPosition(candidate._panel) & (direction < 0 ? 2 : 4));
  });
  chip = chip || candidates[0];
  var target = chip._panel;
  // A selection supplies the first origin, then the new passage owns later steps.
  var selection = window.getSelection();
  if (selection && !selection.isCollapsed) selection.removeAllRanges();
  toggleParagraph(chip, true, true);
  rememberPassageLocation(target);
  scrollAndFlash(target, {analysisVisible: true});
  syncOutlierNavigation();
}

function paintLayerAction(panel, info) {
  var actions = panel._paragraphActions || (panel._paragraphActions = panel.querySelector(".reader-paragraph-actions"));
  if (!actions) return;
  var shown = document.body.classList.contains("workbench-analysis") && !document.body.classList.contains("workbench-overview") &&
    !document.body.classList.contains("reader-focus") && (!comparisonToggle || comparisonToggle.checked);
  var notable = Boolean(shown && info && info[4] === true);
  if (!actions._metricBase) actions._metricBase = {label: actions.getAttribute("aria-label"), help: actions.dataset.help};
  if (notable) {
    var fullLabel = info[1] + " · " + actions._metricBase.label;
    if (actions.getAttribute("aria-label") !== fullLabel) actions.setAttribute("aria-label", fullLabel);
    actions.dataset.help = info[1] + " · " + actions._metricBase.help;
    actions.dataset.layerSymbol = info[2] < 0 ? "↓" : "↑";
  } else if (actions.dataset.layerSymbol) {
    actions.setAttribute("aria-label", actions._metricBase.label);
    actions.dataset.help = actions._metricBase.help;
    delete actions.dataset.layerSymbol;
  }
  var marker = panel._comparisonMarker;
  if (!marker && (notable || panel.querySelector(":scope > .reader-comparison-value"))) {
    marker = panel._comparisonMarker = panel.querySelector(":scope > .reader-comparison-value");
  }
  if (!marker && notable && info[3] !== undefined) {
    marker = document.createElement("button"); marker.type = "button";
    marker.className = "reader-comparison-value";
    marker.addEventListener("click", function() {
      if (window.LixityAnalysisEvidence && LixityAnalysisEvidence.available()) LixityAnalysisEvidence.inspect(panel, marker);
      else actions.click();
    });
    panel.prepend(marker);
    panel._comparisonMarker = marker;
  }
  if (marker) {
    marker.hidden = !notable;
    if (notable) {
      var unit = selectedLayerOption()?.dataset.unit;
      var text = actions.dataset.layerSymbol + " " + info[3] + (unit ? " " + unit : "");
      if (marker.textContent !== text) marker.textContent = text;
      var aria = info[1] + ". " + uiLabel("evidence_inspect");
      if (marker.getAttribute("aria-label") !== aria) marker.setAttribute("aria-label", aria);
      if (marker.title !== info[1]) marker.title = info[1];
    }
  }
}

function syncEvidenceLegend() {
  var legend = document.getElementById("layer-evidence-legend");
  var toggle = document.getElementById("analysis-evidence-enabled");
  var selectedOption = selectedLayerOption();
  var selected = Boolean(layer?.value);
  var unavailable = Boolean(selectedOption && selectedOption.dataset.available === "0");
  var note = document.getElementById("layer-language-unavailable");
  if (note) note.hidden = !unavailable;
  if (toggle) toggle.disabled = !selected || unavailable;
  if (legend) legend.hidden = unavailable || !toggle || !toggle.checked;
  var inlineOnly = Boolean(selectedOption && selectedOption.dataset.inlineEvidence === "1");
  var comparisonUnavailable = document.getElementById("layer-comparison-unavailable");
  if (comparisonUnavailable) comparisonUnavailable.hidden = !inlineOnly || unavailable;
  var comparison = document.getElementById("layer-comparison-legend");
  if (comparison) comparison.hidden = unavailable || inlineOnly || Boolean(comparisonToggle && !comparisonToggle.checked);
  var comparisonControls = comparisonToggle && comparisonToggle.closest(".reader-comparison-controls");
  if (comparisonControls) comparisonControls.hidden = !selected || unavailable || inlineOnly;
  var instruction = document.getElementById("analysis-evidence-instruction");
  if (instruction && layer) instruction.textContent = uiLabel(
    layer.value === "sticky" ? "evidence_sticky_instruction" : "evidence_open_instruction"
  );
  if (layerLegend) layerLegend.hidden = !selected ||
    (!unavailable && !inlineOnly && Boolean(legend && legend.hidden && comparison && comparison.hidden));
}

var allChips = null;
function applyLayer() {
  var key = layer ? layer.value : "";
  var option = selectedLayerOption();
  var comparing = !!key && option?.dataset.available !== "0" && option?.dataset.inlineEvidence !== "1" &&
    (!comparisonToggle || comparisonToggle.checked);
  var comparisonMissing = comparing ? uiLabel("comparison_missing_mark") : "";
  document.body.classList.toggle("layer-on", !!key);
  document.body.classList.toggle("comparison-on", comparing);
  if (!allChips) allChips = Array.prototype.slice.call(document.querySelectorAll(".chip"));
  var nextOutliers = [];
  allChips.forEach(function (chip) {
    var info = key ? chipLayers(chip)[key] : null;
    var panel = chip._panel || (chip._panel = document.getElementById(chip.dataset.target));
    var notable = Boolean(info && info[4] === true);
    chip.classList.toggle("layer-unavailable", comparing && !info);
    if (info && comparing) {
      chip.style.setProperty("--layer-color", info[0]);
      chip.classList.add("has-layer");
      chip.setAttribute("data-tip", info[1]);
      chip.removeAttribute("title");
      chip.classList.toggle("outlier", notable);
      chip.setAttribute("aria-label", info[1]);
      if (notable) nextOutliers.push(chip);
    } else if (chip.classList.contains("has-layer") || chip.classList.contains("outlier") || chip.hasAttribute("data-tip") || !chip.hasAttribute("title")) {
      chip.style.removeProperty("--layer-color");
      chip.classList.remove("has-layer");
      chip.classList.remove("outlier");
      if (!comparing) {
        chip.removeAttribute("data-tip");
        var base = chip.getAttribute("data-tip-base");
        if (base) { chip.setAttribute("title", base); chip.setAttribute("aria-label", base); }
      }
    }
    if (comparing && !info) {
      var lines = panel && panel.dataset.start;
      if (lines && panel.dataset.end !== lines) lines += "–" + panel.dataset.end;
      var missing = lines ? uiLabel("line") + " " + lines + " · " + comparisonMissing : comparisonMissing;
      chip.setAttribute("data-tip", missing);
      chip.removeAttribute("title");
      chip.setAttribute("aria-label", missing);
    }
    if (panel) {
      if (notable) {
        panel.classList.add("metric-notable");
        panel.style.setProperty("--paragraph-layer-color", info[0]);
      } else if (panel.classList.contains("metric-notable")) {
        panel.classList.remove("metric-notable");
        panel.style.removeProperty("--paragraph-layer-color");
      }
      if (info || panel._comparisonMarker || panel.querySelector(":scope > .reader-comparison-value")) {
        paintLayerAction(panel, info);
      }
    }
  });
  comparisonCandidates = nextOutliers;
  if (layerLegend) {
    layerLegend.hidden = !key;
    if (key && layer) {
      if (option) {
        var title = document.getElementById("layer-legend-title");
        var hint = option.getAttribute("data-hint") || "";
        if (title) {
          title.textContent = option.dataset.unit ? option.textContent + " · " + option.dataset.unit : option.textContent;
          if (hint) title.setAttribute("data-tip", hint);
          else title.removeAttribute("data-tip");
        }
        var comparisonHint = document.getElementById("layer-comparison-hint");
        if (comparisonHint) comparisonHint.textContent = hint;
        if (layerReference) layerReference.hash = option.dataset.reference;
        var evidenceHint = document.getElementById("layer-evidence-hint");
        if (evidenceHint) evidenceHint.textContent = uiFormat(key === "asl" ? "legend_counted_sentences_hint" : "legend_counted_text_hint", {metric: option.textContent});
        var comparable = Number(option.dataset.comparable);
        if (layerOnly) layerOnly.disabled = comparable === 0 || !comparing;
        if (comparable === 0 || !comparing) setFilter(layerOnly, "layer-only", false);
      }
    }
  }
  syncPassageScope();
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
  setFilter(layerOnly, "layer-only", false);
  selectAnalysisMetric("");
  if (layer) layer.focus({preventScroll: true});
});
document.addEventListener("lixity:reader-ready", applyLayer);
document.addEventListener("lixity:workbench-change", function() {
  document.querySelectorAll("#chapters .ptext.metric-notable").forEach(function(panel) {
    var chip = paragraphChips[panel.id];
    paintLayerAction(panel, chip && layer ? chipLayers(chip)[layer.value] : null);
  });
  syncPassageScope();
});
function jsonApi(url, options, responseType) {
  return window.LixityComponents.jsonApi(url, options, responseType);
}

function markerApi(payload) {
  return window.LixityComponents.postJson(API + "/marker-" + payload._action, payload);
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
var UI_LABELS = window.LixityLabels ? window.LixityLabels.all() : {};
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
var reviewToggleBtn = document.getElementById("analysis-review-toggle");
var reviewBody = document.getElementById("analysis-review-body");
if (reviewToggleBtn && reviewBody) {
  var reviewHideKey = "lixity:hide-review-guide";
  var reviewHidden = false;
  try { reviewHidden = localStorage.getItem(reviewHideKey) === "1"; } catch (_) { /* ignore */ }
  function applyReviewVisibility(hidden) {
    reviewBody.hidden = hidden;
    reviewToggleBtn.setAttribute("aria-expanded", String(!hidden));
    reviewToggleBtn.textContent = hidden
      ? (reviewToggleBtn.getAttribute("data-show-label") || "Show")
      : (reviewToggleBtn.getAttribute("data-hide-label") || "Hide");
  }
  applyReviewVisibility(reviewHidden);
  reviewToggleBtn.addEventListener("click", function() {
    reviewHidden = !reviewBody.hidden;
    applyReviewVisibility(reviewHidden);
    try {
      if (reviewHidden) localStorage.setItem(reviewHideKey, "1");
      else localStorage.removeItem(reviewHideKey);
    } catch (_) { /* ignore */ }
  });
}
if (window.LixityIcons && typeof window.LixityIcons.svg === "function") {
  [
    ["btn-modal-new-project", "file-text"],
    ["btn-modal-open-project", "folder-open"],
    ["btn-site-export", "share-2"],
    ["welcome-show", "help-circle"]
  ].forEach(function (entry) {
    var el = document.getElementById(entry[0]);
    if (!el || el.querySelector(".lixity-icon-slot")) return;
    var slot = document.createElement("span");
    slot.className = "lixity-icon-slot";
    slot.setAttribute("aria-hidden", "true");
    slot.innerHTML = window.LixityIcons.svg(entry[1], { size: 15 });
    el.prepend(slot);
  });
}
(function initManuscriptPdf() {
  var form = document.getElementById("manuscript-pdf-form");
  if (!form) return;
  var layout = document.getElementById("manuscript-pdf-layout");
  var layoutDesc = document.getElementById("manuscript-pdf-layout-desc");
  var button = document.getElementById("manuscript-pdf-download");
  var status = document.getElementById("manuscript-pdf-status");
  var components = window.LixityComponents;
  var available = form.dataset.available === "true" && !!form.dataset.projectToken;
  var busy = false;
  function syncLayoutDescription() {
    if (!layoutDesc || !layout) return;
    var text = uiLabel("manuscript_pdf_desc_" + layout.value);
    layoutDesc.textContent = text === "manuscript_pdf_desc_" + layout.value ? "" : text;
  }
  if (layout) layout.addEventListener("change", syncLayoutDescription);
  syncLayoutDescription();
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
    var token = form.dataset.projectToken;
    var payload = {layout: selected, project_token: token};
    var path = form.getAttribute("action");
    var filename = "manuscript-" + selected + ".pdf";
    function isCurrent() {
      return form.isConnected && token === form.dataset.projectToken && token === document.body.dataset.manuscriptProjectToken;
    }
    pending(true);
    message("manuscript_pdf_busy", false);
    try {
      var nativeSave = components.saveExport({path: path, method: "POST", payload: payload}, filename, isCurrent);
      if (nativeSave) {
        var outcome = await nativeSave;
        if (isCurrent() && outcome.saved) message("manuscript_pdf_success", false);
        else components.setStatus(status, "", "");
        return;
      }
      var response = await fetch(path, {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      var blob = await components.readPdfBlob(response);
      if (!isCurrent()) return;
      components.downloadBlob(blob, filename, 1000);
      message("manuscript_pdf_success", false);
    } catch (error) {
      if (!isCurrent()) return;
      message("manuscript_pdf_error", true);
      if (error?.serverMessage) status.textContent += " " + error.serverMessage;
    } finally {
      pending(false);
      if (!isCurrent()) components.setStatus(status, "", "");
    }
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
  var analysisOptions = document.getElementById("site-export-analysis-options");
  var audioOption = document.getElementById("site-export-audio-option");
  var audio = document.getElementById("site-export-audio");
  var analysisChoices = ["chapters", "language", "full"].map(function(key) {
    return document.getElementById("site-export-analysis-" + key);
  });
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
    else if (current) { cap.value = ""; sources.checked = false; analysisChoices.forEach(function(input) { input.checked = false; }); }
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
    analysisOptions.hidden = mode.value !== "reader";
    audioOption.hidden = mode.value !== "reader";
    audio.disabled = busy || !token || mode.value !== "reader";
    analysisChoices.forEach(function(input) { input.disabled = busy || !token || mode.value !== "reader"; });
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
    details.append(summary);
    var unit = Object.prototype.hasOwnProperty.call(report, "limit_bytes") ? "bytes" : "count";
    ["observed", "limit", "overflow"].forEach(function (key) {
      var value = report[key + "_" + unit];
      if (!Number.isSafeInteger(value) || value < 0) return;
      var line = document.createElement("p"); line.className = "ctl-note";
      var amount = new Intl.NumberFormat(document.documentElement.lang || "en").format(value);
      line.textContent = uiLabel("site_export_limit_" + key) + ": " + amount +
        (unit === "bytes" ? " B" : "");
      details.append(line);
    });
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
  function resetSelection() {
    mode.value = "review"; research.checked = sources.checked = false;
    profile.value = cap.value = "";
    analysisChoices.forEach(function(input) { input.checked = false; });
  }
  function refreshContext() {
    var currentToken = document.body.dataset.manuscriptProjectToken || "";
    if (token === currentToken) return;
    token = currentToken; resetSelection(); invalidatePreflight();
    status.textContent = ""; status.className = "ctl-status"; updateProfiles();
  }
  new MutationObserver(refreshContext).observe(document.body, {
    attributes:true, attributeFilter:["data-manuscript-project-token"]
  });
  open.addEventListener("click", function() {
    if (open.disabled) return;
    invalidatePreflight();
    refreshContext();
    status.textContent = ""; status.className = "ctl-status";
    updateProfiles(); dialog.showModal();
  });
  dialog.addEventListener("close", invalidatePreflight);
  mode.addEventListener("change", function() {
    research.checked = sources.checked = false;
    analysisChoices.forEach(function(input) { input.checked = false; });
    sync(); reportProfiles();
  });
  analysisChoices.forEach(function(input) {
    input.addEventListener("change", function() {
      if (!input.checked) return;
      if (input.value === "full") {
        analysisChoices.forEach(function(other) { if (other !== input) other.checked = false; });
      } else analysisChoices[2].checked = false;
    });
  });
  profile.addEventListener("change", function() { sources.checked = false; sync(); });
  document.addEventListener("lixity:site-publications-saved", function() {
    sources.checked = false; invalidatePreflight(); updateProfiles();
  });
  editProfiles.addEventListener("click", function() {
    dialog.close(); switchActiveView("project");
    var editor = document.getElementById("settings-site-publications");
    if (editor) {
      editor.open = true;
      var target = Object.keys(savedProfiles()).length ? editor.querySelector("summary") :
        editor.querySelector("[data-site-publication-add-profile]");
      if (target) {
        if (typeof scrollAndFlash === "function") scrollAndFlash(target, { block: "nearest" });
        target.focus({ preventScroll: true });
      }
    }
  });
  research.addEventListener("change", sync);
  form.addEventListener("submit", async function(event) {
    event.preventDefault();
    refreshContext();
    if (busy || !token) return;
    var curated = mode.value !== "review";
    if (curated && !Object.prototype.hasOwnProperty.call(savedProfiles(), profile.value)) return;
    var payload = {project_token:token, include_research:!curated && research.checked,
      include_source_files:(curated || research.checked) && sources.checked};
    if (curated) {
      payload.mode = mode.value; payload.publication_profile = profile.value;
      payload.max_chapter = cap.value === "" ? null : Number(cap.value);
      var analysisSections = analysisChoices.filter(function(input) { return input.checked; }).map(function(input) { return input.value; });
      if (mode.value === "reader" && analysisSections.length) payload.analysis_sections = analysisSections;
      if (mode.value === "reader" && audio.checked) payload.include_audio = true;
    }
    var checking = event.submitter === checkButton, requestToken = token;
    function sameExportContext() { return token === requestToken && document.body.dataset.manuscriptProjectToken === requestToken; }
    var selectedSerial = selectionSerial;
    invalidatePreflight(); selectedSerial = selectionSerial;
    busy = true; sync(); message("site_export_busy");
    var reason = "";
    var failureKey = "site_export_network_error";
    var exportId = "", stage = "response_read";
    try {
      var nativeSave = !checking && window.LixityComponents.saveExport(
        {path: API + "/site-export", method: "POST", payload: payload},
        "lixity-reading-website.zip", sameExportContext
      );
      if (nativeSave) {
        stage = "download_start";
        failureKey = "site_export_download_error";
        var outcome = await nativeSave;
        if (!sameExportContext()) return;
        if (outcome && outcome.saved) {
          message("site_export_success");
        } else {
          status.textContent = "";
        }
        return;
      }
      var response = await fetch(API + (checking ? "/site-preflight" : "/site-export"), {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });
      if (!sameExportContext()) return;
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
        var htmlBytes = typeof report.sizes.total_html_bytes === "number" ? report.sizes.total_html_bytes : report.sizes.html_bytes;
        line(uiFormat("site_preflight_sizes", {html:size(htmlBytes), zip:size(report.sizes.zip_bytes), total:size(report.sizes.total_bytes)}));
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
      if (!sameExportContext()) return;
      stage = "zip_check";
      failureKey = "site_export_response_error";
      var magic = new Uint8Array(await blob.slice(0, 4).arrayBuffer());
      if (!sameExportContext()) return;
      if (blob.size < 22 || magic[0] !== 0x50 || magic[1] !== 0x4b ||
          !((magic[2] === 3 && magic[3] === 4) || (magic[2] === 5 && magic[3] === 6))) {
        reason = uiLabel(failureKey);
        throw new Error("Invalid ZIP response");
      }
      stage = "download_start";
      failureKey = "site_export_download_error";
      window.LixityComponents.downloadBlob(blob, "lixity-reading-website.zip", 1000);
      reportExport(exportId, "download_started");
      message("site_export_success");
    } catch (error) {
      if (!sameExportContext()) return;
      reportExport(exportId, stage, error);
      if (!reason) {
        reason = uiLabel(failureKey);
        if (error instanceof Error) reason += " (" + error.name + ": " + error.message + ")";
      }
      message("site_export_error", true, reason);
    }
    finally {
      busy = false; sync();
      // Some browsers move focus out of a modal when a programmatic download
      // starts. Restore a usable in-dialog focus only when it was actually lost.
      if (selectedSerial === selectionSerial && dialog.open &&
          (document.activeElement === document.body || document.activeElement === dialog)) {
        (checking ? checkButton : downloadButton).focus();
      }
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
        window.LixityComponents.downloadBlob(await response.blob(), format === "pdf" ? "nda.pdf" : "nda.txt", 1000);
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
var locationMode = document.getElementById("set-location-mode");
var locationNames = document.getElementById("set-location-names");
if (locationMode && locationNames) {
  locationMode.addEventListener("change", function() {
    locationNames.disabled = locationMode.value !== "names";
    document.getElementById("location-names-field").hidden = locationNames.disabled;
    locationNames.setCustomValidity("");
  });
  locationNames.addEventListener("input", function() { locationNames.setCustomValidity(""); });
}
function thresholdValue(field) {
  if (field.type === "number") return field.valueAsNumber;
  return field.dataset.thresholdKey === "flag_min_severity" ? Number(field.value) : field.value;
}
if (settingsForm) {
  var presetSelect = document.getElementById("set-threshold-preset");
  var presets = JSON.parse(presetSelect.dataset.presets);
  var thresholdFields = Array.from(settingsForm.querySelectorAll("[data-threshold-key]"));
  function syncThresholdPreset() {
    var matched = Object.keys(presets).find(function(name) {
      return thresholdFields.every(function(field) {
        return thresholdValue(field) === presets[name][field.dataset.thresholdKey];
      });
    });
    presetSelect.value = matched || "custom";
  }
  presetSelect.addEventListener("change", function() {
    var chosen = presets[presetSelect.value];
    if (!chosen) return;
    thresholdFields.forEach(function(field) {
      field.value = String(chosen[field.dataset.thresholdKey]);
      field.setCustomValidity("");
    });
  });
  thresholdFields.forEach(function(field) {
    field.addEventListener("input", syncThresholdPreset);
    field.addEventListener("change", syncThresholdPreset);
  });
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
    syncThresholdPreset();
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
  fdrFilter.disabled = false;
}
var projectSelectionRevision = 0;
async function runAction(action, payload, button, canReload, acceptResponse) {
  var selectionRevision = ["project-open", "project-create", "load"].includes(action) ? ++projectSelectionRevision : null;
  var savingSettings = action === "settings";
  var status = document.getElementById(savingSettings ? "settings-save-status" : "ctl-status");
  var {setStatus, setButtonPending} = window.LixityComponents;
  setStatus(status, uiLabel(savingSettings ? "settings_applying" : "editor_loading"), "loading");
  setButtonPending(button, true);
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
    LixityLog.api("POST", url, performance.now() - t0, res.status);
    if (acceptResponse && !acceptResponse()) return data;
    var message = data.message;
    if (savingSettings) {
      if (data.ok) message = uiLabel("settings_applied");
      else if (data.code === "stale-context") message = uiLabel("settings_stale_context");
      else if (data.code === "invalid-language") message = uiLabel("settings_invalid_language");
    }
    setStatus(status, message, data.ok === true, {prefix: !savingSettings});
    if (data.ok && data.reload) {
      setTimeout(function () { if (!canReload || canReload()) {
        if (typeof data.workspace_url === "string" && /^\/w\/[a-f0-9]{32}\/$/.test(data.workspace_url)) {
          if (selectionRevision === projectSelectionRevision) location.assign(data.workspace_url);
        }
        else location.reload();
      } }, 1200);
    }
    return data;
  } catch (err) {
    if (acceptResponse && !acceptResponse()) return {ok: false, message: String(err)};
    LixityLog.error("runAction (" + action + ") error:", err);
    setStatus(status, savingSettings ? uiLabel("settings_connection_failed") : String(err), false, {prefix: !savingSettings});
    return { ok: false, message: String(err) };
  } finally {
    setButtonPending(button, false);
  }
}
function corpusNumber(text, decimalShift) {
  if (!text) return NaN;
  if (!decimalShift) return Number(text);
  // Move the decimal point before converting. Dividing an already rounded
  // percentage can move an inclusive cutoff by one representable value.
  var [digits, exponent = "0"] = text.toLowerCase().split("e");
  return Number(digits + "e" + (Number(exponent) - decimalShift));
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
  settings.querySelectorAll("[data-order-error]").forEach(function(group) {
    var ordered = Array.from(group.querySelectorAll("[data-ascending]"));
    ordered.slice(1).forEach(function(field, index) {
      if (field.validity.valid && ordered[index].valueAsNumber >= field.valueAsNumber) {
        field.setCustomValidity(group.dataset.orderError);
      }
    });
  });
  if (window.LixityRegisterSettings) Object.assign(payload, window.LixityRegisterSettings.readChanges());
  if (window.LixityPublicationSettings) Object.assign(payload, window.LixityPublicationSettings.readChanges());
  var submittedCorpusFields = new Map();
  settings.querySelectorAll("[data-corpus-field]").forEach(function(field) {
    var shift = Number(field.dataset.decimalShift);
    var value = corpusNumber(field.value, shift);
    if (shift && value === 0 && field.validity.valid) field.setCustomValidity(uiLabel("settings_bound_error"));
    if (value !== corpusNumber(field.dataset.initial, shift)) {
      payload[field.dataset.corpusField] = value;
      submittedCorpusFields.set(field, field.value);
    }
  });
  var dossierDrafts = settings.querySelector("[data-dossier-drafts-key]");
  if (dossierDrafts) {
    var draftSettings = Object.fromEntries(Array.from(dossierDrafts.querySelectorAll("[data-dossier-drafts-field]"), function(field) {
      return [field.dataset.dossierDraftsField, field.type === "checkbox" ? field.checked : field.valueAsNumber];
    }));
    var initialDraftSettings = JSON.parse(dossierDrafts.dataset.initial);
    if (Object.keys(draftSettings).some(function(key) { return draftSettings[key] !== initialDraftSettings[key]; })) {
      payload[dossierDrafts.dataset.dossierDraftsKey] = draftSettings;
    }
  }
  if (locationMode && locationMode.value) {
    var configured = locationNames.value.split("\n").map(function(name) { return name.trim(); }).filter(Boolean);
    var searchNames = locationMode.value === "names";
    var limit = Number(locationNames.dataset.nameLimit);
    var lengthInvalid = configured.some(function(name) { return Array.from(name).length > limit; });
    locationNames.setCustomValidity(!searchNames ? "" : !configured.length ? uiLabel("settings_location_names_empty") :
      lengthInvalid ? uiFormat("settings_location_names_limit", {limit: limit}) : "");
    var places = searchNames ? configured : locationMode.value === "off" ? [] : locationMode.value;
    if (JSON.stringify(places) !== locationMode.dataset.initial) payload.locations = places;
  }
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
  settings.querySelectorAll("[data-threshold-key]").forEach(function(field) {
    payload[field.dataset.thresholdKey] = thresholdValue(field);
  });
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
      if (Object.prototype.hasOwnProperty.call(payload, "locations")) locationMode.dataset.initial = JSON.stringify(payload.locations);
      submittedCorpusFields.forEach(function(value, field) { field.dataset.initial = value; });
      if (dossierDrafts && Object.hasOwn(payload, dossierDrafts.dataset.dossierDraftsKey)) {
        dossierDrafts.dataset.initial = JSON.stringify(payload[dossierDrafts.dataset.dossierDraftsKey]);
      }
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
    if (btn.disabled || btn.dataset.payload === "settings") return;
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
      var {setStatus, setButtonPending} = window.LixityComponents;
      setButtonPending(btn, true);
      setStatus("ctl-status", uiLabel("research_ingesting_reading"), "loading");
      var reader = new FileReader();
      reader.onload = function () {
        runAction("load", { name: file.name, content: reader.result }, btn);
      };
      reader.onerror = reader.onabort = function () {
        manuscriptFileError("manuscript_read_failed");
        setButtonPending(btn, false);
      };
      try { reader.readAsText(file); }
      catch (_) { reader.onerror(); }
      return;
    }
    runAction(btn.dataset.action, payload, btn);
  });
});

function syncSelectPills(selectId) {
  var select = document.getElementById(selectId);
  if (!select) return;
  document.querySelectorAll('[data-sync-select="' + selectId + '"] button[data-value]').forEach(function (btn) {
    btn.setAttribute("aria-pressed", String(btn.dataset.value === select.value));
    btn.disabled = Boolean(select.disabled);
  });
}

(function initSelectPillGroups() {
  var groups = document.querySelectorAll("[data-sync-select]");
  if (!groups.length) return;
  var boundSelects = new Set();
  groups.forEach(function (group) {
    var selectId = group.dataset.syncSelect;
    var select = document.getElementById(selectId);
    if (!select) return;
    group.addEventListener("click", function (event) {
      var btn = event.target.closest("button[data-value]");
      if (!btn || btn.disabled || select.disabled) return;
      if (select.value !== btn.dataset.value) {
        select.value = btn.dataset.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
      syncSelectPills(selectId);
    });
    if (!boundSelects.has(selectId)) {
      boundSelects.add(selectId);
      select.addEventListener("change", function () { syncSelectPills(selectId); });
      new MutationObserver(function () { syncSelectPills(selectId); })
        .observe(select, { attributes: true, attributeFilter: ["disabled"] });
    }
    syncSelectPills(selectId);
  });

  var scopeStatus = document.getElementById("analysis-scope-status");
  if (scopeStatus) {
    new MutationObserver(function () {
      syncSelectPills("analysis-scope-register");
      syncSelectPills("analysis-scope-pov");
    }).observe(scopeStatus, { childList: true, characterData: true, subtree: true });
  }

})();
