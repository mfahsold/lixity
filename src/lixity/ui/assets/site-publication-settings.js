/* Curated publication profiles use the existing project settings transaction. */
(function() {
  "use strict";
  var editor = document.getElementById("site-publication-editor");
  if (!editor) return;
  var labels = JSON.parse(editor.dataset.labels);
  var initial;
  try { initial = JSON.parse(editor.dataset.initial); } catch (_) { initial = null; }
  var profiles = editor.querySelector("[data-site-publication-profiles]");
  var addProfile = editor.querySelector("[data-site-publication-add-profile]");
  var status = editor.querySelector("[data-site-publication-status]");
  var retry = editor.querySelector("[data-site-publication-retry]");
  var catalogue = [], catalogueLoaded = false, cataloguePending = false, serial = 0, recovery;
  var contextToken = editor.dataset.contextToken;
  function text(key) { return labels["publication_editor_" + key]; }
  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function object(value) { return value && typeof value === "object" && !Array.isArray(value); }
  function supported(value) {
    if (!object(value)) return false;
    return Object.values(value).every(function(profile) {
      return object(profile) && Object.keys(profile).every(function(key) { return ["title", "introduction", "entries"].includes(key); }) &&
        typeof profile.title === "string" &&
        (!Object.hasOwn(profile, "introduction") || typeof profile.introduction === "string") &&
        (!Object.hasOwn(profile, "entries") || Array.isArray(profile.entries) && profile.entries.every(function(entry) {
          return object(entry) && Object.keys(entry).every(function(key) {
            return ["dossier_id", "revision", "section", "reveal_after_chapter", "title", "include_citations", "include_geography"].includes(key);
          }) && typeof entry.dossier_id === "string" &&
            ["section", "title"].every(function(key) { return entry[key] == null || typeof entry[key] === "string" && entry[key].trim(); }) &&
            (entry.revision == null || typeof entry.revision === "number") &&
            (!Object.hasOwn(entry, "reveal_after_chapter") || typeof entry.reveal_after_chapter === "number") &&
            ["include_citations", "include_geography"].every(function(key) { return !Object.hasOwn(entry, key) || typeof entry[key] === "boolean"; });
        }));
    });
  }
  function normalized(value) {
    var result = Object.create(null);
    Object.entries(value).forEach(function(pair) {
      var profile = pair[1];
      result[pair[0]] = {title: (profile.title || "").trim(), introduction: (profile.introduction || "").trim(),
        entries: (profile.entries || []).map(function(entry) {
          var item = {dossier_id: entry.dossier_id || "", reveal_after_chapter: entry.reveal_after_chapter == null ? 0 : entry.reveal_after_chapter,
            include_citations: entry.include_citations === true, include_geography: entry.include_geography === true};
          if (entry.revision != null) item.revision = entry.revision;
          ["section", "title"].forEach(function(key) { if (entry[key] != null) item[key] = entry[key].trim(); });
          return item;
        })};
    });
    return result;
  }
  var saved = supported(initial) ? normalized(initial) : {};
  var initialNormalized = supported(initial) ? JSON.stringify(saved) : null;
  function field(node, key) { return node.querySelector('[data-site-publication-field="' + key + '"]'); }
  function control(parent, key, title, value, kind) {
    var wrapper = document.createElement("label"); wrapper.className = "setting-field";
    wrapper.appendChild(document.createTextNode(text(title)));
    var input = document.createElement(kind === "select" ? "select" : kind === "textarea" ? "textarea" : "input");
    input.className = "ctl"; input.id = "site-publication-field-" + (++serial);
    input.dataset.sitePublicationField = key;
    if (kind === "textarea") input.rows = 3;
    else if (kind !== "select") input.type = kind || "text";
    input.value = value == null ? "" : value;
    wrapper.appendChild(input); parent.appendChild(wrapper); return input;
  }
  function checkbox(parent, key, value) {
    var label = document.createElement("label"); label.className = "form-checkbox";
    var input = document.createElement("input"); input.type = "checkbox";
    input.id = "site-publication-field-" + (++serial); input.dataset.sitePublicationField = key;
    input.checked = value === true;
    label.appendChild(input); var span = document.createElement("span");
    span.textContent = text(key === "include_citations" ? "citations" : "geography");
    label.appendChild(span); parent.appendChild(label); return input;
  }
  function button(parent, label, attribute, action) {
    var node = document.createElement("button"); node.className = "ctl"; node.type = "button";
    node.textContent = label; node.setAttribute(attribute, ""); node.addEventListener("click", action);
    parent.appendChild(node); return node;
  }
  function option(select, value, label) {
    var node = document.createElement("option"); node.value = value; node.textContent = label; select.appendChild(node);
  }
  function options(select, values, value, placeholder) {
    select.replaceChildren(); option(select, "", placeholder);
    values.forEach(function(pair) { option(select, String(pair[0]), pair[1]); });
    if (value != null && value !== "" && !values.some(function(pair) { return String(pair[0]) === String(value); })) option(select, String(value), text("missing") + ": " + value);
    select.value = value == null ? "" : String(value);
  }
  function summary(card) {
    if (card.hasAttribute("data-site-publication-profile")) {
      card.querySelector(":scope > summary").textContent = field(card, "title").value || field(card, "id").value || text("profile");
    } else {
      var selected = field(card, "dossier_id");
      var dossier = catalogue.find(function(item) { return item.id === selected.value; });
      card.querySelector(":scope > summary").textContent = field(card, "title").value || (dossier && dossier.title) || text("entry");
    }
  }
  function remove(node, actions, fallback) {
    button(actions, labels.remove_recent_project, "data-site-publication-remove", function() {
      node.remove(); updateLimits(); clearValidity(); fallback.focus();
    });
  }
  function clearValidity() { editor.querySelectorAll("input, select, textarea").forEach(function(input) { input.setCustomValidity(""); }); }
  function updateLimits() {
    addProfile.disabled = profiles.children.length >= 50;
    profiles.querySelectorAll("[data-site-publication-profile]").forEach(function(profile) {
      var entries = profile.querySelector("[data-site-publication-entries]");
      profile.querySelector("[data-site-publication-add-entry]").disabled = entries.children.length >= 500;
      Array.from(entries.children).forEach(function(entry, index) {
        entry.querySelector("[data-site-publication-up]").disabled = index === 0;
        entry.querySelector("[data-site-publication-down]").disabled = index === entries.children.length - 1;
      });
    });
  }
  async function getDossiers(query) {
    var parameters = new URLSearchParams(query || {});
    parameters.set("research_token", contextToken);
    return jsonApi(API + "/research/dossiers?" + parameters.toString());
  }
  function updateDossier(entry) {
    var select = field(entry, "dossier_id"), value = select.value;
    options(select, catalogue.map(function(item) { return [item.id, item.title]; }), value, text("choose_dossier"));
    var dossier = catalogue.find(function(item) { return item.id === value; });
    var revision = field(entry, "revision"), prior = revision.value, versions = [];
    if (dossier) for (var number = 1; number <= Math.min(dossier.revision, 10000); number++) versions.push([String(number), text("version").replace("{number}", number)]);
    options(revision, versions, prior, text("current"));
    summary(entry); loadSections(entry);
  }
  async function loadSections(entry) {
    var dossierId = field(entry, "dossier_id").value, revision = field(entry, "revision").value;
    var request = entry._sectionRequest = (entry._sectionRequest || 0) + 1;
    if (!catalogueLoaded || !catalogue.some(function(item) { return item.id === dossierId; })) return;
    var query = {id: dossierId}; if (revision) query.revision = revision;
    var result = await getDossiers(query);
    if (!editor.isConnected || !entry.isConnected || request !== entry._sectionRequest || editor.dataset.contextToken !== contextToken) return;
    if (!result.ok) {
      status.textContent = text("load_error"); retry.hidden = false;
      reportSiteExport("catalogue_failed", {http_status:result.http_status, error_name:"Error"});
      return;
    }
    var select = field(entry, "section"), value = select.value;
    // Native editable_sections contains only unique real headings, including
    // nested subtrees; merged duplicate labels are not publication choices.
    options(select, (result.editable_sections || []).map(function(name) { return [name, name]; }), value, text("whole_body"));
  }
  async function loadCatalogue() {
    if (editor.disabled || !contextToken || cataloguePending || catalogueLoaded) return;
    cataloguePending = true; status.textContent = text("loading"); retry.hidden = true;
    var result = await getDossiers(); cataloguePending = false;
    if (!editor.isConnected || editor.dataset.contextToken !== contextToken) return;
    if (!result.ok) {
      status.textContent = text("load_error"); retry.hidden = false;
      reportSiteExport("catalogue_failed", {http_status:result.http_status, error_name:"Error"});
      return;
    }
    catalogue = result.dossiers || []; catalogueLoaded = true;
    status.textContent = catalogue.length ? "" : text("no_dossiers");
    profiles.querySelectorAll("[data-site-publication-entry]").forEach(updateDossier);
  }
  function addEntry(profile, value, open) {
    value = value || {};
    var entries = profile.querySelector("[data-site-publication-entries]");
    var entry = document.createElement("details"); entry.className = "site-publication-entry";
    entry.setAttribute("data-site-publication-entry", ""); entry.open = Boolean(open);
    var heading = document.createElement("summary"); heading.textContent = text("entry"); entry.appendChild(heading);
    var grid = document.createElement("div"); grid.className = "settings-grid"; entry.appendChild(grid);
    var dossier = control(grid, "dossier_id", "dossier", "", "select"); dossier.required = true;
    options(dossier, [], value.dossier_id, text("choose_dossier"));
    var revision = control(grid, "revision", "revision", "", "select");
    options(revision, [], value.revision, text("current"));
    var section = control(grid, "section", "section", "", "select");
    options(section, [], value.section, text("whole_body"));
    var chapter = control(grid, "reveal_after_chapter", "after", value.reveal_after_chapter == null ? 0 : value.reveal_after_chapter, "number");
    chapter.min = "0"; chapter.step = "1"; chapter.required = true;
    var hint = document.createElement("p"); hint.className = "ctl-note"; hint.id = chapter.id + "-help";
    hint.textContent = text("after_hint"); chapter.parentElement.appendChild(hint); chapter.setAttribute("aria-describedby", hint.id);
    control(grid, "title", "override", value.title).maxLength = 500;
    var scope = document.createElement("p"); scope.className = "ctl-note"; scope.textContent = text("scope");
    scope.id = "site-publication-scope-" + (++serial); entry.appendChild(scope);
    var scopeChoices = document.createElement("div"); scopeChoices.className = "row"; entry.appendChild(scopeChoices);
    ["include_citations", "include_geography"].forEach(function(key) { checkbox(scopeChoices, key, value[key]).setAttribute("aria-describedby", scope.id); });
    var actions = document.createElement("div"); actions.className = "settings-actions"; entry.appendChild(actions);
    button(actions, text("move_up"), "data-site-publication-up", function() {
      if (entry.previousElementSibling) entries.insertBefore(entry, entry.previousElementSibling);
      updateLimits(); (this.disabled ? heading : this).focus();
    });
    button(actions, text("move_down"), "data-site-publication-down", function() {
      if (entry.nextElementSibling) entries.insertBefore(entry.nextElementSibling, entry);
      updateLimits(); (this.disabled ? heading : this).focus();
    });
    remove(entry, actions, profile.querySelector("[data-site-publication-add-entry]"));
    dossier.addEventListener("change", function() { updateDossier(entry); });
    revision.addEventListener("change", function() { loadSections(entry); });
    entry.addEventListener("input", function() { summary(entry); });
    entries.appendChild(entry); updateDossier(entry); updateLimits(); return entry;
  }
  function add(value, name, open) {
    value = value || {};
    var profile = document.createElement("details"); profile.className = "site-publication-profile";
    profile.setAttribute("data-site-publication-profile", ""); profile.open = Boolean(open);
    profile.appendChild(document.createElement("summary"));
    var grid = document.createElement("div"); grid.className = "settings-grid"; profile.appendChild(grid);
    var identifier = control(grid, "id", "id", name); identifier.required = true;
    identifier.pattern = "[a-z][a-z0-9_\\-]{0,63}"; identifier.maxLength = 64;
    var identifierHint = document.createElement("p"); identifierHint.className = "ctl-note";
    identifierHint.id = identifier.id + "-help"; identifierHint.textContent = text("id_hint");
    identifier.parentElement.appendChild(identifierHint); identifier.setAttribute("aria-describedby", identifierHint.id);
    identifier.title = text("id_hint");
    var title = control(grid, "title", "name", value.title); title.required = true; title.maxLength = 500;
    control(profile, "introduction", "introduction", value.introduction, "textarea").maxLength = 10000;
    var entriesTitle = document.createElement("h4"); entriesTitle.textContent = text("entries"); profile.appendChild(entriesTitle);
    var entries = document.createElement("div"); entries.setAttribute("data-site-publication-entries", ""); profile.appendChild(entries);
    var actions = document.createElement("div"); actions.className = "settings-actions"; profile.appendChild(actions);
    button(actions, text("add_entry"), "data-site-publication-add-entry", function() {
      var entry = addEntry(profile, {}, true); field(entry, "dossier_id").focus();
    });
    remove(profile, actions, addProfile);
    profiles.appendChild(profile);
    (value.entries || []).forEach(function(entry) { addEntry(profile, entry); });
    profile.addEventListener("input", function() { summary(profile); });
    summary(profile); updateLimits(); return profile;
  }
  function show(value) {
    profiles.replaceChildren(); recovery = null;
    Object.entries(value).forEach(function(pair) { add(pair[1], pair[0]); });
    addProfile.hidden = false; updateLimits();
  }
  function showRecovery(value) {
    addProfile.hidden = true;
    var warning = document.createElement("p"); warning.className = "ctl-status err";
    warning.textContent = text("raw_error"); profiles.appendChild(warning);
    recovery = control(profiles, "recovery", "raw", value, "textarea"); recovery.rows = 8;
    button(profiles, text("recover"), "data-site-publication-recover", function() {
      var candidate;
      try { candidate = JSON.parse(recovery.value); } catch (_) { /* Retain the original for correction. */ }
      if (!supported(candidate)) { recovery.setCustomValidity(text("raw_error")); recovery.reportValidity(); return; }
      show(candidate); profiles.querySelector("input, button")?.focus();
    });
  }
  function read(validate) {
    validate = validate !== false;
    if (validate) clearValidity();
    if (recovery) {
      try {
        var candidate = JSON.parse(recovery.value);
        if (supported(candidate)) return normalized(candidate);
      } catch (_) { /* Failed recovery never becomes an empty profile map. */ }
      if (validate) recovery.setCustomValidity(text("raw_error"));
      return null;
    }
    var result = Object.create(null);
    profiles.querySelectorAll("[data-site-publication-profile]").forEach(function(profile) {
      var identifier = field(profile, "id"), name = identifier.value;
      if (validate && (!/^[a-z][a-z0-9_-]{0,63}$/.test(name) || Object.hasOwn(result, name))) identifier.setCustomValidity(text("invalid"));
      var title = field(profile, "title"); if (validate && !title.value.trim()) title.setCustomValidity(text("invalid"));
      result[name] = {title: title.value.trim(), introduction: field(profile, "introduction").value.trim(), entries: []};
      profile.querySelectorAll("[data-site-publication-entry]").forEach(function(entry) {
        var dossier = field(entry, "dossier_id"), chapter = field(entry, "reveal_after_chapter");
        if (validate && !/^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(dossier.value)) dossier.setCustomValidity(text("invalid"));
        if (validate && (!Number.isSafeInteger(chapter.valueAsNumber) || chapter.valueAsNumber < 0)) chapter.setCustomValidity(text("invalid"));
        var item = {dossier_id: dossier.value, reveal_after_chapter: chapter.valueAsNumber,
          include_citations: field(entry, "include_citations").checked, include_geography: field(entry, "include_geography").checked};
        var revision = field(entry, "revision");
        if (revision.value) {
          item.revision = Number(revision.value);
          if (validate && (!Number.isSafeInteger(item.revision) || item.revision < 1)) revision.setCustomValidity(text("invalid"));
        }
        ["section", "title"].forEach(function(key) { var value = field(entry, key).value.trim(); if (value) item[key] = value; });
        result[name].entries.push(item);
      });
    });
    return result;
  }
  if (supported(initial)) show(initial);
  else showRecovery(editor.dataset.initial);
  addProfile.addEventListener("click", function() { field(add({}, "", true), "id").focus(); loadCatalogue(); });
  retry.addEventListener("click", function() {
    if (catalogueLoaded) {
      retry.hidden = true; status.textContent = "";
      profiles.querySelectorAll("[data-site-publication-entry]").forEach(loadSections);
    } else loadCatalogue();
  });
  editor.addEventListener("input", clearValidity);
  editor.closest("details").addEventListener("toggle", function() { if (this.open) loadCatalogue(); });
  window.LixityPublicationSettings = {
    readChanges: function() {
      if (editor.disabled) return {};
      if (recovery && recovery.value === editor.dataset.initial) {
        recovery.setCustomValidity(""); return {};
      }
      var value = read();
      return value && JSON.stringify(value) !== initialNormalized ? {site_publications: value} : {};
    },
    accepted: function(value) {
      saved = normalized(value); initialNormalized = JSON.stringify(saved);
      document.dispatchEvent(new CustomEvent("lixity:site-publications-saved"));
    },
    savedProfiles: function() { return clone(saved); },
    state: function() {
      return {invalid:initialNormalized === null,
        unsaved:recovery && recovery.value === editor.dataset.initial ? false :
          JSON.stringify(read(false)) !== initialNormalized};
    }
  };
})();
