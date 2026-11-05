/* Project-local listening drafts share one token-bound native dialog. */
(function() {
  "use strict";
  var body = document.body, settingsForm = document.getElementById("settings-form");
  if (body.dataset.speechCapable !== "true" || body.dataset.readOnly === "true" || !settingsForm) return;
  var canRender = body.dataset.speechRenderCapable === "true";
  var dialog, fields = {}, settings, capabilities, workers, generation = 0, openSequence = 0, job = null, timer, openedContext, paragraph;
  var executionTarget = "local", migrationRequired = false, direction, savedDirectionView, lastPreset = "Ryan", mode = "reference", editingPronunciation = null;
  var savedSettings = null, profilesDirty = false, profileSaving = false, auditAudioUrl = null;
  var speechReady = false, speechLoadMessage = "";
  var specialPronunciations = Object.create(null);
  var profileProsody;
  var currentAudioSchema = "lixity-audio-settings/5";
  var allReferences = [], calibrationTexts = null;
  var microphoneState = null, microphoneBusy = false;
  var chapterAudio = null, chapterAudioBusy = false, chapterAudioSequence = 0;
  var audioStream = null, audioCtx = null, audioSource = null, audioProcessor = null, recordedChunks = [], totalRecordedSamples = 0;
  var recTimerInterval = null, recStartTime = 0, isRecordingVoice = false, lastRecordedWavBlob = null, sampleVariant = "short";

  var importedTake = null, takeTokens = null, takeImportSequence = 0;
  var recordingPending = false, recordingSequence = 0, takeUrl = null, takeTranscript = "", voiceSaving = false, takeValid = false;
  function label(key) { return uiLabel("speech_" + key); }
  function recordingFeedback(state, message, stateLabel) {
    if (!fields.recState) return;
    fields.recState.dataset.state = state;
    fields.recState.textContent = label(stateLabel || "record_state_" + state);
    fields.recState.hidden = state === "idle" && !speechReady;
    fields.recError.textContent = message || "";
    fields.recError.hidden = !message;
    // Keep recording errors beside their control instead of repeating the
    // same long explanation above the dialog's scrolling content.
    if (state === "failed" && message && fields.status.textContent === message) fields.status.hidden = true;
    var descriptions = (fields.recBtn.getAttribute("aria-describedby") || "").split(/\s+/).filter(function(id) {
      return id && id !== fields.recError.id;
    });
    if (message) descriptions.push(fields.recError.id);
    if (descriptions.length) fields.recBtn.setAttribute("aria-describedby", descriptions.join(" "));
    else fields.recBtn.removeAttribute("aria-describedby");
    if (state === "failed" || state === "busy") {
      var sequence = recordingSequence;
      requestAnimationFrame(function() {
        if (!dialog.open || mode !== "reference" || sequence !== recordingSequence || fields.recState.dataset.state !== state) return;
        // The fixed status above the scroller can grow after an error. Reveal
        // feedback inside the dialog without moving the underlying manuscript.
        var bounds = fields.panel.getBoundingClientRect(), button = fields.recBtn.getBoundingClientRect();
        var feedback = fields.recState.getBoundingClientRect(), top = Math.min(button.top, feedback.top);
        var bottom = Math.max(button.bottom, feedback.bottom), inset = 8;
        if (!fields.recError.hidden) {
          var errorBottom = fields.recError.getBoundingClientRect().bottom;
          if (errorBottom - top <= bounds.height - inset * 2) bottom = Math.max(bottom, errorBottom);
        }
        var offset = Math.max(0, bottom - (bounds.bottom - inset));
        // When all details do not fit, keep the button and concise state first.
        if (top - offset < bounds.top + inset) offset = top - bounds.top - inset;
        if (offset) fields.panel.scrollTop += offset;
      });
    }
  }
  function recordingDiagnostic(stage, errorName) {
    if (!window.LixityLog) return;
    var knownErrors = ["NotAllowedError", "PermissionDeniedError", "SecurityError", "NotFoundError", "NotReadableError",
      "OverconstrainedError", "ConstraintNotSatisfiedError", "AbortError", "InvalidStateError", "NotSupportedError",
      "InvalidAccessError", "OperationError", "TypeError", "RangeError", "ReferenceError", "SyntaxError", "Error"];
    var microphonePolicy = null;
    try {
      var policy = document.permissionsPolicy || document.featurePolicy;
      if (policy && typeof policy.allowsFeature === "function") {
        var allowed = policy.allowsFeature("microphone");
        if (typeof allowed === "boolean") microphonePolicy = allowed;
      }
    } catch (_) { /* An unavailable policy inspector is not a denied permission. */ }
    var audioState = audioCtx && audioCtx.state;
    // Never include Error objects/messages, URLs, device identities or captured data.
    window.LixityLog.error("Audio recording failed", {
      stage: stage,
      error_name: knownErrors.includes(errorName) ? errorName : "UnknownError",
      secure_context: window.isSecureContext === true,
      media_devices_available: !!navigator.mediaDevices,
      get_user_media_available: !!navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === "function",
      audio_context_available: typeof (window.AudioContext || window.webkitAudioContext) === "function",
      audio_context_state: ["suspended", "running", "closed", "interrupted"].includes(audioState) ? audioState : null,
      microphone_policy: microphonePolicy,
      top_level: window.top === window
    });
  }
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
    addHelp(el, key);
    el.dataset.speechAction = key; el.addEventListener("click", action); return el;
  }
  function field(parent, key, type) {
    var input = window.LixityComponents.createField(parent, {label: label(key), type: type, id: "speech-" + key});
    addHelp(input, key);
    fields[key] = input;
    if (type === "textarea") input.rows = 3;
    return input;
  }
  function options(select, values, selected, unavailableLabel) {
    select.replaceChildren(); values.forEach(function(pair) { select.add(new Option(pair[1], pair[0])); });
    // Retain saved values visibly even when capabilities no longer list them.
    if (selected && !values.some(function(pair) { return pair[0] === selected; })) select.add(new Option(unavailableLabel || selected, selected));
    select.value = selected || (values[0] && values[0][0]) || "";
  }
  function profileCapability() { return capabilities && capabilities[fields.engine.value] || {}; }
  function profileSupport() {
    var cap = profileCapability(), support = Object.assign({}, cap.control_support || {});
    if (cap.configurable_instructions) support.direction = fields.supports_instructions.checked ? "model_interpreted" : "unsupported";
    return support;
  }
  function createProsody(parent, prefix, changed, inherited) {
    var section = node("fieldset", parent, "settings-section"), inputs = {}, support = {};
    node("legend", section, "", label("prosody"));
    node("p", section, "ctl-note", label(inherited ? "prosody_inherit" : "prosody_default"));
    var grid = node("div", section, "settings-grid");
    ["duration_scaling_factor", "pitch_variance_scale", "energy_variance_scale", "pause_duration_scaling_factor", "prosody_creativity"].forEach(function(key) {
      var input = window.LixityComponents.createField(grid, {label:label("prosody_" + key), type:"number",
        id:"speech-" + prefix + key, help:label("prosody_" + key + "_help")});
      input.step = "any";
      input.addEventListener("input", function() { update(support); changed(); });
      inputs[key] = input;
    });
    button(section, "prosody_reset", function() { load({}); changed(); });
    function update(next) {
      support = next || {};
      var present = Object.values(inputs).some(function(input) { return input.value !== ""; });
      section.hidden = !Object.keys(support).length && !present;
      Object.entries(inputs).forEach(function(pair) {
        var key = pair[0], input = pair[1], control = support[key];
        input.closest("label").hidden = !control && input.value === "";
        input.disabled = !control && input.value === "";
        input.setCustomValidity(!control && input.value !== "" ? label("controls_unsupported") : "");
        if (control) {
          input.min = String(control.minimum); input.max = String(control.maximum);
          input.placeholder = inherited ? label("prosody_inherited") : String(control.default);
        }
      });
    }
    function load(values) {
      Object.entries(inputs).forEach(function(pair) { pair[1].value = values && values[pair[0]] != null ? values[pair[0]] : ""; });
      update(support);
    }
    return {section:section, update:update, load:load, read:function() {
      var values = {};
      Object.entries(inputs).forEach(function(pair) {
        if (!pair[1].reportValidity()) throw new Error(pair[1].validationMessage);
        if (pair[1].value !== "") values[pair[0]] = Number(pair[1].value);
      });
      return values;
    }};
  }
  function phonemeEntries() {
    var result = Object.create(null);
    fields.phonemes.value.split("\n").forEach(function(line) {
      if (!line.trim()) return;
      var split = line.lastIndexOf("="), term = line.slice(0, split).trim(), ipa = line.slice(split + 1).trim();
      if (split < 1 || !term || !ipa || Array.from(term).length > 100 || Array.from(ipa).length > 300 || Object.hasOwn(result, term)) throw new Error(label("phonemes_error"));
      result[term] = ipa;
    });
    if (Object.keys(result).length > 200) throw new Error(label("phonemes_error"));
    return result;
  }
  function status(message) { fields.status.textContent = message || ""; fields.status.hidden = !message; }
  function addHelp(el, key) {
    var aliases = {engine:"service_help", voice:"voice_hint", voice_description:"design_hint", reference_id:"reference_hint",
      speed:"speed_hint", pronunciations:"pronunciation_hint", pronunciation_term:"pronunciation_hint", pronunciation_spoken:"pronunciation_hint",
      direction_instructions:"direction_hint", instructions:"direction_hint", audit_audio:"audit_hint", audit_transcript:"audit_hint",
      export_scope:"export_hint", direction_plan:"export_hint", worker_refresh:"service_help", profile:"profile_help",
      name:"profile_help", language:"language_help", paragraph_pause:"pause_help", scene_pause:"pause_help",
      direction_before:"pause_help", direction_after:"pause_help", direction_profile:"profile_help",
      direction_selection:"selection_help", direction_text:"selection_help", direction_style:"direction_hint",
      direction_entries:"selection_help", direction_passage:"selection_help", chapter:"selection_help",
      preview:"preview_help", chapter_render:"render_help", save:"save_help", profiles_discard:"discard_help",
      record_start:"record_help", record_save:"record_save_help", upload_voice_file:"upload_help", upload_voice_transcript:"transcript_help"};
    var help = label(aliases[key] || key + "_help");
    if (!help.startsWith("speech_")) el.dataset.help = help;
  }
  function arrangeSections() {
    var reading = mode === "reader" || mode === "output";
    fields.chapter_audio_section.hidden = !reading;
    fields.export_section.hidden = !reading;
    fields.render_section.hidden = !reading || !canRender;
    fields.service_section.hidden = mode !== "profiles";
    fields.microphone_section.hidden = mode !== "microphone";
    fields.render_heading.textContent = label("render_title");
    fields.playback_section.hidden = mode === "microphone";
    if (mode === "reference") fields.active_voice_badge.after(fields.playback_section);
    else if (mode === "profiles") fields.service_section.after(fields.playback_section);
    else fields.audit_section.after(fields.playback_section);
    fields.audit_section.before(...(mode === "reader" ? [fields.render_section, fields.export_section] : [fields.export_section, fields.render_section]));
    fields.export_section.after(fields.chapter_audio_section);
    fields.schema_hint.hidden = fields.schema_preview.hidden = mode !== "profiles" || !settings || settings.schema_version === currentAudioSchema || migrationRequired;
    if (mode !== "profiles") fields.schema_review.hidden = fields.schema_apply.hidden = true;
  }
  function downloadText(text, filename, type) {
    var address = URL.createObjectURL(new Blob([text], {type: type + ";charset=utf-8"}));
    var link = document.createElement("a"); link.href = address; link.download = filename;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(function() { URL.revokeObjectURL(address); }, 2000);
  }
  function microphoneMixer() {
    var mic = microphoneState, info = mic && mic.gain_info;
    var device = mic && (mic.devices || []).find(function(item) { return item.alsa_id === fields.microphone_device.value; });
    if (!info || !device || info.card == null || !info.control ||
        ![device.card, device.card_id].some(function(card) { return card != null && String(card) === String(info.card); }) ||
        !Number.isInteger(mic.current_gain) || !Number.isInteger(info.min) || !Number.isInteger(info.max) ||
        info.min < 0 || info.max <= info.min ||
        mic.current_gain < info.min || mic.current_gain > info.max) return null;
    return info;
  }
  function microphoneControls() {
    var mixer = microphoneMixer(), editable = mixer && mixer.max <= 100;
    fields.microphone_device.disabled = microphoneBusy || !microphoneState || !fields.microphone_device.options.length;
    fields.microphone_gain.disabled = fields.microphone_gain_range.disabled = fields.microphone_set_btn.disabled = microphoneBusy || !editable;
    fields.microphone_calib_btn.disabled = microphoneBusy || !microphoneState || !fields.microphone_device.value;
  }
  function showMicrophoneGain() {
    var info = microphoneMixer();
    fields.microphone_gain.value = fields.microphone_gain_range.value = info ? String(microphoneState.current_gain) : "";
    fields.microphone_gain_range.hidden = !info;
    fields.microphone_gain_info.textContent = label("microphone_gain_unknown");
    if (info) {
      [fields.microphone_gain, fields.microphone_gain_range].forEach(function(input) {
        input.min = String(info.min); input.max = String(info.max);
        input.value = String(microphoneState.current_gain);
      });
      fields.microphone_gain_info.textContent = uiFormat("speech_microphone_gain_limits", {minimum:info.min, maximum:info.max}) +
        (Number.isFinite(info.db) ? " · " + (info.db >= 0 ? "+" : "") + info.db.toFixed(1) + " dB" : "") +
        (info.max > 100 ? " · " + label("microphone_gain_read_only") : "");
    }
    fields.microphone_calib_result.replaceChildren();
    microphoneControls();
  }
  function populateMicrophone(mic, selectedDevice) {
    if (!fields.microphone_device) return;
    microphoneState = mic;
    fields.microphone_device.replaceChildren();
    if (mic && mic.devices && mic.devices.length) {
      mic.devices.forEach(function(d) {
        var opt = new Option(d.label, d.alsa_id);
        if (d.alsa_id === (selectedDevice || mic.default_device)) opt.selected = true;
        fields.microphone_device.add(opt);
      });
    }
    showMicrophoneGain();
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
    fields.worker_guide.hidden = fields.engine.value === "openai-compatible" || profileCapability().runtime_status === "unavailable";
    fields.worker_guide.href = profileCapability().guide_url || (fields.engine.value.startsWith("coqui") ? settingsForm.dataset.speechCoquiGuide : settingsForm.dataset.speechQwenGuide);
    if (fields.engine.value === "openai-compatible") { fields.worker_status.textContent = label("provider_status"); return; }
    if (profileCapability().runtime_status === "unavailable") { fields.worker_status.textContent = label("engine_unavailable"); return; }
    var target = fields.target.value || "local", cap = capabilities[fields.engine.value];
    var worker = Array.isArray(workers) ? workers.find(function(item) { return item.target === target && (!item.engines || item.engines.includes(fields.engine.value)); }) : null;
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
    var cap = profileCapability();
    var key = cap.runtime_status === "unavailable" ? "engine_unavailable" : cap.configurable_model ? "provider_hint" : "runtime_hint";
    fields.runtime_hint.textContent = label(key);
  }
  function updateModelFields() {
    var cap = profileCapability(), support = profileSupport();
    var designed = !!cap.voice_design, referenced = !!cap.reference_required;
    var noInstructions = support.direction !== "model_interpreted";
    var exportOnly = !!support.prosody;
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
    fields.instructions.closest("label").hidden = noInstructions && !instructionPresent && !exportOnly;
    fields.instructions.disabled = noInstructions && !instructionPresent && !exportOnly;
    fields.instructions.setCustomValidity(noInstructions && instructionPresent && !exportOnly ? label("model_clear_instructions") : "");
    fields.instructions_note.hidden = !exportOnly;
    fields.phonemes_section.hidden = !support.phonemes && !fields.phonemes.value.trim();
    fields.phonemes.disabled = !support.phonemes && !fields.phonemes.value.trim();
    fields.phonemes.setCustomValidity(!support.phonemes && fields.phonemes.value.trim() ? label("controls_unsupported") : "");
    profileProsody.update(support.prosody);
    fields.model_conflict.textContent = [fields.voice_description, fields.reference_id, fields.instructions]
      .filter(function(input) { return input.validity.customError; }).map(function(input) { return input.validationMessage; }).join(" ");
    fields.model_conflict.hidden = !fields.model_conflict.textContent;
  }
  function voiceControls() {
    var cap = capabilities[fields.engine.value];
    if (!cap) return;
    var designed = !!cap.voice_design;
    var external = !!cap.configurable_model;
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
    fields.reference_hint.hidden = !referenced;
    fields.voice_hint.hidden = true;
    fields.design_hint.hidden = !designed;
    fields.speed.min = String(cap.speed.minimum);
    fields.speed.max = String(cap.speed.maximum);
    fields.model.textContent = cap.name;
    direction.setCapabilities(capabilities, fields.engine.value, profileSupport());
    options(fields.target, cap.targets.map(function(value) { return [value, label("target_" + value)]; }),
      cap.targets.includes(executionTarget) ? executionTarget : cap.targets[0]);
    fields.target.disabled = cap.targets.length < 2;
    fields.target.closest("label").hidden = mode !== "profiles" || fields.target.disabled;
    updateRuntimeHint();
    fields.reuse.closest("label").hidden = mode !== "output" || !canRender;
    updateWorkerStatus(); updateVoiceCard();
  }
  function loadProfile() {
    invalidate();
    if (!settings.selected) return;
    var profile = settings.profiles[settings.selected];
    lastPreset = profile.engine === "qwen3" ? profile.voice : "Ryan";
    ["name", "instructions", "speed", "paragraph_pause", "scene_pause"].forEach(function(key) { fields[key].value = profile[key]; });
    options(fields.engine, Object.keys(capabilities).filter(function(key) {
      return capabilities[key].creation_enabled !== false || key === profile.engine;
    }).map(function(key) {
      return [key, capabilities[key].name];
    }), profile.engine);
    fields.base_url.value = profile.base_url || ""; fields.provider_model.value = profile.model || "";
    fields.api_key_env.value = profile.api_key_env || ""; fields.supports_instructions.checked = !!profile.supports_instructions;
    fields.provider_voice.value = profile.engine === "openai-compatible" ? profile.voice : "";
    fields.provider_language.value = profile.language;
    fields.voice_description.value = profile.voice_description || "";
    fields.phonemes.value = Object.entries(profile.phonemes || {}).map(function(pair) { return pair.join("="); }).join("\n");
    profileProsody.load(profile.prosody || {});
    referenceOptions(profile.reference_id || "");
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
    if (profileCapability().voice_design && !fields.voice_description.value.trim()) throw new Error(label("model_need_description"));
    var replacements = pronunciationEntries();
    var profile = {name: fields.name.value.trim(), engine: fields.engine.value, language: fields.language.value,
      voice: fields.voice.value,
      speed: Number(fields.speed.value), instructions: fields.instructions.value.trim(),
      paragraph_pause: Number(fields.paragraph_pause.value), scene_pause: Number(fields.scene_pause.value), pronunciations: replacements};
    if (profileCapability().voice_design) profile.voice_description = fields.voice_description.value.trim();
    if (capabilities[profile.engine].reference_required) profile.reference_id = fields.reference_id.value.trim();
    var phonemes = phonemeEntries(), prosody = profileProsody.read();
    if (Object.keys(phonemes).length) profile.phonemes = phonemes;
    if (Object.keys(prosody).length) profile.prosody = prosody;
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
    var authorEngine = "ims-toucan", cap = capabilities[authorEngine];
    var engine = cap && cap.creation_enabled !== false && cap.languages.includes(language) ? authorEngine : Object.keys(capabilities).find(function(key) {
      return capabilities[key].creation_enabled !== false && capabilities[key].languages.includes(language) && !capabilities[key].reference_required && !capabilities[key].voice_design;
    }) || "openai-compatible";
    cap = capabilities[engine];
    var external = !!cap.configurable_model;
    if (external && !["lixity-audio-settings/4", currentAudioSchema].includes(settings.schema_version)) { status(label("provider_schema_required")); return; }
    if (engine === authorEngine && settings.schema_version !== currentAudioSchema) { status(label("phonemes_schema_required")); return; }
    var voice = cap.reference_required ? "reference" : external ? "" : Object.keys(cap.voices)[0];
    settings.profiles[id] = {name: label("new_profile"), engine: engine, language: language, voice: voice, speed: cap.speed.default,
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
        if (result.context && result.context.mode === "chapter") refreshChapterAudio();
      } else if (["error", "stale", "cancelled"].includes(result.state)) finish();
      else timer = setTimeout(function() { poll(serial, active); }, 500);
    } catch (error) { if (valid(serial)) { status(error.message); finish(); } }
  }
  function finish() { job = null; fields.cancel.disabled = true; fields.preview.disabled = fields.chapter_render.disabled = !canRender || !settings || !settings.selected || !fields.chapter.options.length || openedContext !== context(); }
  function showChapterAudio() {
    if (!fields.chapter_audio_status || chapterAudio === null || chapterAudioBusy) return;
    var entry = chapterAudio.find(function(item) { return item.chapter === Number(fields.chapter.value); });
    fields.chapter_audio_status.textContent = entry ? label("chapter_audio_ready") + " · " + entry.duration_seconds.toFixed(1) + " s" : label("chapter_audio_missing");
  }
  async function refreshChapterAudio() {
    if (!speechReady || chapterAudioBusy || (mode !== "reader" && mode !== "output")) return;
    var sequence = ++chapterAudioSequence, opening = openSequence, bound = context();
    chapterAudio = null;
    fields.chapter_audio_status.textContent = label("loading");
    try {
      var result = await request("speech-audio-artifacts");
      if (sequence !== chapterAudioSequence || opening !== openSequence || !dialog.open || bound !== context()) return;
      chapterAudio = result.artifacts || []; showChapterAudio();
    } catch (error) {
      if (sequence === chapterAudioSequence && opening === openSequence && dialog.open && bound === context()) fields.chapter_audio_status.textContent = error.message;
    }
  }
  async function importChapterAudio() {
    if (chapterAudioBusy || !speechReady || openedContext !== context()) return;
    var file = fields.chapter_audio_file.files[0];
    if (!file) { fields.chapter_audio_file.reportValidity(); return; }
    if (file.size > 48 * 1024 * 1024) { fields.chapter_audio_status.textContent = label("chapter_audio_too_large"); return; }
    var bound = tokens(), chapter = Number(fields.chapter.value), opening = openSequence, captureContext = context();
    ++chapterAudioSequence; chapterAudioBusy = true;
    fields.chapter_audio_import.disabled = fields.chapter_audio_file.disabled = fields.chapter.disabled = true;
    fields.chapter_audio_status.textContent = label("saving");
    try {
      var encoded = await new Promise(function(resolve, reject) {
        var reader = new FileReader();
        reader.onload = function() { resolve(String(reader.result).split(",")[1]); };
        reader.onerror = function() { reject(new Error(label("failed"))); };
        reader.readAsDataURL(file);
      });
      if (opening !== openSequence || !dialog.open || captureContext !== context()) throw new Error(label("direction_context_changed"));
      var result = await request("speech-audio-import", Object.assign({}, bound, {chapter:chapter, audio:encoded}));
      if (opening !== openSequence || !dialog.open || captureContext !== context()) return;
      chapterAudio = (chapterAudio || []).filter(function(entry) { return entry.chapter !== chapter; });
      chapterAudio.push(result.artifact); fields.chapter_audio_file.value = "";
      fields.chapter_audio_status.textContent = label("chapter_audio_ready") + " · " + result.artifact.duration_seconds.toFixed(1) + " s";
    } catch (error) {
      if (opening === openSequence && dialog.open) fields.chapter_audio_status.textContent = error.message;
    } finally {
      if (opening === openSequence) {
        chapterAudioBusy = false;
        fields.chapter_audio_import.disabled = fields.chapter_audio_file.disabled = !speechReady || openedContext !== context();
        fields.chapter.disabled = false;
      }
    }
  }
  async function render(mode, planOnly) {
    if (migrationRequired || (!planOnly && !canRender)) return;
    if (openedContext !== context()) { status(label("direction_context_changed")); return; }
    try {
      if (!Array.from(fields.editor.querySelectorAll("input, select, textarea")).every(function(input) { return input.reportValidity(); })) return;
      var profile = readProfile(); invalidate(); var serial = generation;
      if (!planOnly && profile.instructions && profileSupport().direction !== "model_interpreted") throw new Error(label("instructions_export_only"));
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
          var item = node("li",segments);
          if (row.text) window.LixitySpeechPresentation.appendText(item, row);
          else item.appendChild(document.createTextNode(label("direction_pause")));
          var voiceName = row.profile.voice_description || (row.profile.reference_id ? referenceLabel(row.profile.reference_id) : row.profile.voice);
          node("p",item,"ctl-note",[voiceName].concat(window.LixitySpeechPresentation.controls(row, uiLabel)).filter(Boolean).join(" · "));
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
    if (migrationRequired || profileSaving) return false;
    if (openedContext !== context()) { status(label("pronunciation_context_changed")); return false; }
    try {
      if (!Array.from(fields.editor.querySelectorAll("input, select, textarea")).every(function(input) { return input.reportValidity(); })) return false;
      stash();
      if (!["lixity-audio-settings/3", "lixity-audio-settings/4", currentAudioSchema].includes(settings.schema_version) && Object.values(settings.profiles).some(function(profile) { return profile.engine.startsWith("coqui"); })) {
        status(label("coqui_schema_required")); return false;
      }
      if (!["lixity-audio-settings/4", currentAudioSchema].includes(settings.schema_version) && Object.values(settings.profiles).some(function(profile) { return profile.engine === "openai-compatible"; })) {
        status(label("provider_schema_required")); return false;
      }
      if (settings.schema_version !== currentAudioSchema && Object.values(settings.profiles).some(function(profile) {
        return profile.engine === "ims-toucan" || Object.keys(profile.phonemes || {}).length || Object.keys(profile.prosody || {}).length;
      })) { status(label("phonemes_schema_required")); return false; }
      invalidate(); var serial = generation; profileSaving = true;
      fields.editor.disabled = fields.profile.disabled = fields.create.disabled = fields.remove_profile.disabled = fields.profile_discard.disabled = fields.save.disabled = true;
      status(label("saving"));
      await request("settings", {project_token: tokens().project_token, audio: settings});
      if (!valid(serial)) return false;
      location.reload();
      return true;
    } catch (error) {
      if (serial == null || valid(serial)) status(error.message.includes("A removed voice profile is used by saved speech direction") ? label("profile_referenced") : error.message);
      return false;
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
  function referenceName(reference, index, limit) {
    var name = (reference.title || reference.transcript || "").trim() || label("reference_untitled") + " " + (index + 1);
    return limit && name.length > limit ? name.slice(0, limit).trimEnd() + "…" : name;
  }
  function referenceDuration(reference) {
    var seconds = reference && reference.duration_seconds;
    return typeof seconds === "number" && Number.isFinite(seconds) && seconds >= 0
      ? seconds.toLocaleString(document.documentElement.lang || undefined, {maximumFractionDigits: 1}) + " s" : "";
  }
  function referenceLabel(referenceId) {
    var index = allReferences.findIndex(function(reference) { return reference.id === referenceId; });
    if (index < 0) return label("reference_unavailable");
    var reference = allReferences[index], duration = referenceDuration(reference);
    return referenceName(reference, index, 72) + (duration ? " · " + duration : "");
  }
  function referenceOptions(selected) {
    options(fields.reference_id, [["", label("reference_none")]].concat(allReferences.map(function(reference) {
      return [reference.id, referenceLabel(reference.id)];
    })), selected, label("reference_unavailable"));
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
    if (match) {
      var playBtn = node("button", fields.profile_voice_card, "ctl", "▶ " + label("listen_reference"));
      playBtn.type = "button";
      playBtn.addEventListener("click", function() {
        fields.audio.src = url("speech-audio", {reference_id: curId});
        fields.audio.hidden = false;
        fields.audio.play().catch(function(error) { status(error.message); });
      });
    } else {
      node("span", fields.profile_voice_card, "voice-card-info", label(curId ? "reference_unavailable_help" : "no_voice_yet"));
    }
    var recordBtn = node("button", fields.profile_voice_card, "ctl", "🎙 " + label("record_author_title"));
    recordBtn.type = "button";
    recordBtn.addEventListener("click", function() { switchMode("reference"); });
  }
  function renderActiveVoiceBadge() {
    if (!fields.active_voice_badge) return;
    fields.active_voice_badge.replaceChildren();
    var persisted = savedSettings || settings;
    var curProf = persisted && persisted.selected && persisted.profiles[persisted.selected];
    var activeId = curProf && curProf.reference_id;
    var match = activeId && allReferences.find(function(r) { return r.id === activeId; });
    var span = node("span", fields.active_voice_badge, "voice-badge-text");
    if (activeId) {
      span.textContent = label("active_voice") + ": " + referenceLabel(activeId);
      if (!match) return;
      var prevBtn = node("button", fields.active_voice_badge, "ctl", "▶ " + label("listen_reference"));
      prevBtn.type = "button";
      prevBtn.addEventListener("click", function() {
        fields.audio.src = url("speech-audio", {reference_id: activeId});
        fields.audio.hidden = false;
        fields.audio.play().catch(function(error) { status(error.message); });
      });
    } else {
      span.innerHTML = "⚪ <em>" + (label("no_voice_yet") || "Noch keine Autorenstimme für dieses Projekt hinterlegt.") + "</em>";
    }
  }
  function renderReferenceList(refs) {
    if (!fields.reference_list) return;
    fields.reference_list.replaceChildren();
    if (!refs || !refs.length) {
      node("p", fields.reference_list, "ctl-note", label("reference_empty"));
      return;
    }
    refs.forEach(function(ref, index) {
      var item = node("div", fields.reference_list, "voice-ref-item");
      var info = node("div", item, "voice-ref-info");
      node("div", info, "voice-ref-text", referenceName(ref, index));
      var duration = referenceDuration(ref);
      if (duration) node("div", info, "voice-ref-meta", label("audit_duration") + ": " + duration);
      var actions = node("div", item, "row");
      var play = node("button", actions, "ctl", "▶");
      play.type = "button"; play.setAttribute("aria-label", label("listen_reference")); addHelp(play, "listen_reference");
      play.addEventListener("click", function() {
        fields.audio.src = url("speech-audio", {reference_id: ref.id});
        fields.audio.hidden = false;
        fields.audio.play().catch(function(error) { status(error.message); });
      });
      var persisted = savedSettings || settings;
      var activeProfile = persisted && persisted.selected && persisted.profiles[persisted.selected];
      var isCurrent = activeProfile && activeProfile.reference_id === ref.id;
      if (isCurrent) {
        node("span", actions, "badge", "✓ " + label("active_voice"));
      } else {
        var useBtn = node("button", actions, "ctl", label("use_as_active") || "Aktivieren");
        useBtn.type = "button";
        useBtn.addEventListener("click", async function() {
          var curProf = settings && settings.selected && settings.profiles[settings.selected];
          if (curProf && switchMode("profiles")) {
            // Populate a visible draft first. A rejected write must not change
            // the persisted active badge or hide fields that need correction.
            fields.reference_id.value = ref.id;
            profilesDirty = true;
            fields.engine.value = curProf.engine;
            options(fields.voice, [], curProf.voice); voiceControls();
            if (!await save()) updateVoiceCard();
          }
        });
      }
    });
  }
  function releaseRecording() {
    isRecordingVoice = false; recordingPending = false;
    clearInterval(recTimerInterval); recTimerInterval = null;
    if (audioProcessor) { audioProcessor.onaudioprocess = null; audioProcessor.disconnect(); audioProcessor = null; }
    if (audioSource) { audioSource.disconnect(); audioSource = null; }
    if (audioStream) { audioStream.getTracks().forEach(function(t) { t.stop(); }); audioStream = null; }
    if (fields.takeWidget) fields.takeWidget.clearLiveAnalyser();
    if (audioCtx) { audioCtx.close().catch(function() {}); audioCtx = null; }
    fields.recBtn.disabled = !speechReady;
    fields.recBtn.textContent = "🎙 " + label("record_start");
    fields.recBtn.classList.remove("is-recording");
    fields.recTimer.hidden = true;
    fields.promptControls.forEach(function(el) { el.disabled = false; });
    fields.saveVoiceBtn.disabled = !takeValid;
    recordingFeedback("idle");
  }
  async function startVoiceRecording() {
    if (!speechReady || recordingPending || isRecordingVoice || voiceSaving) return;
    if (sampleVariant === "custom" && !fields.customTextarea.value.trim()) {
      recordingDiagnostic("preflight", "InvalidStateError");
      status(label("transcript_help")); recordingFeedback("failed", label("transcript_help")); return;
    }
    if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== "function") {
      recordingDiagnostic("preflight", "NotSupportedError");
      status(label("mic_unavailable")); recordingFeedback("failed", label("mic_unavailable")); return;
    }
    var sequence = ++recordingSequence, captureContext = context();
    recordingPending = true; fields.recBtn.disabled = true; status(label("mic_pending"));
    recordingFeedback("busy");
    var stage = "audio_context_create";
    try {
      var AudioCtxClass = window.AudioContext || window.webkitAudioContext;
      audioCtx = new AudioCtxClass({sampleRate: 24000});
      stage = "audio_context_resume";
      await audioCtx.resume();
      if (sequence !== recordingSequence || !dialog.open || mode !== "reference" || captureContext !== context()) return;
      stage = "microphone_request";
      var stream = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false}});
      if (sequence !== recordingSequence || !dialog.open || mode !== "reference" || captureContext !== context()) {
        stream.getTracks().forEach(function(t) { t.stop(); }); return;
      }
      audioStream = stream;
      stage = "audio_source_create";
      audioSource = audioCtx.createMediaStreamSource(stream);
      stage = "capture_processor_create";
      audioProcessor = audioCtx.createScriptProcessor(4096, 1, 1);
      stage = "analyser_create";
      var analyser = audioCtx.createAnalyser(); analyser.fftSize = 256; audioSource.connect(analyser);
      recordedChunks = []; totalRecordedSamples = 0; isRecordingVoice = true; recordingPending = false;
      importedTake = null; takeTokens = tokens();
      fields.takeExports.hidden = true;
      fields.take_confirmed.closest("label").hidden = fields.takeNotice.hidden = true;
      lastRecordedWavBlob = null; takeValid = false;
      if (takeUrl) { URL.revokeObjectURL(takeUrl); takeUrl = null; }
      takeTranscript = sampleVariant === "custom" ? fields.customTextarea.value.trim() : fields.promptText.textContent.trim();
      fields.promptControls.forEach(function(el) { el.disabled = true; });
      fields.audio.pause(); fields.takePlayer.pause(); fields.takePlayer.removeAttribute("src"); fields.takePlayer.load();
      fields.takeCard.hidden = false; fields.takeStats.textContent = ""; fields.saveVoiceBtn.disabled = true;
      fields.takeWidget.setLiveAnalyser(analyser);
      audioProcessor.onaudioprocess = function(e) {
        if (!isRecordingVoice) return;
        var remaining = 30 * audioCtx.sampleRate - totalRecordedSamples;
        var copy = new Float32Array(e.inputBuffer.getChannelData(0).subarray(0, remaining));
        recordedChunks.push(copy); totalRecordedSamples += copy.length;
        if (totalRecordedSamples >= 30 * audioCtx.sampleRate) setTimeout(function() { if (isRecordingVoice) stopVoiceRecording(); }, 0);
      };
      stage = "capture_connect";
      audioSource.connect(audioProcessor); audioProcessor.connect(audioCtx.destination);
      fields.recBtn.disabled = false; fields.recBtn.textContent = "⏹ " + label("record_stop"); fields.recBtn.classList.add("is-recording");
      fields.recTimer.hidden = false; fields.recTimer.textContent = "00:00"; recStartTime = Date.now();
      recTimerInterval = setInterval(function() {
        var elapsed = Math.floor((Date.now() - recStartTime) / 1000);
        fields.recTimer.textContent = String(Math.floor(elapsed / 60)).padStart(2, "0") + ":" + String(elapsed % 60).padStart(2, "0");
        if (elapsed >= 30) stopVoiceRecording();
      }, 250);
      status(label("record_running"));
      recordingFeedback("recording");
    } catch (err) {
      if (sequence !== recordingSequence) return;
      recordingDiagnostic(stage, err && err.name);
      releaseRecording();
      var key = stage !== "microphone_request" ? "mic_failed" :
        ["NotAllowedError", "PermissionDeniedError", "SecurityError"].includes(err && err.name) ? "mic_permission" :
        err && err.name === "NotFoundError" ? "mic_missing" : err && err.name === "NotReadableError" ? "mic_busy" : "mic_failed";
      status(label(key));
      recordingFeedback("failed", label(key));
    }
  }
  async function stopVoiceRecording() {
    if (!isRecordingVoice) return;
    var sampleRate = audioCtx && audioCtx.sampleRate;
    var sequence = openSequence, serial = recordingSequence, bound = Object.assign({}, takeTokens);
    releaseRecording();
    if (!sampleRate || totalRecordedSamples < 1000) {
      recordingDiagnostic("capture_complete", "NotReadableError");
      status(label("record_empty"));
      recordingFeedback("failed", label("record_empty"), "record_state_recorded"); return;
    }
    voiceSaving = true; fields.recBtn.disabled = fields.saveVoiceBtn.disabled = true;
    try {
      var wavBytes = window.LixityAudioTake.encodeWav(recordedChunks, totalRecordedSamples, sampleRate);
      recordedChunks = []; totalRecordedSamples = 0;
      var take = await window.LixityAudioTake.create(new Blob([wavBytes], {type:"audio/wav"}),
        {filename:"author-voice.wav", transcript:takeTranscript, transcript_status:takeTranscript ? "draft" : "missing"});
      if (sequence !== openSequence || serial !== recordingSequence || !dialog.open || !matchingTakeContext(bound)) return;
      voiceSaving = false; presentImportedTake(take, bound);
      recordingFeedback("recorded");
      var audio = take.metadata.audio;
      if (audio.sample_rate_hz !== 24000 || audio.duration_seconds < 1 || audio.duration_seconds > 30) {
        recordingDiagnostic("capture_complete", audio.sample_rate_hz !== 24000 ? "NotSupportedError" : "InvalidStateError");
      }
    } catch (error) {
      if (sequence === openSequence && serial === recordingSequence && dialog.open) {
        recordingDiagnostic("capture_complete", error && error.name);
        status(label("take_invalid")); recordingFeedback("failed", label("take_invalid"), "record_state_recorded");
      }
    } finally {
      voiceSaving = false;
      if (sequence === openSequence && dialog.open) { fields.recBtn.disabled = !speechReady; fields.saveVoiceBtn.disabled = !takeValid; }
    }
  }
  function referenceSaved(res) {
    if (!res || !res.reference) return false;
    if (res.activation && res.activation.state === "activated") { location.reload(); return true; }
    // Saving a take and assigning it to a profile are distinct outcomes.
    allReferences = res.references || allReferences;
    renderReferenceList(allReferences); referenceOptions(fields.reference_id.value);
    renderActiveVoiceBadge(); updateVoiceCard();
    status(label("record_saved_not_active"));
    return true;
  }
  function refreshImportedTake(edited) {
    if (!importedTake) return;
    if (edited) fields.take_confirmed.checked = false;
    var text = fields.takeTranscriptInput.value;
    try {
      importedTake = window.LixityAudioTake.withTranscript(importedTake, text,
        fields.take_confirmed.checked ? "confirmed" : text.trim() ? "draft" : "missing");
      var eligibility = window.LixityAudioTake.referenceEligibility(importedTake);
      takeValid = eligibility.eligible;
      fields.takeNotice.textContent = label(eligibility.reason ? "take_" + eligibility.reason : "take_ready");
    } catch (_) { takeValid = false; fields.takeNotice.textContent = label("take_invalid"); }
    fields.takeNotice.hidden = false; fields.saveVoiceBtn.disabled = !takeValid || voiceSaving;
  }
  async function exportVoiceTake(kind) {
    if (!importedTake || isRecordingVoice || recordingPending) return;
    try {
      var text = fields.takeTranscriptInput.value;
      var take = window.LixityAudioTake.withTranscript(importedTake, text,
        fields.take_confirmed.checked ? "confirmed" : text.trim() ? "draft" : "missing");
      await window.LixityAudioTake.download(take, kind);
    } catch (_) { status(label("take_export_failed")); }
  }
  function presentImportedTake(take, bound) {
    if (isRecordingVoice || recordingPending || voiceSaving) return;
    fields.audio.pause(); fields.takePlayer.pause();
    var nextUrl = URL.createObjectURL(take.blob);
    if (takeUrl) URL.revokeObjectURL(takeUrl);
    takeUrl = nextUrl; importedTake = take; takeTokens = Object.assign({}, bound);
    lastRecordedWavBlob = take.blob; fields.takePlayer.src = takeUrl;
    fields.takePlayer.hidden = false; fields.takeWidget.refresh();
    var audio = take.metadata.audio;
    fields.takeStats.textContent = label("audit_duration") + ": " + audio.duration_seconds.toFixed(1) + " s · " + audio.sample_rate_hz + " Hz · " + audio.channels + " ch · " + audio.sample_width_bits + "-bit PCM";
    fields.takeTranscriptInput.value = take.transcript;
    fields.takeTranscriptInput.closest("details").open = true;
    fields.take_confirmed.closest("label").hidden = false;
    fields.take_confirmed.checked = take.transcript_status === "confirmed";
    fields.takeCard.hidden = false; fields.takeExports.hidden = false; refreshImportedTake(false);
    status(label("take_loaded"));
  }
  function matchingTakeContext(bound) {
    var current = tokens();
    return bound && bound.project_token === current.project_token && bound.source_sha256 === current.source_sha256;
  }
  async function receiveTake(detail) {
    if (!matchingTakeContext(detail.context)) return;
    var serial = ++takeImportSequence, bound = Object.assign({}, detail.context);
    try {
      var take = await window.LixityAudioTake.validate(detail.take);
      if (serial !== takeImportSequence || !matchingTakeContext(bound)) return;
      if (dialog && dialog.open) {
        if (profileSaving || voiceSaving || isRecordingVoice || recordingPending || !switchMode("reference")) return;
      } else await open("reference");
      if (serial !== takeImportSequence || !matchingTakeContext(bound) || !dialog.open || !speechReady) return;
      presentImportedTake(take, bound);
    } catch (_) { if (dialog && dialog.open && matchingTakeContext(bound)) status(label("take_invalid")); }
  }
  async function saveVoiceTake() {
    if (!lastRecordedWavBlob || !takeValid || voiceSaving) return;
    if (!matchingTakeContext(takeTokens)) { status(label("take_context")); return; }
    if (importedTake) { refreshImportedTake(false); if (!takeValid) return; }
    var savedBlob = lastRecordedWavBlob, spoken = fields.takeTranscriptInput.value.trim(), sequence = openSequence, captureContext = context();
    var bound = Object.assign({}, takeTokens);
    voiceSaving = true; fields.recBtn.disabled = true;
    if (fields.saveVoiceBtn) fields.saveVoiceBtn.disabled = true;
    status(label("saving"));
    try {
      var reader = new FileReader();
      var b64Wav = await new Promise(function(resolve, reject) {
        reader.onload = function() { resolve(String(reader.result).split(",")[1]); };
        reader.onerror = reject;
        reader.readAsDataURL(savedBlob);
      });
      if (sequence !== openSequence || !dialog.open || captureContext !== context()) return;
      if (!spoken) throw new Error(label("transcript_help"));
      var res = await request("audio-microphone", Object.assign({}, bound, {
        action: "save_reference",
        audio: b64Wav,
        transcript: spoken,
        profile_id: (settings && settings.selected) || "default"
      }));
      if (sequence !== openSequence || !dialog.open || captureContext !== context()) return;
      if (referenceSaved(res)) {
        lastRecordedWavBlob = null; importedTake = null; takeTokens = null; takeValid = false;
        fields.takeExports.hidden = true;
        fields.take_confirmed.closest("label").hidden = fields.takeNotice.hidden = true;
      }
    } catch (err) { if (sequence === openSequence && dialog.open && captureContext === context()) status(err.message); }
    finally {
      voiceSaving = false;
      if (sequence === openSequence && dialog.open) { fields.recBtn.disabled = !speechReady; if (fields.saveVoiceBtn) fields.saveVoiceBtn.disabled = !takeValid; }
    }
  }
  function switchMode(newMode, initializing) {
    if (newMode === mode && !initializing) return true;
    if (profileSaving || voiceSaving || (direction && direction.busy())) return false;
    if (mode === "profiles" && (pronunciationPending() || profilesDirty)) {
      status(label(pronunciationPending() ? "pronunciation_pending" : "profiles_unsaved"));
      return;
    }
    if (direction && direction.dirty() && newMode !== mode && !(newMode === "output" && mode === "reader" && fields.ignore_direction.checked)) { status(label("direction_switch_first")); return; }
    if (newMode !== "reference" && (isRecordingVoice || recordingPending)) {
      ++recordingSequence;
      if (isRecordingVoice) stopVoiceRecording(); else releaseRecording();
    }
    fields.audio.pause(); fields.takePlayer.pause();
    mode = newMode;
    if (fields.tabs) {
      Object.keys(fields.tabs).forEach(function(k) {
        if (fields.tabs[k]) {
          var active = k === mode || (mode === "output" && k === "reader");
          fields.tabs[k].classList.toggle("active", active);
          fields.tabs[k].setAttribute("aria-selected", String(active));
          fields.tabs[k].tabIndex = active ? 0 : -1;
          if (active) fields.panel.setAttribute("aria-labelledby", fields.tabs[k].id);
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
    fields.target.closest("label").hidden = mode !== "profiles" || fields.target.disabled;
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
      fields.microphone_section.hidden = mode !== "microphone";
      if (mode === "microphone") fields.microphone_section.open = true;
    }
    arrangeSections();
    refreshChapterAudio();
    if (mode === "reference") renderActiveVoiceBadge();
    fields.panel.scrollTop = 0;
    status(speechLoadMessage);
    return true;
  }
  function build() {
    dialog = node("dialog", body, "lixity-modal"); dialog.id = "modal-speech"; dialog.setAttribute("aria-labelledby", "speech-title");
    var card = node("div", dialog, "modal-card"), header = node("div", card, "modal-header");
    fields.heading = node("h3", header, "", label("title")); fields.heading.id = "speech-title";
    var close = button(header, "close", function() {
      if (profileSaving || voiceSaving) { status(label("saving")); return; }
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
    fields.status = node("p", card, "ctl-status modal-intro"); fields.status.id = "speech-status"; fields.status.setAttribute("role", "status"); fields.status.setAttribute("aria-live", "polite");
    var content = node("div", card, "modal-body"); fields.panel = content;
    content.id = "speech-panel"; content.setAttribute("role", "tabpanel");
    tabsBar.setAttribute("aria-label", label("action_title"));
    Object.keys(fields.tabs).forEach(function(key) {
      var tab = fields.tabs[key]; tab.id = "speech-tab-" + key; tab.setAttribute("role", "tab"); tab.setAttribute("aria-controls", content.id);
      tab.addEventListener("keydown", function(event) {
        var keys = Object.keys(fields.tabs), index = keys.indexOf(key), target;
        if (event.key === "ArrowRight") target = keys[(index + 1) % keys.length];
        if (event.key === "ArrowLeft") target = keys[(index + keys.length - 1) % keys.length];
        if (event.key === "Home") target = keys[0]; if (event.key === "End") target = keys[keys.length - 1];
        if (target) { event.preventDefault(); switchMode(target); if (mode === target) fields.tabs[target].focus(); }
      });
    });

    fields.reference_section = node("div", content, "author-voice-studio");
    fields.reference_section.hidden = true;
    var introCard = node("div", fields.reference_section, "voice-studio-intro");
    node("p", introCard, "ctl-note", label("record_author_intro") || "Nimm eine 15–25-sekündige Sprachprobe auf. Sie dient als Stimmreferenz für den KI-Sprecher dieses Buchs.");
    fields.active_voice_badge = node("div", fields.reference_section, "voice-active-card");
    var textCard = node("div", fields.reference_section, "voice-reading-card");
    var textHeader = node("div", textCard, "voice-reading-header");
    fields.promptLabel = node("span", textHeader, "voice-reading-label");
    var sampleSwitcher = node("div", textHeader, "segmented-buttons");
    var btnFull = node("button", sampleSwitcher, "seg-btn active", label("sample_full"));
    var btnShort = node("button", sampleSwitcher, "seg-btn", label("sample_short"));
    var btnCustom = node("button", sampleSwitcher, "seg-btn", label("sample_custom"));
    btnFull.type = btnShort.type = btnCustom.type = "button";
    var promptBox = node("div", textCard, "voice-prompt-box");
    fields.promptText = node("p", promptBox, "voice-prompt-text");
    fields.customTextarea = node("textarea", promptBox, "ctl voice-custom-text");
    fields.customTextarea.rows = 4;
    fields.customTextarea.hidden = true;
    function updatePromptText() {
      fields.promptLabel.textContent = label("sample_" + (sampleVariant === "phonetic" ? "full" : sampleVariant));
      [btnFull, btnShort, btnCustom].forEach(function(el, index) {
        var selected = ["phonetic", "short", "custom"][index] === sampleVariant;
        el.setAttribute("aria-pressed", String(selected)); el.classList.toggle("active", selected);
      });
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
    fields.updatePromptText = updatePromptText;
    fields.promptControls = [btnFull, btnShort, btnCustom, fields.customTextarea];
    fields.customTextarea.setAttribute("aria-label", label("sample_custom"));
    fields.promptControls.forEach(function(el) { el.dataset.help = label("transcript_help"); });
    updatePromptText();
    var recControls = node("div", fields.reference_section, "voice-record-controls");
    fields.recBtn = node("button", recControls, "ctl voice-rec-btn", "🎙 " + (label("record_start") || "Aufnahme starten"));
    fields.recBtn.type = "button"; addHelp(fields.recBtn, "record_start");
    fields.recTimer = node("span", recControls, "voice-rec-timer", "00:00");
    fields.recTimer.hidden = true;
    fields.recState = node("span", recControls, "voice-record-state");
    fields.recState.setAttribute("role", "status"); fields.recState.setAttribute("aria-live", "polite"); fields.recState.hidden = true;
    fields.recError = node("p", fields.reference_section, "voice-record-error");
    fields.recError.id = "speech-record-error"; fields.recError.hidden = true;
    fields.takeCard = node("div", fields.reference_section, "voice-take-card");
    fields.takeCard.hidden = true;
    fields.takePlayer = node("audio", fields.takeCard, "media-player");
    fields.takePlayer.controls = true; fields.takeWidget = window.createSpeechPlayer(fields.takePlayer, {label: label, onError: status});
    fields.takeStats = node("div", fields.takeCard, "voice-take-stats");
    var takeTranscriptSection = node("details", fields.takeCard, "settings-section");
    node("summary", takeTranscriptSection, "", label("upload_voice_transcript"));
    node("p", takeTranscriptSection, "ctl-note", label("transcript_help"));
    fields.takeTranscriptInput = node("textarea", takeTranscriptSection, "ctl");
    fields.takeTranscriptInput.rows = 3; fields.takeTranscriptInput.setAttribute("aria-label", label("upload_voice_transcript"));
    fields.takeTranscriptInput.dataset.help = label("transcript_help");
    fields.take_confirmed = window.LixityComponents.createField(takeTranscriptSection,
      {label:label("take_confirmed"), type:"checkbox", id:"speech-take_confirmed"});
    fields.take_confirmed.closest("label").hidden = true;
    fields.take_confirmed.addEventListener("change", function() { refreshImportedTake(false); });
    fields.takeTranscriptInput.addEventListener("input", function() { refreshImportedTake(true); });
    fields.takeNotice = node("p", fields.takeCard, "ctl-note"); fields.takeNotice.id = "speech-take-notice"; fields.takeNotice.hidden = true;
    fields.take_confirmed.setAttribute("aria-describedby", fields.takeNotice.id);
    fields.takeExports = node("div", fields.takeCard, "row"); fields.takeExports.hidden = true;
    button(fields.takeExports, "take_download_wav", function() { exportVoiceTake("wav"); });
    button(fields.takeExports, "take_download_json", function() { exportVoiceTake("json"); });
    fields.saveVoiceBtn = node("button", fields.takeCard, "ctl primary voice-save-btn", "💾 " + (label("record_save") || "Als Autorenstimme für dieses Buch speichern"));
    fields.saveVoiceBtn.type = "button"; addHelp(fields.saveVoiceBtn, "record_save");
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
    uploadTranscript.placeholder = label("transcript_help");
    var uploadMetadata = field(uploadSec, "take_metadata_file", "file"); uploadMetadata.accept = ".json,application/json";
    node("p", uploadSec, "ctl-note", label("take_import_help"));
    var uploadBtn = button(uploadSec, "take_import", async function() {
      var file = uploadFile.files && uploadFile.files[0];
      var text = uploadTranscript.value, metadata = uploadMetadata.files && uploadMetadata.files[0];
      if (!file) { status(label("take_invalid")); return; }
      if (voiceSaving || isRecordingVoice || recordingPending) return;
      var sequence = openSequence, captureContext = context(), bound = tokens();
      voiceSaving = true; fields.recBtn.disabled = true;
      uploadBtn.disabled = true; status(label("saving"));
      try {
        var take = metadata ? await window.LixityAudioTake.importFiles(file, metadata) :
          await window.LixityAudioTake.create(file, {filename:file.name, transcript:text, transcript_status:text.trim() ? "draft" : "missing"});
        if (sequence !== openSequence || !dialog.open || captureContext !== context()) return;
        voiceSaving = false; presentImportedTake(take, bound);
      } catch (_) { if (sequence === openSequence && dialog.open && captureContext === context()) status(label("take_invalid")); }
      finally {
        voiceSaving = false;
        if (sequence === openSequence && dialog.open) { uploadBtn.disabled = false; fields.recBtn.disabled = !speechReady; }
      }
    });

    fields.profile_row = node("div", content, "row"); field(fields.profile_row, "profile", "select"); fields.create = button(fields.profile_row, "create", create);
    fields.remove_profile = button(fields.profile_row, "remove_profile", removeProfile);
    fields.schema_hint = node("p", content, "ctl-note", label("schema_hint"));
    fields.schema_review = node("p", content, "ctl-note"); fields.schema_review.id = "speech-schema-review"; fields.schema_review.hidden = true;
    fields.schema_preview = button(content, "schema_preview", async function() {
      var sequence = openSequence; fields.schema_preview.disabled = true;
      try {
        var result = await request("audio-schema", Object.assign(tokens(), {apply: false, schema_version: currentAudioSchema}));
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
        await request("audio-schema", Object.assign(tokens(), {apply: true, snapshot: fields.schema_apply.dataset.snapshot, schema_version: currentAudioSchema}));
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
    field(grid, "supports_instructions", "checkbox").addEventListener("change", voiceControls);
    fields.engine.setAttribute("aria-describedby", "speech-model-hint speech-worker-status");
    fields.model_conflict = node("p", fields.editor, "ctl-note"); fields.model_conflict.setAttribute("aria-live", "polite"); fields.model_conflict.hidden = true;
    fields.voice_hint = node("p", fields.editor, "ctl-note", label("voice_hint"));
    field(fields.editor, "voice_description", "textarea").maxLength = 2000;
    fields.design_hint = node("p", fields.editor, "ctl-note", label("design_hint"));
    fields.design_hint.id = "speech-design-hint"; fields.voice_description.setAttribute("aria-describedby", fields.design_hint.id);
    var reference = field(fields.editor, "reference_id", "select");
    fields.reference_hint = node("p", fields.editor, "ctl-note", label("reference_hint"));
    fields.reference_hint.id = "speech-reference-hint"; reference.setAttribute("aria-describedby", fields.reference_hint.id);
    fields.profile_voice_card = node("div", fields.editor, "voice-active-card");
    fields.profile_voice_card.hidden = true;
    var speed = field(grid, "speed", "number"); speed.step = "any"; speed.required = true;
    var speedHint = node("span", speed.closest("label"), "ctl-note", label("speed_hint"));
    speedHint.id = "speech-speed-hint"; speed.setAttribute("aria-describedby", speedHint.id);
    ["paragraph_pause", "scene_pause"].forEach(function(key) { var el = field(grid, key, "number"); el.min = "0"; el.max = "10"; el.step = "any"; el.required = true; });
    field(fields.editor, "instructions", "textarea").maxLength = 2000;
    fields.instructions_note = node("p", fields.editor, "ctl-note", label("instructions_export_only"));
    fields.instructions_note.id = "speech-instructions-note";
    fields.instructions.setAttribute("aria-describedby", fields.instructions_note.id);
    profileProsody = createProsody(fields.editor, "prosody-", function() { profilesDirty = true; invalidate(); }, false);
    [fields.voice_description, fields.reference_id, fields.instructions].forEach(function(input) {
      input.addEventListener("input", function() { updateModelFields(); updateVoiceCard(); });
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
    fields.phonemes_section = node("details", fields.editor, "settings-section"); fields.phonemes_section.id = "speech-phonemes-section";
    node("summary", fields.phonemes_section, "", label("phonemes"));
    field(fields.phonemes_section, "phonemes", "textarea").rows = 5;
    fields.phonemes.placeholder = "Vogel=ˈfoːɡəl";
    var phonemeHelp = node("p", fields.phonemes_section, "ctl-note", label("phonemes_help"));
    phonemeHelp.id = "speech-phonemes-help"; fields.phonemes.setAttribute("aria-describedby", phonemeHelp.id);
    fields.phonemes.addEventListener("input", updateModelFields);
    field(content, "chapter", "select");
    direction = window.LixitySpeechDirection(content, {
      node:node, field:field, button:button, options:options, label:label, request:request,
      status:status, invalidate:invalidate, tokens:tokens, createProsody:createProsody,
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
    field(fields.microphone_section, "microphone_device", "select");
    var micGainField = node("div", fields.microphone_section, "setting-field");
    var micGainLabel = node("span", micGainField, "form-label", label("microphone_gain"));
    micGainLabel.id = "speech-microphone-gain-label";
    var micGainRow = node("div", micGainField, "row");
    fields.microphone_gain_range = node("input", micGainRow, "ctl");
    fields.microphone_gain_range.type = "range"; fields.microphone_gain_range.hidden = true;
    fields.microphone_gain = node("input", micGainRow, "ctl");
    fields.microphone_gain.type = "number"; fields.microphone_gain.step = "1"; fields.microphone_gain.required = true;
    [fields.microphone_gain_range, fields.microphone_gain].forEach(function(input) { input.setAttribute("aria-labelledby", micGainLabel.id); });
    fields.microphone_gain.style.width = "5rem";
    fields.microphone_gain_info = node("span", micGainRow, "ctl-note");
    fields.microphone_gain_info.id = "speech-microphone-gain-info";
    [fields.microphone_gain_range, fields.microphone_gain].forEach(function(input) { input.setAttribute("aria-describedby", fields.microphone_gain_info.id); });
    fields.microphone_device.addEventListener("change", showMicrophoneGain);
    fields.microphone_gain_range.addEventListener("input", function() { fields.microphone_gain.value = fields.microphone_gain_range.value; });
    fields.microphone_gain.addEventListener("input", function() { fields.microphone_gain_range.value = fields.microphone_gain.value; });
    fields.microphone_set_btn = button(fields.microphone_section, "microphone_set_gain", async function() {
      var mixer = microphoneMixer();
      if (microphoneBusy || !mixer || mixer.max > 100 || !fields.microphone_gain.reportValidity()) return;
      var g = Number(fields.microphone_gain.value), sequence = openSequence, device = fields.microphone_device.value;
      microphoneBusy = true; microphoneControls();
      try {
        var res = await request("audio-microphone", {action: "set_gain", gain: g, card:mixer.card, control:mixer.control});
        if (sequence !== openSequence || !dialog.open || context() !== openedContext) return;
        populateMicrophone(res, device);
        status(microphoneMixer() ? uiFormat("speech_microphone_gain_set", {gain:res.current_gain}) : label("microphone_gain_unknown"));
      } catch (err) { if (sequence === openSequence && dialog.open) status(err.message); }
      finally { if (sequence === openSequence) { microphoneBusy = false; microphoneControls(); } }
    });
    var micCalibActions = node("div", fields.microphone_section, "row");
    fields.microphone_calib_btn = button(micCalibActions, "microphone_calibrate", async function() {
      if (microphoneBusy || !microphoneState || !fields.microphone_device.value) return;
      var sequence = openSequence, mixer = microphoneMixer(), dev = fields.microphone_device.value;
      microphoneBusy = true; microphoneControls(); fields.microphone_calib_result.replaceChildren();
      var prepNote = node("p", fields.microphone_calib_result, "ctl-note", "4s Vorlauf... Danach 3× POPP, 2× Klatschen, 1× Sprechen.");
      status("Kalibriere Mikrofonpegel...");
      try {
        // Measure the selected device at its current level. The calibration API's
        // optional gain targets its default mixer, which may be another card.
        var res = await request("audio-microphone", {action: "calibrate", device: dev});
        if (sequence !== openSequence || !dialog.open || context() !== openedContext) return;
        prepNote.remove();
        if (res && res.calibration) {
          var cal = res.calibration;
          var card = node("div", fields.microphone_calib_result, "audit-summary");
          var vBadge = node("div", card, "badge", cal.verdict_label);
          if (cal.verdict === "too_hot") vBadge.classList.add("badge-fail");
          else if (cal.verdict === "calibrated") vBadge.classList.add("badge-pass");
          else vBadge.classList.add("badge-warn");
          node("p", card, "", "Peak: " + (cal.peak_dbfs >= 0 ? "+" : "") + cal.peak_dbfs.toFixed(1) + " dBFS · Clipping: " + cal.clipping_samples + " · Rauschabstand (SNR): " + cal.snr_db.toFixed(1) + " dB");
          // Recommendations currently use the backend's default card/Mic gain.
          if (mixer && mixer.max <= 100 && String(mixer.card) === "1" && mixer.control === "Mic" && Number.isInteger(cal.recommended_gain) &&
              cal.recommended_gain >= mixer.min && cal.recommended_gain <= mixer.max && cal.recommended_gain !== microphoneState.current_gain) {
            var recBtn = node("button", card, "ctl", "Empfohlenen Gain " + cal.recommended_gain + " anwenden");
            recBtn.type = "button";
            recBtn.addEventListener("click", function() {
              fields.microphone_gain.value = fields.microphone_gain_range.value = String(cal.recommended_gain);
              fields.microphone_set_btn.click();
            });
          }
          status("Kalibrierung abgeschlossen.");
        }
      } catch (err) { if (sequence === openSequence && dialog.open) status(err.message); }
      finally { if (sequence === openSequence) { microphoneBusy = false; microphoneControls(); } }
    });
    fields.microphone_calib_result = node("div", fields.microphone_section, "audio-calib-result");
    fields.chapter_render = button(actions, "chapter_render", function() { render("chapter"); });
    fields.open_output = button(actions, "output_title", function() {
      if (direction.dirty() && !fields.ignore_direction.checked) { status(label("direction_save_first")); return; }
      if (!switchMode("output")) return; invalidate();
      direction.section.hidden = !direction.dirty(); fields.direction_plan.hidden = false; fields.export_scope.value = "chapter";
      fields.open_output.hidden = true; fields.chapter_render.hidden = !canRender;
      fields.reuseLabel.hidden = !canRender;
      arrangeSections();
    });
    fields.open_output.textContent = label("open_output");
    fields.cancel = button(actions, "cancel", cancel); fields.cancel.disabled = true;
    fields.context = node("p", content, "ctl-note"); fields.progress = node("progress", content); fields.progress.hidden = true; fields.progress.setAttribute("aria-label", label("progress"));
    fields.playback_section = node("div", content, "speech-playback");
    fields.audio = node("audio", fields.playback_section, "media-player"); fields.audio.id = "speech-audio-player"; fields.audio.controls = true; fields.audio.hidden = true;
    fields.audioWidget = window.createSpeechPlayer(fields.audio, {label: label, onError: status});
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
    fields.chapter_audio_section = node("fieldset", content, "settings-section");
    node("legend", fields.chapter_audio_section, "", label("chapter_audio_title"));
    field(fields.chapter_audio_section, "chapter_audio_file", "file").accept = ".wav,audio/wav";
    fields.chapter_audio_file.required = true;
    fields.chapter_audio_file.dataset.help = label("chapter_audio_hint");
    var chapterActions = node("div", fields.chapter_audio_section, "row");
    fields.chapter_audio_import = button(chapterActions, "chapter_audio_import", importChapterAudio);
    fields.chapter_audio_import.dataset.help = label("chapter_audio_hint");
    fields.chapter_audio_status = node("p", fields.chapter_audio_section, "ctl-note");
    fields.chapter_audio_status.id = "speech-chapter-audio-status";
    fields.chapter_audio_status.setAttribute("role", "status");
    fields.service_section = node("fieldset", content, "settings-section speech-service-section");
    node("legend", fields.service_section, "", label("service_title"));
    fields.service_section.append(fields.target.closest("label"), fields.worker_status, fields.worker_guide, fields.worker_refresh);
    fields.render_section.append(fields.runtime_hint, reuse, actions, fields.context, fields.progress);
    fields.playback_section.append(fields.player_controls, fields.download);
    fields.profile_row.after(fields.editor, fields.service_section, fields.save, fields.profile_discard);
    fields.audit_section.before(fields.render_section, fields.export_section);
    fields.export_section.after(fields.chapter_audio_section);
    content.append(fields.playback_section);
    arrangeSections();
    fields.reuseLabel = reuse;
    fields.editor.addEventListener("input", function(event) {
      if (mode === "profiles" && ![fields.pronunciation_search, fields.pronunciation_term, fields.pronunciation_spoken].includes(event.target)) profilesDirty = true;
      invalidate();
    });
    fields.engine.addEventListener("change", function() {
      if (profileCapability().voices[fields.voice.value]) lastPreset = fields.voice.value;
      var cap = capabilities[fields.engine.value];
      if (cap.languages.length && !cap.languages.includes(fields.language.value)) options(fields.language, [[cap.languages[0], languageName(cap.languages[0])]], cap.languages[0]);
      var voice = cap.voice_design ? "design" : cap.reference_required ? "reference" : cap.voices[lastPreset] ? lastPreset : Object.keys(cap.voices)[0] || "";
      options(fields.voice, [], voice);
      voiceControls(); invalidate();
    });
    fields.language.addEventListener("change", function() { fields.voice.value = ""; voiceControls(); status(label("voice_changed")); });
    fields.profile.addEventListener("change", function() {
      try { stash(); if (settings.selected !== fields.profile.value) profilesDirty = true; settings.selected = fields.profile.value; loadProfile(); }
      catch (error) { fields.profile.value = settings.selected; status(error.message); }
    });
    fields.chapter.addEventListener("change", function() { paragraph = null; invalidate(); var select=fields.direction_passage; var choice=Array.from(select.options).find(function(o) { return o.textContent.startsWith(fields.chapter.value + " · "); }); if (choice) { select.value=choice.value; select.dispatchEvent(new Event("change")); } fields.context.textContent = label("first_preview"); });
    fields.chapter.addEventListener("change", showChapterAudio);
    dialog.addEventListener("cancel", function(event) {
      if (profileSaving || voiceSaving) { event.preventDefault(); status(label("saving")); }
      else if (direction.busy() || direction.dirty()) {
        event.preventDefault(); status(label(direction.busy() ? "saving" : "direction_switch_first"));
      } else if (mode === "profiles" && pronunciationPending()) {
        event.preventDefault(); status(label("pronunciation_pending"));
      } else if (mode === "profiles" && profilesDirty) {
        event.preventDefault(); status(label("profiles_unsaved"));
      }
    });
    [fields.microphone_device, fields.microphone_gain, fields.microphone_gain_range, fields.microphone_set_btn, fields.microphone_calib_btn].forEach(function(el) { el.dataset.help = label("microphone_help"); });
    fields.microphone_device.setAttribute("aria-label", label("microphone_device"));
    fields.microphone_gain.setAttribute("aria-label", label("microphone_gain"));
    fields.microphone_gain_range.setAttribute("aria-label", label("microphone_gain"));
    fields.ignore_direction.dataset.help = label("ignore_help"); fields.reuse.dataset.help = label("reuse_help");
    dialog.addEventListener("close", function() {
      speechReady = false;
      ++takeImportSequence; importedTake = null; takeTokens = null;
      ++recordingSequence; releaseRecording(); fields.takePlayer.pause();
      recordedChunks = []; totalRecordedSamples = 0; lastRecordedWavBlob = null; takeValid = false;
      fields.takePlayer.removeAttribute("src"); fields.takePlayer.load(); fields.takeCard.hidden = true;
      if (takeUrl) { URL.revokeObjectURL(takeUrl); takeUrl = null; }
      invalidate();
    });
  }
  async function open(entry) {
    mode = entry || "reference";
    speechReady = false; speechLoadMessage = label("loading");
    ++openSequence;
    var fromReader = mode === "reader";
    var readerControl = document.getElementById("reader-chapter");
    var readerChapterIntent = fromReader && readerControl ? (readerControl.value || readerControl.dataset.currentChapter || "") : "";
    if (!dialog) build(); invalidate(); direction.disable(); settings = null; savedSettings = null; workers = null; profilesDirty = false; profileSaving = false; openedContext = context(); paragraph = null;
    chapterAudio = null; chapterAudioBusy = false; ++chapterAudioSequence;
    fields.chapter_audio_import.disabled = fields.chapter_audio_file.disabled = true;
    fields.chapter_audio_file.value = ""; fields.chapter.disabled = false;
    fields.chapter_audio_status.textContent = label("loading");
    microphoneBusy = false; populateMicrophone(null);
    fields.worker_status.textContent = label("loading"); fields.worker_refresh.disabled = true; fields.model.textContent = "";
    fields.profile.disabled = false;
    fields.recBtn.disabled = true; fields.reference_section.inert = true;
    recordingFeedback("idle");
    fields.reference_section.setAttribute("aria-busy", "true");
    switchMode(mode, true);
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
    ["profile", "engine", "language", "voice", "reference_id", "chapter"].forEach(function(key) { fields[key].replaceChildren(); });
    dialog.showModal(); status(label("loading")); fields.editor.disabled = true; fields.save.disabled = fields.create.disabled = fields.preview.disabled = fields.chapter_render.disabled = true;
    var serial = generation;
    try {
      var data = await request("speech"); if (!valid(serial)) return;
      migrationRequired = data.requires_migration === true;
      settings = data.settings || {schema_version: "lixity-audio-settings/1", selected: "", profiles: {}}; capabilities = data.capabilities; workers = data.workers;
      allReferences = data.references || [];
      renderReferenceList(allReferences);
      if (data.calibration_texts) {
        calibrationTexts = data.calibration_texts; fields.updatePromptText();
      }
      renderActiveVoiceBadge();
      populateMicrophone(data.microphone || null);
      if (mode === "microphone" && fields.microphone_section) fields.microphone_section.open = true;
      fields.schema_hint.hidden = fields.schema_preview.hidden = mode !== "profiles" || settings.schema_version === currentAudioSchema || migrationRequired;
      fields.schema_apply.hidden = true; fields.schema_apply.disabled = false;
      fields.worker_refresh.disabled = false;
      savedSettings = JSON.parse(JSON.stringify(settings));
      fields.model.textContent = "";
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
      fields.target.closest("label").hidden = mode !== "profiles" || fields.target.disabled;
      fields.reuseLabel.hidden = mode !== "output" || !canRender;
      savedDirectionView = data.direction || null;
      if (data.direction) {
        var initialPassage = paragraph ? {anchor:paragraph.identity} : data.direction.passages.find(function(p) { return p.chapter === Number(fields.chapter.value); });
        direction.open(data.direction, initialPassage && initialPassage.anchor, settings.profiles);
      }
      if (migrationRequired) direction.disable();
      arrangeSections();
      speechReady = true; fields.recBtn.disabled = false; fields.reference_section.inert = false;
      fields.chapter_audio_import.disabled = fields.chapter_audio_file.disabled = false;
      refreshChapterAudio();
      recordingFeedback("idle");
      fields.reference_section.setAttribute("aria-busy", "false");
      speechLoadMessage = data.configuration_error || "";
      status(speechLoadMessage); fields.save.disabled = migrationRequired || !settings.selected;
      fields.context.textContent = label(paragraph ? "paragraph_preview" : "first_preview");
    } catch (error) {
      if (valid(serial)) {
        fields.worker_status.textContent = uiFormat("speech_worker_unknown", {target: label("target_" + (fields.target.value || "local"))});
        speechLoadMessage = error.message;
        fields.reference_section.setAttribute("aria-busy", "false");
        status(speechLoadMessage);
      }
    }
  }
  var audioActions = document.getElementById("project-audio-settings-actions");
  button(audioActions, "record_author_title", function() { open("reference"); }).id = "btn-project-record-voice";
  button(audioActions, "profiles_title", function() { open("profiles"); }).id = "settings-speech";
  button(audioActions, "output_title", function() { open("output"); }).id = "settings-speech-output";
  button(audioActions, "microphone_title", function() { open("microphone"); }).id = "settings-speech-mic";
  var runtimeAction = document.getElementById("runtime-open");
  if (runtimeAction) audioActions.appendChild(runtimeAction);
  var toolbar = document.getElementById("manuscript-reader-controls");
  if (toolbar) {
    var existingSpeech = toolbar.querySelector("#reader-speech");
    var readerSpeech = existingSpeech || button(toolbar, "reader_title", function() { open("reader"); });
    readerSpeech.id = "reader-speech";
    readerSpeech.className = "ctl reader-compact-control";
    readerSpeech.innerHTML = '<span class="reader-control-icon" aria-hidden="true">🎙</span> <span class="reader-control-label">' + label("reader_title") + '</span>';
    readerSpeech.dataset.help = label(canRender ? "reader_help" : "reader_help_plan");
    var anchor = toolbar.querySelector(".reader-analysis-toggle-controls") ||
                 toolbar.querySelector("#workbench-overview-open") ||
                 toolbar.querySelector("#reader-analysis-settings");
    if (anchor && readerSpeech.nextSibling !== anchor) {
      toolbar.insertBefore(readerSpeech, anchor);
    }
  }
  document.addEventListener("lixity:open-speech-studio", function(e) {
    if (e && e.detail && e.detail.take) { receiveTake(e.detail); return; }
    var targetMode = (e && e.detail && e.detail.mode) || "reference";
    open(targetMode);
  });
  document.addEventListener("lixity:workbench-change", function() {
    if (!dialog || !dialog.open) return;
    if (profileSaving || voiceSaving) { status(label("saving")); return; }
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
