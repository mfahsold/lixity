/* Project-local listening drafts share one token-bound native dialog. */
(function() {
  "use strict";
  var body = document.body, settingsForm = document.getElementById("settings-form");
  if (body.dataset.speechCapable !== "true" || body.dataset.readOnly === "true" || !settingsForm) return;
  var canRender = body.dataset.speechRenderCapable === "true";
  var dialog, fields = {}, settings, capabilities, workers, generation = 0, openSequence = 0, job = null, timer, openedContext, paragraph;
  var executionTarget = "local", migrationRequired = false, direction, savedDirectionView, lastPreset = "Ryan", mode = "reference", editingPronunciation = null;
  var savedSettings = null, profilesDirty = false, profileSaving = false, auditAudioUrl = null;
  var specialPronunciations = Object.create(null);
  var allReferences = [], calibrationTexts = null;
  var audioStream = null, audioCtx = null, audioSource = null, audioProcessor = null, recordedChunks = [], totalRecordedSamples = 0;
  var recTimerInterval = null, recStartTime = 0, isRecordingVoice = false, lastRecordedWavBlob = null, sampleVariant = "phonetic";

  function writeWavHeader(sampleRate, numChannels, numSamples) {
    var buffer = new ArrayBuffer(44), view = new DataView(buffer);
    function writeString(offset, string) {
      for (var i = 0; i < string.length; i++) view.setUint8(offset + i, string.charCodeAt(i));
    }
    writeString(0, "RIFF"); view.setUint32(4, 36 + numSamples * 2, true); writeString(8, "WAVE");
    writeString(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
    view.setUint16(22, numChannels, true); view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * numChannels * 2, true); view.setUint16(32, numChannels * 2, true);
    view.setUint16(34, 16, true); writeString(36, "data"); view.setUint32(40, numSamples * 2, true);
    return new Uint8Array(buffer);
  }
  function encodeWav(chunks, totalSamples, sampleRate) {
    var pcm = new Int16Array(totalSamples), offset = 0;
    for (var i = 0; i < chunks.length; i++) {
      var chunk = chunks[i];
      for (var j = 0; j < chunk.length; j++) {
        var s = Math.max(-1, Math.min(1, chunk[j]));
        pcm[offset++] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
    }
    var header = writeWavHeader(sampleRate, 1, totalSamples);
    var wav = new Uint8Array(header.length + pcm.buffer.byteLength);
    wav.set(header, 0); wav.set(new Uint8Array(pcm.buffer), header.length);
    return wav;
  }
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
  function arrangeSections() {
    fields.export_section.hidden = mode === "profiles";
    fields.render_section.hidden = mode !== "profiles" && !canRender;
    if (fields.microphone_section) fields.microphone_section.hidden = mode === "profiles";
    fields.render_heading.textContent = label(mode === "profiles" ? "service_title" : "render_title");
    var first = mode === "reader" ? fields.render_section : fields.export_section;
    var second = mode === "reader" ? fields.export_section : fields.render_section;
    fields.audit_section.before(first, second);
  }
  function downloadText(text, filename, type) {
    var address = URL.createObjectURL(new Blob([text], {type: type + ";charset=utf-8"}));
    var link = document.createElement("a"); link.href = address; link.download = filename;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(function() { URL.revokeObjectURL(address); }, 2000);
  }
  function populateMicrophone(mic) {
    if (!mic || !fields.microphone_device) return;
    fields.microphone_device.replaceChildren();
    if (mic.devices && mic.devices.length) {
      mic.devices.forEach(function(d) {
        var opt = new Option(d.label, d.alsa_id);
        if (d.alsa_id === mic.default_device) opt.selected = true;
        fields.microphone_device.add(opt);
      });
    }
    if (mic.current_gain != null) {
      fields.microphone_gain.value = fields.microphone_gain_range.value = String(mic.current_gain);
      if (mic.gain_info && mic.gain_info.db != null) {
        fields.microphone_gain_info.textContent = " (" + (mic.gain_info.db >= 0 ? "+" : "") + mic.gain_info.db.toFixed(1) + " dB)";
      }
    }
  }
  async function inspectAudio() {
    var file = fields.audit_audio.files[0];
    if (!file) { status(label("audit_choose_audio")); return; }
    if (file.size > 96 * 1024 * 1024) { status(label("audit_size_limit")); return; }
    if (fields.audit_transcript.files[0] && direction.dirty() && !fields.ignore_direction.checked) { status(label("direction_save_first")); return; }
    invalidate(); var serial = generation; fields.audit_run.disabled = true; fields.audit_result.replaceChildren();
    status(label("audit_running"));
    try {
      var encoded = await new Promise(function(resolve, reject) {
        var reader = new FileReader(); reader.onload = function() { resolve(String(reader.result).split(",")[1]); };
        reader.onerror = function() { reject(new Error(label("failed"))); }; reader.readAsDataURL(file);
      });
      var transcriptFile = fields.audit_transcript.files[0], transcript = null;
      if (transcriptFile) {
        if (transcriptFile.size > 8 * 1024 * 1024) throw new Error(label("audit_size_limit"));
        transcript = JSON.parse(await transcriptFile.text());
      }
      if (!valid(serial)) return;
      var scope = fields.export_scope.value === "manuscript" ? "manuscript" : "chapter";
      var result = await request("audio-audit", Object.assign(tokens(), {
        audio: encoded, filename: file.name, transcript: transcript, mode: scope,
        chapter: scope === "manuscript" ? null : Number(fields.chapter.value),
        ...(transcript ? {profile: readProfile()} : {}), ignore_direction: fields.ignore_direction.checked
      }));
      if (!valid(serial)) return;
      var audit = result.audit;
      node("p", fields.audit_result, "ctl-note", label(audit.alignment.status === "compared" ? "audit_compared" : "audit_unknown"));
      var table = node("table", fields.audit_result);
      [[label("audit_duration"), audit.audio.duration_seconds, "s"],
       [label("audit_peak"), audit.signal.peak_dbfs, "dBFS"],
       [label("audit_clipping"), audit.signal.clipped_samples, ""]].forEach(function(row) {
        var tr = node("tr", table); var th = node("th", tr, "", row[0]); th.scope = "row";
        node("td", tr, "", row[1] == null ? "–" : String(typeof row[1] === "number" ? Math.round(row[1] * 100) / 100 : row[1]) + " " + row[2]);
      });
      if (audit.alignment.status === "compared") {
        var details = node("details", fields.audit_result); node("summary", details, "", label("audit_details"));
        node("p", details, "", label("audit_word_match") + ": " + audit.alignment.matched_words + " / " + audit.alignment.expected_word_count);
        [["audit_missing", audit.alignment.missing_words], ["audit_extra", audit.alignment.extra_words]].forEach(function(group) {
          node("p", details, "", label(group[0]) + ": " + group[1].length);
          var list = node("ul", details);
          group[1].slice(0, 100).forEach(function(word) { node("li", list, "", word.text); });
        });
        node("p", details, "", label("audit_replacements") + ": " + audit.alignment.replacements.length);
        var changes = node("ul", details);
        audit.alignment.replacements.slice(0, 100).forEach(function(change) {
          node("li", changes, "", label("audit_expected") + ": " + change.expected_words.join(" ") + " · " + label("audit_observed") + ": " + change.transcript_words.join(" "));
        });
        node("p", details, "", label("audit_pauses") + ": " + audit.pauses.comparisons.length);
        var pauses = node("ul", details);
        audit.pauses.comparisons.slice(0, 100).forEach(function(pause) {
          node("li", pauses, "", label("audit_expected") + ": " + pause.planned_seconds.toFixed(2) + " s · " + label("audit_observed") + ": " + pause.observed_seconds.toFixed(2) + " s");
        });
        if ([audit.alignment.missing_words, audit.alignment.extra_words, audit.alignment.replacements, audit.pauses.comparisons].some(function(rows) { return rows.length > 100; })) node("p", details, "ctl-note", label("audit_more_results"));
      }
      auditAudioUrl = URL.createObjectURL(file); fields.audio.src = auditAudioUrl; fields.audio.hidden = false;
      if (fields.player_controls) fields.player_controls.hidden = false;
      button(fields.audit_result, "audit_download", function() { downloadText(JSON.stringify(audit, null, 2), "audio-audit.json", "application/json"); });
      status(label("audit_ready"));
    } catch (error) { if (valid(serial)) status(error.message); }
    finally { fields.audit_run.disabled = false; }
  }
  function clearAudio() {
    fields.audio.pause(); fields.audio.removeAttribute("src"); fields.audio.load(); fields.audio.hidden = true;
    if (fields.player_controls) fields.player_controls.hidden = true;
    if (auditAudioUrl) { URL.revokeObjectURL(auditAudioUrl); auditAudioUrl = null; }
    fields.download.hidden = true; fields.download.removeAttribute("href");
  }
  function invalidate() {
    ++generation; clearTimeout(timer); clearAudio(); status(""); fields.context.textContent = "";
    if (job) {
      var previous = job; job = null;
      request("speech-cancel", Object.assign({}, previous.tokens, {id: previous.id})).catch(function() {});
    }
    fields.cancel.disabled = true; fields.preview.disabled = fields.chapter_render.disabled = !canRender || !settings || !settings.selected || !fields.chapter.options.length || openedContext !== context();
    if (fields.direction_plan) fields.direction_plan.disabled = !settings || !settings.selected || !fields.chapter.options.length || openedContext !== context();
    fields.progress.hidden = true;
    if (fields.plan) { fields.plan.replaceChildren(); fields.plan.hidden = true; }
    if (fields.audit_result) fields.audit_result.replaceChildren();
  }
  function updateWorkerStatus() {
    if (!fields.worker_status || !fields.engine || !capabilities) return;
    fields.worker_guide.hidden = fields.engine.value === "openai-compatible";
    fields.worker_guide.href = fields.engine.value.startsWith("coqui") ? settingsForm.dataset.speechCoquiGuide : settingsForm.dataset.speechQwenGuide;
    if (fields.engine.value === "openai-compatible") { fields.worker_status.textContent = label("provider_status"); return; }
    var target = fields.target.value || "local", cap = capabilities[fields.engine.value];
    var worker = Array.isArray(workers) ? workers.find(function(item) { return item.target === target; }) : null;
    var args = {target: label("target_" + target)};
    var knownModel = worker && worker.model && Object.values(capabilities).find(function(item) { return item.model === worker.model; });
    var key = "unknown";
    if (worker && worker.state === "starting") key = "starting";
    else if (worker && worker.state === "unavailable") key = "unavailable";
    else if (worker && worker.state === "ready" && knownModel && cap) {
      args.model = knownModel.name;
      key = worker.model === cap.model ? "match" : "mismatch";
    }
    fields.worker_status.textContent = uiFormat("speech_worker_" + key, args);
  }
  function updateRuntimeHint() {
    var engine = fields.engine.value;
    var key = engine === "openai-compatible" ? "provider_hint" : fields.target.value === "jetson" ? "jetson_hint" :
      engine.startsWith("coqui") ? "coqui_runtime_hint" : "runtime_hint";
    fields.runtime_hint.textContent = label(key);
  }
  function updateModelFields() {
    var designed = fields.engine.value === "qwen3-design", referenced = !!capabilities[fields.engine.value].reference_required;
    var noInstructions = fields.engine.value === "openai-compatible" ? !fields.supports_instructions.checked : !capabilities[fields.engine.value].instructions;
    var descriptionPresent = Boolean(fields.voice_description.value.trim());
    var referencePresent = Boolean(fields.reference_id.value.trim());
    var instructionPresent = Boolean(fields.instructions.value.trim());
    fields.voice_description.closest("label").hidden = !designed && !descriptionPresent;
    fields.voice_description.disabled = !designed && !descriptionPresent;
    fields.voice_description.required = designed;
    fields.voice_description.setCustomValidity(!designed && descriptionPresent ? label("model_clear_description") : "");
    fields.reference_id.closest("label").hidden = !referenced && !referencePresent;
    fields.reference_id.disabled = !referenced && !referencePresent;
    fields.reference_id.required = referenced;
    fields.reference_id.setCustomValidity(!referenced && referencePresent ? label("model_clear_reference") : "");
    fields.instructions.closest("label").hidden = noInstructions && !instructionPresent;
    fields.instructions.disabled = noInstructions && !instructionPresent;
    fields.instructions.setCustomValidity(noInstructions && instructionPresent ? label(fields.engine.value.startsWith("coqui") ? "coqui_clear_instructions" : "model_clear_instructions") : "");
    fields.model_conflict.textContent = [fields.voice_description, fields.reference_id, fields.instructions]
      .filter(function(input) { return input.validity.customError; }).map(function(input) { return input.validationMessage; }).join(" ");
    fields.model_conflict.hidden = !fields.model_conflict.textContent;
  }
  function voiceControls() {
    var cap = capabilities[fields.engine.value];
    if (!cap) return;
    var designed = fields.engine.value === "qwen3-design";
    var external = fields.engine.value === "openai-compatible";
    var referenced = !!cap.reference_required;
    var language = fields.language.value, voice = fields.voice.value;
    options(fields.language, cap.languages.map(function(value) { return [value, languageName(value)]; }), language);
    var voices = Object.entries(cap.voices).filter(function(pair) { return pair[1].languages.includes(fields.language.value); });
    options(fields.voice, designed ? [["design", "VoiceDesign"]] : voices.map(function(pair) { return [pair[0], pair[1].name]; }), designed ? "design" : voice);
    fields.voice.closest("label").hidden = designed || referenced || external;
    fields.voice.disabled = designed || referenced || external;
    fields.language.closest("label").hidden = external;
    fields.language.disabled = external;
    ["base_url", "provider_model", "api_key_env", "provider_voice", "provider_language", "supports_instructions"].forEach(function(key) {
      fields[key].closest("label").hidden = !external; fields[key].disabled = !external;
    });
    updateModelFields();
    fields.reference_hint.hidden = !referenced || fields.engine.value === "coqui-reference";
    fields.voice_hint.hidden = designed || referenced || fields.engine.value === "coqui" || external;
    fields.design_hint.hidden = !designed;
    fields.speed.min = String(cap.speed.minimum);
    fields.speed.max = String(cap.speed.maximum);
    fields.model.textContent = external ? label("provider_hint") : fields.engine.value.startsWith("coqui") ? cap.name : label(designed ? "model_design_hint" : referenced ? "model_base_hint" : "model_preset_hint");
    direction.setEngine(fields.engine.value);
    options(fields.target, cap.targets.map(function(value) { return [value, label("target_" + value)]; }),
      cap.targets.includes(executionTarget) ? executionTarget : cap.targets[0]);
    fields.target.disabled = cap.targets.length < 2;
    fields.target.closest("label").hidden = fields.target.disabled;
    updateRuntimeHint();
    fields.reuse.closest("label").hidden = mode !== "output" || !canRender;
    updateWorkerStatus();
  }
  function loadProfile() {
    invalidate();
    if (!settings.selected) return;
    var profile = settings.profiles[settings.selected];
    lastPreset = profile.engine === "qwen3" ? profile.voice : "Ryan";
    ["name", "instructions", "speed", "paragraph_pause", "scene_pause"].forEach(function(key) { fields[key].value = profile[key]; });
    options(fields.engine, Object.keys(capabilities).map(function(key) {
      return [key, key === "openai-compatible" ? label("model_external") : key.startsWith("coqui") ? capabilities[key].name : label(key === "qwen3" ? "model_preset" : key === "qwen3-design" ? "model_design" : "model_base")];
    }), profile.engine);
    fields.base_url.value = profile.base_url || ""; fields.provider_model.value = profile.model || "";
    fields.api_key_env.value = profile.api_key_env || ""; fields.supports_instructions.checked = !!profile.supports_instructions;
    fields.provider_voice.value = profile.engine === "openai-compatible" ? profile.voice : "";
    fields.provider_language.value = profile.language;
    fields.voice_description.value = profile.voice_description || "";
    fields.reference_id.value = profile.reference_id || "";
    options(fields.language, [], profile.language); options(fields.voice, [], profile.voice); voiceControls();
    setPronunciations(profile.pronunciations);
    editingPronunciation = null; fields.pronunciation_term.value = fields.pronunciation_spoken.value = "";
    fields.pronunciation_search.value = ""; renderPronunciations();
    fields.editor.disabled = false; fields.save.disabled = false;
  }
  function pronunciationEntries() {
    var replacements = Object.create(null);
    fields.pronunciations.value.split("\n").forEach(function(line) {
      if (!line.trim()) return;
      var split = line.indexOf("="), term = line.slice(0, split).trim(), value = line.slice(split + 1).trim();
      if (split < 1 || !term || !value || Object.hasOwn(replacements, term)) throw new Error(label("pronunciation_error"));
      replacements[term] = value;
    });
    Object.entries(specialPronunciations).forEach(function(pair) {
      if (Object.hasOwn(replacements, pair[0])) throw new Error(label("pronunciation_error"));
      replacements[pair[0]] = pair[1];
    });
    return replacements;
  }
  function setPronunciations(entries) {
    specialPronunciations = Object.create(null);
    var lines = [];
    Object.entries(entries).forEach(function(pair) {
      if (pair[0].includes("=")) specialPronunciations[pair[0]] = pair[1];
      else lines.push(pair.join("="));
    });
    fields.pronunciations.value = lines.join("\n");
  }
  function readProfile() {
    if (!settings || !settings.selected) throw new Error(label("profile_required"));
    if (pronunciationPending()) throw new Error(label("pronunciation_pending"));
    var conflict = [fields.voice_description, fields.reference_id, fields.instructions].find(function(input) { return input.validity.customError; });
    if (conflict) throw new Error(conflict.validationMessage);
    if (capabilities[fields.engine.value].reference_required && !fields.reference_id.checkValidity()) throw new Error(label("model_need_reference"));
    if (fields.engine.value === "qwen3-design" && !fields.voice_description.value.trim()) throw new Error(label("model_need_description"));
    var replacements = pronunciationEntries();
    var profile = {name: fields.name.value.trim(), engine: fields.engine.value, language: fields.language.value,
      voice: fields.voice.value,
      speed: Number(fields.speed.value), instructions: fields.instructions.value.trim(),
      paragraph_pause: Number(fields.paragraph_pause.value), scene_pause: Number(fields.scene_pause.value), pronunciations: replacements};
    if (profile.engine === "qwen3-design") profile.voice_description = fields.voice_description.value.trim();
    if (capabilities[profile.engine].reference_required) profile.reference_id = fields.reference_id.value.trim();
    if (profile.engine === "openai-compatible") {
      profile.base_url = fields.base_url.value.trim(); profile.model = fields.provider_model.value.trim();
      profile.api_key_env = fields.api_key_env.value.trim() || null;
      profile.supports_instructions = fields.supports_instructions.checked;
      profile.voice = fields.provider_voice.value.trim(); profile.language = fields.provider_language.value.trim();
    }
    return profile;
  }
  function pronunciationPending() {
    return Boolean(fields.pronunciation_term.value.trim() || fields.pronunciation_spoken.value.trim());
  }
  function renderPronunciations() {
    var replacements;
    fields.pronunciation_list.replaceChildren();
    try { replacements = pronunciationEntries(); }
    catch (_) { return; }
    var query = fields.pronunciation_search.value.trim().toLocaleLowerCase();
    var matches = 0;
    Object.entries(replacements).forEach(function(pair) {
      if (query && !pair.join(" ").toLocaleLowerCase().includes(query)) return;
      matches++;
      var row = node("li", fields.pronunciation_list, "row"); row.dataset.pronunciationRow = "true";
      node("span", row, "", pair[0] + " → " + pair[1]);
      var edit = button(row, "pronunciation_edit", function() {
        if (pronunciationPending()) { status(label("pronunciation_pending")); return; }
        editingPronunciation = pair[0]; fields.pronunciation_term.value = pair[0];
        fields.pronunciation_spoken.value = pair[1]; fields.pronunciation_spoken.focus();
      });
      edit.setAttribute("aria-label", label("pronunciation_edit") + ": " + pair[0]);
      var remove = button(row, "pronunciation_remove", function() {
        if (pronunciationPending()) { status(label("pronunciation_pending")); return; }
        try {
          var current = pronunciationEntries(); delete current[pair[0]];
          setPronunciations(current);
          if (editingPronunciation === pair[0]) { editingPronunciation = null; fields.pronunciation_term.value = fields.pronunciation_spoken.value = ""; }
          profilesDirty = true; invalidate(); renderPronunciations(); status(label("profiles_unsaved"));
        } catch (error) { status(error.message); }
      });
      remove.setAttribute("aria-label", label("pronunciation_remove") + ": " + pair[0]);
    });
    fields.pronunciation_empty.hidden = !query || matches > 0;
  }
  function applyPronunciation() {
    try {
      var entries = pronunciationEntries(), term = fields.pronunciation_term.value.trim(), spoken = fields.pronunciation_spoken.value.trim();
      if (!term || !spoken || /[\r\n]/.test(term) || /[\r\n]/.test(spoken) ||
          (Object.hasOwn(entries, term) && term !== editingPronunciation)) throw new Error(label("pronunciation_error"));
      if (editingPronunciation !== null && editingPronunciation !== term) delete entries[editingPronunciation];
      entries[term] = spoken;
      setPronunciations(entries);
      editingPronunciation = null; fields.pronunciation_term.value = fields.pronunciation_spoken.value = "";
      profilesDirty = true; invalidate(); renderPronunciations(); status(label("profiles_unsaved"));
    } catch (error) { status(error.message); }
  }
  function stash() { if (settings && settings.selected) settings.profiles[settings.selected] = readProfile(); }
  function profileOptions() {
    options(fields.profile, Object.entries(settings.profiles).map(function(pair) { return [pair[0], pair[1].name]; }), settings.selected);
    fields.create.disabled = migrationRequired || Object.keys(settings.profiles).length >= 32;
    fields.remove_profile.disabled = migrationRequired || Object.keys(settings.profiles).length <= 1;
  }
  function removeProfile() {
    if (migrationRequired || !settings || Object.keys(settings.profiles).length <= 1) return;
    if (pronunciationPending()) { status(label("pronunciation_pending")); return; }
    var id = settings.selected;
    if (savedDirectionView && savedDirectionView.directions.some(function(item) { return item.profile_id === id; })) {
      status(label("profile_referenced")); return;
    }
    delete settings.profiles[id];
    profilesDirty = true;
    settings.selected = Object.keys(settings.profiles)[0];
    profileOptions(); loadProfile(); status(label("profile_removed_draft"));
  }
  function create() {
    if (migrationRequired) return;
    try { stash(); } catch (error) { status(error.message); return; }
    var id = "narrator", index = 1;
    while (Object.hasOwn(settings.profiles, id)) id = "narrator_" + (++index);
    // Preserve languages that require an explicitly configured external provider.
    var projectLanguage = document.getElementById("set-language");
    var language = fields.language.value || (projectLanguage && projectLanguage.value) || document.documentElement.lang;
    var external = !capabilities.qwen3.languages.includes(language);
    if (external && settings.schema_version !== "lixity-audio-settings/4") { status(label("provider_schema_required")); return; }
    settings.profiles[id] = {name: label("new_profile"), engine: external ? "openai-compatible" : "qwen3", language: language, voice: external ? "" : "Ryan", speed: capabilities.qwen3.speed.default,
      instructions: "", paragraph_pause: 0.45, scene_pause: 1.2, pronunciations: {}};
    profilesDirty = true;
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
      if (result.state === "pending" && !active.cancelling && result.queue_position) status(uiFormat("runtime_queued", {position: result.queue_position}));
      if (result.state === "ready" && active.cancelling) {
        status(label("cancelling")); timer = setTimeout(function() { poll(serial, active); }, 500); return;
      }
      if (result.state === "ready") {
        fields.audio.src = url("speech-audio", {id: active.id}); fields.audio.hidden = false;
        if (fields.player_controls) fields.player_controls.hidden = false;
        fields.context.textContent += result.context && result.context.excerpt ? " · " + result.context.excerpt : "";
        if (result.context && result.context.truncated) fields.context.textContent += " · " + label("truncated");
        fields.download.href = fields.audio.src; fields.download.hidden = false; finish();
      } else if (["error", "stale", "cancelled"].includes(result.state)) finish();
      else timer = setTimeout(function() { poll(serial, active); }, 500);
    } catch (error) { if (valid(serial)) { status(error.message); finish(); } }
  }
  function finish() { job = null; fields.cancel.disabled = true; fields.preview.disabled = fields.chapter_render.disabled = !canRender || !settings || !settings.selected || !fields.chapter.options.length || openedContext !== context(); }
  async function render(mode, planOnly) {
    if (migrationRequired || (!planOnly && !canRender)) return;
    if (openedContext !== context()) { status(label("direction_context_changed")); return; }
    try {
      if (!Array.from(fields.editor.querySelectorAll("input, select, textarea")).every(function(input) { return input.reportValidity(); })) return;
      var profile = readProfile(); invalidate(); var serial = generation;
      fields.preview.disabled = fields.chapter_render.disabled = true;
      status(label("state_pending"));
      var payload = Object.assign(tokens(), {mode: mode, chapter: mode === "manuscript" ? null : Number(fields.chapter.value), profile: profile,
        target: fields.target.value || "local", ignore_direction: fields.ignore_direction.checked});
      if (mode === "preview" && paragraph) payload.paragraph = paragraph.identity;
      if (mode !== "preview") {
        if (direction.dirty() && !fields.ignore_direction.checked) throw new Error(label("direction_save_first"));
        payload.fresh_audio = !fields.reuse.checked;
      } else if (!fields.ignore_direction.checked) {
        var draft = direction.draft(); if (draft) { payload.draft_direction = draft; var replacement=direction.replacement(); if (replacement) payload.draft_replace_id=replacement; }
      }
      fields.context.textContent = (planOnly ? label("direction_plan") : profile.engine === "openai-compatible" ? label("provider_model") : label("target_" + payload.target)) + " · " + (mode === "manuscript" ? label("scope_manuscript") : fields.chapter.selectedOptions[0].textContent) +
        (mode === "preview" ? " · " + label(paragraph ? "paragraph_preview" : "first_preview") : "") +
        (mode === "preview" && paragraph ? " · " + paragraph.identity.start_line + "–" + paragraph.identity.end_line : "");
      var data = await request(planOnly ? "speech-plan" : "speech-render", payload);
      if (planOnly) {
        if (!valid(serial)) return;
        fields.plan.replaceChildren();
        var ssmlHeader = node("div", fields.plan, "row");
        if (data.timeline) button(ssmlHeader, "export_json", function() { downloadText(JSON.stringify(data.timeline, null, 2), "speech-timeline.json", "application/json"); });
        if (data.ssml) {
          var ssmlBtn = button(ssmlHeader, "export_ssml", function() {
            var blob = new Blob([data.ssml], {type: "application/ssml+xml;charset=utf-8"});
            var u = URL.createObjectURL(blob);
            var a = document.createElement("a");
            a.href = u; a.download = "speech-timeline.ssml";
            document.body.appendChild(a); a.click(); document.body.removeChild(a);
            setTimeout(function() { URL.revokeObjectURL(u); }, 2000);
          });
          ssmlBtn.type = "button";
        }
        if (data.export_warnings && data.export_warnings.length) {
          node("p", fields.plan, "ctl-note", label("export_limitations"));
          var limitations = node("ul", fields.plan, "ctl-note");
          var warningCounts = new Map();
          data.export_warnings.forEach(function(warning) {
            var translated = warning.code && label("export_" + warning.code);
            var message = translated && !translated.startsWith("speech_") ? translated : warning.message || String(warning);
            warningCounts.set(message, (warningCounts.get(message) || 0) + 1);
          });
          warningCounts.forEach(function(count, message) {
            node("li", limitations, "", message + (count > 1 ? " × " + count : ""));
          });
        }
        var segments = node("ol", fields.plan);
        (data.timeline || data.plan).segments.forEach(function(row) {
          var item = node("li",segments,"",row.text || label("direction_pause"));
          var instructions = row.instructions || row.profile.instructions;
          node("p",item,"ctl-note",(row.profile.voice_description || row.profile.reference_id || row.profile.voice) + (instructions ? " · " + instructions : "") + " · " + label("export_pause_before") + ": " + row.pause_before + " s · " + label("export_pause_after") + ": " + row.pause_after + " s");
        });
        fields.plan.hidden = false; status(label("export_ready")); finish(); return;
      }
      if (!valid(serial)) { request("speech-cancel", Object.assign({}, {project_token: payload.project_token, source_sha256: payload.source_sha256}, {id: data.job.id})).catch(function() {}); return; }
      job = {id: data.job.id, tokens: tokens(), timeline: data.timeline || data.plan}; fields.cancel.disabled = false; fields.progress.hidden = false; poll(serial, job);
    } catch (error) { if (serial == null || valid(serial)) { status(error.message); finish(); } }
  }
  async function cancel() {
    if (!job) return;
    var active = job; active.cancelling = true; fields.cancel.disabled = true; status(label("cancelling"));
    try { await request("speech-cancel", Object.assign({}, active.tokens, {id: active.id})); }
    catch (error) { if (job === active) { status(error.message); fields.cancel.disabled = false; active.cancelling = false; } }
  }
  async function save() {
    if (migrationRequired || profileSaving) return;
    if (openedContext !== context()) { status(label("pronunciation_context_changed")); return; }
    try {
      if (!Array.from(fields.editor.querySelectorAll("input, select, textarea")).every(function(input) { return input.reportValidity(); })) return;
      stash();
      if (!["lixity-audio-settings/3", "lixity-audio-settings/4"].includes(settings.schema_version) && Object.values(settings.profiles).some(function(profile) { return profile.engine.startsWith("coqui"); })) {
        status(label("coqui_schema_required")); return;
      }
      if (settings.schema_version !== "lixity-audio-settings/4" && Object.values(settings.profiles).some(function(profile) { return profile.engine === "openai-compatible"; })) {
        status(label("provider_schema_required")); return;
      }
      invalidate(); var serial = generation; profileSaving = true;
      fields.editor.disabled = fields.profile.disabled = fields.create.disabled = fields.remove_profile.disabled = fields.profile_discard.disabled = fields.save.disabled = true;
      status(label("saving"));
      await request("settings", {project_token: tokens().project_token, audio: settings});
      if (valid(serial)) location.reload();
    } catch (error) {
      if (serial == null || valid(serial)) status(error.message.includes("A removed voice profile is used by saved speech direction") ? label("profile_referenced") : error.message);
    }
    finally {
      if (profileSaving) {
        profileSaving = false;
        if (dialog.open) {
          fields.editor.disabled = false; fields.profile_discard.disabled = false;
          if (openedContext === context()) { fields.profile.disabled = false; profileOptions(); fields.save.disabled = migrationRequired || !settings.selected; }
        }
      } else if (serial == null || valid(serial)) fields.save.disabled = false;
    }
  }
  function updateVoiceCard() {
    if (!fields.profile_voice_card) return;
    var cap = capabilities && capabilities[fields.engine.value];
    var referenced = cap && cap.reference_required;
    fields.profile_voice_card.hidden = !referenced;
    if (!referenced) return;
    fields.profile_voice_card.replaceChildren();
    var curId = fields.reference_id ? fields.reference_id.value.trim() : "";
    var match = curId && allReferences.find(function(r) { return r.id === curId; });
    var infoSpan = node("span", fields.profile_voice_card, "voice-card-info");
    if (curId) {
      var snippet = match ? (match.transcript ? match.transcript.slice(0, 45) + "…" : match.id.slice(0, 8)) : curId.slice(0, 8) + "…";
      var dur = match ? " (" + match.duration_seconds + "s)" : "";
      infoSpan.innerHTML = "🎙 <strong>" + (label("active_voice") || "Aktive Autorenstimme") + ":</strong> " + snippet + dur;
      var playBtn = node("button", fields.profile_voice_card, "ctl", "▶ " + (label("preview") || "Vorhören"));
      playBtn.type = "button";
      playBtn.addEventListener("click", function() {
        fields.audio.src = url("speech-audio", {reference_id: curId});
        fields.audio.hidden = false;
        fields.audio.play();
      });
      var changeBtn = node("button", fields.profile_voice_card, "ctl", "🎙 " + (label("record_author_title") || "Stimme ändern"));
      changeBtn.type = "button";
      changeBtn.addEventListener("click", function() { switchMode("reference"); });
    } else {
      infoSpan.innerHTML = "⚠️ <em>" + (label("no_voice_yet") || "Noch keine Autorenstimme hinterlegt") + "</em>";
      var recNowBtn = node("button", fields.profile_voice_card, "ctl primary", "🎙 " + (label("record_author_title") || "Jetzt Stimme einsprechen"));
      recNowBtn.type = "button";
      recNowBtn.addEventListener("click", function() { switchMode("reference"); });
    }
  }
  function renderActiveVoiceBadge() {
    if (!fields.active_voice_badge) return;
    fields.active_voice_badge.replaceChildren();
    var curProf = settings && settings.selected && settings.profiles[settings.selected];
    var activeId = curProf && curProf.reference_id;
    var match = activeId && allReferences.find(function(r) { return r.id === activeId; });
    var span = node("span", fields.active_voice_badge, "voice-badge-text");
    if (activeId) {
      var snip = match ? (match.transcript ? match.transcript.slice(0, 50) + "…" : match.id.slice(0, 8)) : activeId.slice(0, 8) + "…";
      var dur = match ? " (" + match.duration_seconds + "s)" : "";
      span.innerHTML = "✓ <strong>" + (label("active_voice") || "Aktive Autorenstimme") + ":</strong> " + snip + dur;
      var prevBtn = node("button", fields.active_voice_badge, "ctl", "▶ " + (label("preview") || "Vorhören"));
      prevBtn.type = "button";
      prevBtn.addEventListener("click", function() {
        fields.audio.src = url("speech-audio", {reference_id: activeId});
        fields.audio.hidden = false;
        fields.audio.play();
      });
    } else {
      span.innerHTML = "⚪ <em>" + (label("no_voice_yet") || "Noch keine Autorenstimme für dieses Projekt hinterlegt.") + "</em>";
    }
  }
  function renderReferenceList(refs) {
    if (!fields.reference_list) return;
    fields.reference_list.replaceChildren();
    if (!refs || !refs.length) {
      node("p", fields.reference_list, "ctl-note", "Bisher keine gespeicherten Aufnahmen in diesem Projekt.");
      return;
    }
    refs.forEach(function(ref) {
      var item = node("div", fields.reference_list, "voice-ref-item");
      var info = node("div", item, "voice-ref-info");
      node("div", info, "voice-ref-text", ref.transcript || ref.id);
      node("div", info, "voice-ref-meta", "Dauer: " + (ref.duration_seconds || "?") + "s · ID: " + ref.id.slice(0, 12) + "…");
      var actions = node("div", item, "row");
      var play = node("button", actions, "ctl", "▶");
      play.type = "button"; play.title = "Anhören";
      play.addEventListener("click", function() {
        fields.audio.src = url("speech-audio", {reference_id: ref.id});
        fields.audio.hidden = false;
        fields.audio.play();
      });
      var curProf = settings && settings.selected && settings.profiles[settings.selected];
      var isCurrent = curProf && curProf.reference_id === ref.id;
      if (isCurrent) {
        node("span", actions, "badge", "✓ Aktiv");
      } else {
        var useBtn = node("button", actions, "ctl", label("use_as_active") || "Aktivieren");
        useBtn.type = "button";
        useBtn.addEventListener("click", async function() {
          if (curProf) {
            curProf.reference_id = ref.id;
            if (fields.reference_id) fields.reference_id.value = ref.id;
            if (curProf.engine in {qwen3: 1, "custom-voice": 1}) {
              curProf.engine = "qwen3-base"; curProf.voice = "reference";
            }
            profilesDirty = true;
            status("Stimme zugewiesen. Speichere Profil...");
            await fields.save.click();
            renderActiveVoiceBadge();
            renderReferenceList(allReferences);
            updateVoiceCard();
          }
        });
      }
    });
  }
  async function startVoiceRecording() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      status("Mikrofonzugriff im Browser nicht verfügbar."); return;
    }
    try {
      audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false}
      });
      var AudioCtxClass = window.AudioContext || window.webkitAudioContext;
      audioCtx = new AudioCtxClass();
      audioSource = audioCtx.createMediaStreamSource(audioStream);
      audioProcessor = audioCtx.createScriptProcessor(4096, 1, 1);
      recordedChunks = []; totalRecordedSamples = 0; isRecordingVoice = true;
      audioProcessor.onaudioprocess = function(e) {
        if (!isRecordingVoice) return;
        var data = e.inputBuffer.getChannelData(0);
        var copy = new Float32Array(data.length);
        copy.set(data);
        recordedChunks.push(copy);
        totalRecordedSamples += copy.length;
      };
      audioSource.connect(audioProcessor);
      audioProcessor.connect(audioCtx.destination);
      if (fields.recBtn) {
        fields.recBtn.textContent = "⏹ " + (label("record_stop") || "Aufnahme beenden");
        fields.recBtn.classList.add("is-recording");
      }
      if (fields.recTimer) fields.recTimer.hidden = false;
      recStartTime = Date.now();
      recTimerInterval = setInterval(function() {
        var elapsed = Math.floor((Date.now() - recStartTime) / 1000);
        var m = String(Math.floor(elapsed / 60)).padStart(2, "0");
        var s = String(elapsed % 60).padStart(2, "0");
        if (fields.recTimer) fields.recTimer.textContent = m + ":" + s + (elapsed >= 15 && elapsed <= 25 ? " ✓ (Gute Länge)" : elapsed > 25 ? " (Fast zu lang)" : "");
      }, 500);
      if (fields.takeCard) fields.takeCard.hidden = true;
      status("Aufnahme läuft... Bitte Text laut und deutlich sprechen.");
    } catch (err) { status("Mikrofonfehler: " + err.message); }
  }
  function stopVoiceRecording() {
    isRecordingVoice = false;
    if (recTimerInterval) clearInterval(recTimerInterval);
    if (fields.recBtn) {
      fields.recBtn.textContent = "🎙 " + (label("record_start") || "Aufnahme starten");
      fields.recBtn.classList.remove("is-recording");
    }
    if (audioProcessor) { audioProcessor.disconnect(); audioProcessor = null; }
    if (audioSource) { audioSource.disconnect(); audioSource = null; }
    if (audioStream) { audioStream.getTracks().forEach(function(t) { t.stop(); }); audioStream = null; }
    var sampleRate = audioCtx ? audioCtx.sampleRate : 44100;
    if (audioCtx) { audioCtx.close(); audioCtx = null; }
    if (!recordedChunks.length || totalRecordedSamples < 1000) {
      status("Keine Audiodaten aufgenommen."); return;
    }
    var wavBytes = encodeWav(recordedChunks, totalRecordedSamples, sampleRate);
    lastRecordedWavBlob = new Blob([wavBytes], {type: "audio/wav"});
    if (fields.takePlayer) fields.takePlayer.src = URL.createObjectURL(lastRecordedWavBlob);
    var duration = (totalRecordedSamples / sampleRate).toFixed(1);
    if (fields.takeStats) fields.takeStats.textContent = "Dauer: " + duration + "s (" + sampleRate + " Hz, 16-Bit Mono PCM)";
    if (fields.takeCard) fields.takeCard.hidden = false;
    status("Aufnahme abgeschlossen (" + duration + "s). Jetzt anhören oder speichern.");
  }
  async function saveVoiceTake() {
    if (!lastRecordedWavBlob) return;
    if (fields.saveVoiceBtn) fields.saveVoiceBtn.disabled = true;
    status(label("saving"));
    try {
      var reader = new FileReader();
      var b64Wav = await new Promise(function(resolve, reject) {
        reader.onload = function() { resolve(String(reader.result).split(",")[1]); };
        reader.onerror = reject;
        reader.readAsDataURL(lastRecordedWavBlob);
      });
      var spoken = sampleVariant === "custom" ? (fields.customTextarea ? fields.customTextarea.value.trim() : "") : (fields.promptText ? fields.promptText.textContent.trim() : "");
      var res = await request("audio-microphone", {
        action: "save_reference",
        audio: b64Wav,
        transcript: spoken,
        profile_id: (settings && settings.selected) || "default"
      });
      if (res && res.reference) {
        status(label("record_saved_success") || "Autorenstimme erfolgreich gespeichert und aktiviert.");
        if (settings && settings.selected && settings.profiles[settings.selected]) {
          settings.profiles[settings.selected].reference_id = res.reference.id;
          if (fields.reference_id) fields.reference_id.value = res.reference.id;
        }
        if (res.references) {
          allReferences = res.references;
          renderReferenceList(res.references);
        }
        renderActiveVoiceBadge();
        updateVoiceCard();
      }
    } catch (err) { status(err.message); }
    finally { if (fields.saveVoiceBtn) fields.saveVoiceBtn.disabled = false; }
  }
  function switchMode(newMode) {
    if (profileSaving || (direction && direction.busy())) return;
    if (mode === "profiles" && (pronunciationPending() || profilesDirty)) {
      status(label(pronunciationPending() ? "pronunciation_pending" : "profiles_unsaved"));
      return;
    }
    mode = newMode;
    if (fields.tabs) {
      Object.keys(fields.tabs).forEach(function(k) {
        if (fields.tabs[k]) {
          var active = k === mode || (mode === "output" && k === "reader");
          fields.tabs[k].classList.toggle("active", active);
          fields.tabs[k].setAttribute("aria-selected", String(active));
        }
      });
    }
    fields.heading.textContent = label(mode === "reference" ? "record_author_title" : mode === "profiles" ? "profiles_title" : mode === "output" ? "output_title" : mode === "microphone" ? "microphone_title" : "reader_title");
    if (fields.reference_section) fields.reference_section.hidden = mode !== "reference";
    if (fields.profile_row) fields.profile_row.hidden = mode !== "profiles";
    fields.editor.hidden = mode !== "profiles";
    fields.create.hidden = mode !== "profiles";
    fields.remove_profile.hidden = mode !== "profiles";
    fields.save.hidden = mode !== "profiles";
    fields.profile_discard.hidden = mode !== "profiles";
    if (direction && direction.section) direction.section.hidden = mode !== "reader";
    fields.chapter.closest("label").hidden = mode !== "reader" && mode !== "output";
    fields.target.closest("label").hidden = true;
    fields.runtime_hint.hidden = mode === "profiles" || mode === "reference";
    fields.ignoreLabel.hidden = mode !== "reader" && mode !== "output";
    fields.preview.hidden = (mode !== "reader" && mode !== "output") || !canRender;
    fields.direction_plan.hidden = mode !== "reader" && mode !== "output";
    fields.export_scope.closest("label").hidden = mode !== "reader" && mode !== "output";
    fields.audit_section.hidden = mode !== "reader" && mode !== "output";
    fields.chapter_render.hidden = mode !== "output" || !canRender;
    fields.open_output.hidden = mode !== "reader";
    fields.cancel.hidden = (mode !== "reader" && mode !== "output") || !canRender;
    fields.reuseLabel.hidden = mode !== "output" || !canRender;
    fields.context.hidden = mode === "profiles" || mode === "reference";
    if (fields.microphone_section) {
      fields.microphone_section.hidden = mode !== "microphone" && mode !== "reference";
      if (mode === "microphone") fields.microphone_section.open = true;
    }
    arrangeSections();
    if (mode === "reference") renderActiveVoiceBadge();
    status("");
  }
  function build() {
    dialog = node("dialog", body, "lixity-modal"); dialog.id = "modal-speech"; dialog.setAttribute("aria-labelledby", "speech-title");
    var card = node("div", dialog, "modal-card"), header = node("div", card, "modal-header");
    fields.heading = node("h3", header, "", label("title")); fields.heading.id = "speech-title";
    var close = button(header, "close", function() {
      if (profileSaving) { status(label("saving")); return; }
      if (direction.busy()) { status(label("saving")); return; }
      if (direction.dirty()) { status(label("direction_switch_first")); return; }
      if (mode === "profiles" && pronunciationPending()) { status(label("pronunciation_pending")); return; }
      if (mode === "profiles" && profilesDirty) { status(label("profiles_unsaved")); return; }
      dialog.close();
    }); close.className = "ctl"; close.setAttribute("aria-keyshortcuts", "Escape"); close.setAttribute("title", label("close"));
    var tabsBar = node("div", card, "modal-tabs");
    tabsBar.setAttribute("role", "tablist");
    var tabVoice = node("button", tabsBar, "modal-tab-btn", "🎙 " + (label("tab_voice") || "Autorenstimme"));
    var tabProfiles = node("button", tabsBar, "modal-tab-btn", "🎭 " + (label("tab_profiles") || "Stimmprofile"));
    var tabReader = node("button", tabsBar, "modal-tab-btn", "🎧 " + (label("tab_reader") || "Hörprobe & Regie"));
    var tabMic = node("button", tabsBar, "modal-tab-btn", "🎚️ " + (label("tab_microphone") || "Mikrofon & Pegel"));
    tabVoice.type = tabProfiles.type = tabReader.type = tabMic.type = "button";
    tabVoice.addEventListener("click", function() { switchMode("reference"); });
    tabProfiles.addEventListener("click", function() { switchMode("profiles"); });
    tabReader.addEventListener("click", function() { switchMode("reader"); });
    tabMic.addEventListener("click", function() { switchMode("microphone"); });
    fields.tabs = {reference: tabVoice, profiles: tabProfiles, reader: tabReader, microphone: tabMic};
    fields.status = node("p", card, "ctl-status modal-intro"); fields.status.setAttribute("role", "status"); fields.status.setAttribute("aria-live", "polite");
    var content = node("div", card, "modal-body");

    fields.reference_section = node("div", content, "author-voice-studio");
    fields.reference_section.hidden = true;
    var introCard = node("div", fields.reference_section, "voice-studio-intro");
    node("h4", introCard, "voice-studio-title", "🎙 " + (label("record_author_title") || "Autorenstimme einsprechen"));
    node("p", introCard, "ctl-note", label("record_author_intro") || "Nimm eine 15–25-sekündige Sprachprobe auf. Sie dient als Stimmreferenz für den KI-Sprecher dieses Buchs.");
    fields.active_voice_badge = node("div", fields.reference_section, "voice-active-card");
    var textCard = node("div", fields.reference_section, "voice-reading-card");
    var textHeader = node("div", textCard, "voice-reading-header");
    node("span", textHeader, "voice-reading-label", label("sample_full") || "Text zum Vorlesen");
    var sampleSwitcher = node("div", textHeader, "segmented-buttons");
    var btnFull = node("button", sampleSwitcher, "seg-btn active", "Fabel");
    var btnShort = node("button", sampleSwitcher, "seg-btn", "Kurz");
    var btnCustom = node("button", sampleSwitcher, "seg-btn", "Eigener");
    btnFull.type = btnShort.type = btnCustom.type = "button";
    var promptBox = node("div", textCard, "voice-prompt-box");
    fields.promptText = node("p", promptBox, "voice-prompt-text");
    fields.customTextarea = node("textarea", promptBox, "ctl voice-custom-text");
    fields.customTextarea.rows = 4;
    fields.customTextarea.hidden = true;
    function updatePromptText() {
      var langTexts = calibrationTexts || {
        phonetic: "Einst stritten sich Nordwind und Sonne, wer von ihnen beiden wohl der Stärkere wäre, als ein Wanderer, der in einen warmen Mantel gehüllt war, des Weges daherkam. Sie wurden einig, dass derjenige für den Stärkeren gelten sollte, der den Wanderer zwingen würde, seinen Mantel abzulegen. Der Nordwind blies mit aller Macht, aber je mehr er blies, desto fester hüllte sich der Wanderer in seinen Mantel ein. Endlich gab der Nordwind den Kampf auf.",
        short: "Zwölf Boxkämpfer jagen Viktor quer über den großen Sylter Deich. Ein kluger Richter prüft jede Aussage gewissenhaft und ruhig."
      };
      if (sampleVariant === "phonetic") {
        fields.promptText.textContent = langTexts.phonetic;
        fields.promptText.hidden = false;
        fields.customTextarea.hidden = true;
      } else if (sampleVariant === "short") {
        fields.promptText.textContent = langTexts.short;
        fields.promptText.hidden = false;
        fields.customTextarea.hidden = true;
      } else {
        fields.promptText.hidden = true;
        fields.customTextarea.hidden = false;
        if (!fields.customTextarea.value) fields.customTextarea.value = langTexts.short;
      }
    }
    btnFull.addEventListener("click", function() {
      sampleVariant = "phonetic"; btnFull.classList.add("active"); btnShort.classList.remove("active"); btnCustom.classList.remove("active"); updatePromptText();
    });
    btnShort.addEventListener("click", function() {
      sampleVariant = "short"; btnShort.classList.add("active"); btnFull.classList.remove("active"); btnCustom.classList.remove("active"); updatePromptText();
    });
    btnCustom.addEventListener("click", function() {
      sampleVariant = "custom"; btnCustom.classList.add("active"); btnFull.classList.remove("active"); btnShort.classList.remove("active"); updatePromptText();
    });
    updatePromptText();
    var recControls = node("div", fields.reference_section, "voice-record-controls");
    fields.recBtn = node("button", recControls, "ctl voice-rec-btn", "🎙 " + (label("record_start") || "Aufnahme starten"));
    fields.recBtn.type = "button";
    fields.recTimer = node("span", recControls, "voice-rec-timer", "00:00");
    fields.recTimer.hidden = true;
    fields.takeCard = node("div", fields.reference_section, "voice-take-card");
    fields.takeCard.hidden = true;
    fields.takePlayer = node("audio", fields.takeCard, "media-player");
    fields.takePlayer.controls = true;
    fields.takeStats = node("div", fields.takeCard, "voice-take-stats");
    fields.saveVoiceBtn = node("button", fields.takeCard, "ctl primary voice-save-btn", "💾 " + (label("record_save") || "Als Autorenstimme für dieses Buch speichern"));
    fields.saveVoiceBtn.type = "button";
    fields.recBtn.addEventListener("click", function() {
      if (!isRecordingVoice) startVoiceRecording();
      else stopVoiceRecording();
    });
    fields.saveVoiceBtn.addEventListener("click", saveVoiceTake);
    var librarySec = node("details", fields.reference_section, "settings-section voice-library-section");
    node("summary", librarySec, "", label("choose_from_library") || "Gespeicherte Aufnahmen in diesem Projekt");
    fields.reference_list = node("div", librarySec, "voice-reference-list");
    var uploadSec = node("details", fields.reference_section, "settings-section voice-upload-section");
    node("summary", uploadSec, "", label("upload_wav") || "Oder Studio-WAV hochladen");
    var uploadFile = field(uploadSec, "upload_voice_file", "file");
    uploadFile.accept = ".wav";
    var uploadTranscript = field(uploadSec, "upload_voice_transcript", "textarea");
    uploadTranscript.placeholder = "Gesprochener Text der WAV-Datei...";
    var uploadBtn = node("button", uploadSec, "ctl", "WAV als Autorenstimme importieren");
    uploadBtn.type = "button";
    uploadBtn.addEventListener("click", async function() {
      var file = uploadFile.files && uploadFile.files[0];
      var text = uploadTranscript.value.trim();
      if (!file || !text) { status("Bitte WAV-Datei und Text angeben."); return; }
      uploadBtn.disabled = true; status(label("saving"));
      try {
        var r = new FileReader();
        var b64 = await new Promise(function(resolve, reject) {
          r.onload = function() { resolve(String(r.result).split(",")[1]); };
          r.onerror = reject;
          r.readAsDataURL(file);
        });
        var res = await request("audio-microphone", {
          action: "save_reference", audio: b64, transcript: text, profile_id: (settings && settings.selected) || "default"
        });
        if (res && res.reference) {
          status(label("record_saved_success") || "Autorenstimme erfolgreich importiert und aktiviert.");
          if (res.references) { allReferences = res.references; renderReferenceList(allReferences); }
          renderActiveVoiceBadge();
          updateVoiceCard();
        }
      } catch (err) { status(err.message); }
      finally { uploadBtn.disabled = false; }
    });

    fields.profile_row = node("div", content, "row"); field(fields.profile_row, "profile", "select"); fields.create = button(fields.profile_row, "create", create);
    fields.remove_profile = button(fields.profile_row, "remove_profile", removeProfile);
    fields.schema_hint = node("p", content, "ctl-note", label("schema_hint"));
    fields.schema_review = node("p", content, "ctl-note"); fields.schema_review.id = "speech-schema-review"; fields.schema_review.hidden = true;
    fields.schema_preview = button(content, "schema_preview", async function() {
      var sequence = openSequence; fields.schema_preview.disabled = true;
      try {
        var result = await request("audio-schema", Object.assign(tokens(), {apply: false}));
        if (sequence !== openSequence || !dialog.open || openedContext !== context()) return;
        fields.schema_review.textContent = uiCountFormat("speech_schema_review", result.migration.retained_profile_count, {schema: result.migration.target_schema}) +
          (result.migration.creates_default_profile ? " " + label("schema_default_profile") : "") +
          (result.migration.configuration_required ? " " + label("schema_configuration_required") : "");
        fields.schema_review.hidden = false;
        fields.schema_apply.dataset.snapshot = result.migration.snapshot; fields.schema_apply.hidden = false;
        status(label("schema_ready"));
      } catch (error) { if (sequence === openSequence && dialog.open) status(error.message); }
      finally { if (sequence === openSequence) fields.schema_preview.disabled = false; }
    });
    fields.schema_apply = button(content, "schema_apply", async function() {
      if (profilesDirty || pronunciationPending() || direction.dirty()) { status(label("profiles_unsaved")); return; }
      fields.schema_apply.disabled = true;
      try {
        await request("audio-schema", Object.assign(tokens(), {apply: true, snapshot: fields.schema_apply.dataset.snapshot}));
        location.reload();
      } catch (error) { status(error.message); fields.schema_apply.disabled = false; }
    });
    fields.schema_apply.hidden = true;
    field(content, "target", "select"); fields.target.closest("label").hidden = true;
    var targetHint = node("span", fields.target.closest("label"), "ctl-note", label("target_scope"));
    targetHint.id = "speech-target-hint"; fields.target.setAttribute("aria-describedby", targetHint.id);
    fields.target.addEventListener("change", function() {
      executionTarget = fields.target.value; invalidate();
      updateRuntimeHint();
      updateWorkerStatus();
    });
    fields.worker_status = node("p", content, "ctl-note"); fields.worker_status.id = "speech-worker-status";
    fields.worker_status.setAttribute("aria-live", "polite");
    fields.worker_guide = node("a", content, "ctl-link", label("worker_guide"));
    fields.worker_guide.id = "speech-worker-guide"; fields.worker_guide.target = "_blank";
    fields.worker_guide.rel = "noopener noreferrer"; fields.worker_guide.hidden = true;
    fields.worker_refresh = button(content, "worker_refresh", async function() {
      var sequence = openSequence; fields.worker_refresh.disabled = true;
      function currentOpen() { return sequence === openSequence && dialog.open && openedContext === context(); }
      try { var data = await request("speech"); if (currentOpen()) { workers = data.workers; updateWorkerStatus(); } }
      catch (_) { if (currentOpen()) { workers = null; updateWorkerStatus(); } }
      finally { if (currentOpen()) fields.worker_refresh.disabled = false; }
    });
    fields.editor = node("fieldset", content, "settings-section");
    node("legend", fields.editor, "", label("delivery"));
    var grid = node("div", fields.editor, "settings-grid");
    field(grid, "name").maxLength = 100; fields.name.required = true;
    field(grid, "engine", "select");
    fields.model = node("span", fields.engine.closest("label"), "ctl-note"); fields.model.id = "speech-model-hint";
    ["language", "voice"].forEach(function(key) { field(grid, key, "select"); });
    ["base_url", "provider_model", "api_key_env", "provider_voice", "provider_language"].forEach(function(key) {
      var input = field(grid, key, key === "base_url" ? "url" : "text"); input.maxLength = key === "base_url" ? 2048 : 200;
      input.required = key !== "api_key_env";
    });
    field(grid, "supports_instructions", "checkbox").addEventListener("change", updateModelFields);
    fields.engine.setAttribute("aria-describedby", "speech-model-hint speech-worker-status");
    fields.model_conflict = node("p", fields.editor, "ctl-note"); fields.model_conflict.setAttribute("aria-live", "polite"); fields.model_conflict.hidden = true;
    fields.voice_hint = node("p", fields.editor, "ctl-note", label("voice_hint"));
    field(fields.editor, "voice_description", "textarea").maxLength = 2000;
    fields.design_hint = node("p", fields.editor, "ctl-note", label("design_hint"));
    fields.design_hint.id = "speech-design-hint"; fields.voice_description.setAttribute("aria-describedby", fields.design_hint.id);
    fields.profile_voice_card = node("div", fields.editor, "voice-active-card");
    fields.profile_voice_card.hidden = true;
    var reference = field(fields.editor, "reference_id"); reference.maxLength = 64; reference.pattern = "[0-9a-f]{64}";
    reference.closest("label").className = "voice-raw-id";
    fields.reference_hint = node("p", fields.editor, "ctl-note", label("reference_hint"));
    fields.reference_hint.id = "speech-reference-hint"; reference.setAttribute("aria-describedby", fields.reference_hint.id);
    var speed = field(grid, "speed", "number"); speed.step = "any"; speed.required = true;
    var speedHint = node("span", speed.closest("label"), "ctl-note", label("speed_hint"));
    speedHint.id = "speech-speed-hint"; speed.setAttribute("aria-describedby", speedHint.id);
    ["paragraph_pause", "scene_pause"].forEach(function(key) { var el = field(grid, key, "number"); el.min = "0"; el.max = "10"; el.step = "any"; el.required = true; });
    field(fields.editor, "instructions", "textarea").maxLength = 2000;
    [fields.voice_description, fields.reference_id, fields.instructions].forEach(function(input) {
      input.addEventListener("input", updateModelFields);
    });
    var lexicon = node("details", fields.editor, "settings-section"); lexicon.id = "speech-lexicon";
    node("summary", lexicon, "", label("pronunciations"));
    var searchRow = node("div", lexicon, "row"), search = field(searchRow, "pronunciation_search", "search");
    search.addEventListener("input", renderPronunciations);
    fields.pronunciation_list = node("ul", lexicon, "pronunciation-list");
    fields.pronunciation_list.setAttribute("aria-label", label("pronunciations"));
    fields.pronunciation_empty = node("p", lexicon, "ctl-note pronunciation-empty", label("pronunciation_not_found"));
    fields.pronunciation_empty.hidden = true; fields.pronunciation_empty.setAttribute("aria-live", "polite");
    var pronunciationEditor = node("div", lexicon, "settings-grid");
    field(pronunciationEditor, "pronunciation_term").maxLength = 100;
    field(pronunciationEditor, "pronunciation_spoken").maxLength = 300;
    button(lexicon, "pronunciation_apply", applyPronunciation);
    button(lexicon, "pronunciation_discard", function() {
      editingPronunciation = null; fields.pronunciation_term.value = fields.pronunciation_spoken.value = ""; status("");
    });
    var rawList = node("details", lexicon, "settings-section");
    node("summary", rawList, "", label("pronunciation_bulk"));
    field(rawList, "pronunciations", "textarea").addEventListener("input", renderPronunciations);
    node("p", rawList, "ctl-note", label("pronunciation_hint"));
    node("p", rawList, "ctl-note", label("pronunciation_bulk_special"));
    field(content, "chapter", "select");
    direction = window.LixitySpeechDirection(content, {
      node:node, field:field, button:button, options:options, label:label, request:request,
      status:status, invalidate:invalidate, tokens:tokens,
      current:function() { return dialog.open && openedContext === context(); },
      selected:function(p) { paragraph={identity:p.anchor,chapter:p.chapter}; fields.chapter.value=String(p.chapter); }
    });
    fields.runtime_hint = node("p", content, "ctl-note", label("runtime_hint")); fields.runtime_hint.id = "speech-runtime-hint";
    var ignore = node("label", content, "form-checkbox"); ignore.hidden = true;
    fields.ignore_direction = node("input", ignore); fields.ignore_direction.type = "checkbox"; fields.ignore_direction.id = "speech-ignore-direction";
    node("span", ignore, "", label("ignore_direction"));
    fields.ignore_direction.addEventListener("change", invalidate);
    fields.ignoreLabel = ignore;
    var reuse = node("label", content, "form-checkbox"); reuse.hidden = true;
    fields.reuse = node("input", reuse); fields.reuse.type = "checkbox"; fields.reuse.id = "speech-reuse"; fields.reuse.checked = true;
    node("span", reuse, "", label("reuse"));
    fields.reuse.addEventListener("change", invalidate);
    field(content, "export_scope", "select");
    options(fields.export_scope, [["preview", label("scope_passage")], ["chapter", label("scope_chapter")], ["manuscript", label("scope_manuscript")]], "chapter");
    fields.export_scope.addEventListener("change", invalidate);
    var actions = node("div", content, "row");
    fields.preview = button(actions, "preview", function() { render("preview"); });
    fields.direction_plan = button(actions, "direction_plan", function() { render(fields.export_scope.value, true); });
    fields.plan = node("div", content, "speech-plan"); fields.plan.hidden = true;
    fields.audit_section = node("details", content, "settings-section");
    node("summary", fields.audit_section, "", label("audit_title"));
    node("p", fields.audit_section, "ctl-note", label("audit_hint"));
    field(fields.audit_section, "audit_audio", "file").accept = ".wav,.flac,.mp3";
    field(fields.audit_section, "audit_transcript", "file").accept = ".json";
    [fields.audit_audio, fields.audit_transcript].forEach(function(input) { input.addEventListener("change", invalidate); });
    fields.audit_run = button(fields.audit_section, "audit_run", inspectAudio);
    fields.audit_result = node("div", fields.audit_section, "audio-audit-result"); fields.audit_result.setAttribute("aria-live", "polite");
    fields.microphone_section = node("details", content, "settings-section");
    fields.microphone_section.id = "speech-microphone-section";
    node("summary", fields.microphone_section, "", label("microphone_title"));
    var micDevLabel = node("label", fields.microphone_section, "setting-field", label("microphone_device"));
    fields.microphone_device = node("select", micDevLabel, "ctl");
    var micGainLabel = node("label", fields.microphone_section, "setting-field", label("microphone_gain"));
    var micGainRow = node("div", micGainLabel, "row");
    fields.microphone_gain_range = node("input", micGainRow, "ctl");
    fields.microphone_gain_range.type = "range"; fields.microphone_gain_range.min = "0"; fields.microphone_gain_range.max = "50"; fields.microphone_gain_range.value = "35";
    fields.microphone_gain = node("input", micGainRow, "ctl");
    fields.microphone_gain.type = "number"; fields.microphone_gain.min = "0"; fields.microphone_gain.max = "50"; fields.microphone_gain.value = "35";
    fields.microphone_gain.style.width = "5rem";
    fields.microphone_gain_info = node("span", micGainRow, "ctl-note");
    fields.microphone_gain_range.addEventListener("input", function() { fields.microphone_gain.value = fields.microphone_gain_range.value; });
    fields.microphone_gain.addEventListener("input", function() { fields.microphone_gain_range.value = fields.microphone_gain.value; });
    fields.microphone_set_btn = button(fields.microphone_section, "microphone_set_gain", async function() {
      var g = parseInt(fields.microphone_gain.value, 10);
      try {
        var res = await request("audio-microphone", {action: "set_gain", gain: g});
        if (res && res.current_gain != null) {
          fields.microphone_gain_info.textContent = res.gain_info && res.gain_info.db != null ? (" (" + (res.gain_info.db >= 0 ? "+" : "") + res.gain_info.db.toFixed(1) + " dB)") : "";
          status("Mikrofon-Gain auf " + res.current_gain + " gesetzt.");
        }
      } catch (err) { status(err.message); }
    });
    var micCalibActions = node("div", fields.microphone_section, "row");
    fields.microphone_calib_btn = button(micCalibActions, "microphone_calibrate", async function() {
      fields.microphone_calib_btn.disabled = true; fields.microphone_calib_result.replaceChildren();
      var prepNote = node("p", fields.microphone_calib_result, "ctl-note", "4s Vorlauf... Danach 3× POPP, 2× Klatschen, 1× Sprechen.");
      status("Kalibriere Mikrofonpegel...");
      try {
        var g = parseInt(fields.microphone_gain.value, 10);
        var dev = fields.microphone_device.value;
        var res = await request("audio-microphone", {action: "calibrate", gain: g, device: dev});
        prepNote.remove();
        if (res && res.calibration) {
          var cal = res.calibration;
          var card = node("div", fields.microphone_calib_result, "audit-summary");
          var vBadge = node("div", card, "badge", cal.verdict_label);
          if (cal.verdict === "too_hot") vBadge.classList.add("badge-fail");
          else if (cal.verdict === "calibrated") vBadge.classList.add("badge-pass");
          else vBadge.classList.add("badge-warn");
          node("p", card, "", "Peak: " + (cal.peak_dbfs >= 0 ? "+" : "") + cal.peak_dbfs.toFixed(1) + " dBFS · Clipping: " + cal.clipping_samples + " · Rauschabstand (SNR): " + cal.snr_db.toFixed(1) + " dB");
          if (cal.recommended_gain != null && cal.recommended_gain !== g) {
            var recBtn = node("button", card, "ctl", "Empfohlenen Gain " + cal.recommended_gain + " anwenden");
            recBtn.type = "button";
            recBtn.addEventListener("click", function() {
              fields.microphone_gain.value = fields.microphone_gain_range.value = String(cal.recommended_gain);
              fields.microphone_set_btn.click();
            });
          }
          status("Kalibrierung abgeschlossen.");
        }
      } catch (err) { status(err.message); }
      finally { fields.microphone_calib_btn.disabled = false; }
    });
    fields.microphone_calib_result = node("div", fields.microphone_section, "audio-calib-result");
    fields.chapter_render = button(actions, "chapter_render", function() { render("chapter"); });
    fields.open_output = button(actions, "output_title", function() {
      if (direction.dirty() && !fields.ignore_direction.checked) { status(label("direction_save_first")); return; }
      invalidate(); mode = "output"; fields.heading.textContent = label("output_title");
      direction.section.hidden = !direction.dirty(); fields.direction_plan.hidden = false; fields.export_scope.value = "chapter";
      fields.open_output.hidden = true; fields.chapter_render.hidden = !canRender;
      fields.reuseLabel.hidden = !canRender;
      arrangeSections();
    });
    fields.open_output.textContent = label("open_output");
    fields.cancel = button(actions, "cancel", cancel); fields.cancel.disabled = true;
    fields.context = node("p", content, "ctl-note"); fields.progress = node("progress", content); fields.progress.hidden = true; fields.progress.setAttribute("aria-label", label("progress"));
    fields.audio = node("audio", content, "media-player"); fields.audio.controls = true; fields.audio.hidden = true;
    fields.player_controls = node("div", content, "speech-player-controls"); fields.player_controls.hidden = true;
    var skipBack = button(fields.player_controls, "skip_back", function() { fields.audio.currentTime = Math.max(0, fields.audio.currentTime - 5); });
    skipBack.textContent = "−5s"; skipBack.title = label("audio_skip_back") || "5s back";
    var skipForward = button(fields.player_controls, "skip_forward", function() { fields.audio.currentTime = Math.min(fields.audio.duration || 0, fields.audio.currentTime + 5); });
    skipForward.textContent = "+5s"; skipForward.title = label("audio_skip_forward") || "5s forward";
    [0.8, 1.0, 1.25, 1.5].forEach(function(rate) {
      var rateBtn = button(fields.player_controls, "rate_" + rate, function() {
        fields.audio.playbackRate = rate;
        fields.player_controls.querySelectorAll(".speech-rate-btn").forEach(function(b) { b.classList.remove("active"); });
        rateBtn.classList.add("active");
      });
      rateBtn.textContent = rate + "×";
      rateBtn.classList.add("speech-rate-btn");
      if (rate === 1.0) rateBtn.classList.add("active");
    });
    fields.download = node("a", content, "ctl", label("download")); fields.download.download = "speech.wav"; fields.download.hidden = true;
    var activeKaraokeSha = null;
    function clearAudioKaraoke() {
      if (activeKaraokeSha) {
        document.querySelectorAll('#chapters .ptext[data-paragraph-sha256="' + activeKaraokeSha + '"]').forEach(function(el) {
          el.classList.remove("reader-audio-active");
        });
        activeKaraokeSha = null;
      }
    }
    fields.audio.addEventListener("timeupdate", function() {
      var cur = fields.audio.currentTime;
      var dur = fields.audio.duration;
      var tl = job && (job.timeline || (job.context && job.context.timeline));
      if (!dur || !tl || !tl.segments) return;
      var segs = tl.segments.filter(function(s) { return s.anchor && s.anchor.paragraph_sha256; });
      if (!segs.length) return;
      var totalWeight = segs.reduce(function(w, s) { return w + (s.text ? s.text.length : 20); }, 0);
      var currentWeight = (cur / dur) * totalWeight;
      var running = 0;
      var match = segs[0];
      for (var i = 0; i < segs.length; i++) {
        running += (segs[i].text ? segs[i].text.length : 20);
        if (running >= currentWeight) {
          match = segs[i];
          break;
        }
      }
      var sha = match.anchor.paragraph_sha256;
      if (sha !== activeKaraokeSha) {
        clearAudioKaraoke();
        activeKaraokeSha = sha;
        document.querySelectorAll('#chapters .ptext[data-paragraph-sha256="' + sha + '"]').forEach(function(el) {
          el.classList.add("reader-audio-active");
          el.scrollIntoView({ behavior: "smooth", block: "nearest" });
        });
      }
    });
    fields.audio.addEventListener("pause", clearAudioKaraoke);
    fields.audio.addEventListener("ended", clearAudioKaraoke);
    fields.save = button(content, "save", save);
    fields.profile_discard = button(content, "profiles_discard", function() {
      if (profileSaving || !savedSettings) return;
      settings = JSON.parse(JSON.stringify(savedSettings)); profilesDirty = false;
      profileOptions(); loadProfile();
      if (openedContext !== context()) fields.save.disabled = fields.create.disabled = fields.remove_profile.disabled = fields.profile.disabled = true;
      status(""); invalidate();
    });
    fields.export_section = node("fieldset", content, "settings-section speech-export-section");
    node("legend", fields.export_section, "", label("export_title"));
    node("p", fields.export_section, "ctl-note", label("export_hint"));
    fields.export_section.append(fields.export_scope.closest("label"), fields.direction_plan, fields.plan);
    fields.render_section = node("fieldset", content, "settings-section speech-render-section");
    fields.render_heading = node("legend", fields.render_section);
    fields.render_section.append(fields.target.closest("label"), fields.worker_status, fields.worker_guide, fields.worker_refresh,
      fields.runtime_hint, reuse, actions, fields.context, fields.progress, fields.audio, fields.player_controls, fields.download);
    arrangeSections();
    fields.reuseLabel = reuse;
    fields.editor.addEventListener("input", function(event) {
      if (mode === "profiles" && ![fields.pronunciation_search, fields.pronunciation_term, fields.pronunciation_spoken].includes(event.target)) profilesDirty = true;
      invalidate();
    });
    fields.engine.addEventListener("change", function() {
      if (capabilities.qwen3.voices[fields.voice.value]) lastPreset = fields.voice.value;
      var cap = capabilities[fields.engine.value];
      if (cap.languages.length && !cap.languages.includes(fields.language.value)) options(fields.language, [[cap.languages[0], languageName(cap.languages[0])]], cap.languages[0]);
      var voice = fields.engine.value === "qwen3-design" ? "design" : cap.reference_required ? "reference" : fields.engine.value === "coqui" ? "thorsten" : lastPreset;
      options(fields.voice, [], voice);
      voiceControls(); invalidate();
    });
    fields.language.addEventListener("change", function() { fields.voice.value = ""; voiceControls(); status(label("voice_changed")); });
    fields.profile.addEventListener("change", function() {
      try { stash(); if (settings.selected !== fields.profile.value) profilesDirty = true; settings.selected = fields.profile.value; loadProfile(); }
      catch (error) { fields.profile.value = settings.selected; status(error.message); }
    });
    fields.chapter.addEventListener("change", function() { paragraph = null; invalidate(); var select=fields.direction_passage; var choice=Array.from(select.options).find(function(o) { return o.textContent.startsWith(fields.chapter.value + " · "); }); if (choice) { select.value=choice.value; select.dispatchEvent(new Event("change")); } fields.context.textContent = label("first_preview"); });
    dialog.addEventListener("cancel", function(event) {
      if (profileSaving) { event.preventDefault(); status(label("saving")); }
      else if (direction.busy() || direction.dirty()) {
        event.preventDefault(); status(label(direction.busy() ? "saving" : "direction_switch_first"));
      } else if (mode === "profiles" && pronunciationPending()) {
        event.preventDefault(); status(label("pronunciation_pending"));
      } else if (mode === "profiles" && profilesDirty) {
        event.preventDefault(); status(label("profiles_unsaved"));
      }
    });
    dialog.addEventListener("close", invalidate);
  }
  async function open(entry) {
    mode = entry || "reference";
    ++openSequence;
    var fromReader = mode === "reader";
    var readerControl = document.getElementById("reader-chapter");
    var readerChapterIntent = fromReader && readerControl ? (readerControl.value || readerControl.dataset.currentChapter || "") : "";
    if (!dialog) build(); invalidate(); direction.disable(); settings = null; savedSettings = null; workers = null; profilesDirty = false; profileSaving = false; openedContext = context(); paragraph = null;
    fields.worker_status.textContent = label("loading"); fields.worker_refresh.disabled = true; fields.model.textContent = "";
    fields.profile.disabled = false;
    switchMode(mode);
    if (fromReader) {
      var selection = window.getSelection(), anchor = selection && selection.anchorNode;
      var element = anchor && (anchor.nodeType === 1 ? anchor : anchor.parentElement);
      var panel = element && element.closest("#chapters .ptext[data-paragraph-sha256]");
      if (!panel) {
        panel = document.querySelector("#chapters .ptext.reader-selected, #chapters .ptext:focus-within");
      }
      var reader = document.getElementById("reader-chapter");
      if (panel && reader && /^ch-\d+$/.test(readerChapterIntent) && panel.closest(".chapter").id !== readerChapterIntent) panel = null;
      if (panel) paragraph = {chapter: Number((panel.closest(".chapter") || {}).id?.replace("ch-", "")), identity: {
        start_line: Number(panel.dataset.start), end_line: Number(panel.dataset.end), paragraph_sha256: panel.dataset.paragraphSha256}};
    }
    fields.context.textContent = ""; fields.reuse.checked = true; fields.reuse.disabled = false; fields.reuse.closest("label").hidden = true;
    fields.editor.querySelectorAll("input, textarea").forEach(function(input) { input.value = ""; });
    ["profile", "engine", "language", "voice", "chapter"].forEach(function(key) { fields[key].replaceChildren(); });
    dialog.showModal(); status(label("loading")); fields.editor.disabled = true; fields.save.disabled = fields.create.disabled = fields.preview.disabled = fields.chapter_render.disabled = true;
    var serial = generation;
    try {
      var data = await request("speech"); if (!valid(serial)) return;
      migrationRequired = data.requires_migration === true;
      settings = data.settings || {schema_version: "lixity-audio-settings/1", selected: "", profiles: {}}; capabilities = data.capabilities; workers = data.workers;
      if (data.references) {
        allReferences = data.references;
        renderReferenceList(allReferences);
      }
      if (data.calibration_texts) {
        calibrationTexts = data.calibration_texts;
      }
      renderActiveVoiceBadge();
      if (data.microphone) populateMicrophone(data.microphone);
      if (mode === "microphone" && fields.microphone_section) fields.microphone_section.open = true;
      fields.schema_hint.hidden = fields.schema_preview.hidden = mode !== "profiles" || settings.schema_version === "lixity-audio-settings/4" || migrationRequired;
      fields.schema_apply.hidden = true; fields.schema_apply.disabled = false;
      fields.worker_refresh.disabled = false;
      savedSettings = JSON.parse(JSON.stringify(settings));
      fields.model.textContent = capabilities.qwen3.name;
      var matchedChapter = paragraph && data.chapters.find(function(chapter) {
        return paragraph.identity.start_line >= chapter.start_line && paragraph.identity.end_line <= chapter.end_line;
      });
      var readerChapter = document.getElementById("reader-chapter");
      var selectedChapter = matchedChapter ? String(matchedChapter.number) : fromReader && readerChapter ? readerChapterIntent.replace("ch-", "") : "";
      if (!data.chapters.some(function(chapter) { return String(chapter.number) === selectedChapter; })) selectedChapter = "";
      options(fields.chapter, data.chapters.map(function(chapter) { return [String(chapter.number), chapter.number + ". " + chapter.title]; }), selectedChapter);
      if (paragraph && !data.chapters.some(function(chapter) { return Number(fields.chapter.value) === chapter.number && paragraph.identity.start_line >= chapter.start_line && paragraph.identity.end_line <= chapter.end_line; })) paragraph = null;
      profileOptions(); loadProfile();
      updateVoiceCard();
      fields.target.closest("label").hidden = fields.target.disabled;
      fields.reuseLabel.hidden = mode !== "output" || !canRender;
      savedDirectionView = data.direction || null;
      if (data.direction) {
        var initialPassage = paragraph ? {anchor:paragraph.identity} : data.direction.passages.find(function(p) { return p.chapter === Number(fields.chapter.value); });
        direction.open(data.direction, initialPassage && initialPassage.anchor, settings.profiles);
      }
      if (migrationRequired) direction.disable();
      status(data.configuration_error || ""); fields.save.disabled = migrationRequired || !settings.selected;
      fields.context.textContent = label(paragraph ? "paragraph_preview" : "first_preview");
    } catch (error) {
      if (valid(serial)) {
        fields.worker_status.textContent = uiFormat("speech_worker_unknown", {target: label("target_" + (fields.target.value || "local"))});
        status(error.message);
      }
    }
  }
  var audioLinks = node("section", null, "project-audio-actions");
  var audioHeading = node("h3", audioLinks, "", label("reader_title")); audioHeading.id = "project-audio-title";
  audioLinks.setAttribute("aria-labelledby", audioHeading.id);
  var audioActions = node("div", audioLinks, "row");
  button(audioActions, "tab_voice", function() { open("reference"); }).id = "settings-speech-record";
  button(audioActions, "profiles_title", function() { open("profiles"); }).id = "settings-speech";
  button(audioActions, "output_title", function() { open("output"); }).id = "settings-speech-output";
  button(audioActions, "microphone_title", function() { open("microphone"); }).id = "settings-speech-mic";
  settingsForm.after(audioLinks);
  var toolbar = document.getElementById("manuscript-reader-controls");
  if (toolbar) {
    var readerSpeech = button(toolbar, "reader_title", function() { open("reader"); });
    readerSpeech.id = "reader-speech";
    readerSpeech.className = "ctl reader-compact-control";
    readerSpeech.innerHTML = '<span class="reader-control-icon" aria-hidden="true">🎙</span> <span class="reader-control-label">' + label("reader_title") + '</span>';
    readerSpeech.dataset.help = label(canRender ? "reader_help" : "reader_help_plan");
  }
  var sidebarSpeechBtn = document.getElementById("btn-sidebar-speech");
  if (sidebarSpeechBtn) {
    sidebarSpeechBtn.addEventListener("click", function() { open("reference"); });
  }
  var projectSpeechBtn = document.getElementById("btn-project-speech");
  if (projectSpeechBtn) {
    projectSpeechBtn.addEventListener("click", function() { open("reference"); });
  }
  var projectRecordVoiceBtn = document.getElementById("btn-project-record-voice");
  if (projectRecordVoiceBtn) {
    projectRecordVoiceBtn.addEventListener("click", function() { open("reference"); });
  }
  var projectProfilesBtn = document.getElementById("btn-project-manage-profiles");
  if (projectProfilesBtn) {
    projectProfilesBtn.addEventListener("click", function() { open("profiles"); });
  }
  document.addEventListener("lixity:open-speech-studio", function(e) {
    var targetMode = (e && e.detail && e.detail.mode) || "reference";
    open(targetMode);
  });
  document.addEventListener("lixity:workbench-change", function() {
    if (!dialog || !dialog.open) return;
    if (profileSaving) { status(label("saving")); return; }
    if (direction.busy() || direction.dirty()) {
      status(label(direction.busy() ? "saving" : "direction_switch_first")); return;
    }
    if (mode === "profiles" && pronunciationPending()) { status(label("pronunciation_pending")); return; }
    if (mode === "profiles" && profilesDirty) { status(label("profiles_unsaved")); return; }
    dialog.close();
  });
  new MutationObserver(function() {
    if (!dialog || !dialog.open || context() === openedContext) return;
    if (mode === "profiles" && (pronunciationPending() || profilesDirty || profileSaving)) {
      invalidate(); fields.save.disabled = fields.create.disabled = fields.remove_profile.disabled = fields.profile.disabled = true;
      status(label(pronunciationPending() && !profilesDirty ? "pronunciation_context_changed" : "profiles_context_changed")); return;
    }
    if (direction.dirty() || direction.busy()) {
      invalidate(); direction.stale(); status(label("direction_context_changed")); return;
    }
    dialog.close();
  }).observe(body, {
    subtree: true, attributes: true, attributeFilter: ["data-project-token", "data-manuscript-source-sha256", "data-manuscript-project-token"]});
})();
