// Research workspace: preview and explicitly save manuscript dossier suggestions.
var manuscriptDraftsState = null;

function resetManuscriptDossierDrafts() {
  if (!manuscriptDraftsState) return;
  manuscriptDraftsState = null;
  var host = document.getElementById("r-manuscript-drafts");
  if (host) host.replaceChildren();
}

var manuscriptDraftKinds = ["character", "location", "scene"];
var existingManuscriptDraftsEndpoint = "research/manuscript-dossier-drafts?include_existing=1";

function existingCharacterDossier(draft) {
  var record = draft.existing_dossier;
  return draft.kind === "character" && draft.already_covered === true && record &&
    typeof record.id === "string" && record.id && typeof record.title === "string" && Number.isInteger(record.revision) && record.revision > 0 &&
    typeof record.project_id === "string" && /^[a-f0-9]{64}$/.test(record.snapshot) ? record : null;
}

function firstManuscriptDraftKind(drafts) {
  return manuscriptDraftKinds.find(function(kind) { return drafts.some(function(draft) { return draft.kind === kind; }); }) || "character";
}

function prepareManuscriptDossierAppend(existing, draft, envelope) {
  var record = envelope && envelope.record;
  if (!record || envelope.project_id !== existing.project_id || envelope.snapshot !== existing.snapshot ||
      record.id !== existing.id || record.revision !== existing.revision || envelope.latest_revision !== existing.revision ||
      envelope.availability || typeof record.body !== "string") return null;
  var current = record.body, proposed = draft.body.trim();
  var nested = proposed.replace(/^## /gm, "### ");
  if (current.trim() === proposed || current.includes("\n\n" + nested)) {
    return {body: current, message: uiLabel("research_dossier_draft_staged_same")};
  }
  var boundary = current.endsWith("\n\n") || !current ? "" : current.endsWith("\n") ? "\n" : "\n\n";
  return {body: current + boundary + "## " + uiLabel("research_dossier_draft_refresh_heading") + "\n\n" + nested,
    message: uiLabel("research_dossier_draft_staged")};
}

function renderManuscriptDraftsView(host, state) {
  function label(key) { return escapeHtml(uiLabel(key)); }
  var number = new Intl.NumberFormat(document.documentElement.lang || undefined);
  var drafts = state.drafts;
  var groups = Object.fromEntries(manuscriptDraftKinds.map(function(kind) {
    return [kind, drafts.filter(function(draft) { return draft.kind === kind; })];
  }));
  var kindLabels = {
    character: uiLabel("research_tpl_character"),
    location: uiLabel("research_tpl_place"),
    scene: uiLabel("research_tpl_scene")
  };
  var active = groups[state.activeKind];
  var selected = active.find(function(draft) { return draft.id === state.selectedByKind[state.activeKind]; }) || active[0];
  if (selected) state.selectedByKind[state.activeKind] = selected.id;
  else delete state.selectedByKind[state.activeKind];

  function choice(draft) {
    var hints = draft.evidence_hints || {};
    var text = hints.character || hints.location || draft.title;
    var unit = "";
    if (hints.scene_scope === "register") {
      text = draft.summary || draft.title;
    } else if (draft.kind === "scene" && Number.isInteger(hints.chapter)) {
      var chapter = uiFormat("publication_chapter", {number: number.format(hints.chapter)});
      if (hints.chapter_title && hints.chapter_title.toLocaleLowerCase() !== chapter.toLocaleLowerCase()) chapter += " · " + hints.chapter_title;
      text = chapter;
      if (hints.scene_scope !== "chapter") {
        text += " · " + uiLabel("research_dossier_draft_scene_unit") + " " + number.format(hints.scene_index);
        if (hints.scene && hints.scene !== hints.chapter_title + " · " + hints.scene_index) text += " · " + hints.scene;
      }
      if (Number.isInteger(hints.words)) unit = number.format(hints.words) + " " + uiCountFormat("words", hints.words);
    } else if (Number.isInteger(hints.mentions)) unit = uiLabel("research_dossier_character_mentions") + " " + number.format(hints.mentions);
    var pressed = draft === selected;
    return '<button type="button" class="ctl ctl-sm' + (pressed ? " active" : "") +
      '" data-draft-select="' + escapeHtml(draft.id) + '" aria-pressed="' + pressed + '">' +
      escapeHtml(text) + (unit ? ' · ' + escapeHtml(unit) : '') + '</button>';
  }

  function catalogue(items, labelKey, group) {
    if (!items.length) return "";
    return '<div data-draft-group="' + group + '">' +
      (labelKey ? '<h5>' + label(labelKey) + '</h5>' : '') +
      (group === "scene-individual" && items.length > 1 ? '<p class="ctl-note">' +
        escapeHtml(uiFormat("research_dossier_draft_scene_units", {count: number.format(items.length)})) + '</p>' : '') +
      '<div class="chip-row" role="group" aria-label="' +
        (labelKey ? label(labelKey) : escapeHtml(kindLabels[state.activeKind])) + '">' +
        items.map(choice).join("") + '</div></div>';
  }

  function preview(draft) {
    var hints = draft.evidence_hints || {};
    var existing = existingCharacterDossier(draft);
    var basis = hints.scene_scope === "chapter" || hints.chapter_fallback === true
      ? "research_dossier_draft_scene_chapter_fallback"
      : draft.kind === "location" && ["configured", "inferred"].includes(hints.basis)
        ? "research_dossier_draft_location_" + hints.basis : null;
    var canSave = !state.saving && !state.stale && /^[a-f0-9]{64}$/.test(draft.preview_sha256);
    var actions = existing ? '<p class="ctl-note">' + label("research_dossier_draft_stage_help") + '</p>' +
      '<div class="chip-row"><button type="button" class="ctl ctl-sm" data-draft-open-existing data-research-history="dossier" data-record-id="' +
      escapeHtml(existing.id) + '">' + label("research_dossier_draft_open_saved") + '</button>' +
      '<button type="button" class="ctl ctl-sm primary" data-draft-stage-existing="' + escapeHtml(draft.id) + '"' +
      (canSave ? "" : " disabled") + '>' + label("research_dossier_draft_stage_existing") + '</button></div>' :
      '<div class="row"><button type="button" class="ctl ctl-sm primary" data-create-manuscript-draft="' +
      escapeHtml(draft.id) + '"' + (canSave && !draft.already_covered ? "" : " disabled") + '>' +
      label("research_dossier_draft_create") + '</button></div>';
    return '<section id="r-manuscript-draft-preview" class="research-card">' +
      '<h5 class="research-card-title">' + escapeHtml(draft.title || "") + '</h5>' +
      (existing ? '<p class="ctl-note">' + escapeHtml(uiFormat("research_dossier_draft_existing_notice", {title: existing.title})) + '</p>' : '') +
      (basis ? '<p class="ctl-note" data-draft-basis>' + label(basis) + '</p>' : '') +
      '<h6>' + label(existing ? "research_dossier_draft_refresh_heading" : "research_dossier_draft_preview") + '</h6>' +
      '<div data-draft-preview-body>' + researchDossierBodyHtml(draft.body) + '</div>' +
      actions + '</section>';
  }

  var html = state.skipped > 0 ? '<p class="ctl-note">' +
    escapeHtml(uiCountFormat("research_dossier_draft_skipped", state.skipped)) + '</p>' : '';
  if (state.saved) {
    html += '<div class="chip-row"><p class="ctl-note" role="status">' +
      label("research_dossier_draft_saved") + ' <strong>' + escapeHtml(state.saved.title) + '</strong></p>' +
      '<button type="button" class="ctl ctl-sm" data-draft-open-saved data-research-history="dossier" data-record-id="' +
      escapeHtml(state.saved.id) + '">' + label("research_dossier_draft_open_saved") + '</button></div>';
  }
  if (state.stale) {
    html += '<div class="chip-row" data-draft-stale><p class="ctl-note err" role="alert">' +
      label("research_dossier_draft_stale") + '</p><button type="button" class="ctl ctl-sm" data-draft-reload>' +
      label("research_dossier_draft_load") + '</button></div>';
  } else if (state.error) html += '<p class="ctl-note err" role="alert">' + escapeHtml(state.error) + '</p>';
  if (state.includeExisting) {
    host.innerHTML = html + (selected ? catalogue(groups.character, "research_dossier_draft_load_existing", "character") + preview(selected) :
      '<p class="ctl-note">' + label("research_dossier_draft_existing_empty") + '</p>');
    return;
  }
  if (state.skipped > 0 || !groups.character.length) {
    html += '<div class="chip-row"><button type="button" class="ctl" data-draft-load-existing>' +
      label("research_dossier_draft_load_existing") + '</button></div>';
  }
  if (!groups.character.length) {
    html += '<div class="chip-row"><p class="ctl-note">' + label("research_dossier_draft_no_characters") + '</p>' +
      '<button type="button" class="ctl" data-draft-manual-character>' +
      label("research_dossier_draft_manual_character") + '</button></div>';
  }
  if (!drafts.length) {
    host.innerHTML = html + '<p class="ctl-note">' + label("research_dossier_draft_empty") + '</p>';
    return;
  }
  html += '<div class="chip-row" role="group" aria-label="' + label("research_dossier_draft_cloud") + '">' +
    manuscriptDraftKinds.map(function(kind) {
      var pressed = kind === state.activeKind;
      return '<button type="button" class="ctl ctl-sm' + (pressed ? " active" : "") +
        '" data-draft-kind="' + kind + '" aria-pressed="' + pressed + '">' +
        escapeHtml(kindLabels[kind]) + " (" + number.format(groups[kind].length) + ")</button>";
    }).join("") + '</div>';
  if (!selected) {
    host.innerHTML = html + (state.activeKind === "character" ? '' :
      '<p class="ctl-note">' + escapeHtml(uiFormat("research_dossier_draft_no_kind", {kind: kindLabels[state.activeKind]})) + '</p>');
    return;
  }
  if (state.activeKind === "scene") {
    html += catalogue(active.filter(function(draft) { return draft.id === "scenes:manuscript"; }),
      "research_dossier_draft_scene_register", "scene-register");
    html += catalogue(active.filter(function(draft) { return draft.id !== "scenes:manuscript"; }),
      "research_dossier_draft_scene_individual", "scene-individual");
  } else html += catalogue(active, "research_dossier_draft_cloud", state.activeKind);
  host.innerHTML = html + preview(selected);
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
  var loadTrigger = event.target.closest("#r-manuscript-dossier-btn, [data-draft-reload], [data-draft-load-existing]");
  if (loadTrigger) {
    var loadDraftsBtn = document.getElementById("r-manuscript-dossier-btn");
    var draftsHost = document.getElementById("r-manuscript-drafts");
    if (!draftsHost || !loadDraftsBtn || loadDraftsBtn.disabled) return;
    var previous = manuscriptDraftsState;
    if (previous && !acceptResearchContext(previous.context, {})) previous = null;
    var includeExisting = loadTrigger.hasAttribute("data-draft-load-existing") ||
      Boolean(previous && previous.includeExisting && loadTrigger.hasAttribute("data-draft-reload"));
    var state = null;
    var loadFocused = document.activeElement === loadTrigger;
    loadDraftsBtn.disabled = true;
    draftsHost.innerHTML = '<p class="ctl-note">' + escapeHtml(uiLabel("research_loading")) + "</p>";
    try {
      // The initial status read establishes the project identity for this view.
      if (!researchSelectionProjectId && researchProjectInfoPending) await researchProjectInfoPending;
      var sameMode = previous && previous.includeExisting === includeExisting;
      state = {context: researchReadContext(), drafts: [], skipped: 0,
        selectedByKind: sameMode ? previous.selectedByKind : Object.create(null),
        activeKind: includeExisting ? "character" : sameMode ? previous.activeKind : null,
        includeExisting: includeExisting, saving: false, stale: false, error: "", saved: null};
      manuscriptDraftsState = state;
      var data = await researchApiGet(includeExisting ? existingManuscriptDraftsEndpoint : "research/manuscript-dossier-drafts");
      if (manuscriptDraftsState !== state || !acceptResearchContext(state.context, data || {})) return;
      if (!data || data.ok !== true || !Array.isArray(data.drafts)) {
        draftsHost.innerHTML = '<p class="ctl-note err">' + escapeHtml((data && data.message) || uiLabel("research_status_unavailable")) + "</p>";
        return;
      }
      if (!data.drafts.every(function(draft) {
        return draft && typeof draft.id === "string" && draft.id && typeof draft.title === "string" &&
          typeof draft.body === "string" && /^[a-f0-9]{64}$/.test(draft.preview_sha256) && manuscriptDraftKinds.includes(draft.kind);
      }) || new Set(data.drafts.map(function(draft) { return draft.id; })).size !== data.drafts.length) {
        draftsHost.innerHTML = '<p class="ctl-note err">' + escapeHtml(uiLabel("research_status_unavailable")) + '</p>';
        return;
      }
      state.drafts = includeExisting ? data.drafts.filter(existingCharacterDossier) : data.drafts;
      state.skipped = includeExisting ? 0 : Number(data.skipped_existing || 0);
      if (!state.activeKind || !state.drafts.some(function(draft) { return draft.kind === state.activeKind; })) {
        state.activeKind = firstManuscriptDraftKind(state.drafts);
      }
      renderManuscriptDraftsView(draftsHost, state);
    } catch (error) {
      if (!state || (manuscriptDraftsState === state && acceptResearchContext(state.context, {}))) {
        draftsHost.innerHTML = '<p class="ctl-note err">' + escapeHtml((error && error.message) || uiLabel("research_status_unavailable")) + "</p>";
      }
    } finally {
      loadDraftsBtn.disabled = false;
      if (loadFocused && document.activeElement === document.body) {
        var refreshed = loadTrigger !== loadDraftsBtn && draftsHost.querySelector('[data-draft-select][aria-pressed="true"]');
        (refreshed || loadDraftsBtn).focus();
      }
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
    if (manuscriptDraftKinds.includes(kind)) state.activeKind = kind;
    else if (state.drafts.some(function(draft) {
      return draft.kind === state.activeKind && draft.id === draftSelection.dataset.draftSelect;
    })) state.selectedByKind[state.activeKind] = draftSelection.dataset.draftSelect;
    else return;
    renderManuscriptDraftsView(draftsHost, state);
    var activeSelection = draftsHost.querySelector((kind ? "[data-draft-kind]" : "[data-draft-select]") + '[aria-pressed="true"]');
    if (activeSelection) activeSelection.focus();
    return;
  }

  var stage = event.target.closest("[data-draft-stage-existing]");
  if (stage) {
    var draftsHost = stage.closest("#r-manuscript-drafts");
    var state = manuscriptDraftsState;
    var id = stage.dataset.draftStageExisting;
    if (!draftsHost || !state || !state.includeExisting || state.saving || state.stale ||
        id !== state.selectedByKind.character || !acceptResearchContext(state.context, {})) return;
    var draft = state.drafts.find(function(item) { return item.id === id; });
    var existing = draft && existingCharacterDossier(draft);
    if (!existing || !window.LixityResearchDrafts) return;
    var load = document.getElementById("r-manuscript-dossier-btn");
    state.saving = true;
    state.error = "";
    stage.setAttribute("aria-disabled", "true");
    load.disabled = true;
    try {
      var checked = await researchApiGet(existingManuscriptDraftsEndpoint);
      if (manuscriptDraftsState !== state || !acceptResearchContext(state.context, checked || {}) ||
          state.selectedByKind.character !== id) return;
      if (!checked.ok || !Array.isArray(checked.drafts)) {
        state.error = (checked && checked.message) || uiLabel("research_status_unavailable");
        return;
      }
      var current = checked.drafts.find(function(item) { return item.id === id; });
      var verified = current && existingCharacterDossier(current);
      if (!verified || current.preview_sha256 !== draft.preview_sha256 || verified.id !== existing.id ||
          verified.revision !== existing.revision || verified.project_id !== existing.project_id) {
        state.stale = true;
        return;
      }
      if (await window.LixityResearchDrafts.stageDossierBody(verified.id, function(envelope) {
        return prepareManuscriptDossierAppend(verified, draft, envelope);
      }) === false) state.stale = true;
    } catch (_) {
      state.error = uiLabel("research_status_unavailable");
    } finally {
      state.saving = false;
      load.disabled = false;
      stage.removeAttribute("aria-disabled");
      if (manuscriptDraftsState === state && acceptResearchContext(state.context, {}) &&
          (!stage.isConnected || state.stale || state.error)) {
        var restore = document.activeElement === stage || draftsHost.contains(document.activeElement);
        renderManuscriptDraftsView(draftsHost, state);
        if (restore) {
          var target = draftsHost.querySelector(state.stale ? "[data-draft-reload]" : '[data-draft-select][aria-pressed="true"]');
          if (target) target.focus();
        }
      }
    }
    return;
  }

  var createDraftBtn = event.target.closest("[data-create-manuscript-draft]");
  if (createDraftBtn) {
    var draftsHost = createDraftBtn.closest("#r-manuscript-drafts");
    var state = manuscriptDraftsState;
    var draftId = createDraftBtn.dataset.createManuscriptDraft;
    if (!draftsHost || !state || state.includeExisting || state.saving || state.stale || draftId !== state.selectedByKind[state.activeKind] ||
        !acceptResearchContext(state.context, {})) return;
    var draft = state.drafts.find(function(item) { return item.id === draftId; });
    if (!draft || draft.already_covered || !/^[a-f0-9]{64}$/.test(draft.preview_sha256)) return;
    var loadDraftsBtn = document.getElementById("r-manuscript-dossier-btn");
    var saveFocused = document.activeElement === createDraftBtn;
    state.saving = true;
    state.error = "";
    createDraftBtn.disabled = true;
    if (loadDraftsBtn) loadDraftsBtn.disabled = true;
    var created;
    try {
      created = await researchApiPost("research-dossier-from-manuscript", {
        draft_id: draftId, preview_sha256: draft.preview_sha256, project_id: state.context.projectId || undefined,
      });
    } catch (error) {
      created = {ok: false, message: error && error.message};
    } finally {
      state.saving = false;
      if (loadDraftsBtn) loadDraftsBtn.disabled = false;
    }
    if (manuscriptDraftsState !== state || !acceptResearchContext(state.context, created || {})) return;
    var saved = created && created.ok;
    if (saved) {
      state.drafts = state.drafts.filter(function(item) { return item.id !== draftId; });
      ++state.skipped;
      if (state.selectedByKind[draft.kind] === draftId) delete state.selectedByKind[draft.kind];
      if (draft.kind === state.activeKind && !state.drafts.some(function(item) { return item.kind === state.activeKind; })) {
        state.activeKind = firstManuscriptDraftKind(state.drafts);
      }
      if (typeof created.dossier_id === "string" && created.dossier_id) {
        state.saved = {id: created.dossier_id, title: created.title || draft.title};
      }
    } else if (created && (created.code === "stale-draft" || created.http_status === 409)) {
      state.stale = true;
    } else {
      state.error = (created && created.message) || uiLabel("research_status_unavailable");
    }
    var currentFocus = document.activeElement;
    var focusSelector = draftsHost.contains(currentFocus) && currentFocus.dataset.draftKind
      ? '[data-draft-kind][aria-pressed="true"]'
      : '[data-draft-select][aria-pressed="true"]';
    var restoreFocus = draftsHost.contains(currentFocus) || (saveFocused && currentFocus === document.body);
    if (!saved && (currentFocus === createDraftBtn || (saveFocused && currentFocus === document.body))) {
      focusSelector = state.stale ? "[data-draft-reload]" : "[data-create-manuscript-draft]";
    }
    renderManuscriptDraftsView(draftsHost, state);
    if (restoreFocus) {
      var nextFocus = draftsHost.querySelector(focusSelector) ||
        draftsHost.querySelector('[data-draft-select][aria-pressed="true"]') ||
        draftsHost.querySelector('[data-draft-open-saved], [data-draft-manual-character]') || loadDraftsBtn;
      if (nextFocus) nextFocus.focus();
    }
    if (saved) await refreshResearchDossiers();
    return;
  }
});
