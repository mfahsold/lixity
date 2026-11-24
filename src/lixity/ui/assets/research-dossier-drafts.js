// Research workspace: preview and explicitly save manuscript dossier suggestions.
var manuscriptDraftsState = null;
var manuscriptDraftsBox = document.getElementById("r-dos-drafts-box");

function resetManuscriptDossierDrafts() {
  if (!manuscriptDraftsState) return;
  manuscriptDraftsState = null;
  var host = document.getElementById("r-manuscript-drafts");
  if (host) host.replaceChildren();
  setManuscriptDraftMode(null);
  setManuscriptDraftStatus();
}

var manuscriptDraftKinds = ["character", "location", "scene"];
var existingManuscriptDraftsEndpoint = "research/manuscript-dossier-drafts?kind=character&include_existing=1";

function setManuscriptDraftMode(state, retry = false) {
  manuscriptDraftsBox?.querySelectorAll("#r-manuscript-dossier-btn, [data-draft-load-existing]").forEach(function(button) {
    var existing = button.hasAttribute("data-draft-load-existing");
    var selected = Boolean(state && state.includeExisting === existing);
    button.setAttribute("aria-pressed", String(selected));
    button.classList.toggle("active", selected);
    button.classList.toggle("primary", retry ? selected : !state && !existing);
  });
}

function setManuscriptDraftStatus(message, state) {
  var status = document.getElementById("r-manuscript-drafts-status");
  if (!status) return;
  status.hidden = !message;
  LixityComponents.setStatus(status, message, state);
}

function existingCharacterDossier(draft) {
  return draft.kind === "character" && draft.already_covered === true ? manuscriptDossierReference(draft) : null;
}

function manuscriptDossierReference(draft) {
  var record = draft && draft.existing_dossier;
  return record &&
    typeof record.id === "string" && record.id && typeof record.title === "string" && Number.isInteger(record.revision) && record.revision > 0 &&
    typeof record.project_id === "string" && /^[a-f0-9]{64}$/.test(record.snapshot) ? record : null;
}

function currentManuscriptDraftCatalogue(state, data = {}) {
  return state && manuscriptDraftsState === state && acceptResearchContext(state.context, data);
}

function selectedManuscriptDraft(state) {
  var id = state.selectedByKind[state.activeKind];
  return state.drafts.find(function(draft) { return draft.kind === state.activeKind && draft.id === id; });
}

function firstManuscriptDraftKind(drafts) {
  return manuscriptDraftKinds.find(function(kind) { return drafts.some(function(draft) { return draft.kind === kind; }); }) || "character";
}

function prepareManuscriptDossierRefresh(draft, envelope) {
  var existing = draft.existing_dossier;
  var record = envelope && envelope.record;
  if (!record || envelope.project_id !== existing.project_id || envelope.snapshot !== existing.snapshot ||
      record.id !== existing.id || record.revision !== existing.revision || envelope.latest_revision !== existing.revision ||
      envelope.availability || typeof record.body !== "string") return null;
  return {body: draft.staged_body, preview: draft.body};
}

function manuscriptDraftSettingsHtml(kind) {
  var actions = [
    {kind: "location", target: "set-location-mode", action: "location_settings"},
    {kind: "character", target: "settings-dossier-drafts", action: "report_settings"}
  ].filter(function(item) { return (!kind || kind === item.kind) && document.getElementById(item.target); });
  if (!actions.length) return "";
  return '<div class="row">' + actions.map(function(item) {
    return '<button type="button" class="ctl ctl-sm" data-draft-' + item.action.replace("_", "-") +
      ' data-draft-settings-target="' + item.target + '">' +
      escapeHtml(uiLabel("research_dossier_draft_" + item.action)) + '</button>';
  }).join("") + '</div>';
}

