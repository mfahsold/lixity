// Native disclosures retain their DOM (including unsaved form values).
function revealDisclosures(target) {
  for (var parent = target && target.parentElement; parent; parent = parent.parentElement) {
    if (parent.tagName === "DETAILS") parent.open = true;
  }
}

function collapseDisclosure(disclosure) {
  if (!disclosure || disclosure.tagName !== "DETAILS") return;
  disclosure.open = false;
  var summary = disclosure.querySelector(":scope > summary");
  if (summary) summary.focus({preventScroll: true});
  if (summary && summary.getBoundingClientRect().top < 0) summary.scrollIntoView({block: "nearest"});
}

document.addEventListener("click", function(event) {
  var close = event.target.closest("[data-close-disclosure]");
  if (close) collapseDisclosure(document.getElementById(close.dataset.closeDisclosure));
});

document.addEventListener("keydown", function(event) {
  if (event.key !== "Escape" || event.defaultPrevented || event.isComposing) return;
  // Let selects and temporary overlays manage their own Escape behavior.
  if (event.target.closest("select, [role=dialog], dialog, [role=listbox]")) return;
  var disclosure = event.target.closest("details[open]");
  if (!disclosure) return;
  event.preventDefault();
  collapseDisclosure(disclosure);
});

// Analysis interactions: paragraph open/close, jump-and-flash,
// style tabs and keyboard handling (extracted from dashboard.js).
function highlightCell(cell, on) {
  var table = cell.closest("table");
  if (!table) return;
  var row = cell.parentElement;
  var index = Array.prototype.indexOf.call(row.children, cell);
  row.querySelectorAll("td.z").forEach(function (td) {
    if (td === cell || index < 1) td.classList.toggle("hl", on);
  });
  if (index < 1) return;
  table.querySelectorAll("tbody tr").forEach(function (tr) {
    var td = tr.children[index];
    if (td) td.classList.toggle("hl", on);
  });
}

document.addEventListener("mouseover", function (event) {
  var cell = event.target.closest ? event.target.closest("td.z[data-chapter]") : null;
  if (cell) highlightCell(cell, true);
}, { passive: true });

document.addEventListener("mouseout", function (event) {
  var cell = event.target.closest ? event.target.closest("td.z[data-chapter]") : null;
  if (cell) highlightCell(cell, false);
}, { passive: true });

var passageMotionPreference = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)");
var reduceMotion = Boolean(passageMotionPreference && passageMotionPreference.matches);
if (passageMotionPreference) passageMotionPreference.addEventListener("change", function(event) {
  reduceMotion = event.matches;
});

function revealChapter(node) {
  var chapter = node && node.closest ? node.closest(".chapter.collapsed") : null;
  if (!chapter) return;
  var toggle = chapter.querySelector("[data-chapter-toggle]");
  if (toggle) toggleChapter(toggle, true);
}

function toggleChapter(toggle, expand) {
  var chapter = toggle.closest(".chapter");
  if (!chapter) return;
  var collapsed = expand === undefined ? !chapter.classList.contains("collapsed") : !expand;
  chapter.classList.toggle("collapsed", collapsed);
  toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
}

function passageScrollContainers(target) {
  var containers = [];
  for (var parent = target.parentElement; parent; parent = parent.parentElement) {
    var style = getComputedStyle(parent);
    if (/(auto|scroll|hidden)/.test(style.overflowY + style.overflowX) &&
        (parent.scrollHeight > parent.clientHeight || parent.scrollWidth > parent.clientWidth)) containers.push(parent);
  }
  return containers;
}

var passageArrival = null;
function flashOnArrival(target) {
  // A window scrollend can precede its nested scrollports. Observe the actual
  // destination and all scrolling ancestors, including layout changes.
  if (passageArrival) {
    cancelAnimationFrame(passageArrival.frame);
    clearTimeout(passageArrival.timer);
    passageArrival.target.classList.remove("flash");
  }
  passageArrival = null;
  // Cancel the incidental view-return cue before a destination starts settling.
  if (window.LixityMotion) window.LixityMotion.passage(null);
  if (!target || !target.isConnected) return;
  target.classList.remove("flash");
  var arrival = {target: target, frame: 0, timer: 0, prose: false};
  passageArrival = arrival;
  var containers = passageScrollContainers(target), previous = null;
  var started = performance.now(), stableSince = started;
  function watch(now) {
    if (passageArrival !== arrival) return;
    if (!target.isConnected || !target.getClientRects().length) { passageArrival = null; return; }
    var rect = target.getBoundingClientRect();
    var position = [rect.top, rect.left, rect.width, rect.height, window.scrollX, window.scrollY];
    var top = 0, bottom = innerHeight, left = 0, right = innerWidth;
    containers.forEach(function(container) {
      position.push(container.scrollTop, container.scrollLeft);
      var bounds = container.getBoundingClientRect();
      top = Math.max(top, bounds.top + container.clientTop);
      bottom = Math.min(bottom, bounds.top + container.clientTop + container.clientHeight);
      left = Math.max(left, bounds.left + container.clientLeft);
      right = Math.min(right, bounds.left + container.clientLeft + container.clientWidth);
    });
    if (!previous || position.some(function(value, index) { return Math.abs(value - previous[index]) > .5; })) stableSince = now;
    previous = position;
    var visible = rect.bottom > top && rect.top < bottom && rect.right > left && rect.left < right;
    if (visible && now - stableSince >= 100) {
      target.classList.add("flash");
      arrival.prose = target.matches("#chapters .ptext") && document.body.classList.contains("manuscript-reading");
      if (arrival.prose && window.LixityMotion) window.LixityMotion.passage(target);
      arrival.timer = setTimeout(function() {
        target.classList.remove("flash");
        if (passageArrival === arrival) passageArrival = null;
      }, 1600);
      return;
    }
    // Hidden or interrupted destinations must not announce a stale arrival.
    if (now - started >= 5000) { passageArrival = null; return; }
    arrival.frame = requestAnimationFrame(watch);
  }
  arrival.frame = requestAnimationFrame(watch);
}

