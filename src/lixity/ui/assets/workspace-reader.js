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
  var status = document.getElementById("workspace-reader-status");
  var body = document.getElementById("workspace-reader-body");
  var enabled = false, requestSerial = 0;
  function message(text, failed) {
    status.textContent = text;
    status.className = "ctl-status " + (failed ? "err" : "ok");
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
    body.replaceChildren();
    if (!id) { message(bridge.label("reader_choose"), false); pending(false); return; }
    pending(true);
    message(bridge.label("research_loading"), false);
    var result = await bridge.read(query(id));
    if (!enabled || serial !== requestSerial) return;
    pending(false);
    if (!result.ok || result.id !== id) {
      message(result.message || bridge.label("reader_error"), true);
      return;
    }
    var heading = document.createElement("h3");
    heading.textContent = result.title || bridge.label("reader_title");
    body.appendChild(heading);
    var content = document.createElement("div");
    content.innerHTML = bridge.renderDossier(result);
    body.appendChild(content);
    message(bridge.label("reader_saved") + " " + bridge.label("research_revision_number").replace("{revision}", result.revision || 1), false);
  }
  async function openDossiers(selectedId) {
    var serial = ++requestSerial;
    pending(true);
    body.replaceChildren();
    message(bridge.label("research_loading"), false);
    var result = await bridge.read(query());
    if (!enabled || serial !== requestSerial) return;
    pending(false);
    if (!result.ok) { message(result.message || bridge.label("reader_error"), true); return; }
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
    if (!(result.dossiers || []).length) { message(bridge.label("research_no_dossiers"), false); return; }
    select.value = selectedId || "";
    await loadDossier(select.value);
  }
  function setEnabled(value, selectedId) {
    enabled = value;
    ++requestSerial;
    panel.hidden = !value;
    layout.classList.toggle("is-open", value);
    toggle.setAttribute("aria-expanded", String(value));
    window.dispatchEvent(new Event("resize"));
    if (value) openDossiers(selectedId || select.value);
    else { pending(false); body.replaceChildren(); }
  }
  toggle.disabled = false;
  toggle.addEventListener("click", function() { setEnabled(!enabled); });
  select.addEventListener("change", function() { loadDossier(select.value); });
  refresh.addEventListener("click", function() { openDossiers(select.value); });
  panel.addEventListener("keydown", function(event) {
    if (event.key !== "Escape" || event.defaultPrevented) return;
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