function renderManuscriptDraftsView(host, state, selectedButton) {
  function label(key) { return escapeHtml(uiLabel(key)); }
  var number = new Intl.NumberFormat(document.documentElement.lang || undefined);

  function chapterLabel(chapter, title) {
    var text = uiFormat("publication_chapter", {number: number.format(chapter)});
    return title && title.toLocaleLowerCase() !== text.toLocaleLowerCase() ? text + " · " + title : text;
  }

  function choice(draft) {
    var hints = draft.evidence_hints || {};
    var text = hints.character || hints.location || draft.title;
    var unit = "";
    if (hints.scene_scope === "register") {
      text = draft.summary || draft.title;
    } else if (draft.kind === "scene" && Number.isInteger(hints.chapter)) {
      text = chapterLabel(hints.chapter, hints.chapter_title);
      if (hints.scene_scope !== "chapter") {
        text += " · " + uiLabel("research_dossier_draft_scene_unit") + " " + number.format(hints.scene_index);
        if (hints.scene && hints.scene !== hints.chapter_title + " · " + hints.scene_index) text += " · " + hints.scene;
      }
      if (Number.isInteger(hints.words)) unit = number.format(hints.words) + " " + uiCountFormat("words", hints.words);
    } else if (Number.isInteger(hints.mentions)) unit = uiLabel("research_dossier_character_mentions") + " " + number.format(hints.mentions);
    var pressed = draft === selected;
    return '<button type="button" class="ctl ctl-sm ctl-choice' + (pressed ? " active" : "") +
      '" data-draft-select="' + escapeHtml(draft.id) + '" aria-pressed="' + pressed + '">' +
      escapeHtml(text) + (unit ? ' · ' + escapeHtml(unit) : '') + '</button>';
  }

  function catalogue(items, labelKey, group) {
    if (!items.length) return "";
    return '<div data-draft-group="' + group + '">' +
      (labelKey ? '<h5>' + label(labelKey) + '</h5>' : '') +
      '<div class="chip-row" role="group" aria-label="' +
        (labelKey ? label(labelKey) : escapeHtml(kindLabels[state.activeKind])) + '">' +
        items.map(choice).join("") + '</div></div>';
  }

  function reasonEvidenceMarkup(hit, labelKey, showQuote) {
    if (!hit?.quote || !Number.isInteger(hit.chapter) || !Number.isInteger(hit.line)) return "";
    var end = Number.isInteger(hit.end_line) && hit.end_line >= hit.line ? hit.end_line : hit.line;
    var line = uiCountFormat("research_dossier_character_lines", end - hit.line + 1, {
      start: number.format(hit.line), end: number.format(end)
    });
    var caption = label(labelKey) + '<br>' + escapeHtml(chapterLabel(hit.chapter, hit.chapter_title) + " · " + line);
    return showQuote ? '<figure data-draft-reason-passage class="research-prose markdown-body">' +
      '<figcaption class="ctl-note">' + caption + '</figcaption><blockquote>' +
      escapeHtml(hit.quote) + '</blockquote></figure>' :
      '<p class="ctl-note" data-draft-reason-passage>' + caption + '</p>';
  }

  function reasonMarkup(draft) {
    var hints = draft.evidence_hints || {};
    var method = "", passage = "";
    if (draft.kind === "character" && ["configured", "inferred"].includes(hints.basis)) {
      method = uiLabel("research_dossier_draft_reason_character_" + hints.basis);
      if (hints.includes_passages === false) {
        passage = reasonEvidenceMarkup(hints.first_hit, "research_dossier_draft_reason_preview_excerpt", true);
      }
    } else if (draft.kind === "location") {
      if (hints.basis === "configured") method = uiLabel("research_dossier_draft_reason_location_configured");
      else if (hints.basis === "inferred") {
        method = Number.isInteger(hints.qualifying_mentions) ? uiFormat("research_dossier_draft_reason_location_inferred", {
          cues: number.format(hints.qualifying_mentions)
        }) : uiLabel("research_dossier_draft_location_inferred");
        var hit = hints.reason_hit;
        var inPreview = hit && [hints.first_hit, hints.last_hit].some(function(excerpt) {
          return excerpt?.chapter === hit.chapter && excerpt.line === hit.line && excerpt.quote === hit.quote;
        });
        passage = reasonEvidenceMarkup(hit, "research_dossier_draft_reason_location_passage", !inPreview);
      }
    } else if (draft.kind === "scene" && ["chapter", "scene", "register"].includes(hints.scene_scope)) {
      method = uiLabel("research_dossier_draft_reason_scene_" + hints.scene_scope);
    }
    return method ? '<div class="ctl-guidance research-draft-reason" data-draft-reason><h6>' + label("research_dossier_draft_reason") +
      '</h6><p id="r-manuscript-draft-why" data-draft-reason-method>' + escapeHtml(method) + '</p>' + passage + '</div>' : "";
  }

  function preview(draft) {
    var existing = existingCharacterDossier(draft);
    var canSave = !state.saving && !state.stale;
    var action = existing ? 'data-draft-stage-existing' : 'data-create-manuscript-draft';
    var actionLabel = existing ? "research_dossier_draft_stage_existing" : "research_dossier_draft_create";
    var reason = reasonMarkup(draft);
    return '<section id="r-manuscript-draft-preview" class="research-card" aria-labelledby="r-manuscript-draft-title">' +
      '<div class="chip-row research-draft-preview-actions"><div><h5 class="research-card-title" id="r-manuscript-draft-title">' +
      escapeHtml(existing ? uiFormat("research_dossier_draft_existing_notice", {title: existing.title}) : draft.title) + '</h5>' +
      (existing ? '<p class="ctl-note">' + label("research_dossier_draft_stage_help") + '</p>' : '') + '</div>' +
      '<button type="button" class="ctl' + (canSave ? ' primary' : '') + '" ' + action + '="' + escapeHtml(draft.id) + '"' +
      (reason ? ' aria-describedby="r-manuscript-draft-why"' : '') + (canSave ? '' : ' disabled') +
      '>' + label(actionLabel) + '</button></div>' +
      reason + manuscriptDraftSettingsHtml(draft.kind) +
      (existing ? '' :
      '<h6>' + label("research_dossier_draft_preview") + '</h6>' +
      '<div data-draft-preview-body><div class="research-prose markdown-body research-dossier-body-rendered">' +
      renderSafeMarkdown(draft.body) + '</div></div>') + '</section>';
  }

  if (selectedButton) {
    var selectedDraft = selectedManuscriptDraft(state);
    var previousButton = host.querySelector('[data-draft-select][aria-pressed="true"]');
    var currentPreview = host.querySelector("#r-manuscript-draft-preview");
    if (selectedDraft && previousButton && currentPreview) {
      currentPreview.outerHTML = preview(selectedDraft);
      previousButton.setAttribute("aria-pressed", "false");
      previousButton.classList.remove("active");
      selectedButton.setAttribute("aria-pressed", "true");
      selectedButton.classList.add("active");
      return;
    }
  }

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
  var selected = selectedManuscriptDraft(state) || active[0];
  if (selected) state.selectedByKind[state.activeKind] = selected.id;
  else delete state.selectedByKind[state.activeKind];

  var html = "";
  if (state.saved) {
    html += '<div class="chip-row"><p class="ctl-status ok" role="status">' +
      label("research_dossier_draft_saved") + ' <strong>' + escapeHtml(state.saved.title) + '</strong></p>' +
      '<button type="button" class="ctl' + (selected || state.stale ? ' ctl-sm' : ' primary') +
      '" data-draft-open-saved data-research-history="dossier" data-record-id="' +
      escapeHtml(state.saved.id) + '">' + label("research_dossier_draft_open_saved") + '</button></div>';
  }
  if (state.stale) {
    html += '<div class="chip-row" data-draft-stale><p class="ctl-status err" id="r-draft-reload-help" role="alert">' +
      label("research_dossier_draft_stale") + '</p><button type="button" class="ctl primary" ' +
      'aria-describedby="r-draft-reload-help" data-draft-reload>' +
      label("research_dossier_draft_reload") + '</button></div>';
  } else if (state.error) html += '<p class="ctl-status err" role="alert" data-draft-error>' + escapeHtml(state.error) + '</p>';
  if (state.includeExisting) {
    host.innerHTML = html + (selected ? catalogue(groups.character, "research_dossier_draft_existing_choices", "character-existing") + preview(selected) :
      '<p class="ctl-note">' + label("research_dossier_draft_existing_empty") + '</p>');
    return;
  }
  var unavailable = ["scene", "location"].filter(function(kind) { return typeof state.unavailable?.[kind] === "string"; });
  html += unavailable.map(function(kind) {
    return '<p class="ctl-note err" data-draft-unavailable="' + kind + '" role="status">' +
      label("research_dossier_draft_" + kind + "_unavailable") + '</p>';
  }).join("");
  if (!groups.character.length) {
    html += '<div class="chip-row"><p class="ctl-note ctl-guidance">' +
      label(drafts.length || unavailable.length ? "research_dossier_draft_no_characters" : "research_dossier_draft_empty") + '</p>' +
      '<button type="button" class="ctl' +
      (!selected && !state.saved && !state.stale && state.activeKind === "character" ? ' primary' : '') +
      '" data-draft-manual-character>' +
      label("research_dossier_draft_manual_character") + '</button></div>';
  }
  if (!drafts.length) {
    host.innerHTML = html + manuscriptDraftSettingsHtml();
    return;
  }
  html += '<div class="chip-row" role="group" aria-label="' + label("research_dossier_draft_cloud") + '">' +
    manuscriptDraftKinds.map(function(kind) {
      var pressed = kind === state.activeKind;
      return '<button type="button" class="ctl ctl-sm ctl-choice' + (pressed ? " active" : "") +
        '" data-draft-kind="' + kind + '" aria-pressed="' + pressed + '">' +
        escapeHtml(kindLabels[kind]) + " (" + number.format(groups[kind].length) + ")</button>";
    }).join("") + '</div>';
  if (!selected) {
    host.innerHTML = html + (state.activeKind === "character" || unavailable.includes(state.activeKind) ? '' :
      '<p class="ctl-note">' + escapeHtml(uiFormat("research_dossier_draft_no_kind", {kind: kindLabels[state.activeKind]})) + '</p>') +
      manuscriptDraftSettingsHtml(state.activeKind);
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
      (!save || !save.disabled)) {
    var characterTag = uiLabel("research_tpl_character_tag");
    var preset = Array.from(composer.querySelectorAll("#r-dos-templates [data-template-tag]"))
      .find(function(button) { return button.dataset.templateTag === characterTag; });
    if (preset) preset.click();
  }
  openResearchDossierComposer();
}