function rememberPassageLocation(target) {
  // Replace an obsolete overview hash without scheduling another hash journey.
  try {
    history.replaceState(null, "", location.pathname + location.search + (target && target.id ? "#" + encodeURIComponent(target.id) : ""));
  } catch (_) { /* Navigation still works when history changes are restricted. */ }
}

function scrollAndFlash(target, options) {
  if (!target) return;
  options = options || {};
  var focused = document.activeElement;
  var leavingOverview = target.closest("#chapters") && window.LixityWorkbench &&
    window.LixityWorkbench.state().surface === "overview";
  var returnFocus = leavingOverview && focused &&
    focused.closest("#manuscript-analysis-panels, #analysis-review, #analysis-sections");
  var sceneDrill = focused && focused.matches(".scene-overview a[data-jump]") &&
    focused.getAttribute("data-jump") === "#" + target.id;
  var view = target.closest(".view-pane");
  if (view && !view.classList.contains("active")) switchActiveView(view.dataset.viewPane);
  if (target.closest("#manuscript-analysis-panels") && window.LixityReader) window.LixityReader.inspect();
  if (target.closest("#chapters") && window.LixityWorkbench && window.LixityWorkbench.state().surface !== "document") {
    window.LixityWorkbench.dispatch({type: "surface", value: "document"});
  }
  revealStyleTarget(target);
  revealDisclosures(target);
  revealChapter(target);
  // Scene drills continue inside their disclosures; manuscript drills leave
  // their hidden overview source. Other callers retain their focus owner.
  if ((sceneDrill || (returnFocus && !focused.getClientRects().length)) &&
      (document.activeElement === focused || document.activeElement === document.body)) {
    if (target.tabIndex < 0) target.tabIndex = -1;
    target.focus({preventScroll: true});
  }
  setPassageScrollMargin(target);
  reduceMotion = Boolean(passageMotionPreference && passageMotionPreference.matches);
  var behavior = options.behavior || "smooth";
  target.scrollIntoView({ behavior: reduceMotion && behavior === "smooth" ? "auto" : behavior, block: options.block || "start" });
  flashOnArrival(target);
}

function setPassageScrollMargin(target) {
  var bars = document.querySelectorAll("#workbench-thread, #manuscript-reader-controls, #view-pane-analysis .toolbar, .research-dossier-location");
  var height = 0, rect = target.getBoundingClientRect();
  var container = passageScrollContainers(target)[0];
  bars.forEach(function(bar) {
    if (!bar.getClientRects().length || target.contains(bar) || passageScrollContainers(bar)[0] !== container) return;
    var style = getComputedStyle(bar), bounds = bar.getBoundingClientRect();
    if (style.position === "sticky" && bounds.right > rect.left && bounds.left < rect.right) {
      height = Math.max(height, (parseFloat(style.top) || 0) + bounds.height);
    }
  });
  target.style.scrollMarginTop = (height + 12) + "px";
}

var paragraphContentNode = document.getElementById("paragraph-content");
var paragraphContent = paragraphContentNode ? JSON.parse(paragraphContentNode.textContent) : {};
if (paragraphContentNode) paragraphContentNode.remove();
document.querySelectorAll("#chapters .ptext > noscript").forEach(function(fallback) {
  fallback.remove();
});
var paragraphChips = Object.create(null);
document.querySelectorAll(".chip[data-target]").forEach(function(chip) {
  paragraphChips[chip.dataset.target] = chip;
});
document.body.classList.add("has-js-paragraphs");

