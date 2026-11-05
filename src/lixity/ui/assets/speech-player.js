/* Shared local audio controls. Spectrum bars represent measured FFT bins. */
(function() {
  "use strict";
  window.createSpeechPlayer = function(audio, options) {
    var label = options.label, onError = options.onError || function() {};
    var context = null, source = null, analyser = null, liveAnalyser = null;
    var frame = null, destroyed = false, spectrumFailed = false, frequencyData = null;
    var listeners = [];
    function node(tag, parent, className) {
      var item = document.createElement(tag); item.className = className || "";
      if (parent) parent.appendChild(item); return item;
    }
    function listen(target, event, callback) {
      target.addEventListener(event, callback); listeners.push([target, event, callback]);
    }
    function namedControl(tag, parent, key) {
      var item = node(tag, parent, "ctl"); item.setAttribute("aria-label", label(key));
      item.dataset.help = label(key); item.title = label(key); return item;
    }
    function time(value) {
      if (!Number.isFinite(value) || value < 0) return "–:––";
      return Math.floor(value / 60) + ":" + String(Math.floor(value % 60)).padStart(2, "0");
    }
    var element = node("section", null, "speech-player");
    element.setAttribute("aria-label", label("player_title"));
    audio.after(element); audio.controls = false; audio.classList.add("speech-player-native");
    var spectrum = node("div", element, "speech-player-spectrum");
    var spectrumHeader = node("div", spectrum, "speech-player-spectrum-label");
    var spectrumTitle = node("span", spectrumHeader); spectrumTitle.textContent = label("player_spectrum");
    spectrumTitle.title = label("player_spectrum_help"); spectrumTitle.dataset.help = label("player_spectrum_help");
    spectrumTitle.tabIndex = 0;
    var spectrumState = node("span", spectrumHeader, "speech-player-spectrum-state");
    var canvas = node("canvas", spectrum, "speech-player-canvas"); canvas.setAttribute("aria-hidden", "true");
    var axis = node("div", spectrum, "speech-player-axis");
    node("span", axis).textContent = "0 Hz";
    var highFrequency = node("span", axis); highFrequency.textContent = "– kHz";
    var controls = node("div", element, "speech-player-controls");
    var play = namedControl("button", controls, "player_play"); play.type = "button"; play.textContent = "▶";
    var clock = node("span", controls, "speech-player-time");
    var seek = namedControl("input", controls, "player_seek"); seek.type = "range"; seek.min = "0"; seek.max = "0"; seek.step = "0.01";
    seek.classList.add("speech-player-seek");
    var volumeGroup = node("div", controls, "speech-player-volume");
    var mute = namedControl("button", volumeGroup, "player_mute"); mute.type = "button"; mute.textContent = "♪";
    var volume = namedControl("input", volumeGroup, "player_volume"); volume.type = "range";
    volume.min = "0"; volume.max = "1"; volume.step = "0.01";
    function name(control, key) {
      control.setAttribute("aria-label", label(key)); control.title = label(key); control.dataset.help = label(key);
    }
    function update() {
      if (destroyed) return;
      element.hidden = !liveAnalyser && (audio.hidden || !audio.getAttribute("src"));
      var duration = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : 0;
      var position = Math.max(0, Number.isFinite(audio.currentTime) ? audio.currentTime : 0);
      var playing = !audio.paused && !audio.ended;
      play.disabled = Boolean(liveAnalyser) || !audio.getAttribute("src");
      seek.disabled = Boolean(liveAnalyser) || !duration;
      mute.disabled = volume.disabled = Boolean(liveAnalyser);
      name(play, playing ? "player_pause" : "player_play"); play.textContent = playing ? "Ⅱ" : "▶";
      clock.textContent = time(position) + " / " + time(duration || NaN);
      seek.max = String(duration); seek.value = String(Math.min(position, duration));
      seek.setAttribute("aria-valuetext", time(position) + " / " + time(duration || NaN));
      name(mute, audio.muted ? "player_unmute" : "player_mute");
      mute.textContent = audio.muted ? "×♪" : "♪"; mute.setAttribute("aria-pressed", String(audio.muted));
      volume.value = String(audio.volume); volume.setAttribute("aria-valuetext", Math.round(audio.volume * 100) + "%");
      spectrumState.textContent = spectrumFailed ? label("player_spectrum_unavailable") : liveAnalyser ? label("player_live") : "";
      if (element.hidden) stopDrawing(); else startDrawing();
    }
    function draw() {
      frame = null;
      if (destroyed || element.hidden) return;
      var active = liveAnalyser || (!audio.paused && !audio.ended ? analyser : null);
      element.dataset.spectrum = liveAnalyser ? "live" : active ? "playback" : "idle";
      var width = Math.max(1, canvas.clientWidth), height = Math.max(1, canvas.clientHeight), scale = window.devicePixelRatio || 1;
      if (canvas.width !== Math.round(width * scale) || canvas.height !== Math.round(height * scale)) {
        canvas.width = Math.round(width * scale); canvas.height = Math.round(height * scale);
      }
      var painter = canvas.getContext("2d");
      if (!painter) return;
      painter.setTransform(scale, 0, 0, scale, 0, 0); painter.clearRect(0, 0, width, height);
      // Resolve the browser's theme color; canvas cannot consume CSS variables.
      painter.fillStyle = getComputedStyle(canvas).color;
      if (active) {
        if (!frequencyData || frequencyData.length !== active.frequencyBinCount) frequencyData = new Uint8Array(active.frequencyBinCount);
        active.getByteFrequencyData(frequencyData);
        highFrequency.textContent = (active.context.sampleRate / 2000).toFixed(1) + " kHz";
        var count = Math.min(48, frequencyData.length), bandWidth = width / count;
        for (var band = 0; band < count; band++) {
          var start = Math.floor(band * frequencyData.length / count), end = Math.floor((band + 1) * frequencyData.length / count), peak = 0;
          for (var bin = start; bin < end; bin++) peak = Math.max(peak, frequencyData[bin]);
          var barHeight = peak / 255 * (height - 2);
          if (barHeight > 0) painter.fillRect(band * bandWidth, height - barHeight, Math.max(1, bandWidth - 2), barHeight);
        }
      }
      painter.globalAlpha = 0.25; painter.fillRect(0, height - 1, width, 1); painter.globalAlpha = 1;
      if (active) frame = requestAnimationFrame(draw);
    }
    function startDrawing() { if (frame == null) frame = requestAnimationFrame(draw); }
    function stopDrawing() { if (frame != null) cancelAnimationFrame(frame); frame = null; }
    async function prepareSpectrum() {
      if (spectrumFailed || destroyed) return;
      try {
        // Local file origins can silently zero a MediaElementAudioSourceNode.
        // Keep native playback intact; a hosted copy can provide the spectrum.
        if (new URL(audio.currentSrc || audio.src, document.baseURI).protocol === "file:") {
          throw new Error("Local file spectrum unavailable");
        }
        if (!context) {
          var AudioContextClass = window.AudioContext || window.webkitAudioContext;
          if (!AudioContextClass) throw new Error("Web Audio unavailable");
          context = new AudioContextClass();
          analyser = context.createAnalyser(); analyser.fftSize = 512; analyser.smoothingTimeConstant = 0.7;
          source = context.createMediaElementSource(audio); source.connect(analyser); analyser.connect(context.destination);
        }
        if (context.state === "suspended") await context.resume();
      } catch (_) {
        spectrumFailed = true;
        // If an analyser failed after source attachment, retain audible output.
        if (source && context) { source.disconnect(); source.connect(context.destination); }
        analyser = null;
      }
      update();
    }
    listen(play, "click", async function() {
      if (!audio.paused && !audio.ended) { audio.pause(); return; }
      // Resume and play inside the click's user activation, before awaiting.
      var preparation = prepareSpectrum();
      try { await audio.play(); } catch (_) { onError(label("player_error")); }
      await preparation; update();
    });
    listen(seek, "input", function() {
      if (Number.isFinite(audio.duration)) audio.currentTime = Math.min(audio.duration, Math.max(0, Number(seek.value)));
      update();
    });
    listen(volume, "input", function() { audio.volume = Number(volume.value); audio.muted = false; update(); });
    listen(mute, "click", function() { audio.muted = !audio.muted; update(); });
    listen(audio, "play", function() { prepareSpectrum(); });
    ["pause", "ended", "timeupdate", "loadedmetadata", "durationchange", "volumechange", "emptied", "loadstart"].forEach(function(event) { listen(audio, event, update); });
    listen(audio, "error", function() { update(); if (audio.getAttribute("src")) onError(label("player_error")); });
    listen(window, "resize", function() { if (!element.hidden) startDrawing(); });
    var observer = new MutationObserver(update); observer.observe(audio, {attributes: true, attributeFilter: ["src", "hidden"]});
    update();
    return {
      element: element,
      setLiveAnalyser: function(value) { audio.pause(); liveAnalyser = value; update(); },
      clearLiveAnalyser: function() { liveAnalyser = null; update(); },
      refresh: update,
      destroy: function() {
        destroyed = true; stopDrawing(); observer.disconnect(); audio.pause();
        listeners.forEach(function(entry) { entry[0].removeEventListener(entry[1], entry[2]); });
        if (source) source.disconnect(); if (analyser) analyser.disconnect();
        if (context) context.close().catch(function() {});
        // A media element cannot detach from its MediaElementAudioSourceNode.
        // Dispose both together rather than restore native controls that are silent.
        audio.removeAttribute("src"); audio.load(); audio.remove(); element.remove();
      }
    };
  };
})();
