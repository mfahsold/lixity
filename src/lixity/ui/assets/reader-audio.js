// Static chapter playback reuses the Studio player and never starts synthesis.
(function() {
  "use strict";
  var publication = window.LixitySite && window.LixitySite.publication;
  var section = document.getElementById("publication-audio");
  if (!section || !publication || !publication.audio || !window.createSpeechPlayer) return;
  var tracks = publication.audio.tracks;
  if (publication.audio.schema_version !== "lixity-reader-audio/1" || !Array.isArray(tracks) || !tracks.length) return;
  var audio = section.querySelector("audio"), choice = section.querySelector("select");
  var status = document.getElementById("publication-audio-status");
  var download = document.getElementById("publication-audio-download");
  var textLink = document.getElementById("publication-audio-text");
  var player = window.createSpeechPlayer(audio, {
    label: function(key) { return uiLabel("speech_" + key); },
    onError: function(message) { status.textContent = message; }
  });
  function select() {
    var track = tracks.find(function(item) { return String(item.chapter) === choice.value; });
    if (!track || !Number.isInteger(track.chapter) || track.chapter < 1 || track.chapter > publication.max_chapter ||
        !/^assets\/audio\/[0-9a-f]{64}\.wav$/.test(track.file)) return;
    audio.pause(); audio.src = track.file; audio.load(); player.refresh();
    download.href = track.file; download.download = "chapter-" + track.chapter + ".wav";
    textLink.href = "#publication-chapter-" + track.chapter;
    status.textContent = uiLabel(track.origin === "imported" ? "publication_audio_imported" : "publication_audio_generated");
  }
  choice.addEventListener("change", select);
  section.addEventListener("toggle", function() {
    if (!section.open) audio.pause();
    player.refresh();
  });
  document.querySelectorAll('a[href="#publication-audio"]').forEach(function(link) {
    link.addEventListener("click", function() { section.open = true; });
  });
  // A chapter switch changes the selection only. Play always requires a user action.
  window.addEventListener("pagehide", function() { audio.pause(); });
  select();
})();
