(function () {
  "use strict";
  var container = document.getElementById("workspace-reader");
  var bridge = window.LixityWorkspaceReader;
  if (!container || !bridge || !container.dataset.projectToken) return;
  var toggle = document.getElementById("workspace-reader-toggle");
  var panel = document.getElementById("workspace-reader-panel");
  var layout = document.getElementById("workspace-reader-layout");
  var colField = document.getElementById("workspace-reader-collection-field");
  var colSelect = document.getElementById("workspace-reader-collection");
  var select = document.getElementById("workspace-reader-dossier");
  var refresh = document.getElementById("workspace-reader-refresh");
  var close = document.getElementById("workspace-reader-close");
  var status = document.getElementById("workspace-reader-status");
  var body = document.getElementById("workspace-reader-body");
  if (!toggle) return;
  var enabled = false, requestSerial = 0, projectId = null, lastCatalogue = null, requestedDossier = null;
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
    if (colSelect) colSelect.disabled = value;
    panel.setAttribute("aria-busy", String(value));
  }
  function populateDossiers(result, selectedId) {
    var dossiers = result.dossiers || [];
    var collections = result.collections || result.dossier_collections || [];
    var unassignedIds = result.unassigned_dossier_ids || [];
    var selectedCol = colSelect ? (colSelect.value || "all") : "all";
    if (colField && colSelect) {
      colField.hidden = !collections.length;
      colSelect.replaceChildren();
      var allOpt = document.createElement("option");
      allOpt.value = "all";
      allOpt.textContent = bridge.label("research_dossier_collection_all");
      colSelect.appendChild(allOpt);
      collections.forEach(function(col) {
        var opt = document.createElement("option");
        opt.value = col.id;
        opt.textContent = col.name + " (" + (col.available_count || 0) + ")";
        colSelect.appendChild(opt);
      });
      var unassignedOpt = document.createElement("option");
      unassignedOpt.value = "unassigned";
      unassignedOpt.textContent = bridge.label("research_dossier_collection_unassigned") + " (" + unassignedIds.length + ")";
      colSelect.appendChild(unassignedOpt);
      if (selectedCol !== "all" && selectedCol !== "unassigned" && !collections.some(function(c) { return c.id === selectedCol; })) {
        selectedCol = "all";
      }
      if (selectedId && selectedCol !== "all") {
        var activeCheck = collections.find(function(c) { return c.id === selectedCol; });
        var inSelection = activeCheck
          ? (activeCheck.entries || []).some(function(e) { return e.status === "available" && e.dossier_id === selectedId; })
          : unassignedIds.includes(selectedId);
        if (!inSelection && dossiers.some(function(d) { return d.id === selectedId; })) {
          selectedCol = "all";
        }
      }
      colSelect.value = selectedCol;
    }
    var byId = Object.fromEntries(dossiers.map(function(d) { return [d.id, d]; }));
    var activeCollection = collections.find(function(c) { return c.id === selectedCol; }) || null;
    var visible = dossiers;
    if (activeCollection) {
      visible = (activeCollection.entries || []).filter(function(entry) { return entry.status === "available"; }).map(function(entry) { return byId[entry.dossier_id]; }).filter(Boolean);
    } else if (selectedCol === "unassigned") {
      var unassignedSet = new Set(unassignedIds);
      visible = dossiers.filter(function(d) { return unassignedSet.has(d.id); });
    }
    var placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = bridge.label("reader_choose");
    select.replaceChildren(placeholder);
    visible.forEach(function(dossier) {
      var option = document.createElement("option");
      option.value = dossier.id;
      option.textContent = dossier.title;
      select.appendChild(option);
    });
    select.value = visible.some(function(d) { return d.id === selectedId; }) ? (selectedId || "") : "";
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
    lastCatalogue = result;
    populateDossiers(result, selectedId);
    if (!(result.dossiers || []).length) { message(bridge.label("research_no_dossiers")); return; }
    await loadDossier(select.value);
  }
  function setEnabled(value, selectedId) {
    var alreadyOpen = enabled;
    // The display subscriber opens a newly requested tool. Retain the explicit
    // ID separately: its option may not exist until that catalogue arrives.
    requestedDossier = value && selectedId ? selectedId : null;
    window.LixityWorkbench.dispatch({type: "tool", value: value ? "dossier" : "none"});
    if (value && selectedId && alreadyOpen) openDossiers(selectedId);
    requestedDossier = null;
  }
  window.LixityWorkbench.subscribe(function(state, previous) {
    var active = state.contextTool === "dossier" && state.surface === "document";
    panel.hidden = !active;
    toggle.setAttribute("aria-expanded", String(active));
    if (active === enabled) return;
    enabled = active; ++requestSerial;
    if (active) openDossiers(requestedDossier || select.value);
    else pending(false);
    document.dispatchEvent(new CustomEvent("lixity:companion-change", {detail: active}));
  });
  toggle.disabled = false;
  toggle.addEventListener("click", function() { setEnabled(!enabled); });
  if (close) close.addEventListener("click", function() { setEnabled(false); toggle.focus(); });
  if (colSelect) colSelect.addEventListener("change", function() {
    if (!lastCatalogue) return;
    var previousDossier = select.value;
    populateDossiers(lastCatalogue, previousDossier);
    if (select.value !== previousDossier || !select.value) loadDossier(select.value);
  });
  select.addEventListener("change", function() { loadDossier(select.value); });
  refresh.addEventListener("click", function() { openDossiers(select.value); });
  panel.addEventListener("keydown", function(event) {
    if (window.LixityWorkbench.state().view !== "analysis" || event.key !== "Escape" || event.defaultPrevented) return;
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
    scrollAndFlash(panel);
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
