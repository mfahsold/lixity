// Research workspace: shared API access, form plumbing and escaping.
// Split of the former research.js; _JS_FILES concatenates the parts in
// the original order, so load-time behaviour is unchanged.
// Research workspace: sources, dossiers, claims, decisions, timeline and
// editorial review (extracted from dashboard.js).
function researchRecordLabel(record, kind) {
  return window.LixityComponents.recordLabel(record, uiLabel("research_name_unavailable_" + kind));
}

function researchDossierDisplayTags(tags) {
  return (Array.isArray(tags) ? tags : []).filter(function(tag) {
    return !/^manuscript-draft:[a-f0-9]{32}$/.test(tag);
  });
}

function researchPassageLabel(passage) {
  var title = researchRecordLabel({title: passage && passage.source_title}, "source");
  var quote = passage && passage.verbatim;
  return title + (typeof quote === "string" && quote.trim() ? " · “" + quote.trim().slice(0, 100) + (quote.trim().length > 100 ? "…" : "") + "”" : "");
}

// Names are presentation only. Identity, exact pins and context checks stay with
// the accepted API records; unavailable metadata never becomes a guessed name.
function researchReferenceChoices(kind, envelope) {
  var choices = [];
  if (kind === "claim") choices = Object.values(researchClaimChoices || {});
  if (kind === "dossier" && researchDossiersPayload && researchDossiersContext &&
      acceptResearchContext(researchDossiersContext, researchDossiersPayload)) {
    choices = researchDossiersPayload.dossiers || [];
  }
  if (kind === "passage") {
    choices = Object.entries(researchPassageContexts || {}).map(function(pair) {
      return Object.assign({}, pair[1], {id: pair[0]});
    });
    choices = choices.concat(((envelope && envelope.citations) || []).map(function(citation) {
      return Object.assign({}, citation, {id: citation.passage_id || citation.id});
    }));
  }
  if (kind === "claim" && envelope) {
    choices = choices.concat([envelope.from_claim, envelope.to_claim].filter(Boolean).map(function(claim) {
      return Object.assign({}, claim, {id: claim.claim_id});
    }));
  }
  return choices.filter(function(record) { return record && record.id; });
}

function researchReferenceLabel(kind, ref, envelope) {
  var candidates = researchReferenceChoices(kind, envelope).filter(function(record) { return record.id === ref.id; });
  var record = candidates.find(function(candidate) { return !ref.revision || candidate.revision === ref.revision; });
  return (kind === "passage" && record ? researchPassageLabel(record) : researchRecordLabel(record, kind)) +
    (ref.revision ? " · " + uiFormat("research_revision_number", {revision: ref.revision}) : "");
}

function disambiguateResearchOptions(field) {
  var counts = Object.create(null);
  Array.from(field.options).forEach(function(option) { counts[option.text] = (counts[option.text] || 0) + 1; });
  var positions = Object.create(null);
  Array.from(field.options).forEach(function(option) {
    var text = option.text;
    if (counts[text] > 1) {
      positions[text] = (positions[text] || 0) + 1;
      option.text += " · " + uiFormat("research_choice_number", {number:positions[text]});
    }
  });
}

function researchStatus(message, ok) {
  var text = ok === "loading" ? (message || uiLabel("research_loading")) : message;
  window.LixityComponents.setStatus("research-status-bar", text, ok, {prefix: true});
}

var researchStatusReads = new Map(), researchStatusReadContext = null;

function invalidateResearchStatusReads() {
  researchStatusReads.clear();
}

async function researchApiPost(action, payload) {
  payload = researchBoundPayload(payload);
  // Neither a pre-write read nor one started during the write can supply its refresh.
  invalidateResearchStatusReads();
  var data;
  try {
    data = await window.LixityComponents.postJson(API + "/" + action, payload || {});
  } finally {
    invalidateResearchStatusReads();
  }
  if (data.ok && ["research-ingest", "research-dossier", "research-claim-add", "research-decision-add"].includes(action)) {
    await refreshResearchProjectInfo();
  }
  return data;
}