async function readManuscriptDrafts(includeExisting) {
  var data = await researchApiGet(includeExisting ? existingManuscriptDraftsEndpoint : "research/manuscript-dossier-drafts");
  if (!data || data.ok !== true || !Array.isArray(data.drafts) || !data.drafts.every(function(draft) {
    return draft && typeof draft.id === "string" && draft.id && typeof draft.title === "string" &&
      typeof draft.body === "string" && /^[a-f0-9]{64}$/.test(draft.preview_sha256) && manuscriptDraftKinds.includes(draft.kind);
  }) || new Set(data.drafts.map(function(draft) { return draft.id; })).size !== data.drafts.length) {
    throw new Error(uiLabel("research_status_unavailable"));
  }
  return data;
}

async function stageCharacterDraft(id, context, expected, canOpen) {
  var draft = await researchApiGet("research/dossier-character?format=markdown&prepare=1&id=" + encodeURIComponent(id));
  if (!canOpen() || !acceptResearchContext(context, draft || {})) return "stale";
  if (draft?.code === "character-dossier-too-large") return "too-large";
  if (draft?.code === "character-dossier-empty") return "unavailable";
  var existing = manuscriptDossierReference(draft);
  if (!draft || !draft.ok || !existing || existing.id !== id || existing.project_id !== context.projectId ||
      typeof draft.body !== "string" || !draft.body.trim() ||
      typeof draft.staged_body !== "string" || !draft.staged_body.trim()) return "unavailable";
  if (expected && (existing.revision !== expected.revision || existing.project_id !== expected.project_id)) return "stale";
  return window.LixityResearchDrafts.stageDossierBody(id, function(envelope) {
    return prepareManuscriptDossierRefresh(draft, envelope);
  });
}

