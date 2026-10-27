// Project surfaces: import, recent projects, view switching and the
// workspace bridges (extracted from dashboard.js).

// --- Workspace & Project Modals -------------------------------------------
var importedFileContent = "";
var importedFileRead = 0;
var researchTemplateChoice = null;
var manuscriptFile = null;
var manuscriptInput = document.getElementById("ms-file");
var manuscriptButton = document.querySelector('[data-action="load"]');

function supportedManuscriptFile(file) {
  return file && /\.(md|markdown|txt)$/i.test(file.name);
}

function manuscriptFileError(key) {
  var status = document.getElementById("ctl-status");
  if (status) {
    status.className = "ctl-status err";
    status.textContent = uiLabel(key || "manuscript_file_invalid");
  }
}

function selectManuscriptFiles(files) {
  if (!manuscriptInput) return;
  var valid = files && files.length === 1 && supportedManuscriptFile(files[0]);
  if (valid) manuscriptFile = files[0];
  var transfer = new DataTransfer();
  if (manuscriptFile) transfer.items.add(manuscriptFile);
  manuscriptInput.files = transfer.files;
  if (!valid) { manuscriptFileError(); return; }
  document.getElementById("manuscript-file-name").textContent = manuscriptFile.name;
  if (manuscriptButton && !manuscriptButton.hasAttribute("aria-busy")) manuscriptButton.disabled = false;
  var status = document.getElementById("ctl-status");
  if (status) { status.className = "ctl-status"; status.textContent = ""; }
}

function switchModalTab(targetPaneId) {
  var targetPane = document.getElementById(targetPaneId);
  var dialog = targetPane && targetPane.closest("dialog");
  if (!dialog) return;
  dialog.querySelectorAll(".modal-tab-btn[data-tab-target]").forEach(function (btn) {
    var isTarget = btn.dataset.tabTarget === targetPaneId;
    btn.classList.toggle("active", isTarget);
    btn.setAttribute("aria-selected", isTarget ? "true" : "false");
  });
  dialog.querySelectorAll(".modal-tab-pane").forEach(function (pane) {
    pane.style.display = pane.id === targetPaneId ? "block" : "none";
  });
}

function updateImportLanguagePreview() {
  var langEl = document.getElementById("import-fpc-lang");
  var langSelect = document.getElementById("import-proj-lang");
  if (langEl && langSelect && langSelect.selectedOptions.length) {
    langEl.textContent = langSelect.selectedOptions[0].textContent;
  }
}

