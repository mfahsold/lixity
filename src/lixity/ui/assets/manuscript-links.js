(function () {
  "use strict";
  var bridge = window.LixityManuscriptLinks;
  var canWrite = document.body.dataset.manuscriptLinks === "1";
  var tokenHost = document.getElementById("manuscript-pdf-form") || document.getElementById("workspace-reader") || document.body;
  function projectToken() {
    return tokenHost === document.body ? tokenHost.dataset.manuscriptProjectToken : tokenHost.dataset.projectToken;
  }
  if (!bridge || (!canWrite && document.body.dataset.manuscriptLinks !== "read") ||
      !projectToken() || !bridge.contextToken() || !document.body.dataset.manuscriptSourceSha256) return;
  var draft = null, serial = 0, reviewSerial = 0, review = null, reviewContext = null, remembered = null, reviewProjectId = null, reviewPending = null;
  var passageOwner = null, reviewFailure = null;
  var reviewFilter = null, renderedReviewFilter = null, openingRelated = false, relatedDestination = null;
  var pending = new Set(), dialog, picker, quotation, statement, consent, save, status, filterInput;
  var chapters = document.getElementById("chapters");
  if (!chapters) return;
  function element(tag, text, className) {
    if (window.LixityComponents && typeof window.LixityComponents.el === "function") {
      return window.LixityComponents.el(tag, { className: className || "", text: text || null });
    }
    var node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function label(key) { return bridge.label(key); }
  function countLabel(key, count) {
    if (typeof window.uiCountFormat === "function") return window.uiCountFormat(key, count);
    var singular = key + "_one";
    var chosen = count === 1 && label(singular) !== singular ? singular : key;
    return label(chosen).replace("{count}", String(count));
  }
  function researchIcon() {
    var icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("viewBox", "0 0 24 24"); icon.setAttribute("aria-hidden", "true");
    icon.setAttribute("focusable", "false"); icon.setAttribute("class", "manuscript-research-icon");
    var path = document.createElementNS(icon.namespaceURI, "path");
    path.setAttribute("d", "M12 8v13M3 4h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5v15h-5a4 4 0 0 0-4 2 4 4 0 0 0-4-2H3z");
    icon.appendChild(path); return icon;
  }
  function context() {
    return {research: bridge.contextToken(), project: projectToken(),
      source: document.body.dataset.manuscriptSourceSha256};
  }
  function same(a, b) { return a.research === b.research && a.project === b.project && a.source === b.source; }
  function live(value) { return same(value, context()); }
  function selection() {
    var selected = window.getSelection();
    if (!selected || selected.rangeCount !== 1 || selected.isCollapsed) return null;
    var range = selected.getRangeAt(0);
    var start = range.startContainer.nodeType === Node.ELEMENT_NODE ? range.startContainer : range.startContainer.parentElement;
    var end = range.endContainer.nodeType === Node.ELEMENT_NODE ? range.endContainer : range.endContainer.parentElement;
    var paragraph = start.closest("#chapters .ptext-inner > p");
    if (!paragraph || !paragraph.contains(end)) return null;
    var panel = paragraph.closest(".ptext"), text = bridge.text(panel);
    if (!text || paragraph.textContent !== text) return null;
    var prefix = document.createRange(); prefix.selectNodeContents(paragraph); prefix.setEnd(range.startContainer, range.startOffset);
    var from = Array.from(prefix.toString()).length;
    prefix.setEnd(range.endContainer, range.endOffset);
    var to = Array.from(prefix.toString()).length;
    var quote = Array.from(text).slice(from, to).join("");
    if (!quote.trim() || to - from > 10000 || quote !== selected.toString()) return null;
    return {panel: panel, context: context(), anchor: {start_line: Number(panel.dataset.start),
      end_line: Number(panel.dataset.end), paragraph_sha256: panel.dataset.paragraphSha256,
      start: from, end: to, quote: quote}};
  }
  function validClaims(claims) {
    return Array.isArray(claims) && claims.every(function(claim) {
      return claim && typeof claim === "object" && typeof claim.id === "string" && claim.id &&
        Number.isInteger(claim.revision) && claim.revision > 0 && typeof claim.title === "string" && typeof claim.statement === "string";
    });
  }
  function validRows(rows) {
    return Array.isArray(rows) && rows.every(function(row) {
      return row && typeof row === "object" && typeof row.claim_id === "string" &&
        Number.isInteger(row.claim_revision) && row.claim_revision > 0 && row.anchor &&
        typeof row.anchor === "object" && typeof row.anchor.quote === "string" &&
        Array.isArray(row.flags) && row.flags.every(function(flag) { return typeof flag === "string"; });
    });
  }
  function updateSave() {
    if (!save) return;
    var writing = Boolean(draft && pending.has(draft.key));
    var ready = Boolean(draft && draft.claims && draft.claims.length);
    picker.disabled = !ready || writing;
    consent.disabled = !ready || writing;
    save.disabled = !ready || !picker.value || !consent.checked || !live(draft.context) || writing;
    if (draft && draft.duplicateClaimId === picker.value) save.disabled = true;
  }
  function createDialog() {
    if (dialog) return;
    dialog = element("dialog", "", "lixity-modal manuscript-link-dialog");
    dialog.id = "manuscript-link-dialog"; dialog.setAttribute("aria-labelledby", "manuscript-link-title");
    var card = element("div", "", "modal-card"), header = element("div", "", "modal-header");
    var title = element("h3", label("manuscript_link_action")); title.id = "manuscript-link-title";
    var closeBtn = element("button", "✕", "modal-close"); closeBtn.type = "button";
    closeBtn.setAttribute("aria-label", label("modal_close"));
    closeBtn.title = label("modal_close");
    closeBtn.setAttribute("aria-keyshortcuts", "Escape");
    closeBtn.addEventListener("click", function() { dialog.close(); });
    header.append(title, closeBtn); card.appendChild(header);
    var body = element("div", "", "modal-body");
    quotation = element("blockquote"); quotation.id = "manuscript-link-quote"; body.appendChild(quotation);
    var choose = element("label", label("manuscript_link_choose")); choose.htmlFor = "manuscript-link-claim"; body.appendChild(choose);
    filterInput = element("input", "", "ctl"); filterInput.type = "text"; filterInput.id = "manuscript-link-filter";
    filterInput.hidden = true; filterInput.placeholder = label("manuscript_link_filter");
    filterInput.setAttribute("aria-label", label("manuscript_link_filter"));
    filterInput.addEventListener("input", function() { fillPicker(); updateSave(); });
    body.appendChild(filterInput);
    picker = element("select", "", "ctl"); picker.id = "manuscript-link-claim"; body.appendChild(picker);
    statement = element("p", "", "ctl-note"); statement.id = "manuscript-link-statement"; body.appendChild(statement);
    var retention = element("label", "", "manuscript-link-retention");
    consent = element("input"); consent.type = "checkbox"; consent.id = "manuscript-link-retain";
    retention.append(consent, document.createTextNode(label("manuscript_link_retention"))); body.appendChild(retention);
    var storageNote = element("details", "", "ctl-note manuscript-link-storage");
    storageNote.appendChild(element("summary", label("manuscript_link_storage_title")));
    storageNote.appendChild(element("p", label("manuscript_link_storage_hint")));
    body.appendChild(storageNote);
    status = element("p", "", "ctl-status"); status.id = "manuscript-link-status";
    status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite"); body.appendChild(status);
    card.appendChild(body);
    var footer = element("div", "", "modal-footer");
    var cancel = element("button", label("modal_cancel"), "ctl"); cancel.type = "button";
    cancel.setAttribute("aria-keyshortcuts", "Escape");
    cancel.addEventListener("click", function() { dialog.close(); });
    save = element("button", label("manuscript_link_save"), "ctl"); save.type = "button"; save.id = "manuscript-link-save";
    save.addEventListener("click", saveDraft); footer.append(cancel, save); card.appendChild(footer); dialog.appendChild(card); document.body.appendChild(dialog);
    picker.addEventListener("change", function() {
      var claim = draft && draft.claims && draft.claims.find(function(c) { return c.id === picker.value; });
      statement.textContent = claim ? claim.statement || "" : ""; updateSave();
      if (draft && draft.duplicateClaimId) status.textContent = label(draft.duplicateClaimId === picker.value ? "manuscript_link_duplicate" : "manuscript_link_hint");
    });
    consent.addEventListener("change", updateSave);
    dialog.addEventListener("close", function() {
      // Native close is queued: a newer open already owns its draft and reads.
      if (dialog.open) return;
      ++serial; draft = null; remembered = null;
    });
  }
  function reloadButton() {
    var button = element("button", label("manuscript_link_reload"), "ctl manuscript-link-reload");
    button.type = "button"; button.dataset.manuscriptLinkReload = "";
    return button;
  }
  function fillPicker() {
    var claims = (draft && draft.claims) || [];
    var query = filterInput && !filterInput.hidden ? filterInput.value.trim().toLowerCase() : "";
    picker.replaceChildren(element("option", label("manuscript_link_choose")));
    picker.firstChild.value = "";
    claims.forEach(function(claim) {
      if (query && (claim.title + " " + claim.statement).toLowerCase().indexOf(query) < 0) return;
      var option = element("option", claim.title + " · " + label("research_revision_number").replace("{revision}", claim.revision));
      option.value = claim.id; picker.appendChild(option);
    });
  }
  function unavailable(message, stale) {
    status.textContent = message || label("manuscript_link_unavailable");
    status.className = "ctl-status err";
    if (stale) status.appendChild(reloadButton());
  }
  function staleReport(report, sourceSha) {
    return Boolean(report && report.ok === true &&
      ((report.current_source_sha256 ?? report.source_sha256) !== sourceSha || report.source_state !== "available"));
  }
  async function open(value) {
    createDialog(); var request = ++serial;
    draft = value; draft.key = JSON.stringify([value.context, value.anchor]);
    quotation.textContent = value.anchor.quote; consent.checked = false; statement.textContent = "";
    picker.replaceChildren(element("option", label("manuscript_link_choose"))); picker.firstChild.value = "";
    if (filterInput) { filterInput.value = ""; filterInput.hidden = true; }
    picker.disabled = true; status.className = "ctl-status loading"; status.textContent = label("research_loading"); updateSave();
    if (!dialog.open) dialog.showModal();
    var archive = await bridge.read("research/status");
    if (request !== serial || draft !== value || !dialog.open || !live(value.context)) return;
    if (!archive.ok || archive.initialized !== true) {
      unavailable(archive.ok && archive.initialized === false ? label("research_not_initialized") : bridge.errorText(archive));
      return;
    }
    var responses = await Promise.all([bridge.read("research/claims"),
      bridge.read("research/manuscript-review?project_token=" + encodeURIComponent(value.context.project))]);
    if (request !== serial || draft !== value || !dialog.open) return;
    if (!live(value.context)) { unavailable(); return; }
    var claims = responses[0], report = responses[1];
    if (!claims.ok || !report.ok || claims.schema_version !== "research-claims-local/2" ||
        report.schema_version !== "research-manuscript-review-local/1" || !claims.project_id ||
        claims.project_id !== report.project_id || !claims.snapshot || claims.snapshot !== report.snapshot ||
        report.current_source_sha256 !== value.context.source || report.source_state !== "available" || !validClaims(claims.claims) || !validRows(report.links)) {
      var stale = staleReport(report, value.context.source) || report.code === "stale-context";
      var reason = stale ? label("manuscript_link_stale") : bridge.errorText(claims.message ? claims : report);
      clearReview(reason, stale); unavailable(reason, stale); return;
    }
    draft.claims = claims.claims.filter(function(claim) { return claim.id && Number.isInteger(claim.revision) && claim.revision > 0; });
    draft.projectId = claims.project_id; draft.snapshot = claims.snapshot;
    if (filterInput) filterInput.hidden = draft.claims.length <= 6;
    fillPicker();
    if (draft.claims.length) {
      picker.disabled = false; status.className = "ctl-status"; status.textContent = label("manuscript_link_hint"); picker.focus();
    } else {
      status.className = "ctl-status"; status.textContent = label("manuscript_link_empty_claims");
    }
    ++reviewSerial; applyReview(report, value.context); updateSave();
  }
  async function saveDraft() {
    updateSave(); if (save.disabled) return;
    var submitted = draft, request = serial;
    var claim = submitted.claims.find(function(c) { return c.id === picker.value; });
    if (!claim) return;
    pending.add(submitted.key); updateSave(); status.textContent = label("form_saving");
    var response;
    try {
      response = await bridge.post("research-manuscript-link", {project_id: submitted.projectId,
        project_token: submitted.context.project, research_token: submitted.context.research,
        expected_snapshot: submitted.snapshot, expected_source_sha256: submitted.context.source,
        claim_id: claim.id, claim_revision: claim.revision, selection: submitted.anchor, allow_retention: true});
    } finally { pending.delete(submitted.key); updateSave(); }
    if (!live(submitted.context)) { if (request === serial) { unavailable(); updateSave(); } return; }
    if (request !== serial || draft !== submitted || !dialog.open) return;
    updateSave();
    if (response && response.ok === false && response.code === "duplicate-link") {
      submitted.duplicateClaimId = claim.id; updateSave();
      status.textContent = label("manuscript_link_duplicate"); return;
    }
    if (response && response.ok === false && response.code === "stale-context") {
      unavailable(label("manuscript_link_stale"), true); return;
    }
    if (response && response.ok === false && response.code === "stale-archive") {
      unavailable(label("manuscript_link_archive_changed")); return;
    }
    var record = response && response.record, pin = record && record.claim_ref, anchor = record && record.anchor;
    if (!response || !response.ok || response.schema_version !== "research-manuscript-link-local/1" ||
        response.project_id !== submitted.projectId || !response.snapshot || !response.link_id ||
        response.claim_id !== claim.id || response.claim_revision !== claim.revision ||
        !record || record.id !== response.link_id || record.kind !== "manuscript_claim_link" ||
        !pin || pin.id !== claim.id || pin.revision !== claim.revision || !anchor ||
        !Object.keys(submitted.anchor).every(function(key) { return anchor[key] === submitted.anchor[key]; })) {
      unavailable(bridge.errorText(response)); return;
    }
    dialog.close();
    var feedback = submitted.panel.querySelector(".manuscript-link-feedback");
    if (feedback) feedback.textContent = label("manuscript_link_saved");
    loadReview();
  }
  var reviewSection = document.getElementById("research-manuscript-review-section");
  var reviewTabHost = document.getElementById("research-manuscript-review");
  var termsSection = document.getElementById("research-manuscript-terms-section");
  var termsTabHost = document.getElementById("research-manuscript-terms");
  var termsManager = document.getElementById("r-term-manage");
  var termDossier = document.getElementById("r-term-dossier");
  var termVariants = document.getElementById("r-term-variants");
  var addTermVariant = document.getElementById("r-term-add-variant");
  var removedTermVariants = false;
  var termsSerial = 0, termsReport = null, termsContext = null, termsWritePending = false;
  var termDossierSerial = 0, termDossierContext = null;
  if (reviewSection && reviewTabHost) {
    reviewSection.hidden = false;
    reviewTabHost.replaceChildren(element("p", label("research_loading"), "ctl-status loading"));
  }
  if (termsSection && termsTabHost) {
    termsSection.hidden = false;
  }
  var panelIndex = null;
  function invalidatePanelIndex() { panelIndex = null; }
  function getPanelIndex() {
    if (panelIndex) return panelIndex;
    var byLineRange = new Map();
    var panels = chapters.querySelectorAll(".ptext");
    for (var i = 0; i < panels.length; i++) {
      var panel = panels[i];
      var rangeKey = Number(panel.dataset.start) + ":" + Number(panel.dataset.end);
      var byRangeList = byLineRange.get(rangeKey);
      if (byRangeList) byRangeList.push(panel);
      else byLineRange.set(rangeKey, [panel]);
    }
    panelIndex = byLineRange;
    return panelIndex;
  }
  if (typeof MutationObserver === "function") {
    new MutationObserver(function(mutations) {
      for (var i = 0; i < mutations.length; i++) {
        var m = mutations[i];
        if (m.type === "attributes" || m.target === chapters ||
            (m.target && m.target.nodeType === 1 && !m.target.closest(".ptext-inner"))) {
          invalidatePanelIndex();
          break;
        }
      }
    }).observe(chapters, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-paragraph-sha256", "data-start", "data-end"]
    });
  }
  document.addEventListener("lixity:reader-ready", invalidatePanelIndex);
  function matchesQuote(panel, start, end, quote) {
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start) return false;
    var points = Array.from(bridge.text(panel) || "");
    return end <= points.length && points.slice(start, end).join("") === quote;
  }
  function matchesExactPanel(panel, anchor, startLine, endLine) {
    return !!(anchor && anchor.paragraph_sha256 && anchor.paragraph_sha256 === panel.dataset.paragraphSha256 &&
      startLine === Number(panel.dataset.start) && endLine === Number(panel.dataset.end) &&
      matchesQuote(panel, anchor.start, anchor.end, anchor.quote));
  }
  function uniquePanel(startLine, endLine, matches) {
    var candidates = (getPanelIndex().get(startLine + ":" + endLine) || []).filter(matches);
    return candidates.length === 1 ? candidates[0] : null;
  }
  function matchesPanel(row, panel) {
    return row.anchor_state === "resolved" && matchesExactPanel(panel, row.anchor, row.resolved_start_line, row.resolved_end_line);
  }
  function passageResearchRows(report, panel) {
    return (report.links || []).filter(function(row) { return matchesPanel(row, panel); });
  }
  function linkedPanel(row) {
    if (!row || row.anchor_state !== "resolved" || !row.anchor || !row.anchor.paragraph_sha256) return null;
    return uniquePanel(row.resolved_start_line, row.resolved_end_line, function(panel) { return matchesPanel(row, panel); });
  }
  function candidatePanel(row) {
    if (!["moved", "adjusted"].includes(row.anchor_state) || !row.anchor ||
        !Number.isInteger(row.resolved_start_line) || !Number.isInteger(row.resolved_end_line) ||
        !Number.isInteger(row.resolved_start) || !Number.isInteger(row.resolved_end)) return null;
    // Adjusted paragraphs retain the recorded quotation at new codepoint
    // offsets; their former paragraph hash and offsets intentionally differ.
    return uniquePanel(row.resolved_start_line, row.resolved_end_line, function(panel) {
      return matchesQuote(panel, row.resolved_start, row.resolved_end, row.anchor.quote);
    });
  }
  function renderReviewItems(report, filtered) {
    var rows = report.links || [];
    if (filtered && reviewFilter) rows = rows.filter(function(row) {
      return (!reviewFilter.claimId || row.claim_id === reviewFilter.claimId) &&
        (!reviewFilter.dossierId || row.dossier_id === reviewFilter.dossierId) &&
        (!reviewFilter.revision || row.claim_revision === reviewFilter.revision) &&
        (!reviewFilter.paragraphId || (document.getElementById(reviewFilter.paragraphId) &&
          matchesPanel(row, document.getElementById(reviewFilter.paragraphId))));
    });
    var fragment = document.createDocumentFragment();
    fragment.appendChild(element("p", countLabel("manuscript_link_review_count", rows.length), "ctl-note"));
    if (filtered && reviewFilter) {
      var all = element("button", label("manuscript_link_review"), "ctl");
      all.type = "button"; all.dataset.manuscriptLinksAll = ""; fragment.appendChild(all);
    }
    if (rows.length) fragment.appendChild(element("p", label("manuscript_link_chapter_hint"), "ctl-note"));
    function chapterNumber(row) {
      return Number.isInteger(row.resolved_chapter_num) && row.resolved_chapter_num > 0 ? row.resolved_chapter_num : Infinity;
    }
    rows = rows.slice().sort(function(a, b) {
      return chapterNumber(a) - chapterNumber(b) ||
        (a.resolved_start_line || Infinity) - (b.resolved_start_line || Infinity);
    });
    var groups = [];
    var currentGroup = null;
    rows.forEach(function(row) {
      var number = chapterNumber(row);
      if (!currentGroup || currentGroup.number !== number) {
        var title = number === Infinity ? label("manuscript_link_no_current_chapter") :
          label("manuscript_link_current_chapter").replace("{number}", number).replace("{title}", function() {return row.resolved_chapter_title || "";});
        currentGroup = {number: number, title: title, rows: [], hasAttention: number === Infinity};
        groups.push(currentGroup);
      }
      var state = ["resolved", "moved", "adjusted", "ambiguous", "changed"].includes(row.anchor_state) ? row.anchor_state : "unavailable_anchor";
      if (state !== "resolved" || (row.flags && row.flags.length)) currentGroup.hasAttention = true;
      currentGroup.rows.push(row);
    });
    var autoExpandClean = rows.length <= 12;
    var attentionOpened = false;
    groups.forEach(function(group) {
      var expandAttention = group.hasAttention && !attentionOpened;
      if (expandAttention) attentionOpened = true;
      var details = document.createElement("details");
      details.className = "research-details mb-2";
      details.dataset.manuscriptChapterGroup = "";
      details.open = autoExpandClean || expandAttention;
      var summary = document.createElement("summary");
      var heading = element("h3", group.title);
      heading.dataset.manuscriptCurrentChapter = "";
      heading.style.display = "inline";
      summary.appendChild(heading);
      summary.appendChild(element("span", " (" + group.rows.length + ")", "ctl-note"));
      details.appendChild(summary);
      group.rows.forEach(function(row) {
        var item = element("div", "", "manuscript-link-review-item");
        item.appendChild(element("p", window.LixityComponents.recordLabel({title:row.claim_title}, label("research_name_unavailable_claim"))));
        var state = ["resolved", "moved", "adjusted", "ambiguous", "changed"].includes(row.anchor_state) ? row.anchor_state : "unavailable_anchor";
        var flags = [label("manuscript_link_" + state)];
        (row.flags || []).forEach(function(flag) {
          if (["source_changed", "claim_changed", "claim_withdrawn"].includes(flag)) flags.push(label("manuscript_link_" + flag));
        });
        item.appendChild(element("p", flags.join(" · "), "ctl-note"));
        if (row.anchor) item.appendChild(element("blockquote", row.anchor.quote));
        if (linkedPanel(row)) {
          var jump = element("button", label("manuscript_link_open_passage"), "ctl"); jump.type = "button";
          jump.dataset.manuscriptLinkJump = row.link_id; item.appendChild(jump);
        }
        if (candidatePanel(row)) {
          var inspect = element("button", label("manuscript_link_inspect_candidate"), "ctl"); inspect.type = "button";
          inspect.dataset.manuscriptLinkCandidate = row.link_id; item.appendChild(inspect);
        }
        var history = element("button", label("research_revision_linked_version").replace("{revision}", row.claim_revision), "ctl"); history.type = "button";
        history.dataset.researchHistory = "claim"; history.dataset.recordId = row.claim_id;
        history.dataset.recordRevision = String(row.claim_revision); item.appendChild(history);
        if (canWrite && (row.anchor_state === "moved" || row.anchor_state === "adjusted")) {
          var acceptLabel = row.anchor_state === "adjusted" ? "manuscript_link_accept_adjusted" : "manuscript_link_accept_moved";
          var accept = element("button", label(acceptLabel), "ctl");
          accept.type = "button"; accept.dataset.manuscriptLinkAccept = row.link_id;
          accept.dataset.manuscriptLinkAcceptRevision = String(row.revision);
          item.appendChild(accept);
          var acceptStatus = element("p", "", "ctl-status");
          acceptStatus.dataset.manuscriptLinkAcceptStatus = ""; acceptStatus.hidden = true;
          item.appendChild(acceptStatus);
        }
        details.appendChild(item);
      });
      fragment.appendChild(details);
    });
    if (!rows.length) fragment.appendChild(element("p", label("manuscript_link_review_empty"), "ctl-note"));
    return fragment;
  }
  // Counts are saved associations, not distinct sources or analytical evidence.
  function paragraphLinksControl(panel) {
    var inner = panel.querySelector(".ptext-inner");
    if (!inner) return;
    var button = inner.querySelector("[data-manuscript-links-paragraph]");
    var count = review && reviewContext && live(reviewContext) ? review.links.filter(function(row) { return matchesPanel(row, panel); }).length : 0;
    if (!count) { if (button) button.remove(); return; }
    if (!button) {
      button = element("button", "", "ctl manuscript-link-related"); button.type = "button";
      button.dataset.manuscriptLinksParagraph = panel.id; inner.appendChild(button);
    }
    button.replaceChildren(researchIcon(), element("span", bridge.countFormat("manuscript_link_research_count", count)));
  }
  function applyReview(report, value) {
    if (!live(value)) return;
    var unchanged = review && reviewContext && same(value, reviewContext) &&
      JSON.stringify(report) === JSON.stringify(review);
    var filterKey = JSON.stringify(reviewFilter);
    if (passageOwner && passageOwner.reviewSerial && review && report.snapshot !== review.snapshot) invalidatePassage();
    reviewFailure = null;
    review = report; reviewContext = value; reviewProjectId = report.project_id;
    document.querySelectorAll("#chapters .ptext").forEach(function(panel) {
      var text = bridge.text(panel), points = Array.from(text || "");
      // Only exact resolved anchors are marked inline; moved and adjusted
      // candidates stay visible in the review list until an explicit re-pin.
      var spans = (report.links || []).filter(function(row) {
        return matchesPanel(row, panel);
      }).map(function(row) { return {start: points.slice(0, row.anchor.start).join("").length,
        end: points.slice(0, row.anchor.end).join("").length}; });
      bridge.marks(panel, spans);
      paragraphLinksControl(panel);
    });
    // An identical refresh must retain controls that native dialogs use as
    // their focus-return targets. Filters still own a distinct rendered view.
    if (reviewTabHost && (!unchanged || renderedReviewFilter !== filterKey)) {
      reviewTabHost.replaceChildren(renderReviewItems(report, true));
      renderedReviewFilter = filterKey;
    }
  }
  function reviewNote(message, stale) {
    var note = element("p", message || label("manuscript_link_unavailable"), "ctl-status err");
    if (stale) note.appendChild(reloadButton());
    return note;
  }
  function clearReview(message, stale) {
    if (passageOwner && passageOwner.reviewSerial) invalidatePassage();
    reviewFailure = {message: message, state: stale ? "stale" : "unavailable"};
    review = null;
    document.querySelectorAll("#chapters .ptext").forEach(function(panel) { bridge.marks(panel, []); paragraphLinksControl(panel); });
    if (reviewTabHost) reviewTabHost.replaceChildren(reviewNote(message, stale));
  }
  async function loadReview(automatic) {
    var value = context();
    if (automatic && reviewPending && reviewPending.request === reviewSerial && same(reviewPending.context, value)) return reviewPending.promise;
    var request = ++reviewSerial, reading = {context: value, request: request};
    reviewPending = reading;
    reading.promise = (async function() {
      try {
        // Archive absence is a normal project state. The status endpoint can
        // represent it without calling a review endpoint that requires setup.
        var archive = await bridge.read("research/status", undefined, automatic === true);
        if (request !== reviewSerial || !live(value)) return;
        if (!archive.ok || archive.initialized !== true) {
          clearReview(archive.ok && archive.initialized === false ? label("research_not_initialized") : bridge.errorText(archive));
          reviewFailure.state = archive.ok && archive.initialized === false ? "uninitialized" : "read-error";
          return;
        }
        var report = await bridge.read("research/manuscript-review?project_token=" + encodeURIComponent(value.project));
        if (request !== reviewSerial || !live(value)) return;
        if (!report.ok || report.schema_version !== "research-manuscript-review-local/1" || !validRows(report.links) ||
            !report.project_id || !report.snapshot || (reviewProjectId && report.project_id !== reviewProjectId) ||
            (archive.project_id && report.project_id !== archive.project_id) ||
            report.current_source_sha256 !== value.source || report.source_state !== "available") {
          var stale = staleReport(report, value.source) || report.code === "stale-context";
          clearReview(stale ? label("manuscript_link_stale") : bridge.errorText(report), stale);
          if (!stale && report.ok === false) reviewFailure.state = "read-error";
          return;
        }
        applyReview(report, value);
      } finally {
        if (reviewPending === reading) reviewPending = null;
      }
    })();
    return reading.promise;
  }
  function enhance(panel) {
    paragraphLinksControl(panel);
    if (!canWrite) {
      if (review) applyReview(review, context());
      else if (reviewSerial === 0) loadReview(true);
      return;
    }
    var inner = panel.querySelector(".ptext-inner");
    if (!inner || inner.querySelector("[data-manuscript-link-selection]")) return;
    var row = inner.querySelector(".marker-row") || element("div", "", "row manuscript-link-controls");
    var button = element("button", label("manuscript_link_action"), "ctl"); button.type = "button";
    button.dataset.manuscriptLinkSelection = ""; button.setAttribute("aria-keyshortcuts", "Alt+L");
    button.title = label("manuscript_link_hint"); button.setAttribute("aria-description", label("manuscript_link_hint"));
    var feedback = element("div", "", "ctl-note manuscript-link-feedback");
    feedback.setAttribute("role", "status"); row.appendChild(button);
    if (!row.parentNode) inner.appendChild(row);
    inner.appendChild(feedback);
    button.addEventListener("pointerdown", function() { var value = selection(); remembered = value && value.panel === panel ? value : null; });
    button.addEventListener("click", function() {
      var value = selection() || remembered;
      if (!value || value.panel !== panel || !live(value.context)) {
        var paragraph = panel.querySelector(".ptext-inner > p");
        var text = bridge.text(panel);
        if (paragraph && text && text.trim() && text.length <= 10000) {
          value = {
            panel: panel,
            anchor: {
              paragraph_sha256: panel.dataset.paragraphSha256,
              start_line: Number(panel.dataset.start),
              end_line: Number(panel.dataset.end),
              start: 0,
              end: Array.from(text).length,
              quote: text
            },
            context: context()
          };
        }
      }
      if (!value || value.panel !== panel || !live(value.context)) { feedback.textContent = label("manuscript_link_invalid"); return; }
      open(value);
    });
    if (!review && reviewSerial === 0) loadReview(true);
  }
  var observedContext = context();
  var contextObserver = new MutationObserver(function() {
    if (passageOwner && (!passageOwner.panel.isConnected || passageOwner.hash !== passageOwner.panel.dataset.paragraphSha256)) invalidatePassage();
    var next = context(); if (same(next, observedContext)) return;
    invalidateResearchStatusReads();
    stopRelatedDestination();
    invalidatePassage();
    observedContext = next; ++reviewSerial; reviewProjectId = null; remembered = null; reviewPending = null; reviewFilter = null;
    clearReview(); if (draft) draft.claims = null;
    if (dialog && dialog.open) { unavailable(); updateSave(); }
  });
  [document.body, tokenHost, document.getElementById("research-manager")].forEach(function(host) {
    if (host) contextObserver.observe(host, {attributes: true, attributeFilter: ["data-project-token", "data-manuscript-project-token", "data-research-token", "data-manuscript-source-sha256"]});
  });
  contextObserver.observe(chapters, {childList: true, subtree: true, attributes: true, attributeFilter: ["data-paragraph-sha256"]});
  document.addEventListener("click", function(event) {
    if (event.target.closest("[data-manuscript-link-reload]")) { event.preventDefault(); window.location.reload(); }
  });
  function openRelated(filter, control) {
    var tab = document.querySelector('[data-rtab="review"]');
    if (!reviewTabHost || !tab) return;
    reviewFilter = filter;
    openingRelated = true;
    try {
      if (window.LixityResearchTools) window.LixityResearchTools.open("review", control || document.activeElement, {focus: false, filter: filter});
      else { switchActiveView("research"); tab.click(); }
    } finally { openingRelated = false; }
    reviewSection.tabIndex = -1;
    reviewSection.focus({preventScroll: true});
    scrollAndFlash(reviewSection, {behavior: "instant"});
    followRelatedDestination();
  }
  function stopRelatedDestination() {
    if (!relatedDestination) return;
    relatedDestination.observer.disconnect();
    cancelAnimationFrame(relatedDestination.frame);
    relatedDestination = null;
  }
  function followRelatedDestination() {
    stopRelatedDestination();
    var destination = {context: context(), frame: 0};
    function align() {
      if (relatedDestination !== destination) return;
      if (!live(destination.context) || document.activeElement !== reviewSection ||
          !reviewSection.getClientRects().length || !(window.LixityResearchTools && window.LixityResearchTools.active() === "review")) {
        stopRelatedDestination(); return;
      }
      scrollAndFlash(reviewSection, {behavior: "instant"});
    }
    function resized() {
      cancelAnimationFrame(destination.frame);
      destination.frame = requestAnimationFrame(align);
    }
    // Review also loads editorial decisions before this destination. Keep its
    // requested position as those reads render, until the user takes control.
    var observesSize = typeof ResizeObserver === "function";
    destination.observer = observesSize ? new ResizeObserver(resized) : new MutationObserver(resized);
    relatedDestination = destination;
    [document.getElementById("research-editorial-review"), reviewTabHost].forEach(function(host) {
      if (host) destination.observer.observe(host, observesSize ? undefined : {childList: true, subtree: true});
    });
  }
  ["pointerdown", "touchstart", "wheel", "keydown"].forEach(function(name) {
    document.addEventListener(name, stopRelatedDestination, {capture: true, passive: true});
  });
  document.addEventListener("focusin", function(event) {
    if (event.target !== reviewSection) stopRelatedDestination();
  });
  document.addEventListener("lixity:viewchange", stopRelatedDestination);
  document.addEventListener("lixity:workbench-change", stopRelatedDestination);
  var passageHost = element("aside", "", "panel passage-research");
  passageHost.dataset.passageResearch = ""; passageHost.hidden = true;
  passageHost.setAttribute("aria-labelledby", "passage-research-title");
  var passageHead = element("div", "", "workspace-reader-head");
  var passageTitle = element("h2", label("passage_research")); passageTitle.id = "passage-research-title";
  passageTitle.prepend(researchIcon());
  var passageClose = element("button", "✕", "ctl"); passageClose.type = "button";
  passageClose.dataset.passageResearchClose = ""; passageClose.setAttribute("aria-label", label("modal_close"));
  passageHead.append(passageTitle, passageClose);
  var passageBody = element("div"); passageBody.setAttribute("aria-live", "polite");
  var passageReview = element("button", label("manuscript_link_review"), "ctl"); passageReview.type = "button"; passageReview.hidden = true;
  passageHost.append(passageHead, passageBody, passageReview);
  var contextHost = document.getElementById("workspace-context-panel");
  var passageTab = element("button", label("passage_research_tab"), "ctl");
  passageTab.type = "button"; passageTab.dataset.contextTool = "research"; passageTab.hidden = true;
  passageTab.setAttribute("aria-pressed", "false");
  if (contextHost) {
    contextHost.appendChild(passageHost);
    contextHost.querySelector(".context-tool-tabs").appendChild(passageTab);
  }
  function resetPassage() {
    passageOwner = null; passageBody.replaceChildren();
    passageHost.dataset.state = "closed"; passageTab.hidden = true; passageReview.hidden = true;
  }
  function invalidatePassage() {
    var panel = passageOwner && passageOwner.panel;
    // A second context change while suspended must retain the stale notice
    // and its explicit retry, rather than erase the now-expired owner again.
    if (!panel && window.LixityWorkbench.state().contextTool !== "research") return;
    resetPassage();
    passageHost.dataset.state = "stale"; passageTab.hidden = false;
    passageBody.appendChild(element("p", label("manuscript_link_stale"), "ctl-status"));
    if (panel && panel.isConnected) {
      var retry = element("button", label("reader_refresh"), "ctl"); retry.type = "button";
      retry.dataset.passageResearchRetry = "";
      retry.addEventListener("click", function() { openPassage(panel, true); });
      passageBody.appendChild(retry);
    }
  }
  function closePassage() {
    var panel = passageOwner && passageOwner.panel;
    window.LixityWorkbench.dispatch({type: "tool", value: "none"});
    if (panel && panel.isConnected) {
      var trigger = panel.querySelector("[data-reader-paragraph]");
      if (trigger) trigger.focus({preventScroll: true});
    }
  }
  passageClose.addEventListener("click", closePassage);
  passageHost.addEventListener("keydown", function(event) {
    if (event.key === "Escape" && !event.defaultPrevented && !event.target.closest("dialog")) {
      event.preventDefault(); closePassage();
    }
  });
  window.LixityWorkbench.subscribe(function(state, previous) {
    passageHost.hidden = state.contextTool !== "research" || state.surface !== "document";
    if (contextHost) contextHost.classList.toggle("passage-research-open", !passageHost.hidden);
    var suspended = state.focus || state.surface === "overview";
    if (state.contextTool !== "research" && previous.contextTool === "research") {
      if (suspended) {
        // The disclosure also owns stale/retry presentation after its async
        // owner expires. Suspending that presentation must not erase it.
        if (passageOwner) {
          passageOwner.suspended = true;
          // A hidden request expires permanently, even if its response arrives
          // after the shared display owner restores this tool.
          if (passageHost.dataset.state === "pending") passageOwner.departed = true;
        }
      } else resetPassage();
    }
    if (passageOwner && passageOwner.suspended && !suspended) {
      passageOwner.suspended = false;
      if (state.contextTool !== "research") resetPassage();
      else if (passageOwner.departed) invalidatePassage();
    }
    if (!suspended && (previous.focus || previous.surface === "overview") && state.contextTool !== "research") resetPassage();
    // Leaving the document invalidates in-flight reads. Accepted content can be
    // revisited, but a late response cannot change a different surface.
    if (state.view !== previous.view && passageOwner) {
      if (state.view !== "analysis") passageOwner.departed = true;
      else if (passageOwner.departed) {
        invalidatePassage();
      }
    }
  });
  function passageCurrent(owner) {
    var state = window.LixityWorkbench.state();
    return passageOwner === owner && !owner.departed && owner.panel.isConnected && live(owner.context) &&
      owner.hash === owner.panel.dataset.paragraphSha256 && state.contextTool === "research" &&
      state.view === "analysis" && state.surface === "document";
  }
  function passageStatus(owner, state, message) {
    if (!passageCurrent(owner)) return;
    passageHost.dataset.state = state;
    var note = element("p", message, "ctl-status"); note.setAttribute("role", "status");
    passageBody.replaceChildren(note);
    if (state === "pending") return;
    var retry = element("button", label("reader_refresh"), "ctl"); retry.type = "button";
    retry.dataset.passageResearchRetry = "";
    retry.addEventListener("click", function() { openPassage(owner.panel, true); });
    passageBody.appendChild(retry);
    if (state === "uninitialized") {
      var setup = element("button", label("passage_research_setup"), "ctl"); setup.type = "button";
      setup.addEventListener("click", function() { switchActiveView("research"); });
      passageBody.appendChild(setup);
    }
  }
  function recordButton(kind, record) {
    var button = element("button", record.title, "ctl passage-record-title");
    button.type = "button"; button.dataset.researchHistory = kind;
    button.dataset.recordId = record.id;
    return button;
  }
  function pinnedRecord(item, kind, current, pins) {
    var section = element("div", "", "passage-research-record");
    section.appendChild(element("p", label("research_revision_kind_" + kind), "ctl-note"));
    section.appendChild(recordButton(kind, current));
    pins.forEach(function(linked) {
      if (linked.revision === current.revision) return;
      var pin = element("button", label("research_revision_linked_version").replace("{revision}", linked.revision), "ctl passage-record-pin");
      pin.type = "button"; pin.dataset.researchHistory = kind;
      pin.dataset.recordId = linked.id; pin.dataset.recordRevision = String(linked.revision);
      section.appendChild(pin);
    });
    item.appendChild(section);
  }
  function passageDetails(title, attribute) {
    var details = element("details", "", "research-details");
    details.setAttribute(attribute, ""); details.appendChild(element("summary", title));
    return details;
  }
  function passageModel(report, panel) {
    var projection = report.passage_context;
    function record(value) {
      return value && typeof value.id === "string" && value.id && typeof value.title === "string" &&
        Number.isInteger(value.revision) && value.revision > 0;
    }
    if (!projection || projection.schema_version !== "research-passage-context-local/1" || !Array.isArray(projection.paragraphs)) throw {state:"unavailable"};
    var matches = projection.paragraphs.filter(function(value) {
      return value && value.start_line === Number(panel.dataset.start) && value.end_line === Number(panel.dataset.end) &&
        value.paragraph_sha256 === panel.dataset.paragraphSha256;
    });
    // Verify transport completeness against the accepted review without
    // rebuilding the backend's grouping, revision choice or decision graph.
    var rows = passageResearchRows(report, panel);
    if (!matches.length && !rows.length) return {state:"empty", total:0, shown:0, groups:[]};
    if (matches.length !== 1) throw {state:"unavailable"};
    var model = matches[0];
    if (model.state === "unavailable") throw {state:"unavailable"};
    if (model.state !== "ready" || !Number.isInteger(model.total) || model.total !== rows.length ||
        !Number.isInteger(model.shown) || model.shown < 1 || model.shown > 5 || model.shown > model.total ||
        !Array.isArray(model.groups)) throw {state:"unavailable"};
    var shown = 0, seen = new Set();
    model.groups.forEach(function(group) {
      if (!group || !Array.isArray(group.claims) || !Array.isArray(group.decisions) || !group.decisions.every(record) ||
          (group.dossier && (!record(group.dossier.current) || !Array.isArray(group.dossier.pins) || !group.dossier.pins.every(record)))) throw {state:"unavailable"};
      if (group.dossier && group.dossier.pins.some(function(pin) {
        return pin.id !== group.dossier.current.id || pin.revision >= group.dossier.current.revision;
      })) throw {state:"unavailable"};
      group.claims.forEach(function(claim) {
        if (!claim || !record(claim.current) || !Array.isArray(claim.versions) || !claim.versions.length) throw {state:"unavailable"};
        claim.versions.forEach(function(version) {
          if (!version || !record(version.pinned) || claim.current.id !== version.pinned.id ||
              typeof version.confidence !== "string" || !Array.isArray(version.associations) || !version.associations.length) throw {state:"unavailable"};
          version.associations.forEach(function(association) {
            var row = association && rows.find(function(value) {return value.link_id === association.link_id;});
            if (!row || seen.has(row.link_id) || row.claim_id !== version.pinned.id || row.claim_revision !== version.pinned.revision ||
                row.claim_current_revision !== claim.current.revision ||
                (row.dossier_id ? !group.dossier || row.dossier_id !== group.dossier.current.id ||
                  row.dossier_revision !== version.dossier_revision ||
                  (row.dossier_revision !== group.dossier.current.revision && !group.dossier.pins.some(function(pin) {
                    return pin.revision === row.dossier_revision;
                  })) : group.dossier !== null || version.dossier_revision !== null) ||
                !association.anchor || association.anchor.quote !== row.anchor.quote || !Array.isArray(association.flags)) throw {state:"unavailable"};
            seen.add(row.link_id);
            shown++;
          });
        });
      });
    });
    if (shown !== model.shown) throw {state:"unavailable"};
    return model;
  }
  async function openPassage(panel, retry) {
    if (!panel || !panel.isConnected || !contextHost || !window.LixityReader) return;
    var owner = {panel: panel, hash: panel.dataset.paragraphSha256, context: context()};
    passageOwner = owner; passageTab.hidden = false;
    passageReview.dataset.manuscriptLinksParagraph = panel.id; passageReview.hidden = false;
    window.LixityReader.requestTool("research", panel);
    passageClose.focus({preventScroll: true});
    passageStatus(owner, "pending", label("research_loading"));
    try {
      if (retry || reviewPending || !review || !reviewContext || !live(reviewContext)) await loadReview(!retry);
      if (!passageCurrent(owner)) return;
      if (!review || !reviewContext || !live(reviewContext)) {
        passageStatus(owner, (reviewFailure || {}).state || "unavailable", (reviewFailure || {}).message || label("manuscript_link_unavailable")); return;
      }
      var report = review; owner.reviewSerial = reviewSerial;
      var model = passageModel(report, panel);
      var fragment = document.createDocumentFragment();
      fragment.appendChild(element("p", model.shown === model.total ?
        countLabel("manuscript_link_review_count", model.total) :
        label("passage_research_count").replace("{shown}", model.shown).replace("{total}", model.total), "ctl-note"));
      if (!model.total) fragment.appendChild(element("p", label("passage_research_empty"), "ctl-note"));
      model.groups.forEach(function(group) {
        var item = element("section", "", "passage-research-item");
        if (group.dossier) pinnedRecord(item, "dossier", group.dossier.current, group.dossier.pins);
        group.claims.forEach(function(claim) {
          var claimItem = element("section", "", "passage-research-claim");
          pinnedRecord(claimItem, "claim", claim.current, claim.versions.map(function(version) {return version.pinned;}));
          claim.versions.forEach(function(version) {
            var warnings = new Set();
            version.associations.forEach(function(row) { row.flags.forEach(function(flag) {
              if (["source_changed", "claim_withdrawn"].includes(flag)) warnings.add(label("manuscript_link_" + flag));
            }); });
            if (warnings.size) claimItem.appendChild(element("p", Array.from(warnings).join(" · "), "ctl-note"));
            var associationTitle = countLabel("passage_research_link_details_count", version.associations.length);
            if (claim.versions.length > 1) associationTitle += " · " + label("research_revision_number").replace("{revision}", version.pinned.revision);
            var associations = passageDetails(associationTitle, "data-passage-research-associations");
            associations.appendChild(element("p", label("research_revision_kind_claim") + " · " +
              label("research_revision_number").replace("{revision}", version.pinned.revision), "ctl-note"));
            if (version.dossier_revision) associations.appendChild(element("p", label("research_revision_kind_dossier") + " · " +
              label("research_revision_number").replace("{revision}", version.dossier_revision), "ctl-note"));
            associations.appendChild(element("p", label("passage_research_confidence") + ": " + label("research_confidence_" + version.confidence), "ctl-note"));
            version.associations.forEach(function(row) {
              associations.appendChild(element("blockquote", row.anchor.quote));
              associations.appendChild(element("p", label("manuscript_link_resolved"), "ctl-note"));
            });
            claimItem.appendChild(associations);
          });
          item.appendChild(claimItem);
        });
        if (group.decisions.length) {
          var count = group.decisions.length;
          var decisions = passageDetails(countLabel("passage_research_decision_count", count), "data-passage-research-decisions");
          var more = count > 5 ? passageDetails(countLabel("passage_research_more_decisions", count - 5), "data-passage-research-more-decisions") : null;
          group.decisions.slice(0, 5).forEach(function(decision) { decisions.appendChild(recordButton("decision", decision)); });
          if (more) more.addEventListener("toggle", function() {
            if (!more.open || more.dataset.loaded || !passageCurrent(owner)) return;
            group.decisions.slice(5).forEach(function(decision) { more.appendChild(recordButton("decision", decision)); });
            more.dataset.loaded = "true";
          });
          if (more) decisions.appendChild(more);
          item.appendChild(decisions);
        }
        fragment.appendChild(item);
      });
      passageBody.replaceChildren(fragment); passageHost.dataset.state = model.total ? "ready" : "empty";
    } catch (error) {
      if (error.state !== "cancelled") passageStatus(owner, error.state || "read-error", error.message || label("manuscript_link_unavailable"));
    }
  }
  bridge.passage = openPassage;
  bridge.review = openRelated;
  document.addEventListener("click", function(event) {
    var action = event.target.closest("[data-manuscript-links-claim], [data-manuscript-links-dossier], [data-manuscript-links-paragraph], [data-manuscript-links-all]");
    var inline = event.target.closest("mark.manuscript-claim-hit");
    if (!action && !inline) return;
    if (inline && !action) {
      var selected = window.getSelection();
      if (selected && !selected.isCollapsed) return;
      var panel = inline.closest("#chapters .ptext");
      if (!panel || !review || !reviewContext || !live(reviewContext) || !review.links.some(function(row) { return matchesPanel(row, panel); })) return;
      openPassage(panel);
      return;
    }
    if (action.hasAttribute("data-manuscript-links-paragraph") && !action.closest("[data-passage-research]")) {
      openPassage(document.getElementById(action.dataset.manuscriptLinksParagraph)); return;
    }
    var modal = action.closest("dialog");
    if (modal) modal.close();
    var pin = Number(action.dataset.recordRevision);
    openRelated(action.hasAttribute("data-manuscript-links-all") ? null : {
      claimId: action.dataset.manuscriptLinksClaim, dossierId: action.dataset.manuscriptLinksDossier,
      paragraphId: action.dataset.manuscriptLinksParagraph,
      revision: Number.isInteger(pin) && pin > 0 ? pin : null}, action);
  });
  document.addEventListener("click", async function(event) {
    var candidate = event.target.closest("[data-manuscript-link-candidate]");
    if (candidate) {
      if (!review || !reviewContext || !live(reviewContext)) return;
      var candidateRow = review.links.find(function(link) { return link.link_id === candidate.dataset.manuscriptLinkCandidate; });
      var candidateTarget = candidateRow && candidatePanel(candidateRow);
      if (candidateTarget) bridge.navigate(candidateTarget);
      return;
    }
    var jump = event.target.closest("[data-manuscript-link-jump]");
    if (jump) {
      if (!review || !reviewContext || !live(reviewContext)) return;
      var row = review.links.find(function(link) { return link.link_id === jump.dataset.manuscriptLinkJump; });
      var panel = row && linkedPanel(row);
      if (panel) bridge.navigate(panel);
      return;
    }
    if (!canWrite) return;
    var accept = event.target.closest("[data-manuscript-link-accept]");
    if (!accept || accept.disabled) return;
    var value = context();
    if (!review || !reviewProjectId || !live(value)) return;
    var item = accept.closest(".manuscript-link-review-item");
    var status = item ? item.querySelector("[data-manuscript-link-accept-status]") : null;
    accept.disabled = true;
    if (status) { status.hidden = false; status.className = "ctl-status loading"; status.textContent = label("form_saving"); }
    var response = await bridge.post("research-manuscript-reanchor", {
      project_id: reviewProjectId, research_token: value.research, project_token: value.project,
      link_id: accept.dataset.manuscriptLinkAccept,
      expected_snapshot: review.snapshot,
      expected_revision: Number(accept.dataset.manuscriptLinkAcceptRevision),
      expected_source_sha256: value.source});
    accept.disabled = false;
    if (response && response.ok) {
      if (status) { status.className = "ctl-status ok"; status.textContent = label("manuscript_link_reanchored"); }
      loadReview();
      return;
    }
    if (response && response.code === "stale-context") { clearReview(label("manuscript_link_stale"), true); return; }
    if (response && response.code === "stale-archive") { clearReview(label("manuscript_link_archive_changed")); return; }
    if (status) { status.className = "ctl-status err"; status.textContent = bridge.errorText(response); }
  });
  if (canWrite) document.addEventListener("selectionchange", function() {
    var value = selection();
    if (value) remembered = value;
    else if (window.getSelection() && !window.getSelection().isCollapsed) remembered = null;
  });
  if (canWrite) document.addEventListener("keydown", function(event) {
    if (event.altKey && !event.ctrlKey && !event.metaKey && event.key.toLowerCase() === "l" && !(dialog && dialog.open)) {
      var value = selection(); if (value) { event.preventDefault(); open(value); }
    }
  });
  function termPanel(occ) {
    var anchor = occ && occ.anchor;
    return anchor ? uniquePanel(anchor.start_line, anchor.end_line, function(panel) {
      return matchesExactPanel(panel, anchor, anchor.start_line, anchor.end_line);
    }) : null;
  }
  function fetchTerms(value, dossierId) {
    var query = new URLSearchParams({project_token: value.project});
    if (dossierId) query.set("dossier_id", dossierId);
    return bridge.read("research/manuscript-terms?" + query);
  }
  function validTerms(report, value) {
    return report && report.ok && report.schema_version === "research-manuscript-terms-local/1" &&
      report.source_sha256 === value.source && report.source_state === "available" &&
      Array.isArray(report.terms) && Array.isArray(report.occurrences);
  }
  function termsFailure(report, value) {
    var stale = staleReport(report, value.source) || (report && report.code === "stale-context");
    return reviewNote(stale ? label("manuscript_link_stale") : bridge.errorText(report), stale);
  }
  function renderTermsReport(report, current, headingTag) {
    var fragment = document.createDocumentFragment();
    var terms = Array.isArray(report.terms) ? report.terms : [];
    var occurrences = Array.isArray(report.occurrences) ? report.occurrences : [];
    if (!terms.length) {
      fragment.appendChild(element("p", label("manuscript_terms_empty"), "ctl-note"));
      return fragment;
    }
    fragment.appendChild(element("p", countLabel("manuscript_terms_count", occurrences.length), "ctl-note"));
    if (!occurrences.length) {
      fragment.appendChild(element("p", label("manuscript_terms_no_matches"), "ctl-note"));
      return fragment;
    }
    var chapterControl = document.getElementById("reader-chapter");
    var currentChapter = chapterControl && Array.from(chapterControl.options).find(function(option) {
      return option.value === chapterControl.dataset.currentChapter;
    });
    var currentChapterNum = Number(currentChapter?.dataset.chapterNumber);
    var groups = [];
    var groupByNum = new Map();
    occurrences.forEach(function(occ, idx) {
      var number = Number.isInteger(occ.chapter_num) && occ.chapter_num > 0 ? occ.chapter_num : Infinity;
      var group = groupByNum.get(number);
      if (!group) {
        var title = number === Infinity ? label("manuscript_link_no_current_chapter") :
          label("publication_chapter").replace("{number}", number);
        if (number !== Infinity && occ.chapter_title && title !== occ.chapter_title) title += " · " + occ.chapter_title;
        group = {
          number: number,
          title: title,
          rows: [],
          isCurrent: Number.isInteger(currentChapterNum) && number === currentChapterNum
        };
        groupByNum.set(number, group);
        groups.push(group);
      }
      group.rows.push({occ: occ, idx: idx});
    });
    var autoExpand = occurrences.length <= 12;
    groups.forEach(function(group) {
      var details = document.createElement("details");
      details.className = "research-details mb-2";
      details.dataset.manuscriptTermChapterGroup = "";
      details.open = autoExpand || group.isCurrent;
      var summary = document.createElement("summary");
      var heading = element(headingTag, group.title);
      heading.dataset.manuscriptTermsChapter = "";
      heading.style.display = "inline";
      summary.appendChild(heading);
      summary.appendChild(element("span", " (" + group.rows.length + ")", "ctl-note"));
      details.appendChild(summary);
      group.rows.forEach(function(entry) {
        var occ = entry.occ;
        var item = element("div", "", "manuscript-link-review-item manuscript-term-occurrence-item");
        var summaryText = occ.term + (occ.matched_form && occ.matched_form !== occ.term ? " (" + occ.matched_form + ")" : "");
        item.appendChild(element("p", summaryText));
        var flags = [label("manuscript_terms_variant_" + (occ.variant_kind || "preferred"))];
        (occ.flags || []).forEach(function(flag) {
          if (["overlapping_term", "unicode_ambiguity", "compound_match"].includes(flag)) {
            flags.push(label("manuscript_terms_flag_" + flag));
          }
        });
        item.appendChild(element("p", flags.join(" · "), "ctl-note"));
        if (occ.anchor && typeof occ.anchor.quote === "string") item.appendChild(element("blockquote", occ.anchor.quote));
        if (termPanel(occ)) {
          var jump = element("button", label("manuscript_link_open_passage"), "ctl");
          jump.type = "button";
          jump.dataset.manuscriptTermJump = String(entry.idx);
          jump.addEventListener("click", function() {
            if (!current()) return;
            var panel = termPanel(occ);
            if (panel) bridge.navigate(panel);
          });
          item.appendChild(jump);
        }
        details.appendChild(item);
      });
      fragment.appendChild(details);
    });
    return fragment;
  }
  window.LixityDossierTerms = {
    html: function() {
      var details = document.createElement("details");
      details.dataset.dossierEvidence = "";
      details.dataset.dossierTerms = "";
      var summary = document.createElement("summary");
      summary.appendChild(element("h4", label("research_dossier_linked_terms")));
      var slot = document.createElement("div");
      slot.dataset.dossierTermsReport = "";
      details.append(summary, element("p", label("research_dossier_linked_terms_scope"), "ctl-note"), slot);
      return details.outerHTML;
    },
    mount: function(host, detail, reading) {
      var panel = host.querySelector("[data-dossier-terms]");
      if (!panel) return;
      var slot = panel.querySelector("[data-dossier-terms-report]");
      var serial = 0;
      async function render() {
        if (!panel.open || !reading.current()) return;
        var value = context(), request = ++serial;
        function current() {
          return request === serial && panel.open && reading.current() && host.contains(slot) && live(value);
        }
        slot.replaceChildren(element("p", label("research_loading"), "ctl-status loading"));
        var report = await fetchTerms(value, detail.id);
        if (!current()) return;
        if (!validTerms(report, value) || report.project_id !== detail.project_id || report.dossier_id !== detail.id) {
          slot.replaceChildren(termsFailure(report, value));
          return;
        }
        slot.replaceChildren(renderTermsReport(report, current, "h5"));
      }
      panel.ontoggle = render;
      if (panel.open) render();
    }
  };
  function selectTermDossier(id) {
    if (!termDossier) return;
    termDossier.querySelector("[data-term-dossier-unavailable]")?.remove();
    termDossier.value = id || "";
    if (id && termDossier.value !== id) {
      var unavailable = new Option(label("research_dossier_collection_missing"), id);
      unavailable.disabled = true;
      unavailable.dataset.termDossierUnavailable = "";
      termDossier.add(unavailable);
      termDossier.value = id;
    }
  }
  async function loadTermDossiers() {
    if (!canWrite || !termDossier?.isConnected || !termsManager?.open) return;
    var value = context(), request = ++termDossierSerial;
    var status = document.getElementById("r-term-dossier-status");
    var setStatus = window.LixityComponents.setStatus;
    if (termDossierContext && (termDossierContext.research !== value.research || termDossierContext.source !== value.source)) {
      termDossier.replaceChildren(new Option(label("research_reference_none"), ""));
    }
    termDossier.disabled = true;
    setStatus(status, label("research_loading"), "loading");
    var report = await bridge.read("research/dossiers?" + new URLSearchParams({project_token: value.project}));
    if (request !== termDossierSerial || !live(value) || !termDossier.isConnected || !termsManager.open) return;
    if (!report?.ok || report.schema_version !== "research-dossiers-local/1" || !Array.isArray(report.dossiers)) {
      setStatus(status, label("research_load_dossiers_failed"), false);
      return;
    }
    var preferred = termDossier.value;
    termDossier.replaceChildren(new Option(label("research_reference_none"), ""));
    report.dossiers.forEach(function(dossier) {
      termDossier.add(new Option(researchRecordLabel(dossier, "dossier"), dossier.id));
    });
    disambiguateResearchOptions(termDossier);
    selectTermDossier(preferred);
    termDossierContext = value;
    termDossier.disabled = false;
    setStatus(status, report.dossiers.length ? "" : label("research_no_dossiers"), "");
  }
  function termChapterNumbers(text) {
    if (!text.trim()) return [];
    var numbers = text.split(",").map(function(piece) {
      var digits = piece.trim();
      return /^\d+$/.test(digits) ? Number(digits) : NaN;
    });
    return numbers.every(function(num) { return Number.isSafeInteger(num) && num > 0; }) &&
      new Set(numbers).size === numbers.length ? numbers : null;
  }
  function labelTermVariants() {
    Array.from(termVariants.children).forEach(function(row, index) {
      row.querySelector("legend").textContent = uiFormat("manuscript_terms_variant_title", {number: index + 1});
    });
  }
  function appendTermVariant(variant) {
    var row = element("fieldset", "", "ctl-group research-term-variant");
    row.dataset.termVariant = "";
    row.appendChild(element("legend"));
    var inputs = element("div", "", "row"), components = window.LixityComponents;
    function field(key, value) {
      var input = components.createField(inputs, {label: label("manuscript_terms_variant_" + key), value: value});
      input.closest(".setting-field").classList.add("research-form-field");
      input.dataset.termVariantField = key;
      return input;
    }
    var form = field("form", variant?.term), scope = field("chapters", (variant?.chapters || []).join(", "));
    field("note", variant?.note);
    form.required = scope.required = true;
    form.addEventListener("input", function() { form.setCustomValidity(""); });
    scope.placeholder = "1, 3";
    scope.dataset.help = label("manuscript_terms_variant_chapters_help");
    row.appendChild(inputs);
    var available = new Set(Array.from(document.querySelectorAll("#reader-chapter [data-chapter-number]"), function(node) {
      return Number(node.dataset.chapterNumber);
    }).filter(function(num) { return Number.isSafeInteger(num) && num > 0; }));
    var chips = element("div", "", "row r-term-chapter-chips");
    function syncChapters() {
      var numbers = termChapterNumbers(scope.value);
      scope.setCustomValidity(numbers ? "" : label("manuscript_terms_variant_chapters_help"));
      chips.querySelectorAll("[data-chapter]").forEach(function(button) {
        var active = Boolean(numbers && numbers.includes(Number(button.dataset.chapter)));
        button.setAttribute("aria-pressed", String(active));
        button.classList.toggle("active", active);
      });
    }
    available.forEach(function(number) {
      var button = element("button", String(number), "ctl r-chapter-chip");
      button.type = "button";
      button.dataset.chapter = String(number);
      button.setAttribute("aria-label", uiFormat("publication_chapter", {number: number}));
      button.addEventListener("click", function() {
        var selected = termChapterNumbers(scope.value);
        if (!selected) { scope.reportValidity(); return; }
        selected = selected.includes(number) ? selected.filter(function(value) { return value !== number; }) : selected.concat(number);
        scope.value = selected.sort(function(a, b) { return a - b; }).join(", ");
        syncChapters();
      });
      chips.appendChild(button);
    });
    scope.addEventListener("input", syncChapters);
    syncChapters();
    if (available.size) {
      var choose = element("details", "", "research-details");
      choose.append(element("summary", label("manuscript_terms_variant_choose_chapters")), chips);
      row.appendChild(choose);
    }
    var actions = element("div", "", "row"), remove = element("button", label("manuscript_terms_variant_remove"), "ctl ctl-sm");
    remove.type = "button";
    remove.addEventListener("click", function() {
      var neighbor = row.nextElementSibling || row.previousElementSibling;
      row.remove();
      removedTermVariants = true;
      labelTermVariants();
      (neighbor?.querySelector('[data-term-variant-field="form"]') || addTermVariant).focus();
    });
    actions.appendChild(remove);
    row.appendChild(actions);
    termVariants.appendChild(row);
    return form;
  }
  function setTermVariants(variants) {
    if (!termVariants) return;
    removedTermVariants = false;
    termVariants.replaceChildren();
    (variants || []).forEach(appendTermVariant);
    labelTermVariants();
  }
  function readTermVariants() {
    var variants = [];
    for (var row of termVariants?.children || []) {
      var termField = row.querySelector('[data-term-variant-field="form"]');
      var scope = row.querySelector('[data-term-variant-field="chapters"]');
      var term = termField.value.trim(), numbers = termChapterNumbers(scope.value);
      termField.setCustomValidity(term ? "" : label("manuscript_terms_variant_form_required"));
      scope.setCustomValidity(numbers?.length ? "" : label("manuscript_terms_variant_chapters_help"));
      if (!termField.reportValidity() || !scope.reportValidity()) return null;
      variants.push({term: term, chapters: numbers, note: row.querySelector('[data-term-variant-field="note"]').value || null});
    }
    return variants.length || removedTermVariants ? variants : undefined;
  }
  if (canWrite && addTermVariant) addTermVariant.addEventListener("click", function() {
    var form = appendTermVariant();
    labelTermVariants();
    form.focus();
  });
  async function loadTerms() {
    if (!termsSection || !termsTabHost) return;
    if (termsManager?.open) loadTermDossiers();
    var value = context(), request = ++termsSerial;
    termsTabHost.replaceChildren(element("p", label("research_loading"), "ctl-status loading"));
    var report = await fetchTerms(value);
    if (request !== termsSerial || !live(value)) return;
    if (!validTerms(report, value)) {
      termsReport = null; termsContext = null;
      termsTabHost.replaceChildren(termsFailure(report, value));
      return;
    }
    termsReport = report; termsContext = value;
    termsTabHost.replaceChildren(renderTermsReport(report, function() {
      return request === termsSerial && live(value);
    }, "h3"));
    var chipsContainer = document.getElementById("r-term-chips");
    if (chipsContainer) {
      chipsContainer.replaceChildren();
      var newBtn = element("button", "+ " + label("manuscript_terms_new"), "ctl");
      newBtn.type = "button";
      newBtn.addEventListener("click", function() {
        var n = document.getElementById("r-term-name"); if (n) n.value = "";
        var a = document.getElementById("r-term-aliases"); if (a) a.value = "";
        var c = document.getElementById("r-term-case"); if (c) c.checked = false;
        var st = document.getElementById("r-term-strict"); if (st) st.checked = false;
        var cp = document.getElementById("r-term-compounds"); if (cp) cp.checked = false;
        selectTermDossier("");
        setTermVariants();
      });
      chipsContainer.appendChild(newBtn);
      ((termsReport && termsReport.terms) || []).forEach(function(item) {
        var chip = element("button", item.term, "ctl");
        chip.type = "button";
        chip.title = (item.aliases || []).join(", ");
        chip.addEventListener("click", function() {
          var n = document.getElementById("r-term-name"); if (n) n.value = item.term;
          var a = document.getElementById("r-term-aliases"); if (a) a.value = (item.aliases || []).join(", ");
          var c = document.getElementById("r-term-case"); if (c) c.checked = Boolean(item.case_sensitive);
          var st = document.getElementById("r-term-strict");
          if (st) st.checked = item.strict_boundaries === null ? Boolean(item.case_sensitive) : Boolean(item.strict_boundaries);
          var cp = document.getElementById("r-term-compounds");
          if (cp) cp.checked = Boolean(item.match_compounds);
          selectTermDossier(item.dossier_id);
          setTermVariants(item.scoped_alternatives);
        });
        chipsContainer.appendChild(chip);
      });
    }
  }
  if (termsSection) {
    termsSection.addEventListener("toggle", function() {
      if (termsSection.open) loadTerms();
    });
  }
  if (termsManager) termsManager.addEventListener("toggle", function() {
    if (termsManager.open) loadTermDossiers();
  });
  function updatedTerm(previous, change) {
    var aliases = previous.aliases || [];
    return Object.assign({}, previous, {
      aliases: change.aliases === aliases.join(", ") ? aliases : change.aliases.split(",").map(function(alias) { return alias.trim(); }).filter(Boolean),
      scoped_alternatives: change.scopedAlternatives ?? previous.scoped_alternatives ?? [],
      case_sensitive: change.caseSensitive,
      strict_boundaries: previous.strict_boundaries != null || change.strict !== change.caseSensitive ? change.strict : null,
      match_compounds: change.matchCompounds,
      ...(change.dossierId === undefined ? {} : {dossier_id: change.dossierId})
    });
  }
  async function writeTermSettings(action) {
    var settings = document.getElementById("settings-form");
    var settingsToken = settings && settings.dataset.projectToken;
    var termName = document.getElementById("r-term-name").value.trim();
    if (!termName || termsWritePending) return;
    var value = context();
    var deleting = action.id === "r-term-delete-btn";
    var scopedAlternatives = deleting ? [] : readTermVariants();
    if (scopedAlternatives === null) return;
    // A failed catalogue read still permits other term edits and preserves the saved dossier link.
    var change = deleting ? null : {
      aliases: document.getElementById("r-term-aliases").value,
      scopedAlternatives: scopedAlternatives,
      caseSensitive: document.getElementById("r-term-case").checked,
      strict: document.getElementById("r-term-strict").checked,
      matchCompounds: document.getElementById("r-term-compounds").checked,
      dossierId: termDossierContext && same(termDossierContext, value) && !termDossier.disabled ? termDossier.value || null : undefined
    };
    var status = document.getElementById("r-term-status");
    var setStatus = window.LixityComponents.setStatus;
    function current() { return settings && settings.isConnected && settings.dataset.projectToken === settingsToken && live(value); }
    if (!settingsToken) {
      setStatus(status, label("settings_stale_context"), false);
      return;
    }
    termsWritePending = true;
    action.disabled = true;
    setStatus(status, label("settings_applying"), "loading");
    try {
      if (!termsReport || !termsContext || !same(termsContext, value)) await loadTerms();
      if (!current()) return;
      if (!termsReport || !termsContext || !same(termsContext, value)) {
        setStatus(status, label("settings_stale_context"), false);
        return;
      }
      var nextTerms = Object.create(null);
      termsReport.terms.forEach(function(item) {
        nextTerms[item.term] = {
          aliases: item.aliases || [],
          scoped_alternatives: item.scoped_alternatives || [],
          case_sensitive: item.case_sensitive,
          strict_boundaries: item.strict_boundaries,
          match_compounds: item.match_compounds,
          dossier_id: item.dossier_id,
          claim_id: item.claim_id
        };
      });
      if (change) nextTerms[termName] = updatedTerm(nextTerms[termName] || {}, change);
      else delete nextTerms[termName];
      var response = await bridge.post("settings", {terms: nextTerms, project_token: settingsToken});
      if (!current()) return;
      if (!response?.ok || !/^[a-f0-9]{64}$/.test(response.project_token) ||
          !/^[a-f0-9]{64}$/.test(response.manuscript_project_token)) {
        setStatus(status, response?.code === "stale-context" ? label("settings_stale_context") : bridge.errorText(response), false);
        return;
      }
      var tool = window.LixityResearchTools;
      var previous = tool && tool.context();
      settings.dataset.projectToken = response.project_token;
      document.body.dataset.manuscriptProjectToken = response.manuscript_project_token;
      document.querySelectorAll("#manuscript-pdf-form, #workspace-reader").forEach(function(host) {
        if (host.dataset.projectToken === value.project) host.dataset.projectToken = response.manuscript_project_token;
      });
      tool?.acceptTermSettings?.(previous);
      setStatus(status, label("settings_applied"), true);
      await loadTerms();
    } catch (_) {
      if (current()) setStatus(status, label("settings_connection_failed"), false);
    } finally {
      termsWritePending = false;
      action.disabled = false;
    }
  }
  document.addEventListener("click", async function(event) {
    if (event.target.closest("#r-terms-refresh")) {
      loadTerms();
      return;
    }
    if (!canWrite) return;
    var termAction = event.target.closest("#r-term-save-btn, #r-term-delete-btn");
    if (termAction) await writeTermSettings(termAction);
  });
  document.addEventListener("lixity:research-review", function(event) {
    reviewFilter = event.detail.filter;
    loadReview();
    if (termsSection && termsSection.open) loadTerms();
  });
  document.addEventListener("click", function(event) {
    if (!openingRelated && event.target.closest("[data-rtab]")) stopRelatedDestination();
    if (!window.LixityResearchTools && event.target.closest('[data-rtab="review"]')) {
      if (!openingRelated) reviewFilter = null;
      loadReview();
      if (termsSection && termsSection.open) loadTerms();
    } else if (event.target.closest("#r-review-refresh")) {
      loadReview();
      if (termsSection && termsSection.open) loadTerms();
    }
  }, true);
  document.addEventListener("lixity:paragraph-rendered", function(event) { enhance(event.detail); });
  document.addEventListener("lixity:reader-ready", function() { if (reviewSerial === 0) loadReview(true); });
  document.addEventListener("lixity:viewchange", function() {
    var pane = document.getElementById("view-pane-analysis");
    if (pane && pane.classList.contains("active") && !review) loadReview(true);
  });
  document.querySelectorAll("#chapters .ptext.open").forEach(enhance);
})();
