// Reading and inspection share source text, anchors and existing action handlers.
(function () {
  "use strict";
  var controls = document.getElementById("manuscript-reader-controls");
  var chapters = document.getElementById("chapters");
  if (!controls || !chapters) return;
  var mode = document.getElementById("manuscript-mode");
  var workbench = window.LixityWorkbench;
  var analysisToggle = document.getElementById("manuscript-analysis-toggle");
  var dock = document.getElementById("workspace-context-panel");
  var layout = document.getElementById("workspace-reader-layout");
  var overviewAnchor = null, inspectorTarget = null, origin = null;
  var panels = Array.from(chapters.querySelectorAll(".ptext"));
  var menu = document.getElementById("manuscript-context-menu");
  var selectionTools = document.getElementById("manuscript-selection-tools");
  var inspector = document.getElementById("reader-inspector");
  var inspectorBody = document.getElementById("reader-inspector-body");
  var focus = document.getElementById("reader-focus");
  var settings = document.getElementById("reader-settings");
  var width = document.getElementById("reader-width");
  var spacing = document.getElementById("reader-spacing");
  var current = null, savedRange = null, returnTarget = null, selecting = false;
  var preferences = {size: 18, width: "standard", spacing: "standard"};
  function read(key) { try { return localStorage.getItem(key); } catch (_) { return null; } }
  function save(key, value) { try { localStorage.setItem(key, value); } catch (_) { /* Display works without storage. */ } }
  try {
    var stored = JSON.parse(read("lixity.manuscript.reader") || "null");
    if (stored && typeof stored === "object") {
      if (Number.isFinite(stored.size)) preferences.size = Math.min(28, Math.max(16, stored.size));
      if (["narrow", "standard", "wide"].includes(stored.width)) preferences.width = stored.width;
      if (["compact", "standard", "relaxed"].includes(stored.spacing)) preferences.spacing = stored.spacing;
    }
  } catch (_) { /* A malformed preference never changes manuscript data. */ }
  function capture() {
    if (workbench.state().view !== "analysis" || workbench.state().surface !== "document") return null;
    var boundary = controls.getBoundingClientRect().bottom;
    var panel = Array.from(chapters.querySelectorAll(".ptext, .reader-structural")).find(function(candidate) {
      var rect = candidate.getBoundingClientRect();
      return rect.height > 0 && rect.bottom > boundary && rect.top < innerHeight;
    });
    return panel ? {panel: panel, top: panel.getBoundingClientRect().top} : null;
  }
  function restore(anchor) {
    if (!anchor) return;
    requestAnimationFrame(function() {
      if (anchor.panel.isConnected) window.scrollBy(0, anchor.panel.getBoundingClientRect().top - anchor.top);
    });
  }
  function retain(action) { var anchor = capture(); action(); restore(anchor); }
  function appearance() {
    document.body.style.setProperty("--reader-font-size", (preferences.size / 16) + "rem");
    document.body.style.setProperty("--reader-measure", {narrow: "54ch", standard: "68ch", wide: "78ch"}[preferences.width]);
    document.body.style.setProperty("--reader-leading", {compact: "1.5", standard: "1.8", relaxed: "2.1"}[preferences.spacing]);
    width.value = preferences.width; spacing.value = preferences.spacing;
    document.getElementById("reader-size-value").value = String(preferences.size);
    document.getElementById("reader-text-smaller").disabled = preferences.size <= 16;
    document.getElementById("reader-text-larger").disabled = preferences.size >= 28;
    save("lixity.manuscript.reader", JSON.stringify(preferences));
  }
  function enhanceText(panel) {
    renderParagraph(panel, true);
    var inner = panel.querySelector(".ptext-inner");
    if (!inner || inner.querySelector(".reader-paragraph-actions")) return;
    var button = document.createElement("button");
    button.type = "button"; button.className = "ctl reader-paragraph-actions";
    button.dataset.readerParagraph = panel.id; button.textContent = "…";
    button.setAttribute("aria-label", uiLabel("reading_actions"));
    button.setAttribute("aria-haspopup", "menu"); button.setAttribute("aria-controls", menu.id);
    button.setAttribute("aria-expanded", "false");
    inner.appendChild(button);
    panel.tabIndex = -1;
  }
  function closeMenu(restoreFocus) {
    menu.hidden = true;
    if (returnTarget) returnTarget.setAttribute("aria-expanded", "false");
    if (restoreFocus && returnTarget && returnTarget.isConnected) returnTarget.focus({preventScroll: true});
  }
  function closeInspector(restoreFocus) {
    workbench.dispatch({type: "tool", value: "none"});
    if (restoreFocus && inspectorTarget && inspectorTarget.isConnected) {
      var button = inspectorTarget.querySelector(".reader-paragraph-actions");
      if (button) button.focus({preventScroll: true});
    }
  }
  function setFocus(value) {
    retain(function() { workbench.dispatch({type: "focus", value: value}); });
  }
  // Compatibility callers request an analysis overview, without replacing prose.
  function setMode(value) {
    if (value === "inspect") {
      if (workbench.state().surface !== "overview") overviewAnchor = capture();
      workbench.dispatch({type: "surface", value: "overview"});
    } else workbench.dispatch({type: "surface", value: "document"});
  }
  function showValues(panel) {
    if (!panel) return;
    renderParagraph(panel);
    var values = panel.querySelector(".paragraph-values");
    if (!values) return;
    var copy = values.cloneNode(true); copy.open = true;
    if (inspectorTarget) inspectorTarget.classList.remove("reader-inspector-target");
    inspectorBody.replaceChildren(copy); inspectorTarget = panel;
    panel.classList.add("reader-inspector-target");
  }
  if (dock) dock.appendChild(inspector);
  workbench.subscribe(function(state, previous) {
    var anchor = capture();
    var open = state.contextTool !== "none" && state.surface === "document";
    if (layout) layout.classList.toggle("is-open", open);
    if (dock) dock.hidden = !open;
    var divider = document.getElementById("workspace-reader-divider");
    if (divider) divider.hidden = !open;
    inspector.hidden = state.contextTool !== "analysis" || state.surface !== "document";
    document.body.classList.toggle("reader-inspector-open", !inspector.hidden);
    if (!inspector.hidden && !inspectorBody.childElementCount) {
      if (anchor && anchor.panel.matches(".ptext")) showValues(anchor.panel);
      else inspectorBody.textContent = uiLabel(panels.length ? "reading_values_hint" : "reading_coverage");
    }
    document.querySelectorAll("[data-context-tool]").forEach(function(button) {
      button.setAttribute("aria-pressed", String(state.contextTool === button.dataset.contextTool));
    });
    analysisToggle.setAttribute("aria-pressed", String(state.analysisVisible));
    document.getElementById("manuscript-analysis-state").textContent = uiLabel(state.analysisVisible ? "reading_on" : "reading_off");
    mode.value = state.surface === "overview" ? "inspect" : "read";
    document.getElementById("workbench-overview-open").hidden = state.surface === "overview";
    document.getElementById("workbench-overview-back").hidden = state.surface !== "overview";
    document.getElementById("workbench-overview-label").hidden = state.surface !== "overview";
    focus.setAttribute("aria-pressed", String(state.focus));
    focus.textContent = uiLabel(state.focus ? "reading_focus_exit" : "reading_focus");
    if (window.LixityWorkspaceNavigation) window.LixityWorkspaceNavigation.companion(open);
    if (state.view !== previous.view || state.surface !== previous.surface) {
      closeMenu(false); selectionTools.hidden = true; settings.open = false;
    }
    if (state.surface === previous.surface && state.view === previous.view &&
        (state.contextTool !== previous.contextTool || state.analysisVisible !== previous.analysisVisible || state.focus !== previous.focus)) restore(anchor);
    window.dispatchEvent(new Event("resize"));
  });
  function rangeFor(panel) {
    var selection = window.getSelection();
    if (!selection || selection.rangeCount !== 1 || selection.isCollapsed) return null;
    var range = selection.getRangeAt(0), paragraph = panel.querySelector(".ptext-inner > p");
    if (!paragraph || !paragraph.contains(range.startContainer) || !paragraph.contains(range.endContainer) || !selection.toString().trim()) return null;
    return range.cloneRange();
  }
  function place(node, x, y) {
    node.hidden = false; node.style.left = "0px"; node.style.top = "0px";
    var rect = node.getBoundingClientRect();
    node.style.left = Math.max(8, Math.min(x, innerWidth - rect.width - 8)) + "px";
    node.style.top = Math.max(8, Math.min(y, innerHeight - rect.height - 8)) + "px";
    node._readerScroll = [window.scrollX, window.scrollY];
  }
  function actionButton(action, label, menuItem) {
    var button = document.createElement("button"); button.type = "button";
    button.className = "ctl"; button.dataset.readerAction = action;
    button.textContent = uiLabel(label);
    if (menuItem) { button.setAttribute("role", "menuitem"); button.tabIndex = -1; }
    return button;
  }
  function actions(panel, compact) {
    renderParagraph(panel);
    var fragment = document.createDocumentFragment();
    if (!compact) fragment.appendChild(actionButton("values", "paragraph_values", true));
    if (panel.querySelector("[data-manuscript-link-selection]") && savedRange && Array.from(savedRange.toString()).length <= 10000) {
      fragment.appendChild(actionButton("link", "manuscript_link_action", !compact));
    }
    if (panel.dataset.markers === "1") {
      (compact ? ["pruefen"] : ["pruefen", "sachcheck", "todo", "achtung"]).forEach(function(kind) {
        var marker = panel.querySelector('[data-marker-kind="' + kind + '"]');
        if (marker && !marker.disabled && marker.getAttribute("aria-disabled") !== "true") fragment.appendChild(actionButton(kind, "marker_" + kind, !compact));
      });
    }
    var companion = document.getElementById("workspace-reader-toggle");
    if (!compact && companion && !companion.disabled) fragment.appendChild(actionButton("companion", "reader_toggle", true));
    return fragment;
  }
  function openMenu(panel, x, y, trigger) {
    closeMenu(false); selectionTools.hidden = true;
    current = panel; savedRange = rangeFor(panel);
    returnTarget = trigger || panel.querySelector(".reader-paragraph-actions") || panel;
    menu.replaceChildren(actions(panel, false));
    place(menu, x, y); returnTarget.setAttribute("aria-expanded", "true");
    var first = menu.querySelector("button"); if (first) { first.tabIndex = 0; first.focus({preventScroll: true}); }
  }
  function run(action) {
    if (!current || !current.isConnected) return;
    var panel = current, range = rangeFor(current) || savedRange;
    closeMenu(false); selectionTools.hidden = true;
    renderParagraph(panel);
    if ((action === "values" || action === "companion") && document.body.classList.contains("reader-focus")) setFocus(false);
    if (action === "values") {
      showValues(panel);
      retain(function() { workbench.dispatch({type: "tool", value: "analysis"}); });
      document.getElementById("reader-inspector-close").focus({preventScroll: true});
    } else if (action === "link") {
      if (!range) return;
      var selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
      var link = panel.querySelector("[data-manuscript-link-selection]"); if (link) link.click();
    } else if (action === "companion") {
      var toggle = document.getElementById("workspace-reader-toggle");
      if (toggle.getAttribute("aria-expanded") !== "true") toggle.click();
      var close = document.getElementById("workspace-reader-close");
      if (close) close.focus({preventScroll: true});
    } else {
      var marker = panel.querySelector('[data-marker-kind="' + action + '"]');
      if (marker) marker.click();
    }
  }
  controls.hidden = false; appearance();
  settings.addEventListener("toggle", function() {
    if (!settings.open) return;
    var summary = settings.querySelector("summary").getBoundingClientRect();
    place(settings.querySelector(".reader-settings-body"), summary.left, summary.bottom + 6);
  });
  mode.addEventListener("change", function() { setMode(mode.value); });
  analysisToggle.addEventListener("click", function() {
    var previous = workbench.state(), anchor = capture();
    if (!previous.analysisVisible && previous.contextTool === "none" && !inspectorBody.childElementCount &&
        anchor && anchor.panel.matches(".ptext")) showValues(anchor.panel);
    retain(function() { workbench.dispatch({type: "analysis", value: !previous.analysisVisible}); });
    if (previous.surface === "overview") {
      rememberPassageLocation(overviewAnchor && overviewAnchor.panel); restore(overviewAnchor);
    }
  });
  document.querySelectorAll("[data-context-tool]").forEach(function(button) {
    button.addEventListener("click", function() { retain(function() {
      workbench.dispatch({type: "tool", value: button.dataset.contextTool});
    }); });
  });
  document.getElementById("workbench-overview-open").addEventListener("click", function() {
    overviewAnchor = capture(); workbench.dispatch({type: "surface", value: "overview"});
    controls.scrollIntoView({block: "start"});
    document.getElementById("workbench-overview-back").focus({preventScroll: true});
  });
  document.getElementById("workbench-overview-back").addEventListener("click", function() {
    rememberPassageLocation(overviewAnchor && overviewAnchor.panel);
    workbench.dispatch({type: "surface", value: "document"}); restore(overviewAnchor);
    document.getElementById("workbench-overview-open").focus({preventScroll: true});
  });
  document.getElementById("reader-text-smaller").addEventListener("click", function() { retain(function() { preferences.size = Math.max(16, preferences.size - 2); appearance(); }); });
  document.getElementById("reader-text-larger").addEventListener("click", function() { retain(function() { preferences.size = Math.min(28, preferences.size + 2); appearance(); }); });
  [width, spacing].forEach(function(select) { select.addEventListener("change", function() { retain(function() { preferences[select === width ? "width" : "spacing"] = select.value; appearance(); }); }); });
  focus.addEventListener("click", function() { setFocus(!document.body.classList.contains("reader-focus")); });
  document.getElementById("reader-chapter").addEventListener("change", function(event) {
    var chapter = document.getElementById(event.target.value);
    if (chapter) {
      var search = document.getElementById("text-search");
      if (search && search.value) document.getElementById("text-search-clear").click();
      revealChapter(chapter); setPassageScrollMargin(chapter);
      chapter.scrollIntoView({block: "start", behavior: reduceMotion ? "auto" : "smooth"});
      event.target.value = "";
    }
  });
  document.getElementById("reader-inspector-close").addEventListener("click", function() { retain(function() { closeInspector(true); }); });
  chapters.addEventListener("click", function(event) {
    var trigger = event.target.closest("[data-reader-paragraph]");
    if (!trigger) return;
    var rect = trigger.getBoundingClientRect(); openMenu(document.getElementById(trigger.dataset.readerParagraph), rect.left, rect.bottom + 4, trigger);
  });
  chapters.addEventListener("contextmenu", function(event) {
    var panel = event.target.closest(".ptext");
    if (!panel || event.shiftKey || !document.body.classList.contains("manuscript-reading") || event.target.closest("input, textarea, select, a")) return;
    event.preventDefault(); openMenu(panel, event.clientX, event.clientY);
  });
  [menu, selectionTools].forEach(function(host) {
    host.addEventListener("pointerdown", function(event) { event.preventDefault(); });
    host.addEventListener("click", function(event) { var action = event.target.closest("[data-reader-action]"); if (action) run(action.dataset.readerAction); });
  });
  document.addEventListener("pointerdown", function(event) {
    selecting = chapters.contains(event.target);
    if (settings.open && !settings.contains(event.target)) settings.open = false;
    if (!menu.hidden && !menu.contains(event.target) && !event.target.closest("[data-reader-paragraph]")) closeMenu(false);
    if (!selectionTools.contains(event.target)) selectionTools.hidden = true;
  });
  function showSelection() {
    if (workbench.state().view !== "analysis" || workbench.state().surface !== "document" || !menu.hidden) return;
    var selection = window.getSelection();
    var node = selection && selection.anchorNode;
    var element = node && (node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement);
    var panel = element && element.closest("#chapters .ptext");
    var range = panel && rangeFor(panel);
    if (!range) { selectionTools.hidden = true; return; }
    current = panel; savedRange = range;
    selectionTools.replaceChildren(actions(panel, true));
    if (!selectionTools.childElementCount) return;
    var rect = range.getBoundingClientRect(); place(selectionTools, rect.left, rect.bottom + 6);
  }
  document.addEventListener("pointerup", function() { if (selecting) { selecting = false; requestAnimationFrame(showSelection); } });
  document.addEventListener("keyup", function(event) { if (event.shiftKey || event.key === "Shift") showSelection(); });
  document.addEventListener("selectionchange", function() { if (!selecting) requestAnimationFrame(showSelection); });
  document.addEventListener("keydown", function(event) {
    if (workbench.state().view !== "analysis") return;
    if (!menu.hidden) {
      var items = Array.from(menu.querySelectorAll("button")), index = items.indexOf(document.activeElement);
      if (event.key === "Escape") {
        event.preventDefault(); event.stopImmediatePropagation(); closeMenu(true); return;
      }
      if (event.key === "Tab") { closeMenu(true); return; }
      if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
        event.preventDefault(); event.stopImmediatePropagation();
        index = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 : (index + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
        items.forEach(function(item, i) { item.tabIndex = i === index ? 0 : -1; }); items[index].focus(); return;
      }
    }
    if ((event.key === "ContextMenu" || (event.key === "F10" && event.shiftKey)) && document.body.classList.contains("manuscript-reading")) {
      var panel = event.target.closest(".ptext");
      if (panel) { event.preventDefault(); event.stopImmediatePropagation(); var rect = panel.getBoundingClientRect(); openMenu(panel, rect.left + 12, rect.top + 12, event.target); }
      return;
    }
    if (event.key !== "Escape" || event.defaultPrevented || event.isComposing || event.target.closest("dialog, [role=dialog], select, input, textarea")) return;
    if (!selectionTools.hidden) { selectionTools.hidden = true; event.preventDefault(); event.stopImmediatePropagation(); }
    else if (settings.open) { event.preventDefault(); event.stopImmediatePropagation(); settings.open = false; settings.querySelector("summary").focus({preventScroll: true}); }
    else if (!inspector.hidden && !document.body.classList.contains("reader-focus")) { event.preventDefault(); event.stopImmediatePropagation(); retain(function() { closeInspector(true); }); }
    else if (document.body.classList.contains("reader-focus") && !event.target.closest("details[open]")) { event.preventDefault(); event.stopImmediatePropagation(); setFocus(false); focus.focus({preventScroll: true}); }
    else if (document.body.classList.contains("manuscript-reading") && event.target.closest("#chapters")) {
      // Escape never removes continuous prose. Existing note/disclosure handlers run.
      if (!event.target.closest("details[open]")) { event.preventDefault(); event.stopImmediatePropagation(); }
    }
  }, true);
  document.addEventListener("lixity:viewchange", function() {
    closeMenu(false); selectionTools.hidden = true;
    var pane = document.getElementById("view-pane-analysis");
    if (pane && !pane.classList.contains("active") && document.body.classList.contains("reader-focus")) setFocus(false);
  });

  window.addEventListener("scroll", function() {
    [menu, selectionTools].forEach(function(overlay) {
      var opened = overlay._readerScroll;
      if (!overlay.hidden && opened && (opened[0] !== window.scrollX || opened[1] !== window.scrollY)) {
        if (overlay === menu) closeMenu(false); else overlay.hidden = true;
      }
    });
  }, {passive: true});
  window.addEventListener("resize", function() { closeMenu(false); selectionTools.hidden = true; });
  var returnButton = document.getElementById("workbench-return");
  var shell = document.querySelector(".workspace-shell");
  if (shell) shell.appendChild(returnButton);
  function sourceContext() {
    var workspace = document.getElementById("manuscript-pdf-form") || document.getElementById("workspace-reader");
    return [workspace ? workspace.dataset.projectToken : document.body.dataset.manuscriptProjectToken,
      document.body.dataset.manuscriptSourceSha256, window.LixityWorkspaceReader && window.LixityWorkspaceReader.contextToken()].join(":");
  }
  document.addEventListener("click", function(event) {
    var relation = event.target.closest("[data-research-history], [data-workspace-dossier], [data-manuscript-link-jump], [data-manuscript-links-claim], [data-manuscript-links-dossier], [data-manuscript-links-paragraph], .manuscript-claim-hit");
    if (!relation || workbench.state().view !== "analysis" || workbench.state().surface !== "document") return;
    var panel = event.target.closest(".ptext");
    var anchor = panel ? {panel: panel, top: panel.getBoundingClientRect().top} : capture();
    if (!anchor) return;
    var range = rangeFor(anchor.panel), offsets = null;
    if (range) {
      var paragraph = anchor.panel.querySelector(".ptext-inner > p"), selection = getSelection();
      var prefix = document.createRange(); prefix.selectNodeContents(paragraph);
      prefix.setEnd(selection.anchorNode, selection.anchorOffset); var from = prefix.toString().length;
      prefix.setEnd(selection.focusNode, selection.focusOffset);
      offsets = {anchor: from, focus: prefix.toString().length};
    }
    origin = {anchor: anchor, offsets: offsets, hash: anchor.panel.dataset.paragraphSha256, context: sourceContext()};
    returnButton.hidden = false;
  }, true);
  returnButton.addEventListener("click", function() {
    if (!origin || origin.context !== sourceContext() || !origin.anchor.panel.isConnected || origin.hash !== origin.anchor.panel.dataset.paragraphSha256) {
      origin = null; returnButton.hidden = true; return;
    }
    switchActiveView("analysis"); workbench.dispatch({type: "surface", value: "document"});
    rememberPassageLocation(origin.anchor.panel);
    revealChapter(origin.anchor.panel); restore(origin.anchor);
    origin.anchor.panel.tabIndex = -1;
    origin.anchor.panel.focus({preventScroll: true});
    if (origin.offsets) {
      var paragraph = origin.anchor.panel.querySelector(".ptext-inner > p");
      var content = paragraphContent[origin.anchor.panel.id];
      if (paragraph && content && paragraph.textContent === content[0]) {
        function point(offset) {
          var walker = document.createTreeWalker(paragraph, NodeFilter.SHOW_TEXT);
          while (walker.nextNode()) {
            if (offset <= walker.currentNode.length) return {node: walker.currentNode, offset: offset};
            offset -= walker.currentNode.length;
          }
          return null;
        }
        var from = point(origin.offsets.anchor), to = point(origin.offsets.focus), selection = getSelection();
        if (from && to) {
          if (selection.setBaseAndExtent) selection.setBaseAndExtent(from.node, from.offset, to.node, to.offset);
          else { selection.collapse(from.node, from.offset); selection.extend(to.node, to.offset); }
        }
      }
    }
    origin = null; returnButton.hidden = true;
  });
  window.LixityReader = {capture: capture, restore: restore, retain: retain,
    inspect: function() { setMode("inspect", true); }};
  document.body.classList.add("manuscript-reading");
  panels.forEach(enhanceText);
  document.dispatchEvent(new Event("lixity:reader-ready"));
  workbench.dispatch({type: "analysis", value: false});
  var hash = document.getElementById(window.location.hash.slice(1));
  if (hash && hash.closest("#manuscript-analysis-panels")) setMode("inspect", true);
  if (hash && hash.closest("#chapters, #manuscript-analysis-panels")) requestAnimationFrame(function() { scrollAndFlash(hash); });
})();
