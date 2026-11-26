// Command palette and workspace-level keyboard commands.
(function () {
  "use strict";

  var paletteDialog = null;
  var searchInput = null;
  var resultsList = null;
  var emptyResults = null;
  var selectedIndex = 0;
  var activeCommands = [];
  var lastFocusedElement = null;
  var paletteShortcuts = "Control+K Meta+K Control+P Meta+P";

  var STANDALONE_DE = {
    cmd_aria_label: "Befehlspalette",
    cmd_empty: "Keine passenden Befehle gefunden.",
    cmd_placeholder: "Befehl eingeben oder suchen...",
    cmd_cat_views: "Ansicht",
    cmd_cat_analysis: "Analyse",
    cmd_cat_research: "Recherche",
    cmd_cat_audio: "Audio & Sprache",
    cmd_cat_export: "Export",
    cmd_layer_dialogue_hint: "Dialoge, Sprecherwechsel & Redeanteile",
    cmd_layer_asl_hint: "Satzlänge & Lesefluss",
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

  function activateAnalysisLayer(select, layerValue, workbench) {
    if (typeof switchActiveView === "function") switchActiveView("analysis");
    if (workbench) workbench.dispatch({ type: "surface", value: "document", analysisVisible: true });
    window.LixityComponents.changeSelectOption(select, layerValue);
  }

  function buildAnalysisLayerCommands(workbench, category) {
    var select = document.getElementById("style-layer");
    if (!select || select.disabled || select.options.length < 2) return [];
    var hints = {
      dialogue: cmdText("cmd_layer_dialogue_hint", "Share of words in quotes and marked speech"),
      asl: cmdText("cmd_layer_asl_hint", "Sentence length & rhythm")
    };
    return Array.from(select.options).filter(function(option) {
      return !option.disabled && !option.parentElement.disabled && option.textContent.trim();
    }).map(function(option) {
      var value = option.value;
      var group = option.parentElement.tagName === "OPTGROUP" ? option.parentElement.label.trim() : "";
      var hint = hints[value] || option.dataset.hint;
      return {
        id: value ? "layer-" + value : "layer-off",
        category: group ? category + ": " + group : category,
        title: option.textContent.trim(),
        subtitle: [group, hint].filter(Boolean).join(" · ") || cmdText("cmd_layer_toggle_sub", "Toggle analysis layer in manuscript"),
        icon: value ? "sigma" : "eye",
        action: function () { activateAnalysisLayer(select, value, workbench); }
      };
    });
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
          if (!window.LixityComponents.changeSelectOption(sel, chId)) {
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
        title: cmdText("cmd_toggle_focus_title", "Toggle Focus Mode").replace(/\s+\(F\)$/, ""),
        subtitle: cmdText("cmd_toggle_focus_sub", "Distraction-free reading without chrome"),
        shortcut: document.getElementById("reader-focus")?.getClientRects().length ? "F" : "",
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
          window.LixityComponents.toggleTheme();
        }
      }
    ];

    if (window.LixityReader && !document.body.classList.contains("manuscript-writing")) {
      commands.push({
        id: "view-analysis-overview",
        category: catViews,
        title: cmdText("reading_overview", "Analysis overview"),
        subtitle: cmdText("reading_help_overview", "Open measurements, chapter matrix and style comparisons"),
        icon: "layout",
        action: window.LixityReader.showOverview
      });
    }
    if (window.LixityDesktopBridge) {
      commands.push({
        id: "tools-system-status",
        category: catViews,
        title: cmdText("cmd_system_status_title", "System Status & Optional Extensions"),
        subtitle: cmdText("cmd_system_status_sub", "Inspect local PDF/OCR, Zotero, audio and runtime status"),
        icon: "settings",
        action: window.LixityDesktopBridge.openSystemStatus
      });
    }

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

    commands = commands.concat(buildAnalysisLayerCommands(workbench, catAnalysis));
    var analysisSections = [
      {
        id: "metric-pacing",
        category: catAnalysis,
        target: "pacing",
        title: cmdText("cmd_metric_pacing_title", "Show Pacing & Scene Tension"),
        subtitle: cmdText("cmd_metric_pacing_sub", "Scene lengths, staccato and hook cues"),
        icon: "layout"
      },
      {
        id: "metric-style-space",
        category: catAnalysis,
        target: "style",
        title: cmdText("cmd_metric_style_space_title", "Open Style Space Comparison"),
        subtitle: cmdText("cmd_metric_style_space_sub", "Inspect chapter distances in style space"),
        icon: "sliders"
      },
      {
        id: "metric-scenes",
        category: catAnalysis,
        target: "scenes",
        title: cmdText("cmd_metric_scenes_title", "Open Scenes & Registers"),
        subtitle: cmdText("cmd_metric_scenes_sub", "Compare scene registers against project targets"),
        icon: "table"
      }
    ];
    if (typeof scrollAndFlash === "function") {
      analysisSections.forEach(function(command) {
        var target = document.getElementById(command.target);
        if (!target) return;
        command.action = function () { scrollAndFlash(target); };
        commands.push(command);
      });
    }
    commands = commands.concat([
      // Research
      {
        id: "research-search",
        category: catResearch,
        title: cmdText("cmd_research_search_title", "Open Research Search"),
        subtitle: cmdText("cmd_research_search_sub", "Search sources, citations and dossiers"),
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
          openResearchDossierComposer();
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
        title: cmdText("cmd_audio_teleprompter_title", "Open Teleprompter").replace(/\s+\(P\)$/, ""),
        subtitle: cmdText("cmd_audio_teleprompter_sub", "Live pacing with vocal cues and phonetics"),
        shortcut: document.getElementById("reader-teleprompter")?.getClientRects().length ? "P" : "",
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
          window.LixityComponents.openManuscriptPdf();
        }
      },
      {
        id: "export-storyboard-canvas",
        category: catExport,
        title: cmdText("cmd_export_storyboard_title", "Export Scenes as JSON Canvas"),
        subtitle: cmdText("cmd_export_storyboard_sub", "Visual storyboard for Obsidian Canvas"),
        icon: "share-2",
        action: function () {
          var apiBase = (document.body && document.body.dataset && document.body.dataset.api) || "/api";
          if (window.lixityDesktop && typeof window.lixityDesktop.saveExport === "function") {
            window.lixityDesktop.saveExport({ path: apiBase + "/canvas", method: "GET" }, "storyboard.canvas").catch(function () {});
            return;
          }
          var link = document.createElement("a");
          link.href = apiBase + "/canvas";
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
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-label", input.placeholder);
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "false");
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
    results.setAttribute("aria-label", dialog.getAttribute("aria-label"));
    input.setAttribute("aria-controls", results.id);

    var empty = document.createElement("div");
    empty.className = "command-palette-empty";
    empty.setAttribute("role", "status");
    empty.hidden = true;
    empty.textContent = cmdText("cmd_empty", "No matching commands found.");

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
    wrap.appendChild(empty);
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
      if (e.isComposing || e.defaultPrevented) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (activeCommands.length) {
          var step = e.key === "ArrowDown" ? 1 : -1;
          setSelectedIndex((selectedIndex + step + activeCommands.length) % activeCommands.length);
        }
      } else if (e.key === "Enter") {
        e.preventDefault();
        executeSelected();
      } else if (e.key === "Escape") {
        e.preventDefault();
        close();
      }
    });

    return { dialog: dialog, input: input, results: results, empty: empty };
  }

  function optionId(command) {
    return "command-palette-option-" + encodeURIComponent(command.id);
  }

  function setSelectedIndex(idx, scroll = true) {
    selectedIndex = idx;
    var items = resultsList.querySelectorAll(".command-palette-item");
    items.forEach(function (item, i) {
      var isSel = i === selectedIndex;
      item.classList.toggle("selected", isSel);
      item.setAttribute("aria-selected", isSel ? "true" : "false");
    });
    var active = items[selectedIndex];
    if (active) {
      searchInput.setAttribute("aria-activedescendant", active.id);
      if (scroll) active.scrollIntoView({ block: "nearest", behavior: "smooth" });
    } else {
      searchInput.removeAttribute("aria-activedescendant");
    }
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

    var hasResults = activeCommands.length > 0;
    resultsList.hidden = !hasResults;
    emptyResults.hidden = hasResults;
    searchInput.setAttribute("aria-expanded", String(hasResults));
    var components = window.LixityComponents;
    if (components && typeof components.html === "function" && typeof components.mount === "function") {
      var html = components.html;
      var nodes = [];
      var cat = null;
      activeCommands.forEach(function (cmd, idx) {
        if (cmd.category !== cat) {
          cat = cmd.category;
          nodes.push(html`<li key=${"cat-" + cat} class="command-palette-category" role="presentation">${cat}</li>`);
        }
        nodes.push(html`
          <li
            key=${cmd.id}
            id=${optionId(cmd)}
            class="command-palette-item"
            role="option"
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
      setSelectedIndex(hasResults ? 0 : -1, false);
      return;
    }

    resultsList.replaceChildren();

    var currentCategory = null;
    activeCommands.forEach(function (cmd, idx) {
      if (cmd.category !== currentCategory) {
        currentCategory = cmd.category;
        var catHeader = document.createElement("li");
        catHeader.className = "command-palette-category";
        catHeader.setAttribute("role", "presentation");
        catHeader.textContent = currentCategory;
        resultsList.appendChild(catHeader);
      }

      var li = document.createElement("li");
      li.id = optionId(cmd);
      li.className = "command-palette-item";
      li.setAttribute("role", "option");

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
    setSelectedIndex(hasResults ? 0 : -1, false);
  }

  function open() {
    if (!paletteDialog) {
      var dom = createPaletteDOM();
      paletteDialog = dom.dialog;
      searchInput = dom.input;
      resultsList = dom.results;
      emptyResults = dom.empty;
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
    searchInput.setAttribute("aria-expanded", "false");
    setSelectedIndex(-1, false);
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

  function bindLauncher() {
    document.querySelectorAll("[data-open-command-palette]").forEach(function (button) {
      button.setAttribute("aria-keyshortcuts", paletteShortcuts);
      button.hidden = false;
      button.addEventListener("click", open);
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bindLauncher);
  else bindLauncher();

  window.addEventListener("keydown", function (e) {
    if (e.defaultPrevented || e.isComposing || e.repeat) return;
    if (e.key === "Escape" && isOpen()) {
      e.preventDefault();
      close();
      return;
    }

    var target = e.target instanceof Element ? e.target : document.body;
    if (e.altKey || (!isOpen() && (target.closest('dialog[open], [role="dialog"], [role="menu"]') ||
        document.querySelector("dialog:modal")))) return;

    var isModifier = e.ctrlKey !== e.metaKey;
    var key = e.key ? e.key.toLowerCase() : "";
    if (isModifier && !e.shiftKey && (key === "p" || key === "k")) {
      // The Markdown editor already uses the same chord to insert a link.
      if (key === "k" && target.matches(".markdown-editor-area")) return;
      e.preventDefault();
      if (isOpen()) {
        close();
      } else {
        open();
      }
      return;
    }

    var isInput = target.closest("input, textarea, select, [contenteditable]");
    if (!isInput && !isOpen()) {
      if ((key === "f" && !e.ctrlKey && !e.metaKey && !e.altKey) || (isModifier && e.shiftKey && key === "f")) {
        var focusBtn = document.getElementById("reader-focus");
        if (focusBtn && focusBtn.getClientRects().length) {
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
