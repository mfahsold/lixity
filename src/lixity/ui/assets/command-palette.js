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

  function icon(name) {
    if (window.LixityIcons && typeof window.LixityIcons.create === "function") {
      return window.LixityIcons.create(name, "command-icon");
    }
    return "";
  }

  function getCommands() {
    var isDe = (document.documentElement.lang || "en").startsWith("de");
    var workbench = window.LixityWorkbench;
    var state = workbench && typeof workbench.state === "function" ? workbench.state() : {};

    return [
      // View switches
      {
        id: "view-analysis",
        category: isDe ? "Ansicht" : "Views",
        title: isDe ? "Zur Manuskript-Analyse wechseln" : "Switch to Manuscript Analysis",
        subtitle: isDe ? "Text, Metriken und Lektorat" : "Text, metrics and editing",
        icon: "file-text",
        action: function () {
          if (workbench) workbench.dispatch({ type: "view", value: "analysis" });
          var btn = document.querySelector('[data-view-pane="analysis"]');
          if (btn) btn.click();
        }
      },
      {
        id: "view-research",
        category: isDe ? "Ansicht" : "Views",
        title: isDe ? "Zum Recherche-Arbeitsbereich wechseln" : "Switch to Research Workspace",
        subtitle: isDe ? "Dossiers, Quellen, Zeitstrahl und Karten" : "Dossiers, sources, timeline and maps",
        icon: "archive",
        action: function () {
          if (workbench) workbench.dispatch({ type: "view", value: "research" });
          var btn = document.querySelector('[data-view-pane="research"]');
          if (btn) btn.click();
        }
      },
      {
        id: "view-project",
        category: isDe ? "Ansicht" : "Views",
        title: isDe ? "Zu den Projekteinstellungen wechseln" : "Switch to Project Settings",
        subtitle: isDe ? "Konfiguration, Autorenziele und Register" : "Configuration, targets and registers",
        icon: "settings",
        action: function () {
          if (workbench) workbench.dispatch({ type: "view", value: "project" });
          var btn = document.querySelector('[data-view-pane="project"]');
          if (btn) btn.click();
        }
      },
      {
        id: "toggle-focus-mode",
        category: isDe ? "Ansicht" : "Views",
        title: isDe ? "Fokus-Modus umschalten (F)" : "Toggle Focus Mode (F)",
        subtitle: isDe ? "Ablenkungsfreies Lesen ohne Seitenleisten" : "Distraction-free reading without chrome",
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
        category: isDe ? "Ansicht" : "Views",
        title: isDe ? "Dunkel-/Hell-Modus umschalten" : "Toggle Dark/Light Mode",
        subtitle: isDe ? "Farbschema des Arbeitsbereichs anpassen" : "Switch workspace color scheme",
        icon: "lightbulb",
        action: function () {
          var themeBtn = document.getElementById("theme-toggle") || document.querySelector("[data-theme-toggle]");
          if (themeBtn) {
            themeBtn.click();
          } else {
            var isDark = document.body.classList.toggle("theme-dark");
            try { localStorage.setItem("lixity-theme", isDark ? "dark" : "light"); } catch (_) {}
          }
        }
      },

      // Analysis & Metrics
      {
        id: "metric-asl",
        category: isDe ? "Analyse" : "Analysis",
        title: isDe ? "Satzlänge & Rhythmus (ASL) hervorheben" : "Highlight Sentence Length & Rhythm",
        subtitle: isDe ? "Mittlere Satzlänge und Variationskoeffizient" : "Average sentence length and rhythm",
        icon: "sigma",
        action: function () {
          if (typeof selectAnalysisMetric === "function") selectAnalysisMetric("asl");
          var sel = document.getElementById("style-layer");
          if (sel) { sel.value = "asl"; sel.dispatchEvent(new Event("change", { bubbles: true })); }
        }
      },
      {
        id: "metric-dialogue",
        category: isDe ? "Analyse" : "Analysis",
        title: isDe ? "Dialoge & Redeanteile hervorheben" : "Highlight Dialogue & Direct Speech",
        subtitle: isDe ? "Sprecherwechsel, Redeanteil und Dialoge" : "Dialogue turns and spoken share",
        icon: "quote",
        action: function () {
          if (typeof selectAnalysisMetric === "function") selectAnalysisMetric("dialogue_share");
          var sel = document.getElementById("style-layer");
          if (sel) { sel.value = "dialogue_share"; sel.dispatchEvent(new Event("change", { bubbles: true })); }
        }
      },
      {
        id: "metric-tense",
        category: isDe ? "Analyse" : "Analysis",
        title: isDe ? "Tempus-Marker hervorheben" : "Highlight Grammatical Tense",
        subtitle: isDe ? "Dominantes Tempus, Mischungen und Wechsel" : "Dominant tense, switches and mix",
        icon: "tag",
        action: function () {
          if (typeof selectAnalysisMetric === "function") selectAnalysisMetric("dominant_tense");
          var sel = document.getElementById("style-layer");
          if (sel) { sel.value = "dominant_tense"; sel.dispatchEvent(new Event("change", { bubbles: true })); }
        }
      },
      {
        id: "metric-pacing",
        category: isDe ? "Analyse" : "Analysis",
        title: isDe ? "Pacing & Szenen-Spannungsbögen anzeigen" : "Show Pacing & Scene Tension",
        subtitle: isDe ? "Szenenlängen, Staccato-Anteile und Hooks" : "Scene lengths, staccato and hook cues",
        icon: "layout",
        action: function () {
          var target = document.getElementById("pacing") || document.querySelector('[data-jump="#pacing"]');
          if (target) {
            target.scrollIntoView({ behavior: "smooth" });
          } else if (typeof selectAnalysisMetric === "function") {
            selectAnalysisMetric("pacing");
          }
        }
      },
      {
        id: "metric-style-space",
        category: isDe ? "Analyse" : "Analysis",
        title: isDe ? "Stilraum-Vergleich öffnen" : "Open Style Space Comparison",
        subtitle: isDe ? "Kapitel im multidimensionalen Stilraum vergleichen" : "Inspect chapter distances in style space",
        icon: "sliders",
        action: function () {
          var target = document.getElementById("style") || document.querySelector('[data-jump="#style"]');
          if (target) target.scrollIntoView({ behavior: "smooth" });
        }
      },
      {
        id: "metric-scenes",
        category: isDe ? "Analyse" : "Analysis",
        title: isDe ? "Szenen & Register-Register öffnen" : "Open Scenes & Registers",
        subtitle: isDe ? "Szenen-Register und Soll-Vorgaben vergleichen" : "Compare scene registers against project targets",
        icon: "table",
        action: function () {
          var target = document.getElementById("scenes") || document.querySelector('[data-jump="#scenes"]');
          if (target) target.scrollIntoView({ behavior: "smooth" });
        }
      },

      // Research
      {
        id: "research-search",
        category: isDe ? "Recherche" : "Research",
        title: isDe ? "Recherche-Suchmaske öffnen" : "Open Research Search",
        subtitle: isDe ? "Quellen, Belege und Dossiers nach Begriffen durchsuchen" : "Search sources, citations and dossiers",
        shortcut: "S",
        icon: "search",
        action: function () {
          if (workbench) workbench.dispatch({ type: "view", value: "research" });
          var searchField = document.getElementById("research-search") || document.querySelector(".research-search-input");
          if (searchField) {
            searchField.focus();
            searchField.select();
          }
        }
      },
      {
        id: "research-new-dossier",
        category: isDe ? "Recherche" : "Research",
        title: isDe ? "Neues Forschungs-Dossier anlegen" : "Create New Research Dossier",
        subtitle: isDe ? "Neues Notizblatt mit Markdown & Belegen verfassen" : "Draft new dossier note with citations",
        icon: "edit",
        action: function () {
          if (workbench) workbench.dispatch({ type: "view", value: "research" });
          var newBtn = document.getElementById("research-new-dossier") || document.querySelector('[data-research-action="new-dossier"]');
          if (newBtn) newBtn.click();
        }
      },
      {
        id: "research-timeline",
        category: isDe ? "Recherche" : "Research",
        title: isDe ? "Chronologie & Zeitstrahl öffnen" : "Open Chronology & Timeline",
        subtitle: isDe ? "Ereignisse, Behauptungen und Belege auf der Zeitachse" : "Inspect claims and events over time",
        icon: "list-ordered",
        action: function () {
          if (workbench) workbench.dispatch({ type: "view", value: "research" });
          var tab = document.querySelector('[data-research-tab="timeline"]');
          if (tab) tab.click();
        }
      },
      {
        id: "research-canvas",
        category: isDe ? "Recherche" : "Research",
        title: isDe ? "Visuelle Beziehungen (JSON Canvas)" : "Visual Relations (JSON Canvas)",
        subtitle: isDe ? "Dossiers und Belege als Obsidian Canvas Board" : "Export dossiers and claims as JSON Canvas",
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
        category: isDe ? "Audio & Sprache" : "Audio & Speech",
        title: isDe ? "Teleprompter öffnen (P)" : "Open Teleprompter (P)",
        subtitle: isDe ? "Flüssiges Mitlesen mit Sprechtempo, Phonetik und Regie" : "Live pacing with vocal cues and phonetics",
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
        category: isDe ? "Audio & Sprache" : "Audio & Speech",
        title: isDe ? "Audio Studio & Aufnahme öffnen" : "Open Audio Studio & Recording",
        subtitle: isDe ? "Kapitel einsprechen, Takes verwalten und Synthese prüfen" : "Record chapter takes and inspect speech",
        icon: "play",
        action: function () {
          var studioBtn = document.getElementById("audio-studio-trigger") || document.querySelector('[data-action="audio-studio"]');
          if (studioBtn) studioBtn.click();
        }
      },

      // Exports
      {
        id: "export-pdf",
        category: isDe ? "Export" : "Export",
        title: isDe ? "Manuskript als PDF exportieren" : "Export Manuscript as PDF",
        subtitle: isDe ? "Druckfertiger Buchsatz oder Lektoratsbericht" : "Print-ready typeset or editorial report",
        icon: "download",
        action: function () {
          var pdfBtn = document.getElementById("export-pdf-trigger") || document.querySelector('button[data-export="pdf"]');
          if (pdfBtn) pdfBtn.click();
        }
      },
      {
        id: "export-storyboard-canvas",
        category: isDe ? "Export" : "Export",
        title: isDe ? "Szenen-Storyboard als JSON Canvas exportieren" : "Export Scenes as JSON Canvas",
        subtitle: isDe ? "Visuelles Storyboard für Obsidian Canvas (.canvas)" : "Visual storyboard for Obsidian Canvas",
        icon: "share-2",
        action: function () {
          var link = document.createElement("a");
          link.href = "/api/canvas";
          link.download = "storyboard.canvas";
          link.click();
        }
      }
    ];
  }

  function createPaletteDOM() {
    var isDe = (document.documentElement.lang || "en").startsWith("de");
    var dialog = document.createElement("dialog");
    dialog.id = "command-palette-dialog";
    dialog.className = "command-palette-dialog";
    dialog.setAttribute("aria-label", isDe ? "Befehlspalette" : "Command Palette");

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
    input.placeholder = isDe ? "Befehl eingeben oder suchen..." : "Type a command or search...";
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
    footer.innerHTML = `
      <span class="command-palette-hint"><kbd>↑</kbd><kbd>↓</kbd> ${isDe ? "Navigieren" : "Navigate"}</span>
      <span class="command-palette-hint"><kbd>↵</kbd> ${isDe ? "Ausführen" : "Run"}</span>
      <span class="command-palette-hint"><kbd>Esc</kbd> ${isDe ? "Schließen" : "Close"}</span>
    `;

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

    resultsList.replaceChildren();
    selectedIndex = 0;

    if (activeCommands.length === 0) {
      var isDe = (document.documentElement.lang || "en").startsWith("de");
      var emptyLi = document.createElement("li");
      emptyLi.className = "command-palette-empty";
      emptyLi.textContent = isDe ? "Keine passenden Befehle gefunden." : "No matching commands found.";
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
