// Native collection editing; read-only catalogues keep only their shared filter.
var researchCollectionEditor = {context: null, id: "", entries: [], payload: null, pending: false};
var researchCollectionFields = ["r-dos-col-id", "r-dos-col-name", "r-dos-col-dossiers"];

function researchCollectionMembers() {
  var field = document.getElementById("r-dos-col-dossiers");
  return field && field.value ? field.value.split(",").map(function(id) { return id.trim(); }).filter(Boolean) : [];
}

function researchCollectionDirty() {
  return researchCollectionFields.some(function(id) {
    var field = document.getElementById(id);
    return field && field.value !== field.defaultValue;
  });
}

function researchCollectionContextCurrent() {
  return researchCollectionEditor.context && acceptResearchContext(researchCollectionEditor.context, {});
}

function resetResearchCollectionEditor(collection) {
  researchCollectionEditor.context = researchReadContext();
  researchCollectionEditor.id = collection ? collection.id : "";
  researchCollectionEditor.entries = collection ? collection.entries || [] : [];
  researchCollectionEditor.payload = researchDossiersPayload;
  var values = [collection ? collection.id : "", collection ? collection.name : "",
    collection ? (collection.dossier_ids || []).join(", ") : ""];
  researchCollectionFields.forEach(function(id, index) {
    var field = document.getElementById(id);
    if (field) field.value = field.defaultValue = values[index];
  });
  ["r-dos-col-save-btn", "r-dos-col-delete-btn"].forEach(function(id) {
    var button = document.getElementById(id);
    if (button) researchFormStatus(button, "", "");
  });
  updateResearchCollectionEditor();
}

function updateResearchCollectionEditor() {
  var host = document.getElementById("r-dos-col-members");
  if (!host) return;
  var state = researchCollectionEditor, ids = researchCollectionMembers();
  var current = Boolean(researchCollectionContextCurrent()), blocked = state.pending || !current;
  var name = document.getElementById("r-dos-col-name");
  document.getElementById("r-dos-col-heading").textContent = state.id
    ? uiFormat("research_dossier_collection_editing", {name: name.value}) : uiLabel("research_dossier_collection_new");
  var notice = document.getElementById("r-dos-col-context");
  notice.hidden = current || !state.context;
  notice.textContent = notice.hidden ? "" : uiLabel("research_dossier_collection_context_changed");
  var data = state.payload || {}, dossiers = data.dossiers || [];
  var picker = document.getElementById("r-dos-col-picker"), chosen = picker.value;
  var available = dossiers.filter(function(dossier) { return !ids.includes(dossier.id); });
  picker.replaceChildren(new Option(uiLabel(available.length ? "research_dossier_collection_choose" : "research_dossier_collection_no_available"), "", true, true));
  available.forEach(function(dossier) { picker.add(new Option(researchRecordLabel(dossier, "dossier"), dossier.id)); });
  if (available.some(function(dossier) { return dossier.id === chosen; })) picker.value = chosen;
  document.getElementById("r-dos-col-count").textContent = ids.length
    ? uiCountFormat("research_dossier_collection_selected_count", ids.length) : uiLabel("research_dossier_collection_selection_empty");
  host.replaceChildren();
  ids.forEach(function(id, index) {
    var entry = state.entries.find(function(item) { return item.dossier_id === id; });
    var dossier = dossiers.find(function(item) { return item.id === id; });
    var title = researchRecordLabel(dossier || entry, "dossier");
    var row = document.createElement("li"); row.dataset.colMemberId = id;
    var position = document.createElement("span"); position.className = "research-collection-position"; position.textContent = String(index + 1);
    var text = document.createElement("span"); text.className = "research-collection-member-title"; text.textContent = title;
    if (!dossier) {
      var unavailable = document.createElement("small"); unavailable.className = "ctl-note";
      unavailable.textContent = uiLabel("research_dossier_collection_missing"); text.appendChild(unavailable);
    }
    var actions = document.createElement("span"); actions.className = "research-collection-member-actions";
    [["up", "↑", index === 0], ["down", "↓", index === ids.length - 1], ["remove", "×", false]].forEach(function(spec) {
      var button = document.createElement("button"); button.type = "button"; button.className = "ctl";
      button.dataset.colAction = spec[0]; button.textContent = spec[1];
      button.title = uiFormat("research_dossier_collection_" + (spec[0] === "remove" ? "remove" : "move_" + spec[0]), {title: title});
      button.setAttribute("aria-label", button.title); button.disabled = blocked || spec[2]; actions.appendChild(button);
    });
    row.append(position, text, actions); host.appendChild(row);
  });
  // A stale draft remains readable to the shared unsaved-work guard and copyable.
  name.disabled = state.pending;
  name.readOnly = !current;
  picker.disabled = blocked || !available.length;
  document.getElementById("r-dos-col-add-btn").disabled = blocked || !picker.value;
  document.getElementById("r-dos-col-save-btn").disabled = blocked || !name.value.trim();
  document.getElementById("r-dos-col-delete-btn").disabled = blocked || !state.id;
  document.getElementById("r-dos-col-new-btn").disabled = state.pending;
  var filter = document.getElementById("r-dos-collection-select");
  if (filter) filter.disabled = state.pending;
}

