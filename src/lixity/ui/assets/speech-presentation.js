/* Present canonical speech timeline data without reimplementing text matching. */
window.LixitySpeechPresentation = (function() {
  "use strict";
  function appendText(parent, row, rubyClass) {
    var text = typeof row.spoken_text === "string" ? row.spoken_text : row.text || "";
    var points = Array.from(text), cursor = 0;
    (row.phonemes || []).forEach(function(phone) {
      if (!Number.isInteger(phone.start) || !Number.isInteger(phone.end) || phone.start < cursor ||
          phone.end <= phone.start || phone.end > points.length || typeof phone.ipa !== "string") return;
      parent.appendChild(document.createTextNode(points.slice(cursor, phone.start).join("")));
      var ruby = document.createElement("ruby"), pronunciation = document.createElement("rt");
      ruby.className = rubyClass || "speech-phonetic";
      ruby.appendChild(document.createTextNode(points.slice(phone.start, phone.end).join("")));
      pronunciation.textContent = "[" + phone.ipa + "]";
      ruby.appendChild(pronunciation); parent.appendChild(ruby); cursor = phone.end;
    });
    parent.appendChild(document.createTextNode(points.slice(cursor).join("")));
  }
  function controls(row, label) {
    var result = [], instructions = row.instructions || row.profile && row.profile.instructions;
    if (instructions) result.push(instructions);
    Object.entries(row.prosody || row.profile && row.profile.prosody || {}).forEach(function(pair) {
      result.push(label("speech_prosody_" + pair[0]) + ": " + pair[1]);
    });
    ["before", "after"].forEach(function(position) {
      var value = row["pause_" + position];
      if (typeof value === "number" && value > 0) result.push(label("speech_export_pause_" + position) + ": " + value + " s");
    });
    return result;
  }
  return {appendText:appendText, controls:controls};
})();
