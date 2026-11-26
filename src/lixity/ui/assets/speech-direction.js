/* Author-owned passage direction; prose is read-only and never sent by the browser. */
window.LixitySpeechDirection = function(parent, h) {
  "use strict";
  var view, profiles, selected, selectedPassage, dirty = false, pending = false, revision = 0;
  var section = h.node("fieldset", parent, "settings-section speech-direction-section");
  h.node("legend", section, "", h.label("direction_title"));
  function updateControls() {
    var support = h.profileSupport(profiles && profiles[voice.value]);
    hint.textContent = h.label(support.direction === "model_interpreted" ? "direction_hint" : "direction_export_hint");
    style.closest("label").hidden = support.direction !== "model_interpreted";
    style.disabled = support.direction !== "model_interpreted";
    h.applyPauseBounds([before, after], support);
    prosody.update(support.prosody);
  }
  var source = h.node("div", section, "settings-grid");
  var passage = h.field(source, "direction_passage", "select");
  var entries = h.field(source, "direction_entries", "select");
  var text = h.field(section, "direction_text", "textarea"); text.readOnly = true; text.rows = 4;
  var selection = h.node("div", section, "row speech-direction-selection");
  var start = 0, end = null;
  var select = h.button(selection, "direction_selection", function() {
    start = Array.from(text.value.slice(0, text.selectionStart)).length;
    end = Array.from(text.value.slice(0, text.selectionEnd)).length;
    if (start === end) { start = 0; end = null; }
    changed(); showRange();
  });
  var range = h.node("p", selection, "ctl-note");
  range.id = "speech-direction-range";
  range.setAttribute("role", "status");
  select.setAttribute("aria-describedby", range.id);
  var delivery = h.node("div", section, "settings-grid");
  var voice = h.field(delivery, "direction_profile", "select");
  var style = h.field(delivery, "direction_style", "select");
  h.options(style, [["", h.label("direction_custom")], ["calm", h.label("direction_calm")], ["tense", h.label("direction_tense")], ["whisper", h.label("direction_whisper")]], "");
  var instructions = h.field(section, "direction_instructions", "textarea"); instructions.maxLength = 2000;
  var hint = h.node("p", section, "ctl-note", h.label("direction_hint"));
  hint.id = "speech-direction-hint";
  instructions.setAttribute("aria-describedby", hint.id);
  delete instructions.dataset.help;
  var grid = h.node("div", section, "settings-grid");
  var before = h.field(grid, "direction_before", "number"), after = h.field(grid, "direction_after", "number");
  var prosody = h.createProsody(section, "direction-prosody-", changed, true);
  var actions = h.node("div", section, "row");
  var save = h.button(actions, "direction_save", function() { mutate(false); });
  save.classList.add("primary");
  var remove = h.button(actions, "direction_remove", function() { mutate(true); });
  h.button(actions, "direction_discard", function() { loadEntry(); h.invalidate(); });
  var warning = h.node("details", section, "speech-stale-directions"); warning.hidden = true;
  function changed() { dirty = true; h.invalidate(); h.status(h.label("direction_unsaved")); }
  function showRange() {
    if (!start && end == null) { range.textContent = h.label("direction_whole"); return; }
    var points = Array.from(text.value), limit = end == null ? points.length : end;
    var snippet = points.slice(start, Math.min(limit, start + 64)).join("").trim();
    range.textContent = snippet ? snippet + (limit > start + 64 ? "…" : "") : start + "–" + limit;
  }
  function current() { return view && view.passages.find(function(p) { return JSON.stringify(p.anchor) === passage.value; }); }
  function read() {
    var p = current(); if (!p) return null;
    if (![before, after, instructions].every(function(el) { return el.reportValidity(); })) throw new Error(h.label("failed"));
    var result = {anchor:p.anchor, start:start, end:end, profile_id:voice.value || null,
      instructions:instructions.value.trim(), pause_before:before.value === "" ? 0 : Number(before.value),
      pause_after:after.value === "" ? null : Number(after.value)};
    var controls = prosody.read(); if (Object.keys(controls).length) result.prosody = controls;
    return result;
  }
  function loadEntry() {
    var entry = view.directions.find(function(d) { return d.id === entries.value; });
    selected = entry || null; start = entry ? entry.start : 0; end = entry ? entry.end : null;
    h.options(voice, [["",h.label("direction_default")]].concat(Object.entries(profiles).map(function(p) { return [p[0],p[1].name]; })), entry && entry.profile_id || "", h.label("profile_unavailable"));
    instructions.value = entry && entry.instructions || "";
    prosody.load(entry && entry.prosody || {});
    before.value = entry ? entry.pause_before : 0; after.value = entry && entry.pause_after != null ? entry.pause_after : "";
    style.value = ""; dirty = false; remove.disabled = !entry || !h.current(); showRange(); updateControls();
  }
  function loadPassage() {
    selectedPassage = passage.value;
    var p = current(); text.value = p ? p.text : "";
    var values = view.directions.filter(function(d) { return p && JSON.stringify(d.anchor) === JSON.stringify(p.anchor); });
    h.options(entries, [["", h.label("direction_new")]].concat(values.map(function(d) { return [d.id, d.start + "–" + (d.end == null ? Array.from(text.value).length : d.end) + " · " + d.instructions.slice(0,50)]; })), "");
    loadEntry(); select.disabled = !p; save.disabled = !p || !h.current();
    if (p) h.selected(p);
  }
  passage.addEventListener("change", function() {
    if (dirty) { passage.value = selectedPassage; h.status(h.label("direction_switch_first")); return; }
    h.invalidate(); loadPassage();
  });
  entries.addEventListener("change", function() {
    if (dirty) { entries.value = selected ? selected.id : ""; h.status(h.label("direction_switch_first")); return; }
    h.invalidate(); loadEntry();
  });
  var chapter = document.getElementById("speech-chapter");
  if (chapter) chapter.addEventListener("change", function(event) {
    if (!dirty) return;
    var p = current();
    if (p) chapter.value = String(p.chapter);
    event.stopImmediatePropagation();
    h.status(h.label("direction_switch_first"));
  }, true);
  [voice,instructions,before,after].forEach(function(el) { el.addEventListener("input", changed); });
  voice.addEventListener("change", updateControls);
  style.addEventListener("change", function() {
    var styles = {calm:"Maintain the same voice; read calmly and clearly, with restrained expression.", tense:"Maintain the same voice; read with restrained tension and controlled urgency, without shouting.", whisper:"Maintain the same voice; whisper quietly while keeping every word intelligible."};
    if (styles[style.value]) { instructions.value = styles[style.value]; changed(); }
  });
  async function mutate(deleting) {
    if (pending) return;
    if (!h.current()) { h.status(h.label("direction_context_changed")); return; }
    var serial = revision;
    var chapterWasDisabled = chapter && chapter.disabled;
    try {
      var payload = Object.assign(h.tokens(), {expected_settings_sha256:view.settings_sha256, expected_direction_sha256:view.direction_sha256});
      if (deleting) { if (!selected) return; payload.remove_id = selected.id; }
      else { payload.direction = read(); if (selected) payload.replace_id = selected.id; }
      pending = true; section.disabled = true;
      if (chapter) chapter.disabled = true;
      var data = await h.request("speech-direction", payload);
      if (serial !== revision || !h.current()) return;
      pending = false; section.disabled = false;
      if (chapter) chapter.disabled = chapterWasDisabled;
      var anchor = passage.value; view = data.direction;
      open(view, anchor, profiles); h.invalidate(); h.status(h.label("direction_saved"));
    } catch (error) { if (serial === revision && h.current()) { h.status(error.message); save.disabled = !current(); remove.disabled = !selected; } }
    finally {
      if (serial === revision && h.current()) {
        pending = false; section.disabled = false;
        if (chapter) chapter.disabled = chapterWasDisabled;
      }
    }
  }
  function open(data, anchor, available) {
    ++revision; view = data; profiles = available; dirty = false; pending = false;
    section.disabled = false;
    h.options(voice, [["",h.label("direction_default")]].concat(Object.entries(profiles).map(function(p) { return [p[0],p[1].name]; })), "");
    h.options(passage, [["",h.label("direction_passage")]].concat(view.passages.map(function(p) { return [JSON.stringify(p.anchor), p.chapter + " · " + p.anchor.start_line + "–" + p.anchor.end_line + " · " + p.text.slice(0,65)]; })), typeof anchor === "string" ? anchor : anchor ? JSON.stringify(anchor) : "", h.label("passage_unavailable"));
    var stale = view.directions.filter(function(d) { return d.stale; });
    warning.replaceChildren();
    warning.hidden = !stale.length;
    if (stale.length) {
      h.node("summary", warning, "", h.label("direction_stale") + " (" + stale.length + ")");
      var list = h.node("ul", warning, "speech-stale-list");
      stale.forEach(function(d) {
        var row = h.node("li", list);
        h.node("span", row, "", d.anchor.start_line + "–" + d.anchor.end_line + " · " + d.instructions.slice(0,120));
        h.button(row, "direction_remove", function() { selected=d; mutate(true); });
      });
    }
    loadPassage();
  }
  function selectAnchor(anchor) {
    if (!view || dirty || pending) return false;
    var encoded = JSON.stringify(anchor);
    if (!view.passages.some(function(p) { return JSON.stringify(p.anchor) === encoded; })) return false;
    passage.value = encoded;
    loadPassage(); h.invalidate();
    return true;
  }
  return {section:section, open:open, selectAnchor:selectAnchor, updateCapabilities:updateControls, draft:function() { return dirty ? read() : null; },
    dirty:function() { return dirty; }, busy:function() { return pending; }, replacement:function() { return dirty && selected ? selected.id : null; },
    stale:function() { ++revision; pending = false; section.disabled = false; save.disabled = remove.disabled = true; if (chapter) chapter.disabled = true; },
    disable:function() { pending = false; section.disabled = true; if (chapter) chapter.disabled = false; }};
};