function processImportedFile(file) {
  if (!file) return;
  var submitBtn = document.getElementById("btn-submit-import-project");
  if (submitBtn && submitBtn.hasAttribute("aria-busy")) return;
  var read = ++importedFileRead;
  importedFileContent = "";
  if (submitBtn) submitBtn.disabled = true;
  var previewBox = document.getElementById("import-preview-box");
  if (previewBox) previewBox.style.display = "none";
  var lossEl = document.getElementById("import-fpc-loss");
  if (lossEl) { lossEl.replaceChildren(); lossEl.hidden = true; }
  var isDocx = /\.docx$/i.test(file.name);
  var feedback = document.getElementById("import-project-status");
  if (feedback) {
    feedback.className = "ctl-status project-form-status loading";
    feedback.textContent = uiLabel(isDocx ? "import_docx_converting" : "research_ingesting_reading");
    feedback.hidden = false;
  }

  if (isDocx) {
    var docxReader = new FileReader();
    docxReader.onload = async function (e) {
      if (read !== importedFileRead) return;
      var dataUrl = String(e.target.result || "");
      var base64Content = dataUrl.indexOf(",") !== -1 ? dataUrl.split(",")[1] : dataUrl;
      try {
        var apiUrl = (typeof API !== "undefined" ? API : (document.body.dataset.api || "")) + "/manuscript-import-preview";
        var res = await fetch(apiUrl, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({filename: file.name, content_base64: base64Content})
        });
        var data = await res.json();
        if (read !== importedFileRead) return;
        if (!res.ok || !data.ok) {
          throw new Error(data.message || uiLabel("manuscript_read_failed"));
        }
        importedFileContent = data.markdown || "";
        var cleanStem = file.name.replace(/\.[^/.]+$/, "").replace(/[-_]+/g, " ");
        var detectedTitle = cleanStem;
        var chapters = 0;
        if (Array.isArray(data.headings)) {
          var h1 = data.headings.find(function (h) { return h.level === 1; });
          if (h1 && h1.text) detectedTitle = h1.text.trim();
          chapters = data.headings.filter(function (h) { return h.level <= 2; }).length;
        }
        var words = Number(data.word_count) || (importedFileContent.trim().match(/\S+/g) || []).length;

        var previewBox = document.getElementById("import-preview-box");
        if (previewBox) previewBox.style.display = "flex";

        var fNameEl = document.getElementById("import-fpc-filename");
        if (fNameEl) fNameEl.textContent = file.name;

        var statsEl = document.getElementById("import-fpc-stats");
        if (statsEl) {
          statsEl.textContent = uiFormat("wizard_preview_stats", {
            words: words.toLocaleString(document.documentElement.lang || "en"),
            chapters: chapters
          });
        }
        updateImportLanguagePreview();

        var titleInput = document.getElementById("import-proj-title");
        if (titleInput) titleInput.value = detectedTitle;

        if (Array.isArray(data.loss_report) && data.loss_report.length > 0 && lossEl) {
          var titleSpan = document.createElement("div");
          titleSpan.className = "fpc-loss-title";
          titleSpan.textContent = uiFormat("import_loss_warning", {count: data.loss_report.length});
          var list = document.createElement("ul");
          data.loss_report.forEach(function (item) {
            var li = document.createElement("li");
            li.textContent = item.element + ": " + item.reason;
            list.appendChild(li);
          });
          lossEl.append(titleSpan, list);
          lossEl.hidden = false;
        }

        if (submitBtn && !submitBtn.hasAttribute("aria-busy")) {
          submitBtn.disabled = false;
        }
        if (feedback) { feedback.textContent = ""; feedback.hidden = true; }
      } catch (err) {
        if (read !== importedFileRead) return;
        if (feedback) {
          feedback.className = "ctl-status project-form-status err";
          feedback.textContent = err.message || uiLabel("manuscript_read_failed");
          feedback.hidden = false;
        }
      }
    };
    docxReader.onerror = function () {
      if (read !== importedFileRead) return;
      if (feedback) {
        feedback.className = "ctl-status project-form-status err";
        feedback.textContent = uiLabel("manuscript_read_failed");
        feedback.hidden = false;
      }
    };
    docxReader.readAsDataURL(file);
    return;
  }

  var reader = new FileReader();
  reader.onload = function (e) {
    if (read !== importedFileRead) return;
    var text = String(e.target.result || "");
    importedFileContent = text;

    // Detect title: first # Heading or file stem
    var titleMatch = text.match(/^#\s+([^\n\r]+)/m);
    var cleanStem = file.name.replace(/\.[^/.]+$/, "").replace(/[-_]+/g, " ");
    var detectedTitle = titleMatch ? titleMatch[1].trim() : cleanStem;

    // Detect chapters: count lines starting with ##
    var chapterMatches = text.match(/^##\s+[^\n\r]+/gm);
    var chapterCount = chapterMatches ? chapterMatches.length : 0;

    // Word count
    var words = (text.trim().match(/\S+/g) || []).length;

    // Update UI Preview
    var previewBox = document.getElementById("import-preview-box");
    if (previewBox) previewBox.style.display = "flex";

    var fNameEl = document.getElementById("import-fpc-filename");
    if (fNameEl) fNameEl.textContent = file.name;

    var statsEl = document.getElementById("import-fpc-stats");
    if (statsEl) {
      statsEl.textContent = uiFormat("wizard_preview_stats", {
        words: words.toLocaleString(document.documentElement.lang || "en"), chapters: chapterCount
      });
    }

    updateImportLanguagePreview();

    var titleInput = document.getElementById("import-proj-title");
    if (titleInput) {
      titleInput.value = detectedTitle;
    }

    if (submitBtn && !submitBtn.hasAttribute("aria-busy")) {
      submitBtn.disabled = false;
    }
    if (feedback) { feedback.textContent = ""; feedback.hidden = true; }
  };
  reader.onerror = function () {
    if (read !== importedFileRead) return;
    if (feedback) {
      feedback.className = "ctl-status project-form-status err";
      feedback.textContent = uiLabel("manuscript_read_failed");
      feedback.hidden = false;
    }
  };
  reader.readAsText(file);
}

document.addEventListener("click", function (event) {
  var kpiToggle = event.target.closest("[data-kpi-toggle]");
  if (kpiToggle) {
    var target = document.getElementById(kpiToggle.dataset.kpiToggle);
    if (target) {
      target.hidden = !target.hidden;
      kpiToggle.setAttribute("aria-expanded", target.hidden ? "false" : "true");
    }
    return;
  }
  var manuscriptDrop = event.target.closest("#manuscript-dropzone");
  if (manuscriptDrop && event.target !== manuscriptInput) {
    if (manuscriptInput) manuscriptInput.click();
    return;
  }
  var tabBtn = event.target.closest(".modal-tab-btn");
  if (tabBtn && tabBtn.dataset.tabTarget) {
    switchModalTab(tabBtn.dataset.tabTarget);
    return;
  }

  var newBtn = event.target.closest("#btn-modal-new-project, #hero-btn-new-project, #analysis-empty-import");
  if (newBtn) {
    var modalNew = document.getElementById("modal-project-create");
    if (modalNew && typeof modalNew.showModal === "function") {
      switchModalTab("tab-pane-import");
      modalNew.showModal();
      var dropzone = document.getElementById("import-dropzone");
      if (dropzone) dropzone.focus();
    }
    return;
  }

  var recentBtn = event.target.closest("[data-recent-project-path]");
  if (recentBtn) {
    openExistingProject(recentBtn.dataset.recentProjectPath, false);
    return;
  }
  var clearRecent = event.target.closest("[data-clear-recent-projects]");
  if (clearRecent) {
    try {
      localStorage.removeItem(RECENT_PROJECTS_KEY);
      renderRecentProjects();
    } catch (_) {
      var recentStatus = clearRecent.closest("[data-recent-projects]").querySelector("[data-recent-project-status]");
      recentStatus.textContent = uiLabel("recent_projects_clear_failed");
      recentStatus.hidden = false;
    }
    return;
  }
  var openBtn = event.target.closest("#btn-modal-open-project, #hero-btn-open-project, #hero-btn-browse-project");
  if (openBtn) {
    openExistingProject(null, openBtn.id === "hero-btn-browse-project");
    return;
  }

  var importDrop = event.target.closest("#import-dropzone");
  if (importDrop) {
    var fileInput = document.getElementById("import-file-input");
    if (fileInput && event.target !== fileInput) fileInput.click();
    return;
  }

  var switchToImportBtn = event.target.closest("#link-switch-to-import");
  if (switchToImportBtn) {
    var modalOpen = document.getElementById("modal-project-open");
    if (modalOpen && typeof modalOpen.close === "function") modalOpen.close();
    var modalNew = document.getElementById("modal-project-create");
    if (modalNew && typeof modalNew.showModal === "function") {
      switchModalTab("tab-pane-import");
      modalNew.showModal();
      var dropzone = document.getElementById("import-dropzone");
      if (dropzone) dropzone.focus();
    }
    return;
  }

  var closeBtn = event.target.closest("[data-close-modal]");
  if (closeBtn) {
    var dialog = closeBtn.closest("dialog");
    if (dialog && typeof dialog.close === "function") dialog.close();
    return;
  }

  if (event.target.tagName === "DIALOG" && event.target.classList.contains("lixity-modal")) {
    var rect = event.target.getBoundingClientRect();
    var isInDialog = (rect.top <= event.clientY && event.clientY <= rect.top + rect.height
      && rect.left <= event.clientX && event.clientX <= rect.left + rect.width);
    if (!isInDialog && typeof event.target.close === "function") {
      event.target.close();
    }
  }
});

// Dropzone Drag & Drop events
["dragenter", "dragover"].forEach(function (eventName) {
  document.addEventListener(eventName, function (e) {
    var dropzone = e.target.closest(".file-dropzone");
    if (dropzone) {
      e.preventDefault();
      dropzone.classList.add("dragover");
    }
  });
});

["dragleave", "drop"].forEach(function (eventName) {
  document.addEventListener(eventName, function (e) {
    var dropzone = e.target.closest(".file-dropzone");
    if (dropzone) {
      dropzone.classList.remove("dragover");
    }
  });
});

document.addEventListener("drop", function (e) {
  if (e.target.closest("#manuscript-dropzone")) {
    e.preventDefault();
    selectManuscriptFiles(e.dataTransfer && e.dataTransfer.files);
    return;
  }
  var importDrop = e.target.closest("#import-dropzone");
  if (importDrop && e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
    e.preventDefault();
    processImportedFile(e.dataTransfer.files[0]);
    return;
  }
});

document.addEventListener("change", function (event) {
  if (event.target === manuscriptInput) {
    selectManuscriptFiles(event.target.files);
    return;
  }
  if (event.target.id === "import-proj-lang") {
    updateImportLanguagePreview();
  }
  if (event.target.id === "import-file-input" && event.target.files && event.target.files.length) {
    processImportedFile(event.target.files[0]);
    return;
  }

  if (event.target.name === "proj_template") {
    document.querySelectorAll(".template-card").forEach(function (card) {
      card.classList.toggle("active", card.contains(event.target));
    });
    var rBox = document.getElementById("new-proj-research");
    if (rBox) {
      if (event.target.value === "research") {
        if (researchTemplateChoice === null) researchTemplateChoice = rBox.checked;
        rBox.checked = true;
        rBox.disabled = true;
      } else {
        rBox.disabled = false;
        if (researchTemplateChoice !== null) rBox.checked = researchTemplateChoice;
        researchTemplateChoice = null;
      }
      document.getElementById("new-proj-research-required").hidden = !rBox.disabled;
    }
  }
});

var RECENT_PROJECTS_KEY = "lixity:recent-projects";
var RECENT_PROJECTS_LIMIT = 8;

function getRecentProjects() {
  try {
    var raw = localStorage.getItem(RECENT_PROJECTS_KEY);
    if (!raw) return [];
    var parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      var paths = [];
      for (var item of parsed) {
        if (typeof item !== "string" || !item.trim() || item.length > 8192) continue;
        var path = item.trim();
        if (!paths.includes(path)) paths.push(path);
        if (paths.length === RECENT_PROJECTS_LIMIT) break;
      }
      return paths;
    }
  } catch (_) {}
  return [];
}