function refreshResearchCollectionEditor(data) {
  var state = researchCollectionEditor;
  if (!state.context || (!researchCollectionContextCurrent() && !researchCollectionDirty())) {
    resetResearchCollectionEditor(null);
  } else if (researchCollectionContextCurrent()) {
    state.payload = data;
    if (!researchCollectionDirty() && !state.pending) {
      var collections = data.collections || data.dossier_collections || [];
      resetResearchCollectionEditor(collections.find(function(collection) { return collection.id === state.id; }) || null);
    } else updateResearchCollectionEditor();
  } else updateResearchCollectionEditor();
}

function newResearchCollectionId() {
  var collections = (researchDossiersPayload && (researchDossiersPayload.collections || researchDossiersPayload.dossier_collections)) || [];
  var id;
  do {
    var random = window.crypto.randomUUID ? window.crypto.randomUUID().replace(/-/g, "") :
      Array.from(window.crypto.getRandomValues(new Uint32Array(4))).map(function(value) { return value.toString(16).padStart(8, "0"); }).join("");
    id = "collection-" + random;
  } while (collections.some(function(collection) { return collection.id === id; }));
  return id;
}

function selectResearchCollectionEditor(event, chosen) {
  if (chosen && !researchCollectionEditor.pending) {
    if (researchCollectionDirty() && !window.confirm(uiLabel("research_dossier_collection_discard_confirm"))) {
      event.target.value = researchCollectionEditor.id || "all";
    } else resetResearchCollectionEditor(chosen);
  }
}

document.addEventListener("change", function(event) {
  if (event.target.id === "r-dos-col-picker") updateResearchCollectionEditor();
});

document.addEventListener("input", function(event) {
  if (event.target.id === "r-dos-col-name") updateResearchCollectionEditor();
});