function manuscriptDraftStageMessage(result) {
  var labels = {same: "research_dossier_draft_staged_same", stale: "research_dossier_draft_revision_retry",
    unavailable: "research_dossier_draft_unavailable", "too-large": "research_dossier_draft_too_large"};
  return result === "staged" ? "" : uiLabel(labels[result] || "research_status_unavailable");
}

document.addEventListener("click", async function(event) {
  var button = event.target.closest("[data-update-character-dossier]");
  if (!button || button.getAttribute("aria-disabled") === "true" || !window.LixityResearchDrafts) return;
  var status = button.parentElement.querySelector("[data-character-update-status]");
  var context = researchReadContext();
  var message = "";
  button.setAttribute("aria-disabled", "true");
  if (status) {
    status.hidden = false;
    status.textContent = uiLabel("research_loading");
  }
  try {
    var result = await stageCharacterDraft(button.dataset.recordId, context, null, function() {
      return button.isConnected;
    });
    message = manuscriptDraftStageMessage(result);
  } catch (_) {
    message = uiLabel("research_status_unavailable");
  } finally {
    button.removeAttribute("aria-disabled");
    if (status) {
      status.textContent = acceptResearchContext(context, {}) ? message : "";
      status.hidden = !status.textContent;
    }
  }
});

async function loadManuscriptDraftCatalogue(host, trigger) {
  if (host.getAttribute("aria-busy") === "true" || manuscriptDraftsState?.saving) return;
  var previous = currentManuscriptDraftCatalogue(manuscriptDraftsState) ? manuscriptDraftsState : null;
  var includeExisting = trigger.hasAttribute("data-draft-load-existing") ||
    Boolean(previous?.includeExisting && trigger.hasAttribute("data-draft-reload"));
  var sameMode = previous?.includeExisting === includeExisting;
  var token = researchContextToken();
  var loadFocused = document.activeElement === trigger;
  var state = null;
  function ownsLoad() { return token === researchContextToken() && (!state || currentManuscriptDraftCatalogue(state)); }

  host.setAttribute("aria-busy", "true");
  setManuscriptDraftStatus(uiLabel("research_dossier_character_loading"), "loading");
  host.replaceChildren();
  try {
    if (!researchSelectionProjectId && researchProjectInfoPending) await researchProjectInfoPending;
    if (!ownsLoad()) return;
    state = {context: researchReadContext(), drafts: [],
      selectedByKind: sameMode ? previous.selectedByKind : Object.create(null),
      activeKind: includeExisting ? "character" : sameMode ? previous.activeKind : null,
      includeExisting: includeExisting, saving: false, stale: false, error: "", saved: null};
    manuscriptDraftsState = state;
    setManuscriptDraftMode(state);
    var data = await readManuscriptDrafts(includeExisting);
    if (!currentManuscriptDraftCatalogue(state, data)) return;
    state.drafts = includeExisting ? data.drafts.filter(existingCharacterDossier) : data.drafts;
    state.unavailable = data.unavailable;
    if (!state.drafts.some(function(draft) { return draft.kind === state.activeKind; })) {
      state.activeKind = firstManuscriptDraftKind(state.drafts);
    }
    renderManuscriptDraftsView(host, state);
  } catch (_) {
    if (ownsLoad()) {
      host.innerHTML = '<p class="ctl-status err" role="alert">' + escapeHtml(uiLabel("research_status_unavailable")) + "</p>";
      setManuscriptDraftMode(state || {includeExisting: includeExisting}, true);
    }
  } finally {
    host.removeAttribute("aria-busy");
    if (ownsLoad()) {
      setManuscriptDraftStatus();
      if (loadFocused && document.activeElement === document.body) {
        (host.querySelector('[data-draft-select][aria-pressed="true"]') ||
          manuscriptDraftsBox.querySelector('[aria-pressed="true"]'))?.focus();
      }
    }
  }
}

