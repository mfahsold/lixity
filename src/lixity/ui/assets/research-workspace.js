// Research workspace: project info, initialization and delegated interactions.
// Split of the former research.js; _JS_FILES concatenates the parts in
// the original order, so load-time behaviour is unchanged.
function ocrReading(ocr) {
  ocr = ocr || {};
    var ocrStatus = ocr.status === "ready (probed)" ? "ready" : ocr.status;
    var badgeClass = ocrStatus === "ready" ? "ok" : (ocrStatus === "native_only" ? "note" : "err");
    var ocrLabels = {
      ready: ocr.backend === "tesseract" ? ["research_ocr_tesseract_ready", "research_ocr_tesseract_ready_help"] : ["research_ocr_ready", "research_ocr_ready_help"],
      native_only: ["research_ocr_native", "research_ocr_native_help"],
      partial: ["research_ocr_partial", "research_ocr_partial_help"],
      misconfigured_worker: ["research_ocr_worker_error", "research_ocr_worker_error_help"],
      misconfigured_backend: ["research_ocr_tesseract_error", "research_ocr_tesseract_error_help"],
      missing_dependencies: ["research_ocr_missing", "research_ocr_missing_help"]
    };
    var ocrKeys = Object.prototype.hasOwnProperty.call(ocrLabels, ocrStatus)
      ? ocrLabels[ocrStatus] : ["research_ocr_unknown", "research_ocr_unknown_help"];
    var labelText = uiLabel(ocrKeys[0]);
    var guidanceText = uiLabel(ocrKeys[1]);
    if (ocr.requested_languages && ocr.requested_languages.length) {
      guidanceText += " " + uiFormat("research_ocr_languages", {languages: ocr.requested_languages.join(" + ")});
    }
    if (ocr.missing_languages && ocr.missing_languages.length) {
      guidanceText += " " + uiFormat("research_ocr_missing_languages", {languages: ocr.missing_languages.join(" + ")});
    }
  return {label: labelText, guidance: guidanceText, badge: badgeClass};
}

async function refreshResearchProjectInfo() {
  var statusRead = ++researchProjectStatusRead;
  var activeRootEl = document.getElementById("r-active-root");
  if (activeRootEl && (!activeRootEl.textContent || activeRootEl.textContent.trim() === "")) {
    activeRootEl.className = "ctl-status loading";
    activeRootEl.textContent = uiLabel("research_loading");
  }
  var status = await researchApiGet("research/status");
  if (statusRead !== researchProjectStatusRead) return {ok: false, superseded: true};
  if (status.ok === true && researchSelectionProjectId !== (status.project_id || null)) {
    ++researchSearchRead; ++researchClaimsRead; ++researchProjectionRead;
    researchClaimsSnapshot = null; researchClaimChoices = Object.create(null);
    clearResearchSourceSelections(); discardResearchEvidenceDraft();
    researchPassageContexts = Object.create(null);
    researchSelectionProjectId = status.project_id || null;
  }
  if (zoteroProjectId !== (status.project_id || null)) {
    clearZoteroSelection();
    zoteroProjectId = status.project_id || null;
  }
  if (activeRootEl && status && status.ok && status.project_root) {
    var rootPath = String(status.project_root);
    var rootName = rootPath.split(/[\\/]/).filter(Boolean).pop() || rootPath;
    activeRootEl.className = "ctl-note";
    activeRootEl.title = rootPath;
    activeRootEl.textContent = uiLabel("research_project") + " " + rootName;
    if (status.initialized) {
      activeRootEl.textContent = uiFormat("research_project_summary", {
        root: rootName,
        sources: status.sources_count || 0,
        dossiers: status.dossiers_count || 0,
        claims: status.claims_count || 0,
        decisions: status.decisions_count || 0
      });
    }
  } else if (activeRootEl && status && !status.ok) {
    activeRootEl.className = "ctl-status err";
    activeRootEl.textContent = status.message || uiLabel("research_status_unavailable");
  }
  var ocrBox = document.getElementById("r-ocr-diagnostic-box");
  if (ocrBox && status && status.ocr) {
    var reading = ocrReading(status.ocr);
    var badgeClass = reading.badge;
    var labelText = reading.label;
    var guidanceText = reading.guidance;
    ocrBox.style.display = "flex";
    ocrBox.style.alignItems = "center";
    ocrBox.innerHTML = '<span class="badge ' + badgeClass + ' badge-sm">' +
      escapeHtml(labelText) + '</span>' +
      (guidanceText ? '<small class="ctl-note ml-2 text-note">' + escapeHtml(guidanceText) + '</small>' : '');
  }
  return status;
}

(function initResearchSetup() {
  var button = document.getElementById("research-setup-check");
  if (!button) return;
  var ocrText = document.getElementById("setup-ocr-reading");
  var zoteroText = document.getElementById("setup-zotero-reading");
  var diagnostics = document.getElementById("setup-diagnostics");
  async function metadata(path) {
    try {
      var response = await fetch(API + "/research/" + path);
      if (!response.ok) return {ok: false};
      return await response.json();
    } catch (_) { return {ok: false}; }
  }
  button.addEventListener("click", async function() {
    if (button.disabled) return;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    ocrText.textContent = "OCR: " + uiLabel("research_loading");
    zoteroText.textContent = "Zotero: " + uiLabel("research_loading");
    try {
      var results = await Promise.all([metadata("ocr-status"), metadata("zotero-status")]);
      var ocr = results[0];
      var zotero = results[1];
      var reading = ocrReading(ocr.ok ? ocr : null);
      ocrText.textContent = "OCR: " + reading.label + " " + reading.guidance;
      var zoteroReady = zotero.ok && (zotero.status === "ready" || zotero.status === "connected");
      var key = zotero.ok && zotero.status === "ready" ? "setup_zotero_ready"
        : zotero.ok && zotero.status === "connected" ? "setup_zotero_connected" : "setup_zotero_unavailable";
      zoteroText.textContent = uiLabel(key) + " " + uiLabel("setup_library_unchecked");
      // Hide the instructions for whatever this check just found working;
      // showing them beside a success message reads as a contradiction.
      var steps = document.getElementById("setup-zotero-steps");
      if (steps) steps.hidden = zoteroReady;
      var ocrSteps = document.getElementById("setup-ocr-steps");
      if (ocrSteps) {
        var ocrReady = ocr.ok && (ocr.status === "ready" || ocr.tesseract_available === true
          || ocr.worker_configured === true);
        ocrSteps.hidden = ocrReady;
      }
      var safeOcr = {};
      ["status", "backend", "pdftotext_available", "pdftoppm_available", "tesseract_available",
       "requested_languages", "available_languages", "missing_languages"].forEach(function(field) {
        if (Object.prototype.hasOwnProperty.call(ocr, field)) safeOcr[field] = ocr[field];
      });
      diagnostics.textContent = JSON.stringify({ocr: safeOcr, zotero: zotero}, null, 2);
    } finally {
      button.disabled = false;
      button.setAttribute("aria-busy", "false");
    }
  });
})();

