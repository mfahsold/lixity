// Research workspace: passage selection, evidence drafts, citations, Zotero.
// Split of the former research.js; _JS_FILES concatenates the parts in
// the original order, so load-time behaviour is unchanged.
var researchPassageContexts = Object.create(null);
var researchSelectionProjectId = null;
var researchProjectStatusRead = 0;
var researchEvidenceDraft = null;
var researchEvidenceReview = null;
var researchClaimChoices = Object.create(null);
var researchClaimsSnapshot = null;
var researchClaimsRead = 0;
var researchProjectionRead = 0;
var researchSearchRead = 0;
var researchRelationPending = false;

function researchReadContext() {
  return {projectId: researchSelectionProjectId, token: researchContextToken()};
}

function acceptResearchContext(context, data) {
  return context.projectId === researchSelectionProjectId && context.token === researchContextToken() &&
    (!data.project_id || data.project_id === researchSelectionProjectId);
}

function reviewedEvidenceClaim() {
  var field = document.getElementById("r-link-claim-select");
  var claim = field && researchClaimChoices[field.value];
  return claim && researchClaimsSnapshot ? {claimId: claim.id, revision: claim.revision,
    snapshot: researchClaimsSnapshot, projectId: researchSelectionProjectId, token: researchContextToken()} : null;
}

document.addEventListener("change", function(event) {
  if (event.target.id === "r-link-claim-select") researchEvidenceReview = reviewedEvidenceClaim();
});

function selectionPlainText(text) {
  var container = document.createElement("div");
  container.innerHTML = renderSafeMarkdown(text || "");
  return container.textContent.replace(/\s+/g, " ").trim();
}

function researchSourceSelection(host) {
  var detail = host && host._selectionDetail;
  var selection = window.getSelection();
  if (!detail || !host.isConnected || !host.getClientRects().length ||
      detail.projectId !== researchSelectionProjectId || !selection ||
      selection.rangeCount !== 1 || selection.isCollapsed) return null;
  var range = selection.getRangeAt(0);
  function element(node) {return node.nodeType === 1 ? node : node.parentElement;}
  var start = element(range.startContainer), end = element(range.endContainer);
  var root = start && start.closest(".research-source-doc-rendered, .research-source-doc-raw");
  if (!root || !host.contains(root) || root.hidden || !root.getClientRects().length ||
      !end || end.closest(".research-source-doc-rendered, .research-source-doc-raw") !== root) return null;
  var quote = range.toString().trim();
  if (!quote) return null;
  var candidates;
  if (root.classList.contains("research-source-doc-raw")) {
    var prefix = document.createRange();
    prefix.selectNodeContents(root); prefix.setEnd(range.startContainer, range.startOffset);
    var first = Array.from(prefix.toString()).length;
    // API passage offsets count Unicode codepoints, rather than UTF-16 units.
    var last = first + Array.from(range.toString()).length;
    candidates = detail.passages.filter(function(passage) {
      return passage.start <= first && passage.end >= last;
    });
  } else {
    var block = start.closest("p, li, pre, h1, h2, h3, h4, h5, h6");
    if (!block || !root.contains(block) || end.closest("p, li, pre, h1, h2, h3, h4, h5, h6") !== block) return null;
    var context = block.textContent.replace(/\s+/g, " ").trim();
    var selected = quote.replace(/\s+/g, " ");
    candidates = detail.passages.filter(function(passage) {
      return passage.plain.indexOf(selected) >= 0 && passage.plain.indexOf(context) >= 0;
    });
  }
  if (candidates.length !== 1) return null;
  return {passage: candidates[0], quote: quote, detail: detail};
}

function clearResearchSourceSelections() {
  document.querySelectorAll(".selection-toolbar").forEach(function(toolbar) {
    toolbar.querySelector(".selection-use").disabled = true;
    toolbar.querySelector(".selection-reading").textContent = uiLabel("selection_hint");
  });
}

function updateResearchSourceSelection() {
  document.querySelectorAll(".selection-toolbar").forEach(function(toolbar) {
    var selected = researchSourceSelection(toolbar.parentElement);
    toolbar.querySelector(".selection-use").disabled = !selected;
    toolbar.querySelector(".selection-reading").textContent = uiLabel(selected ? "selection_ready" : "selection_invalid");
  });
}
document.addEventListener("selectionchange", updateResearchSourceSelection);
document.addEventListener("pointerdown", function(event) {
  if (event.target.closest(".selection-use")) event.preventDefault();
});