async function reviewManuscriptDraft(host, state, button, draft) {
  var existing = existingCharacterDossier(draft);
  if (!existing || !window.LixityResearchDrafts) return;
  state.saving = true;
  state.error = "";
  host.querySelector('[data-draft-error]')?.remove();
  button.setAttribute("aria-disabled", "true");
  setManuscriptDraftStatus(uiLabel("research_dossier_character_loading"), "loading");
  var result;
  try {
    result = await stageCharacterDraft(existing.id, state.context, existing, function() {
      return currentManuscriptDraftCatalogue(state) && selectedManuscriptDraft(state) === draft && button.isConnected;
    });
  } catch (_) {
    result = "failed";
  } finally {
    state.saving = false;
    button.removeAttribute("aria-disabled");
  }
  if (!currentManuscriptDraftCatalogue(state)) return;
  var message = manuscriptDraftStageMessage(result);
  setManuscriptDraftStatus(result === "same" ? message : "", result === "same" ? "ok" : "");
  state.stale = result === "stale";
  if (result !== "same" && result !== "stale") state.error = message;
  if (state.stale || state.error) {
    var restore = host.contains(document.activeElement);
    renderManuscriptDraftsView(host, state);
    if (restore) host.querySelector(state.stale ? "[data-draft-reload]" : '[data-draft-select][aria-pressed="true"]')?.focus();
  }
}