function addRecentProject(path) {
  if (!path || typeof path !== "string") return;
  var norm = path.trim();
  if (!norm) return;
  var recents = getRecentProjects().filter(function(p) { return p !== norm; });
  recents.unshift(norm);
  if (recents.length > RECENT_PROJECTS_LIMIT) recents = recents.slice(0, RECENT_PROJECTS_LIMIT);
  try {
    localStorage.setItem(RECENT_PROJECTS_KEY, JSON.stringify(recents));
  } catch (_) {}
}

function removeRecentProject(path) {
  var recents = getRecentProjects().filter(function(p) { return p !== path; });
  try {
    localStorage.setItem(RECENT_PROJECTS_KEY, JSON.stringify(recents));
  } catch (_) {}
}

function renderRecentProjects() {
  var recents = getRecentProjects();
  document.querySelectorAll("[data-recent-projects]").forEach(function(wrap) {
    var list = wrap.querySelector("[data-recent-project-list]");
    var status = wrap.querySelector("[data-recent-project-status]");
    wrap.hidden = !recents.length;
    list.replaceChildren();
    if (status) status.hidden = true;
    recents.forEach(function(path) {
      var item = document.createElement("li");
      item.className = "project-chooser-toolbar";
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ctl project-chooser-entry";
      btn.style.cssText = "flex:1;width:auto;min-width:0;";
      btn.dataset.recentProjectPath = path;
      btn.textContent = path;
      var del = document.createElement("button");
      del.type = "button";
      del.className = "ctl";
      del.textContent = "×";
      del.setAttribute("aria-label", uiLabel("remove_recent_project") + " " + path);
      del.title = uiLabel("remove_recent_project");
      del.addEventListener("click", function() {
        removeRecentProject(path);
        renderRecentProjects();
      });
      item.append(btn, del);
      list.appendChild(item);
    });
  });
}