function researchEvidenceDraftHost() {
  var passage = document.getElementById("r-link-passage-id");
  if (!passage) return null;
  var host = document.getElementById("research-evidence-draft");
  if (!host) {
    host = document.createElement("div"); host.id = "research-evidence-draft";
    host.className = "selection-draft"; host.hidden = true;
    host.setAttribute("aria-live", "polite");
    passage.parentElement.before(host);
    var technical = document.createElement("details"); technical.className = "selection-technical";
    var summary = document.createElement("summary"); summary.textContent = uiLabel("selection_identifier");
    technical.appendChild(summary); passage.before(technical); technical.appendChild(passage);
  }
  return host;
}

function discardResearchEvidenceDraft() {
  researchEvidenceDraft = null;
  researchEvidenceReview = null;
  var passage = document.getElementById("r-link-passage-id");
  if (passage) passage.value = "";
  var host = document.getElementById("research-evidence-draft");
  if (host) {host.replaceChildren(); host.hidden = true;}
}
document.addEventListener("input", function(event) {
  if (event.target.id !== "r-link-passage-id" || !researchEvidenceDraft ||
      event.target.value.trim() === researchEvidenceDraft.passageId) return;
  researchEvidenceDraft = null;
  var host = document.getElementById("research-evidence-draft");
  if (host) {host.replaceChildren(); host.hidden = true;}
});

function prepareResearchEvidenceDraft(passageId, quote, context) {
  var passage = document.getElementById("r-link-passage-id");
  var host = researchEvidenceDraftHost();
  if (!passage || !host || !context || context.availability === "withdrawn" || context.error) return;
  if (context.project_id && context.project_id !== researchSelectionProjectId) return;
  researchEvidenceDraft = {passageId: passageId, projectId: researchSelectionProjectId, token: researchContextToken(),
    sourceSnapshot: context.snapshot || null};
  if (!researchEvidenceReview) researchEvidenceReview = reviewedEvidenceClaim();
  passage.value = passageId;
  host.replaceChildren(); host.hidden = false;
  function field(tag, className, value) {
    var node = document.createElement(tag); node.className = className;
    node.textContent = value; host.appendChild(node);
  }
  field("p", "ctl-note", context.source_title || "");
  if (quote) {
    field("strong", "selection-label", uiLabel("selection_quote"));
    field("blockquote", "selection-quote", quote);
  }
  field("strong", "selection-label", uiLabel("selection_context"));
  field("blockquote", "selection-context", context.verbatim || "");
  field("p", "ctl-note", uiLabel("selection_pin_help"));
  var discard = document.createElement("button"); discard.type = "button"; discard.className = "ctl";
  discard.textContent = uiLabel("selection_clear");
  discard.addEventListener("click", discardResearchEvidenceDraft); host.appendChild(discard);
  switchActiveView("research");
  document.querySelector('[data-rtab="claims"]').click();
  revealDisclosures(document.getElementById("r-link-claim-select"));
  document.getElementById("r-link-claim-select").focus();
}

researchEvidenceDraftHost();
document.addEventListener("click", function(event) {
  var button = event.target.closest(".selection-use");
  if (!button || button.disabled) return;
  var selected = researchSourceSelection(button.closest(".research-details-body"));
  if (!selected) {clearResearchSourceSelections(); return;}
  prepareResearchEvidenceDraft(selected.passage.id, selected.quote, {
    source_title: selected.detail.title, verbatim: selected.passage.verbatim, availability: "available"});
  clearResearchSourceSelections();
});

function researchPassageActions(passageId, context) {
  if (context) researchPassageContexts[passageId] = context;
  return '<div class="row research-passage-actions">' +
    '<button type="button" class="ctl" data-use-passage="claim" data-passage-id="' + escapeHtml(passageId) + '">' + escapeHtml(uiLabel("research_use_for_claim")) + '</button>' +
    '<button type="button" class="ctl" data-use-passage="dossier" data-passage-id="' + escapeHtml(passageId) + '">' + escapeHtml(uiLabel("research_use_for_dossier")) + '</button></div>';
}

