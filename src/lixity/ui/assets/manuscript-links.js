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
  var pending = new Set(), dialog, picker, quotation, statement, consent, save, status, filterInput;
  var chapters = document.getElementById("chapters");
  if (!chapters) return;
  function element(tag, text, className) {
    var node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function label(key) { return bridge.label(key); }
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
  }
  function createDialog() {
    if (dialog) return;
    dialog = element("dialog", "", "lixity-modal manuscript-link-dialog");
    dialog.id = "manuscript-link-dialog"; dialog.setAttribute("aria-labelledby", "manuscript-link-title");
    var card = element("div", "", "modal-card"), header = element("div", "", "modal-header");
    var title = element("h3", label("manuscript_link_action")); title.id = "manuscript-link-title";
    header.appendChild(title); card.appendChild(header);
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
    var formatNote = element("details", "", "ctl-note manuscript-link-format");
    formatNote.appendChild(element("summary", label("manuscript_link_format_7")));
    formatNote.appendChild(element("p", label("manuscript_link_retention_format")));
    body.appendChild(formatNote);
    status = element("p", "", "ctl-status"); status.id = "manuscript-link-status";
    status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite"); body.appendChild(status);
    card.appendChild(body);
    var footer = element("div", "", "modal-footer");
    var cancel = element("button", label("modal_cancel"), "ctl"); cancel.type = "button";
    cancel.addEventListener("click", function() { dialog.close(); });
    save = element("button", label("manuscript_link_save"), "ctl"); save.type = "button"; save.id = "manuscript-link-save";
    save.addEventListener("click", saveDraft); footer.append(cancel, save); card.appendChild(footer); dialog.appendChild(card); document.body.appendChild(dialog);
    picker.addEventListener("change", function() {
      var claim = draft && draft.claims && draft.claims.find(function(c) { return c.id === picker.value; });
      statement.textContent = claim ? claim.statement || "" : ""; updateSave();
    });
    consent.addEventListener("change", updateSave);
    dialog.addEventListener("close", function() { ++serial; draft = null; remembered = null; });
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
      (report.current_source_sha256 !== sourceSha || report.source_state !== "available"));
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
  if (reviewSection && reviewTabHost) {
    reviewSection.hidden = false;
    reviewTabHost.replaceChildren(element("p", label("research_loading"), "ctl-status loading"));
  }
  var reviewBox = element("details", "", "manuscript-link-review");
  reviewBox.appendChild(element("summary", label("manuscript_link_review")));
  var reviewBody = element("div"); reviewBox.appendChild(reviewBody); chapters.prepend(reviewBox);
  function matchesPanel(row, panel) {
    var a = row.anchor;
    if (row.anchor_state !== "resolved" || !a || row.resolved_start_line !== Number(panel.dataset.start) ||
        row.resolved_end_line !== Number(panel.dataset.end) || a.paragraph_sha256 !== panel.dataset.paragraphSha256) return false;
    var points = Array.from(bridge.text(panel) || "");
    return Number.isInteger(a.start) && Number.isInteger(a.end) && a.start >= 0 && a.end > a.start && a.end <= points.length &&
      points.slice(a.start, a.end).join("") === a.quote;
  }
  function linkedPanel(row) {
    return Array.from(chapters.querySelectorAll(".ptext")).find(function(panel) { return matchesPanel(row, panel); });
  }
  function renderReviewItems(report) {
    var fragment = document.createDocumentFragment();
    fragment.appendChild(element("p", label("manuscript_link_review_count").replace("{count}", String((report.links || []).length)), "ctl-note"));
    (report.links || []).forEach(function(row) {
      var item = element("div", "", "manuscript-link-review-item");
      item.appendChild(element("p", (row.claim_title || row.claim_id) + " · " +
        label("research_revision_number").replace("{revision}", row.claim_revision)));
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
      var history = element("button", label("research_claim_open"), "ctl"); history.type = "button";
      history.dataset.researchHistory = "claim"; history.dataset.recordId = row.claim_id; item.appendChild(history);
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
      fragment.appendChild(item);
    });
    if (!(report.links || []).length) fragment.appendChild(element("p", label("manuscript_link_review_empty"), "ctl-note"));
    return fragment;
  }
  function applyReview(report, value) {
    if (!live(value)) return;
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
    });
    var items = renderReviewItems(report);
    reviewBody.replaceChildren(items.cloneNode(true));
    if (reviewTabHost) reviewTabHost.replaceChildren(items);
  }
  function reviewNote(message, stale) {
    var note = element("p", message || label("manuscript_link_unavailable"), "ctl-status err");
    if (stale) note.appendChild(reloadButton());
    return note;
  }
  function clearReview(message, stale) {
    review = null;
    document.querySelectorAll("#chapters .ptext").forEach(function(panel) { bridge.marks(panel, []); });
    reviewBody.replaceChildren(reviewNote(message, stale));
    if (reviewTabHost) reviewTabHost.replaceChildren(reviewNote(message, stale));
  }
  async function loadReview(automatic) {
    var value = context();
    if (automatic && reviewPending && reviewPending.request === reviewSerial && same(reviewPending.context, value)) return;
    var request = ++reviewSerial, reading = {context: value, request: request};
    reviewPending = reading;
    try {
      // Archive absence is a normal project state. The status endpoint can
      // represent it without calling a review endpoint that requires setup.
      var archive = await bridge.read("research/status");
      if (request !== reviewSerial || !live(value)) return;
      if (!archive.ok || archive.initialized !== true) {
        clearReview(archive.ok && archive.initialized === false ? label("research_not_initialized") : bridge.errorText(archive));
        return;
      }
      var report = await bridge.read("research/manuscript-review?project_token=" + encodeURIComponent(value.project));
      if (request !== reviewSerial || !live(value)) return;
      if (!report.ok || report.schema_version !== "research-manuscript-review-local/1" || !validRows(report.links) ||
          !report.project_id || !report.snapshot || (reviewProjectId && report.project_id !== reviewProjectId) ||
          (archive.project_id && report.project_id !== archive.project_id) ||
          report.current_source_sha256 !== value.source || report.source_state !== "available") {
        var stale = staleReport(report, value.source) || report.code === "stale-context";
        clearReview(stale ? label("manuscript_link_stale") : bridge.errorText(report), stale); return;
      }
      applyReview(report, value);
    } finally {
      if (reviewPending === reading) reviewPending = null;
    }
  }
  function enhance(panel) {
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
      if (!value || value.panel !== panel || !live(value.context)) { feedback.textContent = label("manuscript_link_invalid"); return; }
      open(value);
    });
    if (!review && reviewSerial === 0) loadReview(true);
  }
  var observedContext = context();
  var contextObserver = new MutationObserver(function() {
    var next = context(); if (same(next, observedContext)) return;
    observedContext = next; ++reviewSerial; reviewProjectId = null; remembered = null; reviewPending = null;
    clearReview(); if (draft) draft.claims = null;
    if (dialog && dialog.open) { unavailable(); updateSave(); }
  });
  [document.body, tokenHost, document.getElementById("research-manager")].forEach(function(host) {
    if (host) contextObserver.observe(host, {attributes: true, attributeFilter: ["data-project-token", "data-manuscript-project-token", "data-research-token", "data-manuscript-source-sha256"]});
  });
  document.addEventListener("click", function(event) {
    if (event.target.closest("[data-manuscript-link-reload]")) { event.preventDefault(); window.location.reload(); }
  });
  document.addEventListener("click", async function(event) {
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
  document.addEventListener("click", function(event) {
    if (event.target.closest('[data-rtab="review"]') || event.target.closest("#r-review-refresh")) loadReview();
  }, true);
  document.addEventListener("lixity:paragraph-rendered", function(event) { enhance(event.detail); });
  document.addEventListener("lixity:reader-ready", function() { if (reviewSerial === 0) loadReview(true); });
  document.addEventListener("lixity:viewchange", function() {
    var pane = document.getElementById("view-pane-analysis");
    if (pane && pane.classList.contains("active") && !review) loadReview(true);
  });
  document.querySelectorAll("#chapters .ptext.open").forEach(enhance);
})();
