// Research workspace: shared API access, form plumbing and escaping.
// Split of the former research.js; _JS_FILES concatenates the parts in
// the original order, so load-time behaviour is unchanged.
// Research workspace: sources, dossiers, claims, decisions, timeline and
// editorial review (extracted from dashboard.js).
function researchStatus(message, ok) {
  var el = document.getElementById("research-status-bar");
  if (!el) return;
  if (ok === "loading") {
    el.className = "ctl-status loading";
    el.textContent = message || uiLabel("research_loading");
  } else if (!message) {
    el.className = "ctl-status";
    el.textContent = "";
  } else {
    var isOk = Boolean(ok);
    el.className = "ctl-status " + (isOk ? "ok" : "err");
    el.textContent = (isOk ? "✓ " : "✗ ") + message;
  }
}

async function researchApiPost(action, payload) {
  payload = researchBoundPayload(payload);
  var data = await jsonApi(API + "/" + action, {method: "POST",
    headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload || {})});
  if (data.ok && ["research-ingest", "research-dossier", "research-claim-add", "research-decision-add"].includes(action)) {
    await refreshResearchProjectInfo();
  }
  return data;
}

function researchApiGet(endpoint, responseType) {
  var token = researchContextToken();
  if (token) endpoint += (endpoint.includes("?") ? "&" : "?") + "research_token=" + encodeURIComponent(token);
  return jsonApi(API + "/" + endpoint, undefined, responseType);
}

function researchFormStatus(button, message, state) {
  var identifier = button.id + "-status";
  var status = document.getElementById(identifier);
  if (!status) {
    status = document.createElement("p");
    status.id = identifier;
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    (button.closest(".row") || button).after(status);
  }
  status.className = "ctl-status research-form-status" + (state ? " " + state : "");
  status.textContent = message || "";
}

function fieldSnapshot(identifiers) {
  return Object.fromEntries(identifiers.map(function(identifier) {
    var field = document.getElementById(identifier);
    return [identifier, field && field.type === "checkbox" ? field.checked : field ? field.value : ""];
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
  var div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

