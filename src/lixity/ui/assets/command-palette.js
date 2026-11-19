// Lixity Command Palette (Obsidian-style Ctrl/Cmd+P / Ctrl/Cmd+K)
// Fast keyboard-first access to analyses, audio studio, research search and exports.
(function () {
  "use strict";

  var paletteDialog = null;
  var searchInput = null;
  var resultsList = null;
  var selectedIndex = 0;
  var activeCommands = [];
  var lastFocusedElement = null;

  var STANDALONE_DE = {
    cmd_cat_views: "Ansicht",
    cmd_cat_analysis: "Analyse",
    cmd_cat_research: "Recherche",
    cmd_cat_audio: "Audio & Sprache",
    cmd_cat_export: "Export",
    cmd_metric_dialogue_title: "Dialoge & Redeanteile hervorheben",
    cmd_layer_dialogue_hint: "Dialoge, Sprecherwechsel & Redeanteile",
    cmd_layer_asl_hint: "Satzlänge & Lesefluss",
    cmd_layer_tense_hint: "Grammatisches Tempus & Wechsel",
    cmd_research_search_title: "Recherche-Suchmaske öffnen",
    cmd_research_new_dossier_title: "Neues Forschungs-Dossier anlegen"
  };

  function cmdText(key, enFallback) {
    if (typeof window.uiLabel === "function") {
      var translated = window.uiLabel(key);
      if (translated && translated !== key) return translated;
    }
    var lang = (document.documentElement.lang || "en").split("-")[0].toLowerCase();
    return (lang === "de" && STANDALONE_DE[key]) || enFallback || key;
  }

  function icon(name) {
    if (window.LixityIcons && typeof window.LixityIcons.create === "function") {
      return window.LixityIcons.create(name, "command-icon");
    }
    return "";
  }

  function activateAnalysisLayer(layerValue, workbench) {
    if (typeof switchActiveView === "function") switchActiveView("analysis");
    if (workbench) workbench.dispatch({ type: "surface", value: "document", analysisVisible: true });
    if (typeof selectAnalysisMetric === "function") {
      selectAnalysisMetric(layerValue);
    } else {
      var sel = document.getElementById("style-layer");
      if (sel) { sel.value = layerValue; sel.dispatchEvent(new Event("change", { bubbles: true })); }
    }
  }

  function buildAnalysisLayerCommands(workbench) {
    var styleLayer = document.getElementById("style-layer");
    var analysisCat = cmdText("cmd_cat_analysis", "Analysis");
    if (styleLayer && styleLayer.options && styleLayer.options.length > 1) {
      var layerCommands = [];
      Array.prototype.slice.call(styleLayer.options).forEach(function (opt) {
        var val = opt.value || "";
        var label = (opt.textContent || "").trim();
        if (!label) return;
        var parent = opt.parentElement;
        var groupLabel = (parent && parent.tagName === "OPTGROUP" && parent.label) ? parent.label.trim() : "";
        var valHints = {
          dialogue: cmdText("cmd_layer_dialogue_hint", "Dialogue turns & spoken share"),
          asl: cmdText("cmd_layer_asl_hint", "Sentence length & rhythm"),
          tense: cmdText("cmd_layer_tense_hint", "Grammatical tense & shifts")
        };
        var subtitle = valHints[val]
          ? (groupLabel ? (groupLabel + " · " + valHints[val]) : valHints[val])
          : (groupLabel || cmdText("cmd_layer_toggle_sub", "Toggle analysis layer in manuscript"));
        layerCommands.push({
          id: val ? ("layer-" + val) : "layer-off",
          category: groupLabel ? (analysisCat + ": " + groupLabel) : analysisCat,
          title: label,
          subtitle: subtitle,
          icon: val ? "sigma" : "eye",
          action: function () {
            activateAnalysisLayer(val, workbench);
          }
        });
      });
      if (layerCommands.length) return layerCommands;
    }
    return [
      {
        id: "metric-asl",
        category: analysisCat,
        title: cmdText("cmd_metric_asl_title", "Highlight Sentence Length & Rhythm"),
        subtitle: cmdText("cmd_metric_asl_sub", "Average sentence length and rhythm"),
        icon: "sigma",
        action: function () { activateAnalysisLayer("asl", workbench); }
      },
      {
        id: "metric-dialogue",
        category: analysisCat,
        title: cmdText("cmd_metric_dialogue_title", "Highlight Dialogue & Direct Speech"),
        subtitle: cmdText("cmd_metric_dialogue_sub", "Dialogue turns and spoken share"),
        icon: "quote",
        action: function () { activateAnalysisLayer("dialogue", workbench); }
      },
      {
        id: "metric-tense",
        category: analysisCat,
        title: cmdText("cmd_metric_tense_title", "Highlight Grammatical Tense"),
        subtitle: cmdText("cmd_metric_tense_sub", "Dominant tense, switches and mix"),
        icon: "tag",
        action: function () { activateAnalysisLayer("", workbench); }
      }
    ];
  }

  function buildChapterCommands(workbench) {
    var chapterSelect = document.getElementById("reader-chapter");
    if (!chapterSelect || !chapterSelect.options) return [];
    var chapterCommands = [];
    Array.prototype.slice.call(chapterSelect.options).forEach(function (opt) {
      var chId = opt.value;
      if (!chId) return;
      var chTitle = (opt.textContent || "").trim() || chId;
      chapterCommands.push({
        id: "chapter-" + chId,
        category: cmdText("cmd_cat_chapters", "Chapters"),
        title: cmdText("cmd_chapter_jump_prefix", "Jump to Chapter:") + " " + chTitle,
        subtitle: cmdText("cmd_chapter_jump_sub", "Open in manuscript reader"),
        icon: "book-open",
        action: function () {
          if (typeof switchActiveView === "function") switchActiveView("analysis");
          if (workbench) workbench.dispatch({ type: "surface", value: "document" });
          var sel = document.getElementById("reader-chapter");
          if (sel) {
            sel.value = chId;
            sel.dispatchEvent(new Event("change", { bubbles: true }));
          } else {
            var target = document.getElementById(chId);
            if (target && typeof scrollAndFlash === "function") scrollAndFlash(target);
          }
        }
      });
    });
    return chapterCommands;
  }

  function getCommands() {
    var workbench = window.LixityWorkbench;
    var state = workbench && typeof workbench.state === "function" ? workbench.state() : {};
    var catViews = cmdText("cmd_cat_views", "Views");
    var catAnalysis = cmdText("cmd_cat_analysis", "Analysis");
    var catResearch = cmdText("cmd_cat_research", "Research");
    var catAudio = cmdText("cmd_cat_audio", "Audio & Speech");
    var catExport = cmdText("cmd_cat_export", "Export");
    var commands = [
      // View switches
      {
        id: "view-analysis",
        category: catViews,
        title: cmdText("cmd_view_analysis_title", "Switch to Manuscript Analysis"),
        subtitle: cmdText("cmd_view_analysis_sub", "Text, metrics and editing"),
        icon: "file-text",
        action: function () {
          if (typeof switchActiveView === "function") {
            switchActiveView("analysis");
          } else {
            if (workbench) workbench.dispatch({ type: "view", value: "analysis" });
            var btn = document.querySelector('[data-view="analysis"], [data-view-pane="analysis"]');
            if (btn) btn.click();
          }
        }
      },
      {
        id: "view-research",
        category: catViews,
        title: cmdText("cmd_view_research_title", "Switch to Research Workspace"),
        subtitle: cmdText("cmd_view_research_sub", "Dossiers, sources, timeline and maps"),
        icon: "archive",
        action: function () {
          if (typeof switchActiveView === "function") {
            switchActiveView("research");
          } else {
            if (workbench) workbench.dispatch({ type: "view", value: "research" });
            var btn = document.querySelector('[data-view="research"], [data-view-pane="research"]');
            if (btn) btn.click();
          }
        }
      },
      {
        id: "view-project",
        category: catViews,
        title: cmdText("cmd_view_project_title", "Switch to Project Settings"),
        subtitle: cmdText("cmd_view_project_sub", "Configuration, targets and registers"),
        icon: "settings",
        action: function () {
          if (typeof switchActiveView === "function") {
            switchActiveView("project");
          } else {
            if (workbench) workbench.dispatch({ type: "view", value: "project" });
            var btn = document.querySelector('[data-view="project"], [data-view-pane="project"]');
            if (btn) btn.click();
          }
        }
      },
      {
        id: "toggle-focus-mode",
        category: catViews,
        title: cmdText("cmd_toggle_focus_title", "Toggle Focus Mode (F)"),
        subtitle: cmdText("cmd_toggle_focus_sub", "Distraction-free reading without chrome"),
        shortcut: "F",
        icon: "eye",
        action: function () {
          var focusBtn = document.getElementById("reader-focus");
          if (focusBtn) {
            focusBtn.click();
          } else if (workbench) {
            workbench.dispatch({ type: "focus", value: !state.focus });
          }
        }
      },
      {
        id: "toggle-theme",
        category: catViews,
        title: cmdText("cmd_toggle_theme_title", "Toggle Dark/Light Mode"),
        subtitle: cmdText("cmd_toggle_theme_sub", "Switch workspace color scheme"),
        icon: "lightbulb",
        action: function () {
          var themeBtn = document.querySelector("#theme-toggle, [data-theme-toggle]");
          if (themeBtn) {
            themeBtn.click();
          } else {
            var isDark = document.body.classList.toggle("theme-dark");
            try { localStorage.setItem("lixity-theme", isDark ? "dark" : "light"); } catch (_) {}
          }
        }
      }
    ];

    if (document.querySelector("#manuscript-write") || document.querySelector("#manuscript-close")) {
      commands.push({
        id: "toggle-manuscript-write",
        category: catViews,
        title: cmdText("cmd_toggle_write_title", "Toggle Write / Read Mode"),
        subtitle: cmdText("cmd_toggle_write_sub", "Switch between manuscript editor and reading view"),
        icon: "edit",
        action: function () {
          if (typeof switchActiveView === "function") switchActiveView("analysis");
          var closeBtn = document.querySelector("#manuscript-close");
          var writeBtn = document.querySelector("#manuscript-write");
          if (closeBtn && !closeBtn.hidden) {
            closeBtn.click();
          } else if (writeBtn) {
            writeBtn.click();
          }
        }
      });
    }

    commands = commands.concat(buildAnalysisLayerCommands(workbench), [
      {
        id: "metric-pacing",
        category: catAnalysis,
        title: cmdText("cmd_metric_pacing_title", "Show Pacing & Scene Tension"),
        subtitle: cmdText("cmd_metric_pacing_sub", "Scene lengths, staccato and hook cues"),
        icon: "layout",
        action: function () {
          var target = document.getElementById("pacing");
          if (target && typeof scrollAndFlash === "function") {
            scrollAndFlash(target);
          } else if (typeof selectAnalysisMetric === "function") {
            selectAnalysisMetric("pacing");
          }
        }
      },
      {
        id: "metric-style-space",
        category: catAnalysis,
        title: cmdText("cmd_metric_style_space_title", "Open Style Space Comparison"),
        subtitle: cmdText("cmd_metric_style_space_sub", "Inspect chapter distances in style space"),
        icon: "sliders",
        action: function () {
          var target = document.getElementById("style");
          if (target && typeof scrollAndFlash === "function") scrollAndFlash(target);
        }
      },
      {
        id: "metric-scenes",
        category: catAnalysis,
        title: cmdText("cmd_metric_scenes_title", "Open Scenes & Registers"),
        subtitle: cmdText("cmd_metric_scenes_sub", "Compare scene registers against project targets"),
        icon: "table",
        action: function () {
          var target = document.getElementById("scenes");
          if (target && typeof scrollAndFlash === "function") scrollAndFlash(target);
        }
      },

      // Research
      {
        id: "research-search",
        category: catResearch,
        title: cmdText("cmd_research_search_title", "Open Research Search"),
        subtitle: cmdText("cmd_research_search_sub", "Search sources, citations and dossiers"),
        shortcut: "S",
        icon: "search",
        action: function () {
          if (typeof switchActiveView === "function") switchActiveView("research");
          else if (workbench) workbench.dispatch({ type: "view", value: "research" });
          var searchTab = document.querySelector('#research-tab-search, [data-rtab="search"]');
          if (searchTab) searchTab.click();
          var searchField = document.querySelector("#r-search-query, #research-search, .research-search-input, input[name='q']");
          if (searchField) {
            if (typeof scrollAndFlash === "function") scrollAndFlash(searchField, { block: "nearest" });
            searchField.focus({ preventScroll: true });
            searchField.select();
          }
        }
      },
      {
        id: "research-new-dossier",
        category: catResearch,
        title: cmdText("cmd_research_new_dossier_title", "Create New Research Dossier"),
        subtitle: cmdText("cmd_research_new_dossier_sub", "Draft new dossier note with citations"),
        icon: "edit",
        action: function () {
          if (typeof switchActiveView === "function") switchActiveView("research");
          else if (workbench) workbench.dispatch({ type: "view", value: "research" });
          var dosTab = document.querySelector('#research-tab-dossiers, [data-rtab="dossiers"]');
          if (dosTab) dosTab.click();
          var composer = document.getElementById("r-dos-composer");
          if (composer) composer.open = true;
          var titleField = document.getElementById("r-dos-title");
          if (titleField) {
            if (typeof scrollAndFlash === "function") scrollAndFlash(titleField, { block: "nearest" });
            titleField.focus({ preventScroll: true });
          } else {
            var newBtn = document.querySelector("#research-new-dossier, [data-research-action='new-dossier']");
            if (newBtn) newBtn.click();
          }
        }
      },
      {
        id: "research-timeline",
        category: catResearch,
        title: cmdText("cmd_research_timeline_title", "Open Chronology & Timeline"),
        subtitle: cmdText("cmd_research_timeline_sub", "Inspect claims and events over time"),
        icon: "list-ordered",
        action: function () {
          if (typeof switchActiveView === "function") switchActiveView("research");
          else if (workbench) workbench.dispatch({ type: "view", value: "research" });
          var timelineTab = document.querySelector('#research-tab-timeline, [data-rtab="timeline"]');
          if (timelineTab) timelineTab.click();
          else {
            var claimsTab = document.querySelector('#research-tab-claims, [data-rtab="claims"]');
            if (claimsTab) claimsTab.click();
            var timelineBtn = document.querySelector('#r-open-timeline, [data-claim-view="timeline"], [data-research-tab="timeline"]');
            if (timelineBtn) timelineBtn.click();
          }
        }
      },
      {
        id: "research-canvas",
        category: catResearch,
        title: cmdText("cmd_research_canvas_title", "Visual Relations (JSON Canvas)"),
        subtitle: cmdText("cmd_research_canvas_sub", "Export dossiers and claims as JSON Canvas"),
        icon: "share-2",
        action: function () {
          if (window.LixityResearch && typeof window.LixityResearch.exportCanvas === "function") {
            window.LixityResearch.exportCanvas();
          } else {
            window.location.hash = "#research-canvas";
          }
        }
      },

      // Audio & Speech
      {
        id: "audio-teleprompter",
        category: catAudio,
        title: cmdText("cmd_audio_teleprompter_title", "Open Teleprompter (P)"),
        subtitle: cmdText("cmd_audio_teleprompter_sub", "Live pacing with vocal cues and phonetics"),
        shortcut: "P",
        icon: "mic",
        action: function () {
          var pBtn = document.getElementById("reader-teleprompter");
          if (pBtn) {
            pBtn.click();
          } else if (window.LixityTeleprompter && typeof window.LixityTeleprompter.open === "function") {
            window.LixityTeleprompter.open();
          }
        }
      },
      {
        id: "audio-studio",
        category: catAudio,
        title: cmdText("cmd_audio_studio_title", "Open Audio Studio & Recording"),
        subtitle: cmdText("cmd_audio_studio_sub", "Record chapter takes and inspect speech"),
        icon: "play",
        action: function () {
          var studioBtn = document.querySelector("#audio-studio-trigger, [data-action='audio-studio'], #reader-speech");
          if (studioBtn) studioBtn.click();
        }
      },

      // Exports
      {
        id: "export-pdf",
        category: catExport,
        title: cmdText("cmd_export_pdf_title", "Export Manuscript as PDF"),
        subtitle: cmdText("cmd_export_pdf_sub", "Print-ready typeset or editorial report"),
        icon: "download",
        action: function () {
          var pdfBtn = document.querySelector("#export-pdf-trigger, button[data-export='pdf'], [data-action='export-pdf']");
          if (pdfBtn) {
            pdfBtn.click();
            return;
          }
          var projectActions = document.getElementById("project-actions");
          if (projectActions) projectActions.open = true;
          var manuscriptPdf = document.getElementById("manuscript-pdf");
          if (manuscriptPdf) {
            manuscriptPdf.open = true;
            var layoutSelect = document.getElementById("manuscript-pdf-layout");
            if (layoutSelect) layoutSelect.focus();
          }
        }
      },
      {
        id: "export-storyboard-canvas",
        category: catExport,
        title: cmdText("cmd_export_storyboard_title", "Export Scenes as JSON Canvas"),
        subtitle: cmdText("cmd_export_storyboard_sub", "Visual storyboard for Obsidian Canvas"),
        icon: "share-2",
        action: function () {
          var link = document.createElement("a");
          link.href = "/api/canvas";
          link.download = "storyboard.canvas";
          link.click();
        }
      }
    ]);

    return commands.concat(buildChapterCommands(workbench));
  }

  function createPaletteDOM() {
    var dialog = document.createElement("dialog");
    dialog.id = "command-palette-dialog";
    dialog.className = "command-palette-dialog";
    dialog.setAttribute("aria-label", cmdText("cmd_aria_label", "Command Palette"));

    var wrap = document.createElement("div");
    wrap.className = "command-palette-wrap";

    // Header with search input
    var header = document.createElement("div");
    header.className = "command-palette-header";

    var searchIconWrap = document.createElement("span");
    searchIconWrap.className = "command-palette-search-icon";
    searchIconWrap.innerHTML = icon("search");

    var input = document.createElement("input");
    input.id = "command-palette-search";
    input.className = "command-palette-input";
    input.type = "text";
    input.placeholder = cmdText("cmd_placeholder", "Type a command or search...");
    input.autocomplete = "off";
    input.spellcheck = false;

    var escKbd = document.createElement("kbd");
    escKbd.className = "command-palette-esc-hint";
    escKbd.textContent = "Esc";

    header.appendChild(searchIconWrap);
    header.appendChild(input);
    header.appendChild(escKbd);

    // Results container
    var results = document.createElement("ul");
    results.id = "command-palette-results";
    results.className = "command-palette-results";
    results.setAttribute("role", "listbox");

    // Footer
    var footer = document.createElement("div");
    footer.className = "command-palette-footer";
    var escapeHtml = window.LixityComponents && window.LixityComponents.escapeHtml
      ? window.LixityComponents.escapeHtml
      : function (v) { return String(v); };
    footer.innerHTML =
      '<span class="command-palette-hint"><kbd>↑</kbd><kbd>↓</kbd> ' + escapeHtml(cmdText("cmd_hint_navigate", "Navigate")) + '</span>' +
      '<span class="command-palette-hint"><kbd>↵</kbd> ' + escapeHtml(cmdText("cmd_hint_run", "Run")) + '</span>' +
      '<span class="command-palette-hint"><kbd>Esc</kbd> ' + escapeHtml(cmdText("cmd_hint_close", "Close")) + '</span>';

    wrap.appendChild(header);
    wrap.appendChild(results);
    wrap.appendChild(footer);
    dialog.appendChild(wrap);
    document.body.appendChild(dialog);

    // Event listeners
    dialog.addEventListener("click", function (e) {
      if (e.target === dialog) close();
    });

    input.addEventListener("input", function () {
      renderResults(input.value.trim().toLowerCase());
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((selectedIndex + 1) % Math.max(1, activeCommands.length));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((selectedIndex - 1 + activeCommands.length) % Math.max(1, activeCommands.length));
      } else if (e.key === "Enter") {
        e.preventDefault();
        executeSelected();
      } else if (e.key === "Escape") {
        e.preventDefault();
        close();
      }
    });

    return { dialog: dialog, input: input, results: results };
  }

  function setSelectedIndex(idx) {
    selectedIndex = idx;
    var items = resultsList.querySelectorAll(".command-palette-item");
    items.forEach(function (item, i) {
      var isSel = i === selectedIndex;
      item.classList.toggle("selected", isSel);
      item.setAttribute("aria-selected", isSel ? "true" : "false");
      if (isSel) {
        item.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    });
  }

  function executeSelected() {
    if (activeCommands.length > 0 && activeCommands[selectedIndex]) {
      var cmd = activeCommands[selectedIndex];
      close();
      try {
        cmd.action();
      } catch (err) {
        console.error("Command palette error executing command:", err);
      }
    }
  }

  function renderResults(query) {
    var commands = getCommands();
    activeCommands = commands.filter(function (cmd) {
      if (!query) return true;
      var text = (cmd.title + " " + cmd.subtitle + " " + cmd.category).toLowerCase();
      return text.indexOf(query) !== -1;
    });

    selectedIndex = 0;
    var components = window.LixityComponents;
    if (components && typeof components.html === "function" && typeof components.mount === "function") {
      var html = components.html;
      if (activeCommands.length === 0) {
        components.mount(
          resultsList,
          html`<li class="command-palette-empty">${cmdText("cmd_empty", "No matching commands found.")}</li>`
        );
        return;
      }
      var nodes = [];
      var cat = null;
      activeCommands.forEach(function (cmd, idx) {
        if (cmd.category !== cat) {
          cat = cmd.category;
          nodes.push(html`<li key=${"cat-" + cat} class="command-palette-category">${cat}</li>`);
        }
        var isSel = idx === 0;
        nodes.push(html`
          <li
            key=${cmd.id}
            class=${"command-palette-item" + (isSel ? " selected" : "")}
            role="option"
            aria-selected=${isSel ? "true" : "false"}
            onClick=${function () { selectedIndex = idx; executeSelected(); }}
            onMouseMove=${function () { if (selectedIndex !== idx) setSelectedIndex(idx); }}
          >
            <span class="command-palette-item-icon" dangerouslySetInnerHTML=${{ __html: icon(cmd.icon || "command") }}></span>
            <div class="command-palette-item-text">
              <span class="command-palette-item-title">${cmd.title}</span>
              <span class="command-palette-item-sub">${cmd.subtitle}</span>
            </div>
            ${cmd.shortcut ? html`<kbd class="command-palette-item-shortcut">${cmd.shortcut}</kbd>` : null}
          </li>
        `);
      });
      components.mount(resultsList, nodes);
      return;
    }

    resultsList.replaceChildren();

    if (activeCommands.length === 0) {
      var emptyLi = document.createElement("li");
      emptyLi.className = "command-palette-empty";
      emptyLi.textContent = cmdText("cmd_empty", "No matching commands found.");
      resultsList.appendChild(emptyLi);
      return;
    }

    var currentCategory = null;
    activeCommands.forEach(function (cmd, idx) {
      if (cmd.category !== currentCategory) {
        currentCategory = cmd.category;
        var catHeader = document.createElement("li");
        catHeader.className = "command-palette-category";
        catHeader.textContent = currentCategory;
        resultsList.appendChild(catHeader);
      }

      var li = document.createElement("li");
      li.className = "command-palette-item" + (idx === 0 ? " selected" : "");
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", idx === 0 ? "true" : "false");

      var iconSpan = document.createElement("span");
      iconSpan.className = "command-palette-item-icon";
      iconSpan.innerHTML = icon(cmd.icon || "command");

      var textWrap = document.createElement("div");
      textWrap.className = "command-palette-item-text";

      var titleSpan = document.createElement("span");
      titleSpan.className = "command-palette-item-title";
      titleSpan.textContent = cmd.title;

      var subSpan = document.createElement("span");
      subSpan.className = "command-palette-item-sub";
      subSpan.textContent = cmd.subtitle;

      textWrap.appendChild(titleSpan);
      textWrap.appendChild(subSpan);

      li.appendChild(iconSpan);
      li.appendChild(textWrap);

      if (cmd.shortcut) {
        var kbd = document.createElement("kbd");
        kbd.className = "command-palette-item-shortcut";
        kbd.textContent = cmd.shortcut;
        li.appendChild(kbd);
      }

      li.addEventListener("click", function () {
        selectedIndex = idx;
        executeSelected();
      });

      li.addEventListener("mousemove", function () {
        if (selectedIndex !== idx) {
          setSelectedIndex(idx);
        }
      });

      resultsList.appendChild(li);
    });
  }

  function open() {
    if (!paletteDialog) {
      var dom = createPaletteDOM();
      paletteDialog = dom.dialog;
      searchInput = dom.input;
      resultsList = dom.results;
    }

    lastFocusedElement = document.activeElement;
    searchInput.value = "";
    renderResults("");

    if (typeof paletteDialog.showModal === "function") {
      paletteDialog.showModal();
    } else {
      paletteDialog.setAttribute("open", "");
    }

    setTimeout(function () {
      searchInput.focus();
    }, 50);
  }

  function close() {
    if (!paletteDialog) return;
    if (typeof paletteDialog.close === "function") {
      paletteDialog.close();
    } else {
      paletteDialog.removeAttribute("open");
    }
    if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
      lastFocusedElement.focus({ preventScroll: true });
    }
  }

  function isOpen() {
    return paletteDialog && (paletteDialog.open || paletteDialog.hasAttribute("open"));
  }

  // Global keyboard shortcuts
  window.addEventListener("keydown", function (e) {
    // Escape when open
    if (e.key === "Escape" && isOpen()) {
      e.preventDefault();
      close();
      return;
    }

    // Ctrl+P / Cmd+P or Ctrl+K / Cmd+K triggers Command Palette
    var isModifier = e.ctrlKey || e.metaKey;
    var key = e.key ? e.key.toLowerCase() : "";
    if (isModifier && (key === "p" || key === "k")) {
      e.preventDefault();
      if (isOpen()) {
        close();
      } else {
        open();
      }
      return;
    }

    // Single 'F' or 'Ctrl+Shift+F' toggles Focus Mode if not inside an input/textarea
    var isInput = e.target.matches && e.target.matches("input, textarea, select, [contenteditable='true']");
    if (!isInput && !isOpen()) {
      if ((key === "f" && !e.ctrlKey && !e.metaKey && !e.altKey) || (isModifier && e.shiftKey && key === "f")) {
        var focusBtn = document.getElementById("reader-focus");
        if (focusBtn && document.body.classList.contains("manuscript-reading")) {
          e.preventDefault();
          focusBtn.click();
        }
      }
    }
  }, true);

  window.LixityCommandPalette = {
    open: open,
    close: close,
    isOpen: isOpen,
    getCommands: getCommands
  };
})();