// Search and explicit claim links share one renderer over the original text.
// Interval boundaries are UTF-16 DOM offsets; persisted anchors use codepoints.
var manuscriptParagraphMarks = Object.create(null);
function renderParagraphText(paragraph, query) {
  var panel = paragraph.closest(".ptext"), content = panel && paragraphContent[panel.id];
  if (!content) return;
  var selection = window.getSelection(), selected = null;
  if (selection && selection.rangeCount === 1 &&
      (paragraph.contains(selection.anchorNode) || paragraph.contains(selection.focusNode))) {
    function rememberPoint(node, offset) {
      if (!paragraph.contains(node)) return {node: node, offset: offset};
      var prefix = document.createRange();
      prefix.selectNodeContents(paragraph); prefix.setEnd(node, offset);
      return {offset: prefix.toString().length};
    }
    // DOM offsets are UTF-16 positions, including astral characters and text
    // split across search/claim marks. Keep anchor/focus direction as well.
    selected = {anchor: rememberPoint(selection.anchorNode, selection.anchorOffset),
      focus: rememberPoint(selection.focusNode, selection.focusOffset)};
  }
  var text = content[0], spans = [];
  paragraph.dataset.searchQuery = query || "";
  if (query) {
    // Case folding can expand characters such as İ. Match the original text
    // so every interval keeps its DOM offset; the query remains literal data.
    var pattern = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi"), match;
    while ((match = pattern.exec(text)) !== null) {
      spans.push({start: match.index, end: match.index + match[0].length, search: true});
    }
  }
  (manuscriptParagraphMarks[panel.id] || []).forEach(function(mark) { spans.push(mark); });
  var boundaries = Array.from(new Set([0, text.length].concat(spans.flatMap(function(span) {
    return [span.start, span.end];
  })))).sort(function(a, b) { return a - b; });
  var fragment = document.createDocumentFragment();
  for (var i = 0; i < boundaries.length - 1; i++) {
    var start = boundaries[i], end = boundaries[i + 1];
    var active = spans.filter(function(span) { return span.start <= start && span.end >= end; });
    if (!active.length) { fragment.appendChild(document.createTextNode(text.slice(start, end))); continue; }
    var mark = document.createElement("mark");
    mark.className = (active.some(function(span) {return span.search;}) ? "text-hit " : "") +
      (active.some(function(span) {return !span.search;}) ? "manuscript-claim-hit" : "");
    mark.textContent = text.slice(start, end);
    fragment.appendChild(mark);
  }
  paragraph.replaceChildren(fragment);
  if (selected) {
    function restorePoint(point) {
      if (point.node) return point;
      var walker = document.createTreeWalker(paragraph, NodeFilter.SHOW_TEXT), remaining = point.offset;
      while (walker.nextNode()) {
        if (remaining <= walker.currentNode.length) return {node: walker.currentNode, offset: remaining};
        remaining -= walker.currentNode.length;
      }
      return {node: paragraph, offset: paragraph.childNodes.length};
    }
    var anchor = restorePoint(selected.anchor), focus = restorePoint(selected.focus);
    if (selection.setBaseAndExtent) selection.setBaseAndExtent(anchor.node, anchor.offset, focus.node, focus.offset);
    else { selection.collapse(anchor.node, anchor.offset); selection.extend(focus.node, focus.offset); }
  }
}

function renderParagraph(panel, textOnly) {
  var inner = panel.querySelector(".ptext-inner");
  if (inner && inner.querySelector(textOnly ? "p" : ".paragraph-values")) return;
  var content = paragraphContent[panel.id];
  if (!content) return;
  if (!inner) {
    inner = document.createElement("div");
    inner.className = "ptext-inner";
    panel.appendChild(inner);
  }
  if (!inner.querySelector("p")) {
    var text = document.createElement("p");
    text.textContent = content[0];
    inner.appendChild(text);
    renderParagraphText(text, "");
  }
  if (textOnly) return;
  var values = document.createElement("details");
  values.className = "paragraph-values";
  var summary = document.createElement("summary");
  summary.textContent = uiLabel("paragraph_values");
  values.appendChild(summary);
  ["anchor", "stats"].forEach(function(name, index) {
    var field = document.createElement("div");
    field.className = name;
    field.textContent = content[index + 1];
    values.appendChild(field);
  });
  inner.appendChild(values);
  if (panel.dataset.markers === "1") {
    var row = document.createElement("div");
    row.className = "row marker-row";
    ["pruefen", "sachcheck", "todo", "achtung"].forEach(function(kind) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "ctl";
      button.dataset.markerKind = kind;
      button.dataset.line = panel.dataset.start;
      button.textContent = "+ " + uiLabel("marker_" + kind);
      row.appendChild(button);
    });
    var slot = document.createElement("span");
    slot.className = "marker-note-slot";
    slot.dataset.placeholder = uiLabel("marker_note");
    row.appendChild(slot);
    inner.appendChild(row);
  }
  document.dispatchEvent(new CustomEvent("lixity:paragraph-rendered", {detail: panel}));
}