function researchCitationHtml(cite, interactive) {
  var unavailable = Boolean(cite.error) || !["available", "withdrawn"].includes(cite.availability);
  var withdrawn = cite.availability === "withdrawn";
  var availability = unavailable ? uiLabel("research_evidence_unavailable") : (withdrawn ? uiLabel("research_evidence_withdrawn_context") : uiLabel("research_evidence_retained_unreviewed"));
  return '<div class="research-passage-card">' +
    '<span class="research-badge ' + (unavailable || withdrawn ? 'badge-warning' : 'badge-neutral') + '">' + escapeHtml(availability) + '</span>' +
    '<div class="ctl-note">' + escapeHtml(cite.source_title || cite.passage_id || cite.id || "") + '</div>' +
    '<div class="research-passage-quote">' + (!unavailable && cite.verbatim ? escapeHtml(cite.verbatim) : escapeHtml(uiLabel("research_no_quote"))) + '</div>' +
    (cite.passage_id ? '<code>' + escapeHtml(cite.passage_id) + '</code>' : '') +
    (cite.evidence_link_id ? '<div class="ctl-note">' + escapeHtml(uiLabel("research_revision_kind_evidence_link")) + ': ' +
      escapeHtml(cite.evidence_link_id) + ' · ' + escapeHtml(uiFormat("research_revision_number", {revision: cite.evidence_link_revision})) +
      ' · ' + escapeHtml(uiLabel("research_revision_kind_claim")) + ' · ' +
      escapeHtml(uiFormat("research_revision_number", {revision: cite.claim_revision})) + '</div>' : '') +
    (interactive !== false && !unavailable && !withdrawn && cite.passage_id ? researchPassageActions(cite.passage_id, cite) : '') +
    '</div>';
}

function researchDetailsControl(kind, id) {
  return '<details class="research-details"><summary data-research-detail="' + kind + '" data-record-id="' + escapeHtml(id) + '">' + escapeHtml(uiLabel("research_view_details")) + '</summary><div class="research-details-body"></div></details>';
}

function researchRevisionActions(kind, id) {
  var attrs = ' data-record-id="' + escapeHtml(id) + '"';
  return '<div class="research-record-actions">' +
    '<button type="button" class="ctl" data-research-revise="' + kind + '"' + attrs + '>' + escapeHtml(uiLabel("research_revision_edit")) + '</button>' +
    '<button type="button" class="ctl" data-research-history="' + kind + '"' + attrs + '>' + escapeHtml(uiLabel("research_revision_history")) + '</button>' +
    '</div>';
}

// Zotero remains an external catalogue. Only explicit captures enter evidence storage.
var zoteroProjectId = null;
var zoteroSelection = null;
var zoteroNextRequest = null;
var zoteroRequestSerial = 0;

function zoteroLibraryIdentity(library) {
  return /^users\/(0|[1-9]\d*)$/.test(library || "") ? "users/0" : library;
}

function zoteroOpenLink(library, key, quiet) {
  if (!/^[A-Z0-9]{8}$/.test(key || "") || !/^(users\/\d+|groups\/[1-9]\d*)$/.test(library || "")) return "";
  var prefix = library.startsWith("groups/") ? library : "library";
  var href = 'zotero://select/' + prefix + '/items/' + key;
  if (quiet) {
    // Dense lists show a quiet catalogue link instead of a button on every card.
    return '<a class="research-zotero-link" href="' + href + '" title="' +
      escapeHtml(uiLabel("zotero_open")) + '">' + escapeHtml(uiLabel("zotero_open")) + ' ↗</a>';
  }
  return '<a class="ctl" href="' + href + '">' + escapeHtml(uiLabel("zotero_open")) + '</a>';
}

function clearZoteroSelection() {
  zoteroRequestSerial++;
  zoteroSelection = null;
  zoteroNextRequest = null;
  var host = document.getElementById("r-zotero-results");
  if (host) {
    if (window.LixityZoteroResults) window.LixityZoteroResults.clear(host);
    else host.textContent = "";
  }
  var retention = document.getElementById("r-zotero-retention");
  if (retention) retention.checked = false;
}

function zoteroSetMessage(host, text) {
  // Messages render through the component as well: writing text nodes next to
  // a preact tree leaves residues that the next patch cannot account for.
  window.LixityZoteroResults.render(host, {message: text});
}

