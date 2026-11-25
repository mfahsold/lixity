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
  var thread = document.createElement("aside"), originText = document.createElement("p");
  thread.id = "workbench-thread"; thread.className = "workbench-thread";
  thread.setAttribute("aria-label", uiLabel("reading_thread"));
  originText.className = "ctl-note";
  thread.append(originText, button); shell.appendChild(thread);
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
  sidebar.addEventListener("change", function() { update(); });
  if (typeof ResizeObserver === "function") new ResizeObserver(threadHeight).observe(thread);
  placeThread();
  var passage = null, dossier = null, pendingDossier = null, returnSerial = 0;
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
    // A passage return is redundant while that passage is already in view.
    // Only the desktop sidebar thread hides: the mobile thread is in-flow and
    // toggling it while reading would shift the prose.
    var atOrigin = !dossier && passage && sidebar.matches && typeof passage.atOrigin === "function" && passage.atOrigin();
    thread.hidden = button.hidden = (!dossier && !passage) || Boolean(atOrigin);
    text(button, uiLabel(dossier ? "reading_back_dossier" : "reading_back"));
    text(originText, dossier ? uiFormat("reading_dossier_origin", {title: dossier.reading.title, revision: dossier.reading.revision}) : passage ? passage.description : "");
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
      dossier = value; ++returnSerial; update();
    } else if (action.closest("#modal-research-revision") &&
        action.matches("[data-manuscript-links-claim]") && current(pendingDossier)) {
      dossier = pendingDossier; ++returnSerial; update();
    }
  }, true);
  var dialog = document.getElementById("modal-research-revision");
  if (dialog) dialog.addEventListener("close", function() { if (!dialog.open) pendingDossier = null; });
  document.addEventListener("lixity:workbench-change", update);
  // The desktop thread lives in the sidebar, so revealing it after the reader
  // scrolls away from the passage never shifts the prose.
  var visibilityFrame = null;
  function refreshPassageVisibility() {
    if (!passage || dossier || !sidebar.matches || visibilityFrame !== null) return;
    visibilityFrame = requestAnimationFrame(function() { visibilityFrame = null; update(); });
  }
  window.addEventListener("scrollend", refreshPassageVisibility, {passive: true});
  window.addEventListener("resize", refreshPassageVisibility, {passive: true});
  new MutationObserver(function(records) {
    if (!dossier && !pendingDossier && !passage) {
      var hasAttr = false;
      for (var i = 0; i < records.length; i++) {
        if (records[i].type === "attributes") { hasAttr = true; break; }
      }
      if (!hasAttr) return;
    }
    update();
  }).observe(document.body, {subtree: true, childList: true, attributes: true,
    attributeFilter: ["data-project-token", "data-manuscript-project-token", "data-research-token", "data-manuscript-source-sha256", "data-dossier-reading", "open"]});
  button.addEventListener("click", function() {
    update();
    if (!dossier) {
      if (!passage) return;
      var previous = passage; passage = null; ++returnSerial; update(); previous.restore(); return;
    }
    var value = dossier, serial = ++returnSerial;
    dossier = pendingDossier = null; update();
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
    rememberPassage: function(value) { passage = value; dossier = null; ++returnSerial; update(); }
  };
  update();
})();

