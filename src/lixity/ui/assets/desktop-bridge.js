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

  function clickViewTab(viewName) {
    var tab = document.querySelector('.view-nav-tab[data-view-tab="' + viewName + '"]');
    if (tab) tab.click();
  }

  var statusDialog = null;
  var statusBody = null;
  var statusFooter = null;
  var updateStatusEl = null;

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
      '  <div class="modal-body" data-desktop-env-body></div>' +
      '  <div class="modal-footer" data-desktop-env-footer></div>' +
      "</div>";
    dialog.addEventListener("click", function (event) {
      if (event.target.closest("[data-close-desktop-env]")) dialog.close();
    });
    document.body.appendChild(dialog);
    statusDialog = dialog;
    statusBody = dialog.querySelector("[data-desktop-env-body]");
    statusFooter = dialog.querySelector("[data-desktop-env-footer]");
    return dialog;
  }

  function statusBadge(available) {
    var cls = available ? "ok" : "warn";
    var text = available
      ? label("desktop_env_available", "Available")
      : label("desktop_env_optional_missing", "Optional / not configured");
    return '<span class="ctl-status ' + cls + '">' + escapeHtml(text) + "</span>";
  }

  async function renderSystemStatus(bodyEl, footerEl) {
    bodyEl.innerHTML = '<p class="ctl-status loading">' + escapeHtml(label("desktop_env_loading", "Checking local environment…")) + "</p>";
    footerEl.innerHTML = "";
    updateStatusEl = null;

    var res;
    try {
      var response = await fetch(apiBase() + "/desktop/environment?probe_zotero=1");
      res = await response.json();
    } catch (error) {
      bodyEl.innerHTML = '<p class="ctl-status err">' + escapeHtml(String(error)) + "</p>";
      return;
    }
    if (!res || !res.ok) {
      bodyEl.innerHTML = '<p class="ctl-status err">' + escapeHtml((res && res.message) || label("desktop_env_error", "Could not inspect environment")) + "</p>";
      return;
    }

    var app = res.app || {};
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
      '<p class="ctl-note">Lixity <strong>v' + escapeHtml(app.version || "") + "</strong> · Python " +
      escapeHtml(app.python || "") + " · " + escapeHtml((app.platform || "") + " / " + (app.machine || "")) +
      (app.desktop_mode ? " · Desktop" : " · Local Browser") + "</p>" +
      '<p class="ctl-note">' + escapeHtml(label("desktop_env_note", "Core manuscript analysis runs offline without optional extensions. External tools stay separate from the core app.")) + "</p>" +
      '<ul class="desktop-env-list">' + listHtml + "</ul>" +
      workerHtml +
      '<div data-desktop-update-status role="status" aria-live="polite"></div>';
    updateStatusEl = bodyEl.querySelector("[data-desktop-update-status]");

    if (window.lixityDesktop && typeof window.lixityDesktop.checkForUpdates === "function") {
      var updBtn = document.createElement("button");
      updBtn.type = "button";
      updBtn.className = "ctl";
      updBtn.textContent = label("desktop_env_check_updates", "Check for Updates…");
      updBtn.addEventListener("click", function () { checkForUpdates(); });
      footerEl.appendChild(updBtn);
    }
    if (window.lixityDesktop && typeof window.lixityDesktop.openLogsFolder === "function") {
      var logBtn = document.createElement("button");
      logBtn.type = "button";
      logBtn.className = "ctl";
      logBtn.textContent = label("desktop_env_open_logs", "Open Logs Folder");
      logBtn.addEventListener("click", function () {
        window.lixityDesktop.openLogsFolder().catch(function () {});
      });
      footerEl.appendChild(logBtn);
    }
    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "ctl primary";
    closeBtn.textContent = label("close", "Close");
    closeBtn.addEventListener("click", function () {
      if (statusDialog) statusDialog.close();
    });
    footerEl.appendChild(closeBtn);
  }

  async function openSystemStatus() {
    var dialog = ensureSystemStatusDialog();
    if (typeof dialog.showModal === "function" && !dialog.open) dialog.showModal();
    if (statusBody && statusFooter) await renderSystemStatus(statusBody, statusFooter);
  }

  async function checkForUpdates() {
    await openSystemStatus();
    var statusEl = updateStatusEl;
    if (!statusEl) return;
    if (!window.lixityDesktop || typeof window.lixityDesktop.checkForUpdates !== "function") {
      statusEl.innerHTML = '<p class="ctl-note">' + escapeHtml(label("desktop_env_updates_desktop_only", "Release checks are available in the Lixity Desktop app.")) + "</p>";
      return;
    }
    statusEl.innerHTML = '<p class="ctl-status loading">' + escapeHtml(label("desktop_env_checking_updates", "Checking GitHub Releases…")) + "</p>";
    try {
      var result = await window.lixityDesktop.checkForUpdates();
      var summary = result.update_available
        ? label("desktop_env_update_available", "Newer release available") + ": " + result.latest_tag
        : label("desktop_env_up_to_date", "Up to date") + " (" + result.latest_tag + ")";
      statusEl.innerHTML =
        '<p class="ctl-status ' + (result.update_available ? "warn" : "ok") + '">' + escapeHtml(summary) + "</p>" +
        '<p class="ctl-note">' + escapeHtml(result.note || "") + "</p>";
      if (result.release_url && window.lixityDesktop.openExternalUrl) {
        var linkBtn = document.createElement("button");
        linkBtn.type = "button";
        linkBtn.className = "ctl ctl-sm";
        linkBtn.textContent = label("desktop_env_open_release", "Open release notes");
        linkBtn.addEventListener("click", function () {
          window.lixityDesktop.openExternalUrl(result.release_url).catch(function () {});
        });
        statusEl.appendChild(linkBtn);
      }
    } catch (error) {
      statusEl.innerHTML = '<p class="ctl-status err">' + escapeHtml(String(error)) + "</p>";
    }
  }

  async function openPath(targetPath) {
    if (!targetPath || typeof targetPath !== "string") return;
    var normalized = targetPath.replace(/[\\/]+lixity\.toml$/i, "") || targetPath;
    var response = await fetch(apiBase() + "/project-open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: normalized })
    });
    var data = await response.json();
    if (!response.ok || !data || !data.ok) return;
    if (window.lixityDesktop && typeof window.lixityDesktop.recordRecentProject === "function") {
      window.lixityDesktop.recordRecentProject(
        data.workspace_root || normalized,
        data.title || null,
        data.language || null
      ).catch(function () {});
    }
    if (typeof data.workspace_url === "string" && data.workspace_url) {
      if (window.lixityDesktop && typeof window.lixityDesktop.openProjectWindow === "function" &&
          document.body && document.body.dataset && document.body.dataset.manuscriptSourceSha256) {
        window.lixityDesktop.openProjectWindow(data.workspace_url, data.title || "Lixity").catch(function () {
          window.location.assign(data.workspace_url);
        });
      } else {
        window.location.assign(data.workspace_url);
      }
      return;
    }
    if (data.reload) {
      window.location.reload();
    }
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
        clickViewTab("project");
        var pdfDetails = document.getElementById("manuscript-pdf");
        if (pdfDetails) {
          pdfDetails.open = true;
          pdfDetails.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
        break;
      }
      case "view-analysis":
        clickViewTab("analysis");
        break;
      case "view-research":
        clickViewTab("research");
        break;
      case "view-project":
        clickViewTab("project");
        break;
      case "view-teleprompter": {
        var tpBtn = document.getElementById("reader-teleprompter");
        if (tpBtn) tpBtn.click();
        break;
      }
      case "view-zoom-in":
        adjustZoom(0.1);
        break;
      case "view-zoom-out":
        adjustZoom(-0.1);
        break;
      case "view-zoom-reset":
        setZoom(1.0);
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

  var currentZoom = 1.0;
  var savedToastEl = null;
  var savedToastTimer = null;

  function applyZoom(factor) {
    var clamped = Math.round(Math.max(0.8, Math.min(1.6, Number(factor) || 1.0)) * 100) / 100;
    currentZoom = clamped;
    document.documentElement.style.zoom = clamped === 1.0 ? "" : String(clamped);
    return clamped;
  }

  function setZoom(factor) {
    var clamped = applyZoom(factor);
    if (window.lixityDesktop && typeof window.lixityDesktop.setPreference === "function") {
      window.lixityDesktop.setPreference("zoom", clamped).catch(function () {});
    }
  }

  function adjustZoom(delta) {
    setZoom(currentZoom + delta);
  }

  function notifySavedExport(outcome) {
    if (!outcome || !outcome.saved || !outcome.path || !window.lixityDesktop ||
        typeof window.lixityDesktop.revealInFileManager !== "function") return;
    if (savedToastTimer) {
      clearTimeout(savedToastTimer);
      savedToastTimer = null;
    }
    if (!savedToastEl || !document.body.contains(savedToastEl)) {
      savedToastEl = document.createElement("div");
      savedToastEl.className = "desktop-save-toast";
      savedToastEl.setAttribute("role", "status");
      savedToastEl.setAttribute("aria-live", "polite");
      savedToastEl.style.cssText =
        "position:fixed;right:1rem;bottom:1rem;z-index:9500;display:flex;align-items:center;gap:0.6rem;" +
        "padding:0.65rem 0.9rem;border-radius:10px;background:var(--surface,#fff);color:var(--ink,#1f2328);" +
        "border:1px solid var(--border,#d0d7de);box-shadow:0 8px 24px rgba(0,0,0,0.18);font-size:0.875rem;";
      document.body.appendChild(savedToastEl);
    }
    var fileLabel = String(outcome.path).split(/[\\/]/).pop() || outcome.path;
    savedToastEl.replaceChildren();
    var text = document.createElement("span");
    text.textContent = "✓ " + fileLabel;
    var revealBtn = document.createElement("button");
    revealBtn.type = "button";
    revealBtn.className = "ctl ctl-sm";
    revealBtn.textContent = label("open", "Open");
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
    savedToastEl.append(text, revealBtn, closeBtn);
    savedToastEl.hidden = false;
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

    // Intercept target="_blank" external links so WKWebView / WebKitGTK route them
    // reliably to the OS default browser via the audited https/mailto allowlist.
    document.addEventListener("click", function (event) {
      var anchor = event.target && event.target.closest ? event.target.closest("a[href]") : null;
      if (!anchor) return;
      var href = anchor.getAttribute("href") || "";
      if (!/^(https:\/\/|mailto:)/i.test(href)) return;
      if (anchor.target === "_blank" || /^mailto:/i.test(href)) {
        event.preventDefault();
        if (typeof window.lixityDesktop.openExternalUrl === "function") {
          window.lixityDesktop.openExternalUrl(href).catch(function () {});
        }
      }
    });

    // Hydrate display preferences that outlive ephemeral 127.0.0.1:0 loopback ports.
    if (typeof window.lixityDesktop.getPreferences === "function") {
      window.lixityDesktop.getPreferences().then(function (prefs) {
        if (!prefs || typeof prefs !== "object") return;
        if (typeof prefs.zoom === "number") applyZoom(prefs.zoom);
        if (prefs.theme === "dark" || prefs.theme === "light") {
          document.body.classList.toggle("theme-dark", prefs.theme === "dark");
          try { localStorage.setItem("lixity-theme", prefs.theme); } catch (_) {}
        }
      }).catch(function () {});
    }

    // Persist dark/light mode changes back to the desktop preferences store.
    if (typeof MutationObserver === "function" && typeof window.lixityDesktop.setPreference === "function") {
      var lastTheme = document.body.classList.contains("theme-dark") ? "dark" : "light";
      new MutationObserver(function () {
        var nextTheme = document.body.classList.contains("theme-dark") ? "dark" : "light";
        if (nextTheme !== lastTheme) {
          lastTheme = nextTheme;
          window.lixityDesktop.setPreference("theme", nextTheme).catch(function () {});
        }
      }).observe(document.body, { attributes: true, attributeFilter: ["class"] });
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

  window.addEventListener("lixity:desktop-open-path", function (event) {
    if (event && typeof event.detail === "string") {
      openPath(event.detail).catch(function () {});
    }
  });

  window.LixityDesktopBridge = Object.freeze({
    openSystemStatus: openSystemStatus,
    checkForUpdates: checkForUpdates,
    openPath: openPath,
    handleMenuAction: handleMenuAction,
    setZoom: setZoom,
    notifySavedExport: notifySavedExport,
    decodeBase64Wav: decodeBase64Wav,
    recordWavTake: recordWavTake
  });
})();