function researchApiGet(endpoint, responseType, sharePending) {
  var isStatus = endpoint.split("?")[0] === "research/status";
  var token = researchContextToken();
  if (token) endpoint += (endpoint.includes("?") ? "&" : "?") + "research_token=" + encodeURIComponent(token);
  var url = API + "/" + endpoint;
  if (!isStatus) return jsonApi(url, undefined, responseType);
  // The research token identifies the exact root, including restored copies.
  var host = document.getElementById("manuscript-pdf-form") || document.getElementById("workspace-reader") || document.body;
  var project = host === document.body ? host.dataset.manuscriptProjectToken : host.dataset.projectToken;
  var context = JSON.stringify([token, project || "", document.body.dataset.manuscriptSourceSha256 || ""]);
  if (context !== researchStatusReadContext) {
    invalidateResearchStatusReads();
    researchStatusReadContext = context;
  }
  var key = JSON.stringify([context, url, responseType || null]);
  if (sharePending && researchStatusReads.has(key)) return researchStatusReads.get(key);
  // Ordinary reads replace the pending owner; automatic consumers may join only
  // while this exact observation is unfinished. No result survives settlement.
  var pending = jsonApi(url, undefined, responseType).finally(function() {
    if (researchStatusReads.get(key) === pending) researchStatusReads.delete(key);
  });
  researchStatusReads.set(key, pending);
  return pending;
}

function researchFormStatus(button, message, state) {
  var identifier = button.id + "-status";
  var status = document.getElementById(identifier);
  if (!status) {
    status = window.LixityComponents.el("p", {
      id: identifier,
      attrs: { role: "status", "aria-live": "polite" }
    });
    (button.closest(".row") || button).after(status);
  }
  window.LixityComponents.setStatus(status, message, state, { baseClass: "ctl-status research-form-status" });
}

function fieldSnapshot(identifiers) {
  return Object.fromEntries(identifiers.map(function(identifier) {
    var field = document.getElementById(identifier);
    return [identifier, field && field.multiple ? Array.from(field.selectedOptions).map(function(option) { return option.value; }) :
      field && field.type === "checkbox" ? field.checked : field ? field.value : ""];
  }));
}

async function submitResearchForm(button, action, payload, fields, clearFields, complete, refresh) {
  if (button.dataset.pending === "true") return;
  var submitted = fieldSnapshot(fields), context = researchReadContext();
  button.dataset.pending = "true";
  button.disabled = true;
  button.classList.add("busy");
  button.setAttribute("aria-busy", "true");
  researchFormStatus(button, uiLabel("form_saving"), "loading");
  try {
    var result = await researchApiPost(action, payload);
    if (!button.isConnected || !acceptResearchContext(context, result)) return;
    researchFormStatus(button, result.ok ? uiLabel(complete) : result.message || uiLabel("research_status_unavailable"), result.ok ? "ok" : "err");
    if (result.ok) {
      if (JSON.stringify(fieldSnapshot(fields)) === JSON.stringify(submitted)) {
        clearFields.forEach(function(identifier) {
          var field = document.getElementById(identifier);
          if (field._geographyEditor) field._geographyEditor.reset();
          else if (field.type === "checkbox") field.checked = false;
          else field.value = "";
        });
      }
      refresh();
    }
    return result;
  } finally {
    button.dataset.pending = "false";
    button.disabled = false;
    button.classList.remove("busy");
    button.removeAttribute("aria-busy");
  }
}

function researchContextToken() {
  var panel = document.getElementById("research-manager");
  return panel ? panel.dataset.researchToken || "" : "";
}

function researchBoundPayload(payload) {
  var token = researchContextToken();
  return token ? Object.assign({research_token: token}, payload || {}) : payload || {};
}

function escapeHtml(str) {
  if (typeof window !== "undefined" && window.LixityComponents && typeof window.LixityComponents.escapeHtml === "function") {
    return window.LixityComponents.escapeHtml(str);
  }
  return String(str == null ? "" : str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