async function initResearchUI(freshRead) {
  researchStatus(uiLabel("research_loading"), "loading");
  var status = await refreshResearchProjectInfo();
  if (status.superseded) return;
  var initBox = document.getElementById("research-init-box");
  var tabs = document.getElementById("research-tabs");
  document.querySelectorAll(".research-tab-pane").forEach(function(p) { p.style.display = "none"; });

  if (!status || status.ok !== true) {
    if (initBox) initBox.style.display = "none";
    if (tabs) tabs.style.display = "none";
    researchStatus(uiFormat("research_api_unavailable", { reason: (status && status.message) || uiLabel("research_no_response") }), false);
    return;
  }

  if (!status.initialized) {
    if (initBox) initBox.style.display = "block";
    if (tabs) tabs.style.display = "none";
    document.querySelectorAll(".research-tab-pane").forEach(function(p) { p.style.display = "none"; });
    researchStatus("", true);
    return;
  }
  if (initBox) initBox.style.display = "none";
  if (tabs) tabs.style.display = "flex";
  var activeTab = document.querySelector(".research-tabs button.active");
  var targetPane = activeTab ? "rtab-" + activeTab.dataset.rtab : "rtab-dossiers";
  document.querySelectorAll(".research-tab-pane").forEach(function(p) {
    p.style.display = p.id === targetPane ? "block" : "none";
  });
  researchStatus("", true);
  refreshResearchSources(status, null, freshRead);
  refreshResearchDossiers(status, null, freshRead);
  refreshResearchClaims(status);
  refreshResearchDecisions(status);
  if (activeTab && activeTab.dataset.rtab === "review") refreshResearchEditorialReview();
}

// Retain the shared manual keyboard tabs while making hidden destinations
// discoverable on narrow screens. Moving the scrollport never selects a view.
(function initResearchNavigation() {
  var tabs = document.getElementById("research-tabs");
  var previous = document.getElementById("research-navigation-previous");
  var next = document.getElementById("research-navigation-next");
  if (!tabs || !previous || !next) return;
  function update() {
    var overflow = tabs.getClientRects().length && tabs.scrollWidth > tabs.clientWidth + 1;
    previous.hidden = next.hidden = !overflow;
    previous.disabled = tabs.scrollLeft <= 1;
    next.disabled = tabs.scrollLeft + tabs.clientWidth >= tabs.scrollWidth - 1;
  }
  previous.addEventListener("click", function() { tabs.scrollBy({left: -tabs.clientWidth * .75}); update(); });
  next.addEventListener("click", function() { tabs.scrollBy({left: tabs.clientWidth * .75}); update(); });
  tabs.addEventListener("scroll", update, {passive: true});
  function reveal(event) {
    var tab = event.target.closest("[data-rtab]");
    if (tab) tab.scrollIntoView({block: "nearest", inline: "nearest"});
    update();
  }
  tabs.addEventListener("focusin", reveal);
  tabs.addEventListener("click", reveal);
  window.addEventListener("resize", update);
  if (typeof ResizeObserver === "function") new ResizeObserver(update).observe(tabs);
  update();
})();

// Display an existing tab without reading or replacing its draft/detail DOM.
// Ordinary tab actions below still refresh their records explicitly.
function showResearchTab(tabBtn) {
  if (!tabBtn) return;
  document.querySelectorAll(".research-tabs button").forEach(function(button) {
    var active = button === tabBtn;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
    button.tabIndex = active ? 0 : -1;
  });
  var targetId = "rtab-" + tabBtn.dataset.rtab;
  document.querySelectorAll(".research-tab-pane").forEach(function(pane) {
    pane.style.display = pane.id === targetId ? "block" : "none";
  });
}