function openExistingProject(path, browse) {
  renderRecentProjects();
  var modal = document.getElementById("modal-project-open");
  var input = document.getElementById("open-proj-path");
  if (!modal || typeof modal.showModal !== "function") return;
  if (typeof path === "string" && input) input.value = path;
  modal.showModal();
  if (browse) document.getElementById("open-proj-choose").click();
  else if (typeof path === "string" && input) input.focus();
  else document.getElementById("open-proj-choose").focus();
}

renderRecentProjects();

async function submitProjectForm(form, action, payload, button) {
  if (button && button.disabled) return;
  var feedback = form.querySelector(".project-form-status");
  if (feedback) {
    feedback.hidden = true;
    feedback.textContent = "";
  }
  var result = await runAction(action, payload, button);
  if (result && result.ok) {
    if (action === "project-open" && payload && payload.path) {
      addRecentProject(typeof result.manuscript === "string" && result.manuscript ? result.manuscript :
        typeof result.workspace_root === "string" && result.workspace_root ? result.workspace_root : payload.path);
      renderRecentProjects();
    }
    var modal = form.closest("dialog");
    if (modal && typeof modal.close === "function") modal.close();
  } else if (feedback) {
    feedback.className = "ctl-status project-form-status err";
    feedback.textContent = uiFormat("wizard_action_failed", {
      reason: (result && result.message) || uiLabel("wizard_unknown_error")
    });
    feedback.hidden = false;
  }
}

// Form: Import existing manuscript
var formImport = document.getElementById("form-project-import");
if (formImport) {
  formImport.addEventListener("submit", async function (e) {
    e.preventDefault();
    var titleEl = document.getElementById("import-proj-title");
    var title = titleEl ? titleEl.value.trim() : "";
    if (!title) return;

    var langEl = document.getElementById("import-proj-lang");
    var lang = langEl ? langEl.value : "de";
    var pathEl = document.getElementById("import-proj-path");
    var folder = pathEl ? pathEl.value.trim() : "";
    var researchEl = document.getElementById("import-proj-research");
    var initResearch = Boolean(researchEl && researchEl.checked);
    var authorEl = document.getElementById("import-proj-author");
    var author = authorEl ? authorEl.value.trim() : "";

    var submitBtn = document.getElementById("btn-submit-import-project");
    await submitProjectForm(formImport, "project-create", {
      title: title,
      language: lang,
      author_name: author,
      path: folder,
      content: importedFileContent,
      init_research: initResearch
    }, submitBtn);
  });
}

// Form: Start new project from scratch
var formCreate = document.getElementById("form-project-create");
if (formCreate) {
  formCreate.addEventListener("submit", async function (e) {
    e.preventDefault();
    var titleEl = document.getElementById("new-proj-title");
    var title = titleEl ? titleEl.value.trim() : "";
    if (!title) return;
    var langEl = document.getElementById("new-proj-lang");
    var lang = langEl ? langEl.value : "en";
    var pathEl = document.getElementById("new-proj-path");
    var folder = pathEl ? pathEl.value.trim() : "";
    var templateEl = document.querySelector('input[name="proj_template"]:checked');
    var template = templateEl ? templateEl.value : "minimal";
    var researchEl = document.getElementById("new-proj-research");
    var initResearch = Boolean(researchEl && researchEl.checked);
    var authorEl = document.getElementById("new-proj-author");
    var author = authorEl ? authorEl.value.trim() : "";

    var submitBtn = document.getElementById("btn-submit-create-project");
    await submitProjectForm(formCreate, "project-create", {
      title: title,
      language: lang,
      author_name: author,
      path: folder,
      template: template,
      init_research: initResearch
    }, submitBtn);
  });
}

