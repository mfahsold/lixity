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
  var planStatus = null;

  var isPlaying = false;
  var isRecording = false;
  var recordStartTime = 0;
  var recordTimerId = null;
  var takeCard = null, currentTake = null, takeContext = null, takePlayer = null;
  var takeImportBtn = null, takeFiles = null, sidebarScroll = null, takeSequence = 0;
  var lastRecordedBlobUrl = null;

  var wordsPerMinute = 130;
  var fontSize = 28;
  var animFrameId = null;
  var lastTimestamp = 0;
  var activeParagraphSha = null;
  var previousActiveElement = null;

  var speechData = null;
  var researchDossiers = null;
  var passageContexts = null, researchView = null, dossierReads = new Map();
  var activeDossierKey = null, dossierSequence = 0;
  var spokenParagraphs = new WeakMap();

  function label(key) {
    return typeof window.uiLabel === "function" ? window.uiLabel(key) : key;
  }

  function fetchApi(path, options) {
    var prefix = document.body.dataset.api || "/api";
    return fetch(prefix.replace(/\/api$/, "") + path, options).then(function(res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    });
  }

  var contextSequence = 0;
  function selectedContext() {
    var form = document.getElementById("settings-form");
    return {project_token: form ? form.dataset.projectToken || "" : "", source_sha256: document.body.dataset.manuscriptSourceSha256 || ""};
  }
  function loadContextData() {
    var sequence = ++contextSequence, selected = selectedContext(), identity = JSON.stringify(selected);
    function current() { return sequence === contextSequence && modal && !modal.hidden && identity === JSON.stringify(selectedContext()); }
    if (document.body.dataset.speechCapable === "true" && selected.project_token && selected.source_sha256) {
      planStatus.hidden = false; planStatus.dataset.state = "loading";
      planStatus.textContent = label("teleprompter_plan_loading");
      fetchApi("/api/speech-plan", {method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify(Object.assign({}, selected, {mode:"manuscript", chapter:null}))}).then(function(data) {
        if (!current()) return;
        if (!data.ok || !data.timeline || !Array.isArray(data.timeline.segments)) throw new Error("Speech timeline unavailable");
        speechData = data.timeline; buildRunwayContent();
        planStatus.dataset.state = "ready"; planStatus.textContent = label("teleprompter_plan_ready");
      }).catch(function() {
        if (!current()) return;
        speechData = null; buildRunwayContent();
        planStatus.dataset.state = "failed"; planStatus.textContent = label("teleprompter_plan_failed");
      });
    }
    // Research access shares the workspace's explicit archive boundary.
    if (typeof researchApiGet !== "function" || typeof researchContextToken !== "function" ||
        !researchContextToken() || !selected.project_token) return;
    if (!window.LixityDossierImages) { dossierFailure(); return; }
    var researchToken = researchContextToken();
    var view = {state:"loading", project:null, token:selected.project_token, invalidated:false,
      current:function() { return !view.invalidated && current() && researchContextToken() === researchToken; }};
    researchView = view;
    dossierNote("loading", "teleprompter_images_loading");
    researchApiGet("research/status", undefined, true).then(function(state) {
      if (!view.current()) return;
      if (!state.ok) throw new Error("Research status unavailable");
      if (!state.initialized) { view.state = "empty"; dossierNote("empty", "research_not_initialized"); return; }
      var binding = "project_token=" + encodeURIComponent(selected.project_token);
      return Promise.all([researchApiGet("research/manuscript-review?" + binding), researchApiGet("research/dossiers?" + binding)]).then(function(results) {
        if (!view.current()) return;
        var review = results[0], index = results[1], projection = review.passage_context;
        if (!review.ok || !index.ok || review.schema_version !== "research-manuscript-review-local/1" ||
            review.source_state !== "available" || review.current_source_sha256 !== selected.source_sha256 ||
            !review.project_id || review.project_id !== index.project_id || !Array.isArray(index.dossiers) ||
            !projection || projection.schema_version !== "research-passage-context-local/1" || !Array.isArray(projection.paragraphs)) {
          throw new Error("Research context unavailable");
        }
        view.project = review.project_id; view.state = "ready";
        researchDossiers = index.dossiers; passageContexts = projection.paragraphs;
        var active = scrollPane.querySelector(".teleprompter-paragraph.is-active") || scrollPane.querySelector(".teleprompter-paragraph");
        if (active) updateDossierSidebar(active, true);
      });
    }).catch(function() { if (view.current()) { view.state = "failed"; dossierFailure(); } });
  }

  function createModal() {
    if (modal) return;
    modal = document.createElement("div");
    modal.id = "teleprompter-modal";
    modal.hidden = true;
    modal.setAttribute("role", "dialog");
    modal.setAttribute("aria-modal", "true");
    modal.setAttribute("aria-label", label("reading_teleprompter"));

    recordStatusAnnouncer = document.createElement("div");
    recordStatusAnnouncer.id = "teleprompter-record-status";
    recordStatusAnnouncer.className = "teleprompter-plan-status";
    recordStatusAnnouncer.hidden = true;
    recordStatusAnnouncer.setAttribute("role", "status");
    recordStatusAnnouncer.setAttribute("aria-live", "polite");
    modal.appendChild(recordStatusAnnouncer);

    // Toolbar
    var toolbar = document.createElement("header");
    toolbar.className = "teleprompter-toolbar";

    // 1. Left Group: Brand & Chapter Selector
    var leftGroup = document.createElement("div");
    leftGroup.className = "teleprompter-toolbar-group teleprompter-left-group";

    var brand = document.createElement("div");
    brand.className = "teleprompter-brand";
    var brandIcon = window.LixityIcons && typeof window.LixityIcons.svg === "function" ?
      window.LixityIcons.svg("teleprompter", { size: 15 }) : "";
    brand.innerHTML = brandIcon;
    var brandTitle = document.createElement("strong");
    brandTitle.className = "teleprompter-title-text";
    brandTitle.textContent = label("reading_teleprompter");
    brand.append(" ", brandTitle);
    leftGroup.appendChild(brand);

    chapterSelect = document.createElement("select");
    chapterSelect.className = "teleprompter-select";
    chapterSelect.setAttribute("aria-label", label("reading_chapter"));
    chapterSelect.addEventListener("change", function() {
      var targetId = chapterSelect.value;
      if (!targetId) return;
      var targetEl = scrollPane.querySelector('[data-chapter-id="' + targetId + '"]');
      if (targetEl) targetEl.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    leftGroup.appendChild(chapterSelect);

    toolbar.appendChild(leftGroup);

    // 2. Center Group: Play/Pause, Speed Slider, Font Sizing
    var centerGroup = document.createElement("div");
    centerGroup.className = "teleprompter-toolbar-group teleprompter-center-group";

    playBtn = document.createElement("button");
    playBtn.type = "button";
    playBtn.className = "teleprompter-btn teleprompter-btn-primary";
    var playSpan = document.createElement("span");
    playSpan.className = "teleprompter-btn-label";
    playSpan.textContent = label("teleprompter_play");
    playBtn.append("▶ ", playSpan);
    playBtn.setAttribute("aria-label", label("teleprompter_play"));
    playBtn.title = label("teleprompter_play");
    playBtn.addEventListener("click", togglePlay);
    centerGroup.appendChild(playBtn);

    var speedWrapper = document.createElement("div");
    speedWrapper.className = "teleprompter-speed-control";

    speedSlider = document.createElement("input");
    speedSlider.type = "range";
    speedSlider.min = "60";
    speedSlider.max = "240";
    speedSlider.value = String(wordsPerMinute);
    speedSlider.step = "5";
    speedSlider.setAttribute("aria-label", label("teleprompter_speed"));
    speedSlider.title = label("teleprompter_speed");
    speedSlider.addEventListener("input", function() {
      wordsPerMinute = parseInt(speedSlider.value, 10);
      speedVal.textContent = wordsPerMinute + " WPM";
    });
    speedWrapper.appendChild(speedSlider);

    speedVal = document.createElement("span");
    speedVal.className = "teleprompter-speed-val";
    speedVal.textContent = wordsPerMinute + " WPM";
    speedWrapper.appendChild(speedVal);

    centerGroup.appendChild(speedWrapper);

    var fontGroup = document.createElement("div");
    fontGroup.className = "teleprompter-btn-group";

    var sizeMinus = document.createElement("button");
    sizeMinus.type = "button";
    sizeMinus.className = "teleprompter-btn";
    sizeMinus.textContent = "A−";
    sizeMinus.title = label("reading_smaller");
    sizeMinus.setAttribute("aria-label", label("reading_smaller"));
    sizeMinus.addEventListener("click", function() {
      fontSize = Math.max(20, fontSize - 4);
      modal.style.setProperty("--teleprompter-font-size", fontSize + "px");
    });
    fontGroup.appendChild(sizeMinus);

    var sizePlus = document.createElement("button");
    sizePlus.type = "button";
    sizePlus.className = "teleprompter-btn";
    sizePlus.textContent = "A+";
    sizePlus.title = label("reading_larger");
    sizePlus.setAttribute("aria-label", label("reading_larger"));
    sizePlus.addEventListener("click", function() {
      fontSize = Math.min(56, fontSize + 4);
      modal.style.setProperty("--teleprompter-font-size", fontSize + "px");
    });
    fontGroup.appendChild(sizePlus);

    centerGroup.appendChild(fontGroup);
    toolbar.appendChild(centerGroup);

    // 3. Right Group: Dossiers Toggle, Audio Recording, Close Modal
    var rightGroup = document.createElement("div");
    rightGroup.className = "teleprompter-toolbar-group teleprompter-right-group";

    sidebarToggleBtn = document.createElement("button");
    sidebarToggleBtn.type = "button";
    sidebarToggleBtn.className = "teleprompter-btn teleprompter-dossier-toggle";
    var dossierIcon = window.LixityIcons && typeof window.LixityIcons.svg === "function" ?
      window.LixityIcons.svg("panel-right", { size: 15 }) : "";
    sidebarToggleBtn.innerHTML = dossierIcon;
    var sidebarBtnSpan = document.createElement("span");
    sidebarBtnSpan.className = "teleprompter-btn-label";
    sidebarBtnSpan.textContent = label("teleprompter_dossiers");
    sidebarToggleBtn.append(" ", sidebarBtnSpan);
    sidebarToggleBtn.title = label("teleprompter_dossier_context") + " (D)";
    sidebarToggleBtn.setAttribute("aria-label", label("teleprompter_dossier_context"));
    sidebarToggleBtn.setAttribute("aria-pressed", "false");
    sidebarToggleBtn.addEventListener("click", function() {
      if (sidebar) {
        var open = sidebar.classList.toggle("is-open");
        sidebarToggleBtn.classList.toggle("is-active", open);
        sidebarToggleBtn.setAttribute("aria-pressed", String(open));
      }
    });
    rightGroup.appendChild(sidebarToggleBtn);

    recordBtn = document.createElement("button");
    recordBtn.type = "button";
    recordBtn.className = "teleprompter-btn teleprompter-btn-record";
    var micIcon = window.LixityIcons && typeof window.LixityIcons.svg === "function" ?
      window.LixityIcons.svg("mic", { size: 15 }) : "";
    recordBtn.innerHTML = micIcon;
    var recordBtnSpan = document.createElement("span");
    recordBtnSpan.className = "teleprompter-btn-label";
    recordBtnSpan.textContent = label("teleprompter_record_take");
    recordBtn.append(" ", recordBtnSpan);
    recordBtn.title = label("teleprompter_record_hint") + " (R)";
    recordBtn.setAttribute("aria-label", label("teleprompter_record_hint"));
    recordBtn.addEventListener("click", toggleRecording);
    rightGroup.appendChild(recordBtn);
    takeImportBtn = document.createElement("button"); takeImportBtn.type = "button";
    var folderIcon = window.LixityIcons && typeof window.LixityIcons.svg === "function" ?
      window.LixityIcons.svg("folder-open", { size: 15 }) : "📂";
    takeImportBtn.className = "teleprompter-btn"; takeImportBtn.innerHTML = folderIcon;
    takeImportBtn.setAttribute("aria-label", label("teleprompter_take_import"));
    takeImportBtn.title = label("teleprompter_take_import");
    takeImportBtn.addEventListener("click", function() { takeFiles.click(); });
    rightGroup.appendChild(takeImportBtn);
    takeFiles = document.createElement("input"); takeFiles.type = "file"; takeFiles.multiple = true;
    takeFiles.accept = ".wav,.json"; takeFiles.id = "teleprompter-take-files"; takeFiles.hidden = true;
    takeFiles.addEventListener("change", importTakeFiles); rightGroup.appendChild(takeFiles);

    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "teleprompter-btn teleprompter-btn-close";
    closeBtn.innerHTML = '<span aria-hidden="true">✕</span>';
    closeBtn.title = label("modal_close") + " (Esc)";
    closeBtn.setAttribute("aria-label", label("modal_close") + " (Esc)");
    closeBtn.addEventListener("click", closeTeleprompter);
    rightGroup.appendChild(closeBtn);

    toolbar.appendChild(rightGroup);
    modal.appendChild(toolbar);
    modal.appendChild(recordStatusAnnouncer);

    planStatus = document.createElement("p"); planStatus.id = "teleprompter-plan-status";
    planStatus.className = "teleprompter-plan-status"; planStatus.setAttribute("role", "status");
    planStatus.setAttribute("aria-live", "polite"); planStatus.hidden = true; modal.appendChild(planStatus);

    // Body
    var body = document.createElement("div");
    body.className = "teleprompter-body";

    // Runway Container
    var runwayContainer = document.createElement("div");
    runwayContainer.className = "teleprompter-runway-container";

    scrollPane = document.createElement("main");
    scrollPane.className = "teleprompter-scroll-pane";
    scrollPane.addEventListener("scroll", handleScrollSync);
    runwayContainer.appendChild(scrollPane);

    body.appendChild(runwayContainer);

    // Sidebar: Historical Dossiers & Context (slide-over drawer)
    sidebar = document.createElement("aside");
    sidebar.className = "teleprompter-sidebar";

    var sidebarHeader = document.createElement("div");
    sidebarHeader.className = "teleprompter-sidebar-header";
    var sidebarTitle = document.createElement("span");
    sidebarTitle.textContent = "🏛 " + label("teleprompter_dossier_context");
    sidebarHeader.appendChild(sidebarTitle);

    var sidebarClose = document.createElement("button");
    sidebarClose.type = "button";
    sidebarClose.className = "teleprompter-btn teleprompter-btn-close";
    sidebarClose.innerHTML = '<span aria-hidden="true">✕</span>';
    sidebarClose.title = label("modal_close");
    sidebarClose.setAttribute("aria-label", label("modal_close"));
    sidebarClose.addEventListener("click", function() {
      sidebar.classList.remove("is-open");
      if (sidebarToggleBtn) {
        sidebarToggleBtn.classList.remove("is-active");
        sidebarToggleBtn.setAttribute("aria-pressed", "false");
      }
    });
    sidebarHeader.appendChild(sidebarClose);
    sidebar.appendChild(sidebarHeader);

    sidebarContent = document.createElement("div");
    sidebarContent.className = "teleprompter-sidebar-content";
    sidebarContent.setAttribute("aria-live", "polite");
    sidebarScroll = document.createElement("div"); sidebarScroll.className = "teleprompter-sidebar-scroll";
    sidebarScroll.appendChild(sidebarContent); sidebar.appendChild(sidebarScroll);

    body.appendChild(sidebar);
    modal.appendChild(body);
    document.body.appendChild(modal);
    var researchObserver = new MutationObserver(function() {
      if (!modal.hidden && researchView && !researchView.current()) {
        ++dossierSequence; researchView.invalidated = true; researchView.state = "failed";
        passageContexts = null; researchDossiers = null;
        dossierFailure();
      }
    });
    researchObserver.observe(document.body, {subtree:true, attributes:true,
      attributeFilter:["data-project-token", "data-research-token", "data-manuscript-source-sha256"]});

    modal.style.setProperty("--teleprompter-font-size", fontSize + "px");

    // Keyboard controls
    document.addEventListener("keydown", function(e) {
      if (!modal || modal.hidden) return;
      if (e.code !== "Escape" && e.target.closest("input, textarea, select, [contenteditable=true]")) return;
      if (e.code === "Space" && e.target.closest("button, a")) return;
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
        speedVal.textContent = wordsPerMinute + " WPM";
      } else if (e.code === "ArrowDown") {
        e.preventDefault();
        wordsPerMinute = Math.max(60, wordsPerMinute - 10);
        speedSlider.value = String(wordsPerMinute);
        speedVal.textContent = wordsPerMinute + " WPM";
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
        if (sidebar) {
          var open = sidebar.classList.toggle("is-open");
          if (sidebarToggleBtn) {
            sidebarToggleBtn.classList.toggle("is-active", open);
            sidebarToggleBtn.setAttribute("aria-pressed", String(open));
          }
        }
      } else if (e.code === "KeyR" && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        toggleRecording();
      }
    });
  }

  function segmentsForParagraph(startLine, endLine, sha) {
    if (!speechData || !sha) return [];
    return speechData.segments.filter(function(row) {
      var anchor = row.anchor;
      return anchor && anchor.paragraph_sha256 === sha && anchor.start_line === startLine && anchor.end_line === endLine;
    });
  }

  function buildRunwayContent() {
    if (!scrollPane) return;
    var selectedSha = activeParagraphSha, selectedChapter = chapterSelect.value, position = scrollPane.scrollTop;
    scrollPane.replaceChildren();
    chapterSelect.replaceChildren();

    var chaptersContainer = document.getElementById("chapters");
    if (!chaptersContainer) return;

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

        var textNode = document.createElement("div");
        textNode.className = "teleprompter-text";
        var segments = segmentsForParagraph(startLine, endLine, sha);
        spokenParagraphs.set(pNode, segments.length ? segments.map(function(row) { return row.spoken_text || row.text || ""; }).join("") : rawText);
        if (segments.length) segments.forEach(function(row) {
          var group = document.createElement("span"); group.className = "teleprompter-segment";
          var cues = window.LixitySpeechPresentation.controls(row, label);
          if (cues.length) {
            var cue = document.createElement("span"); cue.className = "teleprompter-cue";
            cue.textContent = cues.join(" · "); group.appendChild(cue);
          }
          var spoken = document.createElement("span"); spoken.className = "teleprompter-spoken";
          window.LixitySpeechPresentation.appendText(spoken, row, "teleprompter-phonetic");
          group.appendChild(spoken); textNode.appendChild(group);
        });
        else textNode.textContent = rawText;
        pNode.appendChild(textNode);

        scrollPane.appendChild(pNode);
      });
    });
    scrollPane.scrollTop = position;
    if (selectedChapter) chapterSelect.value = selectedChapter;
    if (selectedSha) {
      var selected = Array.from(scrollPane.querySelectorAll(".teleprompter-paragraph")).find(function(paragraph) {
        return paragraph.dataset.sha === selectedSha;
      });
      if (selected) selected.classList.add("is-active");
      else activeParagraphSha = null;
    }
  }

  function dossierNote(state, key) {
    if (!sidebarContent) return;
    sidebarContent.replaceChildren(); sidebarContent.dataset.state = state;
    var note = document.createElement("p"); note.className = "teleprompter-sidebar-empty";
    note.textContent = label(key); sidebarContent.appendChild(note);
  }
  function dossierFailure() {
    dossierNote("failed", "teleprompter_images_failed");
  }
  function updateDossierSidebar(paragraphNode, force) {
    if (!sidebarContent || !paragraphNode) return;
    var sha = paragraphNode.getAttribute("data-sha");
    var key = JSON.stringify([sha, paragraphNode.dataset.start, paragraphNode.dataset.end]);
    if (key === activeDossierKey && !force) return;
    activeDossierKey = key;
    activeParagraphSha = sha;

    // Remove old active highlight
    var prevActive = scrollPane.querySelector(".teleprompter-paragraph.is-active");
    if (prevActive) prevActive.classList.remove("is-active");
    paragraphNode.classList.add("is-active");

    var view = researchView, request = ++dossierSequence;
    if (!view) { dossierNote("empty", "teleprompter_no_images"); return; }
    if (!view.current() || view.state === "failed") { dossierFailure(); return; }
    if (view.state === "loading") { dossierNote("loading", "teleprompter_images_loading"); return; }
    if (view.state === "empty") { dossierNote("empty", "research_not_initialized"); return; }
    var references = [], suggested = false;
    try {
      // The backend owns exact-anchor matching and historical claim/dossier pins.
      var matches = passageContexts.filter(function(row) { return row.paragraph_sha256 === sha &&
        row.start_line === Number(paragraphNode.dataset.start) && row.end_line === Number(paragraphNode.dataset.end); });
      if (matches.length > 1 || (matches.length && matches[0].state !== "ready")) throw new Error("Passage context unavailable");
      var seen = new Set();
      if (matches.length) matches[0].groups.forEach(function(group) {
        if (!group.dossier) return;
        group.claims.forEach(function(claim) { claim.versions.forEach(function(version) {
          var records = [group.dossier.current].concat(group.dossier.pins);
          var pin = records.find(function(record) { return record.revision === version.dossier_revision; });
          if (!pin || !pin.id || pin.id !== group.dossier.current.id || !Number.isInteger(pin.revision) || pin.revision < 1) throw new Error("Dossier pin unavailable");
          var identity = pin.id + ":" + pin.revision;
          if (!seen.has(identity)) { seen.add(identity); references.push(pin); }
        }); });
      });
      if (references.length > 5) throw new Error("Passage context exceeds its bounded projection");
      if (!references.length && !matches.length) {
        var text = (spokenParagraphs.get(paragraphNode) || "").toLowerCase();
        references = researchDossiers.filter(function(dossier) {
          return (dossier.title && text.includes(dossier.title.toLowerCase())) ||
            (dossier.tags || []).some(function(tag) { return tag.length > 3 && text.includes(tag.toLowerCase()); });
        }).slice(0, 2);
        suggested = references.length > 0;
      }
    } catch (_) { dossierFailure(); return; }
    if (!references.length) { dossierNote("empty", "teleprompter_no_images"); return; }
    dossierNote("loading", "teleprompter_images_loading");
    Promise.all(references.map(function(pin) {
      var identity = pin.id + ":" + pin.revision;
      if (!dossierReads.has(identity)) {
        // Bound retained detail payloads while scrolling through a long manuscript.
        if (dossierReads.size >= 32) dossierReads.delete(dossierReads.keys().next().value);
        var pending = researchApiGet("research/dossiers?id=" + encodeURIComponent(pin.id) + "&revision=" + encodeURIComponent(pin.revision) +
          "&project_token=" + encodeURIComponent(view.token)).then(function(detail) {
          if (!detail.ok || detail.id !== pin.id || detail.revision !== pin.revision || detail.project_id !== view.project ||
              detail.availability === "withdrawn" || !Array.isArray(detail.images)) throw new Error("Dossier images unavailable");
          return detail;
        });
        dossierReads.set(identity, pending);
      }
      return dossierReads.get(identity);
    })).then(function(details) {
      if (request !== dossierSequence || !view.current()) return;
      sidebarContent.replaceChildren(); sidebarContent.dataset.state = suggested ? "suggested" : "ready";
      if (suggested) {
        var note = document.createElement("p"); note.className = "ctl-note";
        note.textContent = label("teleprompter_images_suggested"); sidebarContent.appendChild(note);
      }
      var shown = new Set();
      details.forEach(function(detail) { detail.images.forEach(function(image) {
        var identity = image.source_id + ":" + image.source_version_id;
        if (!shown.has(identity) && (!suggested || shown.size < 2) && renderDossierCard(detail, image)) shown.add(identity);
      }); });
      if (!shown.size) dossierNote("empty", "teleprompter_no_images");
    }).catch(function() { if (request === dossierSequence && view.current()) dossierFailure(); });
  }

  function renderDossierCard(detail, image) {
    var alt = String(image.alt || image.title || detail.title || "").replace(/[\r\n]/g, " ").replace(/[\\[\]]/g, "\\$&");
    var prepared = window.LixityDossierImages.prepareMarkdown("![" + alt + "](lixity:image/" + image.source_id + "/" + image.source_version_id + ")",
      {project_id:detail.project_id, images:[image]});
    if (!prepared.html.length) return false;
    var card = document.createElement("div");
    card.className = "teleprompter-dossier-card";
    var h = document.createElement("div");
    h.className = "teleprompter-dossier-title";
    h.textContent = detail.title; card.appendChild(h);
    var content = document.createElement("div");
    content.innerHTML = window.LixityDossierImages.restoreMarkdown(prepared.text, prepared);
    card.appendChild(content);
    sidebarContent.appendChild(card);
    return true;
  }

  function handleScrollSync() {
    if (!scrollPane) return;
    var paragraphs = Array.from(scrollPane.querySelectorAll(".teleprompter-paragraph"));
    if (!paragraphs.length) return;

    var closest = null;
    if (scrollPane.scrollTop <= 20) {
      closest = paragraphs[0];
    } else if (scrollPane.scrollTop + scrollPane.clientHeight >= scrollPane.scrollHeight - 1) {
      // The last paragraph can be visible below the reading line at the end of the runway.
      closest = paragraphs[paragraphs.length - 1];
    } else {
      var paneRect = scrollPane.getBoundingClientRect();
      var targetY = paneRect.top + scrollPane.clientHeight * 0.28;
      var minDiff = Infinity;
      paragraphs.forEach(function(p) {
        var rect = p.getBoundingClientRect();
        // Distance to the paragraph interval, not only its beginning.
        var diff = targetY < rect.top ? rect.top - targetY : Math.max(0, targetY - rect.bottom);
        if (diff < minDiff) {
          minDiff = diff;
          closest = p;
        }
      });
    }

    if (closest) {
      chapterSelect.value = closest.dataset.chapterId;
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
      playBtn.classList.add("is-active");
      var pauseSpan = document.createElement("span");
      pauseSpan.className = "teleprompter-btn-label";
      pauseSpan.textContent = label("teleprompter_pause");
      playBtn.replaceChildren("⏸ ", pauseSpan);
      playBtn.setAttribute("aria-label", label("teleprompter_pause"));
      playBtn.title = label("teleprompter_pause");
      lastTimestamp = 0;
      animFrameId = requestAnimationFrame(scrollLoop);
    } else {
      playBtn.classList.remove("is-active");
      var resumeSpan = document.createElement("span");
      resumeSpan.className = "teleprompter-btn-label";
      resumeSpan.textContent = label("teleprompter_play");
      playBtn.replaceChildren("▶ ", resumeSpan);
      playBtn.setAttribute("aria-label", label("teleprompter_play"));
      playBtn.title = label("teleprompter_play");
      if (animFrameId) cancelAnimationFrame(animFrameId);
    }
  }

  var pcmAudioContext = null;
  var pcmMediaStream = null;
  var pcmProcessorNode = null;
  var pcmSourceNode = null;
  var pcmRecordedChunks = [];
  var pcmTotalSamples = 0;
  var pcmCaptureSequence = 0;
  var pcmCaptureContext = null;

  function recordingState(state, key) {
    recordStatusAnnouncer.dataset.state = state;
    recordStatusAnnouncer.textContent = label(key);
    recordStatusAnnouncer.hidden = false;
  }
  function resetCapture() {
    ++pcmCaptureSequence; isRecording = false;
    if (recordTimerId) clearInterval(recordTimerId); recordTimerId = null;
    if (pcmProcessorNode) { pcmProcessorNode.onaudioprocess = null; pcmProcessorNode.disconnect(); pcmProcessorNode = null; }
    if (pcmSourceNode) { pcmSourceNode.disconnect(); pcmSourceNode = null; }
    if (pcmMediaStream) { pcmMediaStream.getTracks().forEach(function(track) { track.stop(); }); pcmMediaStream = null; }
    if (pcmAudioContext) { pcmAudioContext.close().catch(function() {}); pcmAudioContext = null; }
    recordBtn.classList.remove("is-active"); recordBtn.removeAttribute("aria-busy");
    var micIcon = window.LixityIcons && typeof window.LixityIcons.svg === "function" ?
      window.LixityIcons.svg("mic", { size: 15 }) : "";
    recordBtn.innerHTML = micIcon;
    var recLabel = document.createElement("span");
    recLabel.className = "teleprompter-btn-label";
    recLabel.textContent = label("teleprompter_record_take");
    recordBtn.append(" ", recLabel);
    recordBtn.setAttribute("aria-label", label("teleprompter_record_hint"));
    takeImportBtn.disabled = false;
  }
  function captureFailed(error) {
    resetCapture(); pcmRecordedChunks = []; pcmTotalSamples = 0;
    if (error && error.name === "ContextChangedError") {
      recordingState("failed", "teleprompter_take_context"); return;
    }
    var denied = error && ["NotAllowedError", "PermissionDeniedError", "SecurityError"].includes(error.name);
    recordingState("failed", denied ? "teleprompter_take_denied" : "teleprompter_take_failed");
  }
  async function startAudioCapture() {
    pcmRecordedChunks = []; pcmTotalSamples = 0; ++takeSequence; pcmCaptureContext = selectedContext();
    if (takeCard) takeCard.querySelectorAll("audio").forEach(function(audio) { audio.pause(); });
    var AudioCtxClass = window.AudioContext || window.webkitAudioContext;
    isRecording = true; takeImportBtn.disabled = true;
    var request = ++pcmCaptureSequence;
    var captureIdentity = JSON.stringify(pcmCaptureContext);
    function sameContext() {
      if (captureIdentity !== JSON.stringify(selectedContext())) {
        var error = new Error("Recording context changed"); error.name = "ContextChangedError"; throw error;
      }
    }
    recordingState("pending", "teleprompter_take_pending");
    recordBtn.setAttribute("aria-busy", "true");
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !AudioCtxClass) throw new Error("Microphone unavailable");
      var stream = await navigator.mediaDevices.getUserMedia({audio:{channelCount:1, echoCancellation:false, noiseSuppression:false, autoGainControl:false}});
      if (request !== pcmCaptureSequence || !isRecording || modal.hidden) { stream.getTracks().forEach(function(track) { track.stop(); }); return; }
      pcmMediaStream = stream; sameContext(); var context = new AudioCtxClass({sampleRate:24000}); pcmAudioContext = context;
      await context.resume();
      if (request !== pcmCaptureSequence || !isRecording || modal.hidden) return;
      sameContext();
      if (context.state !== "running") throw new Error("Audio capture is suspended");
      pcmSourceNode = context.createMediaStreamSource(stream); pcmProcessorNode = context.createScriptProcessor(4096, 1, 1);
      pcmProcessorNode.onaudioprocess = function(event) {
        if (request !== pcmCaptureSequence || !isRecording) return;
        var input = event.inputBuffer.getChannelData(0);
        var remaining = Math.floor((window.LixityAudioTake.maximumBytes - 44) / 2) - pcmTotalSamples;
        var copy = new Float32Array(input.subarray(0, remaining));
        if (copy.length) { pcmRecordedChunks.push(copy); pcmTotalSamples += copy.length; }
        if (copy.length < input.length) {
          toggleRecording(); recordingState("ready", "teleprompter_take_limit");
        }
      };
      pcmSourceNode.connect(pcmProcessorNode); pcmProcessorNode.connect(context.destination);
      recordBtn.removeAttribute("aria-busy"); recordBtn.classList.add("is-active");
      recordBtn.setAttribute("aria-label", label("teleprompter_recording"));
      recordingState("running", "teleprompter_take_running");
      recordStartTime = Date.now();
      function tick() { var elapsed = Math.floor((Date.now() - recordStartTime) / 1000);
        recordBtn.textContent = "⏹ " + String(Math.floor(elapsed / 60)).padStart(2, "0") + ":" + String(elapsed % 60).padStart(2, "0"); }
      tick(); recordTimerId = setInterval(tick, 1000);
      if (!isPlaying) togglePlay();
    } catch (error) { if (request === pcmCaptureSequence) captureFailed(error); }
  }
  function stopAudioCapture() {
    var sampleRate = pcmAudioContext && pcmAudioContext.sampleRate, chunks = pcmRecordedChunks, count = pcmTotalSamples;
    resetCapture(); pcmRecordedChunks = []; pcmTotalSamples = 0;
    recordingState("idle", "teleprompter_take_stopped");
    if (count) {
      try {
        var blob = new Blob([window.LixityAudioTake.encodeWav(chunks, count, sampleRate)], {type:"audio/wav"});
        var stamp = new Date().toISOString().replace(/[:.]/g, "-");
        acceptTake(window.LixityAudioTake.create(blob, {filename:"teleprompter-take-" + stamp + ".wav"}), pcmCaptureContext, true);
      } catch (error) { captureFailed(error); }
    }
  }
  async function acceptTake(pending, context, captured) {
    var sequence = ++takeSequence, view = contextSequence; recordBtn.disabled = true; takeImportBtn.disabled = true;
    try {
      var value = await pending;
      if (sequence !== takeSequence) return;
      if (!captured && (modal.hidden || view !== contextSequence || JSON.stringify(context) !== JSON.stringify(selectedContext()))) {
        if (!modal.hidden) recordingState("failed", "teleprompter_take_context");
        return;
      }
      renderTake(value, context);
      recordingState("ready", "teleprompter_take_ready");
    } catch (_) {
      if (sequence === takeSequence) recordingState("failed", "teleprompter_take_import_failed");
    } finally { if (sequence === takeSequence) { recordBtn.disabled = false; takeImportBtn.disabled = false; } }
  }
  function importTakeFiles() {
    var files = Array.from(takeFiles.files || []); takeFiles.value = "";
    if (isRecording) return;
    var wav = files.filter(function(file) { return /\.wav$/i.test(file.name); });
    var json = files.filter(function(file) { return /\.json$/i.test(file.name); });
    if (files.length !== 2 || wav.length !== 1 || json.length !== 1) {
      recordingState("failed", "teleprompter_take_import_failed"); return;
    }
    acceptTake(window.LixityAudioTake.importFiles(wav[0], json[0]), selectedContext());
  }
  function renderTake(value, context) {
    if (takePlayer) { takePlayer.destroy(); takePlayer = null; }
    if (takeCard) {
      var oldAudio = takeCard.querySelector("audio");
      if (oldAudio) { oldAudio.pause(); oldAudio.removeAttribute("src"); oldAudio.load(); }
      takeCard.remove();
    }
    if (lastRecordedBlobUrl) URL.revokeObjectURL(lastRecordedBlobUrl);
    currentTake = value; takeContext = context; lastRecordedBlobUrl = URL.createObjectURL(value.blob);
    takeCard = document.createElement("section"); takeCard.className = "teleprompter-dossier-card teleprompter-take-card";
    var title = document.createElement("strong"); title.textContent = label("teleprompter_take_ready"); takeCard.appendChild(title);
    var audio = document.createElement("audio"); audio.controls = true; audio.src = lastRecordedBlobUrl; takeCard.appendChild(audio);
    if (typeof window.createSpeechPlayer === "function") takePlayer = window.createSpeechPlayer(audio, {
      label:function(key) { return label("speech_" + key); },
      onError:function() { recordingState("failed", "teleprompter_take_play_failed"); }
    });
    var description = document.createElement("p"); description.textContent = label("teleprompter_take_help"); takeCard.appendChild(description);
    var field = document.createElement("label"); field.className = "setting-field"; field.textContent = label("teleprompter_take_transcript");
    var text = document.createElement("textarea"); text.className = "ctl"; text.rows = 3; text.maxLength = 100000; text.value = currentTake.transcript; field.appendChild(text); takeCard.appendChild(field);
    var confirmation = document.createElement("label"); confirmation.className = "teleprompter-take-confirm";
    var checked = document.createElement("input"); checked.type = "checkbox"; checked.checked = currentTake.transcript_status === "confirmed";
    confirmation.appendChild(checked); confirmation.appendChild(document.createTextNode(label("teleprompter_take_confirm"))); takeCard.appendChild(confirmation);
    function update(edited) {
      var previousInvalid = text.getAttribute("aria-invalid") === "true";
      if (edited) checked.checked = false;
      if (!text.value.trim()) checked.checked = false;
      var invalid = false;
      try { currentTake = window.LixityAudioTake.withTranscript(currentTake, text.value, checked.checked ? "confirmed" : text.value.trim() ? "draft" : "missing"); }
      catch (_) { invalid = true; checked.checked = false;
        recordingState("failed", "teleprompter_take_export_failed"); }
      takeCard.querySelectorAll('[data-take-download="json"], [data-take-studio]').forEach(function(button) { button.disabled = invalid; });
      text.setAttribute("aria-invalid", String(invalid));
      if (!invalid && previousInvalid) recordingState("ready", "teleprompter_take_ready");
    }
    text.addEventListener("input", function() { update(true); }); checked.addEventListener("change", function() { update(false); });
    var actions = document.createElement("div"); actions.className = "row"; takeCard.appendChild(actions);
    ["wav", "json"].forEach(function(kind) {
      var button = document.createElement("button"); button.type = "button"; button.className = "teleprompter-btn";
      button.dataset.takeDownload = kind; button.textContent = kind.toUpperCase();
      button.addEventListener("click", function() { window.LixityAudioTake.download(currentTake, kind).catch(function() {
        recordingState("failed", "teleprompter_take_export_failed");
      }); }); actions.appendChild(button);
    });
    var studio = document.createElement("button"); studio.type = "button"; studio.className = "teleprompter-voice-studio-link"; studio.dataset.takeStudio = "";
    studio.textContent = label("teleprompter_open_studio");
    studio.addEventListener("click", function() {
      if (document.body.dataset.speechCapable !== "true") return;
      if (JSON.stringify(takeContext) !== JSON.stringify(selectedContext())) {
        recordingState("failed", "teleprompter_take_context"); return;
      }
      var detail = {mode:"reference", take:currentTake, context:takeContext}; closeTeleprompter();
      document.dispatchEvent(new CustomEvent("lixity:open-speech-studio", {detail:detail}));
    });
    if (document.body.dataset.speechCapable === "true") takeCard.appendChild(studio);
    sidebarScroll.prepend(takeCard); sidebar.classList.add("is-open"); sidebarToggleBtn.classList.add("is-active"); sidebarToggleBtn.setAttribute("aria-pressed", "true");
  }
  function toggleRecording() {
    if (recordBtn.disabled) return;
    if (isRecording) { stopAudioCapture(); if (isPlaying) togglePlay(); }
    else startAudioCapture();
  }

  function openTeleprompter(startParagraphSha) {
    previousActiveElement = document.activeElement;
    createModal();
    planStatus.hidden = true; planStatus.textContent = ""; delete planStatus.dataset.state;
    speechData = null; researchDossiers = null; passageContexts = null; researchView = null; activeParagraphSha = null;
    activeDossierKey = null; ++dossierSequence; dossierReads = new Map();
    dossierNote("empty", "teleprompter_no_images");
    if (sidebar) sidebar.classList.remove("is-open");
    if (sidebarToggleBtn) {
      sidebarToggleBtn.classList.remove("is-active");
      sidebarToggleBtn.setAttribute("aria-pressed", "false");
    }
    buildRunwayContent();
    modal.hidden = false;
    loadContextData();
    document.body.classList.add("teleprompter-open");

    // Scroll to initial paragraph or synchronize top paragraph
    if (startParagraphSha) {
      setTimeout(function() {
        var el = scrollPane.querySelector('[data-sha="' + startParagraphSha + '"]');
        if (el) {
          el.scrollIntoView({ behavior: "auto", block: "center" });
          updateDossierSidebar(el);
        }
      }, 50);
    } else {
      setTimeout(function() {
        handleScrollSync();
      }, 50);
    }

    if (playBtn) playBtn.focus();
  }

  function closeTeleprompter() {
    ++contextSequence;
    if (isPlaying) togglePlay();
    if (isRecording) toggleRecording();
    if (modal) modal.querySelectorAll("audio").forEach(function(audio) { audio.pause(); });
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