document.addEventListener("click", async function (event) {
  var comparisonClose = event.target.closest("[data-decision-review-close]");
  if (comparisonClose) {
    collapseDisclosure(comparisonClose.closest("[data-decision-review]"));
    return;
  }
  var comparisonRetry = event.target.closest("[data-decision-review-retry]");
  if (comparisonRetry) {
    loadResearchDecisionComparison(comparisonRetry.closest("[data-decision-review]"));
    return;
  }
  var ackButton = event.target.closest("[data-decision-ack-status]");
  if (ackButton) {
    var pair = ackButton.closest(".research-decision-acknowledgement");
    if (!pair || ackButton.disabled || researchAcknowledgementPending || pair.dataset.decisionAckPending === "1") return;
    var payload = {decision_id: pair.dataset.decisionAckDecision, dossier_id: pair.dataset.decisionAckDossier,
      expected_snapshot: pair.dataset.decisionAckSnapshot,
      expected_decision_revision: Number(pair.dataset.decisionAckDecisionRevision),
      expected_dossier_revision: Number(pair.dataset.decisionAckDossierRevision), status: ackButton.dataset.decisionAckStatus};
    var feedback = pair.querySelector("[data-decision-ack-feedback]");
    var acknowledgementContext = {projectId: pair.dataset.decisionAckProject || null, token: pair.dataset.decisionAckToken};
    if (!acceptResearchContext(acknowledgementContext, {})) {
      feedback.textContent = uiLabel("research_decision_ack_conflict");
      feedback.className = "ctl-status err";
      feedback.hidden = false;
      return;
    }
    var restoreFocus = document.activeElement === ackButton;
    var updatedPair;
    function movedFocus(event) {
      if (event.target !== ackButton && (!updatedPair || !updatedPair.contains(event.target))) restoreFocus = false;
    }
    function movedPointer(event) {
      if (!pair.contains(event.target) && (!updatedPair || !updatedPair.contains(event.target))) restoreFocus = false;
    }
    function stopTrackingFocus() {
      document.removeEventListener("focusin", movedFocus);
      document.removeEventListener("pointerdown", movedPointer);
    }
    document.addEventListener("focusin", movedFocus);
    document.addEventListener("pointerdown", movedPointer);
    researchAcknowledgementPending = true;
    pair.dataset.decisionAckPending = "1";
    ackButton.disabled = true;
    ackButton.setAttribute("aria-busy", "true");
    feedback.hidden = true;
    var acknowledged = await researchApiPost("research-decision-acknowledge", payload);
    if (!pair.isConnected || !acceptResearchContext(acknowledgementContext, acknowledged)) {
      researchAcknowledgementPending = false;
      delete pair.dataset.decisionAckPending;
      ackButton.disabled = false;
      ackButton.removeAttribute("aria-busy");
      stopTrackingFocus();
      return;
    }
    delete pair.dataset.decisionAckPending;
    if (!acknowledged.ok) {
      ackButton.disabled = false;
      ackButton.removeAttribute("aria-busy");
      feedback.className = "ctl-status err";
      feedback.textContent = acknowledged.http_status === 409 ? uiLabel("research_decision_ack_conflict") :
        uiFormat("research_decision_ack_failed", {reason: acknowledged.message || uiLabel("wizard_unknown_error")});
      feedback.hidden = false;
      researchAcknowledgementPending = false;
      if (restoreFocus && (document.activeElement === ackButton || document.activeElement === document.body)) ackButton.focus();
      stopTrackingFocus();
      return;
    }
    var replacement = document.createElement("div");
    replacement.innerHTML = researchDecisionAcknowledgement({decisionId: payload.decision_id,
      decisionRevision: payload.expected_decision_revision, dossierId: payload.dossier_id,
      dossierRevision: payload.expected_dossier_revision, snapshot: acknowledged.snapshot,
      acknowledgement: {current: true, status: acknowledged.status}});
    advanceResearchDecisionComparisons(payload, acknowledged);
    document.querySelectorAll(".research-decision-acknowledgement").forEach(function(displayed) {
      if (displayed.dataset.decisionAckSnapshot !== payload.expected_snapshot) return;
      displayed.dataset.decisionAckSnapshot = acknowledged.snapshot;
      if (displayed.dataset.decisionAckDecision === payload.decision_id && displayed.dataset.decisionAckDossier === payload.dossier_id &&
          Number(displayed.dataset.decisionAckDecisionRevision) === payload.expected_decision_revision &&
          Number(displayed.dataset.decisionAckDossierRevision) === payload.expected_dossier_revision) {
        acknowledgeEditorialFlags(displayed, acknowledged.status);
        var next = replacement.firstElementChild.cloneNode(true);
        displayed.replaceWith(next);
        if (displayed === pair) updatedPair = next;
      }
    });
    if (restoreFocus && updatedPair && document.activeElement === document.body) updatedPair.querySelector("button").focus();
    await refreshResearchEditorialReview(true, acknowledged.snapshot);
    researchAcknowledgementPending = false;
    if (restoreFocus && updatedPair && !updatedPair.isConnected && document.activeElement === document.body) {
      var nextButton = document.querySelector("#research-editorial-review [data-decision-ack-status]");
      (nextButton || document.getElementById("r-review-refresh")).focus();
    }
    stopTrackingFocus();
    return;
  }
  var impactButton = event.target.closest("[data-decision-impact]");
  if (impactButton) {
    if (impactButton.parentElement.open) return;
    var impactHost = impactButton.parentElement.querySelector(".research-details-body");
    var impactContext = researchReadContext();
    var impactRequest = impactHost._decisionImpactRequest = (impactHost._decisionImpactRequest || 0) + 1;
    impactHost.textContent = uiLabel("research_loading");
    var impact = await researchApiGet("research/decision-impact?id=" + encodeURIComponent(impactButton.dataset.decisionImpact));
    if (!impactHost.isConnected || impactRequest !== impactHost._decisionImpactRequest || !impactButton.parentElement.open) return;
    if (!acceptResearchContext(impactContext, impact)) {
      impactHost.textContent = uiLabel("research_decision_ack_conflict");
      return;
    }
    if (impact.ok && (impact.schema_version !== "research-decision-impact-local/1" || !impact.snapshot ||
        !impact.decision || impact.decision.id !== impactButton.dataset.decisionImpact || !Array.isArray(impact.dossiers))) {
      impactHost.textContent = uiLabel("research_status_unavailable");
      return;
    }
    impactHost.innerHTML = impact.ok ?
      '<p class="ctl-note">' + escapeHtml(uiLabel("research_editorial_decision_date")) + ': ' + researchEditorialTime(impact.decision.created_at) + '</p>' +
      (impact.unlinked ? '<p>' + escapeHtml(uiLabel("research_editorial_no_linked_dossier")) + '</p>' : impact.dossiers.map(function(dossier) {
        return researchAffectedDossier(dossier, impact);
      }).join("")) :
      '<p>' + escapeHtml(impact.message || uiLabel("research_status_unavailable")) + '</p>';
    return;
  }
  if (event.target.closest("#r-review-refresh")) {
    refreshResearchEditorialReview();
    return;
  }
  var globalRecords = event.target.closest("[data-research-global]");
  if (globalRecords) {
    var globalTab = document.querySelector('.research-tabs [data-rtab="' + globalRecords.dataset.researchGlobal + '"]');
    if (globalTab) {
      switchActiveView("research");
      globalTab.click(); globalTab.focus();
    }
    return;
  }
  var contextualClaim = event.target.closest("[data-dossier-claim]");
  var contextualDecision = event.target.closest("[data-dossier-decision]");
  if (contextualClaim || contextualDecision) {
    var forContextClaim = Boolean(contextualClaim);
    var contextSelect = document.getElementById(forContextClaim ? "r-claim-dossier-select" : "r-decision-dossier-select");
    contextSelect.value = forContextClaim ? contextualClaim.dataset.dossierClaim : contextualDecision.dataset.dossierDecision;
    document.querySelector('[data-rtab="' + (forContextClaim ? "claims" : "decisions") + '"]').click();
    document.getElementById(forContextClaim ? "r-claim-options" : "r-decision-options").open = true;
    var contextTitle = document.getElementById(forContextClaim ? "r-claim-title" : "r-decision-title");
    revealDisclosures(contextTitle);
    contextTitle.focus();
    return;
  }
  var passageBtn = event.target.closest("[data-use-passage]");
  if (passageBtn) {
    var forClaim = passageBtn.dataset.usePassage === "claim";
    var passageField = document.getElementById(forClaim ? "r-link-passage-id" : "r-dos-eids");
    if (!passageField) return;
    if (forClaim) {
      var passageContext = researchPassageContexts[passageBtn.dataset.passageId];
      if (passageContext) {
        prepareResearchEvidenceDraft(passageBtn.dataset.passageId, "", passageContext);
        return;
      }
      passageField.value = passageBtn.dataset.passageId;
    } else {
      var passageIds = passageField.value.split(",").map(function(id) { return id.trim(); }).filter(Boolean);
      if (!passageIds.includes(passageBtn.dataset.passageId)) passageIds.push(passageBtn.dataset.passageId);
      passageField.value = passageIds.join(", ");
    }
    switchActiveView("research");
    document.querySelector('[data-rtab="' + (forClaim ? 'claims' : 'dossiers') + '"]').click();
    revealDisclosures(passageField);
    passageField.focus();
    return;
  }

  var detailsBtn = event.target.closest("[data-research-detail]");
  if (detailsBtn) {
    var detailHost = detailsBtn.parentElement.querySelector(".research-details-body");
    if (detailsBtn.parentElement.open) return;
    detailHost.textContent = uiLabel("research_details_loading");
    var isSource = detailsBtn.dataset.researchDetail === "source";
    var sourceSelectionProject = researchSelectionProjectId;
    var detailContext = researchReadContext();
    var detailRead = detailHost._detailRead = (detailHost._detailRead || 0) + 1;
    var sourceSelectionRead = isSource ? (detailHost._selectionRead = (detailHost._selectionRead || 0) + 1) : null;
    var detail = await researchApiGet("research/" + (isSource ? "sources" : "dossiers") + "?id=" + encodeURIComponent(detailsBtn.dataset.recordId));
    function detailCurrent() {
      return detailHost.isConnected && detailRead === detailHost._detailRead &&
        detailsBtn.parentElement.open && detailContext.token === researchContextToken() &&
        detailContext.projectId === researchSelectionProjectId;
    }
    if (!detailCurrent() || !acceptResearchContext(detailContext, detail)) return;
    if (detail.ok && detail.id !== detailsBtn.dataset.recordId) return;
    if (isSource && (!detailHost.isConnected || sourceSelectionProject !== researchSelectionProjectId ||
        sourceSelectionRead !== detailHost._selectionRead || !detailsBtn.parentElement.open)) return;
    if (!detail.ok) {
      detailHost.textContent = detail.message || uiLabel(isSource ? "research_load_sources_failed" : "research_load_dossiers_failed");
      return;
    }
    if (isSource) {
      clearResearchSourceSelections();
      var context = detail.context || {};
      var external = context.external_reference;
      var sourceReturn = external ? zoteroOpenLink(external.library, external.item_key) : "";
      var captureContext = '<p class="ctl-note">' + escapeHtml(uiLabel("research_captures_hint")) + '</p>' +
        (sourceReturn ? '<p>' + sourceReturn + '</p>' : '');
      var contextRows = ["genre", "created_period", "depicted_period", "place", "perspective", "original_language", "is_translation", "provenance_note", "origin_url"].filter(function(key) {
        return context[key] !== null && context[key] !== undefined && context[key] !== "";
      }).map(function(key) {
        var value = typeof context[key] === "boolean" ? uiLabel(context[key] ? "ctx_yes" : "ctx_no") : context[key];
        return '<dt>' + escapeHtml(uiLabel("ctx_" + key)) + '</dt><dd>' + escapeHtml(value) + '</dd>';
      }).join("");
      if (["image/png", "image/jpeg"].includes(detail.media_type)) {
        detailHost.innerHTML = captureContext + '<p class="ctl-note">' + escapeHtml(uiLabel("research_context_unverified")) + '</p>' +
          '<p><strong>' + escapeHtml(detail.media_type) + '</strong> · ' + escapeHtml(uiLabel("image_text_unavailable")) + '</p>' +
          (contextRows ? '<h4>' + escapeHtml(uiLabel("research_source_context")) + '</h4><dl>' + contextRows + '</dl>' : '');
        return;
      }
      var fullDocText = detail.text || (detail.passages || []).map(function(p) { return p.verbatim; }).join("\n\n");
      var docRendered = fullDocText ? renderSafeMarkdown(fullDocText) : '<p class="ctl-note">' + escapeHtml(uiLabel("research_no_records")) + '</p>';
      var passagesCount = detail.passages ? detail.passages.length : 0;
      var passagesHtml = (detail.passages || []).map(function(p) {
        return researchCitationHtml({availability: "available", passage_id: p.id, verbatim: p.verbatim, source_title: detail.title});
      }).join("");
      detailHost._selectionDetail = {projectId: sourceSelectionProject, title: detail.title,
        passages: (detail.passages || []).map(function(p) {return Object.assign({}, p, {plain: selectionPlainText(p.verbatim)});})};

      detailHost.innerHTML = captureContext + '<p class="ctl-note">' + escapeHtml(uiLabel("research_context_unverified")) + '</p>' +
        (contextRows ? '<h4>' + escapeHtml(uiLabel("research_source_context")) + '</h4><dl>' + contextRows + '</dl>' : '') +
        '<div class="research-source-view-bar">' +
          '<div class="row gap-2">' +
            '<button type="button" class="ctl ctl-sm active" data-source-view="doc">📄 ' + escapeHtml(uiLabel("research_doc_view")) + '</button>' +
            '<button type="button" class="ctl ctl-sm" data-source-view="passages">🔍 ' + escapeHtml(uiLabel("research_passages_view")) + ' (' + passagesCount + ')</button>' +
          '</div>' +
          '<button type="button" class="ctl ctl-sm research-source-toggle" data-source-toggle>' + escapeHtml(uiLabel("research_show_source")) + '</button>' +
        '</div>' +
        '<div class="selection-toolbar"><button type="button" class="ctl selection-use" disabled>' +
          escapeHtml(uiLabel("selection_use")) + '</button><p class="ctl-note selection-reading" role="status">' +
          escapeHtml(uiLabel("selection_hint")) + '</p></div>' +
        '<div class="research-source-doc-wrap">' +
          '<div class="research-prose markdown-body research-source-doc-rendered">' + docRendered + '</div>' +
          '<pre class="research-source-doc-raw" hidden>' + escapeHtml(fullDocText) + '</pre>' +
        '</div>' +
        '<div class="research-source-passages-wrap" hidden>' +
          '<h4>' + escapeHtml(uiLabel("research_passages")) + '</h4>' +
          passagesHtml +
        '</div>';
      // HTML parsing normalizes CRLF and an initial pre newline. Preserve the
      // retained text exactly so raw selections use the API's passage offsets.
      detailHost.querySelector(".research-source-doc-raw").textContent = fullDocText;
    } else {
      detailHost.innerHTML = researchDossierDetailHtml(detail);
      enhanceResearchDossierClaims(detailHost, detail, detailCurrent);
    }
    return;
  }

  var sourceToggleBtn = event.target.closest("[data-source-toggle]");
  if (sourceToggleBtn) {
    clearResearchSourceSelections();
    window.getSelection().removeAllRanges();
    var wrap = sourceToggleBtn.closest(".research-dossier-body-wrap");
    if (!wrap) wrap = sourceToggleBtn.parentElement.parentElement.querySelector(".research-source-doc-wrap");
    if (wrap) {
      var rendered = wrap.querySelector(".research-dossier-body-rendered, .research-source-doc-rendered");
      var source = wrap.querySelector(".research-dossier-body-source, .research-source-doc-raw");
      if (rendered && source) {
        var isSource = !source.hidden;
        source.hidden = isSource;
        rendered.hidden = !isSource;
        sourceToggleBtn.textContent = uiLabel(isSource ? "research_show_source" : "research_show_preview");
      }
    }
    return;
  }

  var sourceViewBtn = event.target.closest("[data-source-view]");
  if (sourceViewBtn) {
    clearResearchSourceSelections();
    window.getSelection().removeAllRanges();
    var bar = sourceViewBtn.closest(".research-source-view-bar");
    if (bar) {
      var host = bar.parentElement;
      var docWrap = host.querySelector(".research-source-doc-wrap");
      var passWrap = host.querySelector(".research-source-passages-wrap");
      var toggleRawBtn = bar.querySelector("[data-source-toggle]");
      bar.querySelectorAll("[data-source-view]").forEach(function(b) { b.classList.remove("active"); });
      sourceViewBtn.classList.add("active");
      var isDoc = sourceViewBtn.dataset.sourceView === "doc";
      if (docWrap) docWrap.hidden = !isDoc;
      if (passWrap) passWrap.hidden = isDoc;
      if (toggleRawBtn) toggleRawBtn.style.display = isDoc ? "inline-block" : "none";
    }
    return;
  }

  var viewBtn = event.target.closest("[data-claim-view]");
  if (viewBtn) {
    document.querySelectorAll("[data-claim-view]").forEach(function(button) {
      var selected = button === viewBtn;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    var showTimeline = viewBtn.dataset.claimView === "timeline";
    var claimsList = document.getElementById("rtab-claims-list");
    var timelinePane = document.getElementById("rtab-timeline");
    if (claimsList) claimsList.style.display = showTimeline ? "none" : "block";
    if (timelinePane) timelinePane.style.display = showTimeline ? "block" : "none";
    if (showTimeline) refreshResearchClaimProjections();
    return;
  }

  var tabBtn = event.target.closest("[data-rtab]");
  if (tabBtn) {
    clearResearchSourceSelections();
    showResearchTab(tabBtn);
    var targetId = "rtab-" + tabBtn.dataset.rtab;
    if (tabBtn.dataset.rtab === "sources") refreshResearchSources();
    if (tabBtn.dataset.rtab === "dossiers") refreshResearchDossiers();
    if (tabBtn.dataset.rtab === "claims") { refreshResearchClaims(); refreshResearchClaimProjections(); }
    if (tabBtn.dataset.rtab === "decisions") refreshResearchDecisions();
    if (tabBtn.dataset.rtab === "review") refreshResearchEditorialReview();
    if (window.LixityMotion) window.LixityMotion.view(document.getElementById(targetId));
    return;
  }

  var initBtn = event.target.closest("#r-init-btn");
  if (initBtn) {
    var titleInput = document.getElementById("r-init-title");
    var res = await researchApiPost("research-init", { title: titleInput ? titleInput.value : "" });
    researchStatus(res.ok ? uiLabel("research_init_complete") : res.message, res.ok);
    if (res.ok) initResearchUI(true);
    return;
  }

  var ingestBtn = event.target.closest("#r-ingest-btn");
  if (ingestBtn) {
    var retCheck = document.getElementById("r-ingest-retention");
    if (!retCheck || !retCheck.checked) {
      researchStatus(uiLabel("research_retention_required"), false);
      return;
    }
    var originEl = document.getElementById("r-ingest-origin-url");
    var originUrl = originEl ? originEl.value.trim() : "";
    if (originUrl) {
      try {
        var parsedOrigin = new URL(originUrl);
        if (!["http:", "https:"].includes(parsedOrigin.protocol) || parsedOrigin.username || parsedOrigin.password || /[\s\\]/.test(originUrl)) throw new Error("invalid");
      } catch (_) {
        researchStatus(uiLabel("research_origin_url_invalid"), false);
        if (originEl) originEl.focus();
        return;
      }
    }
    var titleEl = document.getElementById("r-ingest-title");
    var tagsEl = document.getElementById("r-ingest-tags");
    var textEl = document.getElementById("r-ingest-text");
    var fileEl = document.getElementById("r-ingest-file");
    var tags = (tagsEl && tagsEl.value) ? tagsEl.value.split(",").map(function(t){ return t.trim(); }).filter(Boolean) : [];

    function sendIngest(content, filename, isBase64) {
      researchStatus(uiLabel("research_ingesting_extracting") || uiLabel("research_ingesting"), true);
      if (ingestBtn) ingestBtn.disabled = true;
      var payload = {
        title: (titleEl && titleEl.value.trim()) || filename || uiLabel("research_tab_sources"),
        filename: filename,
        origin_url: originUrl || null,
        tags: tags,
        allow_retention: true
      };
      if (isBase64) {
        payload.content_base64 = content;
      } else {
        payload.content = content;
      }
      researchApiPost("research-ingest", payload).then(function(res) {
        if (ingestBtn) ingestBtn.disabled = false;
        var msg = res.ok
          ? (uiLabel("research_ingest_complete") + (res.passages ? " (" + res.passages + " passages)" : ""))
          : (res.message || "Failed");
        if (res.ok && Array.isArray(res.warnings) && res.warnings.length) {
          msg += " " + res.warnings.join(" ");
        }
        researchStatus(msg, res.ok);
        if (res.ok) {
          if (titleEl) titleEl.value = "";
          if (originEl) originEl.value = "";
          if (tagsEl) tagsEl.value = "";
          if (textEl) textEl.value = "";
          if (fileEl) fileEl.value = "";
          retCheck.checked = false;
          refreshResearchSources(null, null, true);
        }
      }).catch(function(err) {
        if (ingestBtn) ingestBtn.disabled = false;
        researchStatus(String(err), false);
      });
    }

    if (fileEl && fileEl.files && fileEl.files.length) {
      var file = fileEl.files[0];
      researchStatus(uiLabel("research_ingesting_reading") || "Reading file…", true);
      var isPdf = file.name.toLowerCase().endsWith(".pdf");
      var reader = new FileReader();
      if (isPdf) {
        reader.onload = function() {
          var dataUrl = String(reader.result || "");
          var base64 = dataUrl.split(",")[1] || "";
          sendIngest(base64, file.name, true);
        };
        reader.readAsDataURL(file);
      } else {
        reader.onload = function() { sendIngest(reader.result, file.name, false); };
        reader.readAsText(file);
      }
    } else if (textEl && textEl.value.trim()) {
      sendIngest(textEl.value, "", false);
    } else {
      researchStatus(uiLabel("research_source_required"), false);
    }
    return;
  }

function highlightSearchTerms(text, query) {
  if (!text || !query) return escapeHtml(text || "");
  var terms = query.trim().split(/\s+/).filter(function(t) { return t.length > 0; });
  if (!terms.length) return escapeHtml(text);
  var escapedTerms = terms.map(function(t) { return t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); });
  var regex = new RegExp('(' + escapedTerms.join('|') + ')', 'gi');
  var escaped = escapeHtml(text);
  return escaped.replace(regex, '<mark class="search-hit">$1</mark>');
}

  var searchBtn = event.target.closest("#r-search-btn");
  if (searchBtn) {
    var searchRead = ++researchSearchRead;
    var searchContext = researchReadContext();
    var qEl = document.getElementById("r-search-query");
    var query = qEl ? qEl.value.trim() : "";
    if (!query) { researchStatus(uiLabel("research_query_required"), false); return; }
    var resultsHost = document.getElementById("research-search-results");
    if (resultsHost) resultsHost.innerHTML = '<p class="ctl-note">' + escapeHtml(uiLabel("research_searching")) + '</p>';
    var scopeEl = document.getElementById("r-search-scope");
    var sres = await researchApiPost("research-search", { query: query, scope: scopeEl ? scopeEl.value : "sources" });
    if (searchRead !== researchSearchRead || !acceptResearchContext(searchContext, sres)) return;
    if (!sres.ok) {
      if (resultsHost) resultsHost.innerHTML = '<p class="ctl-note">' + escapeHtml(sres.message || uiLabel("research_search_failed")) + '</p>';
      researchStatus(sres.message || uiLabel("research_search_failed"), false);
      return;
    }
    var hits = sres.hits || [];
    if (!hits.length) {
      var currentScope = scopeEl ? scopeEl.value : "sources";
      var scopeHint = "";
      if (currentScope !== "all") {
        scopeHint = '<div class="mt-2">' +
          '<span class="ctl-note">' + escapeHtml(uiLabel("research_search_scope_hint")) + ' </span>' +
          '<button type="button" class="ctl ctl-sm" id="r-search-all-btn">' + escapeHtml(uiLabel("research_search_all_records")) + '</button>' +
          '</div>';
      }
      if (resultsHost) resultsHost.innerHTML = '<p class="ctl-note">' + escapeHtml(uiFormat("research_no_hits", { query: query })) + '</p>' + scopeHint;
      researchStatus(uiFormat("research_no_hits", { query: query }), true);
      return;
    }
    if (resultsHost) {
      resultsHost.innerHTML = hits.map(function(h) {
        if (["dossier", "claim", "decision"].indexOf(h.kind) !== -1) {
          var statusLabel = h.kind === "claim"
            ? uiLabel("research_confidence_" + h.confidence)
            : h.kind === "decision" ? uiLabel(h.deviation_from_fact ? "research_deliberate_deviation" : "research_no_deviation_recorded") : "";
          return '<div class="research-passage-card">' +
            '<div class="research-card-title">' + escapeHtml(h.title || "") + '</div>' +
            '<div class="ctl-note">' + escapeHtml(uiLabel("research_revision_kind_" + h.kind)) + ' · ' +
              escapeHtml(uiFormat("research_revision_number", {revision: h.revision})) + '</div>' +
            (statusLabel ? '<div class="ctl-note">' + escapeHtml(statusLabel) + '</div>' : '') +
            '<p class="research-passage-quote">' + highlightSearchTerms(h.excerpt || "", query) + '</p>' +
            '<button type="button" class="ctl" data-research-history="' + h.kind + '" data-record-id="' + escapeHtml(h.record_id) + '">' +
              escapeHtml(uiLabel("research_view_details")) + '</button></div>';
        }
        return '<div class="research-passage-card">' +
          '<div class="research-passage-quote">„' + highlightSearchTerms(h.verbatim || "", query) + '“</div>' +
          '<div class="research-passage-cite">' +
            escapeHtml(uiLabel("research_source")) + ' <strong>' + escapeHtml(h.source_title || "") + '</strong> · ' +
            escapeHtml(uiLabel("research_rank_score")) + ': ' + (h.rank_score !== undefined ? Number(h.rank_score).toFixed(2) : 'n/a') + ' · ' +
            escapeHtml(uiLabel("research_id")) + ' <code class="select-code" title="' + escapeHtml(uiLabel("research_select_id")) + '">' + escapeHtml(h.passage_id || "") + '</code>' +
          '</div>' +
          researchPassageActions(h.passage_id, h) +
        '</div>';
      }).join("");
    }
    researchStatus(uiCountFormat("research_hits_count", hits.length), true);
    return;
  }

  var searchAllBtn = event.target.closest("#r-search-all-btn");
  if (searchAllBtn) {
    var scopeSel = document.getElementById("r-search-scope");
    if (scopeSel) scopeSel.value = "all";
    var sBtn = document.getElementById("r-search-btn");
    if (sBtn) sBtn.click();
    return;
  }

  var dosBtn = event.target.closest("#r-dos-create-btn");
  if (dosBtn) {
    if (dosBtn.dataset.pending === "true") return;
    var dTitle = document.getElementById("r-dos-title");
    var dTags = document.getElementById("r-dos-tags");
    var dEids = document.getElementById("r-dos-eids");
    var dBody = document.getElementById("r-dos-body");
    var titleVal = dTitle ? dTitle.value.trim() : "";
    if (!titleVal) { researchFormStatus(dosBtn, uiLabel("research_dossier_title_required"), "err"); return; }
    var tagsArr = (dTags && dTags.value) ? dTags.value.split(",").map(function(t){ return t.trim(); }).filter(Boolean) : [];
    var eidsArr = (dEids && dEids.value) ? dEids.value.split(",").map(function(t){ return t.trim(); }).filter(Boolean) : [];
    var dGeography = document.getElementById("r-dos-geography"), geography = null;
    try { if (dGeography && dGeography._geographyEditor) geography = dGeography._geographyEditor.read(); }
    catch (error) { researchFormStatus(dosBtn, error.message || uiLabel("geography_invalid"), "err"); return; }
    await submitResearchForm(dosBtn, "research-dossier", {
      title: titleVal,
      body: dBody ? dBody.value : "",
      tags: tagsArr,
      evidence_ids: eidsArr,
      geography: geography
    }, ["r-dos-title", "r-dos-tags", "r-dos-eids", "r-dos-body", "r-dos-geography"],
      ["r-dos-title", "r-dos-tags", "r-dos-eids", "r-dos-body", "r-dos-geography"], "research_dossier_complete",
      function() { refreshResearchDossiers(null, null, true); });
    return;
  }

  var groundBtn = event.target.closest("#r-ground-btn");
  if (groundBtn) {
    var srcSelect = document.getElementById("r-ground-source-select");
    var sid = srcSelect ? srcSelect.value : "";
    if (!sid) { researchStatus(uiLabel("research_select_source_required"), false); return; }
    var gHost = document.getElementById("research-grounding-results");
    if (gHost) gHost.innerHTML = '<p class="ctl-note">' + escapeHtml(uiLabel("research_grounding")) + '</p>';
    var gres = await researchApiPost("research-compare", { source_id: sid });
    if (!gres.ok) {
      if (gHost) gHost.innerHTML = '<p class="ctl-note">' + escapeHtml(gres.message || uiLabel("research_ground_failed")) + '</p>';
      researchStatus(gres.message || uiLabel("research_ground_failed"), false);
      return;
    }
    var sum = gres.summary || {};
    var comparisonMeta = gres.meta || {};
    var crossLanguage = comparisonMeta.source_language && comparisonMeta.manuscript_language &&
      comparisonMeta.source_language !== comparisonMeta.manuscript_language;
    var topShared = (gres.lexical_overlap && gres.lexical_overlap.top_shared_terms) || [];
    var sharedWordsHtml = topShared.slice(0, 15).map(function(w) {
      return '<span class="research-tag">' + escapeHtml(w.word) + ' (' + w.total_count + ')</span>';
    }).join(" ");

    var sourceKeyTerms = (gres.keyness && gres.keyness.source_key_terms) || [];
    var keyTermsHtml = sourceKeyTerms.slice(0, 15).map(function(k) {
      return '<span class="research-tag" style="border-color:var(--accent);">' + escapeHtml(k.word) + ' (G² ' + k.g2 + ')</span>';
    }).join(" ");

    var chapters = gres.chapter_grounding || [];
    var chRows = chapters.map(function(c) {
      return '<tr>' +
        '<td>' + escapeHtml(uiLabel("research_chapter_prefix")) + ' ' + c.chapter + ' (' + escapeHtml(c.title || "") + ')</td>' +
        '<td class="num-right">' + c.overlap_tokens + '</td>' +
        '<td class="num-right">' + (c.grounding_density ? c.grounding_density.toFixed(1) : '0') + '‰</td>' +
      '</tr>';
    }).join("");

    if (gHost) {
      gHost.innerHTML = '<div class="research-card mt-3">' +
        '<div class="research-card-title mb-2">' + escapeHtml(uiLabel("research_results_for")) + ' ' + escapeHtml(gres.provenance ? gres.provenance.source_title : "") + '</div>' +
        '<p class="ctl-note">' + escapeHtml(uiLabel("research_comparison_limit")) + '</p>' +
        (crossLanguage ? '<p class="ctl-note research-comparison-warning" role="status">' + escapeHtml(uiLabel("research_cross_language_limit")) + '</p>' : '') +
        '<div class="research-compare-metric"><span>' + escapeHtml(uiLabel("research_similarity")) + '</span><strong>' + (sum.jaccard_similarity !== undefined ? (sum.jaccard_similarity * 100).toFixed(1) + '%' : 'n/a') + '</strong></div>' +
        '<div class="research-compare-metric"><span>' + escapeHtml(uiLabel("research_shared_types")) + '</span><strong>' + (sum.shared_types || 0) + '</strong></div>' +
        '<div class="research-compare-metric"><span>' + escapeHtml(uiLabel("research_word_counts")) + '</span><span>' + (sum.source_content_words || 0) + ' / ' + (sum.manuscript_content_words || 0) + '</span></div>' +
        (sharedWordsHtml ? '<div class="mt-2"><div class="ctl-label mb-1">' + escapeHtml(uiLabel("research_shared_words")) + '</div><div class="research-tags">' + sharedWordsHtml + '</div></div>' : '') +
        (keyTermsHtml ? '<div class="mt-2"><div class="ctl-label mb-1">' + escapeHtml(uiLabel("research_source_key_terms")) + '</div><div class="research-tags">' + keyTermsHtml + '</div></div>' : '') +
        (chRows ? '<div class="mt-3"><div class="ctl-label mb-1">' + escapeHtml(uiLabel("research_chapter_density")) + '</div><table class="research-chapter-table"><thead><tr><th class="num-left">' + escapeHtml(uiLabel("research_chapter")) + '</th><th class="num-right">' + escapeHtml(uiLabel("research_tokens")) + '</th><th class="num-right">' + escapeHtml(uiLabel("research_density")) + '</th></tr></thead><tbody>' + chRows + '</tbody></table></div>' : '') +
      '</div>';
    }
    researchStatus(uiLabel("research_ground_complete"), true);
    return;
  }

  var claimBtn = event.target.closest("#r-claim-create-btn");
  if (claimBtn) {
    if (claimBtn.dataset.pending === "true") return;
    var cTitle = document.getElementById("r-claim-title");
    var cConf = document.getElementById("r-claim-confidence");
    var cTags = document.getElementById("r-claim-tags");
    var cStmt = document.getElementById("r-claim-statement");
    var cTime = document.getElementById("r-claim-time");
    var cPlace = document.getElementById("r-claim-place");
    var cActors = document.getElementById("r-claim-actors");
    var cDossier = document.getElementById("r-claim-dossier-select");

    var titleVal = cTitle ? cTitle.value.trim() : "";
    var stmtVal = cStmt ? cStmt.value.trim() : "";
    if (!titleVal || !stmtVal) {
      researchFormStatus(claimBtn, uiLabel("research_claim_required"), "err");
      return;
    }
    var tagsArr = (cTags && cTags.value) ? cTags.value.split(",").map(function(t){ return t.trim(); }).filter(Boolean) : [];
    var actorsArr = (cActors && cActors.value) ? cActors.value.split(",").map(function(a){ return a.trim(); }).filter(Boolean) : [];

    await submitResearchForm(claimBtn, "research-claim-add", {
      title: titleVal,
      statement: stmtVal,
      confidence: cConf ? cConf.value : "hypothetical",
      time_period: cTime ? cTime.value.trim() : "",
      place: cPlace ? cPlace.value.trim() : "",
      actors: actorsArr,
      dossier_id: cDossier ? cDossier.value : "",
      tags: tagsArr
    }, ["r-claim-title", "r-claim-statement", "r-claim-tags", "r-claim-time", "r-claim-place",
      "r-claim-actors", "r-claim-confidence", "r-claim-dossier-select"],
      ["r-claim-title", "r-claim-statement", "r-claim-tags", "r-claim-time", "r-claim-place", "r-claim-actors"],
      "research_claim_complete", refreshResearchClaims);
    return;
  }

  var matrixBtn = event.target.closest("#r-claim-matrix-btn");
  if (matrixBtn) {
    if (matrixBtn.disabled) return;
    var matrixContext = researchReadContext();
    matrixBtn.disabled = true; matrixBtn.setAttribute("aria-busy", "true");
    try {
      var resp = await researchApiGet("research/matrix?format=md", "markdown");
      if (!acceptResearchContext(matrixContext, resp)) return;
      if (!resp.ok) {
        researchFormStatus(matrixBtn, resp.message || uiLabel("research_matrix_failed"), "err");
        return;
      }
      var mdText = resp.text;
      var blob = new Blob([mdText], { type: "text/markdown;charset=utf-8" });
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = "claim-evidence-matrix.md";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      researchFormStatus(matrixBtn, uiLabel("research_matrix_saved"), "ok");
    } catch (e) {
      researchFormStatus(matrixBtn, uiLabel("research_matrix_failed"), "err");
    } finally { matrixBtn.disabled = false; matrixBtn.removeAttribute("aria-busy"); }
    return;
  }

  var linkEvBtn = event.target.closest("#r-link-evidence-btn");
  if (linkEvBtn) {
    if (linkEvBtn.disabled) return;
    var lClaim = document.getElementById("r-link-claim-select");
    var lPassage = document.getElementById("r-link-passage-id");
    var lRel = document.getElementById("r-link-relation");
    var lRat = document.getElementById("r-link-rationale");

    var claimVal = lClaim ? lClaim.value.trim() : "";
    var passageVal = lPassage ? lPassage.value.trim() : "";
    if (researchEvidenceDraft && (researchEvidenceDraft.projectId !== researchSelectionProjectId ||
        researchEvidenceDraft.token !== researchContextToken() ||
        researchEvidenceDraft.passageId !== passageVal)) {
      discardResearchEvidenceDraft();
      researchStatus(uiLabel("selection_invalid"), false);
      return;
    }
    if (!claimVal || !passageVal) {
      researchStatus(uiLabel("research_link_required"), false);
      return;
    }

    var submittedDraft = researchEvidenceDraft;
    var evidenceContext = researchReadContext();
    var reviewed = researchEvidenceReview;
    if (researchContextToken() && (!reviewed || reviewed.claimId !== claimVal ||
        reviewed.projectId !== researchSelectionProjectId || reviewed.token !== researchContextToken())) {
      researchStatus(uiLabel("selection_invalid"), false); return;
    }
    var submittedRelation = lRel ? lRel.value : "supports";
    var submittedRationale = lRat ? lRat.value.trim() : "";
    linkEvBtn.disabled = true;
    linkEvBtn.setAttribute("aria-busy", "true");
    var lres;
    var linkPayload = {
      claim_id: claimVal,
      passage_id: passageVal,
      relation: submittedRelation,
      rationale: submittedRationale
    };
    if (researchContextToken()) Object.assign(linkPayload, {project_id: reviewed.projectId,
      expected_snapshot: submittedDraft && submittedDraft.sourceSnapshot || reviewed.snapshot,
      expected_claim_revision: reviewed.revision});
    try {lres = await researchApiPost("research-evidence-link", linkPayload);
    } finally {linkEvBtn.disabled = false; linkEvBtn.removeAttribute("aria-busy");}
    if (!acceptResearchContext(evidenceContext, lres)) return;
    researchStatus(lres.ok ? uiLabel("research_evidence_link_complete") : lres.message, lres.ok);
    if (lres.ok) {
      if (researchEvidenceDraft === submittedDraft && lPassage.value.trim() === passageVal &&
          lClaim.value.trim() === claimVal && (!lRel || lRel.value === submittedRelation) &&
          (!lRat || lRat.value.trim() === submittedRationale)) {
        discardResearchEvidenceDraft();
        if (lRat) lRat.value = "";
      }
      refreshResearchClaims();
    }
    return;
  }

  var decBtn = event.target.closest("#r-decision-create-btn");
  if (decBtn) {
    if (decBtn.dataset.pending === "true") return;
    var decTitle = document.getElementById("r-decision-title");
    var decClaim = document.getElementById("r-decision-claim-select");
    var decRat = document.getElementById("r-decision-rationale");
    var decPlot = document.getElementById("r-decision-plot");
    var decDev = document.getElementById("r-decision-deviation");
    var decDossier = document.getElementById("r-decision-dossier-select");

    var dTitleVal = decTitle ? decTitle.value.trim() : "";
    var dRatVal = decRat ? decRat.value.trim() : "";
    if (!dTitleVal || !dRatVal) {
      researchFormStatus(decBtn, uiLabel("research_decision_required"), "err");
      return;
    }

    await submitResearchForm(decBtn, "research-decision-add", {
      title: dTitleVal,
      rationale: dRatVal,
      claim_id: decClaim ? decClaim.value.trim() : "",
      dossier_ids: decDossier && decDossier.value ? [decDossier.value] : [],
      impact_on_plot: decPlot ? decPlot.value.trim() : "",
      deviation_from_fact: decDev ? decDev.checked : false
    }, ["r-decision-title", "r-decision-rationale", "r-decision-plot", "r-decision-deviation",
      "r-decision-claim-select", "r-decision-dossier-select"],
      ["r-decision-title", "r-decision-rationale", "r-decision-plot", "r-decision-deviation"],
      "research_decision_complete", refreshResearchDecisions);
    return;
  }

  var linkClaimEvidence = event.target.closest("[data-link-claim-evidence]");
  if (linkClaimEvidence) {
    var targetClaim = linkClaimEvidence.dataset.linkClaimEvidence;
    var claimField = document.getElementById("r-link-claim-select");
    var passageField = document.getElementById("r-link-passage-id");
    if (!researchContextToken() || !researchClaimChoices[targetClaim] || !claimField || !passageField) return;
    // An existing evidence draft belongs to its chosen claim. Opening another
    // claim's guidance must not replace that choice or its retained passage.
    if (!claimField.value) {
      claimField.value = targetClaim;
      claimField.dispatchEvent(new Event("change", {bubbles: true}));
    }
    revealDisclosures(claimField);
    var nextField = claimField.value === targetClaim && !passageField.value.trim()
      ? document.getElementById("r-find-passage") : claimField;
    (nextField || claimField).focus();
    return;
  }

  var loadEvBtn = event.target.closest("[data-load-evidence]");
  if (loadEvBtn) {
    var cid = loadEvBtn.dataset.loadEvidence;
    var cardItem = researchClaimCardItems.find(function(entry) { return entry.id === cid; });
    if (!cardItem) return;
    var evidenceToken = researchContextToken();
    var evidenceProject = researchSelectionProjectId;
    cardItem.evidenceHtml = '<span class="ctl-note">' + escapeHtml(uiLabel("research_loading_evidence")) + '</span>';
    renderResearchClaimCards();
    var evData = await researchApiGet("research/claims?claim_id=" + encodeURIComponent(cid));
    if (cardItem !== researchClaimCardItems.find(function(entry) { return entry.id === cid; }) ||
        evidenceToken !== researchContextToken() || evidenceProject !== researchSelectionProjectId) return;
    cardItem.evidenceHtml = researchEvidencePanelHtml(evData, cid);
    renderResearchClaimCards();
    return;
  }
});

document.addEventListener("toggle", function(event) {
  var disclosure = event.target;
  if (!disclosure.matches("[data-decision-review]")) return;
  if (disclosure.open) loadResearchDecisionComparison(disclosure);
  else {
    ++disclosure._decisionReviewRequest;
    disclosure._decisionReviewPending = false;
  }
}, true);

function researchEvidencePanelHtml(evData, claimId) {
  var links = evData.evidence_links;
  var renderable = Array.isArray(links) && links.every(function(link) {
    if (!link || typeof link !== "object" || Array.isArray(link)) return false;
    var cite = link.citation || {};
    // Optional metadata may be absent. Objects in text/number fields can fail
    // JSON value coercion and must not strand the panel in its loading state.
    return [link.id, link.relation, link.passage_id, link.rationale, link.revision,
      link.claim_revision, link.claim_latest_revision, cite.source_title, cite.verbatim].every(function(value) {
      return value === null || typeof value !== "object";
    });
  });
  if (!evData.ok || !renderable) {
    return '<p class="ctl-note">' + escapeHtml(evData.message || uiLabel("research_load_evidence_failed")) + '</p>' +
      '<button type="button" class="ctl ctl-compact" data-load-evidence="' + escapeHtml(claimId) + '">' +
      escapeHtml(uiLabel("research_load_evidence")) + '</button>';
  }
  if (!links.length) {
    var canLink = researchContextToken() && researchClaimChoices[claimId] && document.getElementById("r-link-composer");
    return '<p class="ctl-note">' + escapeHtml(uiLabel("research_no_linked_evidence")) + '</p>' +
      (canLink ? '<button type="button" class="ctl ctl-compact" data-link-claim-evidence="' + escapeHtml(claimId) + '">' +
      escapeHtml(uiLabel("research_link_heading")) + '</button>' : '');
  }
  return '<div class="research-block-heading">' + escapeHtml(uiCountFormat("research_linked_evidence_count", links.length)) + '</div>' +
      links.map(function(l) {
        var relBadge = '<span class="research-badge badge-neutral research-relation-badge">' + escapeHtml(uiLabel("research_relation_" + l.relation)) + '</span>';
        var cite = l.citation || {};
        var unavailable = Boolean(cite.error) || !cite.availability;
        var withdrawn = cite.availability === "withdrawn";
        var availability = unavailable ? uiLabel("research_evidence_unavailable") : (withdrawn ? uiLabel("research_evidence_withdrawn_context") : uiLabel("research_evidence_retained_unreviewed"));
        var quote = !unavailable && cite.verbatim ? '„' + escapeHtml(cite.verbatim) + '“' : '<em>' + escapeHtml(uiLabel("research_no_quote")) + '</em>';
        return '<div class="research-passage-card research-passage-card">' +
          '<div class="research-passage-head">' +
            relBadge +
            '<span class="research-badge ' + (unavailable || withdrawn ? 'badge-warning' : 'badge-neutral') + '">' + escapeHtml(availability) + '</span>' +
            '<span class="ctl-note research-passage-title-note">' + escapeHtml(cite.source_title || l.passage_id) + '</span>' +
          '</div>' +
          '<div class="research-passage-quote">' + quote + '</div>' +
          (l.rationale ? '<div class="ctl-note text-note">' + escapeHtml(l.rationale) + '</div>' : '') +
          (l.revision ? '<div class="ctl-note">' + escapeHtml(uiFormat("research_revision_number", { revision: l.revision })) + '</div>' : '') +
          (l.claim_revision && l.claim_latest_revision && Number(l.claim_revision) < Number(l.claim_latest_revision)
            ? '<div class="ctl-note">' + escapeHtml(uiFormat("research_revision_pinned_claim", { revision: l.claim_revision })) + '</div>' : '') +
          researchRevisionActions("evidence_link", l.id) +
        '</div>';
      }).join("");
}