// Browse local paths without changing the project until the form is submitted.
var openChooser = document.getElementById("open-project-chooser");
if (openChooser) {
  var chooseButton = document.getElementById("open-proj-choose");
  var chooseClose = document.getElementById("open-project-chooser-close");
  var chooseHome = document.getElementById("open-project-chooser-home");
  var chooseParent = document.getElementById("open-project-chooser-parent");
  var chooseFolder = document.getElementById("open-project-chooser-select-folder");
  var choosePath = document.getElementById("open-project-chooser-path");
  var chooseList = document.getElementById("open-project-chooser-list");
  var chooseStatus = document.getElementById("open-project-chooser-status");
  var chooseProject = document.getElementById("open-project-chooser-project");
  var openPathInput = document.getElementById("open-proj-path");
  var currentChoosePath = "";
  var parentChoosePath = null;
  var chooseRequest = 0;

  function closeOpenChooser(focusTarget) {
    chooseRequest++;
    openChooser.hidden = true;
    chooseButton.setAttribute("aria-expanded", "false");
    if (focusTarget) focusTarget.focus();
  }

  function chooseMessage(message, error) {
    chooseStatus.textContent = message;
    chooseStatus.setAttribute("role", error ? "alert" : "status");
    chooseStatus.classList.toggle("err", Boolean(error));
  }

  function selectOpenPath(path) {
    openPathInput.value = path;
    var formStatus = document.getElementById("open-project-status");
    if (formStatus) {
      formStatus.textContent = "";
      formStatus.hidden = true;
    }
    closeOpenChooser(openPathInput);
  }

  async function loadOpenChooser(path, focusEntry) {
    var request = ++chooseRequest;
    currentChoosePath = "";
    parentChoosePath = null;
    choosePath.textContent = "";
    chooseParent.disabled = true;
    chooseList.replaceChildren();
    chooseList.setAttribute("aria-busy", "true");
    chooseFolder.disabled = true;
    chooseMessage(uiLabel("wizard_choose_loading"), false);
    var t0 = performance.now();
    var url = API + "/project-paths" + (path ? "?path=" + encodeURIComponent(path) : "");
    try {
      var response = await fetch(url);
      var data = await response.json();
      LixityLog.api("GET", url, performance.now() - t0, response.status, data);
      if (request !== chooseRequest || openChooser.hidden) return;
      if (!response.ok || !data.ok || typeof data.path !== "string" || !Array.isArray(data.entries)) {
        LixityLog.warn("loadOpenChooser response issue:", data);
        if (path) {
          chooseMessage(uiLabel("wizard_choose_stale_path") || (data.message || uiLabel("wizard_unknown_error")), true);
          setTimeout(function() {
            if (request === chooseRequest && !openChooser.hidden) {
              loadOpenChooser(null, focusEntry);
            }
          }, 1200);
          return;
        }
        chooseMessage(uiFormat("wizard_choose_failed", {
          reason: data.message || uiLabel("wizard_unknown_error")
        }), true);
        return;
      }
      currentChoosePath = data.path;
      parentChoosePath = typeof data.parent === "string" ? data.parent : null;
      choosePath.textContent = currentChoosePath;
      if (chooseProject) {
        var probe = data.project && typeof data.project === "object" ? data.project : null;
        if (probe && probe.detected === true) {
          var details = [];
          details.push(typeof probe.title === "string" && probe.title ? probe.title : uiLabel("chooser_project_badge"));
          if (typeof probe.language === "string" && probe.language) details.push(probe.language.toUpperCase());
          if (typeof probe.manuscript === "string" && probe.manuscript) details.push(probe.manuscript);
          chooseProject.textContent = uiFormat("chooser_project_found", {details: details.join(" · ")});
          chooseProject.classList.add("detected");
        } else {
          chooseProject.textContent = chooseProject.dataset.empty || "";
          chooseProject.classList.remove("detected");
        }
      }
      chooseParent.disabled = !parentChoosePath;
      chooseFolder.disabled = false;
      data.entries.forEach(function(entry) {
        if (!entry || typeof entry.name !== "string" || typeof entry.path !== "string" ||
            !["directory", "manuscript"].includes(entry.kind)) return;
        var item = document.createElement("li");
        var button = document.createElement("button");
        button.type = "button";
        button.className = "ctl project-chooser-entry";
        button.dataset.openPathKind = entry.kind;
        button.dataset.openPath = entry.path;
        button.setAttribute("aria-label", uiFormat(
          entry.kind === "directory" ? "wizard_choose_directory_entry" : "wizard_choose_manuscript_entry",
          { name: entry.name }
        ));
        var icon = document.createElement("span");
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = entry.kind === "directory" ? "📁" : "📄";
        var name = document.createElement("span");
        name.textContent = entry.name;
        button.append(icon, name);
        if (entry.kind === "directory" && entry.project === true) {
          // The badge sits beside the entry button: inside it, it would change
          // the button's text and break exact-text filters (tests, tooling).
          var badge = document.createElement("span");
          badge.className = "project-chooser-badge";
          badge.textContent = uiLabel("chooser_project_badge");
          item.appendChild(badge);
        }
        item.appendChild(button);
        chooseList.appendChild(item);
      });
      chooseMessage(chooseList.children.length === 0 ? uiLabel("wizard_choose_empty") :
        (data.truncated ? uiLabel("wizard_choose_truncated") : ""), false);
      if (focusEntry) (chooseList.querySelector("button") || chooseFolder).focus();
    } catch (error) {
      LixityLog.error("loadOpenChooser error:", error);
      if (request === chooseRequest && !openChooser.hidden) {
        chooseMessage(uiFormat("wizard_choose_failed", { reason: String(error) }), true);
      }
    } finally {
      if (request === chooseRequest) chooseList.removeAttribute("aria-busy");
    }
  }

  chooseButton.addEventListener("click", function() {
    if (!openChooser.hidden) {
      closeOpenChooser(chooseButton);
      return;
    }
    openChooser.hidden = false;
    chooseButton.setAttribute("aria-expanded", "true");
    loadOpenChooser(openPathInput.value.trim() || currentChoosePath || null, false);
  });
  chooseClose.addEventListener("click", function() { closeOpenChooser(chooseButton); });
  chooseHome.addEventListener("click", function() { loadOpenChooser(null, true); });
  chooseParent.addEventListener("click", function() {
    if (parentChoosePath) loadOpenChooser(parentChoosePath, true);
  });
  chooseFolder.addEventListener("click", function() {
    if (currentChoosePath) selectOpenPath(currentChoosePath);
  });
  chooseList.addEventListener("click", function(event) {
    var button = event.target.closest("[data-open-path-kind]");
    if (!button || !chooseList.contains(button)) return;
    if (button.dataset.openPathKind === "directory") loadOpenChooser(button.dataset.openPath, true);
    else selectOpenPath(button.dataset.openPath);
  });
  document.getElementById("modal-project-open").addEventListener("close", function() {
    closeOpenChooser(null);
  });
}

