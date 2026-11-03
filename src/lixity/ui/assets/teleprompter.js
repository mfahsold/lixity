/**
 * Lixity Teleprompter: Fullscreen reading mode with auto-scroll, direction cues,
 * phonetics and synchronized historical research images from dossiers.
 */
(function() {
  "use strict";

  var modal = null;
  var scrollPane = null;
  var sidebar = null;
  var sidebarContent = null;
  var sidebarToggleBtn = null;
  var playBtn = null;
  var speedSlider = null;
  var speedVal = null;
  var chapterSelect = null;
  var recordBtn = null;
  var recordStatusAnnouncer = null;

  var isPlaying = false;
  var isRecording = false;
  var recordStartTime = 0;
  var recordTimerId = null;
  var mediaRecorder = null;
  var recordedAudioChunks = [];
  var lastRecordedBlobUrl = null;

  var wordsPerMinute = 130;
  var fontSize = 32;
  var animFrameId = null;
  var lastTimestamp = 0;
  var activeParagraphSha = null;
  var previousActiveElement = null;

  var speechData = null;
  var researchDossiers = null;
  var manuscriptLinks = null;

  function label(key, fallback) {
    if (typeof window.uiLabel === "function") {
      var l = window.uiLabel(key);
      if (l && !l.startsWith("teleprompter_") && !l.startsWith("reading_")) return l;
    }
    return fallback || key;
  }

  function fetchApi(path, options) {
    var prefix = document.body.dataset.api || "/api";
    return fetch(prefix.replace(/\/api$/, "") + path, options).then(function(res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    });
  }

  function loadContextData() {
    // 1. Fetch speech settings, pronunciations & directions
    fetchApi("/api/speech").then(function(data) {
      speechData = data;
      if (modal && !modal.hidden) buildRunwayContent();
    }).catch(function() {});

    // 2. Fetch research dossiers
    fetchApi("/api/research/dossiers").then(function(data) {
      if (data && data.dossiers) researchDossiers = data.dossiers;
    }).catch(function() {});

    // 3. Fetch manuscript links
    fetchApi("/api/research/manuscript-links").then(function(data) {
      if (data && data.links) manuscriptLinks = data.links;
    }).catch(function() {});
  }

  function createModal() {
    if (modal) return;
    modal = document.createElement("div");
    modal.id = "teleprompter-modal";
    modal.hidden = true;
    modal.setAttribute("role", "dialog");
    modal.setAttribute("aria-modal", "true");
    modal.setAttribute("aria-label", label("reading_teleprompter", "Teleprompter"));

    recordStatusAnnouncer = document.createElement("div");
    recordStatusAnnouncer.className = "visually-hidden";
    recordStatusAnnouncer.setAttribute("aria-live", "polite");
    modal.appendChild(recordStatusAnnouncer);

    // Toolbar
    var toolbar = document.createElement("header");
    toolbar.className = "teleprompter-toolbar";

    var leftGroup = document.createElement("div");
    leftGroup.className = "teleprompter-toolbar-group";

    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "teleprompter-btn";
    closeBtn.textContent = "✕ " + label("reading_shortcut_close", "Schließen");
    closeBtn.setAttribute("aria-label", label("reading_shortcut_close", "Schließen"));
    closeBtn.addEventListener("click", closeTeleprompter);
    leftGroup.appendChild(closeBtn);

    playBtn = document.createElement("button");
    playBtn.type = "button";
    playBtn.className = "teleprompter-btn teleprompter-btn-primary";
    playBtn.textContent = "▶ " + label("teleprompter_play", "Lauf starten");
    playBtn.setAttribute("aria-label", label("teleprompter_play", "Lauf starten"));
    playBtn.addEventListener("click", togglePlay);
    leftGroup.appendChild(playBtn);

    chapterSelect = document.createElement("select");
    chapterSelect.className = "teleprompter-btn";
    chapterSelect.setAttribute("aria-label", label("reading_chapter", "Kapitel"));
    chapterSelect.addEventListener("change", function() {
      var targetId = chapterSelect.value;
      if (!targetId) return;
      var targetEl = scrollPane.querySelector('[data-chapter-id="' + targetId + '"]');
      if (targetEl) targetEl.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    leftGroup.appendChild(chapterSelect);

    toolbar.appendChild(leftGroup);

    // Center Group: Speed & Size
    var centerGroup = document.createElement("div");
    centerGroup.className = "teleprompter-toolbar-group";

    var speedWrapper = document.createElement("div");
    speedWrapper.className = "teleprompter-speed-control";
    var speedLabel = document.createElement("span");
    speedLabel.textContent = label("teleprompter_speed", "Tempo") + ":";
    speedWrapper.appendChild(speedLabel);

    speedSlider = document.createElement("input");
    speedSlider.type = "range";
    speedSlider.min = "60";
    speedSlider.max = "240";
    speedSlider.value = String(wordsPerMinute);
    speedSlider.step = "5";
    speedSlider.setAttribute("aria-label", label("teleprompter_speed", "Tempo"));
    speedSlider.addEventListener("input", function() {
      wordsPerMinute = parseInt(speedSlider.value, 10);
      speedVal.textContent = wordsPerMinute + " WpM";
    });
    speedWrapper.appendChild(speedSlider);

    speedVal = document.createElement("span");
    speedVal.className = "teleprompter-speed-val";
    speedVal.textContent = wordsPerMinute + " WpM";
    speedWrapper.appendChild(speedVal);

    centerGroup.appendChild(speedWrapper);

    // Font Size Controls
    var sizeMinus = document.createElement("button");
    sizeMinus.type = "button";
    sizeMinus.className = "teleprompter-btn";
    sizeMinus.textContent = "A−";
    sizeMinus.setAttribute("aria-label", label("reading_smaller", "Schrift verkleinern"));
    sizeMinus.addEventListener("click", function() {
      fontSize = Math.max(20, fontSize - 4);
      modal.style.setProperty("--teleprompter-font-size", fontSize + "px");
    });
    centerGroup.appendChild(sizeMinus);

    var sizePlus = document.createElement("button");
    sizePlus.type = "button";
    sizePlus.className = "teleprompter-btn";
    sizePlus.textContent = "A+";
    sizePlus.setAttribute("aria-label", label("reading_larger", "Schrift vergrößern"));
    sizePlus.addEventListener("click", function() {
      fontSize = Math.min(56, fontSize + 4);
      modal.style.setProperty("--teleprompter-font-size", fontSize + "px");
    });
    centerGroup.appendChild(sizePlus);

    toolbar.appendChild(centerGroup);

    // Right Group: Dossier Toggle & Recording
    var rightGroup = document.createElement("div");
    rightGroup.className = "teleprompter-toolbar-group";

    sidebarToggleBtn = document.createElement("button");
    sidebarToggleBtn.type = "button";
    sidebarToggleBtn.className = "teleprompter-btn";
    sidebarToggleBtn.textContent = "🏛 " + label("teleprompter_dossier_context", "Dossiers");
    sidebarToggleBtn.setAttribute("aria-label", label("teleprompter_dossier_context", "Dossiers"));
    sidebarToggleBtn.addEventListener("click", function() {
      if (sidebar) sidebar.classList.toggle("is-open");
    });
    rightGroup.appendChild(sidebarToggleBtn);

    recordBtn = document.createElement("button");
    recordBtn.type = "button";
    recordBtn.className = "teleprompter-btn teleprompter-btn-record";
    recordBtn.textContent = "🎙 " + label("teleprompter_record", "Aufnahme");
    recordBtn.setAttribute("aria-label", label("teleprompter_record", "Aufnahme"));
    recordBtn.addEventListener("click", toggleRecording);
    rightGroup.appendChild(recordBtn);

    toolbar.appendChild(rightGroup);
    modal.appendChild(toolbar);

    // Body
    var body = document.createElement("div");
    body.className = "teleprompter-body";

    // Runway Container
    var runwayContainer = document.createElement("div");
    runwayContainer.className = "teleprompter-runway-container";

    var ribbon = document.createElement("div");
    ribbon.className = "teleprompter-focus-ribbon";
    runwayContainer.appendChild(ribbon);

    scrollPane = document.createElement("main");
    scrollPane.className = "teleprompter-scroll-pane";
    scrollPane.addEventListener("scroll", handleScrollSync);
    runwayContainer.appendChild(scrollPane);

    body.appendChild(runwayContainer);

    // Sidebar: Historical Dossiers & Context
    sidebar = document.createElement("aside");
    sidebar.className = "teleprompter-sidebar";

    var sidebarHeader = document.createElement("div");
    sidebarHeader.className = "teleprompter-sidebar-header";
    var sidebarTitle = document.createElement("span");
    sidebarTitle.textContent = "🏛 " + label("teleprompter_dossier_context", "Historischer Kontext & Dossier-Bilder");
    sidebarHeader.appendChild(sidebarTitle);

    var sidebarClose = document.createElement("button");
    sidebarClose.type = "button";
    sidebarClose.className = "teleprompter-btn";
    sidebarClose.style.padding = "0.2rem 0.4rem";
    sidebarClose.style.fontSize = "0.75rem";
    sidebarClose.textContent = "✕";
    sidebarClose.setAttribute("aria-label", label("reading_shortcut_close", "Schließen"));
    sidebarClose.addEventListener("click", function() {
      sidebar.classList.remove("is-open");
    });
    sidebarHeader.appendChild(sidebarClose);
    sidebar.appendChild(sidebarHeader);

    sidebarContent = document.createElement("div");
    sidebarContent.className = "teleprompter-sidebar-content";
    sidebar.appendChild(sidebarContent);

    body.appendChild(sidebar);
    modal.appendChild(body);
    document.body.appendChild(modal);

    modal.style.setProperty("--teleprompter-font-size", fontSize + "px");

    // Keyboard controls
    document.addEventListener("keydown", function(e) {
      if (!modal || modal.hidden) return;
      if (e.code === "Space") {
        e.preventDefault();
        togglePlay();
      } else if (e.code === "Escape") {
        e.preventDefault();
        closeTeleprompter();
      } else if (e.code === "ArrowUp") {
        e.preventDefault();
        wordsPerMinute = Math.min(240, wordsPerMinute + 10);
        speedSlider.value = String(wordsPerMinute);
        speedVal.textContent = wordsPerMinute + " WpM";
      } else if (e.code === "ArrowDown") {
        e.preventDefault();
        wordsPerMinute = Math.max(60, wordsPerMinute - 10);
        speedSlider.value = String(wordsPerMinute);
        speedVal.textContent = wordsPerMinute + " WpM";
      } else if (e.key === "+" || e.key === "=") {
        e.preventDefault();
        fontSize = Math.min(56, fontSize + 4);
        modal.style.setProperty("--teleprompter-font-size", fontSize + "px");
      } else if (e.key === "-" || e.key === "_") {
        e.preventDefault();
        fontSize = Math.max(20, fontSize - 4);
        modal.style.setProperty("--teleprompter-font-size", fontSize + "px");
      } else if (e.code === "KeyD" && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        if (sidebar) sidebar.classList.toggle("is-open");
      }
    });
  }

  function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function applyPronunciations(text, pronunciations) {
    if (!pronunciations || !Object.keys(pronunciations).length) return text;
    var keys = Object.keys(pronunciations).sort(function(a, b) { return b.length - a.length; });
    var pattern = new RegExp("\\b(" + keys.map(escapeRegex).join("|") + ")\\b", "g");
    return text.replace(pattern, function(match) {
      var spoken = pronunciations[match];
      return '<ruby class="teleprompter-phonetic">' + match + '<rt>[' + spoken + ']</rt></ruby>';
    });
  }

  function findDirectionForParagraph(startLine, endLine, sha) {
    if (!speechData || !speechData.direction || !speechData.direction.directions) return null;
    return speechData.direction.directions.find(function(d) {
      if (!d.anchor) return false;
      return (sha && d.anchor.paragraph_sha256 === sha) ||
             (d.anchor.start_line <= endLine && d.anchor.end_line >= startLine);
    });
  }

  function buildRunwayContent() {
    if (!scrollPane) return;
    scrollPane.replaceChildren();
    chapterSelect.replaceChildren();

    var chaptersContainer = document.getElementById("chapters");
    if (!chaptersContainer) return;

    var pronunciations = (speechData && speechData.settings && speechData.settings.pronunciations) || {};
    var chapterElements = Array.from(chaptersContainer.querySelectorAll(".chapter"));

    chapterElements.forEach(function(chapterEl, idx) {
      var chId = chapterEl.id || ("ch-" + (idx + 1));
      var headingEl = chapterEl.querySelector("h2, h3, .chapter-title");
      var chTitle = headingEl ? headingEl.textContent.trim() : ("Kapitel " + (idx + 1));

      var opt = document.createElement("option");
      opt.value = chId;
      opt.textContent = chTitle;
      chapterSelect.appendChild(opt);

      // Chapter heading in runway
      var chHeading = document.createElement("div");
      chHeading.className = "teleprompter-chapter-heading";
      chHeading.setAttribute("data-chapter-id", chId);
      chHeading.style.fontSize = "0.75em";
      chHeading.style.color = "#f0883e";
      chHeading.style.textTransform = "uppercase";
      chHeading.style.letterSpacing = "0.08em";
      chHeading.style.margin = "2.5rem 0 1rem 0";
      chHeading.style.fontWeight = "bold";
      chHeading.textContent = chTitle;
      scrollPane.appendChild(chHeading);

      var pElements = Array.from(chapterEl.querySelectorAll(".ptext"));
      pElements.forEach(function(pEl) {
        var startLine = Number(pEl.dataset.start || 0);
        var endLine = Number(pEl.dataset.end || 0);
        var sha = pEl.dataset.paragraphSha256 || "";
        var innerP = pEl.querySelector(".ptext-inner > p") || pEl;
        var rawText = innerP.textContent.trim();
        if (!rawText) return;

        var pNode = document.createElement("div");
        pNode.className = "teleprompter-paragraph";
        pNode.setAttribute("data-start", startLine);
        pNode.setAttribute("data-end", endLine);
        pNode.setAttribute("data-sha", sha);
        pNode.setAttribute("data-chapter-id", chId);

        // Direction / Regieanweisung
        var dir = findDirectionForParagraph(startLine, endLine, sha);
        if (dir && dir.instructions) {
          var cue = document.createElement("div");
          cue.className = "teleprompter-cue";
          var icon = document.createElement("span");
          icon.textContent = "🎬";
          cue.appendChild(icon);
          var textSpan = document.createElement("span");
          textSpan.textContent = dir.instructions;
          cue.appendChild(textSpan);
          if (dir.pause_after != null && dir.pause_after > 0) {
            var pauseSpan = document.createElement("span");
            pauseSpan.className = "teleprompter-cue-pause";
            pauseSpan.textContent = "+" + dir.pause_after.toFixed(1) + "s Pause";
            cue.appendChild(pauseSpan);
          }
          pNode.appendChild(cue);
        }

        // Text with phonetics
        var textNode = document.createElement("div");
        textNode.className = "teleprompter-text";
        textNode.innerHTML = applyPronunciations(rawText, pronunciations);
        pNode.appendChild(textNode);

        scrollPane.appendChild(pNode);
      });
    });
  }

  function updateDossierSidebar(paragraphNode) {
    if (!sidebarContent || !paragraphNode) return;
    var sha = paragraphNode.getAttribute("data-sha");
    if (sha === activeParagraphSha) return;
    activeParagraphSha = sha;

    // Remove old active highlight
    var prevActive = scrollPane.querySelector(".teleprompter-paragraph.is-active");
    if (prevActive) prevActive.classList.remove("is-active");
    paragraphNode.classList.add("is-active");

    sidebarContent.replaceChildren();

    // 1. Check direct manuscript links
    var matchedLinks = (manuscriptLinks || []).filter(function(l) {
      return l.anchor && l.anchor.paragraph_sha256 === sha;
    });

    var shownImages = new Set();

    if (matchedLinks.length && researchDossiers) {
      matchedLinks.forEach(function(l) {
        var d = researchDossiers.find(function(item) { return item.id === l.dossier_id; });
        if (d && d.images && d.images.length) {
          d.images.forEach(function(img) {
            if (!shownImages.has(img.id)) {
              shownImages.add(img.id);
              renderDossierCard(d.title, img);
            }
          });
        }
      });
    }

    // 2. Heuristic text search in dossiers if no direct link
    if (!shownImages.size && researchDossiers) {
      var pText = paragraphNode.textContent.toLowerCase();
      researchDossiers.forEach(function(d) {
        if (!d.images || !d.images.length) return;
        var titleMatch = d.title && pText.includes(d.title.toLowerCase());
        var tagMatch = (d.tags || []).some(function(t) { return t.length > 3 && pText.includes(t.toLowerCase()); });
        if (titleMatch || tagMatch) {
          d.images.forEach(function(img) {
            if (!shownImages.has(img.id) && shownImages.size < 2) {
              shownImages.add(img.id);
              renderDossierCard(d.title, img);
            }
          });
        }
      });
    }

    if (!shownImages.size) {
      var emptyNote = document.createElement("div");
      emptyNote.className = "teleprompter-sidebar-empty";
      emptyNote.textContent = label("teleprompter_no_images", "Keine Dossier-Bilder mit dieser Passage verknüpft.");
      sidebarContent.appendChild(emptyNote);
    }
  }

  function renderDossierCard(title, image) {
    var card = document.createElement("div");
    card.className = "teleprompter-dossier-card";

    var img = document.createElement("img");
    img.className = "teleprompter-dossier-img";
    img.src = "/api/research/media?id=" + encodeURIComponent(image.id || image.source_id || "");
    img.alt = image.caption || title || "Historisches Bild";
    img.onerror = function() {
      img.style.display = "none";
    };
    card.appendChild(img);

    var meta = document.createElement("div");
    meta.className = "teleprompter-dossier-meta";

    var h = document.createElement("div");
    h.className = "teleprompter-dossier-title";
    h.textContent = title;
    meta.appendChild(h);

    if (image.caption || (image.context && image.context.provenance_note)) {
      var cap = document.createElement("p");
      cap.className = "teleprompter-dossier-caption";
      cap.textContent = image.caption || image.context.provenance_note;
      meta.appendChild(cap);
    }

    card.appendChild(meta);
    sidebarContent.appendChild(card);
  }

  function handleScrollSync() {
    if (!scrollPane) return;
    var ribbonTop = window.innerHeight * 0.30;
    var paragraphs = Array.from(scrollPane.querySelectorAll(".teleprompter-paragraph"));
    var closest = null;
    var minDiff = Infinity;

    paragraphs.forEach(function(p) {
      var rect = p.getBoundingClientRect();
      var diff = Math.abs(rect.top - ribbonTop);
      if (diff < minDiff) {
        minDiff = diff;
        closest = p;
      }
    });

    if (closest) {
      updateDossierSidebar(closest);
    }
  }

  function scrollLoop(timestamp) {
    if (!isPlaying) return;
    if (!lastTimestamp) lastTimestamp = timestamp;
    var delta = (timestamp - lastTimestamp) / 1000.0;
    lastTimestamp = timestamp;

    if (scrollPane) {
      var wordsPerSecond = wordsPerMinute / 60.0;
      var pixelsPerSecond = wordsPerSecond * (fontSize * 0.95);
      scrollPane.scrollTop += pixelsPerSecond * delta;
      handleScrollSync();
    }

    animFrameId = requestAnimationFrame(scrollLoop);
  }

  function togglePlay() {
    isPlaying = !isPlaying;
    if (isPlaying) {
      playBtn.textContent = "⏸ " + label("teleprompter_pause", "Pause");
      playBtn.setAttribute("aria-label", label("teleprompter_pause", "Pause"));
      lastTimestamp = 0;
      animFrameId = requestAnimationFrame(scrollLoop);
    } else {
      playBtn.textContent = "▶ " + label("teleprompter_play", "Lauf starten");
      playBtn.setAttribute("aria-label", label("teleprompter_play", "Lauf starten"));
      if (animFrameId) cancelAnimationFrame(animFrameId);
    }
  }

  function startAudioCapture() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
    recordedAudioChunks = [];
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function(stream) {
      try {
        var options = { mimeType: "audio/webm" };
        if (!MediaRecorder.isTypeSupported("audio/webm")) {
          options = MediaRecorder.isTypeSupported("audio/ogg") ? { mimeType: "audio/ogg" } : {};
        }
        mediaRecorder = new MediaRecorder(stream, options);
        mediaRecorder.ondataavailable = function(e) {
          if (e.data && e.data.size > 0) recordedAudioChunks.push(e.data);
        };
        mediaRecorder.onstop = function() {
          stream.getTracks().forEach(function(track) { track.stop(); });
          if (recordedAudioChunks.length > 0) {
            var blob = new Blob(recordedAudioChunks, { type: mediaRecorder.mimeType || "audio/webm" });
            if (lastRecordedBlobUrl) URL.revokeObjectURL(lastRecordedBlobUrl);
            lastRecordedBlobUrl = URL.createObjectURL(blob);
            offerRecordingDownload(blob);
          }
        };
        mediaRecorder.start(250);
      } catch (err) {
        stream.getTracks().forEach(function(track) { track.stop(); });
      }
    }).catch(function() {});
  }

  function stopAudioCapture() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      try {
        mediaRecorder.stop();
      } catch (err) {}
    }
  }

  function offerRecordingDownload(blob) {
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "teleprompter-recording-" + (new Date().toISOString().replace(/[:.]/g, "-")) + ".webm";
    a.className = "teleprompter-btn";
    a.style.background = "#238636";
    a.style.color = "#ffffff";
    a.textContent = "💾 " + label("speech_download", "Aufnahme herunterladen");
    if (sidebarContent) {
      var note = document.createElement("div");
      note.className = "teleprompter-dossier-card";
      note.style.padding = "0.75rem";
      note.style.textAlign = "center";
      note.appendChild(a);
      sidebarContent.prepend(note);
    }
  }

  function toggleRecording() {
    isRecording = !isRecording;
    if (isRecording) {
      recordBtn.classList.add("is-active");
      recordBtn.textContent = "⏹ " + label("teleprompter_recording", "Aufnahme läuft...");
      recordBtn.setAttribute("aria-label", label("teleprompter_recording", "Aufnahme läuft..."));
      if (recordStatusAnnouncer) recordStatusAnnouncer.textContent = "Audioaufnahme gestartet";
      recordStartTime = Date.now();
      recordTimerId = setInterval(function() {
        var elapsed = Math.floor((Date.now() - recordStartTime) / 1000);
        var m = String(Math.floor(elapsed / 60)).padStart(2, "0");
        var s = String(elapsed % 60).padStart(2, "0");
        recordBtn.textContent = "⏹ " + m + ":" + s;
      }, 1000);

      startAudioCapture();
      if (!isPlaying) togglePlay();
    } else {
      recordBtn.classList.remove("is-active");
      recordBtn.textContent = "🎙 " + label("teleprompter_record", "Aufnahme");
      recordBtn.setAttribute("aria-label", label("teleprompter_record", "Aufnahme"));
      if (recordStatusAnnouncer) recordStatusAnnouncer.textContent = "Audioaufnahme gestoppt";
      if (recordTimerId) clearInterval(recordTimerId);
      stopAudioCapture();
      if (isPlaying) togglePlay();
    }
  }

  function openTeleprompter(startParagraphSha) {
    previousActiveElement = document.activeElement;
    createModal();
    buildRunwayContent();
    modal.hidden = false;
    document.body.classList.add("teleprompter-open");

    // Scroll to initial paragraph
    if (startParagraphSha) {
      setTimeout(function() {
        var el = scrollPane.querySelector('[data-sha="' + startParagraphSha + '"]');
        if (el) {
          el.scrollIntoView({ behavior: "auto", block: "center" });
          updateDossierSidebar(el);
        }
      }, 50);
    } else {
      handleScrollSync();
    }

    if (playBtn) playBtn.focus();
  }

  function closeTeleprompter() {
    if (isPlaying) togglePlay();
    if (isRecording) toggleRecording();
    if (modal) modal.hidden = true;
    document.body.classList.remove("teleprompter-open");

    // Two-way sync: scroll reader view to active paragraph
    if (activeParagraphSha) {
      var readerP = document.querySelector('#chapters .ptext[data-paragraph-sha256="' + activeParagraphSha + '"]');
      if (readerP) {
        readerP.scrollIntoView({ behavior: "smooth", block: "center" });
        readerP.focus();
      }
    } else if (previousActiveElement && typeof previousActiveElement.focus === "function") {
      previousActiveElement.focus();
    }
  }

  function init() {
    loadContextData();

    document.addEventListener("click", function(e) {
      var target = e.target.closest("#reader-teleprompter");
      if (target) {
        e.preventDefault();
        var selected = document.querySelector("#chapters .ptext.reader-selected, #chapters .ptext:focus-within");
        var sha = selected ? selected.dataset.paragraphSha256 : "";
        openTeleprompter(sha);
      }
    });

    document.addEventListener("keydown", function(e) {
      if (e.code === "KeyP" && !e.ctrlKey && !e.altKey && !e.metaKey) {
        var activeEl = document.activeElement;
        if (activeEl && (activeEl.tagName === "INPUT" || activeEl.tagName === "TEXTAREA" || activeEl.isContentEditable)) {
          return;
        }
        var readerMode = document.getElementById("manuscript-mode");
        if (readerMode && readerMode.value === "read" && (!modal || modal.hidden)) {
          e.preventDefault();
          var selected = document.querySelector("#chapters .ptext.reader-selected, #chapters .ptext:focus-within");
          var sha = selected ? selected.dataset.paragraphSha256 : "";
          openTeleprompter(sha);
        }
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.LixityTeleprompter = {
    open: openTeleprompter,
    close: closeTeleprompter,
  };
})();