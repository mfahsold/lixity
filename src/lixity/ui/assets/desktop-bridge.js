/** Native desktop bridge: OS menu dispatch, Open-with forwarding, system status and Rust audio takes. */
(function () {
  "use strict";

  function label(key, fallback) {
    if (typeof window.uiLabel === "function") {
      var resolved = window.uiLabel(key);
      if (resolved && resolved !== key) return resolved;
    }
    return fallback || key;
  }

  function escapeHtml(value) {
    if (window.LixityComponents && typeof window.LixityComponents.escapeHtml === "function") {
      return window.LixityComponents.escapeHtml(value);
    }
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function apiBase() {
    return (document.body && document.body.dataset && document.body.dataset.api) || "/api";
  }

  var statusDialog = null;
  var statusBody = null;
  var updateStatusEl = null;
  var updateButton = null;
  var checkingForUpdates = false;

  function ensureSystemStatusDialog() {
    if (statusDialog && document.body.contains(statusDialog)) return statusDialog;
    var dialog = document.createElement("dialog");
    dialog.id = "modal-desktop-environment";
    dialog.className = "lixity-modal";
    dialog.setAttribute("closedby", "any");
    dialog.setAttribute("aria-labelledby", "desktop-env-heading");
    dialog.innerHTML =
      '<div class="modal-card">' +
      '  <div class="modal-header">' +
      '    <h2 id="desktop-env-heading">' + escapeHtml(label("desktop_env_title", "System Status & Optional Extensions")) + "</h2>" +
      '    <button type="button" class="modal-close" data-close-desktop-env aria-label="' + escapeHtml(label("close", "Close")) + '">✕</button>' +
      "  </div>" +
      '  <div class="modal-body"><div data-desktop-env-body></div>' +
      '    <div data-desktop-update-status role="status"></div></div>' +
      '  <div class="modal-footer" data-desktop-env-footer></div>' +
      "</div>";
    dialog.addEventListener("click", function (event) {
      if (event.target.closest("[data-close-desktop-env]")) dialog.close();
    });
    document.body.appendChild(dialog);
    statusDialog = dialog;
    statusBody = dialog.querySelector("[data-desktop-env-body]");
    updateStatusEl = dialog.querySelector("[data-desktop-update-status]");
    var footer = dialog.querySelector("[data-desktop-env-footer]");
    if (window.lixityDesktop && typeof window.lixityDesktop.checkForUpdates === "function") {
      updateButton = document.createElement("button");
      updateButton.type = "button";
      updateButton.className = "ctl";
      updateButton.textContent = label("desktop_env_check_updates", "Check for Updates…");
      updateButton.addEventListener("click", checkForUpdates);
      footer.appendChild(updateButton);
    }
    if (window.lixityDesktop && typeof window.lixityDesktop.openLogsFolder === "function") {
      var logs = document.createElement("button");
      logs.type = "button";
      logs.className = "ctl";
      logs.textContent = label("desktop_env_open_logs", "Open Logs Folder");
      logs.addEventListener("click", function () {
        window.lixityDesktop.openLogsFolder().catch(function () {});
      });
      footer.appendChild(logs);
    }
    var close = document.createElement("button");
    close.type = "button";
    close.className = "ctl primary";
    close.textContent = label("close", "Close");
    close.addEventListener("click", function () { dialog.close(); });
    footer.appendChild(close);
    return dialog;
  }

  function statusBadge(available) {
    var cls = available ? "ok" : "warn";
    var text = available
      ? label("desktop_env_available", "Available")
      : label("desktop_env_optional_missing", "Optional / not configured");
    return '<span class="ctl-status ' + cls + '">' + escapeHtml(text) + "</span>";
  }

  async function renderSystemStatus(bodyEl) {
    bodyEl.innerHTML = '<p class="ctl-status loading">' + escapeHtml(label("desktop_env_loading", "Checking local environment…")) + "</p>";

    var desktop = window.lixityDesktop;
    var failure = label("desktop_env_error", "Could not inspect environment");
    var res;
    try {
      if (typeof desktop?.getRuntimeEnvironment === "function") {
        res = await desktop.getRuntimeEnvironment();
      } else {
        var response = await fetch(apiBase() + "/desktop/environment?probe_zotero=1");
        res = await response.json();
      }
    } catch (_) {
      bodyEl.innerHTML = '<p class="ctl-status err">' + escapeHtml(failure) + "</p>";
      return;
    }
    if (!res || !res.ok) {
      bodyEl.innerHTML = '<p class="ctl-status err">' + escapeHtml((res && res.message) || failure) + "</p>";
      return;
    }

    var app = res.app || {};
    var revision = desktop && desktop.appRevision;
    var buildStatus = typeof revision === "string" && /^[a-f0-9]{40}$/i.test(revision)
      ? " · " + escapeHtml(label("desktop_env_build", "Build")) + ' <code title="' +
        escapeHtml(revision) + '">' + escapeHtml(revision.slice(0, 8)) + "</code>"
      : "";
    var tools = res.tools || {};
    var zoteroAvailable = Boolean(res.zotero && (res.zotero.available || res.zotero.reachable));
    var workers = Array.isArray(res.audio_workers) ? res.audio_workers : [];
    var rows = [
      ["Poppler (PDF)", Boolean(tools.pdftotext && tools.pdftoppm)],
      ["Tesseract (OCR)", Boolean(tools.tesseract)],
      ["FFmpeg (Audio)", Boolean(tools.ffmpeg)],
      ["Zotero Local Bridge", zoteroAvailable],
      ["spaCy (Grammatical Tense)", Boolean(tools.spacy)],
      ["Stanza (Grammatical Tense)", Boolean(tools.stanza)]
    ];

    var listHtml = rows.map(function (entry) {
      return '<li><strong>' + escapeHtml(entry[0]) + "</strong>: " + statusBadge(entry[1]) + "</li>";
    }).join("");

    var workerHtml = workers.length
      ? "<p class=\"ctl-note\">" + escapeHtml(label("desktop_env_audio_workers", "Local audio workers")) + ": " +
        workers.map(function (w) { return escapeHtml((w.engine || w.id || "worker") + " (" + (w.state || "unknown") + ")"); }).join(", ") +
        "</p>"
      : "";

    bodyEl.innerHTML =
      '<p class="ctl-note">Lixity <strong>v' + escapeHtml(app.version || "") + "</strong>" + buildStatus + " · Python " +
      escapeHtml(app.python || "") + " · " + escapeHtml((app.platform || "") + " / " + (app.machine || "")) +
      (app.desktop_mode ? " · Desktop" : " · Local Browser") + "</p>" +
      '<p class="ctl-note">' + escapeHtml(label("desktop_env_note", "Core manuscript analysis runs offline without optional extensions. External tools stay separate from the core app.")) + "</p>" +
      '<ul class="desktop-env-list">' + listHtml + "</ul>" + workerHtml;
  }

  async function openSystemStatus() {
    var dialog = ensureSystemStatusDialog();
    if (typeof dialog.showModal === "function" && !dialog.open) dialog.showModal();
    await renderSystemStatus(statusBody);
  }

  async function checkForUpdates() {
    if (checkingForUpdates) return;
    if (!ensureSystemStatusDialog().open) void openSystemStatus();
    var statusEl = updateStatusEl;
    var desktop = window.lixityDesktop;
    if (typeof desktop?.checkForUpdates !== "function") {
      statusEl.innerHTML = '<p class="ctl-note">' + escapeHtml(label("desktop_env_updates_desktop_only", "Release checks are available in the Lixity Desktop app.")) + "</p>";
      return;
    }
    checkingForUpdates = true;
    window.LixityComponents.setButtonPending(updateButton, true);
    statusEl.innerHTML = '<p class="ctl-status loading">' + escapeHtml(label("desktop_env_checking_updates", "Checking desktop downloads…")) + "</p>";
    var failure = label("desktop_env_update_failed", "Could not check desktop downloads. Try again later.");
    try {
      var result = await desktop.checkForUpdates();
      var messages = {
        no_public_installer: label("desktop_env_no_public_installer", "Desktop installers are not publicly available yet."),
        no_matching_installer: label("desktop_env_no_matching_installer", "There is no published desktop installer for this system."),
        current: label("desktop_env_up_to_date", "The installed desktop version is current."),
        available: label("desktop_env_update_available", "A newer desktop installer is available."),
        installed_ahead: label("desktop_env_installed_ahead", "This installation is newer than the public desktop package.")
      };
      if (!Object.hasOwn(messages, result.status)) throw new Error("Unknown desktop update result");
      var versions = label("desktop_env_installed_version", "Installed") + " " + result.current_version;
      if (result.latest_tag) versions += " · " + label("desktop_env_published_version", "Published") + " " + result.latest_tag;
      statusEl.innerHTML = '<p class="ctl-status ' + (result.status === "current" ? "ok" : "") + '">' +
        escapeHtml(messages[result.status]) + '</p><p class="ctl-note">' + escapeHtml(versions) + "</p>";
      if (result.status === "available" && result.guide_url && desktop.openExternalUrl) {
        var linkBtn = document.createElement("button");
        linkBtn.type = "button";
        linkBtn.className = "ctl ctl-sm";
        linkBtn.textContent = label("desktop_env_open_downloads", "Open desktop downloads");
        linkBtn.addEventListener("click", function () {
          desktop.openExternalUrl(result.guide_url).catch(function () {
            var error = document.createElement("p");
            error.className = "ctl-status err";
            error.textContent = label("desktop_env_open_downloads_failed", "Could not open desktop downloads.");
            statusEl.appendChild(error);
          });
        });
        statusEl.appendChild(linkBtn);
      }
    } catch (_) {
      statusEl.innerHTML = '<p class="ctl-status err">' + escapeHtml(failure) + "</p>";
    } finally {
      checkingForUpdates = false;
      window.LixityComponents.setButtonPending(updateButton, false);
    }
  }

  async function openPath(targetPath) {
    if (!targetPath || typeof targetPath !== "string") return;
    var response = await fetch(apiBase() + "/project-open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: targetPath })
    });
    var data = await response.json();
    if (!response.ok || !data || !data.ok) return;
    if (window.lixityDesktop && typeof window.lixityDesktop.recordRecentProject === "function") {
      window.lixityDesktop.recordRecentProject(
        data.workspace_root || targetPath,
        data.title || null,
        data.language || null
      ).catch(function () {});
    }
    if (typeof data.workspace_url === "string" && data.workspace_url) {
      if (window.lixityDesktop && typeof window.lixityDesktop.openProjectWindow === "function" &&
          document.body && document.body.dataset && document.body.dataset.manuscriptSourceSha256) {
        try {
          await window.lixityDesktop.openProjectWindow(data.workspace_url, data.title || "Lixity");
          return false;
        } catch (_) {
          // Keep the project reachable when the native window could not be created.
        }
      }
      window.location.assign(data.workspace_url);
      return true;
    }
    if (data.reload) {
      window.location.reload();
      return true;
    }
    return false;
  }

  function handleMenuAction(actionId) {
    switch (actionId) {
      case "file-open-project": {
        var openBtn = document.getElementById("btn-modal-open-project") || document.getElementById("hero-btn-open-project");
        if (openBtn) openBtn.click();
        break;
      }
      case "file-import-manuscript": {
        var impBtn = document.getElementById("btn-modal-new-project") || document.getElementById("hero-btn-new-project");
        if (impBtn) impBtn.click();
        break;
      }
      case "file-export-pdf": {
        switchActiveView("project", true);
        window.LixityComponents.openManuscriptPdf();
        break;
      }
      case "view-analysis":
        switchActiveView("analysis", true);
        break;
      case "view-analysis-overview":
        if (window.LixityReader) window.LixityReader.showOverview();
        break;
      case "view-research":
        switchActiveView("research", true);
        break;
      case "view-project":
        switchActiveView("project", true);
        break;
      case "view-teleprompter": {
        var tpBtn = document.getElementById("reader-teleprompter");
        if (tpBtn) tpBtn.click();
        break;
      }
      case "view-toggle-theme":
        window.LixityComponents.toggleTheme();
        break;
      case "tools-system-status":
        openSystemStatus();
        break;
      case "help-check-updates":
        checkForUpdates();
        break;
      default:
        break;
    }
  }

  var savedToastEl = null;
  var savedToastTimer = null;

  function notifySavedExport(outcome) {
    if (!outcome || !outcome.saved || !outcome.path || !outcome.filename || !window.lixityDesktop ||
        typeof window.lixityDesktop.revealInFileManager !== "function") return;
    if (savedToastTimer) {
      clearTimeout(savedToastTimer);
      savedToastTimer = null;
    }
    if (!savedToastEl || !document.body.contains(savedToastEl)) {
      savedToastEl = document.createElement("div");
      savedToastEl.className = "action-toast desktop-save-toast";
    }
    // Controls outside a modal dialog are inert. Keep the feedback in the
    // same interaction surface as the export that triggered it.
    var surface = document.querySelector("dialog:modal") || document.body;
    if (savedToastEl.parentElement !== surface) surface.appendChild(savedToastEl);
    var text = document.createElement("span");
    text.className = "action-toast-message";
    text.setAttribute("role", "status");
    var actions = document.createElement("div");
    actions.className = "action-toast-actions";
    var revealBtn = document.createElement("button");
    revealBtn.type = "button";
    revealBtn.className = "ctl ctl-sm";
    revealBtn.textContent = label("desktop_export_reveal", "Show in folder");
    revealBtn.addEventListener("click", function () {
      window.lixityDesktop.revealInFileManager(outcome.path).catch(function () {});
    });
    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "ctl ctl-sm";
    closeBtn.textContent = "✕";
    closeBtn.setAttribute("aria-label", label("close", "Close"));
    closeBtn.addEventListener("click", function () {
      if (savedToastEl) savedToastEl.hidden = true;
    });
    actions.append(revealBtn, closeBtn);
    savedToastEl.replaceChildren(text, actions);
    savedToastEl.hidden = false;
    text.textContent = window.LixityComponents.uiFormat("desktop_export_saved", {filename: outcome.filename});
    savedToastTimer = setTimeout(function () {
      if (savedToastEl) savedToastEl.hidden = true;
    }, 9000);
  }

  function initDesktopEnhancements() {
    if (!window.lixityDesktop || !(window.lixityDesktop.version >= 1)) return;
    document.documentElement.classList.add("lixity-desktop");
    if (window.lixityDesktop.platform) {
      document.documentElement.dataset.desktopPlatform = String(window.lixityDesktop.platform);
    }
    var projectTitle = document.querySelector(".workspace-shell .project-header h1");
    if (projectTitle && typeof window.lixityDesktop.setWorkspaceTitle === "function") {
      window.lixityDesktop.setWorkspaceTitle(projectTitle.textContent.trim()).catch(function () {});
    }

    var root = document.documentElement;
    var initialTheme = root.dataset.theme;
    var lastTheme = initialTheme;
    window.addEventListener("lixity:desktop-theme", function (event) {
      var theme = event.detail;
      if (theme === "dark" || theme === "light") {
        lastTheme = theme;
        window.LixityComponents.applyTheme(theme);
      } else if (theme === null) {
        lastTheme = undefined;
        delete root.dataset.theme;
        try { localStorage.removeItem("lixity-theme"); } catch (_) { /* Keep the OS theme. */ }
      }
    });
    // Read portable desktop settings once. Rust also applies native zoom.
    var settings = typeof window.lixityDesktop.getPreferences === "function" ?
      window.lixityDesktop.getPreferences() : Promise.resolve(null);
    settings.then(function (prefs) {
      if (prefs && root.dataset.theme === initialTheme && (prefs.theme === "dark" || prefs.theme === "light")) {
        lastTheme = prefs.theme;
        window.LixityComponents.applyTheme(prefs.theme);
      }
    }).catch(function () {});

    if (typeof window.lixityDesktop.setPreference === "function") {
      window.LixityReader?.connectDesktopPreferences?.(
        settings.then(function (prefs) { return prefs?.reader; }),
        function (changes) { window.lixityDesktop.setPreference("reader", changes).catch(function () {}); }
      );
      new MutationObserver(function () {
        var nextTheme = root.dataset.theme;
        if ((nextTheme === "dark" || nextTheme === "light") && nextTheme !== lastTheme) {
          lastTheme = nextTheme;
          window.lixityDesktop.setPreference("theme", nextTheme).catch(function () {});
        }
      }).observe(root, {attributes: true, attributeFilter: ["data-theme"]});
    }
  }

  initDesktopEnhancements();

  function decodeBase64Wav(raw) {
    var binary = atob(raw.wav_base64);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return new Blob([bytes], { type: "audio/wav" });
  }

  async function recordWavTake(deviceName, durationSeconds, filename) {
    if (!window.lixityDesktop || !window.lixityDesktop.audioCapture ||
        typeof window.lixityDesktop.audioCapture.recordTake !== "function") {
      throw new Error("Desktop native audio capture unavailable");
    }
    var raw = await window.lixityDesktop.audioCapture.recordTake(deviceName || null, durationSeconds || 10.0, filename || "recording.wav");
    var blob = decodeBase64Wav(raw);
    if (window.LixityAudioTake && typeof window.LixityAudioTake.create === "function") {
      return window.LixityAudioTake.create(blob, { filename: raw.filename || "recording.wav" });
    }
    return { blob: blob, metadata: raw };
  }

  window.addEventListener("lixity:desktop-menu", function (event) {
    if (event && typeof event.detail === "string") handleMenuAction(event.detail);
  });

  var openPathsRequested = false;
  var drainingOpenPaths = false;
  var leavingForProject = false;

  async function openPendingPaths() {
    var bridge = window.lixityDesktop;
    if (!bridge || typeof bridge.takeOpenPath !== "function" || leavingForProject) return;
    openPathsRequested = true;
    if (drainingOpenPaths) return;

    drainingOpenPaths = true;
    try {
      while (openPathsRequested && !leavingForProject) {
        openPathsRequested = false;
        var path = await bridge.takeOpenPath();
        if (path) {
          openPathsRequested = true;
          leavingForProject = await openPath(path).catch(function () { return false; });
        }
      }
    } finally {
      drainingOpenPaths = false;
    }
  }

  window.addEventListener("lixity:desktop-open-path", function (event) {
    if (event && typeof event.detail === "string") {
      openPath(event.detail).catch(function () {});
    } else {
      openPendingPaths().catch(function () {});
    }
  });

  window.LixityDesktopBridge = Object.freeze({
    openSystemStatus: openSystemStatus,
    checkForUpdates: checkForUpdates,
    openPath: openPath,
    handleMenuAction: handleMenuAction,
    notifySavedExport: notifySavedExport,
    decodeBase64Wav: decodeBase64Wav,
    recordWavTake: recordWavTake
  });

  // Carry requests received before this document was able to listen, including cold OS launches.
  openPendingPaths().catch(function () {});
})();