// Form: Open existing path
var formOpen = document.getElementById("form-project-open");
document.querySelectorAll(".project-form-status").forEach(function(status) {
  var form = status.closest("form");
  if (form) form.addEventListener("input", function() {
    status.textContent = "";
    status.hidden = true;
  });
});
if (formOpen) {
  formOpen.addEventListener("submit", async function (e) {
    e.preventDefault();
    var pathEl = document.getElementById("open-proj-path");
    var path = pathEl ? pathEl.value.trim() : "";
    if (!path) return;

    var submitBtn = document.getElementById("btn-submit-open-project");
    await submitProjectForm(formOpen, "project-open", { path: path }, submitBtn);
  });
}

// Workspace Navigation (3 Main Views)
var workspaceScrollPositions = Object.create(null);
var workspaceNavigationRevision = 0;
document.addEventListener("lixity:workbench-change", function() { ++workspaceNavigationRevision; });
function switchActiveView(viewName, restorePosition, preserveHash) {
  if (!viewName) return;
  if (window.LixitySite.readOnly && (viewName === "project" || (viewName === "research" && !researchContextToken()))) return;
  var tabs = document.querySelectorAll(".view-nav-tab");
  var panes = document.querySelectorAll(".view-pane");
  if (!panes.length || !Array.from(panes).some(function(pane) { return pane.dataset.viewPane === viewName; })) return;
  var previous = document.querySelector(".view-pane.active");
  if (!preserveHash && (restorePosition || (previous && previous.dataset.viewPane !== viewName))) {
    // Explicit workspace intent supersedes fragment events already queued by
    // an earlier passage jump, without adding a browser-history entry.
    try { history.replaceState(null, "", location.pathname + location.search + "#view-" + viewName); }
    catch (_) { /* The workspace remains usable without URL persistence. */ }
  }
  if (window.LixityWorkbench) window.LixityWorkbench.dispatch({type: "view", value: viewName});
  if (previous && previous.dataset.viewPane !== viewName) {
    workspaceScrollPositions[previous.dataset.viewPane] = window.scrollY;
  }
  tabs.forEach(function(tab) {
    var isActive = tab.dataset.view === viewName;
    tab.classList.toggle("active", isActive);
    tab.setAttribute("aria-selected", isActive ? "true" : "false");
  });
  panes.forEach(function(pane) {
    var isPaneActive = pane.dataset.viewPane === viewName;
    pane.classList.toggle("active", isPaneActive);
  });
  try {
    localStorage.setItem("lixity_active_view", viewName);
  } catch (e) {}
  if (viewName === "analysis") {
    window.dispatchEvent(new Event("resize"));
  }
  document.dispatchEvent(new Event("lixity:viewchange"));
  // Explicit workspace navigation resumes its own reading position. Hash and
  // evidence jumps keep control of their more specific destination.
  if (restorePosition && previous && previous.dataset.viewPane !== viewName) {
    window.scrollTo({top: workspaceScrollPositions[viewName] || 0, behavior: "instant"});
  }
  if (previous && previous.dataset.viewPane !== viewName && window.LixityMotion) {
    window.LixityMotion.view(document.querySelector('.view-pane.active'));
  }
}