async function browseZotero(request) {
  var serial = ++zoteroRequestSerial;
  var host = document.getElementById("r-zotero-results");
  zoteroSetMessage(host, uiLabel("research_loading"));
  var result = await researchApiPost("research-zotero", request);
  if (serial !== zoteroRequestSerial || request.project_id !== zoteroProjectId) return;
  if (!result.ok) { zoteroSetMessage(host, result.message || uiLabel("research_search_failed")); return; }
  zoteroSelection = {request: request, result: result};
  zoteroNextRequest = result.next_start === null || result.next_start === undefined ? null : Object.assign({}, request, {start: result.next_start});
  var items = (result.attachments || result.items || []).map(function(item) {
    var capture = (result.captures || []).find(function(c) {
      return c.server_id === result.server_id && zoteroLibraryIdentity(c.library) === zoteroLibraryIdentity(request.library) && c.attachment_key === item.key;
    });
    return {key: item.key, version: item.version, data: item.data || {}, capture: capture || null};
  });
  if (!items.length && !result.item) {
    zoteroSetMessage(host, uiCountFormat("research_hits_count", 0));
    return;
  }
  // Rendering lives in the component layer (assets/zotero-results.js).
  window.LixityZoteroResults.render(host, {
    library: request.library,
    item: result.item || null,
    items: items,
    serverId: result.server_id || null,
    next: zoteroNextRequest !== null,
  });
}

document.addEventListener("change", function(event) {
  if (["r-zotero-library", "r-zotero-collection"].includes(event.target.id)) {
    clearZoteroSelection();
    if (event.target.id === "r-zotero-library") {
      document.getElementById("r-zotero-collection").innerHTML = '<option value="">' + escapeHtml(uiLabel("zotero_all")) + '</option>';
      document.getElementById("r-zotero-collections").dataset.start = "0";
    }
  }
});

document.addEventListener("click", async function(event) {
  var button = event.target.closest("#r-zotero-browse, #r-zotero-collections, #r-zotero-more, [data-zotero-item], [data-zotero-capture]");
  if (!button || button.disabled || !zoteroProjectId) return;
  button.disabled = true;
  try {
    var request = {project_id: zoteroProjectId, library: document.getElementById("r-zotero-library").value.trim()};
    if (button.id === "r-zotero-collections") {
      request.mode = "collections";
      request.start = Number(button.dataset.start || 0);
      var collections = await researchApiPost("research-zotero", request);
      if (!collections.ok) { researchStatus(collections.message, false); return; }
      if (request.project_id !== zoteroProjectId || request.library !== document.getElementById("r-zotero-library").value.trim()) return;
      var select = document.getElementById("r-zotero-collection");
      if (!request.start) select.innerHTML = '<option value="">' + escapeHtml(uiLabel("zotero_all")) + '</option>';
      (collections.collections || []).forEach(function(c) { select.add(new Option(c.data.name, c.key)); });
      button.dataset.start = String(collections.next_start || 0);
      button.textContent = uiLabel(collections.next_start ? "zotero_more" : "zotero_collections");
    } else if (button.id === "r-zotero-browse") {
      request.query = document.getElementById("r-zotero-query").value.trim();
      request.collection_key = document.getElementById("r-zotero-collection").value || null;
      await browseZotero(request);
    } else if (button.id === "r-zotero-more") {
      if (zoteroNextRequest) await browseZotero(zoteroNextRequest);
    } else if (zoteroSelection) {
      var selection = zoteroSelection;
      var items = selection.result.attachments || selection.result.items || [];
      var item = items[Number(button.dataset.zoteroItem || button.dataset.zoteroCapture)];
      if (!item) return;
      if (button.hasAttribute("data-zotero-item")) {
        await browseZotero({project_id: selection.request.project_id, library: selection.request.library, item_key: item.key});
      } else {
        if (!document.getElementById("r-zotero-retention").checked) { researchStatus(uiLabel("research_retention_required"), false); return; }
        var captured = (selection.result.captures || []).find(function(c) {
          return c.server_id === selection.result.server_id && zoteroLibraryIdentity(c.library) === zoteroLibraryIdentity(selection.request.library) && c.attachment_key === item.key;
        });
        var response = await researchApiPost("research-zotero-ingest", {project_id: selection.request.project_id,
          library: selection.request.library, attachment_key: item.key, expected_server_id: selection.result.server_id,
          source_id: captured ? captured.source_id : null, allow_retention: true});
        if (selection.request.project_id !== zoteroProjectId) return;
        var captureMessage = response.ok ? uiLabel("research_ingest_complete") : response.message;
        if (response.ok && Array.isArray(response.warnings) && response.warnings.length) {
          captureMessage += " " + response.warnings.join(" ");
        }
        researchStatus(captureMessage, response.ok);
        if (response.ok) {
          document.getElementById("r-zotero-retention").checked = false;
          await refreshResearchSources(null, null, true);
          await browseZotero(selection.request);
        }
      }
    }
  } finally { button.disabled = false; }
});