function panelNeedsScroll(panel) {
  var rect = panel.getBoundingClientRect();
  return rect.top >= innerHeight - 24 || rect.bottom <= 0;
}

function toggleParagraph(chip, forceOpen, instant) {
  var panel = document.getElementById(chip.dataset.target);
  if (!panel) return;
  var fromClick = forceOpen === undefined;
  var open = forceOpen === undefined ? !panel.classList.contains("open") : forceOpen;
  if (open) revealChapter(panel);
  // A collapsed panel measures zero height. Scrolling to that stale geometry
  // lands the expanded block past the viewport ("clicks do not get through",
  // imprecise anchors). Expand synchronously whenever a scroll follows.
  var instantExpand = Boolean(open && (instant || (fromClick && panelNeedsScroll(panel))));
  if (instantExpand) panel.classList.add("no-anim");
  panel.classList.toggle("open", open);
  chip.classList.toggle("active", open);
  chip.setAttribute("aria-expanded", open ? "true" : "false");
  if (open) {
    renderParagraph(panel);
    panel.style.borderLeftColor = chip.style.getPropertyValue("--layer-color") || "";
    if (instantExpand) void panel.offsetHeight;
    if (fromClick) {
      scrollAndFlash(panel, {block: "nearest"});
    }
    if (instantExpand) requestAnimationFrame(function () {
      requestAnimationFrame(function () { panel.classList.remove("no-anim"); });
    });
  } else if (!panel.querySelector(".marker-note") && !document.body.classList.contains("manuscript-reading")) {
    var inner = panel.querySelector(".ptext-inner");
    if (inner) inner.remove();
  }
}

function selectStyleView(viewId, focus) {
  var tabs = document.querySelectorAll("#style-tabs [data-style-view]");
  tabs.forEach(function(tab) {
    var selected = tab.dataset.styleView === viewId;
    tab.setAttribute("aria-selected", selected ? "true" : "false");
    tab.tabIndex = selected ? 0 : -1;
    var panel = document.getElementById(tab.dataset.styleView);
    if (panel) {
      panel.hidden = !selected;
      panel.setAttribute("role", "tabpanel");
      panel.setAttribute("aria-labelledby", tab.id);
    }
    if (selected && focus) tab.focus();
  });
  window.dispatchEvent(new Event("resize"));
}

function syncTabStops(container, selector) {
  var tabs = Array.from(container.querySelectorAll(selector));
  var active = tabs.find(function(tab) { return tab.getAttribute("aria-selected") === "true"; }) || tabs[0];
  tabs.forEach(function(tab) { tab.tabIndex = tab === active ? 0 : -1; });
}

function initKeyboardTabs(container, selector, manual) {
  if (!container || container.dataset.keyboardTabs === "true") return;
  container.dataset.keyboardTabs = "true";
  syncTabStops(container, selector);
  new MutationObserver(function() { syncTabStops(container, selector); }).observe(container,
    {subtree: true, attributes: true, attributeFilter: ["aria-selected"]});
  container.addEventListener("click", function() {
    queueMicrotask(function() { syncTabStops(container, selector); });
  });
  container.addEventListener("keydown", function(event) {
    var tabs = Array.from(container.querySelectorAll(selector)).filter(function(tab) { return !tab.disabled; });
    var index = tabs.indexOf(event.target);
    if (index < 0 || !tabs.length) return;
    var vertical = container.getAttribute("aria-orientation") === "vertical";
    if (event.key === (vertical ? "ArrowDown" : "ArrowRight")) index = (index + 1) % tabs.length;
    else if (event.key === (vertical ? "ArrowUp" : "ArrowLeft")) index = (index + tabs.length - 1) % tabs.length;
    else if (event.key === "Home") index = 0;
    else if (event.key === "End") index = tabs.length - 1;
    else return;
    event.preventDefault();
    tabs[index].focus();
    if (!manual) tabs[index].click();
  });
}

function revealStyleTarget(target) {
  if (window.LixityAnalysisScope) window.LixityAnalysisScope.reveal(target);
  var panel = target.closest("#style-panels > .panel");
  if (panel) selectStyleView(panel.id, false);
}

(function() {
  var list = document.getElementById("style-tabs");
  if (!list) return;
  var tabs = Array.prototype.slice.call(list.querySelectorAll("[data-style-view]"));
  list.hidden = false;
  if (tabs.length) selectStyleView(tabs[0].dataset.styleView, false);
  list.addEventListener("click", function(event) {
    var tab = event.target.closest("[data-style-view]");
    if (tab) selectStyleView(tab.dataset.styleView, false);
  });
  initKeyboardTabs(list, "[data-style-view]", false);
})();