document.addEventListener("click", async function(event) {
  var state = researchCollectionEditor;
  var newButton = event.target.closest("#r-dos-col-new-btn");
  if (newButton) {
    if (state.pending || (researchCollectionDirty() && !window.confirm(uiLabel("research_dossier_collection_discard_confirm")))) return;
    resetResearchCollectionEditor(null);
    var filter = document.getElementById("r-dos-collection-select");
    if (filter) filter.value = "all";
    renderResearchDossiersView(researchDossiersPayload);
    document.getElementById("r-dos-col-name").focus();
    return;
  }
  var memberAction = event.target.closest("[data-col-action]");
  var addButton = event.target.closest("#r-dos-col-add-btn");
  if (memberAction || addButton) {
    if (state.pending || !researchCollectionContextCurrent()) { updateResearchCollectionEditor(); return; }
    var ids = researchCollectionMembers(), focusId, action = memberAction && memberAction.dataset.colAction;
    if (addButton) {
      var picker = document.getElementById("r-dos-col-picker");
      if (!picker.value || ids.includes(picker.value)) return;
      ids.push(picker.value); picker.value = "";
    } else {
      focusId = memberAction.closest("[data-col-member-id]").dataset.colMemberId;
      var index = ids.indexOf(focusId), offset = action === "up" ? -1 : 1;
      if (action === "remove") ids.splice(index, 1);
      else if (index + offset >= 0 && index + offset < ids.length) {
        ids.splice(index, 1); ids.splice(index + offset, 0, focusId);
      }
    }
    document.getElementById("r-dos-col-dossiers").value = ids.join(", ");
    updateResearchCollectionEditor();
    var focusRow = Array.from(document.querySelectorAll("#r-dos-col-members [data-col-member-id]")).find(function(row) { return row.dataset.colMemberId === focusId; });
    if (focusRow) {
      var focusAction = focusRow.querySelector('[data-col-action="' + action + '"]');
      if (focusAction.disabled) focusAction = focusRow.querySelector("button:not(:disabled)");
      if (focusAction) focusAction.focus();
    } else document.getElementById("r-dos-col-name").focus();
    return;
  }
  var button = event.target.closest("#r-dos-col-save-btn, #r-dos-col-delete-btn");
  if (!button || state.pending) return;
  if (!researchCollectionContextCurrent()) { updateResearchCollectionEditor(); return; }
  var deleting = button.id === "r-dos-col-delete-btn", name = document.getElementById("r-dos-col-name");
  if (deleting && (!state.id || !window.confirm(uiFormat("research_dossier_collection_delete_confirm", {name: name.value})))) return;
  if (!deleting && (!name.value.trim() || !name.reportValidity())) return;
  var idField = document.getElementById("r-dos-col-id");
  if (!deleting && !idField.value) idField.value = newResearchCollectionId();
  var payload = {action: deleting ? "delete_collection" : "save_collection", collection_id: idField.value};
  if (!deleting) { payload.name = name.value.trim(); payload.dossier_ids = researchCollectionMembers(); }
  var submitted = fieldSnapshot(researchCollectionFields), context = researchReadContext();
  state.pending = true;
  try {
    // The shared submitter rejects disabled triggers. Let it claim the
    // button before disabling the rest of the editor.
    var pending = submitResearchForm(button, "research-dossier", payload, researchCollectionFields, [], "research_dossier_complete", function() {});
    updateResearchCollectionEditor();
    var result = await pending;
    if (!result || !result.ok || !acceptResearchContext(context, result)) return;
    if (JSON.stringify(fieldSnapshot(researchCollectionFields)) === JSON.stringify(submitted)) {
      if (deleting) resetResearchCollectionEditor(null);
      else {
        state.id = payload.collection_id;
        researchCollectionFields.forEach(function(id) { var field = document.getElementById(id); field.defaultValue = field.value; });
      }
    }
    // Collection writes return their filtered view; the chooser needs the full catalogue.
    var refreshed = await refreshResearchDossiers(null, null, true);
    if (!refreshed && acceptResearchContext(context, result)) {
      researchFormStatus(button, uiLabel("research_load_dossiers_failed"), "err");
    } else if (refreshed && acceptResearchContext(context, result)) {
      var select = document.getElementById("r-dos-collection-select");
      if (select) select.value = deleting ? "all" : state.id;
      renderResearchDossiersView(researchDossiersPayload);
    }
  } catch (error) {
    if (acceptResearchContext(context, {})) researchFormStatus(button, error.message || uiLabel("research_status_unavailable"), "err");
  } finally { state.pending = false; updateResearchCollectionEditor(); }
});
