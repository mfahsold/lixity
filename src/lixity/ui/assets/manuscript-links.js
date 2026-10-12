(function () {
  "use strict";
  var bridge = window.LixityManuscriptLinks;
  var tokenHost = document.getElementById("manuscript-pdf-form") || document.getElementById("workspace-reader");
  if (!bridge || document.body.dataset.manuscriptLinks !== "1" || !tokenHost ||
      !tokenHost.dataset.projectToken || !bridge.contextToken() || !document.body.dataset.manuscriptSourceSha256) return;
  var draft = null, serial = 0, reviewSerial = 0, review = null, remembered = null, reviewProjectId = null;
  var pending = new Set(), dialog, picker, quotation, statement, consent, save, status;
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
    return {research: bridge.contextToken(), project: tokenHost.dataset.projectToken,
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
    picker.disabled = !draft || !draft.claims || writing;
    consent.disabled = !draft || !draft.claims || writing;
    save.disabled = !draft || !draft.claims || !picker.value || !consent.checked || !live(draft.context) || writing;
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
    picker = element("select", "", "ctl"); picker.id = "manuscript-link-claim"; body.appendChild(picker);
    statement = element("p", "", "ctl-note"); statement.id = "manuscript-link-statement"; body.appendChild(statement);
    var retention = element("label", "", "manuscript-link-retention");
    consent = element("input"); consent.type = "checkbox"; consent.id = "manuscript-link-retain";
    retention.append(consent, document.createTextNode(label("manuscript_link_retention"))); body.appendChild(retention);
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
  function unavailable(message) { status.textContent = message || label("manuscript_link_unavailable"); status.className = "ctl-status err"; }
  async function open(value) {
    createDialog(); var request = ++serial;
    draft = value; draft.key = JSON.stringify([value.context, value.anchor]);
    quotation.textContent = value.anchor.quote; consent.checked = false; statement.textContent = "";
    picker.replaceChildren(element("option", label("manuscript_link_choose"))); picker.firstChild.value = "";
    picker.disabled = true; status.className = "ctl-status loading"; status.textContent = label("research_loading"); updateSave();
    if (!dialog.open) dialog.showModal();
    var responses = await Promise.all([bridge.read("research/claims"),
      bridge.read("research/manuscript-review?project_token=" + encodeURIComponent(value.context.project))]);
    if (request !== serial || draft !== value || !dialog.open) return;
    if (!live(value.context)) { unavailable(); return; }
    var claims = responses[0], report = responses[1];
    if (!claims.ok || !report.ok || claims.schema_version !== "research-claims-local/2" ||
        report.schema_version !== "research-manuscript-review-local/1" || !claims.project_id ||
        claims.project_id !== report.project_id || !claims.snapshot || claims.snapshot !== report.snapshot ||
        report.current_source_sha256 !== value.context.source || report.source_state !== "available" || !validClaims(claims.claims) || !validRows(report.links)) {
      clearReview(claims.message || report.message); unavailable(claims.message || report.message); return;
    }
    draft.claims = claims.claims.filter(function(claim) { return claim.id && Number.isInteger(claim.revision) && claim.revision > 0; });
    draft.projectId = claims.project_id; draft.snapshot = claims.snapshot;
    draft.claims.forEach(function(claim) {
      var option = element("option", claim.title + " · " + label("research_revision_number").replace("{revision}", claim.revision));
      option.value = claim.id; picker.appendChild(option);
    });
    picker.disabled = false; status.className = "ctl-status"; status.textContent = label("manuscript_link_hint");
    ++reviewSerial; applyReview(report, value.context); updateSave(); picker.focus();
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
    var record = response && response.record, pin = record && record.claim_ref, anchor = record && record.anchor;
    if (!response || !response.ok || response.schema_version !== "research-manuscript-link-local/1" ||
        response.project_id !== submitted.projectId || !response.snapshot || !response.link_id ||
        response.claim_id !== claim.id || response.claim_revision !== claim.revision ||
        !record || record.id !== response.link_id || record.kind !== "manuscript_claim_link" ||
        !pin || pin.id !== claim.id || pin.revision !== claim.revision || !anchor ||
        !Object.keys(submitted.anchor).every(function(key) { return anchor[key] === submitted.anchor[key]; })) {
      unavailable(response && response.message); return;
    }
    dialog.close();
    var feedback = submitted.panel.querySelector(".manuscript-link-feedback");
    if (feedback) feedback.textContent = label("manuscript_link_saved");
    loadReview();
  }
  var reviewBox = element("details", "", "manuscript-link-review");
  reviewBox.appendChild(element("summary", label("manuscript_link_review")));
  var reviewBody = element("div"); reviewBox.appendChild(reviewBody); chapters.prepend(reviewBox);
  function applyReview(report, value) {
    if (!live(value)) return;
    review = report; reviewProjectId = report.project_id; reviewBody.replaceChildren();
    document.querySelectorAll("#chapters .ptext").forEach(function(panel) {
      var text = bridge.text(panel), points = Array.from(text || "");
      var spans = (report.links || []).filter(function(row) {
        var a = row.anchor;
        return row.anchor_state === "resolved" && a && row.resolved_start_line === Number(panel.dataset.start) &&
          row.resolved_end_line === Number(panel.dataset.end) && a.paragraph_sha256 === panel.dataset.paragraphSha256 &&
          Number.isInteger(a.start) && Number.isInteger(a.end) && a.start >= 0 && a.end > a.start && a.end <= points.length &&
          points.slice(a.start, a.end).join("") === a.quote;
      }).map(function(row) { return {start: points.slice(0, row.anchor.start).join("").length,
        end: points.slice(0, row.anchor.end).join("").length}; });
      bridge.marks(panel, spans);
    });
    (report.links || []).forEach(function(row) {
      var item = element("div", "", "manuscript-link-review-item");
      item.appendChild(element("p", (row.claim_title || row.claim_id) + " · " +
        label("research_revision_number").replace("{revision}", row.claim_revision)));
      var state = ["resolved", "moved", "ambiguous", "changed"].includes(row.anchor_state) ? row.anchor_state : "unavailable_anchor";
      var flags = [label("manuscript_link_" + state)];
      (row.flags || []).forEach(function(flag) {
        if (["source_changed", "claim_changed", "claim_withdrawn"].includes(flag)) flags.push(label("manuscript_link_" + flag));
      });
      item.appendChild(element("p", flags.join(" · "), "ctl-note"));
      if (row.anchor) item.appendChild(element("blockquote", row.anchor.quote));
      var history = element("button", label("research_revision_history"), "ctl"); history.type = "button";
      history.dataset.researchHistory = "claim"; history.dataset.recordId = row.claim_id; item.appendChild(history);
      reviewBody.appendChild(item);
    });
  }
  function clearReview(message) {
    review = null;
    document.querySelectorAll("#chapters .ptext").forEach(function(panel) { bridge.marks(panel, []); });
    reviewBody.replaceChildren(element("p", message || label("manuscript_link_unavailable"), "ctl-status err"));
  }
  async function loadReview() {
    var request = ++reviewSerial, value = context();
    var report = await bridge.read("research/manuscript-review?project_token=" + encodeURIComponent(value.project));
    if (request !== reviewSerial || !live(value)) return;
    if (!report.ok || report.schema_version !== "research-manuscript-review-local/1" || !validRows(report.links) ||
        !report.project_id || !report.snapshot || (reviewProjectId && report.project_id !== reviewProjectId) ||
        report.current_source_sha256 !== value.source || report.source_state !== "available") {
      clearReview(report.message); return;
    }
    applyReview(report, value);
  }
  function enhance(panel) {
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
    if (!review && reviewSerial === 0) loadReview();
  }
  var observedContext = context();
  var contextObserver = new MutationObserver(function() {
    var next = context(); if (same(next, observedContext)) return;
    observedContext = next; ++reviewSerial; reviewProjectId = null; remembered = null;
    clearReview(); if (draft) draft.claims = null;
    if (dialog && dialog.open) { unavailable(); updateSave(); }
  });
  [document.body, tokenHost, document.getElementById("research-manager")].forEach(function(host) {
    if (host) contextObserver.observe(host, {attributes: true, attributeFilter: ["data-project-token", "data-research-token", "data-manuscript-source-sha256"]});
  });
  document.addEventListener("selectionchange", function() {
    var value = selection();
    if (value) remembered = value;
    else if (window.getSelection() && !window.getSelection().isCollapsed) remembered = null;
  });
  document.addEventListener("keydown", function(event) {
    if (event.altKey && !event.ctrlKey && !event.metaKey && event.key.toLowerCase() === "l" && !(dialog && dialog.open)) {
      var value = selection(); if (value) { event.preventDefault(); open(value); }
    }
  });
  document.addEventListener("lixity:paragraph-rendered", function(event) { enhance(event.detail); });
  document.querySelectorAll("#chapters .ptext.open").forEach(enhance);
})();