async function saveManuscriptDraft(host, state, button, draft) {
  var saveFocused = document.activeElement === button;
  state.saving = true;
  state.error = "";
  button.disabled = true;
  var created;
  try {
    created = await researchApiPost("research-dossier-from-manuscript", {
      draft_id: draft.id, preview_sha256: draft.preview_sha256, project_id: state.context.projectId || undefined,
    });
  } catch (error) {
    created = {ok: false, message: error?.message};
  } finally {
    state.saving = false;
  }
  if (!currentManuscriptDraftCatalogue(state, created || {})) return;
  var saved = created?.ok;
  if (saved) {
    state.drafts = state.drafts.filter(function(item) { return item !== draft; });
    delete state.selectedByKind[draft.kind];
    if (!state.drafts.some(function(item) { return item.kind === state.activeKind; })) {
      state.activeKind = firstManuscriptDraftKind(state.drafts);
    }
    if (typeof created.dossier_id === "string" && created.dossier_id) {
      state.saved = {id: created.dossier_id, title: created.title || draft.title};
    }
  } else if (created?.code === "stale-draft" || created?.http_status === 409) state.stale = true;
  else state.error = created?.message || uiLabel("research_status_unavailable");

  var currentFocus = document.activeElement;
  var lostFocus = saveFocused && currentFocus === document.body;
  var selection = '[data-draft-select][aria-pressed="true"]';
  var focusSelector = currentFocus?.dataset?.draftKind ? '[data-draft-kind][aria-pressed="true"]' : selection;
  if (!saved && (currentFocus === button || lostFocus)) {
    focusSelector = state.stale ? "[data-draft-reload]" : "[data-create-manuscript-draft]";
  }
  var restoreFocus = host.contains(currentFocus) || lostFocus;
  renderManuscriptDraftsView(host, state);
  if (restoreFocus) {
    (host.querySelector(focusSelector) || host.querySelector(selection) ||
      host.querySelector('[data-draft-open-saved], [data-draft-manual-character]') ||
      document.getElementById("r-manuscript-dossier-btn"))?.focus();
  }
  if (saved) await refreshResearchDossiers();
}

manuscriptDraftsBox?.addEventListener("click", async function (event) {
  var host = document.getElementById("r-manuscript-drafts");
  if (!host) return;
  var load = event.target.closest("#r-manuscript-dossier-btn, [data-draft-reload], [data-draft-load-existing]");
  if (load) return loadManuscriptDraftCatalogue(host, load);
  if (event.target.closest("[data-draft-manual-character]")) return openManualCharacterDossier();
  var settingsAction = event.target.closest("[data-draft-settings-target]");
  if (settingsAction && host.contains(settingsAction)) {
    var target = document.getElementById(settingsAction.dataset.draftSettingsTarget);
    if (target) {
      if (target.matches("details")) target.open = true;
      scrollAndFlash(target);
      (target.querySelector("summary") || target).focus({preventScroll: true});
    }
    return;
  }
  if (!host.contains(event.target)) return;

  var state = manuscriptDraftsState;
  if (!currentManuscriptDraftCatalogue(state) || state.saving) return;
  var selection = event.target.closest("[data-draft-kind], [data-draft-select]");
  if (selection) {
    var kind = selection.dataset.draftKind;
    if (kind) {
      if (!manuscriptDraftKinds.includes(kind) || kind === state.activeKind) return;
      state.activeKind = kind;
    } else {
      var id = selection.dataset.draftSelect;
      if (id === state.selectedByKind[state.activeKind]) return;
      state.selectedByKind[state.activeKind] = id;
    }
    renderManuscriptDraftsView(host, state, kind ? null : selection);
    setManuscriptDraftStatus();
    host.querySelector((kind ? "[data-draft-kind]" : "[data-draft-select]") + '[aria-pressed="true"]')?.focus();
    return;
  }

  var button = event.target.closest("[data-draft-stage-existing], [data-create-manuscript-draft]");
  if (!button || state.stale) return;
  var draft = selectedManuscriptDraft(state);
  if (!draft) return;
  if (state.includeExisting && button.dataset.draftStageExisting === draft.id) return reviewManuscriptDraft(host, state, button, draft);
  if (!state.includeExisting && button.dataset.createManuscriptDraft === draft.id && !draft.already_covered) {
    return saveManuscriptDraft(host, state, button, draft);
  }
});
