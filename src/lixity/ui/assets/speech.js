/* Project-local listening drafts share one token-bound native dialog. */
(function() {
  "use strict";
  var body = document.body, settingsForm = document.getElementById("settings-form");
  if (body.dataset.speechCapable !== "true" || body.dataset.readOnly === "true" || !settingsForm) return;
  var dialog, fields = {}, settings, capabilities, generation = 0, job = null, timer, openedContext, paragraph;
  var executionTarget = "local";
  function label(key) { return uiLabel("speech_" + key); }
  function languageName(code) {
    try { return new Intl.DisplayNames([document.documentElement.lang || "en"], {type: "language"}).of(code); }
    catch (_) { return code; }
  }
  function context() { return [settingsForm.dataset.projectToken, body.dataset.manuscriptSourceSha256].join(":"); }
  function tokens() { return {project_token: settingsForm.dataset.projectToken, source_sha256: body.dataset.manuscriptSourceSha256}; }
  function url(route, extra) { return API + "/" + route + "?" + new URLSearchParams(Object.assign(tokens(), extra || {})); }
  async function request(route, payload) {
    var response = await fetch(payload ? API + "/" + route : url(route), payload ? {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)
    } : {});
    var data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.message || data.error || label("failed"));
    return data;
  }
  function node(tag, parent, className, text) {
    var el = document.createElement(tag); if (className) el.className = className;
    if (text != null) el.textContent = text; if (parent) parent.appendChild(el); return el;
  }
  function button(parent, key, action) {
    var el = node("button", parent, "ctl", label(key)); el.type = "button";
    el.dataset.speechAction = key; el.addEventListener("click", action); return el;
  }
  function field(parent, key, type) {
    var wrapper = node("label", parent, "setting-field", label(key));
    var input = node(type === "select" || type === "textarea" ? type : "input", wrapper, "ctl");
    input.id = "speech-" + key; fields[key] = input;
    if (input.tagName === "INPUT") input.type = type || "text";
    if (type === "textarea") input.rows = 3;
    return input;
  }
  function options(select, values, selected) {
    select.replaceChildren(); values.forEach(function(pair) { select.add(new Option(pair[1], pair[0])); });
    // Retain saved values visibly even when capabilities no longer list them.
    if (selected && !values.some(function(pair) { return pair[0] === selected; })) select.add(new Option(selected, selected));
    select.value = selected || (values[0] && values[0][0]) || "";
  }
  function status(message) { fields.status.textContent = message || ""; }
  function clearAudio() { fields.audio.pause(); fields.audio.removeAttribute("src"); fields.audio.load(); fields.audio.hidden = true; fields.download.hidden = true; fields.download.removeAttribute("href"); }
  function invalidate() {
    ++generation; clearTimeout(timer); clearAudio(); status("");
    if (job) {
      var previous = job; job = null;
      request("speech-cancel", Object.assign({}, previous.tokens, {id: previous.id})).catch(function() {});
    }
    fields.cancel.disabled = true; fields.preview.disabled = fields.chapter_render.disabled = !settings || !settings.selected || !fields.chapter.options.length;
    fields.progress.hidden = true;
  }
  function engineControls(reset) {
    var cap = capabilities[fields.engine.value];
    if (!cap) return;
    var language = fields.language.value, voice = fields.voice.value;
    if (reset) {
      language = cap.languages.includes(language) ? language : cap.languages[0];
      voice = ""; fields.instructions.value = ""; fields.speed.value = "1";
      status(label("engine_reset"));
    }
    options(fields.language, cap.languages.map(function(value) { return [value, languageName(value)]; }), language);
    var voices = Object.entries(cap.voices).filter(function(pair) { return pair[1].languages.includes(fields.language.value); });
    options(fields.voice, voices.map(function(pair) { return [pair[0], pair[1].name]; }), voice);
    fields.speed.disabled = !cap.speed.supported; fields.instructions.disabled = !cap.instructions;
    fields.advanced_voice.disabled = fields.engine.value !== "piper";
    options(fields.target, cap.targets.map(function(value) { return [value, label("target_" + value)]; }),
      cap.targets.includes(executionTarget) ? executionTarget : cap.targets[0]);
    fields.target.disabled = cap.targets.length < 2;
    fields.target.closest("label").hidden = fields.target.disabled;
    fields.runtime_hint.textContent = label(fields.target.value === "jetson" ? "jetson_hint" : "runtime_hint");
    fields.runtime_hint.hidden = fields.engine.value !== "qwen3";
    fields.reuse.disabled = fields.engine.value !== "qwen3";
    fields.reuse.closest("label").hidden = fields.reuse.disabled;
    ["advanced_voice", "speed", "instructions"].forEach(function(key) {
      fields[key].closest("label").hidden = fields[key].disabled;
    });
    if (reset) fields.advanced_voice.value = "";
  }
  function loadProfile() {
    invalidate();
    if (!settings.selected) return;
    var profile = settings.profiles[settings.selected];
    ["name", "engine", "speed", "instructions", "paragraph_pause", "scene_pause"].forEach(function(key) { fields[key].value = profile[key]; });
    options(fields.language, [], profile.language); options(fields.voice, [], profile.voice); engineControls(false);
    fields.advanced_voice.value = profile.engine === "piper" && !Object.hasOwn(capabilities.piper.voices, profile.voice) ? profile.voice : "";
    fields.pronunciations.value = Object.entries(profile.pronunciations).map(function(pair) { return pair.join("="); }).join("\n");
    fields.editor.disabled = false; fields.save.disabled = false;
  }
  function readProfile() {
    var replacements = Object.create(null);
    fields.pronunciations.value.split("\n").forEach(function(line) {
      if (!line.trim()) return;
      var split = line.indexOf("="), term = line.slice(0, split).trim(), value = line.slice(split + 1).trim();
      if (split < 1 || !term || !value || Object.hasOwn(replacements, term)) throw new Error(label("pronunciation_error"));
      replacements[term] = value;
    });
    return {name: fields.name.value.trim(), engine: fields.engine.value, language: fields.language.value,
      voice: fields.engine.value === "piper" && fields.advanced_voice.value.trim() ? fields.advanced_voice.value.trim() : fields.voice.value,
      speed: Number(fields.speed.value), instructions: fields.instructions.value.trim(),
      paragraph_pause: Number(fields.paragraph_pause.value), scene_pause: Number(fields.scene_pause.value), pronunciations: replacements};
  }
  function stash() { if (settings && settings.selected) settings.profiles[settings.selected] = readProfile(); }
  function profileOptions() {
    options(fields.profile, Object.entries(settings.profiles).map(function(pair) { return [pair[0], pair[1].name]; }), settings.selected);
    fields.create.disabled = Object.keys(settings.profiles).length >= 32;
  }
  function create() {
    try { stash(); } catch (error) { status(error.message); return; }
    var id = "narrator", index = 1;
    while (Object.hasOwn(settings.profiles, id)) id = "narrator_" + (++index);
    // Creating a Qwen profile is an explicit action, including unsupported default languages.
    var projectLanguage = document.getElementById("set-language");
    var language = fields.language.value || (projectLanguage && projectLanguage.value) || document.documentElement.lang;
    if (!capabilities.qwen3.languages.includes(language)) language = "en";
    settings.profiles[id] = {name: label("new_profile"), engine: "qwen3", language: language, voice: "Ryan", speed: 1,
      instructions: "", paragraph_pause: 0.45, scene_pause: 1.2, pronunciations: {}};
    settings.selected = id; profileOptions(); loadProfile(); fields.name.focus();
  }
  function valid(serial) { return serial === generation && dialog.open && openedContext === context(); }
  async function poll(serial, active) {
    if (!valid(serial) || job !== active) return;
    try {
      var response = await fetch(url("speech-job", {id: active.id})); var data = await response.json();
      if (!valid(serial) || job !== active) return;
      if (!response.ok || !data.ok) throw new Error(data.message || label("failed"));
      var result = data.job;
      fields.progress.max = result.total || 1; fields.progress.value = result.done || 0;
      status(label(active.cancelling && ["pending", "running"].includes(result.state) ? "cancelling" : "state_" + ({ready: "completed", error: "failed", stale: "failed"}[result.state] || result.state)) + (result.message ? ": " + result.message : ""));
      if (result.state === "ready" && active.cancelling) {
        status(label("cancelling")); timer = setTimeout(function() { poll(serial, active); }, 500); return;
      }
      if (result.state === "ready") {
        fields.audio.src = url("speech-audio", {id: active.id}); fields.audio.hidden = false;
        fields.context.textContent += result.context && result.context.excerpt ? " · " + result.context.excerpt : "";
        if (result.context && result.context.truncated) fields.context.textContent += " · " + label("truncated");
        fields.download.href = fields.audio.src; fields.download.hidden = false; finish();
      } else if (["error", "stale", "cancelled"].includes(result.state)) finish();
      else timer = setTimeout(function() { poll(serial, active); }, 500);
    } catch (error) { if (valid(serial)) { status(error.message); finish(); } }
  }
  function finish() { job = null; fields.cancel.disabled = true; fields.preview.disabled = fields.chapter_render.disabled = !settings || !settings.selected || !fields.chapter.options.length; }
  async function render(mode) {
    try {
      if (!Array.from(fields.editor.querySelectorAll("input, select, textarea")).every(function(input) { return input.reportValidity(); })) return;
      var profile = readProfile(); invalidate(); var serial = generation;
      fields.preview.disabled = fields.chapter_render.disabled = true;
      status(label("state_pending"));
      var payload = Object.assign(tokens(), {mode: mode, chapter: Number(fields.chapter.value), profile: profile, target: fields.target.value || "local"});
      if (mode === "preview" && paragraph) payload.paragraph = paragraph.identity;
      if (mode === "chapter" && profile.engine === "qwen3") payload.fresh_audio = !fields.reuse.checked;
      fields.context.textContent = label("target_" + payload.target) + " · " + (mode === "preview" ? label(paragraph ? "paragraph_preview" : "first_preview") : label("chapter_render")) + " · " + fields.chapter.selectedOptions[0].textContent +
        (mode === "preview" && paragraph ? " · " + paragraph.identity.start_line + "–" + paragraph.identity.end_line : "");
      var data = await request("speech-render", payload);
      if (!valid(serial)) { request("speech-cancel", Object.assign({}, {project_token: payload.project_token, source_sha256: payload.source_sha256}, {id: data.job.id})).catch(function() {}); return; }
      job = {id: data.job.id, tokens: tokens()}; fields.cancel.disabled = false; fields.progress.hidden = false; poll(serial, job);
    } catch (error) { if (serial == null || valid(serial)) { status(error.message); finish(); } }
  }
  async function cancel() {
    if (!job) return;
    var active = job; active.cancelling = true; fields.cancel.disabled = true; status(label("cancelling"));
    try { await request("speech-cancel", Object.assign({}, active.tokens, {id: active.id})); }
    catch (error) { if (job === active) { status(error.message); fields.cancel.disabled = false; active.cancelling = false; } }
  }
  async function save() {
    try {
      if (!Array.from(fields.editor.querySelectorAll("input, select, textarea")).every(function(input) { return input.reportValidity(); })) return;
      stash(); invalidate(); var serial = generation; fields.save.disabled = true; status(label("saving"));
      await request("settings", {project_token: tokens().project_token, audio: settings});
      if (valid(serial)) location.reload();
    } catch (error) { if (serial == null || valid(serial)) status(error.message); }
    finally { if (serial == null || valid(serial)) fields.save.disabled = false; }
  }
  function build() {
    dialog = node("dialog", body, "lixity-modal"); dialog.id = "modal-speech"; dialog.setAttribute("aria-labelledby", "speech-title");
    var card = node("div", dialog, "modal-card"), header = node("div", card, "modal-header");
    node("h3", header, "", label("title")).id = "speech-title";
    var close = button(header, "close", function() { dialog.close(); }); close.className = "ctl";
    var content = node("div", card, "modal-body");
    fields.status = node("p", content, "ctl-status"); fields.status.setAttribute("role", "status"); fields.status.setAttribute("aria-live", "polite");
    var row = node("div", content, "row"); field(row, "profile", "select"); fields.create = button(row, "create", create);
    fields.editor = node("fieldset", content, "settings-section");
    node("legend", fields.editor, "", label("delivery"));
    fields.runtime_hint = node("p", fields.editor, "ctl-note", label("runtime_hint")); fields.runtime_hint.hidden = true; fields.runtime_hint.id = "speech-runtime-hint";
    var grid = node("div", fields.editor, "settings-grid");
    field(grid, "name").maxLength = 100; fields.name.required = true;
    ["engine", "language", "voice"].forEach(function(key) { field(grid, key, "select"); });
    field(grid, "advanced_voice"); node("p", fields.editor, "ctl-note", label("voice_hint"));
    ["speed", "paragraph_pause", "scene_pause"].forEach(function(key) { var el = field(grid, key, "number"); el.min = key === "speed" ? "0.2" : "0"; el.max = key === "speed" ? "3" : "10"; el.step = "any"; el.required = true; });
    field(fields.editor, "instructions", "textarea").maxLength = 2000;
    field(fields.editor, "pronunciations", "textarea"); node("p", fields.editor, "ctl-note", label("pronunciation_hint"));
    field(content, "chapter", "select");
    field(content, "target", "select"); fields.target.closest("label").hidden = true;
    fields.target.addEventListener("change", function() {
      executionTarget = fields.target.value; invalidate();
      fields.runtime_hint.textContent = label(executionTarget === "jetson" ? "jetson_hint" : "runtime_hint");
    });
    var reuse = node("label", content, "form-checkbox"); reuse.hidden = true;
    fields.reuse = node("input", reuse); fields.reuse.type = "checkbox"; fields.reuse.id = "speech-reuse"; fields.reuse.checked = true;
    node("span", reuse, "", label("reuse"));
    fields.reuse.addEventListener("change", invalidate);
    var actions = node("div", content, "row");
    fields.preview = button(actions, "preview", function() { render("preview"); });
    fields.chapter_render = button(actions, "chapter_render", function() { render("chapter"); });
    fields.cancel = button(actions, "cancel", cancel); fields.cancel.disabled = true;
    fields.context = node("p", content, "ctl-note"); fields.progress = node("progress", content); fields.progress.hidden = true; fields.progress.setAttribute("aria-label", label("progress"));
    fields.audio = node("audio", content, "media-player"); fields.audio.controls = true; fields.audio.hidden = true;
    fields.download = node("a", content, "ctl", label("download")); fields.download.download = "speech.wav"; fields.download.hidden = true;
    fields.save = button(content, "save", save);
    fields.editor.addEventListener("input", function() { invalidate(); });
    fields.engine.addEventListener("change", function() { engineControls(true); });
    fields.language.addEventListener("change", function() { fields.voice.value = ""; fields.advanced_voice.value = ""; engineControls(false); status(label("voice_changed")); });
    fields.voice.addEventListener("change", function() { fields.advanced_voice.value = ""; });
    fields.profile.addEventListener("change", function() {
      try { stash(); settings.selected = fields.profile.value; loadProfile(); }
      catch (error) { fields.profile.value = settings.selected; status(error.message); }
    });
    fields.chapter.addEventListener("change", function() { paragraph = null; invalidate(); fields.context.textContent = label("first_preview"); });
    dialog.addEventListener("close", invalidate);
  }
  async function open(fromReader) {
    if (!dialog) build(); invalidate(); settings = null; openedContext = context(); paragraph = null;
    if (fromReader) {
      var selection = window.getSelection(), anchor = selection && selection.anchorNode;
      var element = anchor && (anchor.nodeType === 1 ? anchor : anchor.parentElement);
      var panel = element && element.closest("#chapters .ptext[data-paragraph-sha256]");
      if (!panel) panel = document.querySelector("#chapters .ptext.reader-selected, #chapters .ptext:focus-within");
      if (panel) paragraph = {chapter: Number((panel.closest(".chapter") || {}).id?.replace("ch-", "")), identity: {
        start_line: Number(panel.dataset.start), end_line: Number(panel.dataset.end), paragraph_sha256: panel.dataset.paragraphSha256}};
    }
    fields.context.textContent = ""; fields.reuse.checked = true; fields.reuse.disabled = true; fields.reuse.closest("label").hidden = true;
    fields.editor.querySelectorAll("input, textarea").forEach(function(input) { input.value = ""; });
    ["profile", "engine", "language", "voice", "chapter"].forEach(function(key) { fields[key].replaceChildren(); });
    dialog.showModal(); status(label("loading")); fields.editor.disabled = true; fields.save.disabled = fields.create.disabled = fields.preview.disabled = fields.chapter_render.disabled = true;
    var serial = generation;
    try {
      var data = await request("speech"); if (!valid(serial)) return;
      settings = data.settings || {schema_version: "lixity-audio-settings/1", selected: "", profiles: {}}; capabilities = data.capabilities;
      options(fields.engine, Object.entries(capabilities).map(function(pair) { return [pair[0], pair[1].name]; }));
      var matchedChapter = paragraph && data.chapters.find(function(chapter) {
        return paragraph.identity.start_line >= chapter.start_line && paragraph.identity.end_line <= chapter.end_line;
      });
      var readerChapter = document.getElementById("reader-chapter");
      var selectedChapter = matchedChapter ? String(matchedChapter.number) : fromReader && readerChapter ? readerChapter.value.replace("ch-", "") : "";
      if (!data.chapters.some(function(chapter) { return String(chapter.number) === selectedChapter; })) selectedChapter = "";
      options(fields.chapter, data.chapters.map(function(chapter) { return [String(chapter.number), chapter.number + ". " + chapter.title]; }), selectedChapter);
      if (paragraph && !data.chapters.some(function(chapter) { return Number(fields.chapter.value) === chapter.number && paragraph.identity.start_line >= chapter.start_line && paragraph.identity.end_line <= chapter.end_line; })) paragraph = null;
      profileOptions(); loadProfile(); status(data.configuration_error || ""); fields.save.disabled = !settings.selected;
      fields.context.textContent = label(paragraph ? "paragraph_preview" : "first_preview");
    } catch (error) { if (valid(serial)) status(error.message); }
  }
  button(settingsForm, "title", function() { open(false); }).id = "settings-speech";
  var toolbar = document.getElementById("manuscript-reader-controls");
  if (toolbar) button(toolbar, "title", function() { open(true); }).id = "reader-speech";
  document.addEventListener("lixity:workbench-change", function() { if (dialog && dialog.open) dialog.close(); });
  new MutationObserver(function() { if (dialog && dialog.open && context() !== openedContext) dialog.close(); }).observe(body, {
    subtree: true, attributes: true, attributeFilter: ["data-project-token", "data-manuscript-source-sha256", "data-manuscript-project-token"]});
})();