// Reading and inspection share source text, anchors and existing action handlers.
(function () {
  "use strict";
  var controls = document.getElementById("manuscript-reader-controls");
  var chapters = document.getElementById("chapters");
  if (!controls || !chapters) return;
  var workbench = window.LixityWorkbench;
  var analysisToggle = document.getElementById("manuscript-analysis-toggle");
  var dock = document.getElementById("workspace-context-panel");
  var layout = document.getElementById("workspace-reader-layout");
  var overviewAnchor = null, inspectorTarget = null, contextPassage = null, inspectorTrigger = null, origin = null;
  var retainedAnchor = null, requestedAnchor = null, dockOrigin = null, arrangementRevision = 0;
  var pendingDockAnchor = null, pendingDockFocusRevision = null, clampedAnchor = null, scrollIntentRevision = 0;
  var pendingComparisonRestore = null, comparisonRestoreRevision = 0, passageNavigationRevision = 0;
  var narrowContext = window.matchMedia("(max-width: 900px)");
  var dockFitFrame = 0, dockViewport = null;
  function updateContextDock() {
    dockFitFrame = 0;
    if (!dock || !layout) return;
    if (narrowContext.matches) { dock.style.removeProperty("--context-available-height"); return; }
    if (dock.hidden) return;
    // Dock placement depends on viewport size and reading chrome. Neither
    // computed style changes with ordinary scrolling through the manuscript.
    if (!dockViewport) {
      if (!dock.getClientRects().length) return;
      dockViewport = {
        top: parseFloat(getComputedStyle(dock).top),
        bottom: innerHeight - parseFloat(getComputedStyle(document.documentElement).fontSize)
      };
    }
    // Sticky positioning is bounded by the grid, not just by the viewport.
    // Fit its existing scrollport without moving the prose or extending it
    // over the footer when the document is short or near its lower boundary.
    var bounds = layout.getBoundingClientRect();
    var top = Math.max(dockViewport.top, bounds.top);
    var bottom = Math.min(dockViewport.bottom, bounds.bottom);
    var height = Math.max(0, Math.floor(bottom - top)) + "px";
    if (dock.style.getPropertyValue("--context-available-height") !== height) {
      var atEnd = dock.scrollTop > 0 && Math.ceil(dock.scrollTop + dock.clientHeight) >= dock.scrollHeight - 1;
      dock.style.setProperty("--context-available-height", height);
      // A smaller scrollport must not leave a previously reached document end
      // behind. Writing scrollTop cancels a pending smooth jump up the dock.
      if (atEnd) {
        var destination = passageArrival && !passageArrival.timer && passageArrival.target;
        var jumpingUp = destination && dock.contains(destination) &&
          destination.getBoundingClientRect().top < dock.getBoundingClientRect().top + dock.clientTop;
        if (!jumpingUp) dock.scrollTop = dock.scrollHeight - dock.clientHeight;
      }
    }
  }
  function fitContextDock() {
    if (dockFitFrame) cancelAnimationFrame(dockFitFrame);
    dockViewport = null;
    updateContextDock();
  }
  function scheduleDockFit() {
    if (!dockFitFrame) dockFitFrame = requestAnimationFrame(updateContextDock);
  }
  function invalidateDockViewport() {
    dockViewport = null;
    scheduleDockFit();
  }
  window.addEventListener("resize", invalidateDockViewport);
  // Scrolling within the dock or another scrollport leaves its viewport fit intact.
  window.addEventListener("scroll", function() {
    if (dock && !dock.hidden && !narrowContext.matches) scheduleDockFit();
  }, {passive: true});
  if (typeof ResizeObserver === "function") {
    var dockSizeObserver = new ResizeObserver(function(entries) {
      if (entries.some(function(entry) { return entry.target !== layout; })) dockViewport = null;
      scheduleDockFit();
    });
    var thread = document.getElementById("workbench-thread");
    if (layout) dockSizeObserver.observe(layout);
    if (thread) dockSizeObserver.observe(thread);
  }

  var panels = Array.from(chapters.querySelectorAll(".ptext"));
  var readingBlocks = Array.from(chapters.querySelectorAll(".ptext, .reader-structural"));
  var menu = document.getElementById("manuscript-context-menu");
  var selectionTools = document.getElementById("manuscript-selection-tools");
  var inspector = document.getElementById("reader-inspector");
  var inspectorBody = document.getElementById("reader-inspector-body");
  var focus = document.getElementById("reader-focus");
  var focusShortcuts = focus.getAttribute("aria-keyshortcuts") || "";
  var directSpeechBtn = document.getElementById("reader-direct-speech");
  var directSpeechActive = false;
  var directSpeechObserver = null;
  var directSpeechIntersection = null;
  var directSpeechVisible = new Set();
  var directSpeechFrame = 0;
  var directSpeechGeneration = 0;
  var settings = document.getElementById("reader-settings");
  var settingsPanels = Array.from(controls.querySelectorAll(".reader-settings"));
  var analysisGuide = document.getElementById("reader-analysis-guide");
  var analysisOptions = document.getElementById("reader-analysis-options");
  var metric = document.getElementById("style-layer"), evidenceToggle = document.getElementById("analysis-evidence-enabled");
  var comparisonToggle = document.getElementById("analysis-comparison-enabled");
  var current = null, savedRange = null, evidencePoint = null, returnTarget = null, selecting = false;
  var sizeOutput = document.getElementById("reader-size-value");
  var smaller = document.getElementById("reader-text-smaller");
  var larger = document.getElementById("reader-text-larger");
  var minSize = Number(sizeOutput.dataset.min), maxSize = Number(sizeOutput.dataset.max), sizeStep = Number(sizeOutput.dataset.step);
  var preferences = {size: Number(sizeOutput.defaultValue), metric: null, evidence: false, evidenceByMetric: Object.create(null), comparison: true};
  var appearanceChoices = Array.from(settings.querySelectorAll("select[data-reader-setting]"), function(select) {
    var key = select.dataset.readerSetting;
    var options = new Map(Array.from(select.options, function(option) { return [option.value, option.dataset.cssValue]; }));
    var buttons = select.parentElement.querySelectorAll("[data-reader-choice]");
    preferences[key] = select.value;
    return {key: key, select: select, options: options, buttons: buttons};
  });
  function boundedSize(size) { return Math.min(maxSize, Math.max(minSize, size)); }
  var preferenceKey = "lixity.manuscript.reader";
  var publishReaderPreferences = null, applyingNativePreferences = false, choosingDefaultMetric = false;
  var knownMetrics = new Set(metric ? Array.from(metric.options, function(option) { return option.value; }) : []);
  function useReaderPreferences(stored) {
    if (!stored || typeof stored !== "object") return;
    if (Number.isFinite(stored.size)) preferences.size = boundedSize(stored.size);
    appearanceChoices.forEach(function(choice) {
      if (choice.options.has(stored[choice.key])) preferences[choice.key] = stored[choice.key];
    });
    if (knownMetrics.has(stored.metric)) preferences.metric = stored.metric;
    if (typeof stored.evidence === "boolean") preferences.evidence = stored.evidence;
    if (stored.evidenceByMetric && typeof stored.evidenceByMetric === "object" && !Array.isArray(stored.evidenceByMetric)) {
      Object.keys(stored.evidenceByMetric).forEach(function(key) {
        if (key && knownMetrics.has(key) && typeof stored.evidenceByMetric[key] === "boolean") {
          preferences.evidenceByMetric[key] = stored.evidenceByMetric[key];
        }
      });
    } else if (preferences.metric && typeof stored.evidence === "boolean") {
      // A global legacy choice belongs only to the last selected metric.
      preferences.evidenceByMetric[preferences.metric] = stored.evidence;
    }
    if (typeof stored.comparison === "boolean") preferences.comparison = stored.comparison;
  }
  function saveReaderPreferences(changes) {
    try { localStorage.setItem(preferenceKey, JSON.stringify(preferences)); }
    catch (_) { /* Display works without browser storage. */ }
    if (changes && publishReaderPreferences) publishReaderPreferences(changes);
  }
  try { useReaderPreferences(JSON.parse(localStorage.getItem(preferenceKey) || "null")); }
  catch (_) { /* A malformed preference never changes manuscript data. */ }
  if (metric && preferences.metric !== null) metric.value = preferences.metric;
  function restoreEvidencePreference() {
    if (!metric || !evidenceToggle) return;
    var selected = metric.selectedOptions[0];
    var saved = preferences.evidenceByMetric[metric.value];
    evidenceToggle.checked = typeof saved === "boolean" ? saved :
      Boolean(selected && selected.dataset.inlineEvidence === "1" && selected.dataset.available !== "0");
  }
  restoreEvidencePreference();
  if (comparisonToggle) comparisonToggle.checked = preferences.comparison;
  function rememberAnalysis(changes) {
    if (metric) preferences.metric = metric.value;
    if (metric && metric.value && evidenceToggle) preferences.evidence = evidenceToggle.checked;
    if (comparisonToggle) preferences.comparison = comparisonToggle.checked;
    saveReaderPreferences(changes);
  }
  function connectDesktopPreferences(initial, publish) {
    // A late IPC reply can restore untouched fields, but never overwrite an
    // explicit change made while the desktop preference read was in flight.
    var touched = new Set(), touchedEvidence = new Set();
    publishReaderPreferences = function(changes) {
      Object.keys(changes).forEach(function(key) { touched.add(key); });
      Object.keys(changes.evidenceByMetric || {}).forEach(function(key) { touchedEvidence.add(key); });
      publish(changes);
    };
    initial.then(function(stored) {
      publishReaderPreferences = publish;
      if (!stored || typeof stored !== "object") return;
      var restored = {};
      ["size", "width", "spacing", "metric", "comparison"].forEach(function(key) {
        if (!touched.has(key) && Object.prototype.hasOwnProperty.call(stored, key)) restored[key] = stored[key];
      });
      if (stored.evidenceByMetric && typeof stored.evidenceByMetric === "object") {
        restored.evidenceByMetric = Object.fromEntries(Object.entries(stored.evidenceByMetric).filter(function(pair) {
          return !touchedEvidence.has(pair[0]);
        }));
      }
      retain(function() {
        var before = [metric?.value, evidenceToggle?.checked, comparisonToggle?.checked];
        useReaderPreferences(restored);
        if (metric && preferences.metric !== null) metric.value = preferences.metric;
        restoreEvidencePreference();
        if (comparisonToggle) comparisonToggle.checked = preferences.comparison;
        appearance();
        if (metric && (metric.value !== before[0] || evidenceToggle?.checked !== before[1] ||
            comparisonToggle?.checked !== before[2])) {
          applyingNativePreferences = true;
          try { metric.dispatchEvent(new Event("change", {bubbles: true})); }
          finally { applyingNativePreferences = false; }
        }
      });
    }).catch(function() { publishReaderPreferences = publish; });
  }
  function defaultMetric(force) {
    if (!metric || metric.value || (!force && preferences.metric !== null)) return;
    choosingDefaultMetric = true;
    try { window.LixityComponents.changeSelectOption(metric, "asl"); }
    finally { choosingDefaultMetric = false; }
  }
  function setAnalysisVisible(visible) {
    retain(function() {
      if (visible) defaultMetric(false);
      workbench.dispatch({type:"analysis", value:visible});
    });
  }
  function selectMetricPreference() {
    if (applyingNativePreferences) return;
    restoreEvidencePreference();
    rememberAnalysis(choosingDefaultMetric ? undefined : {metric: metric.value});
  }
  if (metric) {
    // Capture the passage before the dashboard changes the visible evidence and comparison badges.
    metric.addEventListener("change", queueAnalysisRestore, true);
    metric.addEventListener("change", selectMetricPreference, true);
  }
  if (evidenceToggle) evidenceToggle.addEventListener("change", function() {
    if (!metric || !metric.value) return;
    preferences.evidenceByMetric[metric.value] = evidenceToggle.checked;
    rememberAnalysis({evidenceByMetric: {[metric.value]: evidenceToggle.checked}});
  });
  if (comparisonToggle) {
    // Capture before the dashboard changes comparison badges and paragraph height.
    comparisonToggle.addEventListener("change", queueAnalysisRestore, true);
    comparisonToggle.addEventListener("change", function() {
      rememberAnalysis({comparison: comparisonToggle.checked});
    });
  }
  function capture() {
    if (workbench.state().view !== "analysis" || workbench.state().surface !== "document") return null;
    if (pendingDockAnchor && pendingDockAnchor.revision === arrangementRevision) return pendingDockAnchor.anchor;
    var boundary = readingViewportTop();
    var threshold = boundary + 10;
    var panel = null;
    var unfiltered = !document.body.classList.contains("only-flags") &&
      !document.body.classList.contains("text-search-active") &&
      !chapters.querySelector(".chapter.collapsed");
    if (unfiltered && readingBlocks.length > 16) {
      var low = 0, high = readingBlocks.length - 1, candidateIdx = -1;
      while (low <= high) {
        var mid = (low + high) >> 1;
        var midRect = readingBlocks[mid].getBoundingClientRect();
        if (midRect.height === 0) { candidateIdx = -1; break; }
        if (midRect.bottom > threshold) {
          candidateIdx = mid;
          high = mid - 1;
        } else {
          low = mid + 1;
        }
      }
      if (candidateIdx >= 0) {
        var candRect = readingBlocks[candidateIdx].getBoundingClientRect();
        if (candRect.height > 0 && candRect.bottom > threshold && candRect.top < innerHeight) {
          panel = readingBlocks[candidateIdx];
        }
      }
    }
    if (!panel) {
      panel = readingBlocks.find(function(candidate) {
        var rect = candidate.getBoundingClientRect();
        return rect.height > 0 && rect.bottom > threshold && rect.top < innerHeight;
      });
    }
    if (!panel) return null;
    var anchor = {panel: panel, top: panel.getBoundingClientRect().top};
    var prose = panel.querySelector(".ptext-inner > p");
    if (prose) anchor.proseOffset = prose.getBoundingClientRect().top - anchor.top;
    return anchor;
  }
  // Geometry capture stays literal for navigation. A layout-preserving action
  // may instead retry a position which the previous layout could not reach.
  function captureForRestore() {
    if (pendingComparisonPassage()) return pendingComparisonRestore.anchor;
    if (clampedAnchor && clampedAnchor.anchor.panel.isConnected && clampedAnchor.context === sourceContext() &&
        clampedAnchor.hash === clampedAnchor.anchor.panel.dataset.paragraphSha256 &&
        Math.abs(window.scrollY - clampedAnchor.scrollY) < 1) return clampedAnchor.anchor;
    clampedAnchor = null;
    return capture();
  }
  function cancelComparisonRestore() {
    pendingComparisonRestore = null;
    ++comparisonRestoreRevision;
  }
  function pendingComparisonPassage() {
    var pending = pendingComparisonRestore;
    if (!pending) return null;
    var panel = pending.anchor.panel;
    if (!panel.isConnected || sourceContext() !== pending.context ||
        panel.dataset.paragraphSha256 !== pending.hash ||
        (scrollIntentRevision !== pending.intent && Math.abs(window.scrollY - pending.scrollY) >= 1)) {
      cancelComparisonRestore(); return null;
    }
    return panel;
  }
  function queueAnalysisRestore() {
    if (applyingNativePreferences) return;
    var previous = pendingComparisonPassage() && pendingComparisonRestore;
    var anchor = previous ? previous.anchor : captureForRestore();
    if (!anchor) { cancelComparisonRestore(); return; }
    if (!previous) anchor = Object.assign({}, anchor, {comparisonBoundary: readingViewportTop()});
    var revision = ++comparisonRestoreRevision;
    pendingComparisonRestore = previous || {anchor: anchor, context: sourceContext(),
      hash: anchor.panel.dataset.paragraphSha256, intent: scrollIntentRevision, scrollY: window.scrollY};
    restore(anchor, false, function() {
      return revision === comparisonRestoreRevision && Boolean(pendingComparisonPassage());
    }, function() { pendingComparisonRestore = null; });
  }
  // A real window scroll supersedes a pending target even if the reader
  // subsequently returns to the same position. Nested panels do not affect it.
  function clearClampedAnchor() { clampedAnchor = null; }
  window.addEventListener("scroll", function() {
    if (clampedAnchor && Math.abs(window.scrollY - clampedAnchor.scrollY) >= 1) clearClampedAnchor();
  }, {passive:true});
  // Record user gestures separately from browser scroll anchoring. The frame
  // cancels only when a gesture also changed the document's scroll position,
  // so scrolling an independent panel does not cancel manuscript restoration.
  function scrollIntent() { ++scrollIntentRevision; }
  window.addEventListener("wheel", scrollIntent, {passive:true});
  window.addEventListener("touchmove", scrollIntent, {passive:true});
  document.addEventListener("keydown", function(event) {
    // Space activates controls or edits text; it is not a document scroll.
    if (event.key === " " && event.target.closest && event.target.closest(
      'button, input, textarea, select, summary, [role="button"], [role="menuitem"], [role="checkbox"], [role="switch"], [role="tab"], [role="radio"], [contenteditable="true"]'
    )) return;
    if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "].includes(event.key)) scrollIntent();
  });
  document.addEventListener("pointerdown", function(event) {
    if (event.target === document.documentElement && event.clientX >= document.documentElement.clientWidth) scrollIntent();
  }, {passive:true});
  function currentMeasuredPassage(anchor) {
    if (anchor && anchor.panel.matches(".ptext")) return anchor.panel;
    var boundary = readingViewportTop();
    return panels.find(function(item) {
      var rect = item.getBoundingClientRect();
      return rect.height > 0 && rect.bottom > boundary && rect.top < innerHeight;
    }) || panels.find(function(item) {return item.getClientRects().length;});
  }
  var inspectCurrent = document.getElementById("reader-inspect-current");
  if (inspectCurrent) inspectCurrent.addEventListener("click", function() {
    var panel = currentMeasuredPassage(capture());
    if (panel) inspectValues(panel, null, inspectCurrent);
  });
  if (analysisGuide && metric) {
    var summary = analysisGuide.querySelector("summary");
    var status = document.getElementById("reader-analysis-guide-state");
    var reference = document.getElementById("reader-metric-reference");
    var definition = document.getElementById("reader-metric-definition");
    var countedHelp = document.getElementById("reader-guide-counted");
    var comparisonHelp = document.getElementById("reader-guide-comparison");
    var choose = analysisGuide.querySelector('[data-analysis-guide-action="choose"]');
    var example = analysisGuide.querySelector('[data-analysis-guide-action="example"]');
    var explore = analysisGuide.querySelector('[data-analysis-guide-action="explore"]');
    function updateGuide() {
      var state = workbench.state();
      analysisGuide.hidden = state.surface !== "document" || state.focus;
      var option = state.analysisVisible && metric.value ? metric.selectedOptions[0] : null;
      var available = option && option.dataset.available !== "0";
      var text = uiLabel(state.analysisVisible ? "analysis_guide_none" : "analysis_guide_off");
      if (option) {
        var unit = option.dataset.unit;
        text = unit ? uiFormat("analysis_guide_selected", {metric:option.textContent, unit:unit}) : option.textContent;
        if (!available) text += ". " + uiLabel("layer_language_unavailable");
      }
      if (status.textContent !== text) status.textContent = text;
      reference.hash = option?.dataset.reference || "measurements";
      definition.hidden = !option?.dataset.hint;
      definition.textContent = option?.dataset.hint || "";
      countedHelp.hidden = !available;
      comparisonHelp.hidden = !available || option.dataset.inlineEvidence === "1";
      var canInspect = Boolean(available && window.LixityCountedResults?.available());
      example.hidden = !canInspect;
      explore.hidden = !state.analysisVisible || !panels.length;
      choose.classList.toggle("primary", !canInspect);
      example.classList.toggle("primary", canInspect);
      choose.textContent = uiLabel(state.analysisVisible ? "analysis_guide_choose" : "analysis_guide_enable");
    }
    analysisGuide.addEventListener("toggle", updateGuide);
    document.addEventListener("lixity:analysis-layer-change", updateGuide);
    document.addEventListener("lixity:counted-results-change", updateGuide);
    document.addEventListener("lixity:workbench-change", updateGuide);
    analysisGuide.addEventListener("click", function(event) {
      var action = event.target.closest("[data-analysis-guide-action]");
      if (!action || action.hidden) return;
      var anchor = capture();
      analysisGuide.open = false;
      if (action.dataset.analysisGuideAction === "choose") {
        if (!workbench.state().analysisVisible) setAnalysisVisible(true);
        metric.focus({preventScroll:true});
        return;
      }
      if (action.dataset.analysisGuideAction === "example") {
        window.LixityCountedResults?.open(summary, anchor);
      }
      else {
        var panel = currentMeasuredPassage(anchor);
        if (!panel) return;
        current = panel; savedRange = null; evidencePoint = null; returnTarget = summary;
        run("values");
      }
    });
    updateGuide();
  }
  function restore(anchor, arrival, stillCurrent, didBegin) {
    if (!anchor) return;
    if (clampedAnchor && clampedAnchor.anchor !== anchor) clampedAnchor = null;
    var revision = arrangementRevision;
    var scheduledNavigationRevision = passageNavigationRevision;
    var scheduledScrollY = window.scrollY;
    var scheduledScrollIntent = scrollIntentRevision;
    var scheduledContext = sourceContext(), scheduledHash = anchor.panel.dataset.paragraphSha256;
    requestAnimationFrame(function() {
      if (stillCurrent && !stillCurrent()) {
        if (pendingDockAnchor && pendingDockAnchor.revision === revision) pendingDockAnchor = null;
        return;
      }
      if (didBegin) didBegin();
      if (scheduledNavigationRevision !== passageNavigationRevision || revision !== arrangementRevision) {
        if (pendingDockAnchor && pendingDockAnchor.revision === revision) pendingDockAnchor = null;
        return;
      }
      if (!anchor.panel.isConnected || !anchor.panel.getClientRects().length || sourceContext() !== scheduledContext ||
          anchor.panel.dataset.paragraphSha256 !== scheduledHash) {
        clampedAnchor = null;
        if (pendingDockAnchor && pendingDockAnchor.revision === revision) pendingDockAnchor = null;
        return;
      }
      var scrollRoot = document.scrollingElement || document.documentElement;
      var maximum = Math.max(0, scrollRoot.scrollHeight - window.innerHeight);
      // Automatic scroll anchoring is not a reader's gesture. Only a newer
      // gesture that actually moved this document supersedes the restoration.
      if (scheduledScrollIntent !== scrollIntentRevision && Math.abs(window.scrollY - scheduledScrollY) >= 1) {
        clampedAnchor = null;
        if (pendingDockAnchor && pendingDockAnchor.revision === revision) pendingDockAnchor = null;
        return;
      }
      var top = anchor.panel.getBoundingClientRect().top;
      var prose = anchor.panel.querySelector(".ptext-inner > p");
      // Inline analysis controls may disappear while the prose stays in view.
      if (prose && Number.isFinite(anchor.proseOffset)) top = prose.getBoundingClientRect().top - anchor.proseOffset;
      var intendedTop = anchor.top;
      if (Number.isFinite(anchor.comparisonBoundary)) {
        intendedTop += readingViewportTop() - anchor.comparisonBoundary;
      }
      var offset = top - intendedTop, before = window.scrollY;
      window.scrollBy(0, offset);
      // A changed layout can temporarily make the requested position
      // unreachable. Retry it on the next preserving transition only if
      // the reader has not moved elsewhere.
      var requested = before + offset;
      clampedAnchor = (requested < -1 || requested > maximum + 1) &&
        Math.abs(window.scrollY - before - offset) > 1 ?
        {anchor: anchor, scrollY: window.scrollY, context: sourceContext(), hash: anchor.panel.dataset.paragraphSha256} : null;
      if (arrival && window.LixityMotion) window.LixityMotion.passage(anchor.panel);
      if (pendingDockAnchor && pendingDockAnchor.revision === revision) pendingDockAnchor = null;
    });
  }
  function retain(action) {
    var anchor = captureForRestore(), previous = workbench.state(), outer = retainedAnchor;
    retainedAnchor = anchor;
    try { action(); } finally { retainedAnchor = outer; }
    var next = workbench.state();
    // The tool subscriber owns one layout restore, including an immediate
    // reversal before its opening frame. Do not queue a second transient anchor.
    if (previous.contextTool !== next.contextTool && next.surface === "document") return;
    restore(anchor);
  }
  function appearance(changes) {
    document.body.style.setProperty("--reader-font-size", (preferences.size / 16) + "rem");
    appearanceChoices.forEach(function(choice) {
      var value = preferences[choice.key];
      document.body.style.setProperty(choice.select.dataset.cssProperty, choice.options.get(value));
      choice.select.value = value;
      choice.buttons.forEach(function(button) {
        button.setAttribute("aria-pressed", String(button.dataset.readerChoice === value));
      });
    });
    sizeOutput.value = String(preferences.size);
    smaller.disabled = preferences.size <= minSize;
    larger.disabled = preferences.size >= maxSize;
    saveReaderPreferences(changes);
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
    if (panel.classList.contains("flagged")) {
      var flag = document.createElement("button");
      flag.type = "button"; flag.className = "ctl reader-review-flag";
      flag.dataset.readerFlag = panel.id;
      flag.textContent = uiLabel("reading_tense_flag");
      flag.dataset.help = tenseTitle(panel);
      flag.setAttribute("aria-controls", "reader-inspector");
      inner.appendChild(flag);
    }
    panel.tabIndex = -1;
  }
  function closeMenu(restoreFocus) {
    menu.hidden = true;
    evidencePoint = null;
    if (returnTarget) returnTarget.setAttribute("aria-expanded", "false");
    if (restoreFocus && returnTarget && returnTarget.isConnected) returnTarget.focus({preventScroll: true});
  }
  function revealPassageControl(control) {
    // Sticky toolbar controls already have a visible return position.
    if (!control.closest("#chapters")) return;
    var bounds = control.getBoundingClientRect();
    if (bounds.top >= readingViewportTop() && bounds.bottom <= innerHeight) return;
    setPassageScrollMargin(control);
    window.LixityComponents.scrollIntoViewSafe(control, {block: "nearest", behavior: "instant"});
  }
  function closeInspector(restoreFocus) {
    workbench.dispatch({type: "tool", value: "none"});
    if (restoreFocus && inspectorTarget && inspectorTarget.isConnected) {
      var button = inspectorTrigger && inspectorTrigger.isConnected ? inspectorTrigger : inspectorTarget.querySelector(".reader-paragraph-actions");
      if (!button) return;
      button.focus({preventScroll: true});
      if (!narrowContext.matches) {
        var revision = arrangementRevision;
        requestAnimationFrame(function() {
          if (revision === arrangementRevision && document.activeElement === button) revealPassageControl(button);
        });
      }
    }
  }
  function requestTool(value, panel, trigger) {
    clampedAnchor = null;
    contextPassage = panel;
    if (inspectorTarget && inspectorTarget !== panel) {
      inspectorTarget.classList.remove("reader-inspector-target");
      inspectorTarget = inspectorTrigger = null; inspectorBody.replaceChildren();
    }
    // Passage capture precedes the responsive return thread entering layout.
    // Its original position remains authoritative when opening research.
    requestedAnchor = value === "research" && validOrigin() && origin.anchor.panel === panel ?
      origin.anchor : {panel: panel, top: panel.getBoundingClientRect().top};
    if (trigger && panel.contains(trigger)) requestedAnchor.trigger = trigger;
    if (workbench.state().contextTool === value) {
      dockOrigin = requestedAnchor; requestedAnchor = null;
      if (narrowContext.matches) dock.scrollIntoView({block: "start", behavior: "instant"});
      if (window.LixityMotion) window.LixityMotion.reveal(dock);
    } else retain(function() { workbench.dispatch({type: "tool", value: value}); });
  }
  function leavePassage(target) {
    if (!target || !target.closest("#chapters")) return;
    ++passageNavigationRevision;
    cancelComparisonRestore();
    var owner = contextPassage || dockOrigin && dockOrigin.panel || inspectorTarget;
    if (owner && (target === owner || owner.contains(target))) return;
    // Explicit navigation owns the destination. Do not restore the old tool's
    // scroll/focus origin when retiring its context, including on mobile.
    dockOrigin = requestedAnchor = pendingDockAnchor = clampedAnchor = null;
    if (inspectorTarget) inspectorTarget.classList.remove("reader-inspector-target");
    contextPassage = inspectorTarget = inspectorTrigger = null; inspectorBody.replaceChildren();
    if (workbench.state().contextTool !== "none") workbench.dispatch({type: "tool", value: "none"});
  }
  function setFocus(value) {
    retain(function() { workbench.dispatch({type: "focus", value: value}); });
  }
  function openOverview() {
    if (workbench.state().surface === "overview") return;
    overviewAnchor = capture();
    workbench.dispatch({type: "surface", value: "overview"});
  }
  function showOverview() {
    if (document.body.classList.contains("manuscript-writing")) return;
    if (workbench.state().view !== "analysis") switchActiveView("analysis", true);
    if (workbench.state().surface !== "overview") window.LixityAnalysisNavigation?.showMeasurements();
    openOverview();
    (document.getElementById("workspace-reader") || controls).scrollIntoView({block: "start", behavior: "instant"});
    document.getElementById("workbench-overview-back").focus({preventScroll: true});
  }
  function passageContext(panel) {
    var chapter = panel.closest(".chapter"), heading = chapter && chapter.querySelector("h2, h3");
    return (heading ? heading.textContent.trim() + " · " : "") +
      uiFormat("reading_passage_lines", {start: panel.dataset.start, end: panel.dataset.end});
  }
  function tenseTitle(panel) {
    var trigger = panel.dataset.tenseTrigger;
    return uiLabel(["mixed", "switch", "mixed_switch"].includes(trigger) ? "reading_tense_" + trigger : "reading_tense_flag");
  }
  async function renderTenseCues(panel, host) {
    var owner = window.LixityAnalysisEvidence, source = paragraphContent[panel.id];
    var project = document.body.dataset.manuscriptProjectToken, hash = panel.dataset.paragraphSha256;
    function current() {
      return inspectorTarget === panel && inspectorBody.contains(host) && panel.isConnected &&
        paragraphContent[panel.id] === source && document.body.dataset.manuscriptProjectToken === project &&
        panel.dataset.paragraphSha256 === hash;
    }
    host.setAttribute("aria-busy", "true");
    var evidence = null;
    try { if (owner && owner.tense) evidence = await owner.tense(panel); } catch (_) { /* Missing evidence stays explicit. */ }
    if (!current()) return;
    host.setAttribute("aria-busy", "false");
    if (evidence && evidence.grammar) {
      var groups = evidence.grammar.groups;
      var grammarNote = document.createElement("p"); grammarNote.className = "ctl-note";
      grammarNote.textContent = uiFormat("reading_tense_grammar_summary", {
        groups:groups.length,
        excluded:groups.filter(function(group) {return !group.selected;}).length,
        other:groups.filter(function(group) {return group.selected && !group.bucket && group.tense !== "unresolved";}).length,
        unresolved:groups.filter(function(group) {return group.tense === "unresolved" || group.scope === "unresolved";}).length
      });
      host.appendChild(grammarNote);
    }
    var complete = true;
    ["present", "past"].forEach(function(key) {
      var layer = evidence && evidence[key], count = Number(panel.dataset[key === "present" ? "pre" : "pas"]);
      if (!layer || layer.count !== count) {complete = false; return;}
      if (layer.status !== "available") complete = false;
      if (!layer.cues.length) return;
      var group = document.createElement("section"); group.className = "reader-tense-group";
      group.setAttribute("aria-label", uiLabel("reading_tense_" + key));
      var title = document.createElement("strong"); title.textContent = uiLabel("reading_tense_" + key); group.appendChild(title);
      var cues = document.createElement("div"); cues.className = "reader-tense-cues";
      var extra = document.createElement("details"), summary = document.createElement("summary");
      summary.textContent = uiCountFormat("reading_tense_more", layer.cues.length - 3); extra.appendChild(summary);
      var rest = document.createElement("div"); rest.className = "reader-tense-cues"; extra.appendChild(rest);
      layer.cues.forEach(function(cue, index) {
        var button = document.createElement("button"); button.type = "button"; button.className = "ctl reader-tense-cue";
        button.textContent = cue.quote; button.title = uiLabel("reading_tense_cue_help");
        button.addEventListener("click", async function() {
          if (!current()) return;
          var revealed = false;
          try { revealed = await owner.revealTense(panel, key, cue.index); } catch (_) { /* Recheck failed; do not guess a range. */ }
          if (!revealed && current()) {host.textContent = uiLabel("reading_tense_unmapped");}
        });
        (index < 3 ? cues : rest).appendChild(button);
      });
      group.appendChild(cues); if (layer.cues.length > 3) group.appendChild(extra); host.appendChild(group);
    });
    if (!complete) {
      var note = document.createElement("p"); note.className = "ctl-note";
      note.textContent = uiLabel("reading_tense_unmapped"); host.appendChild(note);
    }
  }

  function renderPassageBacklinks(panel, container) {
    var backlinksWrap = document.createElement("div");
    backlinksWrap.className = "reader-backlinks-panel";

    var header = document.createElement("div");
    header.className = "reader-backlinks-header";
    var iconSvg = window.LixityIcons && typeof window.LixityIcons.svg === "function" ?
      window.LixityIcons.svg("link") : "";
    header.innerHTML = iconSvg || "";
    var headerText = document.createElement("span");
    headerText.textContent = uiLabel("reader_backlinks_heading");
    header.appendChild(document.createTextNode(" "));
    header.appendChild(headerText);
    backlinksWrap.appendChild(header);

    // 1. Research dossier & evidence link card
    var researchCard = document.createElement("a");
    researchCard.className = "reader-backlink-card";
    researchCard.setAttribute("role", "button");
    researchCard.tabIndex = 0;

    var rTitle = document.createElement("span");
    rTitle.className = "reader-backlink-title";
    var rIcon = window.LixityIcons && typeof window.LixityIcons.svg === "function" ?
      window.LixityIcons.svg("book-open") : "";
    rTitle.innerHTML = rIcon || "";
    var rTitleText = document.createElement("span");
    rTitleText.textContent = uiLabel("reader_backlinks_dossier_title");
    rTitle.appendChild(document.createTextNode(" "));
    rTitle.appendChild(rTitleText);

    var rSnippet = document.createElement("span");
    rSnippet.className = "reader-backlink-snippet";
    var textPreview = panel.textContent ? panel.textContent.trim().slice(0, 90) + "…" : "";
    rSnippet.textContent = uiFormat("reader_backlinks_dossier_hint", {preview: textPreview});

    researchCard.appendChild(rTitle);
    researchCard.appendChild(rSnippet);
    researchCard.addEventListener("click", function(e) {
      e.preventDefault();
      if (window.LixityManuscriptLinks && typeof window.LixityManuscriptLinks.review === "function") {
        window.LixityManuscriptLinks.review(panel);
      } else if (typeof switchActiveView === "function") {
        switchActiveView("research");
      } else {
        var researchBtn = document.querySelector('[data-view="research"], [data-view-pane="research"]');
        if (researchBtn) researchBtn.click();
      }
    });
    researchCard.addEventListener("keydown", function(e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        researchCard.click();
      }
    });
    backlinksWrap.appendChild(researchCard);

    // 2. Audio & Speech Direction card
    var audioCard = document.createElement("a");
    audioCard.className = "reader-backlink-card";
    audioCard.setAttribute("role", "button");
    audioCard.tabIndex = 0;

    var aTitle = document.createElement("span");
    aTitle.className = "reader-backlink-title";
    var aIcon = window.LixityIcons && typeof window.LixityIcons.svg === "function" ?
      window.LixityIcons.svg("mic") : "";
    aTitle.innerHTML = aIcon || "";
    var aTitleText = document.createElement("span");
    aTitleText.textContent = uiLabel("reader_backlinks_audio_title");
    aTitle.appendChild(document.createTextNode(" "));
    aTitle.appendChild(aTitleText);

    var aSnippet = document.createElement("span");
    aSnippet.className = "reader-backlink-snippet";
    aSnippet.textContent = uiLabel("reader_backlinks_audio_hint");

    audioCard.appendChild(aTitle);
    audioCard.appendChild(aSnippet);
    audioCard.addEventListener("click", function(e) {
      e.preventDefault();
      var pBtn = document.getElementById("reader-teleprompter");
      if (pBtn) pBtn.click();
      else if (window.LixityTeleprompter) window.LixityTeleprompter.open();
    });
    audioCard.addEventListener("keydown", function(e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        audioCard.click();
      }
    });
    backlinksWrap.appendChild(audioCard);

    container.appendChild(backlinksWrap);
  }

  function showValues(panel, point) {
    if (!panel) return;
    renderParagraph(panel);
    var values = panel.querySelector(".paragraph-values");
    if (!values) return;
    var copy = values.cloneNode(true); copy.open = false;
    if (inspectorTarget) inspectorTarget.classList.remove("reader-inspector-target");
    var context = document.createElement("div"); context.className = "reader-passage-context";
    var location = document.createElement("p"); location.className = "ctl-note";
    location.textContent = passageContext(panel); context.appendChild(location);
    if (window.LixityAnalysisReview && window.LixityAnalysisReview.available(panel)) {
      var review = actionButton("review", "triage_open", false);
      review.addEventListener("click", function() {window.LixityAnalysisReview.open(panel);});
      context.appendChild(review);
    }
    if (panel.classList.contains("flagged")) {
      var flagCard = document.createElement("div"); flagCard.className = "reader-passage-flag sev-" + panel.dataset.severity;
      var flagHeader = document.createElement("div"); flagHeader.className = "reader-passage-flag-header";
      var flagBadge = document.createElement("span");
      flagBadge.className = "badge sev-" + panel.dataset.severity;
      flagBadge.textContent = uiLabel("severity_" + panel.dataset.severity);
      var flagTitle = document.createElement("span"); flagTitle.className = "reader-passage-flag-title";
      flagTitle.textContent = tenseTitle(panel);
      flagHeader.appendChild(flagBadge); flagHeader.appendChild(flagTitle);
      var reviewHint = document.createElement("p"); reviewHint.className = "ctl-note";
      reviewHint.textContent = uiLabel("reading_tense_flag_help");
      var cueHost = document.createElement("div"); cueHost.className = "reader-tense-evidence";
      var counts = document.createElement("details"); counts.className = "reader-tense-counts";
      var countsTitle = document.createElement("summary"); countsTitle.textContent = uiLabel("reading_tense_counts");
      counts.appendChild(countsTitle);
      var flagBody = document.createElement("p"); flagBody.className = "reader-passage-flag-reason";
      flagBody.textContent = uiFormat("triage_reason", {
        present: panel.dataset.pre || "0",
        past: panel.dataset.pas || "0",
        mixed: uiLabel(panel.dataset.mix === "1" ? "research_value_yes" : "research_value_no"),
        switch: uiLabel(panel.dataset.swi === "1" ? "research_value_yes" : "research_value_no")
      });
      counts.appendChild(flagBody);
      var help = document.createElement("details"), helpTitle = document.createElement("summary");
      help.className = "reader-tense-help"; helpTitle.textContent = uiLabel("reading_tense_help");
      var guidance = document.createElement("p"); guidance.className = "ctl-note";
      guidance.textContent = uiLabel("triage_author_guidance"); help.append(helpTitle, guidance);
      flagCard.append(flagHeader, reviewHint, cueHost, counts, help);
      context.appendChild(flagCard);
      // Verification is asynchronous; the context identity is checked before display.
      Promise.resolve().then(function() {renderTenseCues(panel, cueHost);});
    } else if (paragraphContent[panel.id]?.[4]?.grammar || paragraphContent[panel.id]?.[3]?.tense?.grammar) {
      var grammarHost = document.createElement("div"); grammarHost.className = "reader-tense-evidence";
      context.appendChild(grammarHost);
      Promise.resolve().then(function() {renderTenseCues(panel, grammarHost);});
    }
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
    renderPassageBacklinks(panel, context);
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
    if (!sameDocument) clampedAnchor = null;
    var anchor = requestedAnchor || (pending && pendingDockAnchor.anchor) || retainedAnchor || captureForRestore();
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
      var selected = contextPassage || anchor && anchor.panel;
      if (selected && selected.matches(".ptext")) showValues(selected);
      else inspectorBody.textContent = uiLabel(panels.length ? "reading_values_hint" : "reading_coverage");
    }
    document.querySelectorAll("[data-context-tool]").forEach(function(button) {
      button.setAttribute("aria-pressed", String(state.contextTool === button.dataset.contextTool));
    });
    analysisToggle.setAttribute("aria-pressed", String(state.analysisVisible));
    document.getElementById("manuscript-analysis-state").textContent = uiLabel(state.analysisVisible ? "reading_on" : "reading_off");
    analysisToggle.hidden = state.surface === "overview";
    var dossierToggle = document.getElementById("workspace-reader-toggle");
    if (dossierToggle) dossierToggle.hidden = state.surface === "overview";
    document.getElementById("workbench-overview-open").hidden = state.surface === "overview";
    document.getElementById("workbench-overview-toolbar").hidden = state.surface !== "overview";
    focus.setAttribute("aria-pressed", String(state.focus));
    focus.setAttribute("aria-keyshortcuts", state.focus ? (focusShortcuts + " Escape").trim() : focusShortcuts);
    var focusLabel = uiLabel(state.focus ? "reading_focus_exit" : "reading_focus");
    focus.querySelector(".reader-control-label").textContent = focusLabel;
    focus.setAttribute("aria-label", focusLabel); focus.title = focusLabel;
    if (state.view !== previous.view || state.surface !== previous.surface) {
      closeMenu(false); selectionTools.hidden = true; settingsPanels.forEach(function(panel) {panel.open = false;});
    }
    if (analysisOptions && (!state.analysisVisible || state.focus)) analysisOptions.open = false;
    if (toolChanged && narrowContext.matches) {
      var destination = open ? null : dockOrigin;
      var returnDockFocus = dock.contains(document.activeElement);
      pendingDockFocusRevision = !open && destination && returnDockFocus ? revision : null;
      requestAnimationFrame(function() {
        if (pendingDockFocusRevision === revision) pendingDockFocusRevision = null;
        if (revision !== arrangementRevision) return;
        if (open) dock.scrollIntoView({block: "start", behavior: "instant"});
        else if (destination && destination.panel.isConnected) {
          window.scrollBy(0, destination.panel.getBoundingClientRect().top - destination.top);
          // The return runs on the next frame. Do not override a new focus
          // choice made after the dock started closing.
          var currentFocus = document.activeElement;
          if (returnDockFocus && (currentFocus === document.body || dock.contains(currentFocus) ||
              currentFocus === destination.trigger || currentFocus === destination.panel)) {
            var trigger = destination.trigger;
            if (!trigger || !trigger.isConnected || !trigger.getClientRects().length || trigger.disabled) {
              trigger = destination.panel.querySelector(".reader-paragraph-actions") || destination.panel;
            }
            trigger.focus({preventScroll: true});
            revealPassageControl(trigger);
          }
          if (window.LixityMotion) window.LixityMotion.passage(destination.panel);
        }
      });
      if (!open) dockOrigin = null;
    } else if (state.surface === previous.surface && state.view === previous.view &&
        (state.contextTool !== previous.contextTool || state.analysisVisible !== previous.analysisVisible || state.focus !== previous.focus)) restore(anchor, toolChanged && !open);
    if (window.LixityMotion) {
      if (state.surface !== previous.surface) window.LixityMotion.view(document.getElementById("view-pane-analysis"));
      if (toolChanged && open) window.LixityMotion.reveal(dock);
      if (state.analysisVisible && !previous.analysisVisible && state.surface === "document") window.LixityMotion.analysis(chapters);
    }
    fitSearchScrollMargin();
    window.dispatchEvent(new Event("resize"));
  });
  function rangeFor(panel) {
    var selection = window.getSelection();
    if (!selection || selection.rangeCount !== 1 || selection.isCollapsed) return null;
    var range = selection.getRangeAt(0), paragraph = panel.querySelector(".ptext-inner > p");
    if (!paragraph || !paragraph.contains(range.startContainer) || !paragraph.contains(range.endContainer) || !selection.toString().trim()) return null;
    return range.cloneRange();
  }
  function place(node, x, y, anchor) {
    LixityComponents.measureOverlay(node, function() {
      node.hidden = false; node.style.left = "0px"; node.style.top = "0px";
      var rect = node.getBoundingClientRect();
      if (anchor) {
        var trigger = anchor.getBoundingClientRect();
        var below = Math.max(0, innerHeight - trigger.bottom - 12), above = Math.max(0, trigger.top - 12);
        var useBelow = below >= rect.height || below >= above;
        node.style.maxHeight = (useBelow ? below : above) + "px";
        rect = node.getBoundingClientRect();
        x = trigger.left; y = useBelow ? trigger.bottom + 4 : trigger.top - rect.height - 4;
      }
      LixityComponents.placeClampedOverlay(node, x, y, {bounds: rect, gutter: 8});
      node._readerScroll = [window.scrollX, window.scrollY];
    });
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
      if (document.getElementById("reader-speech") && panel.dataset.paragraphSha256) {
        fragment.appendChild(actionButton("direction", "speech_direction_title", true));
      }
    }
    if (panel.querySelector("[data-manuscript-link-selection]")) {
      var hasSub = savedRange && Array.from(savedRange.toString()).length > 0 && Array.from(savedRange.toString()).length <= 10000;
      var linkBtn = actionButton("link", hasSub ? "manuscript_link_action" : "manuscript_link_paragraph_action", !compact);
      linkBtn.setAttribute("aria-keyshortcuts", "Alt+L");
      linkBtn.title = uiLabel("manuscript_link_hint");
      fragment.appendChild(linkBtn);
    }
    if (panel.dataset.markers === "1") {
      (compact ? ["pruefen"] : ["pruefen", "sachcheck", "todo", "achtung"]).forEach(function(kind) {
        var marker = panel.querySelector('[data-marker-kind="' + kind + '"]');
        if (marker && !marker.disabled && marker.getAttribute("aria-disabled") !== "true") fragment.appendChild(actionButton(kind, "marker_action_" + kind, !compact));
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
    menu.style.maxHeight = "";
    place(menu, x, y, trigger && trigger.closest("[data-reader-paragraph]"));
    returnTarget.setAttribute("aria-expanded", "true");
    var first = menu.querySelector("button"); if (first) { first.tabIndex = 0; first.focus({preventScroll: true}); }
  }
  function inspectValues(panel, point, trigger) {
    showValues(panel, point);
    inspectorTrigger = trigger;
    requestTool("analysis", panel, trigger);
    if (trigger) document.getElementById("reader-inspector-close").focus({preventScroll: true});
  }
  function run(action) {
    if (!current || !current.isConnected) return;
    var panel = current, range = rangeFor(current) || savedRange, point = evidencePoint;
    closeMenu(false); selectionTools.hidden = true;
    renderParagraph(panel);
    if ((action === "values" || action === "companion") && document.body.classList.contains("reader-focus")) setFocus(false);
    if (action === "values") {
      inspectValues(panel, point, returnTarget);
    } else if (action === "direction") {
      document.dispatchEvent(new CustomEvent("lixity:open-speech-studio", {
        detail: {mode:"reader", passage:panel, opener:returnTarget}
      }));
    } else if (action === "link") {
      if (!range) {
        var pnode = panel.querySelector(".ptext-inner > p");
        if (pnode) {
          range = document.createRange();
          range.selectNodeContents(pnode);
        }
      }
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
  var search = document.getElementById("text-search");
  function fitSearchScrollMargin() {
    document.body.style.setProperty("--reader-controls-height", controls.getBoundingClientRect().height + "px");
    if (search) setPassageScrollMargin(search);
  }
  // Native focus and scrollIntoView must expose search below the sticky controls.
  if (typeof ResizeObserver === "function") {
    var readerChromeObserver = new ResizeObserver(fitSearchScrollMargin);
    [controls, document.getElementById("workbench-thread")].filter(Boolean).forEach(function(node) {
      readerChromeObserver.observe(node);
    });
  }
  window.addEventListener("resize", fitSearchScrollMargin);
  fitSearchScrollMargin();
  function settingsInFlow(panel, body) {
    return getComputedStyle(body || panel.querySelector(".reader-settings-body")).position !== "fixed";
  }
  function placeSettings() {
    settingsPanels.forEach(function(panel) {
      if (!panel.open) return;
      var body = panel.querySelector(".reader-settings-body"), gutter = 8, gap = 6;
      if (settingsInFlow(panel, body)) {
        body.style.left = body.style.top = body.style.maxHeight = "";
        return;
      }
      var summary = panel.querySelector("summary").getBoundingClientRect();
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
  analysisToggle.addEventListener("click", function() {
    var previous = workbench.state();
    setAnalysisVisible(!previous.analysisVisible);
    if (previous.surface === "overview") {
      rememberPassageLocation(overviewAnchor && overviewAnchor.panel); restore(overviewAnchor, true);
    }
  });
  document.querySelectorAll("[data-context-tool]").forEach(function(button) {
    button.addEventListener("click", function() { retain(function() {
      workbench.dispatch({type: "tool", value: button.dataset.contextTool});
    }); });
  });
  document.getElementById("workbench-overview-open").addEventListener("click", showOverview);
  document.getElementById("workbench-overview-back").addEventListener("click", function() {
    rememberPassageLocation(overviewAnchor && overviewAnchor.panel);
    workbench.dispatch({type: "surface", value: "document"}); restore(overviewAnchor, true);
    document.getElementById("workbench-overview-open").focus({preventScroll: true});
  });
  function resizeText(direction) {
    retain(function() {
      preferences.size = boundedSize(preferences.size + direction * sizeStep);
      appearance({size: preferences.size});
    });
  }
  smaller.addEventListener("click", function() { resizeText(-1); });
  larger.addEventListener("click", function() { resizeText(1); });
  appearanceChoices.forEach(function(choice) {
    function choose(value) {
      if (!choice.options.has(value)) return;
      retain(function() { preferences[choice.key] = value; appearance({[choice.key]: value}); });
    }
    choice.select.addEventListener("change", function() { choose(choice.select.value); });
    choice.buttons.forEach(function(button) {
      button.addEventListener("click", function() { choose(button.dataset.readerChoice); });
    });
  });
  focus.addEventListener("click", function() {
    if (focus.getClientRects().length) setFocus(!document.body.classList.contains("reader-focus"));
  });
  function codepointSpansToRanges(prose, text, spans) {
    if (!prose || !spans || !spans.length || prose.textContent !== text) return [];
    var offsets = LixityComponents.cpOffsets(text), rangeAt = LixityComponents.textRangeMap(prose);
    var ranges = [];
    spans.forEach(function(span) {
      var s = offsets[span.start], e = offsets[span.end];
      if (!Number.isInteger(s) || !Number.isInteger(e) || e <= s) return;
      ranges.push(rangeAt(s, e));
    });
    return ranges;
  }
  async function applyDirectSpeech() {
    directSpeechFrame = 0;
    var generation = ++directSpeechGeneration;
    if (!directSpeechActive || !directSpeechIntersection) return;
    var visiblePanels = Array.from(directSpeechVisible);
    var evidence = await Promise.all(visiblePanels.map(function(panel) {return loadParagraphEvidence(panel.id);}));
    if (!directSpeechActive || generation !== directSpeechGeneration) return;
    var highlight = new Highlight();
    visiblePanels.forEach(function(panel, index) {
      if (!directSpeechVisible.has(panel)) return;
      var record = evidence[index], pairs = record?.layers?.dialogue?.quotation_ranges;
      if (record?.paragraph_sha256 !== panel.dataset.paragraphSha256 || !Array.isArray(pairs)) return;
      var prose = panel.querySelector(".ptext-inner > p"), text = paragraphContent[panel.id]?.[0];
      codepointSpansToRanges(prose, text, pairs.map(function(pair) {
        return {start:pair[0], end:pair[1]};
      })).forEach(function(range) {highlight.add(range);});
    });
    if (highlight.size) CSS.highlights.set("lixity-direct-speech", highlight);
    else CSS.highlights.delete("lixity-direct-speech");
  }
  function scheduleDirectSpeech() {
    if (directSpeechActive && !directSpeechFrame) {
      directSpeechFrame = requestAnimationFrame(applyDirectSpeech);
    }
  }
  function setDirectSpeech(enabled) {
    directSpeechActive = Boolean(enabled);
    document.body.classList.toggle("reader-direct-speech", directSpeechActive);
    if (directSpeechBtn) directSpeechBtn.setAttribute("aria-pressed", directSpeechActive ? "true" : "false");
    if (directSpeechIntersection) {directSpeechIntersection.disconnect(); directSpeechIntersection = null;}
    if (directSpeechObserver) {directSpeechObserver.disconnect(); directSpeechObserver = null;}
    directSpeechVisible.clear();
    directSpeechGeneration++;
    if (window.CSS && CSS.highlights) CSS.highlights.delete("lixity-direct-speech");
    if (directSpeechActive) {
      if (window.CSS && CSS.highlights && window.Highlight && typeof IntersectionObserver === "function") {
        directSpeechIntersection = new IntersectionObserver(function(entries) {
          entries.forEach(function(entry) {
            if (entry.isIntersecting && entry.intersectionRect.height > 0) directSpeechVisible.add(entry.target);
            else directSpeechVisible.delete(entry.target);
          });
          scheduleDirectSpeech();
        }, {threshold:Number.EPSILON});
        directSpeechObserver = new MutationObserver(scheduleDirectSpeech);
        directSpeechObserver.observe(chapters, {childList: true, subtree: true});
      }
    }
    panels.forEach(function(panel) {
      panel.classList.remove("direct-speech-narrative", "direct-speech-mixed", "direct-speech-only");
      if (!directSpeechActive) return;
      var content = paragraphContent[panel.id];
      var dialogue = content?.[4]?.dialogue || content?.[3]?.layers?.dialogue;
      if (!dialogue) return;
      var quoted = dialogue.count, words = dialogue.denominator;
      if (dialogue.reason !== "quotation_context_unresolved" && Number.isSafeInteger(words) &&
          Number.isSafeInteger(quoted) && words > 0 && quoted >= 0 && quoted <= words) {
        panel.classList.add(quoted === 0 ? "direct-speech-narrative" :
          quoted === words ? "direct-speech-only" : "direct-speech-mixed");
      }
      if ((dialogue.has_ranges || dialogue.quotation_ranges?.length) && directSpeechIntersection) {
        directSpeechIntersection.observe(panel);
      }
    });
  }
  if (directSpeechBtn) {
    directSpeechBtn.addEventListener("click", function() {
      retain(function() { setDirectSpeech(!directSpeechActive); });
    });
  }
  document.getElementById("reader-chapter").addEventListener("change", function(event) {
    var chapter = document.getElementById(event.target.value);
    if (chapter) {
      event.target.dataset.currentChapter = chapter.id;
      rememberPassageLocation(chapter);
      scrollAndFlash(chapter);
      event.target.value = "";
    }
  });
  document.getElementById("reader-inspector-close").addEventListener("click", function() { retain(function() { closeInspector(true); }); });
  chapters.addEventListener("click", function(event) {
    var flag = event.target.closest("[data-reader-flag]");
    if (flag) {
      current = document.getElementById(flag.dataset.readerFlag);
      savedRange = null; evidencePoint = null; returnTarget = flag;
      run("values"); return;
    }
    var trigger = event.target.closest("[data-reader-paragraph]");
    if (!trigger) return;
    var rect = trigger.getBoundingClientRect(); openMenu(document.getElementById(trigger.dataset.readerParagraph), rect.left, rect.bottom + 4, trigger);
  });
  // Reading a different paragraph is an explicit context change; selecting text
  // in the current paragraph or interacting inside the dock keeps its owner.
  chapters.addEventListener("pointerdown", function(event) {
    var panel = event.target.closest(".ptext");
    if (panel && !event.target.closest("button, a, input, textarea, select")) {
      var anchor = {panel: panel, top: panel.getBoundingClientRect().top};
      leavePassage(panel); restore(anchor);
    }
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
      var content = paragraphContent[panel.id];
      if (node && prose.contains(node) && content && prose.textContent === content[0]) {
        var prefix = document.createRange(); prefix.selectNodeContents(prose); prefix.setEnd(node, offset);
        point = {offset:prefix.toString().length, hash:panel.dataset.paragraphSha256};
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
    settingsPanels.forEach(function(panel) {
      if (panel !== analysisOptions && panel.open && !panel.contains(event.target)) panel.open = false;
    });
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
    if ((event.key === "d" || event.key === "D") && !event.ctrlKey && !event.metaKey && !event.altKey &&
        !event.defaultPrevented && !event.isComposing &&
        !event.target.closest("dialog, [role=dialog], select, input, textarea, [contenteditable]")) {
      if (directSpeechBtn && directSpeechBtn.getClientRects().length) {
        event.preventDefault();
        retain(function() { setDirectSpeech(!directSpeechActive); });
        return;
      }
    }
    if (event.key === "Escape" && !event.defaultPrevented && !event.isComposing && !event.target.closest("dialog, [role=dialog], select")) {
      var opened = settingsPanels.find(function(panel) {return panel.open && panel.getClientRects().length;});
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
  var readingScroll = false;
  function readingInput(event) {
    if (event.target.closest && event.target.closest("#workspace-context-panel, #manuscript-context-menu, #manuscript-selection-tools")) return;
    if (workbench.state().view === "analysis" && workbench.state().surface === "document") readingScroll = true;
  }
  window.addEventListener("wheel", readingInput, {passive: true});
  window.addEventListener("touchmove", readingInput, {passive: true});
  chapters.addEventListener("keydown", function(event) {
    if (["PageDown", "PageUp", "Home", "End", "ArrowDown", "ArrowUp", " "].includes(event.key) &&
        !event.target.closest("button, input, textarea, select, a")) readingInput(event);
  });
  window.addEventListener("scrollend", function() {
    if (!readingScroll) return;
    readingScroll = false;
    var owner = contextPassage || dockOrigin && dockOrigin.panel;
    if (!owner || workbench.state().contextTool === "none") return;
    var bounds = owner.getBoundingClientRect(), boundary = readingViewportTop();
    if (bounds.bottom > boundary && bounds.top < innerHeight) return;
    var anchor = capture();
    if (anchor && anchor.panel !== owner) { leavePassage(anchor.panel); restore(anchor); }
  }, {passive: true});
  window.addEventListener("resize", function() { closeMenu(false); selectionTools.hidden = true; placeSettings(); });
  document.addEventListener("scroll", function(event) {
    settingsPanels.forEach(function(panel) {
      if (!panel.open || panel.contains(event.target) || settingsInFlow(panel)) return;
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
    var paragraphId = relation.dataset.manuscriptLinksParagraph;
    var panel = event.target.closest(".ptext") || (paragraphId ? document.getElementById(paragraphId) : null);
    // Following records in a dialog or companion belongs to the same passage journey.
    if ((!panel || relation.closest("[data-passage-research]")) && readingThread.hasPassage()) return;
    rememberReadingPassage(panel);
  }, true);
  function rememberReadingPassage(panel, selectedRange) {
    var anchor = panel ? {panel: panel, top: panel.getBoundingClientRect().top} : capture();
    if (!anchor) return;
    var chapterControl = document.getElementById("reader-chapter");
    if (chapterControl && anchor.panel.closest(".chapter")) chapterControl.dataset.currentChapter = anchor.panel.closest(".chapter").id;
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
    var originPanel = anchor.panel;
    readingThread.rememberPassage({description: passageContext(anchor.panel), valid: validOrigin, restore: returnToPassage,
      atOrigin: function() {
        var state = workbench.state();
        if (state.view !== "analysis" || state.surface !== "document" || !originPanel.isConnected) return false;
        var rect = originPanel.getBoundingClientRect();
        return rect.height > 0 && rect.bottom > readingViewportTop() && rect.top < innerHeight;
      }});
  }
  window.LixityReader = {fitContext: fitContextDock, requestTool: requestTool, leavePassage: leavePassage, capture: capture, captureForRestore: captureForRestore, restore: restore, retain: retain,
    connectDesktopPreferences: connectDesktopPreferences,
    cancelRestore: function() { ++passageNavigationRevision; pendingDockAnchor = null; clampedAnchor = null; },
    contextFocusReturnPending: function() { return pendingDockFocusRevision === arrangementRevision; },
    pendingComparisonPassage: pendingComparisonPassage,
    enableEvidence: function() { retain(function() {defaultMetric(true); workbench.dispatch({type:"analysis", value:true});}); },
    openOverview: openOverview,
    showOverview: showOverview,
    inspectPassage: function(panel, point, trigger) {
      if (!panel) return;
      retain(function() {
        workbench.dispatch({type: "analysis", value: true});
        inspectValues(panel, point, trigger || null);
      });
    }};
  document.body.classList.add("manuscript-reading");
  panels.forEach(enhanceText);
  document.dispatchEvent(new Event("lixity:reader-ready"));
  workbench.dispatch({type: "analysis", value: false});
  var hashId = window.location.hash.slice(1);
  var hash = hashId ? document.getElementById(hashId) : null;
  if (hash && hash.closest("#manuscript-analysis-panels")) openOverview();
  if (hash && hash.closest("#chapters, #manuscript-analysis-panels")) requestAnimationFrame(function() { scrollAndFlash(hash); });
})();
