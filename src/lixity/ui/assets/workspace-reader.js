(function () {
  "use strict";
  var container = document.getElementById("workspace-reader");
  var bridge = window.LixityWorkspaceReader;
  if (!container || !bridge || !container.dataset.projectToken) return;
  var toggle = document.getElementById("workspace-reader-toggle");
  var panel = document.getElementById("workspace-reader-panel");
  var layout = document.getElementById("workspace-reader-layout");
  var select = document.getElementById("workspace-reader-dossier");
  var refresh = document.getElementById("workspace-reader-refresh");
  var close = document.getElementById("workspace-reader-close");
  var status = document.getElementById("workspace-reader-status");
  var body = document.getElementById("workspace-reader-body");
  var enabled = false, requestSerial = 0, projectId = null;
  function current(serial, projectToken, researchToken) {
    return enabled && serial === requestSerial && projectToken === container.dataset.projectToken &&
      researchToken === bridge.contextToken();
  }
  function message(text, state) {
    status.textContent = text;
    status.className = "ctl-status" + (state ? " " + state : "");
  }
  function pending(value) {
    select.disabled = refresh.disabled = value;
    panel.setAttribute("aria-busy", String(value));
  }
  function query(id) {
    var params = new URLSearchParams();
    params.set("project_token", container.dataset.projectToken);
    if (id) params.set("id", id);
    return "research/dossiers?" + params.toString();
  }
  async function loadDossier(id) {
    var serial = ++requestSerial;
    var projectToken = container.dataset.projectToken, researchToken = bridge.contextToken();
    body.replaceChildren();
    if (!id) { message(bridge.label("reader_choose")); pending(false); return; }
    pending(true);
    message(bridge.label("research_loading"), "loading");
    var result = await bridge.read(query(id));
    if (!current(serial, projectToken, researchToken)) return;
    pending(false);
    if (!result.ok || result.id !== id || (projectId && result.project_id !== projectId)) {
      message(bridge.errorText(result, bridge.label("reader_error")), "err");
      return;
    }
    var heading = document.createElement("h3");
    heading.textContent = result.title || bridge.label("reader_title");
    body.appendChild(heading);
    var content = document.createElement("div");
    content.innerHTML = bridge.renderDossier(result);
    body.appendChild(content);
    bridge.enhanceDossier(content, result, function() { return current(serial, projectToken, researchToken); });
    message(bridge.label("reader_saved") + " " + bridge.label("research_revision_number").replace("{revision}", result.revision || 1));
  }
  async function openDossiers(selectedId) {
    var serial = ++requestSerial;
    var projectToken = container.dataset.projectToken, researchToken = bridge.contextToken();
    pending(true);
    body.replaceChildren();
    message(bridge.label("research_loading"), "loading");
    var result = await bridge.read(query());
    if (!current(serial, projectToken, researchToken)) return;
    pending(false);
    if (!result.ok) { message(bridge.errorText(result, bridge.label("reader_error")), "err"); return; }
    projectId = result.project_id || null;
    var placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = bridge.label("reader_choose");
    select.replaceChildren(placeholder);
    (result.dossiers || []).forEach(function(dossier) {
      var option = document.createElement("option");
      option.value = dossier.id;
      option.textContent = dossier.title;
      select.appendChild(option);
    });
    if (!(result.dossiers || []).length) { message(bridge.label("research_no_dossiers")); return; }
    select.value = selectedId || "";
    await loadDossier(select.value);
  }
  function setEnabled(value, selectedId) {
    var anchor = window.LixityReader && window.LixityReader.capture();
    enabled = value;
    if (window.LixityWorkspaceNavigation) window.LixityWorkspaceNavigation.companion(value);
    ++requestSerial;
    panel.hidden = !value;
    layout.classList.toggle("is-open", value);
    var divider = document.getElementById("workspace-reader-divider");
    if (divider) divider.hidden = !value;
    toggle.setAttribute("aria-expanded", String(value));
    window.dispatchEvent(new Event("resize"));
    if (value) openDossiers(selectedId || select.value);
    else { pending(false); body.replaceChildren(); }
    document.dispatchEvent(new CustomEvent("lixity:companion-change", {detail: value}));
    if (window.LixityReader) window.LixityReader.restore(anchor);
  }
  toggle.disabled = false;
  toggle.addEventListener("click", function() { setEnabled(!enabled); });
  if (close) close.addEventListener("click", function() { setEnabled(false); toggle.focus(); });
  select.addEventListener("change", function() { loadDossier(select.value); });
  refresh.addEventListener("click", function() { openDossiers(select.value); });
  panel.addEventListener("keydown", function(event) {
    if (event.key !== "Escape" || event.defaultPrevented) return;
    if (event.target.closest("details[open]")) return;
    event.preventDefault();
    setEnabled(false);
    toggle.focus();
  });
  document.addEventListener("click", function(event) {
    var pin = event.target.closest("[data-workspace-dossier]");
    if (!pin) return;
    bridge.switchView("analysis");
    setEnabled(true, pin.dataset.workspaceDossier);
    container.scrollIntoView({block: "start", behavior: "smooth"});
    select.focus({preventScroll: true});
  });
})();

// The manuscript/dossier split offers the same operation by pointer or keyboard.
(function() {
  "use strict";
  var divider = document.getElementById("workspace-reader-divider");
  var layout = document.getElementById("workspace-reader-layout");
  if (!divider || !layout) return;
  var share = 62, dragging = false, anchor = null;
  try {
    var stored = Number(localStorage.getItem("lixity.manuscript.split"));
    if (stored >= 35 && stored <= 75) share = stored;
  } catch (_) { /* The split works without persistence. */ }
  function update(value) {
    share = Math.min(75, Math.max(35, value));
    layout.style.setProperty("--manuscript-share", share + "%");
    divider.setAttribute("aria-valuenow", String(Math.round(share)));
    try { localStorage.setItem("lixity.manuscript.split", String(share)); } catch (_) { /* Local display preference only. */ }
    window.dispatchEvent(new Event("resize"));
  }
  update(share);
  divider.addEventListener("keydown", function(event) {
    var next = event.key === "ArrowLeft" ? share - 5 : event.key === "ArrowRight" ? share + 5 :
      event.key === "Home" ? 35 : event.key === "End" ? 75 : null;
    if (next === null) return;
    event.preventDefault();
    anchor = window.LixityReader && window.LixityReader.capture();
    update(next);
    if (window.LixityReader) window.LixityReader.restore(anchor);
  });
  divider.addEventListener("pointerdown", function(event) {
    if (event.button !== 0) return;
    dragging = true; anchor = window.LixityReader && window.LixityReader.capture();
    divider.setPointerCapture(event.pointerId); event.preventDefault();
  });
  divider.addEventListener("pointermove", function(event) {
    if (!dragging) return;
    var rect = layout.getBoundingClientRect();
    update((event.clientX - rect.left) / rect.width * 100);
  });
  function finish() {
    if (!dragging) return;
    dragging = false;
    if (window.LixityReader) window.LixityReader.restore(anchor);
  }
  divider.addEventListener("pointerup", finish);
  divider.addEventListener("pointercancel", finish);
  divider.addEventListener("lostpointercapture", finish);
})();
