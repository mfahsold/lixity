/* Project-local listening drafts share one token-bound native dialog. */
(function() {
  "use strict";
  var body = document.body, settingsForm = document.getElementById("settings-form");
  if (body.dataset.speechCapable !== "true" || body.dataset.readOnly === "true" || !settingsForm) return;
  var canRender = body.dataset.speechRenderCapable === "true", referenceFormat = null, referenceRecording = null;
  var dialog, fields = {}, settings, capabilities, workers, generation = 0, openSequence = 0, job = null, timer, openedContext, paragraph;
  var migrationRequired = false, profileSettingsAvailable = false, schemaReviewAvailable = false;
  var direction, savedDirectionView, lastPreset = "", mode = "reference", editingPronunciation = null;
  var surfaces = {
    reference: {tab: "reference", icon: "mic", label: "tab_voice", title: "record_author_title", playbackAfter: "active_voice_badge"},
    profiles: {tab: "profiles", icon: "sliders", label: "tab_profiles", title: "profiles_title", playbackAfter: "profile_voice_card"},
    microphone: {tab: "microphone", icon: "volume-2", label: "tab_microphone", title: "microphone_title"},
    reader: {tab: "direction", icon: "headphones", label: "tab_reader", title: "reader_title", playbackAfter: "render_section", manuscript: true},
    output: {tab: "output", icon: "file-text", label: "chapter_output", title: "chapter_output", playbackAfter: "render_section", manuscript: true}
  };
  var savedSettings = null, profilesDirty = false, profileSaving = false, auditAudioUrl = null, generatedAudio = null;
  var speechReady = false, speechLoadMessage = "";
  var specialPronunciations = Object.create(null);
  var pronunciationScope = "profile";
  var profileProsody;
  var currentAudioSchema = "lixity-audio-settings/5";
  var allReferences = [], calibrationTexts = null, profileConstraints = null;
  var microphoneState = null, microphoneBusy = false, microphoneRefreshing = false, preferredMicrophone = "";
  var chapterAudio = null, chapterAudioBusy = false, chapterAudioSequence = 0;
  var audioStream = null, audioCtx = null, audioSource = null, audioProcessor = null, recordedChunks = [], totalRecordedSamples = 0;
  var recTimerInterval = null, isRecordingVoice = false, desktopAudioRecording = false, lastRecordedWavBlob = null, sampleVariant = "short";

  var importedTake = null, takeTokens = null, takeImportSequence = 0;
  var trimLimitSeconds = 0, trimSource = null;
  var speechLayout = document.getElementById("workspace-reader-layout"), narrowSpeech = matchMedia("(max-width: 900px)");
  var speechDocked = false, placingSpeech = false, speechPassage = null, speechOpener = null;
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
    var event = {preflight: "recording_preflight_failed", capture_processor_runtime: "recording_capture_failed",
      capture_complete: "recording_finish_failed"}[stage] || "recording_start_failed";
    window.LixityLog?.audioClient?.(event);
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
  function readReferenceFormat(value) {
    if (!value || !["sample_rate_hz", "channels", "sample_width_bits", "min_seconds", "max_seconds", "max_transcript_chars", "max_bytes"].every(function(key) {
      return Number.isSafeInteger(value[key]) && value[key] > 0;
    }) || value.min_seconds > value.max_seconds || value.channels !== 1 || value.sample_width_bits !== 16) return null;
    return value;
  }
  function referenceText(key) {
    return uiFormat("speech_" + key, {min:referenceFormat.min_seconds, max:referenceFormat.max_seconds,
      characters:new Intl.NumberFormat(document.documentElement.lang).format(referenceFormat.max_transcript_chars)});
  }
  function readReferenceRecording(value) {
    if (!referenceFormat || !value) return null;
    function secondsInRange(seconds) {
      return Number.isSafeInteger(seconds) && seconds >= referenceFormat.min_seconds && seconds <= referenceFormat.max_seconds;
    }
    if (!secondsInRange(value.default_seconds) ||
        (value.duration_seconds !== null && !secondsInRange(value.duration_seconds)) ||
        (value.reference_seconds !== null && !secondsInRange(value.reference_seconds)) ||
        typeof value.configuration_error !== "string") return null;
    return value;
  }
  function canRecordVoice() { return speechReady && openedContext === context() && Boolean(referenceRecording?.duration_seconds); }
  function recordingDurationChanged() {
    var input = fields.recording_duration;
    return referenceRecording && (input.validity.badInput || input.value !== String(referenceRecording.reference_seconds ?? ""));
  }
  function recordingDurationHasTake() {
    return voiceSaving || isRecordingVoice || recordingPending || Boolean(importedTake);
  }
  function updateRecordingDuration() {
    var hasTake = recordingDurationHasTake();
    var canEdit = referenceRecording && openedContext === context() && !profileSaving && !hasTake;
    fields.recording_duration.disabled = !canEdit;
    fields.recording_duration_save.disabled = !canEdit || (!recordingDurationChanged() && referenceRecording.duration_seconds !== null);
    fields.recording_duration_discard.disabled = profileSaving || hasTake || !recordingDurationChanged();
    fields.recording_duration_hint.textContent = referenceRecording ? uiFormat("speech_recording_duration_hint", {
      min:referenceFormat.min_seconds, max:referenceFormat.max_seconds, default:referenceRecording.default_seconds
    }) : label("recording_duration_unavailable");
    fields.recording_duration_error.textContent = recordingDurationHasTake() ? label("recording_duration_finish_take") :
      (referenceRecording?.configuration_error || "");
    fields.recording_duration_error.hidden = !fields.recording_duration_error.textContent;
  }
  function prepareRecordingDuration() {
    var input = fields.recording_duration;
    input.value = referenceRecording?.reference_seconds ?? "";
    input.min = referenceFormat?.min_seconds ?? "";
    input.max = referenceFormat?.max_seconds ?? "";
    input.placeholder = referenceRecording?.default_seconds ?? "";
    updateRecordingDuration();
    fields.recLimit.textContent = referenceRecording?.duration_seconds
      ? uiFormat("speech_record_limit", {max:referenceRecording.duration_seconds}) : label("recording_duration_unavailable");
    fields.recLimit.hidden = false;
  }
  function profileDraftMessage() {
    if (mode === "reference" && recordingDurationChanged()) return "recording_duration_unsaved";
    if (mode !== "profiles") return "";
    if (pronunciationPending()) return "pronunciation_pending";
    return profilesDirty ? "profiles_unsaved" : "";
  }
  function languageName(code) {
    try { return new Intl.DisplayNames([document.documentElement.lang || "en"], {type: "language"}).of(code); }
    catch (_) { return code; }
  }
  function context() { return [settingsForm.dataset.projectToken, body.dataset.manuscriptSourceSha256].join(":"); }
  function tokens() { return {project_token: settingsForm.dataset.projectToken, source_sha256: body.dataset.manuscriptSourceSha256}; }
  function syncManuscriptProjectToken(nextToken) {
    if (!/^[a-f0-9]{64}$/.test(nextToken || "")) return;
    var previous = body.dataset.manuscriptProjectToken || "";
    body.dataset.manuscriptProjectToken = nextToken;
    document.querySelectorAll("#manuscript-pdf-form, #workspace-reader").forEach(function(host) {
      if (!previous || host.dataset.projectToken === previous) host.dataset.projectToken = nextToken;
    });
  }
  function url(route, extra) { return API + "/" + route + "?" + new URLSearchParams(Object.assign(tokens(), extra || {})); }
  async function request(route, payload, extra, attempt) {
    var response = await fetch(payload ? API + "/" + route : url(route, extra), payload ? {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)
    } : {});
    if (attempt) {
      var id = response.headers.get("X-Lixity-Diagnostic-Id");
      if (/^[a-f0-9]{16}$/.test(id || "")) attempt.id = id;
      attempt.status = response.status;
    }
    var data = await response.json();
    if (!response.ok || !data.ok) {
      var error = new Error(data.message || data.error || label("failed"));
      error.code = data.code;
      throw error;
    }
    return data;
  }
  function node(tag, parent, className, text) {
    var el = document.createElement(tag); if (className) el.className = className;
    if (text != null) el.textContent = text; if (parent) parent.appendChild(el); return el;
  }
  function actionLabel(control, key, icon) {
    if (!icon || !window.LixityIcons) { control.textContent = label(key); return; }
    var caption = node("span", null, "speech-icon-label");
    caption.append(window.LixityIcons.create(icon), node("span", null, "", label(key)));
    control.replaceChildren(caption);
  }
  function button(parent, key, action, icon) {
    var el = node("button", parent, "ctl"); el.type = "button";
    actionLabel(el, key, icon);
    addHelp(el, key);
    el.dataset.speechAction = key; el.addEventListener("click", action); return el;
  }
  function disclosure(parent, key, icon, className) {
    var section = node("details", parent, "settings-section panel-disclosure " + className);
    actionLabel(node("summary", section), key, icon);
    return section;
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
  function choiceField(parent, key) {
    var input = field(parent, key, "select");
    var readout = node("div", parent, "setting-field speech-choice-readout");
    readout.hidden = true;
    node("span", readout, "form-label", label(key));
    fields[key + "_readout"] = node("strong", readout);
    return input;
  }
  function showChoice(key, visible, fixed, empty) {
    var input = fields[key], value = fields[key + "_readout"];
    var only = fixed && input.options.length === 1 && input.value && input.selectedOptions[0];
    var text = only ? only.textContent : !input.options.length ? empty : "";
    input.closest("label").hidden = !visible || Boolean(text);
    value.parentElement.hidden = !visible || !text;
    value.textContent = text || "";
  }
  function engineOptions(selected) {
    var items = Object.entries(capabilities).filter(function([id, cap]) {
      return cap.creation_enabled !== false || id === selected;
    });
    options(fields.engine, items.map(function([id, cap]) { return [id, cap.short_name || cap.name]; }), selected);
    var groups = new Map();
    Array.from(fields.engine.options).forEach(function(option) {
      var cap = capabilities[option.value];
      var category = !cap || cap.creation_enabled === false ? "retained" :
        providerFields(cap) ? "provider" : cap.voice_design ? "design" :
        referenceSupported(cap) ? "reference" : "presets";
      if (!groups.has(category)) {
        var group = node("optgroup", fields.engine);
        group.label = label("engine_group_" + category);
        groups.set(category, group);
      }
      groups.get(category).append(option);
    });
    fields.engine.value = selected;
  }
  function profileCapability() { return capabilities && capabilities[fields.engine.value] || {}; }
  function usesProviderBinding(engine) { return Boolean(capabilities?.[engine]?.configurable_model); }
  function providerFields(cap) { return !!(cap && cap.configurable_model && cap.provider_fields !== false); }
  function referenceSupported(cap) { return !!(cap && (cap.reference_required || cap.reference_supported)); }
  function selectedReference() {
    var cap = profileCapability();
    var voice = providerFields(cap) && fields.provider_voice ? fields.provider_voice.value : fields.voice && fields.voice.value;
    return !!cap.reference_required || (referenceSupported(cap) && voice === "reference");
  }
  function profileSupport(profile) {
    var cap = profile ? capabilities?.[profile.engine] || {} : profileCapability();
    var support = Object.assign({}, cap.control_support || {});
    var instructionsSupported = profile ? profile.supports_instructions : fields.supports_instructions.checked;
    if (cap.configurable_instructions) support.direction = instructionsSupported ? "model_interpreted" : "unsupported";
    return support;
  }
  function applyPauseBounds(inputs, support) {
    var bounds = support.pause_seconds;
    inputs.forEach(function(input) {
      input.min = bounds ? String(bounds.minimum) : "";
      input.max = bounds ? String(bounds.maximum) : "";
      input.step = "any";
    });
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
  function inReader() { return Boolean(surfaces[mode].manuscript); }
  function sourcePanel(anchor) {
    if (!anchor || !Number.isInteger(anchor.start_line) || !Number.isInteger(anchor.end_line)) return null;
    var selector = `#chapters .ptext[data-start="${anchor.start_line}"][data-end="${anchor.end_line}"]`;
    return Array.from(document.querySelectorAll(selector)).find(function(panel) {
      return panel.dataset.paragraphSha256 === anchor.paragraph_sha256;
    }) || null;
  }
  function passageIdentity(panel) {
    return {start_line:Number(panel.dataset.start), end_line:Number(panel.dataset.end), paragraph_sha256:panel.dataset.paragraphSha256};
  }
  function placeReaderSpeech(panel, align) {
    if (speechPassage !== panel) {
      speechPassage?.classList.remove("speech-direction-target");
      speechPassage = panel;
      speechPassage?.classList.add("speech-direction-target");
    }
    if (!speechDocked) return;
    var active = dialog.contains(document.activeElement) ? document.activeElement : null;
    if (narrowSpeech.matches && panel) {
      if (panel.nextElementSibling !== dialog) panel.after(dialog);
    } else if (dialog.parentElement !== speechLayout) speechLayout.append(dialog);
    if (active && document.activeElement !== active) active.focus({preventScroll:true});
    if (!align || !panel || !dialog.open || dialog.hidden) return;
    if (typeof revealPassageScope === "function") revealPassageScope(panel);
    revealChapter(panel);
    var top = readingViewportTop(), bounds = panel.getBoundingClientRect(), editor = dialog.getBoundingClientRect();
    if (narrowSpeech.matches && (editor.top > innerHeight - 168 || bounds.bottom <= top)) {
      var room = Math.min(156, Math.max(32, (innerHeight - top) / 3));
      window.scrollBy({top:Math.max(bounds.top, editor.top - room) - top, behavior:"instant"});
    } else if (bounds.bottom <= top || bounds.top >= innerHeight - 48) {
      setPassageScrollMargin(panel);
      panel.scrollIntoView({block:"start", behavior:"instant"});
    }
  }
  function visibleReaderSpeech(state) {
    dialog.hidden = state.view !== "analysis" || state.surface !== "document" || state.focus || state.contextTool !== "none";
    speechLayout.classList.toggle("speech-dock-open", !dialog.hidden);
    document.getElementById("reader-speech")?.setAttribute("aria-expanded", String(!dialog.hidden));
  }
  function showReaderDocument() {
    var workbench = window.LixityWorkbench;
    if (workbench.state().view !== "analysis") switchActiveView("analysis", true);
    if (workbench.state().surface !== "document" || workbench.state().contextTool !== "none" || workbench.state().focus) {
      workbench.dispatch({type:"surface", value:"document", contextTool:"none"});
    }
    visibleReaderSpeech(workbench.state());
  }
  function presentSpeechSurface(panel) {
    var dock = Boolean(speechLayout && window.LixityWorkbench && inReader());
    placingSpeech = true;
    try {
      if (dialog.open && speechDocked !== dock) dialog.close();
      if (speechDocked && !dock) placeReaderSpeech(null, false);
      speechDocked = dock;
      dialog.classList.toggle("speech-docked", dock);
      if (dock) {
        if (!speechOpener) speechOpener = document.getElementById("reader-speech");
        showReaderDocument();
        placeReaderSpeech(panel || speechPassage || sourcePanel(paragraph?.identity) || window.LixityReader?.capture()?.panel, false);
        var opening = !dialog.open;
        if (opening) dialog.show();
        placeReaderSpeech(speechPassage, true);
        if (opening || !dialog.contains(document.activeElement) || !document.activeElement.getClientRects().length) {
          fields.heading.focus({preventScroll:true});
        }
      } else {
        speechLayout?.classList.remove("speech-dock-open");
        document.getElementById("reader-speech")?.setAttribute("aria-expanded", "false");
        dialog.hidden = false;
        if (dialog.parentElement !== body) body.append(dialog);
        if (!dialog.open) dialog.showModal();
      }
    } finally { placingSpeech = false; }
  }
  function closeAudioSurface() {
    if (profileSaving || voiceSaving || direction.busy()) { status(label("saving")); return false; }
    if (direction.dirty()) { status(label(mode === "output" ? "direction_output_draft" : "direction_switch_first")); return false; }
    var draft = profileDraftMessage();
    if (draft) { status(label(draft)); return false; }
    if (importedTake) {
      if (mode !== "reference") switchMode("reference");
      status(label("take_unsaved"));
      return false;
    }
    var opener = speechOpener;
    var position = speechDocked && speechPassage?.getClientRects().length ?
      {panel:speechPassage, top:speechPassage.getBoundingClientRect().top} : null;
    dialog.close();
    speechReady = false;
    ++recordingSequence; releaseRecording();
    recordedChunks = []; totalRecordedSamples = 0;
    clearVoiceTake();
    invalidate();
    if (speechDocked) {
      speechLayout.classList.remove("speech-dock-open");
      speechPassage?.classList.remove("speech-direction-target");
      speechPassage = speechOpener = null;
      speechDocked = false;
      document.getElementById("reader-speech")?.setAttribute("aria-expanded", "false");
      if (position) window.LixityReader?.restore(position);
      if (opener?.getClientRects().length) opener.focus({preventScroll:true});
    }
    return true;
  }
  narrowSpeech.addEventListener("change", function() {
    if (dialog?.open && speechDocked) placeReaderSpeech(speechPassage, false);
  });
  function addHelp(el, key) {
    var aliases = {engine:"service_help", voice:"voice_hint", voice_description:"design_hint", reference_id:"reference_hint",
      record_author_title:"record_help", profiles_title:"profile_help", go_to_chapter_audio:"render_help",
      pronunciations:"pronunciation_hint",
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
    var reading = inReader(), output = mode === "output", profiles = mode === "profiles" && profileSettingsAvailable;
    var selected = profiles && Boolean(settings?.selected);
    fields.project_audio_tabs.hidden = reading;
    fields.reader_audio_tabs.hidden = !reading;
    fields.reader_shortcut.hidden = reading;
    fields.reader_context.hidden = !reading;
    fields.reference_section.hidden = mode !== "reference";
    direction.section.hidden = mode !== "reader";
    fields.run_options.hidden = !reading;
    fields.ignore_note.hidden = !fields.ignore_direction.checked;
    fields.target.closest("label").hidden = !reading || !canRender || fields.target.disabled;
    fields.worker_target.closest("label").hidden = fields.worker_target.disabled;
    fields.chapter_audio_section.hidden = !output;
    fields.audit_section.hidden = !output;
    fields.export_section.hidden = !reading;
    fields.render_section.hidden = !reading || !canRender;
    fields.profile_row.hidden = !profiles;
    fields.editor.hidden = fields.lexicon_section.hidden = fields.service_section.hidden = !selected;
    fields.profile_footer.hidden = !profiles || !canSaveProfiles();
    fields.phonemes_section.hidden = !selected || (!profileSupport().phonemes && !fields.phonemes.value.trim());
    fields.microphone_section.hidden = mode !== "microphone";
    fields.render_heading.textContent = label(output ? "render_title" : "preview_title");
    fields.preview.hidden = !reading || !canRender;
    fields.chapter_render.hidden = !output || !canRender;
    fields.preview.classList.toggle("primary", !output);
    fields.chapter_render.classList.toggle("primary", output);
    fields.cancel.hidden = !reading || !canRender || !job;
    fields.reuseLabel.hidden = !output || !canRender;
    fields.playback_section.hidden = mode === "microphone" || !fields.audio.hasAttribute("src");
    var playbackAfter = fields[surfaces[mode].playbackAfter];
    if (playbackAfter && playbackAfter.nextElementSibling !== fields.playback_section) playbackAfter.after(fields.playback_section);
    fields.schema_section.hidden = mode !== "profiles" || !schemaReviewAvailable;
    fields.schema_preview.hidden = fields.schema_section.hidden;
    if (mode !== "profiles") fields.schema_review.hidden = fields.schema_apply.hidden = true;
  }
  function downloadText(text, filename, type) {
    var blob = new Blob([text], {type: type + ";charset=utf-8"});
    if (window.LixityComponents && typeof window.LixityComponents.downloadBlob === "function") {
      window.LixityComponents.downloadBlob(blob, filename, 2000);
      return;
    }
    var address = URL.createObjectURL(blob);
    var link = document.createElement("a"); link.href = address; link.download = filename;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(function() { URL.revokeObjectURL(address); }, 2000);
  }
  function microphoneMixer() {
    var mic = microphoneState, info = mic && mic.gainInfo;
    var device = mic && mic.devices.find(function(item) { return item.id === fields.microphone_device.value; });
    if (!info || !device || info.card == null || !info.control ||
        ![device.card, device.cardId].some(function(card) { return card != null && String(card) === String(info.card); }) ||
        !Number.isInteger(mic.gain) || !Number.isInteger(info.min) || !Number.isInteger(info.max) ||
        info.max <= info.min ||
        mic.gain < info.min || mic.gain > info.max) return null;
    return info;
  }
  function nativeMicrophoneInventory() {
    var capture = window.lixityDesktop?.audioCapture;
    return typeof capture?.listDevices === "function" ? capture : null;
  }
  function microphoneControls() {
    var mixer = microphoneMixer(), unavailable = microphoneBusy || microphoneRefreshing;
    fields.microphone_refresh.disabled = unavailable;
    fields.microphone_device.disabled = unavailable || fields.microphone_device.options.length <= 1;
    fields.microphone_gain.disabled = fields.microphone_gain_range.disabled = fields.microphone_set_btn.disabled = unavailable || mixer?.writable !== true;
    fields.microphone_calib_btn.disabled = unavailable || !fields.microphone_device.value;
  }
  function showMicrophoneGain() {
    window.LixityComponents.setStatus(fields.microphone_gain_status, "");
    window.LixityComponents.setStatus(fields.microphone_check_status, "");
    fields.microphone_gain.removeAttribute("aria-invalid");
    var info = microphoneMixer(), hasDevice = Boolean(fields.microphone_device.value);
    fields.microphone_gain_field.hidden = !hasDevice || Boolean(nativeMicrophoneInventory());
    fields.microphone_gain.hidden = !info;
    fields.microphone_set_btn.hidden = info?.writable !== true;
    fields.microphone_gain.value = fields.microphone_gain_range.value = info ? String(microphoneState.gain) : "";
    fields.microphone_gain_range.hidden = !info;
    fields.microphone_gain_info.textContent = label("microphone_gain_unknown");
    if (info) {
      [fields.microphone_gain, fields.microphone_gain_range].forEach(function(input) {
        input.min = String(info.min); input.max = String(info.max);
        input.value = String(microphoneState.gain);
      });
      fields.microphone_gain_info.textContent = uiFormat("speech_microphone_gain_limits", {minimum:info.min, maximum:info.max}) +
        (Number.isFinite(info.db) ? " · " + (info.db >= 0 ? "+" : "") + info.db.toFixed(1) + " dB" : "") +
        (info.writable !== true ? " · " + label("microphone_gain_read_only") : "");
    }
    fields.microphone_calib_result.replaceChildren();
    microphoneControls();
  }
  function browserMicrophoneState(mic) {
    return {
      devices: (mic?.devices || []).map(function(device) {
        return {id:device.alsa_id, label:device.alsa_id === "default" ? label("microphone_default_input") : device.label,
          card:device.card, cardId:device.card_id};
      }),
      defaultDevice: mic?.default_device, gain: mic?.current_gain, gainInfo: mic?.gain_info
    };
  }
  function populateMicrophone(mic) {
    microphoneState = mic;
    var devices = mic?.devices || [], select = fields.microphone_device;
    if (mic && !devices.some(function(device) { return device.id === preferredMicrophone; })) {
      preferredMicrophone = "";
    }
    var selected = preferredMicrophone || mic?.defaultDevice;
    var choices = devices.map(function(device) {
      var name = device.is_default ? uiFormat("speech_microphone_system_default", {device:device.label}) : device.label;
      return new Option(name, device.id);
    });
    select.replaceChildren(...choices);
    if (devices.some(function(device) { return device.id === selected; })) select.value = selected;
    fields.microphone_choice.hidden = choices.length < 2;
    fields.microphone_current.hidden = choices.length !== 1;
    fields.microphone_current_name.textContent = choices.length === 1 ? choices[0].textContent : "";
    fields.microphone_scope.hidden = !choices.length;
    showMicrophoneGain();
  }
  function microphoneInventoryStatus(key) {
    fields.microphone_inventory_status.textContent = key ? label(key) : "";
  }
  async function refreshMicrophone() {
    if (microphoneRefreshing || microphoneBusy || !dialog.open) return;
    var sequence = openSequence, capture = nativeMicrophoneInventory();
    function current() { return sequence === openSequence && dialog.open && context() === openedContext; }
    microphoneRefreshing = true;
    microphoneInventoryStatus("microphone_looking");
    microphoneControls();
    try {
      var mic;
      if (capture) {
        var devices = await capture.listDevices();
        if (!Array.isArray(devices)) throw new Error("Invalid native microphone inventory");
        var systemDefault = devices.find(function(device) { return device.is_default; });
        mic = {devices:devices, defaultDevice:systemDefault?.id};
      } else {
        mic = browserMicrophoneState(await request("audio-microphone", {
          action:"status", ...(preferredMicrophone ? {device:preferredMicrophone} : {})
        }));
      }
      if (!current()) return;
      populateMicrophone(mic);
      microphoneInventoryStatus(mic.devices.length ? "" : "microphone_empty");
    } catch (_) {
      if (!current()) return;
      populateMicrophone(null);
      microphoneInventoryStatus("microphone_failed");
    } finally {
      if (current()) { microphoneRefreshing = false; microphoneControls(); }
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
      var scope = fields.audit_scope.value;
      var result = await request("audio-audit", Object.assign(tokens(), {
        audio: encoded, filename: file.name, transcript: transcript, mode: scope,
        chapter: scope === "manuscript" ? null : Number(fields.chapter.value),
        ignore_direction: fields.ignore_direction.checked
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
      auditAudioUrl = URL.createObjectURL(file); fields.audio.src = auditAudioUrl;
      fields.playback_section.hidden = fields.audio.hidden = false;
      if (fields.player_controls) fields.player_controls.hidden = false;
      button(fields.audit_result, "audit_download", function() { downloadText(JSON.stringify(audit, null, 2), "audio-audit.json", "application/json"); });
      status(label("audit_ready"));
    } catch (error) { if (valid(serial)) status(error.message); }
    finally { fields.audit_run.disabled = false; }
  }
  function clearAudio() {
    generatedAudio = null;
    fields.audio.pause(); fields.audio.removeAttribute("src"); fields.audio.load(); fields.audio.hidden = true;
    fields.playback_section.hidden = true;
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
    fields.cancel.hidden = fields.cancel.disabled = true;
    fields.preview.disabled = fields.chapter_render.disabled = !canRender || !settings || !settings.selected || !fields.chapter.options.length || openedContext !== context();
    if (fields.direction_plan) fields.direction_plan.disabled = !settings || !settings.selected || !fields.chapter.options.length || openedContext !== context();
    fields.progress.hidden = true;
    if (fields.plan) { fields.plan.replaceChildren(); fields.plan.hidden = true; }
    if (fields.audit_result) fields.audit_result.replaceChildren();
  }
  function applyWorkerInventory(inventory) {
    if (!Array.isArray(inventory)) return;
    var previous = Array.isArray(workers) ? workers : [];
    workers = previous.filter(function(item) {
      return !inventory.some(function(observed) {
        return observed.target === item.target &&
          (!item.engines || !observed.engines || item.engines.some(function(engine) {
            return observed.engines.includes(engine);
          }));
      });
    }).concat(inventory);
    updateWorkerStatus(); updateRuntimeHint();
  }
  function workerFor(engine, target) {
    return Array.isArray(workers) ? workers.find(function(item) {
      return item.target === target && (!item.engines || item.engines.includes(engine));
    }) : null;
  }
  function workerGuide(engine, cap) {
    return cap.guide_url || (engine?.startsWith("coqui") ? settingsForm.dataset.speechCoquiGuide : settingsForm.dataset.speechQwenGuide);
  }
  function updateWorkerStatus() {
    if (!fields.worker_status || !fields.engine || !capabilities) return;
    var selectedCap = profileCapability();
    var engine = fields.engine.value;
    var external = providerFields(selectedCap);
    fields.worker_guide.hidden = external || selectedCap.runtime_status === "unavailable";
    fields.worker_guide.href = workerGuide(engine, selectedCap);
    if (external) { fields.worker_status.textContent = label("provider_status"); return; }
    if (selectedCap.runtime_status === "unavailable") { fields.worker_status.textContent = label("engine_unavailable"); return; }
    var target = fields.worker_target.value || "local", worker = workerFor(engine, target);
    var args = {target: label("target_" + target)};
    var knownModel = worker && worker.model && Object.values(capabilities).find(function(item) { return item.model === worker.model; });
    var key = "unknown";
    if (worker && worker.state === "starting") key = "starting";
    else if (worker && worker.state === "unavailable") key = "unavailable";
    else if (worker && worker.state === "ready" && knownModel && selectedCap.model) {
      args.model = knownModel.name;
      key = worker.model === selectedCap.model ? "match" : "mismatch";
      if (key === "match" && ["unloaded", "loading", "loaded", "failed"].includes(worker.model_state)) {
        key = "model_" + (worker.model_state === "loaded" && worker.active ? "active" : worker.model_state);
      }
    }
    var message = uiFormat("speech_worker_" + key, args);
    if (key.startsWith("model_") && Number.isFinite(worker.idle_timeout_seconds) && worker.idle_timeout_seconds >= 0) {
      var seconds = new Intl.NumberFormat(document.documentElement.lang || "en", {maximumFractionDigits: 20}).format(worker.idle_timeout_seconds);
      message += " " + uiFormat("speech_worker_idle_policy", {seconds: seconds});
    }
    fields.worker_status.textContent = message;
  }
  function updateRuntimeHint() {
    var engine = savedSettings?.profiles[savedSettings.selected]?.engine;
    var cap = capabilities?.[engine] || {};
    var target = fields.target.value || "local";
    var worker = engine && workerFor(engine, target);
    var unavailable = worker?.state === "unavailable";
    var key = cap.runtime_status === "unavailable" ? "engine_unavailable" : cap.local_worker ? "zonos_runtime_hint" :
      cap.configurable_model ? "provider_hint" : "runtime_hint";
    fields.runtime_hint.textContent = unavailable && !providerFields(cap)
      ? uiFormat("speech_worker_unavailable", {target: label("target_" + target)}) : label(key);
    fields.runtime_guide.hidden = !unavailable || cap.runtime_status === "unavailable" || providerFields(cap);
    if (!fields.runtime_guide.hidden) fields.runtime_guide.href = workerGuide(engine, cap);
  }
  function updateModelFields() {
    var cap = profileCapability(), support = profileSupport();
    var designed = !!cap.voice_design, referenced = selectedReference();
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
    fields.phonemes_section.hidden = mode !== "profiles" || (!support.phonemes && !fields.phonemes.value.trim());
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
    fields.engine.dataset.help = cap.name + ". " + label("service_help");
    var designed = !!cap.voice_design;
    var external = !!cap.configurable_model;
    var provider = providerFields(cap);
    var language = fields.language.value, voice = fields.voice.value || (cap.reference_supported && fields.reference_id.value.trim() ? "reference" : "");
    options(fields.language, cap.languages.map(function(value) { return [value, languageName(value)]; }), language);
    var voices = Object.entries(cap.voices).filter(function(pair) { return pair[1].languages.includes(fields.language.value); });
    options(fields.voice, designed ? [["design", "VoiceDesign"]] : voices.map(function(pair) { return [pair[0], pair[1].name]; }), designed ? "design" : voice);
    var referenced = selectedReference();
    var showVoice = !designed && !cap.reference_required && !provider;
    showChoice("voice", showVoice, voices.some(function([value]) { return value === fields.voice.value; }));
    fields.voice.disabled = !showVoice;
    showChoice("language", !provider, cap.languages.includes(fields.language.value));
    fields.language.disabled = provider;
    ["base_url", "provider_model", "api_key_env", "provider_voice", "provider_language", "supports_instructions"].forEach(function(key) {
      fields[key].closest("label").hidden = !provider; fields[key].disabled = !provider;
      fields[key].required = provider && !["api_key_env", "supports_instructions"].includes(key);
    });
    fields.supports_instructions.closest("label").hidden = !external || fields.engine.value === "mlx-audio";
    fields.supports_instructions.disabled = !external || fields.engine.value === "mlx-audio";
    updateModelFields();
    fields.reference_hint.hidden = !referenced;
    fields.design_hint.hidden = !designed;
    fields.speed.min = String(cap.speed.minimum);
    fields.speed.max = String(cap.speed.maximum);
    var modelTempo = cap.speed.implementation === "model-condition";
    var tempoHelp = uiFormat(modelTempo ? "speech_speed_hint_model" : "speech_speed_hint", {
      default: new Intl.NumberFormat(document.documentElement.lang || undefined).format(cap.speed.default)
    });
    fields.speed_label.textContent = label(modelTempo ? "speed_model" : "speed");
    fields.speed_hint.textContent = tempoHelp;
    fields.speed.dataset.help = tempoHelp;
    var support = profileSupport();
    applyPauseBounds([fields.paragraph_pause, fields.scene_pause], support);
    direction.updateCapabilities();
    var targets = cap.targets.map(function(value) { return [value, label("target_" + value)]; });
    [fields.target, fields.worker_target].forEach(function(select) {
      options(select, targets, cap.targets.includes(select.value) ? select.value : cap.targets[0]);
      select.disabled = cap.targets.length < 2;
    });
    fields.target.closest("label").hidden = !inReader() || !canRender || fields.target.disabled;
    fields.worker_target.closest("label").hidden = fields.worker_target.disabled;
    updateRuntimeHint();
    fields.reuse.closest("label").hidden = mode !== "output" || !canRender;
    updateWorkerStatus(); updateVoiceCard();
  }
  function loadProfile() {
    invalidate();
    if (!settings.selected) {
      setEditorDisabled(true); fields.save.disabled = !canSaveProfiles(); arrangeSections();
      return;
    }
    var profile = settings.profiles[settings.selected];
    lastPreset = profile.engine === "qwen3" ? profile.voice : capabilities.qwen3?.default_voice || "";
    ["name", "instructions", "speed", "paragraph_pause", "scene_pause"].forEach(function(key) { fields[key].value = profile[key]; });
    engineOptions(profile.engine);
    fields.base_url.value = profile.base_url || ""; fields.provider_model.value = profile.model || "";
    fields.api_key_env.value = profile.api_key_env || ""; fields.supports_instructions.checked = !!profile.supports_instructions;
    fields.provider_voice.value = usesProviderBinding(profile.engine) ? profile.voice : "";
    fields.provider_language.value = profile.language;
    fields.voice_description.value = profile.voice_description || "";
    fields.phonemes.value = Object.entries(profile.phonemes || {}).map(function(pair) { return pair.join("="); }).join("\n");
    profileProsody.load(profile.prosody || {});
    referenceOptions(profile.reference_id || "");
    options(fields.language, [], profile.language); options(fields.voice, [], profile.voice); voiceControls();
    setPronunciations(profile.pronunciations);
    clearPronunciationDraft();
    fields.pronunciation_search.value = ""; renderPronunciations();
    setEditorDisabled(false); fields.save.disabled = false;
    arrangeSections();
  }
  function setEditorDisabled(disabled) {
    fields.editor.disabled = disabled;
    if (fields.lexicon_section) {
      fields.lexicon_section.querySelectorAll("input, textarea, select, button").forEach(function(el) {
        el.disabled = disabled;
      });
    }
    if (fields.phonemes_section) {
      if (disabled) {
        fields.phonemes_section.querySelectorAll("input, textarea, select, button").forEach(function(el) {
          el.disabled = true;
        });
      } else {
        updateModelFields();
      }
    }
  }
  function setProfileSaving(saving) {
    profileSaving = saving;
    if (!dialog.open) return;
    var current = openedContext === context();
    setEditorDisabled(saving || !current || !settings.selected);
    fields.profile_discard.disabled = saving;
    fields.profile.disabled = saving || !current;
    fields.save.disabled = saving || !current || migrationRequired || !canSaveProfiles();
    if (saving || !current) fields.create.disabled = fields.remove_profile.disabled = true;
    else profileOptions();
    updateRecordingDuration();
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
    if (selectedReference() && !fields.reference_id.checkValidity()) throw new Error(label("model_need_reference"));
    if (profileCapability().voice_design && !fields.voice_description.value.trim()) throw new Error(label("model_need_description"));
    var replacements = pronunciationEntries();
    var profile = {name: fields.name.value.trim(), engine: fields.engine.value, language: fields.language.value,
      voice: fields.voice.value,
      speed: Number(fields.speed.value), instructions: fields.instructions.value.trim(),
      paragraph_pause: Number(fields.paragraph_pause.value), scene_pause: Number(fields.scene_pause.value), pronunciations: replacements};
    if (profileCapability().voice_design) profile.voice_description = fields.voice_description.value.trim();
    if (selectedReference()) profile.reference_id = fields.reference_id.value.trim();
    var phonemes = phonemeEntries(), prosody = profileProsody.read();
    if (Object.keys(phonemes).length) profile.phonemes = phonemes;
    if (Object.keys(prosody).length) profile.prosody = prosody;
    if (usesProviderBinding(profile.engine)) {
      profile.base_url = fields.base_url.value.trim() || profileCapability().default_base_url || "";
      profile.model = fields.provider_model.value.trim() || profileCapability().model || "";
      profile.api_key_env = fields.api_key_env.value.trim() || null;
      profile.supports_instructions = fields.supports_instructions.checked;
      if (providerFields(profileCapability())) {
        profile.voice = fields.provider_voice.value.trim(); profile.language = fields.provider_language.value.trim();
      }
    }
    return profile;
  }
  function pronunciationPending() {
    return Boolean(editingPronunciation !== null || fields.pronunciation_term.value.trim() ||
      fields.pronunciation_spoken.value.trim() || fields.pronunciation_ipa.value.trim());
  }
  function clearPronunciationDraft() {
    editingPronunciation = null;
    fields.pronunciation_term.value = fields.pronunciation_spoken.value = fields.pronunciation_ipa.value = "";
  }
  function editablePronunciations() {
    if (pronunciationScope === "profile") return pronunciationEntries();
    return Object.assign(Object.create(null), settings?.pronunciation_lexicon?.entries);
  }
  function storePronunciations(entries) {
    if (pronunciationScope === "profile") setPronunciations(entries);
    else if (Object.keys(entries).length) settings.pronunciation_lexicon = {
      schema_version: "lixity-pronunciation-lexicon/1", entries: entries,
    };
    else delete settings.pronunciation_lexicon;
    profilesDirty = true;
    invalidate();
    renderPronunciations();
    status(label("profiles_unsaved"));
  }
  function renderPronunciations() {
    var shared = pronunciationScope === "project";
    var needsUpgrade = shared && settings?.schema_version !== currentAudioSchema;
    fields.pronunciation_scope.value = pronunciationScope;
    fields.pronunciation_upgrade.hidden = !needsUpgrade;
    fields.pronunciation_controls.hidden = needsUpgrade;
    fields.pronunciation_project_hint.hidden = !shared;
    fields.pronunciation_bulk.hidden = shared;
    fields.pronunciation_ipa.closest("label").hidden = !shared;
    fields.pronunciation_list.setAttribute("aria-label", label(shared ? "pronunciation_scope_project" : "pronunciation_scope_profile"));
    fields.pronunciation_list.replaceChildren();
    if (needsUpgrade) return;
    var replacements;
    try { replacements = editablePronunciations(); }
    catch (_) { return; }
    var query = fields.pronunciation_search.value.trim().toLocaleLowerCase();
    var matches = 0;
    Object.entries(replacements).forEach(function([term, value]) {
      var ipa = shared ? value.ipa || "" : "";
      var spoken = shared ? value.respelling || "" : value;
      if (query && ![term, spoken, ipa].join(" ").toLocaleLowerCase().includes(query)) return;
      matches++;
      var row = node("li", fields.pronunciation_list, "row"); row.dataset.pronunciationRow = "true";
      node("span", row, "", term + " → " + [ipa && "/" + ipa + "/", spoken].filter(Boolean).join(" · "));
      var edit = button(row, "pronunciation_edit", function() {
        if (pronunciationPending()) { status(label("pronunciation_pending")); return; }
        editingPronunciation = term;
        fields.pronunciation_term.value = term;
        fields.pronunciation_spoken.value = spoken;
        fields.pronunciation_ipa.value = ipa;
        (shared && ipa ? fields.pronunciation_ipa : fields.pronunciation_spoken).focus();
      });
      edit.setAttribute("aria-label", label("pronunciation_edit") + ": " + term);
      var remove = button(row, "pronunciation_remove", function() {
        if (pronunciationPending()) { status(label("pronunciation_pending")); return; }
        try {
          var current = editablePronunciations();
          delete current[term];
          storePronunciations(current);
          fields.pronunciation_search.focus();
        } catch (error) { status(error.message); }
      });
      remove.setAttribute("aria-label", label("pronunciation_remove") + ": " + term);
    });
    fields.pronunciation_empty.hidden = matches > 0;
    fields.pronunciation_empty.textContent = label(query ? "pronunciation_not_found" : "pronunciation_empty");
  }
  function applyPronunciation() {
    try {
      var shared = pronunciationScope === "project";
      var entries = editablePronunciations(), term = fields.pronunciation_term.value.trim();
      var spoken = fields.pronunciation_spoken.value.trim(), ipa = fields.pronunciation_ipa.value.trim();
      if (shared && settings.schema_version !== currentAudioSchema) {
        guideToSchemaReview("pronunciation_schema_required"); return;
      }
      if (!term || (!spoken && !(shared && ipa)) ||
          [term, spoken, ipa].some(function(value) { return /[\u0000-\u001f\u007f]/.test(value); }) ||
          (Object.hasOwn(entries, term) && term !== editingPronunciation)) {
        throw new Error(label(shared ? "pronunciation_project_error" : "pronunciation_error"));
      }
      if (editingPronunciation !== null && editingPronunciation !== term) delete entries[editingPronunciation];
      entries[term] = shared ? Object.assign({}, ipa ? {ipa: ipa} : null, spoken ? {respelling: spoken} : null) : spoken;
      clearPronunciationDraft();
      storePronunciations(entries);
      fields.pronunciation_term.focus();
    } catch (error) { status(error.message); }
  }
  function stash() { if (settings && settings.selected) settings.profiles[settings.selected] = readProfile(); }
  function supportsEmptyProfiles() {
    return ["lixity-audio-settings/4", currentAudioSchema].includes(settings?.schema_version);
  }
  function canSaveProfiles() {
    return Boolean(settings?.selected || (profilesDirty && supportsEmptyProfiles()));
  }
  function profileOptions() {
    options(fields.profile, Object.entries(settings.profiles).map(function(pair) { return [pair[0], pair[1].name]; }), settings.selected);
    showChoice("profile", true, true, label("profile_empty"));
    fields.create.disabled = migrationRequired || !profileConstraints || Object.keys(settings.profiles).length >= profileConstraints.maximum;
    fields.remove_profile.hidden = !settings.selected;
    fields.remove_profile.disabled = migrationRequired || fields.remove_profile.hidden;
  }
  function guideToSchemaReview(reason) {
    status(label(reason));
    if (!fields.schema_section.hidden) fields.schema_preview.focus();
  }
  function removeProfile() {
    if (migrationRequired || !settings?.selected) return;
    if (pronunciationPending()) { status(label("pronunciation_pending")); return; }
    var id = settings.selected;
    if (savedDirectionView && savedDirectionView.directions.some(function(item) { return item.profile_id === id; })) {
      status(label("profile_referenced")); return;
    }
    if (Object.keys(settings.profiles).length === 1 && !supportsEmptyProfiles()) {
      guideToSchemaReview("profile_remove_last_schema");
      return;
    }
    delete settings.profiles[id];
    profilesDirty = true;
    settings.selected = Object.keys(settings.profiles)[0] || "";
    profileOptions(); loadProfile(); status(label("profile_removed_draft"));
  }
  function create() {
    if (fields.create.disabled) return;
    try { stash(); } catch (error) { status(error.message); return; }
    var id = "narrator", index = 1;
    while (Object.hasOwn(settings.profiles, id)) id = "narrator_" + (++index);
    // Preserve languages that require an explicitly configured external provider.
    var projectLanguage = document.getElementById("set-language");
    var language = fields.language.value || (projectLanguage && projectLanguage.value) || document.documentElement.lang;
    var mlx = capabilities["mlx-audio"];
    var mlxPreset = Object.entries(mlx?.voices || {}).find(function(pair) {
      return pair[0] !== "reference" && pair[1].languages.includes(language);
    })?.[0];
    var mlxReady = Array.isArray(workers) &&
      workers.some(function(item) { return item.engines?.includes("mlx-audio") && item.state === "ready"; });
    var mlxReference = referenceSupported(mlx) && mlx.languages.includes(language);
    var authorEngine = mlxReady && (mlxReference || mlxPreset) ? "mlx-audio" : "ims-toucan", cap = capabilities[authorEngine];
    var engine = cap && cap.creation_enabled !== false && cap.languages.includes(language) ? authorEngine : "openai-compatible";
    cap = capabilities[engine];
    var external = !!cap.configurable_model;
    if (external && !["lixity-audio-settings/4", currentAudioSchema].includes(settings.schema_version)) { guideToSchemaReview("provider_schema_required"); return; }
    if (engine === "ims-toucan" && settings.schema_version !== currentAudioSchema) { guideToSchemaReview("phonemes_schema_required"); return; }
    var voice = engine === "mlx-audio" ? (allReferences.length || !mlxPreset ? "reference" : mlxPreset) : cap.reference_required ? "reference" :
      external ? "" : cap.default_voice || Object.keys(cap.voices)[0];
    var created = {name: label("new_profile"), engine: engine, language: language, voice: voice, speed: cap.speed.default,
      instructions: "", paragraph_pause: profileConstraints.default_paragraph_pause,
      scene_pause: profileConstraints.default_scene_pause, pronunciations: {}};
    settings.profiles[id] = created;
    profilesDirty = true;
    settings.selected = id; profileOptions(); loadProfile(); fields.name.focus();
  }
  function valid(serial) { return serial === generation && dialog.open && openedContext === context(); }
  function generatedAudioEvent(event) {
    var result = generatedAudio;
    if (!result || !valid(result.serial) || result.events.has(event)) return;
    result.events.add(event);
    window.LixityLog?.audioClient?.(event, result.diagnosticId);
  }
  async function poll(serial, active) {
    if (!valid(serial) || job !== active) return;
    try {
      var response = await fetch(url("speech-job", {id: active.id})); var data = await response.json();
      if (!valid(serial) || job !== active) return;
      if (!response.ok || !data.ok) throw new Error(data.message || label("failed"));
      var result = data.job;
      fields.progress.max = result.total || 1; fields.progress.value = result.done || 0;
      var statusMsg = label(active.cancelling && ["pending", "running"].includes(result.state) ? "cancelling" : "state_" + ({ready: "completed", error: "failed", stale: "failed"}[result.state] || result.state));
      if (result.state === "running" && result.total && result.done !== undefined) {
        var pct = Math.round((result.done / result.total) * 100);
        statusMsg += " · " + result.done + "/" + result.total + " (" + pct + "%)";
      }
      if (result.message) statusMsg += ": " + result.message;
      status(statusMsg);
      if (result.state === "pending" && !active.cancelling && result.queue_position) status(uiFormat("runtime_queued", {position: result.queue_position}));
      if (result.state === "ready" && active.cancelling) {
        status(label("cancelling")); timer = setTimeout(function() { poll(serial, active); }, 500); return;
      }
      if (result.state === "ready") {
        generatedAudio = {serial: serial, diagnosticId: active.diagnosticId, events: new Set()};
        fields.audio.src = url("speech-audio", {id: active.id});
        fields.playback_section.hidden = fields.audio.hidden = false;
        if (fields.player_controls) fields.player_controls.hidden = false;
        fields.context.textContent += result.context && result.context.excerpt ? " · " + result.context.excerpt : "";
        if (result.context && result.context.truncated) fields.context.textContent += " · " + label("truncated");
        fields.download.href = fields.audio.src; fields.download.hidden = false; finish();
        if (result.context && result.context.mode === "chapter") refreshChapterAudio();
      } else if (["error", "stale", "cancelled"].includes(result.state)) {
        if (result.state === "error" && !active.cancelling) window.LixityLog?.audioClient?.("render_error_shown", active.diagnosticId);
        finish();
      }
      else timer = setTimeout(function() { poll(serial, active); }, 500);
    } catch (error) {
      if (!valid(serial) || job !== active) return;
      if (!active.cancelling && response?.status !== 409) window.LixityLog?.audioClient?.("render_poll_failed", active.diagnosticId);
      status(error.message); finish();
    }
  }
  function finish() {
    job = null; fields.cancel.hidden = fields.cancel.disabled = true;
    fields.preview.disabled = fields.chapter_render.disabled = !canRender || !settings || !settings.selected || !fields.chapter.options.length || openedContext !== context();
  }
  function selectedChapterAudio() {
    return chapterAudio?.find(function(entry) { return entry.chapter === Number(fields.chapter.value); });
  }
  function updateChapterAudioActions() {
    var unavailable = chapterAudioBusy || !speechReady || openedContext !== context();
    fields.chapter_audio_delete.hidden = !selectedChapterAudio();
    fields.chapter_audio_delete.disabled = unavailable;
    fields.chapter_audio_discard.hidden = !fields.chapter_audio_file.files.length;
    fields.chapter_audio_discard.disabled = unavailable;
  }
  function setChapterAudioBusy(busy) {
    chapterAudioBusy = busy;
    fields.chapter.disabled = busy;
    fields.chapter_audio_import.disabled = fields.chapter_audio_file.disabled = busy || !speechReady || openedContext !== context();
    updateChapterAudioActions();
  }
  function showChapterAudio() {
    updateChapterAudioActions();
    if (!fields.chapter_audio_status || chapterAudio === null || chapterAudioBusy) return;
    var entry = selectedChapterAudio();
    fields.chapter_audio_status.textContent = entry ? label("chapter_audio_ready") + " · " + entry.duration_seconds.toFixed(1) + " s" : label("chapter_audio_missing");
  }
  async function refreshChapterAudio() {
    if (!speechReady || chapterAudioBusy || mode !== "output") return;
    var sequence = ++chapterAudioSequence, opening = openSequence, bound = context();
    chapterAudio = null;
    updateChapterAudioActions();
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
    ++chapterAudioSequence; setChapterAudioBusy(true);
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
      if (opening === openSequence) setChapterAudioBusy(false);
    }
  }
  async function removeChapterAudio() {
    var entry = selectedChapterAudio();
    if (!entry || fields.chapter_audio_delete.disabled || !confirm(label("chapter_audio_delete_confirm"))) return;
    var opening = openSequence, bound = context(), removed = false;
    ++chapterAudioSequence; setChapterAudioBusy(true);
    fields.chapter_audio_status.textContent = label("saving");
    function current() { return opening === openSequence && dialog.open && bound === context(); }
    try {
      var result = await request("speech-audio-delete", Object.assign(tokens(), {
        chapter:entry.chapter, audio_sha256:entry.audio_sha256
      }));
      if (!current()) return;
      chapterAudio = chapterAudio.filter(function(item) { return item !== entry; });
      clearAudio();
      fields.chapter_audio_status.textContent = label(result.cleanup_pending ? "chapter_audio_cleanup_pending" : "chapter_audio_deleted");
      removed = true;
    } catch (error) {
      if (!current()) return;
      if (error.code === "chapter-audio-changed") chapterAudio = null;
      fields.chapter_audio_status.textContent = error.message;
    } finally {
      if (opening === openSequence) {
        setChapterAudioBusy(false);
        if (removed && current() && mode === "output") fields.chapter_audio_file.focus();
      }
    }
  }
  function renderBlocked(planOnly, event, message) {
    if (!planOnly) window.LixityLog?.audioClient?.(event);
    status(label(message)); finish();
  }
  async function render(mode, planOnly) {
    if (migrationRequired || (!planOnly && !canRender)) return;
    if (openedContext !== context()) {
      if (!planOnly) window.LixityLog?.audioClient?.("render_blocked_context");
      status(label("direction_context_changed")); return;
    }
    var attempt = {};
    try {
      var profileId = savedSettings?.selected, profile = savedSettings?.profiles[profileId];
      if (!profile) return renderBlocked(planOnly, "render_blocked_profile", "profile_required");
      invalidate(); var serial = generation;
      if (!planOnly && profile.instructions && profileSupport(profile).direction !== "model_interpreted") {
        return renderBlocked(false, "render_blocked_direction", "instructions_export_only");
      }
      fields.preview.disabled = fields.chapter_render.disabled = true;
      status(label("state_pending"));
      var payload = Object.assign(tokens(), {mode: mode, chapter: mode === "manuscript" ? null : Number(fields.chapter.value), profile_id: profileId,
        target: fields.target.value || "local", ignore_direction: fields.ignore_direction.checked});
      if (mode === "preview" && paragraph) payload.paragraph = paragraph.identity;
      if (mode !== "preview") {
        if (direction.dirty() && !fields.ignore_direction.checked) {
          return renderBlocked(planOnly, "render_blocked_direction", "direction_save_first");
        }
        payload.fresh_audio = !fields.reuse.checked;
      } else if (!fields.ignore_direction.checked) {
        var draft = direction.draft(); if (draft) { payload.draft_direction = draft; var replacement=direction.replacement(); if (replacement) payload.draft_replace_id=replacement; }
      }
      var cap = capabilities[profile.engine];
      var execution = providerFields(cap) ? cap.short_name || cap.name : label("target_" + payload.target);
      fields.context.textContent = (planOnly ? label("direction_plan") : execution) + " · " + (mode === "manuscript" ? label("scope_manuscript") : fields.chapter.selectedOptions[0].textContent) +
        (mode === "preview" ? " · " + label(paragraph ? "paragraph_preview" : "first_preview") : "") +
        (mode === "preview" && paragraph ? " · " + paragraph.identity.start_line + "–" + paragraph.identity.end_line : "");
      var data = await request(planOnly ? "speech-plan" : "speech-render", payload, null, planOnly ? null : attempt);
      if (planOnly) {
        if (!valid(serial)) return;
        fields.plan.replaceChildren();
        var ssmlHeader = node("div", fields.plan, "row");
        if (data.timeline) button(ssmlHeader, "export_json", function() { downloadText(JSON.stringify(data.timeline, null, 2), "speech-timeline.json", "application/json"); });
        if (data.ssml) {
          var ssmlBtn = button(ssmlHeader, "export_ssml", function() {
            downloadText(data.ssml, "speech-timeline.ssml", "application/ssml+xml");
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
      job = {id: data.job.id, tokens: tokens(), diagnosticId: attempt.id};
      fields.cancel.hidden = fields.cancel.disabled = fields.progress.hidden = false;
      poll(serial, job);
    } catch (error) {
      if (serial == null || valid(serial)) {
        if (!planOnly && attempt.status !== 409) window.LixityLog?.audioClient?.("render_submit_failed", attempt.id);
        status(error.message); finish();
      }
    }
  }
  async function cancel() {
    if (!job) return;
    var active = job; active.cancelling = true; fields.cancel.disabled = true; status(label("cancelling"));
    try { await request("speech-cancel", Object.assign({}, active.tokens, {id: active.id})); }
    catch (error) { if (job === active) { status(error.message); fields.cancel.disabled = false; active.cancelling = false; } }
  }
  async function save() {
    if (migrationRequired || profileSaving || !canSaveProfiles()) return false;
    if (recordingDurationChanged()) { status(label("recording_duration_unsaved")); return false; }
    if (openedContext !== context()) { status(label("pronunciation_context_changed")); return false; }
    try {
      if (!Array.from(fields.editor.querySelectorAll("input, select, textarea")).every(function(input) { return input.reportValidity(); })) return false;
      stash();
      if (!["lixity-audio-settings/3", "lixity-audio-settings/4", currentAudioSchema].includes(settings.schema_version) && Object.values(settings.profiles).some(function(profile) { return profile.engine.startsWith("coqui"); })) {
        guideToSchemaReview("coqui_schema_required"); return false;
      }
      if (!["lixity-audio-settings/4", currentAudioSchema].includes(settings.schema_version) && Object.values(settings.profiles).some(function(profile) { return usesProviderBinding(profile.engine); })) {
        guideToSchemaReview("provider_schema_required"); return false;
      }
      if (settings.schema_version !== currentAudioSchema && Object.values(settings.profiles).some(function(profile) {
        return profile.engine === "ims-toucan" || Object.keys(profile.phonemes || {}).length || Object.keys(profile.prosody || {}).length;
      })) { guideToSchemaReview("phonemes_schema_required"); return false; }
      invalidate(); var serial = generation; setProfileSaving(true);
      status(label("saving"));
      await request("settings", {project_token: tokens().project_token, audio: settings});
      if (!valid(serial)) return false;
      location.reload();
      return true;
    } catch (error) {
      if (serial == null || valid(serial)) status(error.code === "voice-profile-in-use" ? label("profile_referenced") : error.message);
      return false;
    }
    finally {
      if (profileSaving) setProfileSaving(false);
      else if (serial == null || valid(serial)) fields.save.disabled = false;
    }
  }
  async function saveRecordingDuration() {
    if (fields.recording_duration_save.disabled || recordingDurationHasTake() || direction.dirty() || openedContext !== context()) return;
    if (pronunciationPending() || profilesDirty) {
      status(label(pronunciationPending() ? "pronunciation_pending" : "profiles_unsaved"));
      return;
    }
    var input = fields.recording_duration;
    if (!input.reportValidity()) return;
    var configuration = input.value === "" ? {} : {reference_seconds:input.valueAsNumber};
    var serial = generation;
    setProfileSaving(true); status(label("saving"));
    try {
      await request("settings", {project_token:tokens().project_token, audio_recording:configuration});
      if (valid(serial)) location.reload();
    } catch (error) {
      if (valid(serial)) status(error.message);
    } finally {
      setProfileSaving(false);
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
  function playReference(referenceId) {
    clearAudio();
    var source = url("speech-audio", {reference_id: referenceId});
    fields.audio.src = source;
    fields.playback_section.hidden = fields.audio.hidden = false;
    fields.audio.play().catch(function(error) {
      if (fields.audio.getAttribute("src") === source && error.name !== "AbortError") status(error.message);
    });
  }
  function updateVoiceCard() {
    if (!fields.profile_voice_card) return;
    var cap = capabilities && capabilities[fields.engine.value];
    var referenced = cap && selectedReference();
    fields.profile_voice_card.hidden = !referenced;
    if (!referenced) return;
    fields.profile_voice_card.replaceChildren();
    var curId = fields.reference_id ? fields.reference_id.value.trim() : "";
    var match = curId && allReferences.find(function(r) { return r.id === curId; });
    if (match) {
      var playBtn = node("button", fields.profile_voice_card, "ctl", "▶ " + label("listen_reference"));
      playBtn.type = "button";
      playBtn.addEventListener("click", function() { playReference(curId); });
    } else {
      node("span", fields.profile_voice_card, "voice-card-info", label(curId ? "reference_unavailable_help" : "no_voice_yet"));
    }
    var recordBtn = node("button", fields.profile_voice_card, "ctl", label("record_author_title"));
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
      prevBtn.addEventListener("click", function() { playReference(activeId); });
    } else {
      node("em", span, "", label("no_voice_yet"));
    }
  }
  var referenceDeleting = false;
  async function deleteLibraryRecording(referenceId, name, trigger) {
    if (!profileSettingsAvailable || referenceDeleting || voiceSaving || isRecordingVoice || recordingPending ||
        !speechReady || openedContext !== context()) return;
    if (!window.confirm(uiFormat("speech_reference_delete_confirm", {name:name}))) return;
    var sequence = openSequence, captureContext = context(), restoreFocus = document.activeElement === trigger;
    function current() { return sequence === openSequence && dialog.open && captureContext === context(); }
    referenceDeleting = true; trigger.disabled = true;
    try {
      var response = await request("audio-microphone", Object.assign(tokens(), {
        action:"delete_reference", reference_id:referenceId
      }));
      if (!current()) return;
      if (response.reference_id !== referenceId) throw new Error(label("failed"));
      if (fields.audio.getAttribute("src") === url("speech-audio", {reference_id:referenceId})) clearAudio();
      allReferences = allReferences.filter(function(item) { return item.id !== referenceId; });
      referenceOptions(fields.reference_id.value);
      renderReferenceList(allReferences); renderActiveVoiceBadge(); updateVoiceCard();
      status(label("reference_delete_done"));
      if (restoreFocus && document.activeElement === body) {
        fields.reference_list.closest("details").querySelector("summary").focus({preventScroll:true});
      }
    } catch (error) { if (current()) status(error.message); }
    finally {
      referenceDeleting = false;
      if (trigger.isConnected) trigger.disabled = false;
    }
  }
  function renderReferenceList(refs) {
    if (!fields.reference_list) return;
    fields.reference_list.replaceChildren();
    if (!refs || !refs.length) {
      node("p", fields.reference_list, "ctl-note", label("reference_empty"));
      return;
    }
    var persisted = savedSettings || settings;
    var activeProfile = persisted && persisted.selected && persisted.profiles[persisted.selected];
    var usedReferences = new Set(Object.values(persisted?.profiles || {}).map(function(profile) { return profile.reference_id; }));
    refs.forEach(function(ref, index) {
      var item = node("div", fields.reference_list, "voice-ref-item");
      var info = node("div", item, "voice-ref-info");
      var name = referenceName(ref, index);
      node("div", info, "voice-ref-text", name);
      var duration = referenceDuration(ref);
      if (duration) node("div", info, "voice-ref-meta", label("audit_duration") + ": " + duration);
      var actions = node("div", item, "row");
      var play = node("button", actions, "ctl", "▶");
      play.type = "button";
      window.LixityComponents.setControlLabel(play, label("listen_reference"));
      play.addEventListener("click", function() { playReference(ref.id); });
      var isCurrent = activeProfile && activeProfile.reference_id === ref.id;
      if (isCurrent) {
        node("span", actions, "badge", "✓ " + label("active_voice"));
      } else {
        var useBtn = node("button", actions, "ctl", label("use_as_active"));
        useBtn.type = "button";
        useBtn.addEventListener("click", async function() {
          var curProf = settings && settings.selected && settings.profiles[settings.selected];
          if (curProf && switchMode("profiles")) {
            // Populate a visible draft first. A rejected write must not change
            // the persisted active badge or hide fields that need correction.
            fields.reference_id.value = ref.id;
            profilesDirty = true;
            fields.engine.value = curProf.engine;
            var cap = profileCapability();
            if (cap.reference_supported && !cap.reference_required) {
              options(fields.voice, [], "reference");
              fields.provider_voice.value = "reference";
            } else options(fields.voice, [], curProf.voice);
            voiceControls();
            if (!await save()) updateVoiceCard();
          }
        });
      }
      if (!profileSettingsAvailable) return;
      if (usedReferences.has(ref.id)) node("span", actions, "ctl-note", label("reference_delete_in_use"));
      else {
        var shortName = referenceName(ref, index, 72);
        var remove = button(actions, "reference_delete", function() { deleteLibraryRecording(ref.id, shortName, remove); });
        remove.setAttribute("aria-label", label("reference_delete") + " · " + shortName);
      }
    });
  }
  function startRecordingTimer(limit, current, capture) {
    var started = performance.now(), checking = false;
    function clock(seconds) {
      return String(Math.floor(seconds / 60)).padStart(2, "0") + ":" + String(seconds % 60).padStart(2, "0");
    }
    function tick() {
      var elapsed = Math.floor((performance.now() - started) / 1000);
      fields.recTimer.textContent = clock(Math.min(elapsed, limit)) + " / " + clock(limit);
      if (elapsed >= limit) { stopVoiceRecording(); return; }
      if (capture && typeof capture.recordingStatus === "function" && !checking) {
        checking = true;
        capture.recordingStatus().then(function(state) {
          if (current() && desktopAudioRecording && state && (state.auto_stopped || state.recording === false)) stopVoiceRecording();
        }).catch(function() {}).finally(function() { checking = false; });
      }
    }
    fields.recBtn.disabled = false;
    actionLabel(fields.recBtn, "record_stop", "square"); fields.recBtn.classList.add("is-recording");
    fields.recBtn.dataset.help = label("record_stop_help");
    fields.recTimer.hidden = false;
    tick(); recTimerInterval = setInterval(tick, 250);
  }
  function releaseRecording() {
    if (desktopAudioRecording && window.lixityDesktop && window.lixityDesktop.audioCapture &&
        typeof window.lixityDesktop.audioCapture.cancelRecording === "function") {
      window.lixityDesktop.audioCapture.cancelRecording().catch(function() {});
    }
    desktopAudioRecording = false;
    isRecordingVoice = false; recordingPending = false;
    clearInterval(recTimerInterval); recTimerInterval = null;
    if (audioProcessor) { audioProcessor.close(); audioProcessor = null; }
    if (audioSource) { audioSource.disconnect(); audioSource = null; }
    if (audioStream) { audioStream.getTracks().forEach(function(t) { t.stop(); }); audioStream = null; }
    if (fields.takeWidget) fields.takeWidget.clearLiveAnalyser();
    if (audioCtx) { audioCtx.close().catch(function() {}); audioCtx = null; }
    fields.recBtn.disabled = !canRecordVoice();
    actionLabel(fields.recBtn, "record_start", "mic");
    fields.recBtn.classList.remove("is-recording");
    fields.recBtn.dataset.help = label("record_help");
    fields.recTimer.hidden = true;
    fields.promptControls.forEach(function(el) { el.disabled = false; });
    fields.saveVoiceBtn.disabled = !takeValid;
    recordingFeedback("idle");
  }
  async function startVoiceRecording() {
    if (!canRecordVoice() || recordingPending || isRecordingVoice || voiceSaving) return;
    var seconds = referenceRecording.duration_seconds;
    var spoken = sampleVariant === "custom" ? fields.customTextarea.value.trim() : fields.promptText.textContent.trim();
    if (!spoken) {
      recordingDiagnostic("preflight", "InvalidStateError");
      status(label("transcript_help")); recordingFeedback("failed", label("transcript_help")); return;
    }
    var desktopCapture = window.lixityDesktop && window.lixityDesktop.audioCapture &&
      typeof window.lixityDesktop.audioCapture.startRecording === "function" ? window.lixityDesktop.audioCapture : null;
    if (!desktopCapture && (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== "function")) {
      recordingDiagnostic("preflight", "NotSupportedError");
      status(label("mic_unavailable")); recordingFeedback("failed", label("mic_unavailable")); return;
    }
    var sequence = ++recordingSequence, captureContext = context(), refocus = document.activeElement === fields.recBtn;
    function current() {
      return sequence === recordingSequence && dialog.open && mode === "reference" && captureContext === context();
    }
    function restoreRecordFocus() {
      if (refocus && current() && document.activeElement === body) fields.recBtn.focus({preventScroll:true});
    }
    recordingPending = true; fields.recBtn.disabled = true; status(label("mic_pending"));
    recordingFeedback("busy");
    if (desktopCapture) {
      try {
        var preferredDevice = nativeMicrophoneInventory() ? preferredMicrophone || fields.microphone_device.value || null : null;
        var nativeStatus = await desktopCapture.startRecording(preferredDevice, "author-voice.wav", seconds);
        if (!current()) {
          desktopCapture.cancelRecording().catch(function() {});
          return;
        }
        desktopAudioRecording = true; isRecordingVoice = true; recordingPending = false;
        clearVoiceTake(); takeTokens = tokens();
        takeTranscript = spoken;
        fields.promptControls.forEach(function(el) { el.disabled = true; });
        fields.audio.pause(); fields.takeCard.hidden = false;
        var nativeLimit = nativeStatus?.max_duration_seconds;
        startRecordingTimer(Number.isSafeInteger(nativeLimit) && nativeLimit > 0 ?
          Math.min(nativeLimit, seconds) : seconds, current, desktopCapture);
        restoreRecordFocus();
        status(label("record_running"));
        recordingFeedback("recording");
        return;
      } catch (err) {
        if (sequence !== recordingSequence) return;
        recordingDiagnostic("microphone_request", err && err.name);
        releaseRecording();
        restoreRecordFocus();
        status(label("mic_failed"));
        recordingFeedback("failed", label("mic_failed"));
        return;
      }
    }
    var stage = "audio_context_create";
    try {
      var AudioCtxClass = window.AudioContext || window.webkitAudioContext;
      audioCtx = new AudioCtxClass({sampleRate: referenceFormat.sample_rate_hz});
      stage = "audio_context_resume";
      await audioCtx.resume();
      if (!current()) return;
      stage = "microphone_request";
      var stream = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false}});
      if (!current()) {
        stream.getTracks().forEach(function(t) { t.stop(); }); return;
      }
      audioStream = stream;
      stage = "audio_source_create";
      audioSource = audioCtx.createMediaStreamSource(stream);
      stage = "capture_processor_create";
      var capture = await window.LixityAudioTake.openPcmCapture(audioCtx, function(samples) {
        if (!isRecordingVoice || !current()) return;
        var limit = seconds * audioCtx.sampleRate;
        var remaining = limit - totalRecordedSamples;
        if (remaining <= 0) return;
        var chunk = samples.subarray(0, remaining);
        recordedChunks.push(chunk); totalRecordedSamples += chunk.length;
        if (totalRecordedSamples >= limit) stopVoiceRecording();
      }, function() {
        if (!current()) return;
        recordingDiagnostic("capture_processor_runtime", "OperationError");
        releaseRecording();
        status(label("mic_failed")); recordingFeedback("failed", label("mic_failed"));
      });
      if (!current()) {
        capture.close();
        if (sequence === recordingSequence) releaseRecording();
        return;
      }
      audioProcessor = capture;
      stage = "analyser_create";
      var analyser = audioCtx.createAnalyser(); analyser.fftSize = 256; audioSource.connect(analyser);
      recordedChunks = []; totalRecordedSamples = 0; isRecordingVoice = true; recordingPending = false;
      clearVoiceTake(); takeTokens = tokens();
      takeTranscript = spoken;
      fields.promptControls.forEach(function(el) { el.disabled = true; });
      fields.audio.pause(); fields.takeCard.hidden = false;
      fields.takeWidget.setLiveAnalyser(analyser);
      stage = "capture_connect";
      audioProcessor.connect(audioSource);
      startRecordingTimer(seconds, current);
      restoreRecordFocus();
      status(label("record_running"));
      recordingFeedback("recording");
    } catch (err) {
      if (sequence !== recordingSequence) return;
      recordingDiagnostic(stage, err && err.name);
      releaseRecording();
      restoreRecordFocus();
      var key = stage !== "microphone_request" ? "mic_failed" :
        ["NotAllowedError", "PermissionDeniedError", "SecurityError"].includes(err && err.name) ? "mic_permission" :
        err && err.name === "NotFoundError" ? "mic_missing" : err && err.name === "NotReadableError" ? "mic_busy" : "mic_failed";
      status(label(key));
      recordingFeedback("failed", label(key));
    }
  }
  function presentRecordedTake(take, bound) {
    voiceSaving = false;
    presentImportedTake(take, bound);
    recordingFeedback("recorded");
    var reason = window.LixityAudioTake.referenceEligibility(take, referenceFormat).reason;
    if (reason === "format" || reason === "duration") {
      recordingDiagnostic("capture_complete", reason === "format" ? "NotSupportedError" : "InvalidStateError");
    } else {
      window.LixityLog?.audioClient?.("author_recording_ready");
    }
  }
  async function stopVoiceRecording() {
    if (!isRecordingVoice) return;
    if (desktopAudioRecording) {
      desktopAudioRecording = false;
      var desktopSequence = openSequence, desktopSerial = recordingSequence, desktopBound = Object.assign({}, takeTokens);
      releaseRecording();
      voiceSaving = true; fields.recBtn.disabled = fields.saveVoiceBtn.disabled = true;
      try {
        var raw = await window.lixityDesktop.audioCapture.stopRecording();
        var blob = window.LixityDesktopBridge && typeof window.LixityDesktopBridge.decodeBase64Wav === "function"
          ? window.LixityDesktopBridge.decodeBase64Wav(raw)
          : new Blob([Uint8Array.from(atob(raw.wav_base64), function(c) { return c.charCodeAt(0); })], {type: "audio/wav"});
        var desktopTake = await window.LixityAudioTake.create(blob,
          {filename: (raw && raw.filename) || "author-voice.wav", transcript: takeTranscript, transcript_status: takeTranscript ? "draft" : "missing"});
        if (desktopSequence !== openSequence || desktopSerial !== recordingSequence || !dialog.open || !matchingTakeContext(desktopBound)) return;
        presentRecordedTake(desktopTake, desktopBound);
      } catch (error) {
        if (desktopSequence === openSequence && desktopSerial === recordingSequence && dialog.open) {
          recordingDiagnostic("capture_complete", error && error.name);
          status(label("take_invalid")); recordingFeedback("failed", label("take_invalid"), "record_state_recorded");
        }
      } finally {
        voiceSaving = false;
        if (desktopSequence === openSequence && dialog.open) { fields.recBtn.disabled = !canRecordVoice(); fields.saveVoiceBtn.disabled = !takeValid; }
      }
      return;
    }
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
      presentRecordedTake(take, bound);
    } catch (error) {
      if (sequence === openSequence && serial === recordingSequence && dialog.open) {
        recordingDiagnostic("capture_complete", error && error.name);
        status(label("take_invalid")); recordingFeedback("failed", label("take_invalid"), "record_state_recorded");
      }
    } finally {
      voiceSaving = false;
      if (sequence === openSequence && dialog.open) { fields.recBtn.disabled = !canRecordVoice(); fields.saveVoiceBtn.disabled = !takeValid; }
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
      var eligibility = window.LixityAudioTake.referenceEligibility(importedTake, referenceFormat);
      takeValid = eligibility.eligible;
      fields.takeNotice.textContent = eligibility.reason === "duration" || eligibility.reason === "transcript" ?
        referenceText("take_" + eligibility.reason) : label(eligibility.reason ? "take_" + eligibility.reason : "take_ready");
    } catch (_) { takeValid = false; fields.takeNotice.textContent = label("take_invalid"); }
    fields.takeNotice.hidden = false;
    fields.saveVoiceBtn.disabled = !takeValid || voiceSaving || !matchingTakeContext(takeTokens);
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
  function clearVoiceTake() {
    ++takeImportSequence;
    importedTake = null; trimSource = null; takeTokens = null;
    lastRecordedWavBlob = null; takeValid = false; takeTranscript = "";
    fields.takePlayer.pause();
    fields.takePlayer.removeAttribute("src"); fields.takePlayer.load();
    if (takeUrl) { URL.revokeObjectURL(takeUrl); takeUrl = null; }
    fields.takeCard.hidden = fields.takeExports.hidden = fields.take_trim.hidden = fields.takeDiscard.hidden = true;
    fields.takeStats.textContent = fields.takeTranscriptInput.value = "";
    fields.takeTranscriptInput.closest("details").open = false;
    fields.take_confirmed.checked = false;
    fields.take_confirmed.closest("label").hidden = fields.takeNotice.hidden = true;
    fields.saveVoiceBtn.disabled = true;
    updateRecordingDuration();
  }
  function discardVoiceTake() {
    if (!importedTake || isRecordingVoice || recordingPending) return;
    if (voiceSaving) { status(label("saving")); return; }
    clearVoiceTake();
    fields.upload_voice_file.value = fields.take_metadata_file.value = fields.upload_voice_transcript.value = "";
    recordingFeedback("idle");
    status(label("take_discarded"));
    (fields.recBtn.disabled ? fields.heading : fields.recBtn).focus();
  }
  function presentImportedTake(take, bound, original) {
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
    fields.takeCard.hidden = fields.takeExports.hidden = fields.takeDiscard.hidden = false;
    refreshImportedTake(false);
    trimSource = original || null;
    fields.take_trim.hidden = !trimSource && (!referenceFormat || !window.LixityAudioTake.matchesReferenceFormat(audio, referenceFormat) ||
      audio.duration_seconds <= referenceFormat.min_seconds || audio.duration_seconds > trimLimitSeconds);
    fields.take_trim.open = Boolean(trimSource);
    fields.trim_controls.hidden = Boolean(trimSource);
    fields.trim_restore.hidden = !trimSource;
    fields.take_trim_start.value = "0";
    fields.take_trim_end.value = referenceFormat ? String(Math.floor(Math.min(referenceFormat.max_seconds, audio.duration_seconds) * 1000) / 1000) : "";
    window.LixityComponents.setStatus(fields.trim_status, "");
    updateRecordingDuration();
    status(label("take_loaded"));
  }
  function audioBase64(blob) {
    return new Promise(function(resolve, reject) {
      var reader = new FileReader();
      reader.onload = function() { resolve(String(reader.result).split(",")[1]); };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }
  async function trimVoiceTake() {
    if (!referenceFormat || !trimLimitSeconds || !importedTake || trimSource || voiceSaving || isRecordingVoice || recordingPending || !matchingTakeContext(takeTokens)) return;
    var prior = importedTake, bound = Object.assign({}, takeTokens), sequence = openSequence;
    var audio = prior.metadata.audio, rate = audio.sample_rate_hz, feedback = fields.trim_status;
    var start = Math.round(fields.take_trim_start.valueAsNumber * rate), end = Math.round(fields.take_trim_end.valueAsNumber * rate);
    if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end > audio.frames ||
        end - start < rate * referenceFormat.min_seconds || end - start > rate * referenceFormat.max_seconds ||
        (start === 0 && end === audio.frames)) {
      window.LixityComponents.setStatus(feedback, referenceText("take_trim_range"), "err");
      return;
    }
    function current() { return sequence === openSequence && dialog.open && matchingTakeContext(bound); }
    voiceSaving = true;
    [fields.recBtn, fields.saveVoiceBtn, fields.take_confirmed, fields.takeTranscriptInput,
      fields.take_trim_start, fields.take_trim_end].forEach(function(input) { input.disabled = true; });
    window.LixityComponents.setButtonPending(fields.trim_apply, true);
    window.LixityComponents.setStatus(feedback, label("take_trim_pending"), "loading");
    try {
      var encoded = await audioBase64(prior.blob);
      if (!current()) return;
      var res = await request("audio-take-trim", Object.assign({}, bound, {audio:encoded, start_frame:start, end_frame:end}));
      if (!current()) return;
      var bytes = Uint8Array.from(atob(res.audio), function(c) { return c.charCodeAt(0); });
      var name = audio.filename.slice(0, -4).slice(0, 168) + "-excerpt.wav";
      var take = await window.LixityAudioTake.create(new Blob([bytes], {type:"audio/wav"}), {filename:name});
      if (!current()) return;
      if (take.metadata.audio.frames !== end - start) throw new Error("Unexpected excerpt length");
      voiceSaving = false;
      presentImportedTake(take, bound, prior);
      window.LixityComponents.setStatus(feedback, label("take_trim_ready"), "ok");
      fields.takeTranscriptInput.disabled = false;
      fields.takeTranscriptInput.focus({preventScroll:true});
    } catch (_) {
      if (current()) window.LixityComponents.setStatus(feedback, label("take_trim_failed"), "err");
    } finally {
      voiceSaving = false;
      [fields.take_confirmed, fields.takeTranscriptInput, fields.take_trim_start,
        fields.take_trim_end].forEach(function(input) { input.disabled = false; });
      window.LixityComponents.setButtonPending(fields.trim_apply, false);
      if (current()) { fields.recBtn.disabled = !canRecordVoice(); fields.saveVoiceBtn.disabled = !takeValid; }
    }
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
    var attempt = {};
    voiceSaving = true; fields.recBtn.disabled = true;
    if (fields.saveVoiceBtn) fields.saveVoiceBtn.disabled = true;
    status(label("saving"));
    try {
      var b64Wav = await audioBase64(savedBlob);
      if (sequence !== openSequence || !dialog.open || captureContext !== context()) return;
      if (!spoken) throw new Error(label("transcript_help"));
      var res = await request("audio-microphone", Object.assign({}, bound, {
        action: "save_reference",
        audio: b64Wav,
        transcript: spoken,
        profile_id: (settings && settings.selected) || "default"
      }), null, attempt);
      if (sequence !== openSequence || !dialog.open || captureContext !== context()) return;
      if (referenceSaved(res)) clearVoiceTake();
    } catch (err) {
      if (sequence === openSequence && dialog.open && captureContext === context()) {
        if (attempt.status !== 409) window.LixityLog?.audioClient?.("reference_save_failed", attempt.id);
        status(err.message);
      }
    }
    finally {
      voiceSaving = false;
      updateRecordingDuration();
      if (sequence === openSequence && dialog.open) { fields.recBtn.disabled = !canRecordVoice(); if (fields.saveVoiceBtn) fields.saveVoiceBtn.disabled = !takeValid; }
    }
  }
  function switchMode(newMode, initializing) {
    if (newMode === mode && !initializing) return true;
    if (profileSaving || voiceSaving || (direction && direction.busy())) return false;
    var draft = profileDraftMessage();
    if (draft) { status(label(draft)); return false; }
    if (direction && direction.dirty() && newMode !== "reader" && newMode !== "output" && newMode !== mode) {
      status(label("direction_switch_first"));
      return;
    }
    if (newMode !== "reference" && (isRecordingVoice || recordingPending)) {
      ++recordingSequence;
      if (isRecordingVoice) stopVoiceRecording(); else releaseRecording();
    }
    fields.audio.pause(); fields.takePlayer.pause();
    if (!initializing && inReader() !== Boolean(surfaces[newMode].manuscript)) clearAudio();
    mode = newMode;
    Object.entries(fields.tabs).forEach(function([key, tab]) {
      var active = key === mode;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", String(active));
    });
    fields.panel.setAttribute("aria-labelledby", fields.tabs[mode].id);
    fields.heading.textContent = label(surfaces[mode].title);
    updateRecordingDuration();
    arrangeSections();
    if (!initializing) presentSpeechSurface();
    refreshChapterAudio();
    if (mode === "reference") renderActiveVoiceBadge();
    fields.panel.scrollTop = 0;
    status(mode === "output" && direction.dirty() ? label("direction_output_draft") : speechLoadMessage);
    if (!initializing && mode === "microphone") void refreshMicrophone();
    return true;
  }
  function build() {
    dialog = node("dialog", body, "lixity-modal"); dialog.id = "modal-speech"; dialog.setAttribute("aria-labelledby", "speech-title");
    var card = node("div", dialog, "modal-card"), header = node("div", card, "modal-header");
    fields.heading = node("h3", header, "", label("title")); fields.heading.id = "speech-title";
    fields.heading.tabIndex = -1;
    var close = button(header, "close", closeAudioSurface);
    close.className = "modal-close";
    close.textContent = "✕";
    var closeLabel = uiLabel("modal_close");
    if (!closeLabel || closeLabel === "modal_close") closeLabel = label("close");
    close.setAttribute("aria-label", closeLabel);
    close.setAttribute("title", closeLabel);
    close.setAttribute("aria-keyshortcuts", "Escape");
    fields.project_audio_tabs = node("div", card, "modal-tabs speech-project-tabs");
    fields.reader_audio_tabs = node("div", card, "modal-tabs speech-reader-tabs");
    fields.tabs = {};
    fields.status = node("p", card, "ctl-status modal-intro"); fields.status.id = "speech-status"; fields.status.setAttribute("role", "status"); fields.status.setAttribute("aria-live", "polite");
    var content = node("div", card, "modal-body"); fields.panel = content;
    content.id = "speech-panel"; content.setAttribute("role", "tabpanel");
    function setupTabs(container, manuscript) {
      container.setAttribute("role", "tablist");
      container.setAttribute("aria-label", label("action_title"));
      Object.entries(surfaces).forEach(function([key, surface]) {
        if (Boolean(surface.manuscript) !== manuscript) return;
        var tab = node("button", container, "modal-tab-btn");
        actionLabel(tab, surface.label, surface.icon);
        tab.type = "button"; tab.id = "speech-tab-" + surface.tab;
        tab.setAttribute("role", "tab"); tab.setAttribute("aria-controls", content.id);
        tab.addEventListener("click", function() { switchMode(key); });
        fields.tabs[key] = tab;
      });
      initKeyboardTabs(container, '[role="tab"]', false);
    }
    setupTabs(fields.project_audio_tabs, false);
    setupTabs(fields.reader_audio_tabs, true);
    fields.tabs.output.dataset.speechAction = "output_title";
    fields.reader_shortcut = node("div", content, "row speech-project-shortcut");
    button(fields.reader_shortcut, "go_to_manuscript_audio", function() {
      if (switchMode("reader")) fields.export_scope.value = "preview";
    }, "headphones").id = "speech-tab-reader";
    fields.reader_context = node("div", content, "ctl-group speech-reader-context");
    fields.project_profile_summary = node("div", fields.reader_context, "row speech-profile-summary");
    fields.project_profile_name = node("p", fields.project_profile_summary, "ctl-note");
    fields.project_profile_name.id = "speech-project-profile";
    button(fields.project_profile_summary, "profiles_title", function() {
      if (!closeAudioSurface()) return;
      switchActiveView("project", true);
      fields.project_profiles_action.focus({preventScroll:true});
      open("profiles");
    }, "sliders").id = "speech-edit-project-voice";

    fields.reference_section = node("div", content, "author-voice-studio");
    fields.reference_section.hidden = true;
    var introCard = node("div", fields.reference_section, "voice-studio-intro");
    node("p", introCard, "ctl-note", label("record_author_intro"));
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
      var custom = sampleVariant === "custom";
      fields.promptText.hidden = custom;
      fields.customTextarea.hidden = !custom;
      fields.promptText.textContent = calibrationTexts?.[sampleVariant] || "";
      if (custom && !fields.customTextarea.value) fields.customTextarea.value = calibrationTexts?.short || "";
    }
    [[btnFull, "phonetic"], [btnShort, "short"], [btnCustom, "custom"]].forEach(function([button, variant]) {
      button.addEventListener("click", function() { sampleVariant = variant; updatePromptText(); });
    });
    fields.updatePromptText = updatePromptText;
    fields.promptControls = [btnFull, btnShort, btnCustom, fields.customTextarea];
    fields.customTextarea.setAttribute("aria-label", label("sample_custom"));
    fields.promptControls.forEach(function(el) { el.dataset.help = label("transcript_help"); });
    updatePromptText();
    var recControls = node("div", fields.reference_section, "voice-record-controls");
    fields.recLimit = node("p", fields.reference_section, "ctl-note");
    fields.recLimit.id = "speech-record-limit"; fields.recLimit.hidden = true;
    recControls.before(fields.recLimit);
    fields.recBtn = node("button", recControls, "ctl primary voice-rec-btn");
    actionLabel(fields.recBtn, "record_start", "mic");
    fields.recBtn.type = "button"; addHelp(fields.recBtn, "record_start");
    fields.recBtn.setAttribute("aria-describedby", fields.recLimit.id);
    fields.recTimer = node("span", recControls, "voice-rec-timer");
    fields.recTimer.setAttribute("role", "timer");
    fields.recTimer.setAttribute("aria-label", label("record_elapsed"));
    fields.recTimer.hidden = true;
    fields.recState = node("span", recControls, "voice-record-state");
    fields.recState.setAttribute("role", "status"); fields.recState.setAttribute("aria-live", "polite"); fields.recState.hidden = true;
    button(recControls, "recording_duration_edit", function() {
      if (recordingDurationHasTake()) { status(label("recording_duration_finish_take")); return; }
      fields.recording_defaults_section.open = true;
      fields.recording_duration.focus();
    }, "settings");
    fields.recError = node("p", fields.reference_section, "voice-record-error");
    fields.recError.id = "speech-record-error"; fields.recError.hidden = true;
    fields.takeCard = node("div", fields.reference_section, "voice-take-card");
    fields.takeCard.hidden = true;
    fields.takePlayer = node("audio", fields.takeCard, "media-player");
    fields.takePlayer.controls = true; fields.takeWidget = window.createSpeechPlayer(fields.takePlayer, {label: label, onError: status});
    fields.takeStats = node("div", fields.takeCard, "voice-take-stats");
    fields.take_trim = node("details", fields.takeCard, "settings-section");
    fields.take_trim.id = "speech-take-trim";
    fields.take_trim.hidden = true;
    node("summary", fields.take_trim, "", label("take_trim_title"));
    fields.trim_controls = node("div", fields.take_trim, "ctl-group");
    node("p", fields.trim_controls, "ctl-note", label("take_trim_help"));
    var trimInputs = node("div", fields.trim_controls, "settings-grid");
    [field(trimInputs, "take_trim_start", "number"), field(trimInputs, "take_trim_end", "number")].forEach(function(input) {
      input.min = "0"; input.step = "any";
    });
    fields.trim_apply = button(node("div", fields.trim_controls, "row"), "take_trim_apply", trimVoiceTake);
    fields.trim_restore = button(node("div", fields.take_trim, "row"), "take_trim_restore", function() {
      if (!trimSource || voiceSaving || isRecordingVoice || recordingPending || !matchingTakeContext(takeTokens)) return;
      presentImportedTake(trimSource, takeTokens);
      fields.take_trim.querySelector("summary").focus({preventScroll:true});
    });
    fields.trim_status = node("p", fields.take_trim, "ctl-status");
    fields.trim_status.id = "speech-take-trim-status";
    fields.trim_status.setAttribute("role", "status");
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
    var takeActions = node("div", fields.takeCard, "row");
    fields.saveVoiceBtn = node("button", takeActions, "ctl primary voice-save-btn");
    actionLabel(fields.saveVoiceBtn, "record_save", "save");
    fields.saveVoiceBtn.type = "button"; addHelp(fields.saveVoiceBtn, "record_save");
    fields.takeDiscard = button(takeActions, "take_discard", discardVoiceTake);
    fields.takeDiscard.hidden = true;
    fields.recBtn.addEventListener("click", function() {
      if (!isRecordingVoice) startVoiceRecording();
      else stopVoiceRecording();
    });
    fields.saveVoiceBtn.addEventListener("click", saveVoiceTake);
    var librarySec = node("details", fields.reference_section, "settings-section voice-library-section");
    node("summary", librarySec, "", label("choose_from_library"));
    fields.reference_list = node("div", librarySec, "voice-reference-list");
    var uploadSec = node("details", fields.reference_section, "settings-section voice-upload-section");
    node("summary", uploadSec, "", label("upload_wav"));
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
        if (sequence === openSequence && dialog.open) { uploadBtn.disabled = false; fields.recBtn.disabled = !canRecordVoice(); }
      }
    });

    fields.recording_defaults_section = node("details", fields.reference_section, "settings-section panel-disclosure speech-recording-defaults");
    var recordingHeading = node("summary", fields.recording_defaults_section, "", label("recording_duration_title"));
    recordingHeading.id = "speech-recording-defaults-heading";
    fields.recording_defaults = node("fieldset", fields.recording_defaults_section, "ctl-group");
    fields.recording_defaults.setAttribute("aria-labelledby", recordingHeading.id);
    var recordingDuration = field(fields.recording_defaults, "recording_duration", "number");
    recordingDuration.step = "1";
    fields.recording_duration_hint = node("p", fields.recording_defaults, "ctl-note");
    fields.recording_duration_hint.id = "speech-recording-duration-hint";
    fields.recording_duration_error = node("p", fields.recording_defaults, "ctl-note");
    fields.recording_duration_error.id = "speech-recording-duration-error";
    fields.recording_duration_error.setAttribute("aria-live", "polite");
    recordingDuration.setAttribute("aria-describedby", fields.recording_duration_hint.id + " " + fields.recording_duration_error.id);
    var recordingActions = node("div", fields.recording_defaults, "row");
    fields.recording_duration_save = button(recordingActions, "recording_duration_save", saveRecordingDuration);
    fields.recording_duration_save.classList.add("primary");
    fields.recording_duration_discard = button(recordingActions, "recording_duration_discard", function() {
      prepareRecordingDuration(); status("");
    });
    recordingDuration.addEventListener("input", function() {
      updateRecordingDuration();
      status(recordingDurationChanged() ? label("recording_duration_unsaved") : "");
    });
    fields.schema_section = node("section", content, "settings-section speech-profile-schema");
    node("h4", fields.schema_section, "section-heading", label("schema_title"));
    node("p", fields.schema_section, "ctl-note", label("schema_hint"));
    fields.schema_review = node("p", fields.schema_section, "ctl-note"); fields.schema_review.id = "speech-schema-review"; fields.schema_review.hidden = true;
    var schemaActions = node("div", fields.schema_section, "row");
    fields.schema_preview = button(schemaActions, "schema_preview", async function() {
      if (profileSaving) return;
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
        fields.schema_apply.focus({preventScroll:true});
      } catch (error) { if (sequence === openSequence && dialog.open) status(error.message); }
      finally { if (sequence === openSequence) fields.schema_preview.disabled = false; }
    });
    fields.schema_apply = button(schemaActions, "schema_apply", async function() {
      if (profileSaving) return;
      if (direction.dirty()) { status(label("direction_switch_first")); return; }
      var draft = profileDraftMessage(), serial = generation, applied = false;
      setProfileSaving(true);
      fields.schema_preview.disabled = fields.schema_apply.disabled = true;
      status(label("saving"));
      try {
        var result = await request("audio-schema", Object.assign(tokens(), {apply: true, snapshot: fields.schema_apply.dataset.snapshot, schema_version: currentAudioSchema}));
        if (!valid(serial)) return;
        if (!draft) { location.reload(); return; }
        // The review covers the saved settings. Keep the draft in the form
        // and use the committed settings as the new discard baseline.
        savedSettings = result.settings;
        settings.schema_version = savedSettings.schema_version;
        settingsForm.dataset.projectToken = result.project_token;
        syncManuscriptProjectToken(result.manuscript_project_token);
        openedContext = context();
        schemaReviewAvailable = false;
        fields.schema_review.hidden = fields.schema_apply.hidden = true;
        arrangeSections();
        renderPronunciations();
        status(label("schema_applied_draft"));
        applied = true;
      } catch (error) {
        if (valid(serial)) status(error.message);
      } finally {
        fields.schema_preview.disabled = fields.schema_apply.disabled = false;
        setProfileSaving(false);
        if (applied) (pronunciationPending() ? fields.pronunciation_term : fields.save).focus();
      }
    });
    fields.schema_apply.hidden = true;
    fields.schema_apply.classList.add("primary");
    fields.profile_row = node("div", content, "speech-profile-picker");
    choiceField(fields.profile_row, "profile");
    var profileActions = node("div", fields.profile_row, "speech-profile-actions");
    fields.create = button(profileActions, "create", create);
    fields.remove_profile = button(profileActions, "remove_profile", removeProfile);
    field(content, "target", "select"); fields.target.closest("label").hidden = true;
    var targetHint = node("span", fields.target.closest("label"), "ctl-note", label("target_scope"));
    targetHint.id = "speech-target-hint"; fields.target.setAttribute("aria-describedby", targetHint.id);
    fields.target.addEventListener("change", function() {
      invalidate(); updateRuntimeHint();
    });
    field(content, "worker_target", "select").addEventListener("change", updateWorkerStatus);
    fields.worker_status = node("p", content, "ctl-note"); fields.worker_status.id = "speech-worker-status";
    fields.worker_status.setAttribute("aria-live", "polite");
    fields.worker_guide = node("a", content, "ctl-link", label("worker_guide"));
    fields.worker_guide.id = "speech-worker-guide"; fields.worker_guide.target = "_blank";
    fields.worker_guide.rel = "noopener noreferrer"; fields.worker_guide.hidden = true;
    fields.worker_refresh = button(content, "worker_refresh", async function() {
      var sequence = openSequence, selectedEngine = fields.engine && fields.engine.value;
      fields.worker_refresh.disabled = true;
      function currentOpen() { return sequence === openSequence && dialog.open && openedContext === context(); }
      try {
        var data = await request("speech", null, selectedEngine ? {engine: selectedEngine} : undefined);
        if (currentOpen()) applyWorkerInventory(data.workers);
      }
      catch (_) { if (currentOpen()) { workers = null; updateWorkerStatus(); updateRuntimeHint(); } }
      finally { if (currentOpen()) fields.worker_refresh.disabled = false; }
    });
    fields.editor = node("fieldset", content, "settings-section speech-profile-editor");
    fields.editor.setAttribute("aria-label", label("profiles_title"));
    var voiceSettings = node("fieldset", fields.editor, "speech-profile-voice");
    node("legend", voiceSettings, "", label("voice_settings"));
    var grid = node("div", voiceSettings, "settings-grid speech-profile-voice-grid");
    field(grid, "name").maxLength = 100; fields.name.required = true;
    field(grid, "engine", "select");
    ["language", "voice"].forEach(function(key) { choiceField(grid, key); });
    ["base_url", "provider_model", "api_key_env", "provider_voice", "provider_language"].forEach(function(key) {
      var input = field(grid, key, key === "base_url" ? "url" : "text"); input.maxLength = key === "base_url" ? 2048 : 200;
      input.required = key !== "api_key_env";
    });
    field(grid, "supports_instructions", "checkbox").addEventListener("change", voiceControls);
    fields.model_conflict = node("p", voiceSettings, "ctl-note"); fields.model_conflict.setAttribute("aria-live", "polite"); fields.model_conflict.hidden = true;
    field(voiceSettings, "voice_description", "textarea").maxLength = 2000;
    fields.design_hint = node("p", voiceSettings, "ctl-note", label("design_hint"));
    fields.design_hint.id = "speech-design-hint"; fields.voice_description.setAttribute("aria-describedby", fields.design_hint.id);
    var reference = field(voiceSettings, "reference_id", "select");
    fields.reference_hint = node("p", voiceSettings, "ctl-note", label("reference_hint"));
    fields.reference_hint.id = "speech-reference-hint"; reference.setAttribute("aria-describedby", fields.reference_hint.id);
    fields.profile_voice_card = node("div", voiceSettings, "voice-active-card");
    fields.profile_voice_card.hidden = true;
    var delivery = node("fieldset", fields.editor, "speech-profile-delivery");
    node("legend", delivery, "", label("delivery"));
    var deliveryGrid = node("div", delivery, "settings-grid speech-profile-delivery-grid");
    var speed = field(deliveryGrid, "speed", "number"); speed.step = "any"; speed.required = true;
    var speedField = speed.closest("label");
    fields.speed_label = speedField.querySelector(".form-label");
    fields.speed_label.id = "speech-speed-label";
    fields.speed_hint = node("span", speedField, "ctl-note");
    fields.speed_hint.id = "speech-speed-hint";
    speed.setAttribute("aria-labelledby", fields.speed_label.id);
    speed.setAttribute("aria-describedby", fields.speed_hint.id);
    ["paragraph_pause", "scene_pause"].forEach(function(key) { field(deliveryGrid, key, "number").required = true; });
    field(delivery, "instructions", "textarea").maxLength = 2000;
    fields.instructions_note = node("p", delivery, "ctl-note", label("instructions_export_only"));
    fields.instructions_note.id = "speech-instructions-note";
    fields.instructions.setAttribute("aria-describedby", fields.instructions_note.id);
    profileProsody = createProsody(delivery, "prosody-", function() { profilesDirty = true; invalidate(); }, false);
    [fields.voice_description, fields.reference_id, fields.instructions].forEach(function(input) {
      input.addEventListener("input", function() { updateModelFields(); updateVoiceCard(); });
    });
    var lexicon = node("details", content, "settings-section panel-disclosure speech-profile-utilities"); lexicon.id = "speech-lexicon";
    fields.lexicon_section = lexicon;
    node("summary", lexicon, "", label("pronunciations"));
    var scope = field(lexicon, "pronunciation_scope", "select");
    options(scope, [["project", label("pronunciation_scope_project")], ["profile", label("pronunciation_scope_profile")]], pronunciationScope);
    scope.addEventListener("change", function() {
      if (pronunciationPending()) {
        scope.value = pronunciationScope;
        status(label("pronunciation_pending")); return;
      }
      pronunciationScope = scope.value;
      fields.pronunciation_search.value = "";
      renderPronunciations();
    });
    fields.pronunciation_upgrade = node("div", lexicon, "row");
    fields.pronunciation_upgrade.hidden = true;
    node("p", fields.pronunciation_upgrade, "ctl-note", label("pronunciation_schema_required"));
    button(fields.pronunciation_upgrade, "pronunciation_schema_review", function() {
      fields.schema_preview.focus();
      fields.schema_preview.click();
    });
    var pronunciationControls = node("div", lexicon);
    fields.pronunciation_controls = pronunciationControls;
    fields.pronunciation_project_hint = node("p", pronunciationControls, "ctl-note", label("pronunciation_project_hint"));
    fields.pronunciation_project_hint.id = "speech-pronunciation-project-hint";
    var searchRow = node("div", pronunciationControls, "row"), search = field(searchRow, "pronunciation_search", "search");
    search.addEventListener("input", renderPronunciations);
    fields.pronunciation_list = node("ul", pronunciationControls, "pronunciation-list");
    fields.pronunciation_list.setAttribute("aria-label", label("pronunciations"));
    fields.pronunciation_empty = node("p", pronunciationControls, "ctl-note pronunciation-empty");
    fields.pronunciation_empty.hidden = true; fields.pronunciation_empty.setAttribute("aria-live", "polite");
    var pronunciationEditor = node("div", pronunciationControls, "settings-grid");
    var termInput = field(pronunciationEditor, "pronunciation_term");
    termInput.maxLength = 100;
    var spokenInput = field(pronunciationEditor, "pronunciation_spoken");
    spokenInput.maxLength = 300;
    var ipaInput = field(pronunciationEditor, "pronunciation_ipa");
    ipaInput.maxLength = 300;
    ipaInput.setAttribute("aria-describedby", fields.pronunciation_project_hint.id);
    [termInput, spokenInput, ipaInput].forEach(function(input) {
      input.spellcheck = false;
      input.setAttribute("autocapitalize", "off");
    });
    var pronunciationActions = node("div", pronunciationControls, "row");
    button(pronunciationActions, "pronunciation_apply", applyPronunciation);
    button(pronunciationActions, "pronunciation_discard", function() {
      clearPronunciationDraft();
      fields.pronunciation_term.focus();
      status(profilesDirty ? label("profiles_unsaved") : "");
    });
    var rawList = node("details", pronunciationControls, "settings-advanced");
    fields.pronunciation_bulk = rawList;
    node("summary", rawList, "", label("pronunciation_bulk"));
    field(rawList, "pronunciations", "textarea").addEventListener("input", renderPronunciations);
    node("p", rawList, "ctl-note", label("pronunciation_hint"));
    node("p", rawList, "ctl-note", label("pronunciation_bulk_special"));
    fields.phonemes_section = node("details", content, "settings-section panel-disclosure speech-profile-utilities"); fields.phonemes_section.id = "speech-phonemes-section";
    node("summary", fields.phonemes_section, "", label("phonemes"));
    field(fields.phonemes_section, "phonemes", "textarea").rows = 5;
    fields.phonemes.placeholder = "Vogel=ˈfoːɡəl";
    var phonemeHelp = node("p", fields.phonemes_section, "ctl-note", label("phonemes_help"));
    phonemeHelp.id = "speech-phonemes-help"; fields.phonemes.setAttribute("aria-describedby", phonemeHelp.id);
    fields.phonemes.addEventListener("input", updateModelFields);
    field(fields.reader_context, "chapter", "select");
    direction = window.LixitySpeechDirection(content, {
      node:node, field:field, button:button, options:options, label:label, request:request,
      status:status, invalidate:invalidate, tokens:tokens, createProsody:createProsody, applyPauseBounds:applyPauseBounds,
      profileSupport:profileSupport,
      current:function() { return dialog.open && openedContext === context(); },
      selected:function(p) {
        paragraph={identity:p.anchor,chapter:p.chapter}; fields.chapter.value=String(p.chapter);
        if (speechDocked) placeReaderSpeech(sourcePanel(p.anchor), true);
      }
    });
    fields.runtime_hint = node("p", content, "ctl-note", label("runtime_hint")); fields.runtime_hint.id = "speech-runtime-hint";
    fields.runtime_guide = node("a", content, "ctl-link", label("worker_guide"));
    fields.runtime_guide.target = "_blank"; fields.runtime_guide.rel = "noopener noreferrer"; fields.runtime_guide.hidden = true;
    var ignore = node("label", content, "form-checkbox");
    fields.ignore_direction = node("input", ignore); fields.ignore_direction.type = "checkbox"; fields.ignore_direction.id = "speech-ignore-direction";
    node("span", ignore, "", label("ignore_direction_label"));
    fields.ignore_direction.dataset.help = label("ignore_direction");
    fields.run_options = disclosure(content, "run_options", "sliders", "speech-run-options");
    fields.run_options.append(fields.target.closest("label"), ignore);
    fields.ignore_note = node("p", fields.run_options, "ctl-note", label("ignore_direction"));
    fields.ignore_note.id = "speech-ignore-direction-note";
    fields.ignore_direction.setAttribute("aria-describedby", fields.ignore_note.id);
    fields.ignore_direction.addEventListener("change", function() {
      fields.ignore_note.hidden = !fields.ignore_direction.checked;
      invalidate();
    });
    var reuse = node("label", content, "form-checkbox"); reuse.hidden = true;
    fields.reuse = node("input", reuse); fields.reuse.type = "checkbox"; fields.reuse.id = "speech-reuse"; fields.reuse.checked = true;
    node("span", reuse, "", label("reuse"));
    fields.reuse.addEventListener("change", invalidate);
    field(content, "export_scope", "select");
    options(fields.export_scope, [["preview", label("scope_passage")], ["chapter", label("scope_chapter")], ["manuscript", label("scope_manuscript")]], "chapter");
    fields.export_scope.addEventListener("change", invalidate);
    var actions = node("div", content, "row speech-render-actions");
    fields.preview = button(actions, "preview", function() { render("preview"); }, "play");
    fields.direction_plan = button(actions, "direction_plan", function() { render(fields.export_scope.value, true); }, "file-text");
    fields.plan = node("div", content, "speech-plan"); fields.plan.hidden = true;
    fields.audit_section = disclosure(content, "audit_title", "search", "speech-audit-section");
    node("p", fields.audit_section, "ctl-note", label("audit_hint"));
    field(fields.audit_section, "audit_audio", "file").accept = ".wav,.flac,.mp3";
    field(fields.audit_section, "audit_transcript", "file").accept = ".json";
    field(fields.audit_section, "audit_scope", "select");
    options(fields.audit_scope, [["chapter", label("scope_chapter")], ["manuscript", label("scope_manuscript")]], "chapter");
    [fields.audit_audio, fields.audit_transcript, fields.audit_scope].forEach(function(input) { input.addEventListener("change", invalidate); });
    fields.audit_run = button(fields.audit_section, "audit_run", inspectAudio);
    fields.audit_result = node("div", fields.audit_section, "audio-audit-result"); fields.audit_result.setAttribute("aria-live", "polite");
    fields.microphone_section = node("section", content, "settings-section");
    fields.microphone_section.id = "speech-microphone-section";
    var micInputRow = node("div", fields.microphone_section, "row speech-microphone-input");
    fields.microphone_choice = field(micInputRow, "microphone_device", "select").closest("label");
    fields.microphone_current = node("div", micInputRow, "setting-field");
    node("span", fields.microphone_current, "form-label", label("microphone_device"));
    fields.microphone_current_name = node("strong", fields.microphone_current);
    fields.microphone_current_name.id = "speech-microphone-current";
    fields.microphone_refresh = button(micInputRow, "microphone_refresh", refreshMicrophone, "rotate-cw");
    fields.microphone_inventory_status = node("div", fields.microphone_section, "ctl-status");
    fields.microphone_inventory_status.id = "speech-microphone-inventory-status";
    fields.microphone_inventory_status.setAttribute("role", "status");
    var micCapture = nativeMicrophoneInventory();
    var micHelp = micCapture && window.lixityDesktop.platform === "macos" ? "microphone_macos_help" :
      micCapture ? "microphone_native_help" : "microphone_help";
    fields.microphone_scope = node("p", fields.microphone_section, "ctl-note", label(micHelp));
    var micGainField = fields.microphone_gain_field = node("div", fields.microphone_section, "setting-field");
    var micGainLabel = node("span", micGainField, "form-label", label("microphone_gain"));
    micGainLabel.id = "speech-microphone-gain-label";
    var micGainRow = node("div", micGainField, "row");
    fields.microphone_gain_range = node("input", micGainRow, "ctl");
    fields.microphone_gain_range.type = "range"; fields.microphone_gain_range.hidden = true;
    fields.microphone_gain = node("input", micGainRow, "ctl");
    fields.microphone_gain.type = "number"; fields.microphone_gain.step = "1"; fields.microphone_gain.required = true;
    [fields.microphone_gain_range, fields.microphone_gain].forEach(function(input) { input.setAttribute("aria-labelledby", micGainLabel.id); });
    fields.microphone_gain.style.width = "5rem";
    fields.microphone_gain_info = node("p", micGainField, "ctl-note");
    fields.microphone_gain_info.id = "speech-microphone-gain-info";
    fields.microphone_gain_status = node("p", fields.microphone_section, "ctl-status");
    fields.microphone_gain_status.id = "speech-microphone-gain-status";
    fields.microphone_gain_status.setAttribute("role", "status");
    [fields.microphone_gain_range, fields.microphone_gain].forEach(function(input) {
      input.setAttribute("aria-describedby", fields.microphone_gain_info.id + " " + fields.microphone_gain_status.id);
    });
    fields.microphone_device.addEventListener("change", function() {
      preferredMicrophone = fields.microphone_device.value;
      showMicrophoneGain();
      if (!nativeMicrophoneInventory()) void refreshMicrophone();
    });
    function editGain(source, target) {
      target.value = source.value;
      fields.microphone_gain.removeAttribute("aria-invalid");
      window.LixityComponents.setStatus(fields.microphone_gain_status, "");
    }
    fields.microphone_gain_range.addEventListener("input", function() { editGain(fields.microphone_gain_range, fields.microphone_gain); });
    fields.microphone_gain.addEventListener("input", function() { editGain(fields.microphone_gain, fields.microphone_gain_range); });
    fields.microphone_set_btn = button(micGainRow, "microphone_set_gain", async function() {
      var mixer = microphoneMixer(), input = fields.microphone_gain, feedback = fields.microphone_gain_status;
      if (microphoneBusy || microphoneRefreshing || mixer?.writable !== true) return;
      if (!input.validity.valid) {
        input.setAttribute("aria-invalid", "true");
        window.LixityComponents.setStatus(feedback, uiFormat("speech_microphone_gain_invalid", {minimum:mixer.min, maximum:mixer.max}), "err");
        input.focus({preventScroll:true});
        return;
      }
      var g = input.valueAsNumber, sequence = openSequence, device = fields.microphone_device.value;
      if (g === microphoneState.gain) {
        window.LixityComponents.setStatus(feedback, uiFormat("speech_microphone_gain_same", {gain:g}), "ok");
        return;
      }
      microphoneBusy = true; microphoneControls();
      window.LixityComponents.setStatus(feedback, label("microphone_gain_applying"), "loading");
      function current() { return sequence === openSequence && dialog.open && context() === openedContext; }
      try {
        var res = await request("audio-microphone", {action: "set_gain", gain: g, card:mixer.card, control:mixer.control});
        if (!current()) return;
        populateMicrophone(browserMicrophoneState(res));
        var reported = microphoneMixer();
        if (!reported || fields.microphone_device.value !== device || String(reported.card) !== String(mixer.card) || reported.control !== mixer.control) {
          window.LixityComponents.setStatus(feedback, label("microphone_gain_unverified"), "err");
        } else if (microphoneState.gain !== g) {
          window.LixityComponents.setStatus(feedback, uiFormat("speech_microphone_gain_different", {requested:g, actual:microphoneState.gain}), "warn");
        } else {
          window.LixityComponents.setStatus(feedback, uiFormat("speech_microphone_gain_set", {gain:g}), "ok");
        }
      } catch (_) {
        if (current()) window.LixityComponents.setStatus(feedback, label("microphone_gain_failed"), "err");
      } finally {
        if (sequence === openSequence) { microphoneBusy = false; microphoneControls(); }
      }
    });
    var micCalibActions = node("div", fields.microphone_section, "row");
    fields.microphone_calib_btn = button(micCalibActions, "microphone_calibrate", async function() {
      if (microphoneBusy || microphoneRefreshing || !fields.microphone_device.value) return;
      var sequence = openSequence, mixer = microphoneMixer(), dev = fields.microphone_device.value;
      var capture = nativeMicrophoneInventory();
      microphoneBusy = true; microphoneControls(); fields.microphone_calib_result.replaceChildren();
      var feedback = fields.microphone_check_status;
      window.LixityComponents.setStatus(feedback, label(capture ? "microphone_calib_native_prep" : "microphone_calib_prep"), "loading");
      try {
        var res;
        if (capture) {
          res = {calibration:await capture.calibrate(dev, 4.0)};
        } else {
          // Measure the selected device at its current level. The calibration API's
          // optional gain targets its default mixer, which may be another card.
          res = await request("audio-microphone", {action: "calibrate", device: dev});
        }
        if (sequence !== openSequence || !dialog.open || context() !== openedContext) return;
        var cal = res?.calibration;
        if (!cal || !Number.isFinite(cal.peak_dbfs) || !Number.isInteger(cal.clipping_samples) || typeof cal.signal_present !== "boolean" ||
            !["calibrated", "too_hot", "too_quiet"].includes(cal.verdict)) throw new Error("Invalid microphone check");
        window.LixityComponents.setStatus(feedback, "");
        var verdict = cal.signal_present ? cal.verdict : "silent";
        var card = node("div", fields.microphone_calib_result, "audit-summary");
        var tone = verdict === "calibrated" ? "pass" : verdict === "too_hot" ? "fail" : "warn";
        node("div", card, "badge badge-" + tone, label("microphone_check_" + verdict));
        node("p", card, "", label("microphone_check_" + verdict + "_help"));
        var numbers = new Intl.NumberFormat(document.documentElement.lang);
        node("p", card, "ctl-note", uiFormat("speech_microphone_check_readings",
          {peak:numbers.format(cal.peak_dbfs), clipping:numbers.format(cal.clipping_samples)}));
        if (cal.signal_present && mixer?.writable === true && cal.mixer &&
            String(mixer.card) === String(cal.mixer.card) && mixer.control === cal.mixer.control && Number.isInteger(cal.recommended_gain) &&
            cal.recommended_gain >= mixer.min && cal.recommended_gain <= mixer.max && cal.recommended_gain !== microphoneState.gain) {
          var applyGainText = uiFormat("speech_microphone_calib_apply_gain", {gain: cal.recommended_gain});
          var recBtn = node("button", card, "ctl", applyGainText);
          recBtn.type = "button";
          recBtn.addEventListener("click", function() {
            fields.microphone_gain.value = fields.microphone_gain_range.value = String(cal.recommended_gain);
            fields.microphone_set_btn.click();
          });
        }
      } catch (_) {
        if (sequence === openSequence && dialog.open && context() === openedContext) {
          window.LixityComponents.setStatus(feedback, label("microphone_check_failed"), "err");
        }
      } finally {
        if (sequence === openSequence) { microphoneBusy = false; microphoneControls(); }
      }
    });
    fields.microphone_calib_btn.classList.add("primary");
    actionLabel(fields.microphone_calib_btn, "microphone_calibrate", "volume-2");
    fields.microphone_check_status = node("p", fields.microphone_section, "ctl-status");
    fields.microphone_check_status.id = "speech-microphone-check-status";
    fields.microphone_check_status.setAttribute("role", "status");
    fields.microphone_calib_result = node("div", fields.microphone_section, "audio-calib-result");
    fields.microphone_calib_result.setAttribute("aria-live", "polite");
    fields.chapter_render = button(actions, "chapter_render", function() { render("chapter"); }, "headphones");
    fields.cancel = button(actions, "cancel", cancel, "square"); fields.cancel.disabled = true;
    fields.context = node("p", content, "ctl-note"); fields.progress = node("progress", content); fields.progress.hidden = true; fields.progress.setAttribute("aria-label", label("progress"));
    fields.playback_section = node("div", content, "speech-playback");
    fields.audio = node("audio", fields.playback_section, "media-player"); fields.audio.id = "speech-audio-player"; fields.audio.controls = true; fields.audio.hidden = true;
    fields.audioWidget = window.createSpeechPlayer(fields.audio, {label: label, onError: function(message) {
      generatedAudioEvent("generated_audio_failed"); status(message);
    }});
    fields.audio.addEventListener("playing", function() { generatedAudioEvent("generated_audio_playing"); });
    fields.player_controls = node("div", content, "speech-player-controls"); fields.player_controls.hidden = true;
    var skipBack = button(fields.player_controls, "skip_back", function() { fields.audio.currentTime = Math.max(0, fields.audio.currentTime - 5); });
    skipBack.textContent = "−5 s";
    window.LixityComponents.setControlLabel(skipBack, label("playback_back"));
    var skipForward = button(fields.player_controls, "skip_forward", function() { fields.audio.currentTime = Math.min(fields.audio.duration || 0, fields.audio.currentTime + 5); });
    skipForward.textContent = "+5 s";
    window.LixityComponents.setControlLabel(skipForward, label("playback_forward"));
    var rateFormat = new Intl.NumberFormat(document.documentElement.lang || undefined);
    [0.8, 1.0, 1.25, 1.5].forEach(function(rate) {
      var rateBtn = button(fields.player_controls, "rate_" + rate, function() {
        fields.audio.playbackRate = rate;
        fields.player_controls.querySelectorAll(".speech-rate-btn").forEach(function(b) {
          b.classList.remove("active");
          b.setAttribute("aria-pressed", "false");
        });
        rateBtn.classList.add("active");
        rateBtn.setAttribute("aria-pressed", "true");
      });
      var rateText = rateFormat.format(rate) + "×";
      rateBtn.textContent = rateText;
      window.LixityComponents.setControlLabel(rateBtn, uiFormat("speech_playback_rate", {rate:rateText}));
      rateBtn.classList.add("speech-rate-btn");
      var isDefaultRate = rate === 1.0;
      if (isDefaultRate) rateBtn.classList.add("active");
      rateBtn.setAttribute("aria-pressed", String(isDefaultRate));
    });
    fields.download = node("a", content, "ctl", label("download")); fields.download.download = "speech.wav"; fields.download.hidden = true;
    fields.profile_footer = node("div", card, "modal-footer speech-profile-footer");
    fields.profile_discard = button(fields.profile_footer, "profiles_discard", function() {
      if (profileSaving || !savedSettings) return;
      settings = JSON.parse(JSON.stringify(savedSettings)); profilesDirty = false;
      profileOptions(); loadProfile();
      if (openedContext !== context()) fields.save.disabled = fields.create.disabled = fields.remove_profile.disabled = fields.profile.disabled = true;
      status(""); invalidate();
    });
    fields.save = button(fields.profile_footer, "save", save, "save");
    fields.save.classList.add("primary");
    fields.export_section = disclosure(content, "export_title", "download", "speech-export-section");
    node("p", fields.export_section, "ctl-note", label("export_hint"));
    fields.export_section.append(fields.export_scope.closest("label"), fields.direction_plan, fields.plan);
    fields.render_section = node("fieldset", content, "settings-section speech-render-section");
    fields.render_heading = node("legend", fields.render_section);
    fields.chapter_audio_section = disclosure(content, "chapter_audio_title", "file-up", "speech-chapter-recording");
    field(fields.chapter_audio_section, "chapter_audio_file", "file").accept = ".wav,audio/wav";
    fields.chapter_audio_file.required = true;
    fields.chapter_audio_file.dataset.help = label("chapter_audio_hint");
    var chapterActions = node("div", fields.chapter_audio_section, "row");
    fields.chapter_audio_import = button(chapterActions, "chapter_audio_import", importChapterAudio, "file-up");
    fields.chapter_audio_import.dataset.help = label("chapter_audio_hint");
    fields.chapter_audio_discard = button(chapterActions, "chapter_audio_discard", function() {
      fields.chapter_audio_file.value = "";
      showChapterAudio();
      fields.chapter_audio_file.focus();
    });
    fields.chapter_audio_delete = button(chapterActions, "chapter_audio_delete", removeChapterAudio);
    fields.chapter_audio_discard.hidden = fields.chapter_audio_delete.hidden = true;
    fields.chapter_audio_file.addEventListener("change", updateChapterAudioActions);
    fields.chapter_audio_status = node("p", fields.chapter_audio_section, "ctl-note");
    fields.chapter_audio_status.id = "speech-chapter-audio-status";
    fields.chapter_audio_status.setAttribute("role", "status");
    fields.service_section = disclosure(content, "service_title", "settings", "speech-service-section speech-profile-utilities");
    fields.service_section.id = "speech-service";
    var serviceActions = node("div", null, "row");
    serviceActions.append(fields.worker_guide, fields.worker_refresh);
    fields.service_section.append(fields.worker_target.closest("label"), fields.worker_status, serviceActions);
    actions.prepend(fields.chapter_render);
    fields.render_section.append(actions, fields.context, fields.progress, fields.runtime_hint, fields.runtime_guide);
    fields.run_options.append(reuse);
    fields.playback_section.append(fields.player_controls, fields.download);
    fields.profile_row.before(fields.schema_section);
    fields.profile_row.after(fields.editor, fields.lexicon_section, fields.phonemes_section, fields.service_section);
    fields.reuseLabel = reuse;
    content.append(fields.reader_context, fields.render_section, fields.playback_section, direction.section, fields.run_options,
      fields.chapter_audio_section, fields.export_section, fields.audit_section, fields.reader_shortcut);
    arrangeSections();
    function markProfileDirty(event) {
      if (mode === "profiles" && ![fields.pronunciation_search, fields.pronunciation_term, fields.pronunciation_spoken,
        fields.pronunciation_ipa, fields.pronunciation_scope].includes(event.target)) profilesDirty = true;
      invalidate();
    }
    [fields.editor, fields.lexicon_section, fields.phonemes_section].forEach(function(section) {
      section.addEventListener("input", markProfileDirty);
    });
    fields.engine.addEventListener("change", function() {
      if (profileCapability().voices[fields.voice.value]) lastPreset = fields.voice.value;
      var cap = capabilities[fields.engine.value];
      if (cap.languages.length && !cap.languages.includes(fields.language.value)) options(fields.language, [[cap.languages[0], languageName(cap.languages[0])]], cap.languages[0]);
      var matchingVoices = Object.entries(cap.voices).filter(function(pair) {
        return pair[1].languages.includes(fields.language.value);
      });
      var defaultVoice = cap.default_voice || "";
      var hasReference = Boolean(fields.reference_id && fields.reference_id.value.trim());
      var voice = cap.voice_design ? "design" :
        (cap.reference_required || (cap.reference_supported && hasReference)) ? "reference" :
        cap.voices[lastPreset] && cap.voices[lastPreset].languages.includes(fields.language.value) ? lastPreset :
        cap.voices[defaultVoice] && cap.voices[defaultVoice].languages.includes(fields.language.value) ? defaultVoice :
        (matchingVoices[0] && matchingVoices[0][0]) || "";
      options(fields.voice, [], voice);
      if (!fields.speed.value || (fields.engine.value === "mlx-audio" && Number(fields.speed.value) === 1)) {
        fields.speed.value = String(cap.speed.default);
      }
      if (fields.engine.value === "mlx-audio") {
        fields.base_url.value = cap.default_base_url || fields.base_url.value;
        fields.provider_model.value = cap.model || fields.provider_model.value;
        fields.provider_voice.value = voice || fields.provider_voice.value;
      }
      voiceControls(); invalidate();
      var chosenEngine = fields.engine.value;
      if (chosenEngine && chosenEngine !== "openai-compatible" && cap.runtime_status !== "unavailable" &&
          Array.isArray(workers) && !workers.some(function(item) { return !item.engines || item.engines.includes(chosenEngine); })) {
        var sequence = openSequence;
        request("speech", null, {engine: chosenEngine}).then(function(data) {
          if (sequence === openSequence && dialog.open && openedContext === context()) {
            applyWorkerInventory(data.workers);
          }
        }).catch(function() {});
      }
    });
    fields.language.addEventListener("change", function() { fields.voice.value = ""; voiceControls(); status(label("voice_changed")); });
    fields.voice.addEventListener("change", function() {
      var cap = profileCapability();
      if (cap.reference_supported && fields.voice.value !== "reference") fields.reference_id.value = "";
      voiceControls(); updateVoiceCard(); updateModelFields(); status(label("voice_changed"));
    });
    fields.profile.addEventListener("change", function() {
      try { stash(); if (settings.selected !== fields.profile.value) profilesDirty = true; settings.selected = fields.profile.value; loadProfile(); }
      catch (error) { fields.profile.value = settings.selected; status(error.message); }
    });
    fields.chapter.addEventListener("change", function() { paragraph = null; invalidate(); var select=fields.direction_passage; var choice=Array.from(select.options).find(function(o) { return o.textContent.startsWith(fields.chapter.value + " · "); }); if (choice) { select.value=choice.value; select.dispatchEvent(new Event("change")); } fields.context.textContent = label("first_preview"); });
    fields.chapter.addEventListener("change", showChapterAudio);
    dialog.addEventListener("cancel", function(event) {
      event.preventDefault();
      closeAudioSurface();
    });
    dialog.addEventListener("keydown", function(event) {
      if (speechDocked && event.key === "Escape" && !event.defaultPrevented && !event.isComposing) {
        event.preventDefault(); event.stopPropagation(); closeAudioSurface();
      }
    });
    fields.microphone_device.setAttribute("aria-label", label("microphone_device"));
    fields.microphone_gain.setAttribute("aria-label", label("microphone_gain"));
    fields.microphone_gain_range.setAttribute("aria-label", label("microphone_gain"));
    fields.reuse.dataset.help = label("reuse_help");
  }
  async function open(entry, requestedPanel, opener) {
    if (dialog?.open && speechDocked && entry === "reader") {
      if (!speechReady && requestedPanel && closeAudioSurface()) return open(entry, requestedPanel, opener);
      if (direction.busy() || direction.dirty()) {
        showReaderDocument(); status(label(direction.busy() ? "saving" : "direction_switch_first"));
        return;
      }
      if (opener) speechOpener = opener;
      if (mode !== "reader") switchMode("reader");
      showReaderDocument();
      if (requestedPanel && !direction.selectAnchor(passageIdentity(requestedPanel))) status(label("passage_unavailable"));
      fields.heading.focus({preventScroll:true});
      return;
    }
    if (dialog?.open && speechDocked && (direction.busy() || direction.dirty())) showReaderDocument();
    if (dialog?.open && !closeAudioSurface()) return;
    mode = Object.hasOwn(surfaces, entry) ? entry : "reference";
    speechOpener = mode === "reader" ? opener || document.getElementById("reader-speech") : null;
    speechReady = false; speechLoadMessage = label("loading"); trimLimitSeconds = 0; referenceFormat = null; referenceRecording = null; profileConstraints = null;
    profileSettingsAvailable = schemaReviewAvailable = migrationRequired = false;
    ++openSequence;
    var fromReader = inReader();
    var readerControl = document.getElementById("reader-chapter");
    var readerChapterIntent = fromReader && readerControl ? (readerControl.value || readerControl.dataset.currentChapter || "") : "";
    var micCapture = nativeMicrophoneInventory(), currentContext = context();
    if (!micCapture || openedContext !== currentContext) preferredMicrophone = "";
    if (!dialog) build(); invalidate(); direction.disable(); settings = null; savedSettings = null; workers = null; profilesDirty = false; profileSaving = false; openedContext = currentContext; paragraph = null;
    chapterAudio = null; ++chapterAudioSequence;
    fields.chapter_audio_file.value = ""; setChapterAudioBusy(false);
    fields.chapter_audio_status.textContent = label("loading");
    fields.audit_audio.value = fields.audit_transcript.value = "";
    fields.run_options.open = fields.chapter_audio_section.open = fields.export_section.open = fields.audit_section.open = false;
    microphoneBusy = false; microphoneRefreshing = !micCapture;
    microphoneInventoryStatus("microphone_looking");
    populateMicrophone(null);
    fields.worker_status.textContent = label("loading"); fields.worker_refresh.disabled = true;
    fields.service_section.open = fields.recording_defaults_section.open = false;
    fields.profile.disabled = false;
    fields.recBtn.disabled = true; fields.reference_section.inert = true;
    fields.recLimit.hidden = true;
    recordingFeedback("idle");
    fields.reference_section.setAttribute("aria-busy", "true");
    switchMode(mode, true);
    if (fromReader) {
      var selection = window.getSelection(), anchor = selection && selection.anchorNode;
      var element = anchor && (anchor.nodeType === 1 ? anchor : anchor.parentElement);
      var panel = requestedPanel || element && element.closest("#chapters .ptext[data-paragraph-sha256]");
      if (!panel) {
        panel = document.querySelector("#chapters .ptext.reader-selected, #chapters .ptext:focus-within");
      }
      var reader = document.getElementById("reader-chapter");
      if (!requestedPanel && panel && reader && /^ch-\d+$/.test(readerChapterIntent) && panel.closest(".chapter").id !== readerChapterIntent) panel = null;
      if (panel) paragraph = {chapter: Number((panel.closest(".chapter") || {}).id?.replace("ch-", "")), identity:passageIdentity(panel)};
    }
    fields.context.textContent = "";
    fields.project_profile_name.textContent = label("loading");
    fields.target.value = fields.worker_target.value = "";
    fields.export_scope.value = mode === "reader" ? "preview" : "chapter";
    fields.audit_scope.value = "chapter";
    fields.ignore_direction.checked = false;
    fields.ignore_note.hidden = true;
    fields.reuse.checked = true;
    fields.reuse.disabled = false;
    calibrationTexts = null; sampleVariant = "short"; fields.customTextarea.value = "";
    fields.updatePromptText();
    fields.editor.querySelectorAll("input, textarea").forEach(function(input) { input.value = ""; });
    ["profile", "engine", "language", "voice", "reference_id", "chapter"].forEach(function(key) { fields[key].replaceChildren(); });
    presentSpeechSurface(fromReader ? panel : null);
    status(label("loading")); setEditorDisabled(true); fields.save.disabled = fields.create.disabled = fields.preview.disabled = fields.chapter_render.disabled = true;
    if (micCapture) void refreshMicrophone();
    var serial = generation, sequence = openSequence;
    try {
      var data = await request("speech"); if (!valid(serial)) return;
      referenceFormat = readReferenceFormat(data.reference_format);
      referenceRecording = readReferenceRecording(data.reference_recording);
      prepareRecordingDuration();
      trimLimitSeconds = data.can_trim_take === true && Number.isFinite(data.take_trim_limit_seconds) ? data.take_trim_limit_seconds : 0;
      profileConstraints = data.profile_constraints;
      migrationRequired = data.requires_migration === true;
      profileSettingsAvailable = Boolean(data.settings) && !migrationRequired;
      schemaReviewAvailable = !migrationRequired && (data.settings ?
        data.settings.schema_version !== currentAudioSchema : data.audio_settings_present === false);
      settings = data.settings || {schema_version: "lixity-audio-settings/1", selected: "", profiles: {}}; capabilities = data.capabilities; workers = data.workers;
      pronunciationScope = settings.schema_version === currentAudioSchema ? "project" : "profile";
      allReferences = data.references || [];
      renderReferenceList(allReferences);
      calibrationTexts = data.calibration_texts || null; fields.updatePromptText();
      renderActiveVoiceBadge();
      if (!micCapture) {
        var microphone = browserMicrophoneState(data.microphone);
        microphoneRefreshing = false;
        populateMicrophone(microphone);
        microphoneInventoryStatus(microphone.devices.length ? "" : "microphone_empty");
      }
      fields.schema_apply.hidden = true; fields.schema_apply.disabled = false;
      fields.worker_refresh.disabled = false;
      savedSettings = JSON.parse(JSON.stringify(settings));
      var savedProfile = savedSettings.profiles[savedSettings.selected];
      fields.project_profile_name.textContent = savedProfile ? uiFormat("speech_project_profile_summary", {
        profile:savedProfile.name, engine:capabilities[savedProfile.engine]?.short_name || capabilities[savedProfile.engine]?.name || savedProfile.engine
      }) : label("profile_required");
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
      savedDirectionView = data.direction || null;
      if (data.direction) {
        var initialPassage = paragraph ? {anchor:paragraph.identity} : data.direction.passages.find(function(p) { return p.chapter === Number(fields.chapter.value); });
        direction.open(data.direction, initialPassage && initialPassage.anchor, settings.profiles);
      }
      if (migrationRequired) direction.disable();
      arrangeSections();
      speechReady = true; fields.recBtn.disabled = !canRecordVoice(); fields.reference_section.inert = false;
      fields.chapter_audio_import.disabled = fields.chapter_audio_file.disabled = false;
      refreshChapterAudio();
      recordingFeedback("idle");
      fields.reference_section.setAttribute("aria-busy", "false");
      speechLoadMessage = profileSettingsAvailable && !settings.selected ? "" : data.configuration_error || "";
      status(speechLoadMessage); fields.save.disabled = migrationRequired || !settings.selected;
      fields.context.textContent = label(paragraph ? "paragraph_preview" : "first_preview");
    } catch (error) {
      if (sequence === openSequence && dialog.open && openedContext === context()) {
        if (!micCapture) {
          microphoneRefreshing = false;
          microphoneInventoryStatus("microphone_failed");
          microphoneControls();
        }
        fields.project_profile_name.textContent = label("profile_required");
        fields.worker_status.textContent = uiFormat("speech_worker_unknown", {target: label("target_" + (fields.worker_target.value || "local"))});
        speechLoadMessage = error.message;
        fields.reference_section.setAttribute("aria-busy", "false");
        status(speechLoadMessage);
      }
    }
  }
  var audioActions = document.getElementById("project-audio-settings-actions");
  audioActions.classList.add("speech-project-actions");
  button(audioActions, "record_author_title", function() { open("reference"); }, "mic").id = "btn-project-record-voice";
  fields.project_profiles_action = button(audioActions, "profiles_title", function() { open("profiles"); }, "sliders");
  fields.project_profiles_action.id = "settings-speech";
  button(audioActions, "microphone_title", function() { open("microphone"); }, "volume-2").id = "settings-speech-mic";
  var runtimeAction = document.getElementById("runtime-open");
  if (runtimeAction) audioActions.appendChild(runtimeAction);
  var outputShortcut = node("div", null, "row speech-project-actions");
  audioActions.after(outputShortcut);
  button(outputShortcut, "go_to_chapter_audio", function() { open("output"); }, "file-text").id = "settings-speech-output";
  var toolbar = document.getElementById("manuscript-reader-controls");
  if (toolbar) {
    var existingSpeech = toolbar.querySelector("#reader-speech");
    var readerSpeech = existingSpeech || button(toolbar, "reader_title", function() { open("reader"); });
    readerSpeech.id = "reader-speech";
    readerSpeech.className = "ctl reader-compact-control";
    var audioSvg = window.LixityIcons ? window.LixityIcons.svg("headphones", { size: 16, strokeWidth: 1.85 }) : "";
    readerSpeech.innerHTML = '<span class="reader-control-icon" aria-hidden="true">' + audioSvg + '</span> <span class="reader-control-label">' + label("reader_title") + '</span>';
    readerSpeech.title = label("reader_title");
    readerSpeech.setAttribute("aria-controls", "modal-speech");
    readerSpeech.setAttribute("aria-expanded", "false");
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
    open(targetMode, e.detail?.passage, e.detail?.opener);
  });
  document.addEventListener("lixity:workbench-change", function(event) {
    if (!dialog || !dialog.open || placingSpeech) return;
    if (speechDocked && event.detail) {
      visibleReaderSpeech(event.detail);
      if (!dialog.hidden) return;
    }
    if (profileSaving || voiceSaving) { status(label("saving")); return; }
    if (direction.busy() || direction.dirty()) {
      status(label(direction.busy() ? "saving" : "direction_switch_first")); return;
    }
    closeAudioSurface();
  });
  new MutationObserver(function() {
    if (!dialog || !dialog.open || context() === openedContext) return;
    if (mode === "reference" && (recordingDurationChanged() || profileSaving)) {
      updateRecordingDuration(); status(label(profileSaving ? "saving" : "recording_duration_unsaved"));
      return;
    }
    if (mode === "profiles" && (profileDraftMessage() || profileSaving)) {
      invalidate(); fields.save.disabled = fields.create.disabled = fields.remove_profile.disabled = fields.profile.disabled = true;
      updateRecordingDuration();
      status(label(pronunciationPending() && !profilesDirty ? "pronunciation_context_changed" : "profiles_context_changed")); return;
    }
    if (direction.dirty() || direction.busy()) {
      invalidate(); direction.stale(); status(label("direction_context_changed")); return;
    }
    if (importedTake && !matchingTakeContext(takeTokens)) {
      fields.saveVoiceBtn.disabled = true;
      fields.recBtn.disabled = true;
      updateRecordingDuration();
      status(label("take_context"));
      return;
    }
    closeAudioSurface();
  }).observe(body, {
    subtree: true, attributes: true, attributeFilter: ["data-project-token", "data-manuscript-source-sha256", "data-manuscript-project-token"]});
})();
