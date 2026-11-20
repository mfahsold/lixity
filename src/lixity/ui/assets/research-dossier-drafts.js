// Research workspace: preview and explicitly save manuscript dossier suggestions.
var manuscriptDraftsState = null;

function resetManuscriptDossierDrafts() {
  if (!manuscriptDraftsState) return;
  manuscriptDraftsState = null;
  var host = document.getElementById("r-manuscript-drafts");
  if (host) host.replaceChildren();
}

function renderManuscriptDraftsView(host, state) {
  var drafts = state.drafts;
  var skipped = state.skipped;
  var skippedNote = skipped > 0
    ? '<p class="ctl-note">' + escapeHtml(uiCountFormat("research_dossier_draft_skipped", skipped)) + "</p>"
    : "";
  var manualCharacter = '<button type="button" class="ctl" data-draft-manual-character>' +
    escapeHtml(uiLabel("research_dossier_draft_manual_character")) + '</button>';
  if (!drafts.length) {
    host.innerHTML = skippedNote + '<p class="ctl-note">' +
      escapeHtml(uiLabel("research_dossier_draft_empty")) + "</p>" + manualCharacter;
    return;
  }
  var groups = {
    character: drafts.filter(function(d) { return d.kind === "character"; }),
    location: drafts.filter(function(d) { return d.kind === "location"; }),
    scene: drafts.filter(function(d) { return d.kind === "scene"; })
  };
  var availableKinds = ["character", "location", "scene"].filter(function(k) { return groups[k].length > 0; });
  if (!availableKinds.includes(state.activeKind)) {
    state.activeKind = availableKinds[0];
  }
  var activeList = groups[state.activeKind] || drafts;
  var selected = activeList.find(function(d) {
    return d.id === state.selectedByKind[state.activeKind];
  }) || activeList[0];
  state.selectedByKind[state.activeKind] = selected.id;

  var draftTagLabels = {
    "manuscript-draft": uiLabel("research_draft_tag_manuscript"),
    "character": uiLabel("research_tpl_character"),
    "location": uiLabel("research_tpl_place"),
    "scene": uiLabel("research_tpl_scene"),
    "scenes": uiLabel("research_tpl_scene")
  };
  function renderDraftCard(d) {
    var tags = Array.isArray(d.tags) && d.tags.length
      ? '<div class="ctl-note">' + d.tags.map(function(t) { return '<span class="badge">' + escapeHtml(draftTagLabels[t] || t) + "</span>"; }).join(" ") + "</div>"
      : "";
    return '<div class="research-card">' +
      '<div class="research-card-title">' + escapeHtml(d.title || "") + "</div>" +
      '<p class="ctl-note">' + escapeHtml(d.summary || "") + "</p>" +
      tags +
      '<div class="row mt-2"><button type="button" class="ctl ctl-sm primary" data-create-manuscript-draft="' +
      escapeHtml(d.id || "") + '"' + (state.saving ? " disabled" : "") + ">" +
      escapeHtml(uiLabel("research_dossier_draft_create")) + "</button></div>" +
      "</div>";
  }

  var kindLabels = {
    character: uiLabel("research_tpl_character"),
    location: uiLabel("research_tpl_place"),
    scene: uiLabel("research_tpl_scene")
  };
  var html = skippedNote;
  if (state.error) html += '<p class="ctl-note err">' + escapeHtml(state.error) + "</p>";
  if (!groups.character.length) {
    html += '<div class="mb-2"><p class="ctl-note">' +
      escapeHtml(uiLabel("research_dossier_draft_no_characters")) + "</p>" + manualCharacter + "</div>";
  }
  if (availableKinds.length > 1) {
    html += '<div class="row mb-2 chip-row">' + availableKinds.map(function(k) {
      var isCurrent = k === state.activeKind;
      return '<button type="button" class="ctl ctl-sm' + (isCurrent ? " active" : "") +
        '" data-draft-kind="' + k + '" aria-pressed="' + String(isCurrent) + '">' +
        escapeHtml(kindLabels[k] || k) + " (" + groups[k].length + ")</button>";
    }).join("") + "</div>";
  }

  var weights = activeList.map(function(d) {
    var hints = d.evidence_hints || {};
    return Number(hints.mentions || hints.words || hints.scenes || 1);
  });
  var maxW = Math.max.apply(null, weights);
  var minW = Math.min.apply(null, weights);
  html += '<p class="ctl-note mb-1">' + escapeHtml(uiLabel("research_dossier_draft_cloud")) + "</p>";
  html += '<div class="character-cloud" role="group" aria-label="' +
    escapeHtml(kindLabels[state.activeKind] || uiLabel("research_nav_draft_dossier")) + '">';
  html += activeList.map(function(d) {
    var hints = d.evidence_hints || {};
    var label = String(hints.character || hints.location || hints.scene || d.title || "");
    var countVal = Number(hints.mentions || hints.words || hints.scenes || 0);
    var ratio = maxW > minW ? (countVal - minW) / (maxW - minW) : 0.5;
    var scale = (0.9 + ratio * 0.36).toFixed(2);
    var active = d.id === selected.id;
    return '<button type="button" class="ctl character-cloud-chip' + (active ? " active" : "") +
      '" style="--cloud-scale:' + scale + '" data-draft-select="' + escapeHtml(d.id || "") +
      '" aria-pressed="' + String(active) + '">' + escapeHtml(label) +
      (countVal > 0 ? ' <span class="character-cloud-count">' + escapeHtml(String(countVal)) + "</span>" : "") +
      "</button>";
  }).join("");
  html += "</div>";
  html += '<div id="r-manuscript-draft-preview">' + renderDraftCard(selected) + "</div>";
  host.innerHTML = html;
}