function checkUrlHashView(event) {
  if (event && event.newURL !== window.location.href) return;
  var hash = window.location.hash;
  if (!hash) return;
  if (hash.startsWith("#view-")) {
    var v = hash.replace("#view-", "");
    if (["research", "analysis", "project"].includes(v)) {
      switchActiveView(v, false, true);
      return;
    }
  }
  var target = document.querySelector(hash);
  if (!target) return;
  revealStyleTarget(target);
  if (target.classList.contains("ptext")) {
    var chip = document.querySelector('.chip[data-target="' + target.id + '"]');
    if (chip) toggleParagraph(chip, true, true);
  }
  var parentPane = target.closest(".view-pane");
  if (parentPane && parentPane.dataset.viewPane) {
    switchActiveView(parentPane.dataset.viewPane, false, true);
    var revision = workspaceNavigationRevision;
    requestAnimationFrame(function () {
      if (window.location.hash === hash && workspaceNavigationRevision === revision) scrollAndFlash(target);
    });
  }
}

document.addEventListener("click", function(event) {
  var viewTab = event.target.closest(".view-nav-tab[data-view]");
  if (viewTab) {
    switchActiveView(viewTab.dataset.view, true);
    return;
  }
  var switchBtn = event.target.closest("[data-switch-view]");
  if (switchBtn) {
    switchActiveView(switchBtn.dataset.switchView);
    return;
  }
});

window.addEventListener("hashchange", checkUrlHashView);

if (window.location.hash) {
  checkUrlHashView();
} else {
  try {
    var savedView = localStorage.getItem("lixity_active_view");
    if (savedView && document.querySelector('.view-pane[data-view-pane="' + savedView + '"]')) {
      switchActiveView(savedView);
    }
  } catch (e) {}
}
function researchErrorMessage(result, fallback) {
  var text = (result && result.message) || fallback;
  if (text === "Research project not initialized") return uiLabel("research_not_initialized");
  return text;
}
window.LixityWorkspaceReader = {
  label: uiLabel, read: researchApiGet, switchView: switchActiveView,
  errorText: researchErrorMessage,
  contextToken: researchContextToken, enhanceDossier: enhanceResearchDossierClaims,
  renderDossier: function(detail) { return researchDossierDetailHtml(detail, true); }
};
(function () {
  var navigation = document.querySelector(".view-navigation");
  if (!navigation) return;
  var desktop = window.matchMedia("(min-width: 1100px)");
  function orientation() { navigation.setAttribute("aria-orientation", desktop.matches ? "vertical" : "horizontal"); }
  orientation();
  desktop.addEventListener("change", orientation);
  initKeyboardTabs(navigation, window.LixitySite.readOnly ? "[data-view]:not([data-requires-write]):not([data-requires-live])" : "[data-view]", false);
})();
initKeyboardTabs(document.getElementById("research-tabs"), window.LixitySite.readOnly ? "[data-rtab]:not([data-requires-live])" : "[data-rtab]", true);
document.querySelectorAll(".modal-tabs").forEach(function(container) {
  initKeyboardTabs(container, window.LixitySite.readOnly ? '[role="tab"]:not([data-requires-write])' : '[role="tab"]', container.closest("#modal-research-revision") !== null);
});

window.LixityManuscriptLinks = {
  label: uiLabel, countFormat: uiCountFormat, read: researchApiGet, post: researchApiPost,
  contextToken: researchContextToken,
  errorText: researchErrorMessage,
  text: function(panel) { return paragraphContent[panel.id] && paragraphContent[panel.id][0]; },
  navigate: function(panel) {
    switchActiveView("analysis");
    setPassageScrollMargin(panel);
    var action = document.createElement("button");
    action.dataset.reviewPassage = "";
    action.dataset.line = panel.dataset.start;
    action.dataset.target = panel.id;
    activate(action);
  },
  marks: function(panel, spans) {
    var previous = manuscriptParagraphMarks[panel.id] || [];
    var unchanged = previous.length === spans.length && previous.every(function(span, index) {
      return span.start === spans[index].start && span.end === spans[index].end;
    });
    manuscriptParagraphMarks[panel.id] = spans;
    if (unchanged) return;
    var paragraph = panel.querySelector(".ptext-inner > p");
    if (paragraph) renderParagraphText(paragraph, paragraph.dataset.searchQuery || "");
  }
};


// Analysis uses the same active-section presentation as accepted dossier renders.
(function initAnalysisSections() {
  if (!window.LixitySectionNavigation) return;
  var host = document.getElementById("view-pane-analysis") || document.body;
  var topNav = document.getElementById("analysis-sections");
  if (topNav) window.LixitySectionNavigation.mount(topNav, {host: host, horizontal: true});
  var outlineNav = document.getElementById("analysis-outline-nav");
  if (outlineNav) window.LixitySectionNavigation.mount(outlineNav, {host: host, horizontal: false});
})();

