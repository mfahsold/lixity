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

var reduceMotion = window.matchMedia
  && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

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

function flashOnArrival(target) {
  // Flash after the smooth scroll settles; a flash that fades mid-scroll
  // leaves the destination unmarked ("the anchor does not sit precisely").
  var start = window.scrollY, frames = 0;
  function show() {
    target.classList.add("flash");
    setTimeout(function () { target.classList.remove("flash"); }, 1600);
  }
  function waitForEnd() {
    if ("onscrollend" in window) {
      var handler = function () { window.removeEventListener("scrollend", handler); show(); };
      window.addEventListener("scrollend", handler);
      setTimeout(function () { window.removeEventListener("scrollend", handler); show(); }, 2000);
      return;
    }
    setTimeout(show, 450);
  }
  (function watch() {
    frames += 1;
    if (window.scrollY !== start) { waitForEnd(); return; }
    if (frames < 3) { requestAnimationFrame(watch); return; }
    show();
  })();
}

function scrollAndFlash(target) {
  var view = target.closest(".view-pane");
  if (view) switchActiveView(view.dataset.viewPane);
  revealStyleTarget(target);
  revealChapter(target);
  target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  flashOnArrival(target);
}

var paragraphContentNode = document.getElementById("paragraph-content");
var paragraphContent = paragraphContentNode ? JSON.parse(paragraphContentNode.textContent) : {};
if (paragraphContentNode) paragraphContentNode.remove();
document.querySelectorAll("#chapters .ptext-inner").forEach(function(inner) {
  inner.replaceChildren();
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
}

function renderParagraph(panel) {
  var inner = panel.querySelector(".ptext-inner");
  if (!inner || inner.querySelector("p")) return;
  var content = paragraphContent[panel.id];
  if (!content) return;
  inner.replaceChildren();
  var text = document.createElement("p");
  text.textContent = content[0];
  inner.appendChild(text);
  renderParagraphText(text, "");
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
      panel.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
      flashOnArrival(panel);
    }
    if (instantExpand) requestAnimationFrame(function () {
      requestAnimationFrame(function () { panel.classList.remove("no-anim"); });
    });
  } else if (!panel.querySelector(".marker-note")) {
    panel.querySelector(".ptext-inner").replaceChildren();
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
    if (event.key === "ArrowRight") index = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft") index = (index + tabs.length - 1) % tabs.length;
    else if (event.key === "Home") index = 0;
    else if (event.key === "End") index = tabs.length - 1;
    else return;
    event.preventDefault();
    tabs[index].focus();
    if (!manual) tabs[index].click();
  });
}

function revealStyleTarget(target) {
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

