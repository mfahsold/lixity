/* Author-owned passage direction; prose is read-only and never sent by the browser. */
window.LixitySpeechDirection = function(parent, h) {
  "use strict";
  var view, profiles, selected, dirty = false, revision = 0;
  var section = h.node("fieldset", parent, "settings-section");
  h.node("legend", section, "", h.label("direction_title"));
  h.node("p", section, "ctl-note", h.label("direction_hint"));
  var passage = h.field(section, "direction_passage", "select");
  var entries = h.field(section, "direction_entries", "select");
  var text = h.field(section, "direction_text", "textarea"); text.readOnly = true; text.rows = 4;
  var range = h.node("p", section, "ctl-note");
  var start = 0, end = null;
  var select = h.button(h.node("div", section, "row"), "direction_selection", function() {
    start = Array.from(text.value.slice(0, text.selectionStart)).length;
    end = Array.from(text.value.slice(0, text.selectionEnd)).length;
    if (start === end) { start = 0; end = null; }
    changed(); showRange();
  });
  var voice = h.field(section, "direction_profile", "select");
  var style = h.field(section, "direction_style", "select");
  h.options(style, [["", h.label("direction_custom")], ["calm", h.label("direction_calm")], ["tense", h.label("direction_tense")], ["whisper", h.label("direction_whisper")]], "");
  var instructions = h.field(section, "direction_instructions", "textarea"); instructions.maxLength = 2000;
  var grid = h.node("div", section, "settings-grid");
  var before = h.field(grid, "direction_before", "number"), after = h.field(grid, "direction_after", "number");
  [before, after].forEach(function(input) { input.min = "0"; input.max = "10"; input.step = "any"; });
  var actions = h.node("div", section, "row");
  var save = h.button(actions, "direction_save", function() { mutate(false); });
  var remove = h.button(actions, "direction_remove", function() { mutate(true); });
  h.button(actions, "direction_discard", function() { loadEntry(); h.invalidate(); });
  var warning = h.node("p", section, "ctl-note");
  function changed() { dirty = true; h.invalidate(); h.status(h.label("direction_unsaved")); }
  function showRange() { range.textContent = (start || end != null) ? start + "–" + (end == null ? Array.from(text.value).length : end) : h.label("direction_whole"); }
  function current() { return view && view.passages.find(function(p) { return JSON.stringify(p.anchor) === passage.value; }); }
  function read() {
    var p = current(); if (!p) return null;
    if (![before, after, instructions].every(function(el) { return el.reportValidity(); })) throw new Error(h.label("failed"));
    return {anchor:p.anchor, start:start, end:end, profile_id:voice.value || null,
      instructions:instructions.value.trim(), pause_before:before.value === "" ? 0 : Number(before.value),
      pause_after:after.value === "" ? null : Number(after.value)};
  }
  function loadEntry() {
    var entry = view.directions.find(function(d) { return d.id === entries.value; });
    selected = entry || null; start = entry ? entry.start : 0; end = entry ? entry.end : null;
    h.options(voice, [["",h.label("direction_default")]].concat(Object.entries(profiles).map(function(p) { return [p[0],p[1].name]; })), entry && entry.profile_id || "");
    instructions.value = entry && entry.instructions || "";
    before.value = entry ? entry.pause_before : 0; after.value = entry && entry.pause_after != null ? entry.pause_after : "";
    style.value = ""; dirty = false; remove.disabled = !entry; showRange();
  }
  function loadPassage() {
    var p = current(); text.value = p ? p.text : "";
    var values = view.directions.filter(function(d) { return p && JSON.stringify(d.anchor) === JSON.stringify(p.anchor); });
    h.options(entries, [["", h.label("direction_new")]].concat(values.map(function(d) { return [d.id, d.start + "–" + (d.end == null ? Array.from(text.value).length : d.end) + " · " + d.instructions.slice(0,50)]; })), "");
    loadEntry(); select.disabled = save.disabled = !p;
    if (p) h.selected(p);
  }
  passage.addEventListener("change", function() { h.invalidate(); loadPassage(); });
  entries.addEventListener("change", function() { h.invalidate(); loadEntry(); });
  [voice,instructions,before,after].forEach(function(el) { el.addEventListener("input", changed); });
  style.addEventListener("change", function() {
    var styles = {calm:"Read calmly and clearly, with restrained expression.", tense:"Read with restrained tension and controlled urgency, without shouting.", whisper:"Speak in a quiet whisper while keeping every word intelligible."};
    if (styles[style.value]) { instructions.value = styles[style.value]; changed(); }
  });
  async function mutate(deleting) {
    var serial = revision;
    try {
      var payload = Object.assign(h.tokens(), {expected_settings_sha256:view.settings_sha256, expected_direction_sha256:view.direction_sha256});
      if (deleting) { if (!selected) return; payload.remove_id = selected.id; }
      else { payload.direction = read(); if (selected) payload.replace_id = selected.id; }
      save.disabled = remove.disabled = true;
      var data = await h.request("speech-direction", payload);
      if (serial !== revision || !h.current()) return;
      var anchor = passage.value; view = data.direction;
      open(view, anchor, profiles); h.invalidate(); h.status(h.label("direction_saved"));
    } catch (error) { if (serial === revision && h.current()) { h.status(error.message); save.disabled = !current(); remove.disabled = !selected; } }
  }
  function open(data, anchor, available) {
    ++revision; view = data; profiles = available; dirty = false;
    section.disabled = false;
    h.options(voice, [["",h.label("direction_default")]].concat(Object.entries(profiles).map(function(p) { return [p[0],p[1].name]; })), "");
    h.options(passage, [["",h.label("direction_passage")]].concat(view.passages.map(function(p) { return [JSON.stringify(p.anchor), p.chapter + " · " + p.anchor.start_line + "–" + p.anchor.end_line + " · " + p.text.slice(0,65)]; })), typeof anchor === "string" ? anchor : anchor ? JSON.stringify(anchor) : "");
    var stale = view.directions.filter(function(d) { return d.stale; });
    warning.replaceChildren();
    if (stale.length) {
      warning.appendChild(document.createTextNode(h.label("direction_stale") + " (" + stale.length + ") "));
      stale.forEach(function(d) { var button=h.button(warning,"direction_remove",function() { selected=d; mutate(true); }); button.textContent += " · " + d.anchor.start_line + "–" + d.anchor.end_line + " · " + d.instructions.slice(0,40); });
    }
    loadPassage();
  }
  return {open:open, draft:function() { return dirty ? read() : null; },
    dirty:function() { return dirty; }, replacement:function() { return dirty && selected ? selected.id : null; }, disable:function() { section.disabled = true; }};
};
