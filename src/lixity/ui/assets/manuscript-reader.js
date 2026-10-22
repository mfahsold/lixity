// One reading thread retains a nearest dossier departure above an optional
// manuscript journey. Research-only projects use the same return control.
(function() {
  "use strict";
  var shell = document.querySelector(".workspace-shell"), workbench = window.LixityWorkbench;
  if (!shell || !workbench) return;
  var button = document.getElementById("workbench-return");
  if (!button) {
    button = document.createElement("button"); button.id = "workbench-return";
    button.type = "button"; button.className = "ctl";
    button.dataset.help = uiLabel("reading_help_return");
  }
  var thread = document.createElement("aside"), originText = document.createElement("p"), recordText = document.createElement("p");
  thread.id = "workbench-thread"; thread.className = "workbench-thread";
  thread.setAttribute("aria-label", uiLabel("reading_thread"));
  originText.className = recordText.className = "ctl-note";
  recordText.setAttribute("aria-live", "polite");
  thread.append(originText, recordText, button); shell.appendChild(thread);
  var sidebar = window.matchMedia("(min-width: 1100px)");
  function threadHeight() {
    var height = !sidebar.matches && !thread.hidden ? thread.getBoundingClientRect().height : 0;
    var value = height + "px";
    if (document.body.style.getPropertyValue("--workbench-return-height") !== value) {
      document.body.style.setProperty("--workbench-return-height", value);
    }
  }
  function placeThread() {
    var focused = thread.contains(document.activeElement) ? document.activeElement : null;
    thread.classList.toggle("workbench-thread-mobile", !sidebar.matches);
    // The mobile parent spans every view, so its sticky return is not bounded
    // by the short project/navigation shell that precedes the destination.
    if (sidebar.matches) shell.appendChild(thread);
    else shell.after(thread);
    if (focused && document.activeElement !== focused) focused.focus({preventScroll: true});
    threadHeight();
  }
  sidebar.addEventListener("change", placeThread);
  if (typeof ResizeObserver === "function") new ResizeObserver(threadHeight).observe(thread);
  placeThread();
  var passage = null, dossier = null, pendingDossier = null, viewed = null, returnSerial = 0;
  function context() {
    var host = document.getElementById("manuscript-pdf-form") || document.getElementById("workspace-reader") || document.body;
    return [researchContextToken(), researchSelectionProjectId, host.dataset.projectToken,
      document.body.dataset.manuscriptProjectToken, document.body.dataset.manuscriptSourceSha256].join(":");
  }
  function current(value) {
    return value && value.context === context() && value.reading.current() &&
      value.control.isConnected && value.reading.root.contains(value.control);
  }
  function text(node, value) { if (node.textContent !== value) node.textContent = value; }
  function update() {
    if (dossier && !current(dossier)) dossier = null;
    if (pendingDossier && !current(pendingDossier)) pendingDossier = null;
    if (passage && !passage.valid()) passage = null;
    thread.hidden = button.hidden = !dossier && !passage;
    text(button, uiLabel(dossier ? "reading_back_dossier" : "reading_back"));
    text(originText, dossier ? uiFormat("reading_dossier_origin", {title: dossier.reading.title, revision: dossier.reading.revision}) : passage ? passage.description : "");
    text(recordText, viewed && (dossier || passage) ? uiLabel("reading_reviewed") + ": " +
      uiLabel("research_revision_kind_" + viewed.kind) + " · " + viewed.title + " · " +
      uiFormat("research_revision_number", {revision: viewed.revision}) +
      (viewed.pinned || viewed.current ? " · " + uiLabel(viewed.pinned ? "reading_pinned" : "research_revision_current") : "") : "");
    threadHeight();
  }
  function capture(reading, control) {
    var scrolls = [];
    for (var node = control.parentElement; node; node = node.parentElement) {
      scrolls.push({node: node, top: node.scrollTop, left: node.scrollLeft});
    }
    return {reading: reading, control: control, context: context(), state: workbench.state(),
      tab: document.querySelector(".research-tabs button.active"), scrolls: scrolls,
      top: window.scrollY, left: window.scrollX};
  }
  document.addEventListener("click", function(event) {
    var action = event.target.closest("[data-manuscript-links-claim], [data-manuscript-links-dossier], [data-research-global], [data-dossier-claim], [data-dossier-decision], [data-use-passage], [data-research-history=claim]");
    if (!action) return;
    var root = action.closest("[data-dossier-reading]"), reading = root && root._dossierReading;
    if (reading && reading.current()) {
      var value = capture(reading, action);
      // Native Close already returns from a record viewer. Keep its dossier
      // only as a candidate if that viewer subsequently leaves for Review.
      if (action.matches("[data-research-history=claim]")) { pendingDossier = value; return; }
      dossier = value; viewed = null; ++returnSerial; update();
    } else if (action.closest("#modal-research-revision") &&
        action.matches("[data-manuscript-links-claim]") && current(pendingDossier)) {
      dossier = pendingDossier; viewed = null; ++returnSerial; update();
    }
  }, true);
  var dialog = document.getElementById("modal-research-revision");
  if (dialog) dialog.addEventListener("close", function() { if (!dialog.open) pendingDossier = null; });
  document.addEventListener("lixity:research-record-view", function(event) { viewed = event.detail; update(); });
  document.addEventListener("lixity:workbench-change", update);
  new MutationObserver(update).observe(document.body, {subtree: true, childList: true, attributes: true,
    attributeFilter: ["data-project-token", "data-manuscript-project-token", "data-research-token", "data-manuscript-source-sha256", "data-dossier-reading", "open"]});
  button.addEventListener("click", function() {
    update();
    if (!dossier) {
      if (!passage) return;
      var previous = passage; passage = null; viewed = null; ++returnSerial; update(); previous.restore(); return;
    }
    var value = dossier, serial = ++returnSerial;
    dossier = pendingDossier = null; viewed = null; update();
    switchActiveView(value.state.view);
    if (value.tab) showResearchTab(value.tab);
    var state = workbench.state();
    if (state.analysisVisible !== value.state.analysisVisible) workbench.dispatch({type: "analysis", value: value.state.analysisVisible});
    if (state.contextTool !== value.state.contextTool) workbench.dispatch({type: "tool", value: value.state.contextTool});
    if (workbench.state().surface !== value.state.surface) workbench.dispatch({type: "surface", value: value.state.surface});
    if (workbench.state().focus !== value.state.focus) workbench.dispatch({type: "focus", value: value.state.focus});
    // View/tool changes can schedule layout work. Restore only after it has
    // run, and never act on a replaced context or a newer departure.
    requestAnimationFrame(function() { requestAnimationFrame(function() {
      if (serial !== returnSerial || !current(value)) return;
      value.control.focus({preventScroll: true});
      // The dock's available height depends on the document position. Settle
      // that geometry before restoring its internal scroll offset, otherwise
      // a temporarily taller scrollport clamps a valid saved offset.
      window.scrollTo({top: value.top, left: value.left, behavior: "instant"});
      if (window.LixityReader) window.LixityReader.fitContext();
      value.scrolls.forEach(function(scroll) { scroll.node.scrollTo({top: scroll.top, left: scroll.left, behavior: "instant"}); });
      window.scrollTo({top: value.top, left: value.left, behavior: "instant"});
      flashOnArrival(value.control);
    }); });
  });
  window.LixityReadingThread = {
    hasDossier: function() { return current(dossier) || current(pendingDossier); },
    hasPassage: function() { return Boolean(passage && passage.valid()); },
    rememberPassage: function(value) { passage = value; dossier = null; viewed = null; ++returnSerial; update(); }
  };
  update();
})();

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
  var retainedAnchor = null, requestedAnchor = null, dockOrigin = null, arrangementRevision = 0;
  var pendingDockAnchor = null;
  var narrowContext = window.matchMedia("(max-width: 900px)");
  var dockFitFrame = 0;
  function fitContextDock() {
    dockFitFrame = 0;
    if (!dock || !layout) return;
    if (narrowContext.matches) { dock.style.removeProperty("--context-available-height"); return; }
    if (dock.hidden || !dock.getClientRects().length) return;
    // Sticky positioning is bounded by the grid, not just by the viewport.
    // Fit its existing scrollport without moving the prose or extending it
    // over the footer when the document is short or near its lower boundary.
    var bounds = layout.getBoundingClientRect();
    var top = Math.max(parseFloat(getComputedStyle(dock).top), bounds.top);
    var gutter = parseFloat(getComputedStyle(document.documentElement).fontSize);
    var bottom = Math.min(innerHeight - gutter, bounds.bottom);
    var height = Math.max(0, Math.floor(bottom - top)) + "px";
    if (dock.style.getPropertyValue("--context-available-height") !== height) {
      var atEnd = dock.scrollTop > 0 && Math.ceil(dock.scrollTop + dock.clientHeight) >= dock.scrollHeight - 1;
      dock.style.setProperty("--context-available-height", height);
      // A smaller scrollport must not leave a previously reached document end
      // behind during a nested heading arrival. Other reading offsets stay put.
      if (atEnd) dock.scrollTop = dock.scrollHeight - dock.clientHeight;
    }
  }
  function scheduleDockFit() {
    if (!dockFitFrame) dockFitFrame = requestAnimationFrame(fitContextDock);
  }
  window.addEventListener("resize", scheduleDockFit);
  document.addEventListener("scroll", scheduleDockFit, {capture: true, passive: true});
  if (typeof ResizeObserver === "function") {
    var dockSizeObserver = new ResizeObserver(scheduleDockFit);
    [layout, document.getElementById("workbench-thread")].forEach(function(node) {
      if (node) dockSizeObserver.observe(node);
    });
  }

  var panels = Array.from(chapters.querySelectorAll(".ptext"));
  var menu = document.getElementById("manuscript-context-menu");
  var selectionTools = document.getElementById("manuscript-selection-tools");
  var inspector = document.getElementById("reader-inspector");
  var inspectorBody = document.getElementById("reader-inspector-body");
  var focus = document.getElementById("reader-focus");
  var settings = document.getElementById("reader-settings");
  var settingsPanels = [settings].filter(Boolean);
  var metric = document.getElementById("style-layer"), evidenceToggle = document.getElementById("analysis-evidence-enabled");
  var comparisonToggle = document.getElementById("analysis-comparison-enabled");
  var width = document.getElementById("reader-width");
  var spacing = document.getElementById("reader-spacing");
  var current = null, savedRange = null, evidencePoint = null, returnTarget = null, selecting = false;
  var preferences = {size: 18, width: "standard", spacing: "standard", metric: null, evidence: true, comparison: true};
  function read(key) { try { return localStorage.getItem(key); } catch (_) { return null; } }
  function save(key, value) { try { localStorage.setItem(key, value); } catch (_) { /* Display works without storage. */ } }
  try {
    var stored = JSON.parse(read("lixity.manuscript.reader") || "null");
    if (stored && typeof stored === "object") {
      if (Number.isFinite(stored.size)) preferences.size = Math.min(28, Math.max(16, stored.size));
      if (["narrow", "standard", "wide"].includes(stored.width)) preferences.width = stored.width;
      if (["compact", "standard", "relaxed"].includes(stored.spacing)) preferences.spacing = stored.spacing;
      if (typeof stored.metric === "string" && metric && Array.from(metric.options).some(function(option) {return option.value === stored.metric;})) preferences.metric = stored.metric;
      if (typeof stored.evidence === "boolean") preferences.evidence = stored.evidence;
      if (typeof stored.comparison === "boolean") preferences.comparison = stored.comparison;
    }
  } catch (_) { /* A malformed preference never changes manuscript data. */ }
  if (metric && preferences.metric !== null) metric.value = preferences.metric;
  if (evidenceToggle) evidenceToggle.checked = preferences.evidence;
  if (comparisonToggle) comparisonToggle.checked = preferences.comparison;
  function rememberAnalysis() {
    if (metric) preferences.metric = metric.value;
    if (evidenceToggle) preferences.evidence = evidenceToggle.checked;
    if (comparisonToggle) preferences.comparison = comparisonToggle.checked;
    save("lixity.manuscript.reader", JSON.stringify(preferences));
  }
  function defaultMetric(force) {
    if (!metric || metric.value || (!force && preferences.metric !== null)) return;
    metric.value = "asl";
    metric.dispatchEvent(new Event("change", {bubbles:true}));
  }
  if (metric) metric.addEventListener("change", rememberAnalysis);
  if (evidenceToggle) evidenceToggle.addEventListener("change", rememberAnalysis);
  if (comparisonToggle) comparisonToggle.addEventListener("change", rememberAnalysis);
  var clearMetric = document.getElementById("layer-clear");
  if (clearMetric) clearMetric.addEventListener("click", function() {
    rememberAnalysis();
    if (metric) metric.focus({preventScroll:true});
  });
  var resetParagraphs = document.getElementById("paragraph-filter-reset");
  if (resetParagraphs) resetParagraphs.addEventListener("click", rememberAnalysis);
  function capture() {
    if (workbench.state().view !== "analysis" || workbench.state().surface !== "document") return null;
    if (pendingDockAnchor && pendingDockAnchor.revision === arrangementRevision) return pendingDockAnchor.anchor;
    var boundary = controls.getBoundingClientRect().bottom;
    var panel = Array.from(chapters.querySelectorAll(".ptext, .reader-structural")).find(function(candidate) {
      var rect = candidate.getBoundingClientRect();
      return rect.height > 0 && rect.bottom > boundary && rect.top < innerHeight;
    });
    if (!panel) return null;
    var anchor = {panel: panel, top: panel.getBoundingClientRect().top};
    var prose = panel.querySelector(".ptext-inner > p");
    if (prose) anchor.proseOffset = prose.getBoundingClientRect().top - anchor.top;
    return anchor;
  }
  function restore(anchor, arrival) {
    if (!anchor) return;
    var revision = arrangementRevision;
    requestAnimationFrame(function() {
      if (revision !== arrangementRevision) return;
      if (anchor.panel.isConnected) {
        var top = anchor.panel.getBoundingClientRect().top;
        var prose = anchor.panel.querySelector(".ptext-inner > p");
        // Inline analysis controls may disappear while the prose stays in view.
        if (prose && Number.isFinite(anchor.proseOffset)) top = prose.getBoundingClientRect().top - anchor.proseOffset;
        window.scrollBy(0, top - anchor.top);
        if (arrival && window.LixityMotion) window.LixityMotion.passage(anchor.panel);
      }
      if (pendingDockAnchor && pendingDockAnchor.revision === revision) pendingDockAnchor = null;
    });
  }
  function retain(action) {
    var anchor = capture(), previous = workbench.state(), outer = retainedAnchor;
    retainedAnchor = anchor;
    try { action(); } finally { retainedAnchor = outer; }
    var next = workbench.state();
    // The tool subscriber owns one layout restore, including an immediate
    // reversal before its opening frame. Do not queue a second transient anchor.
    if (previous.contextTool !== next.contextTool && next.surface === "document") return;
    restore(anchor);
  }
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
    button.dataset.help = uiLabel("reading_help_actions");
    button.setAttribute("aria-keyshortcuts", "Shift+F10");
    button.setAttribute("aria-haspopup", "menu"); button.setAttribute("aria-controls", menu.id);
    button.setAttribute("aria-expanded", "false");
    inner.appendChild(button);
    panel.tabIndex = -1;
  }
  function closeMenu(restoreFocus) {
    menu.hidden = true;
    evidencePoint = null;
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
  function requestTool(value, panel) {
    // Passage capture precedes the responsive return thread entering layout.
    // Its original position remains authoritative when opening research.
    requestedAnchor = value === "research" && validOrigin() && origin.anchor.panel === panel ?
      origin.anchor : {panel: panel, top: panel.getBoundingClientRect().top};
    if (workbench.state().contextTool === value) {
      dockOrigin = requestedAnchor; requestedAnchor = null;
      if (narrowContext.matches) dock.scrollIntoView({block: "start", behavior: "instant"});
      if (window.LixityMotion) window.LixityMotion.reveal(dock);
    } else retain(function() { workbench.dispatch({type: "tool", value: value}); });
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
  function passageContext(panel) {
    var chapter = panel.closest(".chapter"), heading = chapter && chapter.querySelector("h2, h3");
    return (heading ? heading.textContent.trim() + " · " : "") +
      uiFormat("reading_passage_lines", {start: panel.dataset.start, end: panel.dataset.end});
  }
  function showValues(panel, point) {
    if (!panel) return;
    renderParagraph(panel);
    var values = panel.querySelector(".paragraph-values");
    if (!values) return;
    var copy = values.cloneNode(true); copy.open = true;
    if (inspectorTarget) inspectorTarget.classList.remove("reader-inspector-target");
    var context = document.createElement("div"); context.className = "reader-passage-context";
    var location = document.createElement("p"); location.className = "ctl-note";
    location.textContent = passageContext(panel); context.appendChild(location);
    var tools = document.createElement("div"); tools.className = "reader-passage-tools";
    tools.setAttribute("role", "group"); tools.setAttribute("aria-label", uiLabel("reading_actions"));
    if (window.LixityAnalysisEvidence && window.LixityAnalysisEvidence.available()) {
      var explain = actionButton("evidence", "evidence_inspect", false);
      explain.dataset.readerEvidenceParagraph = panel.id;
      var source = paragraphContent[panel.id], project = document.body.dataset.manuscriptProjectToken;
      var hash = panel.dataset.paragraphSha256;
      explain.addEventListener("click", function() {
        if (panel.isConnected && paragraphContent[panel.id] === source &&
            document.body.dataset.manuscriptProjectToken === project && panel.dataset.paragraphSha256 === hash) {
          window.LixityAnalysisEvidence.inspect(panel, explain, point);
        }
      });
      tools.appendChild(explain);
    }
    if (window.LixityManuscriptLinks && typeof window.LixityManuscriptLinks.review === "function") {
      var related = document.createElement("button"); related.type = "button"; related.className = "ctl";
      related.dataset.manuscriptLinksParagraph = panel.id;
      related.dataset.readerAction = "research";
      related.textContent = uiLabel("passage_research"); tools.appendChild(related);
    }
    context.appendChild(tools);
    inspectorBody.replaceChildren(context, copy); inspectorTarget = panel;
    panel.classList.add("reader-inspector-target");
  }
  if (dock) dock.appendChild(inspector);
  workbench.subscribe(function(state, previous) {
    var sameDocument = state.view === "analysis" &&
      previous.view === "analysis" && state.surface === "document" && previous.surface === "document";
    var toolChanged = state.contextTool !== previous.contextTool && sameDocument;
    // Until the opening restore commits, current rectangles describe temporary
    // layout. A reversal must retain the prior reading position instead.
    var pending = sameDocument && pendingDockAnchor && pendingDockAnchor.revision === arrangementRevision;
    var anchor = requestedAnchor || (pending && pendingDockAnchor.anchor) || retainedAnchor || capture();
    var revision = ++arrangementRevision;
    var open = state.contextTool !== "none" && state.surface === "document";
    pendingDockAnchor = sameDocument && open && !narrowContext.matches && (toolChanged || pending) ? {anchor: anchor, revision: revision} : null;
    if (toolChanged && open && (previous.contextTool === "none" || requestedAnchor)) {
      dockOrigin = requestedAnchor || (document.activeElement.closest("#view-pane-analysis") ? anchor : null);
      // A toolbar request retains the passage position, but its own focus origin.
      if (dockOrigin && !requestedAnchor) dockOrigin.trigger = document.activeElement;
    }
    requestedAnchor = null;
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
      closeMenu(false); selectionTools.hidden = true; settingsPanels.forEach(function(panel) {panel.open = false;});
    }
    if (toolChanged && narrowContext.matches) {
      var destination = open ? null : dockOrigin;
      var returnDockFocus = dock.contains(document.activeElement);
      requestAnimationFrame(function() {
        if (revision !== arrangementRevision) return;
        if (open) dock.scrollIntoView({block: "start", behavior: "instant"});
        else if (destination && destination.panel.isConnected) {
          window.scrollBy(0, destination.panel.getBoundingClientRect().top - destination.top);
          if (returnDockFocus) {
            var trigger = destination.trigger;
            if (!trigger || !trigger.isConnected || !trigger.getClientRects().length || trigger.disabled) {
              trigger = destination.panel.querySelector(".reader-paragraph-actions") || destination.panel;
            }
            trigger.focus({preventScroll: true});
          }
          if (window.LixityMotion) window.LixityMotion.passage(destination.panel);
        }
      });
      if (!open) dockOrigin = null;
    } else if (state.surface === previous.surface && state.view === previous.view &&
        (state.contextTool !== previous.contextTool || state.analysisVisible !== previous.analysisVisible || state.focus !== previous.focus)) restore(anchor, toolChanged && !open);
    if (window.LixityMotion) {
      if (toolChanged && open) window.LixityMotion.reveal(dock);
      if (state.analysisVisible && !previous.analysisVisible && state.surface === "document") window.LixityMotion.analysis(chapters);
      if (state.surface !== previous.surface) window.LixityMotion.view(document.getElementById("view-pane-analysis"));
    }
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
    if (!compact) {
      fragment.appendChild(actionButton("values", "reading_explore_passage", true));
    }
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
  function openMenu(panel, x, y, trigger, point) {
    closeMenu(false); selectionTools.hidden = true;
    current = panel; savedRange = rangeFor(panel); evidencePoint = point || null;
    returnTarget = trigger || panel.querySelector(".reader-paragraph-actions") || panel;
    menu.replaceChildren(actions(panel, false));
    place(menu, x, y); returnTarget.setAttribute("aria-expanded", "true");
    var first = menu.querySelector("button"); if (first) { first.tabIndex = 0; first.focus({preventScroll: true}); }
  }
  function run(action) {
    if (!current || !current.isConnected) return;
    var panel = current, range = rangeFor(current) || savedRange, point = evidencePoint;
    closeMenu(false); selectionTools.hidden = true;
    renderParagraph(panel);
    if ((action === "values" || action === "companion") && document.body.classList.contains("reader-focus")) setFocus(false);
    if (action === "values") {
      showValues(panel, point);
      requestTool("analysis", panel);
      document.getElementById("reader-inspector-close").focus({preventScroll: true});
    } else if (action === "link") {
      if (!range) return;
      var selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
      var link = panel.querySelector("[data-manuscript-link-selection]"); if (link) link.click();
    } else if (action === "companion") {
      requestTool("dossier", panel);
      var close = document.getElementById("workspace-reader-close");
      if (close) close.focus({preventScroll: true});
    } else {
      var marker = panel.querySelector('[data-marker-kind="' + action + '"]');
      if (marker) marker.click();
    }
  }
  controls.hidden = false; appearance();
  function placeSettings() {
    settingsPanels.forEach(function(panel) {
      if (!panel.open) return;
      var summary = panel.querySelector("summary").getBoundingClientRect();
      var body = panel.querySelector(".reader-settings-body"), gutter = 8, gap = 6;
      var limit = Math.max(0, innerHeight - gutter * 2);
      // Measure afresh after a resize; a previous placement may have capped height.
      body.style.maxHeight = limit + "px";
      // Enlarged chrome can move the anchor offscreen without adding usable space.
      var below = Math.max(0, Math.min(limit, innerHeight - summary.bottom - gap - gutter));
      var above = Math.max(0, Math.min(limit, summary.top - gap - gutter));
      var downward = body.getBoundingClientRect().height <= below || below >= above;
      body.style.maxHeight = (downward ? below : above) + "px";
      var height = body.getBoundingClientRect().height;
      place(body, summary.left, downward ? summary.bottom + gap : summary.top - gap - height);
    });
  }
  settingsPanels.forEach(function(panel) {
    new MutationObserver(placeSettings).observe(panel, {attributes: true, attributeFilter: ["open"]});
  });
  mode.addEventListener("change", function() { setMode(mode.value); });
  analysisToggle.addEventListener("click", function() {
    var previous = workbench.state();
    retain(function() {
      if (!previous.analysisVisible) defaultMetric(false);
      workbench.dispatch({type: "analysis", value: !previous.analysisVisible});
    });
    if (previous.surface === "overview") {
      rememberPassageLocation(overviewAnchor && overviewAnchor.panel); restore(overviewAnchor, true);
    }
  });
  document.querySelectorAll("[data-context-tool]").forEach(function(button) {
    button.addEventListener("click", function() { retain(function() {
      workbench.dispatch({type: "tool", value: button.dataset.contextTool});
    }); });
  });
  document.getElementById("workbench-overview-open").addEventListener("click", function() {
    overviewAnchor = capture(); workbench.dispatch({type: "surface", value: "overview"});
    (document.getElementById("workspace-reader") || controls).scrollIntoView({block: "start", behavior: "instant"});
    document.getElementById("workbench-overview-back").focus({preventScroll: true});
  });
  document.getElementById("workbench-overview-back").addEventListener("click", function() {
    rememberPassageLocation(overviewAnchor && overviewAnchor.panel);
    workbench.dispatch({type: "surface", value: "document"}); restore(overviewAnchor, true);
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
      scrollAndFlash(chapter);
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
    var prose = event.target.closest(".ptext-inner > p"), point = null;
    if (prose) {
      var caret = document.caretPositionFromPoint ? document.caretPositionFromPoint(event.clientX, event.clientY) : null;
      var nativeRange = !caret && document.caretRangeFromPoint ? document.caretRangeFromPoint(event.clientX, event.clientY) : null;
      var node = caret ? caret.offsetNode : nativeRange && nativeRange.startContainer;
      var offset = caret ? caret.offset : nativeRange && nativeRange.startOffset;
      var content = paragraphContent[panel.id], evidence = content && content[3];
      if (node && prose.contains(node) && evidence && prose.textContent === content[0]) {
        var prefix = document.createRange(); prefix.selectNodeContents(prose); prefix.setEnd(node, offset);
        point = {offset:prefix.toString().length, hash:evidence.paragraph_sha256};
      }
    }
    event.preventDefault(); openMenu(panel, event.clientX, event.clientY, null, point);
  });
  [menu, selectionTools].forEach(function(host) {
    host.addEventListener("pointerdown", function(event) { event.preventDefault(); });
    host.addEventListener("click", function(event) { var action = event.target.closest("[data-reader-action]"); if (action) run(action.dataset.readerAction); });
  });
  document.addEventListener("pointerdown", function(event) {
    selecting = chapters.contains(event.target);
    settingsPanels.forEach(function(panel) {if (panel.open && !panel.contains(event.target)) panel.open = false;});
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
    if (event.key === "Escape" && !event.defaultPrevented && !event.isComposing && !event.target.closest("dialog, [role=dialog], select")) {
      var opened = settingsPanels.find(function(panel) {return panel.open;});
      if (opened) {event.preventDefault(); event.stopImmediatePropagation(); opened.open = false; opened.querySelector("summary").focus({preventScroll:true}); return;}
    }
    if (event.key !== "Escape" || event.defaultPrevented || event.isComposing || event.target.closest("dialog, [role=dialog], select, input, textarea")) return;
    if (!selectionTools.hidden) { selectionTools.hidden = true; event.preventDefault(); event.stopImmediatePropagation(); }
    else if (!inspector.hidden && !document.body.classList.contains("reader-focus")) { event.preventDefault(); event.stopImmediatePropagation(); retain(function() { closeInspector(true); }); }
    else if (document.body.classList.contains("reader-focus") && !event.target.closest("details[open]")) { event.preventDefault(); event.stopImmediatePropagation(); setFocus(false); focus.focus({preventScroll: true}); }
    else if (document.body.classList.contains("manuscript-reading") && event.target.closest("#chapters")) {
      // Escape never removes continuous prose. Existing note/disclosure handlers run.
      if (!event.target.closest("details[open]")) { event.preventDefault(); event.stopImmediatePropagation(); }
    }
  }, true);
  document.addEventListener("lixity:viewchange", function() {
    closeMenu(false); selectionTools.hidden = true;
    settingsPanels.forEach(function(panel) {panel.open = false;});
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
  window.addEventListener("resize", function() { closeMenu(false); selectionTools.hidden = true; placeSettings(); });
  document.addEventListener("scroll", function(event) {
    settingsPanels.forEach(function(panel) {
      if (!panel.open || panel.contains(event.target)) return;
      var summary = panel.querySelector("summary"), box = summary.getBoundingClientRect();
      if (!summary.getClientRects().length || box.bottom <= 0 || box.top >= innerHeight) panel.open = false;
      else placeSettings();
    });
  }, {passive: true, capture: true});
  var readingThread = window.LixityReadingThread;
  function validOrigin() {
    return origin && origin.context === sourceContext() && origin.anchor.panel.isConnected &&
      origin.hash === origin.anchor.panel.dataset.paragraphSha256;
  }
  function sourceContext() {
    var workspace = document.getElementById("manuscript-pdf-form") || document.getElementById("workspace-reader");
    return [workspace ? workspace.dataset.projectToken : document.body.dataset.manuscriptProjectToken,
      document.body.dataset.manuscriptSourceSha256, window.LixityWorkspaceReader && window.LixityWorkspaceReader.contextToken(),
      typeof researchContextToken === "function" ? researchContextToken() : ""].join(":");
  }
  function returnToPassage() {
    switchActiveView("analysis"); workbench.dispatch({type: "surface", value: "document"});
    if (workbench.state().contextTool === "research") {
      workbench.dispatch({type: "tool", value: origin.state.contextTool === "research" ? "none" : origin.state.contextTool});
      workbench.dispatch({type: "analysis", value: origin.state.analysisVisible});
    }
    rememberPassageLocation(origin.anchor.panel);
    revealChapter(origin.anchor.panel); restore(origin.anchor, true);
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
    origin = null;
  }
  document.addEventListener("click", function(event) {
    var relation = event.target.closest("[data-research-history], [data-workspace-dossier], [data-manuscript-link-jump], [data-manuscript-links-claim], [data-manuscript-links-dossier], [data-manuscript-links-paragraph], .manuscript-claim-hit");
    if (!relation || workbench.state().view !== "analysis" || workbench.state().surface !== "document" || readingThread.hasDossier()) return;
    var panel = event.target.closest(".ptext") || document.getElementById(relation.dataset.manuscriptLinksParagraph || "");
    // Following records in a dialog or companion belongs to the same passage journey.
    if ((!panel || relation.closest("[data-passage-research]")) && readingThread.hasPassage()) return;
    rememberReadingPassage(panel);
  }, true);
  function rememberReadingPassage(panel, selectedRange) {
    var anchor = panel ? {panel: panel, top: panel.getBoundingClientRect().top} : capture();
    if (!anchor) return;
    var range = selectedRange || rangeFor(anchor.panel), offsets = null;
    if (range) {
      if (selectedRange && getSelection().isCollapsed) { getSelection().removeAllRanges(); getSelection().addRange(selectedRange); }
      var paragraph = anchor.panel.querySelector(".ptext-inner > p"), selection = getSelection();
      var prefix = document.createRange(); prefix.selectNodeContents(paragraph);
      prefix.setEnd(selection.anchorNode, selection.anchorOffset); var from = prefix.toString().length;
      prefix.setEnd(selection.focusNode, selection.focusOffset);
      offsets = {anchor: from, focus: prefix.toString().length};
    }
    origin = {anchor: anchor, offsets: offsets, state: workbench.state(), hash: anchor.panel.dataset.paragraphSha256, context: sourceContext()};
    readingThread.rememberPassage({description: passageContext(anchor.panel), valid: validOrigin, restore: returnToPassage});
  }
  window.LixityReader = {fitContext: fitContextDock, requestTool: requestTool, capture: capture, restore: restore, retain: retain,
    enableEvidence: function() { retain(function() {defaultMetric(true); workbench.dispatch({type:"analysis", value:true});}); },
    inspect: function() { setMode("inspect", true); }};
  document.body.classList.add("manuscript-reading");
  panels.forEach(enhanceText);
  document.dispatchEvent(new Event("lixity:reader-ready"));
  workbench.dispatch({type: "analysis", value: false});
  var hash = document.getElementById(window.location.hash.slice(1));
  if (hash && hash.closest("#manuscript-analysis-panels")) setMode("inspect", true);
  if (hash && hash.closest("#chapters, #manuscript-analysis-panels")) requestAnimationFrame(function() { scrollAndFlash(hash); });
})();