// Share the desktop navigation toggle with companion reading. A temporary
// companion override never overwrites the user's standalone navigation choice.
(function () {
  var toggle = document.getElementById("workspace-navigation-toggle");
  var content = document.getElementById("workspace-navigation-content");
  if (!toggle || !content) return;
  var destinations = content.parentElement.querySelector(".view-navigation");
  var desktop = window.matchMedia("(min-width: 1100px)");
  var manualCollapsed = false, companionOpen = false, companionOverride = null;
  var toggleFocused = false;
  document.addEventListener("focusin", function(event) { toggleFocused = event.target === toggle; });
  document.body.classList.add("has-workspace-navigation");
  toggle.setAttribute("aria-controls", content.id);
  function companionActive() {
    var analysis = document.getElementById("view-pane-analysis");
    return companionOpen && analysis && analysis.classList.contains("active");
  }
  function update() {
    var collapsed = desktop.matches && (companionActive()
      ? (companionOverride === null ? true : companionOverride) : manualCollapsed);
    if (collapsed && content.contains(document.activeElement)) toggle.focus({preventScroll: true});
    content.hidden = collapsed;
    document.body.classList.toggle("navigation-collapsed", collapsed);
    toggle.setAttribute("aria-expanded", String(!collapsed));
    var text = uiLabel(collapsed ? "navigation_expand" : "navigation_collapse");
    toggle.setAttribute("aria-label", text); toggle.title = text;
    // A CSS breakpoint may blur the disappearing control before matchMedia's
    // change callback runs. Retain its last explicit focus until another target.
    if (!desktop.matches && toggleFocused) {
      var selected = destinations && destinations.querySelector('[data-view][aria-selected="true"]');
      if (selected) selected.focus({preventScroll: true});
    }
    window.dispatchEvent(new Event("resize"));
  }
  toggle.addEventListener("click", function() {
    var next = !document.body.classList.contains("navigation-collapsed");
    if (companionActive()) companionOverride = next;
    else manualCollapsed = next;
    update();
  });
  desktop.addEventListener("change", update);
  document.addEventListener("lixity:viewchange", update);
  window.LixityWorkspaceNavigation = {
    companion: function(open) {
      if (companionOpen !== open) companionOverride = null;
      companionOpen = open;
      update();
    }
  };
  update();
})();

// One native operational view; project content stays in its own scoped routes.
(function() {
  var open = document.getElementById("runtime-open"), modal = document.getElementById("modal-runtime");
  if (!open || !modal || !API) return;
  var content = document.getElementById("runtime-content"), status = document.getElementById("runtime-status"), revision = 0;
  function heading(key) {var node = document.createElement("h4"); node.textContent = uiLabel(key); content.appendChild(node);}
  async function refresh() {
    var serial = ++revision; status.textContent = "…";
    try {
      var response = await fetch(API + "/runtime"), data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.message || uiLabel("runtime_unavailable"));
      if (serial !== revision || !modal.open) return;
      content.replaceChildren(); status.textContent = uiLabel("runtime_ready");
      var modelTitle = document.createElement("h4"); modelTitle.textContent = "Qwen3-TTS"; content.appendChild(modelTitle);
      var targets = document.createElement("dl");
      data.audio.targets.forEach(function(target) {
        var title = document.createElement("dt"), value = document.createElement("dd");
        title.textContent = uiLabel("speech_target_" + target.target);
        value.textContent = uiLabel("runtime_" + target.state); targets.append(title, value);
      }); content.appendChild(targets);
      heading("runtime_jobs");
      var jobs = document.createElement("ul");
      data.audio.jobs.forEach(function(job) {
        var item = document.createElement("li");
        item.textContent = uiLabel("speech_target_" + job.target) + " · " +
          (job.state === "pending" ? uiFormat("runtime_queued", {position: job.queue_position}) :
           uiLabel("speech_state_" + ({ready:"completed", error:"failed", stale:"failed"}[job.state] || job.state)));
        jobs.appendChild(item);
      });
      if (!jobs.children.length) {var empty = document.createElement("li"); empty.textContent = uiLabel("runtime_empty"); jobs.appendChild(empty);}
      content.appendChild(jobs); heading("runtime_workspaces");
      var projects = document.createElement("ul");
      data.workspaces.forEach(function(project) {
        if (!/^\/w\/[a-f0-9]{32}\/$/.test(project.url)) return;
        var item = document.createElement("li"), link = document.createElement("a");
        link.href = project.url; link.textContent = project.title;
        if (location.pathname === project.url) link.setAttribute("aria-current", "page");
        var controls = document.createElement("div"); controls.className = "row"; controls.appendChild(link); item.appendChild(controls);
        if (project.closable) {
          var close = document.createElement("button"); close.type = "button"; close.className = "ctl";
          close.textContent = uiLabel("modal_close"); close.setAttribute("aria-label", close.textContent + " · " + project.title);
          close.addEventListener("click", async function() {
            close.disabled = true;
            try {
              var result = await fetch(API + "/workspace-close", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({id:project.id})});
              var value = await result.json(); if (!result.ok || !value.ok) throw new Error(value.message);
              if (location.pathname === project.url) location.assign("/"); else refresh();
            } catch (error) {status.textContent = error.message; close.disabled = false;}
          }); controls.appendChild(close);
        }
        projects.appendChild(item);
      }); content.appendChild(projects);
    } catch (error) {if (serial === revision && modal.open) status.textContent = error.message;}
  }
  open.addEventListener("click", function() {modal.showModal(); refresh();});
  document.getElementById("runtime-refresh").addEventListener("click", refresh);
  modal.addEventListener("close", function() {revision++;});
})();
