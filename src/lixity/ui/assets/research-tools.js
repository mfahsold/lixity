// One inline host reuses the research components without replacing content drafts.
(function () {
  "use strict";
  var manager = document.getElementById("research-manager");
  var host = document.getElementById("research-tool-host");
  if (!manager || !host) return;
  var title = document.getElementById("research-tool-title");
  var closeButton = document.getElementById("research-tool-close");
  var active = "", origin = null, comparison = null, comparisonReturn = null, serial = 0;
  var reviewFilter = null;
  var panes = {};
  ["search", "review", "grounding"].forEach(function(key) {
    panes[key] = document.getElementById("rtab-" + key);
    if (panes[key]) host.appendChild(panes[key]);
  });
  var searchReader = document.createElement("section");
  searchReader.id = "research-search-reader"; searchReader.hidden = true;
  panes.search.appendChild(searchReader);
  function attr(value) { return escapeHtml(String(value || "")).replace(/"/g, "&quot;"); }
  function context() {
    var manuscript = document.getElementById("manuscript-pdf-form") || document.getElementById("workspace-reader");
    return [researchContextToken(), researchSelectionProjectId, document.body.dataset.manuscriptProjectToken,
      document.body.dataset.manuscriptSourceSha256, manuscript && manuscript.dataset.projectToken,
      document.getElementById("text-search") && document.body.dataset.manuscriptName].join(":");
  }
  var acceptedContext = context();
  function capture(control) {
    var scrolls = [];
    for (var node = control && control.parentElement; node; node = node.parentElement)
      scrolls.push({node: node, top: node.scrollTop, left: node.scrollLeft});
    return {control: control, context: context(), scrolls: scrolls, top: window.scrollY, left: window.scrollX,
      tab: document.querySelector("#research-tabs .active"),
      state: window.LixityWorkbench && window.LixityWorkbench.state()};
  }
  function restoreOrigin(value) {
    var request = serial;
    requestAnimationFrame(function() { requestAnimationFrame(function() {
      if (!value || value.context !== context() || request !== serial) return;
      // A late layout callback must not move focus after the user leaves.
      var focused = document.activeElement;
      if (focused !== closeButton && focused !== document.body && !host.contains(focused)) return;
      if (value.state && window.LixityWorkbench) {
        switchActiveView(value.state.view);
        var workbench = window.LixityWorkbench, state = workbench.state();
        if (state.analysisVisible !== value.state.analysisVisible) workbench.dispatch({type: "analysis", value: value.state.analysisVisible});
        if (state.contextTool !== value.state.contextTool) workbench.dispatch({type: "tool", value: value.state.contextTool});
        if (state.surface !== value.state.surface) workbench.dispatch({type: "surface", value: value.state.surface});
        if (state.focus !== value.state.focus) workbench.dispatch({type: "focus", value: value.state.focus});
      }
      var target = value.control && value.control.isConnected && value.control.getClientRects().length ? value.control : value.tab;
      if (target && target.isConnected) target.focus({preventScroll: true});
      value.scrolls.forEach(function(scroll) {
        if (scroll.node.isConnected) scroll.node.scrollTo({top: scroll.top, left: scroll.left, behavior: "instant"});
      });
      window.scrollTo({top: value.top, left: value.left, behavior: "instant"});
    }); });
  }
  function paint() {
    host.hidden = !active;
    Object.keys(panes).forEach(function(key) { if (panes[key]) panes[key].style.display = active === key ? "block" : "none"; });
    manager.querySelectorAll("#research-tools-entry [data-rtab]").forEach(function(button) {
      var selected = button.dataset.rtab === active;
      button.setAttribute("aria-expanded", String(selected)); button.classList.toggle("active", selected);
    });
    title.textContent = uiLabel(active === "search" ? "research_tools_search" : active === "review" ? "research_tools_review" : "research_source_compare_action");
    closeButton.textContent = uiLabel(active === "grounding" ? "research_source_compare_back" : "research_tools_close");
    host.dataset.tool = active;
  }
  function close(restoreFocus) {
    if (!active) return;
    ++serial;
    if (active === "grounding" && comparisonReturn && restoreFocus !== false && comparisonReturn.context === context()) {
      var previous = comparisonReturn;
      active = previous.tool; comparisonReturn = null; comparison = null; paint();
      restoreOrigin(previous.origin); return;
    }
    var value = origin;
    active = ""; origin = comparison = comparisonReturn = null; paint();
    if (restoreFocus !== false) restoreOrigin(value);
  }
  function open(tool, control, options) {
    if (!panes[tool] || (tool === "search" && window.LixitySite.readOnly)) return;
    if (acceptedContext !== context()) reset();
    if (!active || (control && !host.contains(control) && !control.closest("#research-tools-entry")))
      origin = capture(control || document.activeElement);
    if (active !== tool) ++serial;
    active = tool; comparison = comparisonReturn = null;
    if (tool === "review") {
      reviewFilter = options && options.filter || null;
      document.getElementById("research-review-all").hidden = !reviewFilter;
      refreshResearchEditorialReview();
      document.dispatchEvent(new CustomEvent("lixity:research-review", {detail: {filter: reviewFilter}}));
    }
    paint();
    switchActiveView("research");
    if (!(options && options.focus === false)) {
      (tool === "search" ? document.getElementById("r-search-query") : title).focus({preventScroll: true});
    }
  }
  function reset() {
    ++serial; ++researchSearchRead;
    active = ""; origin = comparison = comparisonReturn = reviewFilter = null;
    acceptedContext = context();
    document.getElementById("research-search-results").replaceChildren();
    searchReader.replaceChildren(); searchReader.hidden = true;
    document.getElementById("research-search-results").hidden = false;
    document.getElementById("r-search-query").value = "";
    document.getElementById("r-search-scope").value = "all";
    paint();
  }
  function sourceAction(detail) {
    if (window.LixitySite.readOnly || document.body.dataset.researchCompareCapable !== "true") return "";
    return '<p><button type="button" class="ctl" data-research-source-compare="' + attr(detail.id) + '">' +
      escapeHtml(uiLabel("research_source_compare_action")) + '</button></p>';
  }
  function unavailable(detail) {
    if (!detail || !(detail.text || (detail.passages || []).some(function(p) { return p.verbatim; }))) return "research_source_compare_no_text";
    if (document.body.dataset.hasManuscript !== "true") return "research_source_compare_no_manuscript";
    if (window.LixitySite.readOnly || document.body.dataset.researchCompareCapable !== "true") return "research_status_unavailable";
    return "";
  }
  function openComparison(button) {
    var reader = button.closest(".research-details-body");
    var detail = reader && reader._researchSource;
    if (!detail || detail.id !== button.dataset.researchSourceCompare || !reader._researchSourceCurrent()) return;
    var value = capture(button);
    var nestedSearch = active === "search" && host.contains(reader) && panes.search.contains(reader);
    if (!nestedSearch) origin = value;
    ++serial;
    comparisonReturn = nestedSearch ? {tool: "search", origin: value, context: context()} : null;
    comparison = {detail: detail, reader: reader, context: context(), current: reader._researchSourceCurrent};
    active = "grounding"; paint();
    document.getElementById("research-comparison-source").textContent = uiLabel("research_source_compare_current") + ": " + detail.title;
    document.getElementById("research-comparison-source").dataset.sourceVersion = detail.version_id;
    document.getElementById("research-comparison-version").textContent = detail.id + " · " + detail.version_id;
    document.getElementById("research-comparison-context-details").hidden = false;
    document.getElementById("research-comparison-manuscript").textContent = uiLabel("research_ground_manuscript") + ": " + (document.body.dataset.manuscriptName || "");
    var reason = unavailable(detail);
    document.getElementById("research-comparison-unavailable").textContent = reason ? uiLabel(reason) : "";
    document.getElementById("r-ground-btn").disabled = Boolean(reason);
    document.getElementById("r-ground-btn").setAttribute("aria-busy", "false");
    document.getElementById("research-grounding-results").replaceChildren();
    title.focus({preventScroll: true});
  }
  function comparisonOwnerCurrent(value) {
    return value && value.context === context() && value.reader.isConnected && value.current();
  }
  function invalidateComparison(value) {
    if (!value || value !== comparison || active !== "grounding") return;
    close(false);
    var button = document.getElementById("r-ground-btn");
    button.disabled = false; button.setAttribute("aria-busy", "false");
  }
  function comparisonCurrent(value, request, result) {
    return value && value === comparison && active === "grounding" && request === serial &&
      comparisonOwnerCurrent(value) && acceptResearchContext(value.researchContext, result || {});
  }
  async function compare() {
    var button = document.getElementById("r-ground-btn"), value = comparison;
    if (value && !comparisonOwnerCurrent(value)) { invalidateComparison(value); return; }
    if (button.disabled || !value || unavailable(value.detail)) return;
    value.researchContext = researchReadContext();
    var request = ++serial, gHost = document.getElementById("research-grounding-results");
    button.disabled = true; button.setAttribute("aria-busy", "true");
    gHost.textContent = uiLabel("research_grounding");
    var gres;
    try { gres = await researchApiPost("research-compare", {source_id: value.detail.id}); }
    catch (_) { gres = {ok: false, message: uiLabel("research_ground_failed")}; }
    if (!comparisonCurrent(value, request, gres)) {
      if (value === comparison && request === serial && !comparisonOwnerCurrent(value)) invalidateComparison(value);
      return;
    }
    button.disabled = false; button.setAttribute("aria-busy", "false");
    if (!gres.ok || !gres.summary || !gres.provenance || !gres.provenance.source_version_id ||
        gres.provenance.source_id !== value.detail.id || gres.provenance.project_id !== researchSelectionProjectId) {
      gHost.textContent = gres.message || uiLabel("research_ground_failed");
      researchStatus(gHost.textContent, false); return;
    }
    document.getElementById("research-comparison-source").textContent = uiLabel("research_source_compare_current") + ": " +
      (gres.provenance.source_title || value.detail.title);
    document.getElementById("research-comparison-source").dataset.sourceVersion = gres.provenance.source_version_id;
    document.getElementById("research-comparison-version").textContent = gres.provenance.source_id + " · " + gres.provenance.source_version_id;
    document.getElementById("research-comparison-context-details").hidden = true;
    renderComparison(gres, gHost);
    researchStatus(uiLabel("research_ground_complete"), true);
  }
  function renderComparison(gres, gHost) {
    var sum = gres.summary || {};
    var comparisonMeta = gres.meta || {};
    var crossLanguage = comparisonMeta.source_language && comparisonMeta.manuscript_language &&
      comparisonMeta.source_language !== comparisonMeta.manuscript_language;

    function measured(value) { return typeof value === "number" && Number.isFinite(value); }
    function count(value) { return measured(value) ? value.toLocaleString() : "–"; }
    function percent(value) { return measured(value) ? (value * 100).toFixed(1) + "%" : "–"; }
    var jaccardVal = sum.jaccard_similarity;
    var jaccardPct = percent(jaccardVal);
    var overlapVal = sum.overlap_coefficient;
    var overlapPct = percent(overlapVal);
    var incomplete = [jaccardVal, overlapVal, sum.shared_types, sum.source_content_words, sum.manuscript_content_words].some(function(value) {return !measured(value);});

    var topShared = (gres.lexical_overlap && gres.lexical_overlap.top_shared_terms) || [];
    var sharedChipsHtml = topShared.slice(0, 25).map(function(w) {
      var sc = w.source_count !== undefined ? w.source_count : "?";
      var mc = w.manuscript_count !== undefined ? w.manuscript_count : "?";
      var tip = escapeHtml(w.word) + ': ' + w.total_count + 'x (' + escapeHtml(uiLabel("sources")) + ': ' + sc + 'x, ' + escapeHtml(uiLabel("workspace_analysis")) + ': ' + mc + 'x) · ' + escapeHtml(uiLabel("research_term_click_help"));
      return '<button type="button" class="grounding-chip" data-term-search="' + escapeHtml(w.word) + '" data-help="' + tip + '" title="' + escapeHtml(w.word) + '">' +
        '<span>' + escapeHtml(w.word) + '</span>' +
        '<span class="grounding-badge-count">' + w.total_count + '</span>' +
      '</button>';
    }).join("");

    var sourceKeyTerms = (gres.keyness && gres.keyness.source_key_terms) || [];
    var keyTermsHtml = sourceKeyTerms.slice(0, 25).map(function(k) {
      var sc = k.source_count !== undefined ? k.source_count : "?";
      var mc = k.manuscript_count !== undefined ? k.manuscript_count : "?";
      var tip = escapeHtml(k.word) + ' (Dunning-G² ' + k.g2 + '): ' + escapeHtml(uiLabel("sources")) + ' ' + sc + 'x vs ' + escapeHtml(uiLabel("workspace_analysis")) + ' ' + mc + 'x · ' + escapeHtml(uiLabel("research_term_click_help"));
      return '<button type="button" class="grounding-chip keyness" data-term-search="' + escapeHtml(k.word) + '" data-help="' + tip + '" title="' + escapeHtml(k.word) + '">' +
        '<span>' + escapeHtml(k.word) + '</span>' +
        '<span class="grounding-badge-count">G² ' + k.g2 + '</span>' +
      '</button>';
    }).join("");

    var topExclusive = (gres.lexical_overlap && gres.lexical_overlap.top_source_exclusive) || [];
    var exclusiveTermsHtml = topExclusive.slice(0, 25).map(function(e) {
      var tip = escapeHtml(e.word) + ': ' + e.count + 'x (' + escapeHtml(uiLabel("research_exclusive_terms")) + ')';
      return '<button type="button" class="grounding-chip exclusive" data-term-search="' + escapeHtml(e.word) + '" data-help="' + tip + '" title="' + escapeHtml(e.word) + '">' +
        '<span>' + escapeHtml(e.word) + '</span>' +
        '<span class="grounding-badge-count">' + e.count + '</span>' +
      '</button>';
    }).join("");

    var chapters = gres.chapter_grounding || [];
    var maxDensity = 1;
    chapters.forEach(function(c) {
      if (c.grounding_density > maxDensity) maxDensity = c.grounding_density;
    });

    var chRows = chapters.map(function(c) {
      var densityVal = c.grounding_density || 0;
      var densityPercent = Math.min(100, Math.round((densityVal / (maxDensity || 1)) * 100));
      var topTermsList = (c.top_terms || []).slice(0, 3).map(function(t) {
        return '<span class="grounding-top-term-badge" data-term-search="' + escapeHtml(t.word) + '" title="' + escapeHtml(uiLabel("research_term_click_help")) + '">' + escapeHtml(t.word) + ' (' + t.count + ')</span>';
      }).join(" ");

      return '<tr class="clickable-row" data-jump-chapter="' + c.chapter + '">' +
        '<td data-sort-value="' + c.chapter + '"><strong>' + escapeHtml(uiLabel("research_chapter_prefix")) + ' ' + c.chapter + '</strong> <span class="muted-note">(' + escapeHtml(c.title || "") + ')</span></td>' +
        '<td class="num-right" data-sort-value="' + (c.words || 0) + '">' + (c.words || 0).toLocaleString() + '</td>' +
        '<td class="num-right" data-sort-value="' + (c.overlap_tokens || 0) + '">' + (c.overlap_tokens || 0).toLocaleString() + '</td>' +
        '<td class="num-right" data-sort-value="' + densityVal.toFixed(2) + '">' +
          '<div class="table-bar-cell">' +
            '<div class="table-bar-track"><div class="table-bar-fill" style="width:' + densityPercent + '%;"></div></div>' +
            '<span class="table-bar-val">' + densityVal.toFixed(1) + '‰</span>' +
          '</div>' +
        '</td>' +
        '<td>' + (topTermsList || '<span class="muted-note">–</span>') + '</td>' +
        '<td class="num-right">' +
          '<button type="button" class="ctl grounding-jump-btn" data-jump-chapter="' + c.chapter + '" title="' + escapeHtml(uiLabel("research_jump_chapter")) + '" data-help="' + escapeHtml(uiLabel("research_jump_chapter")) + '">↗ ' + escapeHtml(uiLabel("open")) + '</button>' +
        '</td>' +
      '</tr>';
    }).join("");

    var reg = gres.register_contrast;
    var registerContrastHtml = "";
    if (reg) {
      registerContrastHtml = '<details class="research-accordion mt-3" id="grounding-register-details">' +
        '<summary data-help="' + escapeHtml(uiLabel("research_register_contrast_help")) + '">' + escapeHtml(uiLabel("research_register_contrast")) + '</summary>' +
        '<div class="table-wrap mt-2"><table class="research-table">' +
          '<thead><tr><th>' + escapeHtml(uiLabel("research_ground_metric")) + '</th><th class="num-right">' + escapeHtml(uiLabel("research_ground_source")) + '</th><th class="num-right">' + escapeHtml(uiLabel("research_ground_manuscript")) + '</th><th class="num-right">' + escapeHtml(uiLabel("research_ground_delta")) + '</th></tr></thead>' +
          '<tbody>' +
            (function() {
              function diffCell(obj, isPct) {
                if (!obj || obj.delta === undefined || obj.delta === null) return '–';
                var d = obj.delta;
                var cls = d > 0 ? 'delta-positive' : (d < 0 ? 'delta-negative' : '');
                var formatted = isPct ? ((d > 0 ? '+' : '') + (d * 100).toFixed(1) + '%') : ((d > 0 ? '+' : '') + d);
                return '<strong class="' + cls + '">' + formatted + '</strong>';
              }
              return '<tr><td>' + escapeHtml(uiLabel("research_ground_asl")) + '</td><td class="num-right">' + (reg.asl ? reg.asl.source : '–') + '</td><td class="num-right">' + (reg.asl ? reg.asl.manuscript : '–') + '</td><td class="num-right">' + diffCell(reg.asl, false) + '</td></tr>' +
                '<tr><td>' + escapeHtml(uiLabel("research_ground_dialogue")) + '</td><td class="num-right">' + (reg.dialogue_pct ? (reg.dialogue_pct.source * 100).toFixed(1) + '%' : '–') + '</td><td class="num-right">' + (reg.dialogue_pct ? (reg.dialogue_pct.manuscript * 100).toFixed(1) + '%' : '–') + '</td><td class="num-right">' + diffCell(reg.dialogue_pct, true) + '</td></tr>' +
                '<tr><td>' + escapeHtml(uiLabel("research_ground_guiraud")) + '</td><td class="num-right">' + (reg.guiraud_r ? reg.guiraud_r.source : '–') + '</td><td class="num-right">' + (reg.guiraud_r ? reg.guiraud_r.manuscript : '–') + '</td><td class="num-right">' + diffCell(reg.guiraud_r, false) + '</td></tr>' +
                '<tr><td>' + escapeHtml(uiLabel("research_ground_yules_k")) + '</td><td class="num-right">' + (reg.yules_k ? reg.yules_k.source : '–') + '</td><td class="num-right">' + (reg.yules_k ? reg.yules_k.manuscript : '–') + '</td><td class="num-right">' + diffCell(reg.yules_k, false) + '</td></tr>';
            })() +
          '</tbody>' +
        '</table></div>' +
      '</details>';
    }

    if (gHost) {
      var prov = gres.provenance || {};
      var srcTitle = prov.source_title || "";
      var langLabel = (comparisonMeta.source_language || "") + ' ↔ ' + (comparisonMeta.manuscript_language || "");

      gHost.innerHTML = '<div class="research-card mt-3">' +
        '<div class="grounding-header-bar">' +
          '<div class="research-card-title">' + escapeHtml(uiLabel("research_results_for")) + ' <strong>' + escapeHtml(srcTitle) + '</strong></div>' +
          '<div class="grounding-meta-chips">' +
            '<span class="badge ' + (crossLanguage ? 'badge-warn' : 'badge-neutral') + '" title="' + escapeHtml(uiLabel("status_freshness") || "") + '">' + escapeHtml(langLabel) + '</span>' +
          '</div>' +
        '</div>' +
        (crossLanguage ? '<p class="ctl-note research-comparison-warning" role="status">' + escapeHtml(uiLabel("research_cross_language_limit")) + '</p>' : '') +

        '<div class="grounding-term-toolbar">' +
          '<div class="ctl-label">' + escapeHtml(uiLabel("research_top_terms_col")) + '</div>' +
          '<div class="grounding-term-tabs" role="tablist">' +
            '<button type="button" class="grounding-tab-btn active" data-ground-tab="shared" role="tab" aria-selected="true">' + escapeHtml(uiLabel("research_shared_words")) + ' (' + topShared.length + ')</button>' +
            '<button type="button" class="grounding-tab-btn" data-ground-tab="keyness" role="tab" aria-selected="false">' + escapeHtml(uiLabel("research_source_key_terms")) + ' (' + sourceKeyTerms.length + ')</button>' +
            '<button type="button" class="grounding-tab-btn" data-ground-tab="exclusive" role="tab" aria-selected="false">' + escapeHtml(uiLabel("research_exclusive_terms")) + ' (' + topExclusive.length + ')</button>' +
          '</div>' +
        '</div>' +

        '<div class="grounding-term-panel" id="ground-terms-shared">' +
          '<div class="grounding-chips">' + (sharedChipsHtml || '<span class="muted-note">–</span>') + '</div>' +
        '</div>' +
        '<div class="grounding-term-panel" id="ground-terms-keyness" hidden>' +
          '<div class="grounding-chips">' + (keyTermsHtml || '<span class="muted-note">–</span>') + '</div>' +
        '</div>' +
        '<div class="grounding-term-panel" id="ground-terms-exclusive" hidden>' +
          '<div class="grounding-chips">' + (exclusiveTermsHtml || '<span class="muted-note">–</span>') + '</div>' +
        '</div>' +

        (chRows ? '<div class="mt-4">' +
          '<div class="ctl-label mb-2">' + escapeHtml(uiLabel("research_chapter_density")) + '</div>' +
          '<div class="table-wrap"><table class="research-chapter-table" data-sortable="true">' +
            '<thead><tr>' +
              '<th class="sortable" data-sort="chapter" tabindex="0" role="columnheader" aria-sort="ascending" data-help="' + escapeHtml(uiLabel("table_sort_help")) + '" aria-keyshortcuts="Enter">' + escapeHtml(uiLabel("research_chapter")) + '</th>' +
              '<th class="sortable num-right" data-sort="words" tabindex="0" role="columnheader" data-help="' + escapeHtml(uiLabel("table_sort_help")) + '" aria-keyshortcuts="Enter">' + escapeHtml(uiLabel("research_ground_words")) + '</th>' +
              '<th class="sortable num-right" data-sort="tokens" tabindex="0" role="columnheader" data-help="' + escapeHtml(uiLabel("table_sort_help")) + '" aria-keyshortcuts="Enter">' + escapeHtml(uiLabel("research_tokens")) + '</th>' +
              '<th class="sortable num-right" data-sort="density" tabindex="0" role="columnheader" data-help="' + escapeHtml(uiLabel("table_sort_help")) + '" aria-keyshortcuts="Enter">' + escapeHtml(uiLabel("research_density")) + '</th>' +
              '<th>' + escapeHtml(uiLabel("research_top_terms_col")) + '</th>' +
              '<th class="num-right">' + escapeHtml(uiLabel("action")) + '</th>' +
            '</tr></thead>' +
            '<tbody>' + chRows + '</tbody>' +
          '</table></div>' +
        '</div>' : '') +

        '<details class="research-details mt-3"><summary>' + escapeHtml(uiLabel("research_source_compare_details")) + '</summary>' +
        '<p class="ctl-note" data-comparison-version>' + escapeHtml(uiLabel("research_source_compare_current")) + ': ' + escapeHtml(prov.source_id) + ' · ' + escapeHtml(prov.source_version_id) + '</p>' +
        '<p class="ctl-note">' + escapeHtml(uiLabel("research_source_compare_parsing")) + '</p>' +
        '<p class="ctl-note">' + escapeHtml(uiLabel("research_source_key_terms")) + ': Dunning G²</p>' +
        (incomplete ? '<p class="ctl-note" role="status">' + escapeHtml(uiLabel("research_status_unavailable")) + '</p>' : '') +
        '<div class="grounding-kpis">' +
          '<div class="grounding-kpi-card" data-help="' + escapeHtml(uiLabel("research_jaccard_help")) + '" title="' + escapeHtml(uiLabel("research_similarity")) + '">' +
            '<div class="grounding-kpi-label"><span>' + escapeHtml(uiLabel("research_similarity")) + '</span><span>ℹ</span></div>' +
            '<div class="grounding-kpi-val">' + jaccardPct + '</div>' +
            '<div class="grounding-mini-bar-track"><div class="grounding-mini-bar-fill" style="width:' + (measured(jaccardVal) ? Math.min(100, Math.round(jaccardVal * 500)) : 0) + '%;"></div></div>' +
          '</div>' +
          '<div class="grounding-kpi-card" data-help="' + escapeHtml(uiLabel("research_overlap_help")) + '" title="' + escapeHtml(uiLabel("research_overlap_coefficient")) + '">' +
            '<div class="grounding-kpi-label"><span>' + escapeHtml(uiLabel("research_overlap_coefficient")) + '</span><span>ℹ</span></div>' +
            '<div class="grounding-kpi-val">' + overlapPct + '</div>' +
            '<div class="grounding-mini-bar-track"><div class="grounding-mini-bar-fill" style="width:' + (measured(overlapVal) ? Math.min(100, Math.round(overlapVal * 100)) : 0) + '%;"></div></div>' +
          '</div>' +
          '<div class="grounding-kpi-card" data-help="' + escapeHtml(uiLabel("research_shared_types_help")) + '" title="' + escapeHtml(uiLabel("research_shared_types")) + '">' +
            '<div class="grounding-kpi-label"><span>' + escapeHtml(uiLabel("research_shared_types")) + '</span><span>ℹ</span></div>' +
            '<div class="grounding-kpi-val">' + count(sum.shared_types) + '</div>' +
          '</div>' +
          '<div class="grounding-kpi-card" data-help="' + escapeHtml(uiLabel("research_word_counts_help")) + '" title="' + escapeHtml(uiLabel("research_word_counts")) + '">' +
            '<div class="grounding-kpi-label"><span>' + escapeHtml(uiLabel("research_word_counts")) + '</span><span>ℹ</span></div>' +
            '<div class="grounding-kpi-val">' + count(sum.source_content_words) + ' <span class="grounding-subval">/ ' + count(sum.manuscript_content_words) + '</span></div>' +
          '</div>' +
        '</div>' +

        registerContrastHtml + '</details>' +
      '</div>';
    }
  }
  var hitOrigin = null;
  function readHit(button) {
    var passage = researchPassageContexts[button.dataset.researchSearchPassage];
    if (!passage) return;
    hitOrigin = capture(button);
    searchReader.innerHTML = '<button type="button" class="ctl" id="research-search-return">' + escapeHtml(uiLabel("research_tools_return_search")) + '</button>' +
      researchCitationHtml(Object.assign({availability: "available"}, passage)) +
      '<p class="ctl-note">' + escapeHtml(uiLabel("research_search_source_version")) + '</p>' +
      '<details class="research-details"><summary>' + escapeHtml(uiLabel("research_tools_search_details")) + '</summary><p>' + escapeHtml(passage.source_version_id || "") + '</p></details>' +
      (passage.source_id ? '<details class="research-details"><summary data-research-detail="source" data-record-id="' + attr(passage.source_id) + '">' +
        escapeHtml(uiLabel("research_search_read_current_source")) + '</summary><div class="research-details-body"></div></details>' : '');
    document.getElementById("research-search-results").hidden = true;
    searchReader.hidden = false; searchReader.querySelector("button").focus({preventScroll: true});
  }
  function returnSearch() {
    searchReader.hidden = true;
    document.getElementById("research-search-results").hidden = false;
    restoreOrigin(hitOrigin);
  }
  function applyReviewFilter() {
    document.querySelectorAll("#research-editorial-review > .research-card").forEach(function(card) {
      var decisionId = card.dataset.reviewCandidateDecision;
      var dossierId = card.dataset.reviewCandidateDossier;
      card.hidden = Boolean(reviewFilter && ((reviewFilter.dossierId && reviewFilter.dossierId !== dossierId) ||
        (reviewFilter.decisionId && reviewFilter.decisionId !== decisionId)));
      if (reviewFilter && !card.hidden && card.tagName === "DETAILS") card.open = true;
    });
  }
  new MutationObserver(applyReviewFilter).observe(document.getElementById("research-editorial-review"), {childList: true});
  document.addEventListener("click", function(event) {
    var action = event.target.closest("[data-research-source-compare]");
    if (action) { openComparison(action); return; }
    if (event.target.closest("#r-ground-btn")) { compare(); return; }
    if (event.target.closest("#research-tool-close")) { close(); return; }
    if (event.target.closest("#research-search-return")) { returnSearch(); return; }
    var hit = event.target.closest("[data-research-search-passage]");
    if (hit) { readHit(hit); return; }
    if (event.target.closest("#research-source-add")) {
      var add = document.getElementById("r-local-import"); add.open = true;
      document.getElementById("r-ingest-file").focus(); return;
    }
    var reviewAction = event.target.closest("[data-research-review-dossier], [data-research-review-decision]");
    if (reviewAction) {
      open("review", reviewAction, {filter: {dossierId: reviewAction.dataset.researchReviewDossier,
        decisionId: reviewAction.dataset.researchReviewDecision}}); return;
    }
    var reviewAll = event.target.closest("#research-review-all");
    if (reviewAll) {
      open("review", reviewAll);
      return;
    }
    var termsTrigger = event.target.closest("#research-reader-terms");
    if (termsTrigger) {
      open("review", termsTrigger);
      var terms = document.getElementById("research-manuscript-terms-section");
      terms.open = true; terms.scrollIntoView({block: "start"});
    }
  });
  document.addEventListener("click", function(event) {
    var button = event.target.closest("[data-term-search], [data-jump-chapter]");
    if (!button || active !== "grounding" || !host.contains(button) || !comparison || !window.LixityReadingThread) return;
    var value = comparison, departure = capture(button);
    window.LixityReadingThread.rememberPassage({description: title.textContent,
      valid: function() { return comparison === value && value.context === context() && value.current(); },
      restore: function() { switchActiveView("research"); paint(); restoreOrigin(departure); }});
  }, true);
  document.addEventListener("keydown", function(event) {
    if (event.key !== "Escape" || !active || event.defaultPrevented || event.target.closest("dialog[open]")) return;
    if (!host.contains(event.target) && !event.target.closest("#research-tools-entry")) return;
    event.preventDefault(); close();
  });
  var contextObserver = new MutationObserver(function() {
    if (!manager.isConnected || !host.isConnected) {
      contextObserver.disconnect(); ++serial;
      active = ""; origin = comparison = comparisonReturn = null;
      return;
    }
    if (acceptedContext !== context()) reset();
    else if (comparison && !comparisonOwnerCurrent(comparison)) invalidateComparison(comparison);
  });
  contextObserver.observe(document.body, {subtree: true, childList: true, attributes: true,
    attributeFilter: ["open", "data-research-token", "data-project-token", "data-manuscript-project-token", "data-manuscript-source-sha256"]});
  window.LixityResearchTools = {open: open, close: close, reset: reset, context: context, sourceAction: sourceAction,
    showResults: function() { searchReader.hidden = true; document.getElementById("research-search-results").hidden = false; },
    active: function() { return active; }, restore: paint,
    sourceChanged: function(id, version) { if (comparison && (comparison.detail.id !== id || comparison.detail.version_id !== version)) close(false); }
  };
  document.addEventListener("lixity:dossier-image-saved", function() {
    if (active !== "review") return;
    if (panes.review.contains(document.activeElement)) title.focus();
    refreshResearchEditorialReview();
  });
  paint();
})();