function openManualCharacterDossier() {
  var composer = document.getElementById("r-dos-composer");
  if (!composer) return;
  var fields = fieldSnapshot(["r-dos-title", "r-dos-body", "r-dos-tags", "r-dos-eids"]);
  var geography = document.getElementById("r-dos-geography");
  var save = document.getElementById("r-dos-create-btn");
  composer.open = true;
  if (!Object.values(fields).some(function(value) { return value.length; }) &&
      (!geography || !geography.value || geography.value === "[]") &&
      (!save || save.dataset.pending !== "true")) {
    var characterTag = uiLabel("research_tpl_character_tag");
    var preset = Array.from(composer.querySelectorAll("#r-dos-templates [data-template-tag]"))
      .find(function(button) { return button.dataset.templateTag === characterTag; });
    if (preset) preset.click();
  }
  openResearchDossierComposer();
}

document.getElementById("r-dos-drafts-box")?.addEventListener("click", async function (event) {
  var loadDraftsBtn = event.target.closest("#r-manuscript-dossier-btn");
  if (loadDraftsBtn) {
    var draftsHost = document.getElementById("r-manuscript-drafts");
    if (!draftsHost || loadDraftsBtn.disabled) return;
    var state = null;
    var loadFocused = document.activeElement === loadDraftsBtn;
    loadDraftsBtn.disabled = true;
    draftsHost.innerHTML = '<p class="ctl-note">' + escapeHtml(uiLabel("research_loading")) + "</p>";
    try {
      // The initial status read establishes the project identity for this view.
      if (!researchSelectionProjectId && researchProjectInfoPending) await researchProjectInfoPending;
      state = {context: researchReadContext(), drafts: [], skipped: 0,
        selectedByKind: Object.create(null), activeKind: "character", saving: false, error: ""};
      manuscriptDraftsState = state;
      var data = await researchApiGet("research/manuscript-dossier-drafts");
      if (manuscriptDraftsState !== state || !acceptResearchContext(state.context, data || {})) return;
      if (!data || data.ok !== true || !Array.isArray(data.drafts)) {
        draftsHost.innerHTML = '<p class="ctl-note err">' + escapeHtml((data && data.message) || uiLabel("research_status_unavailable")) + "</p>";
        return;
      }
      state.drafts = data.drafts;
      state.skipped = Number(data.skipped_existing || 0);
      renderManuscriptDraftsView(draftsHost, state);
    } catch (error) {
      if (!state || (manuscriptDraftsState === state && acceptResearchContext(state.context, {}))) {
        draftsHost.innerHTML = '<p class="ctl-note err">' + escapeHtml((error && error.message) || uiLabel("research_status_unavailable")) + "</p>";
      }
    } finally {
      loadDraftsBtn.disabled = false;
      if (loadFocused && document.activeElement === document.body) loadDraftsBtn.focus();
    }
    return;
  }

  if (event.target.closest("[data-draft-manual-character]")) {
    openManualCharacterDossier();
    return;
  }

  var draftSelection = event.target.closest("[data-draft-kind], [data-draft-select]");
  if (draftSelection) {
    var draftsHost = draftSelection.closest("#r-manuscript-drafts");
    var state = manuscriptDraftsState;
    if (!draftsHost || !state || !acceptResearchContext(state.context, {})) return;
    var kind = draftSelection.dataset.draftKind;
    if (kind) state.activeKind = kind;
    else state.selectedByKind[state.activeKind] = draftSelection.dataset.draftSelect;
    renderManuscriptDraftsView(draftsHost, state);
    var activeSelection = draftsHost.querySelector((kind ? "[data-draft-kind]" : "[data-draft-select]") + '[aria-pressed="true"]');
    if (activeSelection) activeSelection.focus();
    return;
  }

  var createDraftBtn = event.target.closest("[data-create-manuscript-draft]");
  if (createDraftBtn) {
    var draftsHost = createDraftBtn.closest("#r-manuscript-drafts");
    var state = manuscriptDraftsState;
    var draftId = createDraftBtn.dataset.createManuscriptDraft;
    if (!draftsHost || !state || state.saving || !draftId || !acceptResearchContext(state.context, {}) ||
        !state.drafts.some(function(draft) { return draft.id === draftId; })) return;
    var loadDraftsBtn = document.getElementById("r-manuscript-dossier-btn");
    var saveFocused = document.activeElement === createDraftBtn;
    state.saving = true;
    state.error = "";
    createDraftBtn.disabled = true;
    if (loadDraftsBtn) loadDraftsBtn.disabled = true;
    var created;
    try {
      created = await researchApiPost("research-dossier-from-manuscript", {draft_id: draftId});
    } catch (error) {
      created = {ok: false, message: error && error.message};
    } finally {
      state.saving = false;
      if (loadDraftsBtn) loadDraftsBtn.disabled = false;
    }
    if (manuscriptDraftsState !== state || !acceptResearchContext(state.context, created || {})) return;
    var saved = created && created.ok;
    if (saved) {
      state.drafts = state.drafts.filter(function(draft) { return draft.id !== draftId; });
      ++state.skipped;
    } else {
      state.error = (created && created.message) || uiLabel("research_status_unavailable");
    }
    var currentFocus = document.activeElement;
    var focusSelector = draftsHost.contains(currentFocus) && currentFocus.dataset.draftKind
      ? '[data-draft-kind][aria-pressed="true"]'
      : '[data-draft-select][aria-pressed="true"]';
    var restoreFocus = draftsHost.contains(currentFocus) || (saveFocused && currentFocus === document.body);
    if (!saved && (currentFocus === createDraftBtn || (saveFocused && currentFocus === document.body))) {
      focusSelector = "[data-create-manuscript-draft]";
    }
    renderManuscriptDraftsView(draftsHost, state);
    if (restoreFocus) {
      var nextFocus = draftsHost.querySelector(focusSelector) ||
        draftsHost.querySelector('[data-draft-select][aria-pressed="true"], [data-draft-manual-character]') || loadDraftsBtn;
      if (nextFocus) nextFocus.focus();
    }
    if (saved) await refreshResearchDossiers();
    return;
  }
});
