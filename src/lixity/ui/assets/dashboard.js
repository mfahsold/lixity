(function () {
  var isDebug = (function() {
    try {
      var saved = localStorage.getItem("lixity_debug");
      if (saved === "1") return true;
      if (saved === "0") return false;
    } catch (_) {}
    if (window.LIXITY_DEBUG) return true;
    var meta = document.querySelector('meta[name="lixity-debug"]');
    return !!(meta && meta.content === "true");
  })();

  var LixityLog = {
    isDebug: function() { return isDebug; },
    setDebug: function(enable) {
      isDebug = !!enable;
      try {
        localStorage.setItem("lixity_debug", isDebug ? "1" : "0");
      } catch (_) {}
      console.info("[Lixity] Debug logging " + (isDebug ? "enabled" : "disabled"));
    },
    debug: function() {
      if (isDebug && console.debug) {
        console.debug.apply(console, ["[Lixity:debug]"].concat(Array.prototype.slice.call(arguments)));
      }
    },
    info: function() {
      if (isDebug && console.info) {
        console.info.apply(console, ["[Lixity:info]"].concat(Array.prototype.slice.call(arguments)));
      }
    },
    warn: function() {
      if (console.warn) {
        console.warn.apply(console, ["[Lixity:warn]"].concat(Array.prototype.slice.call(arguments)));
      }
    },
    error: function() {
      if (console.error) {
        console.error.apply(console, ["[Lixity:error]"].concat(Array.prototype.slice.call(arguments)));
      }
    },
    api: function(method, url, durationMs, status, details) {
      if (!isDebug) return;
      var label = "[Lixity:api] " + method + " " + url + " -> " + status + " (" + durationMs.toFixed(1) + "ms)";
      if (status >= 400) {
        console.error(label, details !== undefined ? details : "");
      } else {
        console.debug(label, details !== undefined ? details : "");
      }
    }
  };

  window.LixityLog = LixityLog;
  window.setLixityDebug = LixityLog.setDebug;

  if (isDebug) {
    console.info("[Lixity] Debug mode active. API logs and runtime diagnostics are enabled. Use setLixityDebug(false) to disable.");
  }

  var tip = document.createElement("div");
  tip.id = "lixity-tooltip";
  tip.className = "tooltip-popup";
  tip.setAttribute("role", "tooltip");
  tip.setAttribute("aria-hidden", "true");
  document.body.appendChild(tip);
  document.body.classList.add("has-js-tooltips");

  var activeEl = null;
  var touchUntil = 0;
  var touchHelp = null;
  var hideTimer = null;

  function show(el) {
    clearTimeout(hideTimer);
    var text = el.getAttribute("data-help") || el.getAttribute("data-tip") || el.getAttribute("title");
    if (!text || !text.trim()) return;
    if (el.hasAttribute("title")) {
      el.setAttribute("data-tip", text);
      el.removeAttribute("title");
    }
    if (activeEl && activeEl !== el) hide();
    activeEl = el;
    // Keep help in the native dialog's top layer when its control is inside one.
    var host = el.closest("dialog[open]") || document.body;
    if (tip.parentElement !== host) host.appendChild(tip);
    var descriptions = (el.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
    if (descriptions.indexOf(tip.id) === -1) descriptions.push(tip.id);
    el.setAttribute("aria-describedby", descriptions.join(" "));
    tip.textContent = text;
    tip.setAttribute("aria-hidden", "false");
    tip.classList.add("visible");
    updatePos(el);
  }

  function hide() {
    clearTimeout(hideTimer);
    if (activeEl) {
      var descriptions = (activeEl.getAttribute("aria-describedby") || "").split(/\s+/).filter(function(id) { return id && id !== tip.id; });
      if (descriptions.length) activeEl.setAttribute("aria-describedby", descriptions.join(" "));
      else activeEl.removeAttribute("aria-describedby");
    }
    activeEl = null;
    tip.setAttribute("aria-hidden", "true");
    tip.classList.remove("visible");
  }

  function updatePos(el) {
    if (!el || !tip.classList.contains("visible")) return;
    var rect = el.getBoundingClientRect();
    var tipW = tip.offsetWidth;
    var tipH = tip.offsetHeight;
    var left = rect.left + (rect.width - tipW) / 2;
    left = Math.max(10, Math.min(window.innerWidth - tipW - 10, left));
    var top = rect.top - tipH - 8;
    if (top < 10) {
      top = rect.bottom + 8;
    }
    top = Math.max(10, Math.min(window.innerHeight - tipH - 10, top));
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }

  document.addEventListener("mouseover", function (e) {
    if (Date.now() < touchUntil) return;
    var el = e.target.closest("[data-help], [data-tip], [title]");
    if (el && !el.closest(".tooltip-popup")) show(el);
  }, { passive: true });

  document.addEventListener("mouseout", function (e) {
    if (Date.now() < touchUntil) return;
    var el = e.target.closest("[data-help], [data-tip]");
    if (el && !el.contains(e.relatedTarget) && !tip.contains(e.relatedTarget)) {
      hideTimer = setTimeout(hide, 160);
    }
  }, { passive: true });
  tip.addEventListener("mouseenter", function() { clearTimeout(hideTimer); });
  tip.addEventListener("mouseleave", function(e) {
    if (!activeEl || !activeEl.contains(e.relatedTarget)) hide();
  });

  document.addEventListener("focusin", function(e) {
    var el = e.target.closest("[data-help], [data-tip], [title]");
    if (el) show(el);
  });
  document.addEventListener("focusout", hide);

  document.addEventListener("pointerdown", function(e) {
    if (e.pointerType === "touch") touchUntil = Date.now() + 1000;
    var el = e.target.closest(".help[data-help]");
    if (e.pointerType === "touch" && el && !el.closest("button, a")) {
      touchHelp = el;
      var wasOpen = activeEl === el;
      e.preventDefault();
      el.focus({preventScroll: true});
      if (wasOpen) hide();
      else show(el);
    } else if (!e.target.closest("[data-help], [data-tip], [title], .tooltip-popup")) {
      hide();
    }
  });
  document.addEventListener("click", function(e) {
    if (touchHelp && Date.now() < touchUntil && touchHelp.contains(e.target)) {
      e.preventDefault();
      e.stopPropagation();
    }
    touchHelp = null;
  }, true);

  document.addEventListener("close", function(e) {
    if (activeEl && e.target.contains(activeEl)) hide();
  }, true);

  var posTicking = false;
  function scheduleUpdatePos() {
    if (!posTicking && activeEl) {
      posTicking = true;
      requestAnimationFrame(function () {
        posTicking = false;
        if (activeEl) updatePos(activeEl);
      });
    }
  }

  window.addEventListener("scroll", scheduleUpdatePos, { passive: true });
  window.addEventListener("resize", scheduleUpdatePos, { passive: true });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && activeEl) {
      e.preventDefault();
      hide();
    } else if ((e.key === "Enter" || e.key === " ") &&
        e.target.matches(".help[data-help]") && !e.target.closest("button, a")) {
      e.preventDefault();
      if (activeEl === e.target) hide();
      else show(e.target);
    }
  });
})();

function highlightCell(cell, on) {
  var table = cell.closest("table");
  if (!table) return;
  var row = cell.parentElement;
  var index = Array.prototype.indexOf.call(row.children, cell);
  row.querySelectorAll("td.z").forEach(function (td) {
    if (td === cell || index < 1) td.classList.toggle("hl", on);
  });
  if (index < 1) return;
  table.querySelectorAll("tbody tr").forEach(function (tr) {
    var td = tr.children[index];
    if (td) td.classList.toggle("hl", on);
  });
}

document.addEventListener("mouseover", function (event) {
  var cell = event.target.closest ? event.target.closest("td.z[data-chapter]") : null;
  if (cell) highlightCell(cell, true);
}, { passive: true });

document.addEventListener("mouseout", function (event) {
  var cell = event.target.closest ? event.target.closest("td.z[data-chapter]") : null;
  if (cell) highlightCell(cell, false);
}, { passive: true });

var reduceMotion = window.matchMedia
  && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function scrollAndFlash(target) {
  var view = target.closest(".view-pane");
  if (view) switchActiveView(view.dataset.viewPane);
  target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  target.classList.add("flash");
  setTimeout(function () { target.classList.remove("flash"); }, 1400);
}

function toggleParagraph(chip, forceOpen) {
  var panel = document.getElementById(chip.dataset.target);
  if (!panel) return;
  var open = forceOpen === undefined ? !panel.classList.contains("open") : forceOpen;
  panel.classList.toggle("open", open);
  chip.classList.toggle("active", open);
  chip.setAttribute("aria-expanded", open ? "true" : "false");
  if (open) {
    panel.style.borderLeftColor = chip.style.getPropertyValue("--layer-color") || "";
  }
}

function setFilter(input, bodyClass, on) {
  if (!input) return;
  input.checked = on;
  document.body.classList.toggle(bodyClass, on);
}

function activate(el) {
  // drill-down: carry the context filters on the way to the deeper level
  if (el.getAttribute("data-only") && layerOnly) setFilter(layerOnly, "layer-only", true);
  if (el.getAttribute("data-flags")) setFilter(document.getElementById("filter-flags"), "only-flags", true);
  if (el.matches("td.z[data-chapter]")) { jumpToChapter(el); return; }
  if (el.hasAttribute("data-line")) { jumpToLine(el); return; }
  var key = el.getAttribute("data-layer");
  if (key && layer) { layer.value = key; applyLayer(); }
  var jump = el.getAttribute("data-jump");
  var target = jump ? document.querySelector(jump) : null;
  if (target) scrollAndFlash(target);
}

function jumpToLine(row) {
  var line = parseInt(row.getAttribute("data-line"), 10);
  var targetId = row.getAttribute("data-target");
  var panel = targetId ? document.getElementById(targetId) : null;
  if (!panel) {
    var panels = document.querySelectorAll(".ptext[data-start]");
    for (var i = 0; i < panels.length; i++) {
      var start = parseInt(panels[i].getAttribute("data-start"), 10);
      var end = parseInt(panels[i].getAttribute("data-end"), 10);
      if (line >= start && line <= end) { panel = panels[i]; break; }
    }
  }
  if (panel) {
    var chip = document.querySelector('.chip[data-target="' + panel.id + '"]');
    if (chip) toggleParagraph(chip, true);
    scrollAndFlash(panel);
    return;
  }
  var chapters = document.querySelectorAll(".chapter[data-start]");
  for (var j = 0; j < chapters.length; j++) {
    var cstart = parseInt(chapters[j].getAttribute("data-start"), 10);
    var cend = parseInt(chapters[j].getAttribute("data-end"), 10);
    if (line >= cstart && line <= cend) { scrollAndFlash(chapters[j]); return; }
  }
}

// Marker controls (add/resolve/note) live inside jumpable rows; activating
// them must open the note field only – never also scroll the page.
function isMarkerControl(el) {
  return !!el.closest("[data-marker-kind], [data-marker-resolve], .marker-note, .marker-note-slot");
}

// Unified interaction contract: every content drill-down is a [role="button"]
// (KPI tile, band row, loading bar, table row, heatmap cell) or carries
// data-jump / data-line. Native controls use <button>/<select>.
var INTERACTIVE = "[data-jump], [data-line], [role='button'], td.z[data-chapter]";

document.addEventListener("click", function (event) {
  var chip = event.target.closest(".chip");
  if (chip) { toggleParagraph(chip); return; }
  var target = event.target.closest(INTERACTIVE);
  if (target && !target.closest(".controls") && !isMarkerControl(event.target)) {
    activate(target);
  }
});
document.addEventListener("keydown", function (event) {
  if (event.defaultPrevented) return;
  if (event.key === "Escape") {
    closeNoteField();
    document.querySelectorAll(".ptext.open").forEach(function (panel) {
      var chip = document.querySelector('.chip[data-target="' + panel.id + '"]');
      if (chip) toggleParagraph(chip, false);
      else panel.classList.remove("open");
    });
    return;
  }
  if (event.key !== "Enter" && event.key !== " ") return;
  var el = event.target.closest ? event.target.closest(INTERACTIVE) : null;
  if (el && el.tagName !== "BUTTON" && !el.closest(".controls") && !isMarkerControl(event.target)) {
    event.preventDefault();
    activate(el);
  }
});
var filter = document.getElementById("filter-flags");
if (filter) {
  filter.addEventListener("change", function () {
    document.body.classList.toggle("only-flags", filter.checked);
  });
}
var paragraphReset = document.getElementById("paragraph-filter-reset");
if (paragraphReset) paragraphReset.addEventListener("click", function() {
  setFilter(filter, "only-flags", false);
  setFilter(layerOnly, "layer-only", false);
  if (layer) { layer.value = ""; applyLayer(); }
});
var microhint = document.getElementById("microhint");
if (microhint) {
  var dismissHint = function () {
    microhint.classList.add("gone");
    document.removeEventListener("click", dismissHint);
    window.clearTimeout(hintTimer);
  };
  var hintTimer = window.setTimeout(dismissHint, 9000);
  document.addEventListener("click", dismissHint);
}

var layer = document.getElementById("style-layer");
var layerLegend = document.getElementById("layer-legend");

function chipLayers(chip) {
  if (!chip._layers) {
    var raw = chip.getAttribute("data-layers");
    try { chip._layers = raw ? JSON.parse(raw) : {}; } catch (err) { chip._layers = {}; }
  }
  return chip._layers;
}

var layerOnly = document.getElementById("layer-only");
var layerNext = document.getElementById("layer-next");
var layerCount = document.getElementById("layer-legend-count");
var outlierCursor = 0;

function outlierChips() {
  return Array.prototype.slice.call(document.querySelectorAll(".chip.outlier"));
}

function applyLayer() {
  var key = layer ? layer.value : "";
  document.body.classList.toggle("layer-on", !!key);
  document.querySelectorAll(".chip").forEach(function (chip) {
    var info = key ? chipLayers(chip)[key] : null;
    if (info) {
      chip.style.setProperty("--layer-color", info[0]);
      chip.classList.add("has-layer");
      chip.setAttribute("data-tip", info[1]);
      chip.removeAttribute("title");
      chip.classList.toggle("outlier", Math.abs(info[2]) >= 1.5);
    } else {
      chip.style.removeProperty("--layer-color");
      chip.classList.remove("has-layer");
      chip.classList.remove("outlier");
      chip.removeAttribute("data-tip");
      var base = chip.getAttribute("data-tip-base");
      if (base) chip.setAttribute("title", base);
    }
  });
  outlierCursor = 0;
  if (layerLegend) {
    layerLegend.hidden = !key;
    if (key && layer) {
      var option = layer.options[layer.selectedIndex];
      var title = document.getElementById("layer-legend-title");
      if (title) {
        title.textContent = option.textContent;
        var hint = option.getAttribute("data-hint") || "";
        if (hint) title.setAttribute("data-tip", hint);
        else title.removeAttribute("data-tip");
      }
      var low = document.getElementById("layer-scale-low");
      var high = document.getElementById("layer-scale-high");
      var range = option.getAttribute("data-range") || "";
      var parts = range.split(" – ");
      if (low) low.textContent = parts[0] || "";
      if (high) high.textContent = parts[1] || "";
      if (layerCount) {
        var n = outlierChips().length;
        var noun = n === 1
          ? layerLegend.getAttribute("data-outliers-one")
          : layerLegend.getAttribute("data-outliers");
        layerCount.textContent = n ? n + " " + (noun || "") : "";
      }
    }
  }
}

if (layerOnly) {
  layerOnly.addEventListener("change", function () {
    document.body.classList.toggle("layer-only", layerOnly.checked);
  });
}
if (layerNext) {
  layerNext.addEventListener("click", function () {
    var chips = outlierChips();
    if (!chips.length) return;
    if (outlierCursor >= chips.length) outlierCursor = 0;
    var chip = chips[outlierCursor++];
    toggleParagraph(chip, true);
    scrollAndFlash(chip);
  });
}

function jumpToChapter(cell) {
  var key = cell.getAttribute("data-layer");
  if (key && layer) {
    layer.value = key;
    applyLayer();
  }
  var section = document.getElementById("ch-" + cell.getAttribute("data-chapter"));
  if (!section) return;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  section.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  section.classList.add("flash");
  setTimeout(function () { section.classList.remove("flash"); }, 1400);
}

if (layer) {
  layer.addEventListener("change", applyLayer);
  applyLayer();
}
async function jsonApi(url, options) {
  var t0 = performance.now();
  try {
    var response = await fetch(url, options);
    var data = await response.json();
    if (!data || typeof data !== "object" || Array.isArray(data)) data = {ok: false};
    if (!response.ok) data.ok = false;
    data.http_status = response.status;
    LixityLog.api(options && options.method || "GET", url, performance.now() - t0, response.status, data);
    return data;
  } catch (error) {
    return {ok: false, message: String(error), http_status: 0};
  }
}

function markerApi(payload) {
  return jsonApi(API + "/marker-" + payload._action, {method: "POST",
    headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
}
function closeNoteField() {
  var editor = document.querySelector("[data-marker-editor]");
  if (!editor || editor.dataset.pending === "1") return;
  var trigger = editor._markerTrigger;
  editor.remove();
  if (trigger && trigger.isConnected) trigger.focus();
}

function openNoteField(button) {
  var previous = document.querySelector("[data-marker-editor]");
  if (previous) {
    var draft = previous.querySelector(".marker-note");
    if (previous.dataset.pending === "1" || draft.value || previous._markerTrigger === button) {
      if (!draft.disabled) draft.focus();
      return;
    }
    closeNoteField();
  }
  var row = button.closest(".marker-row");
  var slot = row && row.querySelector(".marker-note-slot");
  if (!slot) return;
  var editor = document.createElement("span");
  editor.dataset.markerEditor = "1";
  editor._markerTrigger = button;
  var input = document.createElement("input");
  input.className = "ctl marker-note visible";
  input.type = "text";
  input.placeholder = slot.dataset.placeholder || "";
  input.setAttribute("aria-label", input.placeholder);
  var save = document.createElement("button");
  save.type = "button";
  save.className = "ctl";
  save.dataset.markerSave = "1";
  save.textContent = uiLabel("marker_save");
  var cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "ctl";
  cancel.dataset.markerCancel = "1";
  cancel.textContent = uiLabel("modal_cancel");
  var feedback = document.createElement("span");
  feedback.className = "ctl-status";
  feedback.dataset.markerFeedback = "1";
  feedback.setAttribute("role", "status");
  feedback.setAttribute("aria-live", "polite");
  feedback.hidden = true;
  editor.append(input, save, cancel, feedback);
  slot.appendChild(editor);
  input.focus();
  async function submit() {
    if (editor.dataset.pending === "1") return;
    editor.dataset.pending = "1";
    save.disabled = input.disabled = cancel.disabled = true;
    save.setAttribute("aria-busy", "true");
    feedback.hidden = false;
    feedback.className = "ctl-status";
    feedback.textContent = uiLabel("marker_saving");
    var data = await markerApi({_action: "add", kind: button.dataset.markerKind,
      line: parseInt(button.dataset.line, 10), note: input.value.trim()});
    if (!editor.isConnected) return;
    delete editor.dataset.pending;
    save.disabled = input.disabled = cancel.disabled = false;
    save.removeAttribute("aria-busy");
    feedback.className = "ctl-status " + (data.ok ? "ok" : "err");
    feedback.textContent = data.ok ? uiLabel("marker_saved") :
      uiFormat("marker_save_failed", {reason: data.message || uiLabel("wizard_unknown_error")});
    if (data.ok) { save.disabled = true; input.disabled = true; }
    else input.focus();
  }
  save.addEventListener("click", submit);
  cancel.addEventListener("click", closeNoteField);
  input.addEventListener("keydown", function(event) {
    if (event.key === "Escape") { event.preventDefault(); closeNoteField(); }
    if (event.key === "Enter") { event.preventDefault(); submit(); }
  });
}

document.addEventListener("click", async function(event) {
  var add = event.target.closest("[data-marker-kind]");
  if (add) { openNoteField(add); return; }
  var resolve = event.target.closest("[data-marker-resolve]");
  if (!resolve || resolve.disabled) return;
  resolve.disabled = true;
  resolve.setAttribute("aria-busy", "true");
  var feedback = resolve.parentElement.querySelector("[data-marker-resolve-feedback]");
  if (!feedback) {
    feedback = document.createElement("span");
    feedback.dataset.markerResolveFeedback = "1";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    resolve.after(feedback);
  }
  feedback.textContent = uiLabel("marker_saving");
  var data = await markerApi({_action: "resolve", id: resolve.dataset.markerResolve});
  resolve.removeAttribute("aria-busy");
  resolve.disabled = Boolean(data.ok);
  feedback.className = "ctl-status " + (data.ok ? "ok" : "err");
  feedback.textContent = data.ok ? uiLabel("marker_saved") :
    uiFormat("marker_save_failed", {reason: data.message || uiLabel("wizard_unknown_error")});
});
var API = document.body.dataset.api || "";
var UI_LABELS = {};
try { UI_LABELS = JSON.parse(document.body.dataset.uiLabels || "{}"); } catch (_) { UI_LABELS = {}; }
function uiLabel(key) { return UI_LABELS[key] || key; }
function uiFormat(key, values) {
  return uiLabel(key).replace(/\{([a-z_]+)\}/g, function(match, name) {
    return Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match;
  });
}
var welcomeHero = document.getElementById("welcome-hero");
var welcomeDismiss = document.getElementById("welcome-dismiss");
var welcomeShow = document.getElementById("welcome-show");
if (welcomeHero && welcomeDismiss && welcomeShow) {
  var welcomeStorageKey = "lixity:welcome-dismissed";
  var welcomeWasDismissed = false;
  var welcomeInitiallyVisible = !welcomeHero.hidden;
  try { welcomeWasDismissed = localStorage.getItem(welcomeStorageKey) === "1"; } catch (_) { /* Storage may be unavailable. */ }
  function setWelcomeVisible(visible, focusTarget) {
    welcomeHero.hidden = !visible;
    welcomeShow.hidden = visible;
    welcomeShow.setAttribute("aria-expanded", String(visible));
    if (focusTarget) (visible ? welcomeDismiss : welcomeShow).focus();
  }
  setWelcomeVisible(welcomeInitiallyVisible && !welcomeWasDismissed, false);
  welcomeDismiss.addEventListener("click", function() {
    setWelcomeVisible(false, true);
    try { localStorage.setItem(welcomeStorageKey, "1"); } catch (_) { /* Keep this page usable without storage. */ }
  });
  welcomeShow.addEventListener("click", function() {
    setWelcomeVisible(true, true);
    try { localStorage.removeItem(welcomeStorageKey); } catch (_) { /* Keep this page usable without storage. */ }
  });
}
(function initNdaDraft() {
  var form = document.getElementById("nda-draft-form");
  if (!form) return;
  var preview = document.getElementById("nda-draft-preview");
  var previewWrap = document.getElementById("nda-preview-wrap");
  var status = document.getElementById("nda-draft-status");
  var pdfButton = document.getElementById("nda-pdf-btn");
  var textButton = document.getElementById("nda-text-btn");
  var busy = false;
  var fields = ["name", "address", "project_name", "date", "place"];
  var dateInput = form.elements.namedItem("date");
  if (dateInput && !dateInput.value) {
    var today = new Date();
    dateInput.value = today.getFullYear() + "-" + String(today.getMonth() + 1).padStart(2, "0")
      + "-" + String(today.getDate()).padStart(2, "0");
  }

  function message(key, failed) {
    status.className = "ctl-status " + (failed ? "err" : "ok");
    status.textContent = uiLabel(key);
  }
  function pending(value) {
    busy = value;
    form.setAttribute("aria-busy", String(value));
    form.querySelectorAll("input, textarea, button").forEach(function(control) { control.disabled = value; });
  }
  async function generate(format, showPreview) {
    if (busy || !form.reportValidity()) return;
    var payload = {format: format};
    fields.forEach(function(key) { payload[key] = form.elements.namedItem(key).value.trim(); });
    var missing = fields.find(function(key) { return key !== "address" && !payload[key]; });
    if (missing) {
      message("nda_draft_required", true);
      form.elements.namedItem(missing).focus();
      return;
    }
    pending(true);
    message("nda_draft_working", false);
    var reason = "";
    try {
      var response = await fetch(API + "/nda-draft", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        try {
          var errorBody = await response.json();
          if (typeof errorBody.message === "string") reason = errorBody.message;
        } catch (_) { /* Keep the localized failure message. */ }
        throw new Error("NDA draft unavailable");
      }
      var contentType = response.headers.get("Content-Type") || "";
      if (!contentType.startsWith(format === "pdf" ? "application/pdf" : "text/plain")) {
        throw new Error("NDA draft unavailable");
      }
      if (showPreview) {
        preview.textContent = await response.text();
        previewWrap.hidden = false;
        message("nda_draft_ready", false);
      } else {
        var url = URL.createObjectURL(await response.blob());
        var download = document.createElement("a");
        download.href = url;
        download.download = format === "pdf" ? "nda.pdf" : "nda.txt";
        document.body.appendChild(download);
        download.click();
        download.remove();
        setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
        message("nda_draft_downloaded", false);
      }
    } catch (_) {
      // Neither submitted personal details nor returned agreement text are logged.
      message("nda_draft_failed", true);
      if (reason) status.textContent += " " + reason;
    } finally { pending(false); }
  }
  form.addEventListener("submit", function(event) {
    event.preventDefault();
    generate("text", true);
  });
  form.addEventListener("input", function() {
    preview.textContent = "";
    previewWrap.hidden = true;
    status.textContent = "";
  });
  pdfButton.addEventListener("click", function() { generate("pdf", false); });
  textButton.addEventListener("click", function() { generate("text", false); });
  pending(false);
})();
var settingsForm = document.getElementById("settings-form");
if (settingsForm) {
  settingsForm.addEventListener("input", function() {
    settingsForm.querySelectorAll("input").forEach(function(input) { input.setCustomValidity(""); });
  });
  settingsForm.addEventListener("submit", function(event) {
    event.preventDefault();
    submitSettings();
  });
  document.getElementById("settings-reset").addEventListener("click", function() {
    settingsForm.querySelectorAll("[data-default]").forEach(function(input) {
      input.value = input.dataset.default;
      input.setCustomValidity("");
    });
    settingsForm.querySelector("details").open = true;
  });
}
var fdrFilter = document.getElementById("heatmap-fdr-only");
if (fdrFilter) {
  fdrFilter.addEventListener("change", function() {
    var visible = 0;
    document.querySelectorAll("#heatmap tbody tr[data-fdr-count]").forEach(function(row) {
      row.hidden = fdrFilter.checked && Number(row.dataset.fdrCount) === 0;
      if (!row.hidden) visible++;
    });
    document.getElementById("heatmap-empty").hidden = visible > 0;
  });
}
async function runAction(action, payload, button) {
  var status = document.getElementById("ctl-status");
  if (status) {
    status.className = "ctl-status";
    status.textContent = "…";
  }
  if (button) { button.disabled = true; button.classList.add("busy"); button.setAttribute("aria-busy", "true"); }
  var t0 = performance.now();
  var url = API + "/" + action;
  try {
    var res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {})
    });
    var data = await res.json();
    if (!res.ok) data.ok = false;
    LixityLog.api("POST", url, performance.now() - t0, res.status, data);
    if (status) {
      status.className = "ctl-status " + (data.ok ? "ok" : "err");
      status.textContent = (data.ok ? "✓ " : "✗ ") + (data.message || "");
    }
    if (data.ok && data.reload) { setTimeout(function () { location.reload(); }, 1200); }
    return data;
  } catch (err) {
    LixityLog.error("runAction (" + action + ") error:", err);
    if (status) {
      status.className = "ctl-status err";
      status.textContent = "✗ " + err;
    }
    return { ok: false, message: String(err) };
  } finally {
    if (button) { button.disabled = false; button.classList.remove("busy"); button.removeAttribute("aria-busy"); }
  }
}
function submitSettings() {
  var settings = document.getElementById("settings-form");
  if (!settings) return;
  var button = settings.querySelector('[data-action="settings"]');
  if (button.disabled) return;
  var payload = {};
  var mild = document.getElementById("set-z-mild");
  var strong = document.getElementById("set-z-strong");
  settings.querySelectorAll("input[type=number]").forEach(function(input) {
    var value = input.valueAsNumber;
    var excluded = (input.dataset.minExclusive === "true" && value <= Number(input.min)) ||
      (input.dataset.maxExclusive === "true" && value >= Number(input.max));
    input.setCustomValidity(excluded ? input.dataset.boundError || input.title || uiLabel("settings_bound_error") : "");
  });
  strong.setCustomValidity(strong.valueAsNumber < mild.valueAsNumber
    ? document.getElementById("settings-order-error").textContent : "");
  if (!settings.checkValidity()) {
    settings.querySelector("details").open = true;
    settings.reportValidity();
    return;
  }
  payload.language = document.getElementById("set-language").value;
  payload.title = document.getElementById("set-title").value;
  var zm = document.getElementById("set-z-mild");
  var zs = document.getElementById("set-z-strong");
  var fq = document.getElementById("set-fdr-q");
  var fs = document.getElementById("set-flag-min-sev");
  var dt = document.getElementById("set-dim-threshold");
  if (zm) payload.z_mild = parseFloat(zm.value);
  if (zs) payload.z_strong = parseFloat(zs.value);
  if (fq) payload.fdr_q = parseFloat(fq.value);
  if (fs) payload.flag_min_severity = parseInt(fs.value, 10);
  if (dt) payload.dim_score_threshold = parseFloat(dt.value);
  return runAction("settings", payload, button);
}
document.querySelectorAll("[data-action]").forEach(function (btn) {
  btn.addEventListener("click", function () {
    if (btn.dataset.payload === "settings") return;
    var payload = {};
    if (btn.dataset.payload === "format") {
      payload.format = document.getElementById("fmt").value;
    }
    if (btn.dataset.payload === "load") {
      var input = document.getElementById("ms-file");
      if (!input.files || !input.files.length) {
        manuscriptFileError();
        return;
      }
      var file = input.files[0];
      if (!supportedManuscriptFile(file)) { manuscriptFileError(); return; }
      btn.disabled = true;
      btn.classList.add("busy");
      btn.setAttribute("aria-busy", "true");
      var reader = new FileReader();
      reader.onload = function () {
        runAction("load", { name: file.name, content: reader.result }, btn);
      };
      reader.onerror = function () {
        manuscriptFileError("manuscript_read_failed");
        btn.disabled = false;
        btn.classList.remove("busy");
        btn.removeAttribute("aria-busy");
      };
      reader.readAsText(file);
      return;
    }
    runAction(btn.dataset.action, payload, btn);
  });
});

function researchStatus(message, ok) {
  var el = document.getElementById("research-status-bar");
  if (!el) return;
  if (ok === "loading") {
    el.className = "ctl-status loading";
    el.textContent = message || uiLabel("research_loading");
  } else if (!message) {
    el.className = "ctl-status";
    el.textContent = "";
  } else {
    var isOk = Boolean(ok);
    el.className = "ctl-status " + (isOk ? "ok" : "err");
    el.textContent = (isOk ? "✓ " : "✗ ") + message;
  }
}

async function researchApiPost(action, payload) {
  var data = await jsonApi(API + "/" + action, {method: "POST",
    headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload || {})});
  if (data.ok && ["research-ingest", "research-dossier", "research-claim-add", "research-decision-add"].includes(action)) {
    await refreshResearchProjectInfo();
  }
  return data;
}

function researchApiGet(endpoint) {
  return jsonApi(API + "/" + endpoint);
}

function escapeHtml(str) {
  var div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

function renderMermaidSvg(escapedCode) {
  var temp = document.createElement("textarea");
  temp.innerHTML = escapedCode;
  var code = temp.value.trim();

  try {
    var lines = code.split("\n").map(function(l) { return l.trim(); }).filter(function(l) {
      return l && !l.startsWith("%%");
    });
    if (!lines.length) return "";

    var header = lines[0].toLowerCase();

    // 1. Flowchart / Graph
    if (/^(graph|flowchart)\s+(td|tb|lr|rl)/i.test(header)) {
      var dirMatch = header.match(/^(?:graph|flowchart)\s+(td|tb|lr|rl)/i);
      var dir = dirMatch ? dirMatch[1].toUpperCase() : "TD";
      var isLR = dir === "LR" || dir === "RL";

      var nodes = {};
      var edges = [];

      function getOrCreateNode(id, label, shape) {
        if (!nodes[id]) {
          nodes[id] = { id: id, label: label || id, shape: shape || "rect" };
        } else {
          if (label) nodes[id].label = label;
          if (shape) nodes[id].shape = shape;
        }
        return nodes[id];
      }

      for (var i = 1; i < lines.length; i++) {
        var line = lines[i];

        var edgePattern = /^([a-zA-Z0-9_\-]+)(?:\[(.*?)\]|\((.*?)\)|\{(.*?)\})?\s*(-->|---|==>|-\.->)\s*(?:\|(.*?)\|)?\s*([a-zA-Z0-9_\-]+)(?:\[(.*?)\]|\((.*?)\)|\{(.*?)\})?$/;
        var m = line.match(edgePattern);
        if (m) {
          var fromId = m[1];
          var fromLabel = m[2] || m[3] || m[4];
          var fromShape = m[4] ? "diamond" : (m[3] ? "round" : "rect");
          var edgeLabel = m[6] || "";
          var toId = m[7];
          var toLabel = m[8] || m[9] || m[10];
          var toShape = m[10] ? "diamond" : (m[9] ? "round" : "rect");

          getOrCreateNode(fromId, fromLabel, fromShape);
          getOrCreateNode(toId, toLabel, toShape);
          edges.push({ from: fromId, to: toId, label: edgeLabel });
          continue;
        }

        var nodePattern = /^([a-zA-Z0-9_\-]+)(?:\[(.*?)\]|\((.*?)\)|\{(.*?)\})$/;
        var nm = line.match(nodePattern);
        if (nm) {
          var nId = nm[1];
          var nLabel = nm[2] || nm[3] || nm[4];
          var nShape = nm[4] ? "diamond" : (nm[3] ? "round" : "rect");
          getOrCreateNode(nId, nLabel, nShape);
        }
      }

      var nodeIds = Object.keys(nodes);
      if (nodeIds.length) {
        var inDegrees = {};
        var adj = {};
        nodeIds.forEach(function(id) { inDegrees[id] = 0; adj[id] = []; });
        edges.forEach(function(e) {
          if (inDegrees[e.to] !== undefined) inDegrees[e.to]++;
          if (adj[e.from]) adj[e.from].push(e.to);
        });

        var ranks = {};
        var maxRank = 0;
        var queue = [];
        nodeIds.forEach(function(id) {
          if (inDegrees[id] === 0) {
            ranks[id] = 0;
            queue.push(id);
          }
        });
        if (!queue.length && nodeIds.length) {
          ranks[nodeIds[0]] = 0;
          queue.push(nodeIds[0]);
        }

        while (queue.length) {
          var curr = queue.shift();
          var curRank = ranks[curr] || 0;
          adj[curr].forEach(function(next) {
            var nRank = (ranks[next] === undefined) ? curRank + 1 : Math.max(ranks[next], curRank + 1);
            ranks[next] = nRank;
            if (nRank > maxRank) maxRank = nRank;
            inDegrees[next]--;
            if (inDegrees[next] <= 0) queue.push(next);
          });
        }
        nodeIds.forEach(function(id) {
          if (ranks[id] === undefined) ranks[id] = 0;
        });

        var rankGroups = [];
        for (var r = 0; r <= maxRank; r++) rankGroups.push([]);
        nodeIds.forEach(function(id) {
          rankGroups[ranks[id]].push(id);
        });

        var nodePos = {};
        var padX = 25, padY = 25;
        var rankSep = isLR ? 150 : 80;
        var nodeSep = isLR ? 60 : 120;
        var totalWidth = 0, totalHeight = 0;

        rankGroups.forEach(function(group, rIdx) {
          group.forEach(function(id, idx) {
            var label = nodes[id].label;
            var w = Math.max(85, label.length * 8 + 20);
            var h = 36;
            var x, y;
            if (isLR) {
              x = padX + rIdx * rankSep;
              y = padY + idx * nodeSep;
              totalWidth = Math.max(totalWidth, x + w + padX);
              totalHeight = Math.max(totalHeight, y + h + padY);
            } else {
              x = padX + idx * nodeSep;
              y = padY + rIdx * rankSep;
              totalWidth = Math.max(totalWidth, x + w + padX);
              totalHeight = Math.max(totalHeight, y + h + padY);
            }
            nodePos[id] = { x: x, y: y, w: w, h: h };
          });
        });

        totalWidth = Math.max(totalWidth, 180);
        totalHeight = Math.max(totalHeight, 90);

        var svgParts = [
          '<div class="research-diagram-wrap"><svg class="research-diagram" viewBox="0 0 ' + totalWidth + ' ' + totalHeight + '" role="img" aria-label="Flowchart">',
          '<defs><marker id="rd-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
          '<path d="M 0 1 L 10 5 L 0 9 z" fill="var(--muted, #64748b)" /></marker></defs>'
        ];

        edges.forEach(function(e) {
          var p1 = nodePos[e.from];
          var p2 = nodePos[e.to];
          if (!p1 || !p2) return;

          var startX = isLR ? (p1.x + p1.w) : (p1.x + p1.w / 2);
          var startY = isLR ? (p1.y + p1.h / 2) : (p1.y + p1.h);
          var endX = isLR ? p2.x : (p2.x + p2.w / 2);
          var endY = isLR ? (p2.y + p2.h / 2) : p2.y;

          var midX = (startX + endX) / 2;
          var midY = (startY + endY) / 2;
          var d = 'M ' + startX + ' ' + startY + ' C ' + (isLR ? midX : startX) + ' ' + (isLR ? startY : midY) + ', ' + (isLR ? midX : endX) + ' ' + (isLR ? endY : midY) + ', ' + endX + ' ' + endY;

          svgParts.push('<path d="' + d + '" fill="none" stroke="var(--muted, #64748b)" stroke-width="1.5" marker-end="url(#rd-arrow)" />');
          if (e.label) {
            svgParts.push('<rect x="' + (midX - (e.label.length * 4)) + '" y="' + (midY - 8) + '" width="' + (e.label.length * 8) + '" height="16" fill="var(--bg, #fff)" rx="3" />');
            svgParts.push('<text x="' + midX + '" y="' + (midY + 4) + '" fill="var(--muted, #64748b)" font-size="10" text-anchor="middle">' + escapeHtml(e.label) + '</text>');
          }
        });

        nodeIds.forEach(function(id) {
          var pos = nodePos[id];
          var n = nodes[id];
          var rx = (n.shape === "round") ? "18" : (n.shape === "diamond" ? "0" : "6");
          svgParts.push('<g class="rd-node" tabindex="0" role="group" aria-label="' + escapeHtml(n.label) + '">');
          svgParts.push('<rect x="' + pos.x + '" y="' + pos.y + '" width="' + pos.w + '" height="' + pos.h + '" rx="' + rx + '" fill="var(--surface, #f8fafc)" stroke="var(--accent, #3b82f6)" stroke-width="1.5" />');
          svgParts.push('<text x="' + (pos.x + pos.w / 2) + '" y="' + (pos.y + pos.h / 2 + 4) + '" fill="var(--fg, #0f172a)" font-size="12" font-weight="500" text-anchor="middle">' + escapeHtml(n.label) + '</text>');
          svgParts.push('</g>');
        });

        svgParts.push('</svg></div>');
        return svgParts.join("");
      }
    }

    // 2. Sequence diagram
    if (/^sequencediagram/i.test(header)) {
      var participants = [];
      var pIndices = {};
      var messages = [];

      for (var s = 1; s < lines.length; s++) {
        var sline = lines[s];
        var pMatch = sline.match(/^participant\s+([a-zA-Z0-9_\-]+)(?:\s+as\s+(.*))?$/i);
        if (pMatch) {
          var pId = pMatch[1];
          var pName = pMatch[2] || pId;
          if (pIndices[pId] === undefined) {
            pIndices[pId] = participants.length;
            participants.push({ id: pId, label: pName });
          }
          continue;
        }

        var msgMatch = sline.match(/^([a-zA-Z0-9_\-]+)\s*(->>|-->>|->|-->)\s*([a-zA-Z0-9_\-]+)\s*:\s*(.*)$/);
        if (msgMatch) {
          var fromP = msgMatch[1];
          var arrType = msgMatch[2];
          var toP = msgMatch[3];
          var msgText = msgMatch[4];

          [fromP, toP].forEach(function(pid) {
            if (pIndices[pid] === undefined) {
              pIndices[pid] = participants.length;
              participants.push({ id: pid, label: pid });
            }
          });
          messages.push({ from: fromP, to: toP, text: msgText, dashed: arrType.includes("--") });
        }
      }

      if (participants.length >= 2) {
        var colWidth = 140;
        var pWidth = 100;
        var pHeight = 32;
        var sWidth = Math.max(280, participants.length * colWidth + 40);
        var msgSep = 45;
        var topY = 30;
        var sHeight = topY + (messages.length + 1) * msgSep + 30;

        var seqSvg = [
          '<div class="research-diagram-wrap"><svg class="research-diagram" viewBox="0 0 ' + sWidth + ' ' + sHeight + '" role="img" aria-label="Sequence diagram">',
          '<defs><marker id="rd-seq-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
          '<path d="M 0 1 L 10 5 L 0 9 z" fill="var(--accent, #3b82f6)" /></marker></defs>'
        ];

        participants.forEach(function(p, pIdx) {
          var centerX = 30 + pIdx * colWidth + pWidth / 2;
          seqSvg.push('<line x1="' + centerX + '" y1="' + (topY + pHeight) + '" x2="' + centerX + '" y2="' + (sHeight - 15) + '" stroke="var(--line, #e2e8f0)" stroke-dasharray="4" stroke-width="1.5" />');
          seqSvg.push('<rect x="' + (centerX - pWidth / 2) + '" y="' + topY + '" width="' + pWidth + '" height="' + pHeight + '" rx="4" fill="var(--surface, #f8fafc)" stroke="var(--accent, #3b82f6)" stroke-width="1.5" />');
          seqSvg.push('<text x="' + centerX + '" y="' + (topY + pHeight / 2 + 4) + '" fill="var(--fg, #0f172a)" font-size="12" font-weight="500" text-anchor="middle">' + escapeHtml(p.label) + '</text>');
        });

        messages.forEach(function(msg, mIdx) {
          var y = topY + pHeight + (mIdx + 1) * msgSep;
          var x1 = 30 + pIndices[msg.from] * colWidth + pWidth / 2;
          var x2 = 30 + pIndices[msg.to] * colWidth + pWidth / 2;
          var midX = (x1 + x2) / 2;
          var strokeDash = msg.dashed ? ' stroke-dasharray="4"' : '';

          seqSvg.push('<line x1="' + x1 + '" y1="' + y + '" x2="' + x2 + '" y2="' + y + '" stroke="var(--accent, #3b82f6)" stroke-width="1.5"' + strokeDash + ' marker-end="url(#rd-seq-arrow)" />');
          seqSvg.push('<text x="' + midX + '" y="' + (y - 6) + '" fill="var(--fg, #0f172a)" font-size="11" text-anchor="middle">' + escapeHtml(msg.text) + '</text>');
        });

        seqSvg.push('</svg></div>');
        return seqSvg.join("");
      }
    }
  } catch (err) {
    // Fallback on parse failure
  }

  return '<div class="research-diagram-wrap"><div class="research-diagram-note">' + escapeHtml(uiLabel("research_diagram_source")) + '</div><pre class="language-mermaid"><code>' + escapedCode.trim() + '</code></pre></div>';
}

function renderSafeMarkdown(rawText, dossierContext) {
  if (!rawText) return "";
  var imageRender = window.LixityDossierImages && dossierContext ? window.LixityDossierImages.prepareMarkdown(rawText, dossierContext) : null;
  var text = escapeHtml(imageRender ? imageRender.text : rawText);

  var codeBlocks = [];
  text = text.replace(/```([a-zA-Z0-9_\-]*)\n([\s\S]*?)```/g, function(match, lang, code) {
    var placeholder = "@@@CODE_BLOCK_" + codeBlocks.length + "@@@";
    if (lang && lang.toLowerCase() === "mermaid") {
      codeBlocks.push(renderMermaidSvg(code));
    } else {
      codeBlocks.push('<pre><code' + (lang ? ' class="language-' + lang + '"' : '') + '>' + code.trim() + '</code></pre>');
    }
    return placeholder;
  });

  var blocks = text.split(/\n\s*\n/);
  var htmlBlocks = [];

  function parseInline(str) {
    var inlineCodes = [];
    str = str.replace(/`([^`]+)`/g, function(m, c) {
      var p = "@@@INLINE_CODE_" + inlineCodes.length + "@@@";
      inlineCodes.push('<code>' + c + '</code>');
      return p;
    });

    // Graceful Math notation
    str = str.replace(/\$\$([\s\S]+?)\$\$/g, '<div class="math-display">$1</div>');
    str = str.replace(/\$([^$\n]+?)\$/g, '<span class="math-inline">$1</span>');

    str = str.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function(m, label, url) {
      var cleanUrl = url.trim();
      if (/^lixity:/i.test(cleanUrl)) {
        return '<code class="lixity-ref" title="Internal reference: ' + cleanUrl.replace(/"/g, "&quot;") + '">' + label + ' (' + cleanUrl.replace(/^lixity:/i, "") + ')</code>';
      }
      if (/^(javascript|data|vbscript):/i.test(cleanUrl)) {
        return label + ' (' + cleanUrl + ')';
      }
      if (/^(https?:\/\/|\/|#)/i.test(cleanUrl)) {
        return '<a href="' + cleanUrl.replace(/"/g, "&quot;") + '" target="_blank" rel="noopener noreferrer nofollow">' + label + '</a>';
      }
      return label + ' (' + cleanUrl + ')';
    });

    str = str.replace(/~~(.+?)~~/g, '<del>$1</del>');
    str = str.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    str = str.replace(/___(.+?)___/g, '<strong><em>$1</em></strong>');
    str = str.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    str = str.replace(/__(.+?)__/g, '<strong>$1</strong>');
    str = str.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    str = str.replace(/_([^_]+)_/g, '<em>$1</em>');

    inlineCodes.forEach(function(codeHtml, i) {
      str = str.replace("@@@INLINE_CODE_" + i + "@@@", codeHtml);
    });

    return str;
  }

  for (var b = 0; b < blocks.length; b++) {
    var block = blocks[b].trim();
    if (!block) continue;

    if (/^@@@CODE_BLOCK_\d+@@@$/.test(block)) {
      htmlBlocks.push(block);
      continue;
    }

    var headingMatch = block.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch && !headingMatch[2].includes("\n")) {
      var level = headingMatch[1].length;
      htmlBlocks.push('<h' + level + '>' + parseInline(headingMatch[2]) + '</h' + level + '>');
      continue;
    }

    if (/^(\*{3,}|-{3,}|_{3,})$/.test(block)) {
      htmlBlocks.push('<hr>');
      continue;
    }

    var lines = block.split("\n");
    var isBlockquote = lines.every(function(l) { return /^\s*&gt;/.test(l); });
    if (isBlockquote) {
      var bqContent = lines.map(function(l) { return l.replace(/^\s*&gt;\s?/, ""); }).join("\n");
      htmlBlocks.push('<blockquote><p>' + parseInline(bqContent).replace(/\n/g, '<br>') + '</p></blockquote>');
      continue;
    }

    if (lines.length >= 2 && lines[1].includes("-") && lines[1].includes("|")) {
      var sepCells = lines[1].trim().replace(/^\||\|$/g, "").split("|");
      var isTable = sepCells.every(function(c) { return /^[\s:-]+$/.test(c) && c.includes("-"); });
      if (isTable) {
        var alignments = sepCells.map(function(c) {
          var trimmed = c.trim();
          var left = trimmed.startsWith(":");
          var right = trimmed.endsWith(":");
          if (left && right) return "center";
          if (right) return "right";
          if (left) return "left";
          return "";
        });

        var headerCells = lines[0].trim().replace(/^\||\|$/g, "").split("|");
        var thHtml = headerCells.map(function(cell, idx) {
          var align = alignments[idx] ? ' style="text-align:' + alignments[idx] + '"' : '';
          return '<th' + align + '>' + parseInline(cell.trim()) + '</th>';
        }).join("");

        var tbRowsHtml = [];
        for (var r = 2; r < lines.length; r++) {
          if (!lines[r].trim()) continue;
          var rowCells = lines[r].trim().replace(/^\||\|$/g, "").split("|");
          var tdHtml = rowCells.map(function(cell, idx) {
            var align = alignments[idx] ? ' style="text-align:' + alignments[idx] + '"' : '';
            return '<td' + align + '>' + parseInline(cell.trim()) + '</td>';
          }).join("");
          tbRowsHtml.push('<tr>' + tdHtml + '</tr>');
        }

        htmlBlocks.push('<div class="table-wrap"><table class="research-table"><thead><tr>' + thHtml + '</tr></thead><tbody>' + tbRowsHtml.join("") + '</tbody></table></div>');
        continue;
      }
    }

    var isUnordered = lines.every(function(l) { return /^\s*[-*+]\s+/.test(l); });
    var isOrdered = lines.every(function(l) { return /^\s*\d+\.\s+/.test(l); });
    if (isUnordered) {
      var liHtml = lines.map(function(l) {
        var rawContent = l.replace(/^\s*[-*+]\s+/, "");
        var isTask = false;
        var content = rawContent;
        if (/^\[\s\]\s+/.test(rawContent)) {
          content = '<input type="checkbox" disabled class="task-list-item-checkbox"> ' + parseInline(rawContent.replace(/^\[\s\]\s+/, ""));
          isTask = true;
        } else if (/^\[[xX]\]\s+/.test(rawContent)) {
          content = '<input type="checkbox" checked disabled class="task-list-item-checkbox"> ' + parseInline(rawContent.replace(/^\[[xX]\]\s+/, ""));
          isTask = true;
        } else {
          content = parseInline(rawContent);
        }
        return '<li' + (isTask ? ' class="task-list-item"' : '') + '>' + content + '</li>';
      }).join("");
      htmlBlocks.push('<ul>' + liHtml + '</ul>');
      continue;
    }
    if (isOrdered) {
      var liOrdHtml = lines.map(function(l) {
        return '<li>' + parseInline(l.replace(/^\s*\d+\.\s+/, "")) + '</li>';
      }).join("");
      htmlBlocks.push('<ol>' + liOrdHtml + '</ol>');
      continue;
    }

    htmlBlocks.push('<p>' + parseInline(lines.join("\n")).replace(/\n/g, '<br>') + '</p>');
  }

  var resultHtml = htmlBlocks.join("\n");
  codeBlocks.forEach(function(cbHtml, i) {
    resultHtml = resultHtml.replace("@@@CODE_BLOCK_" + i + "@@@", cbHtml);
  });

  return imageRender ? window.LixityDossierImages.restoreMarkdown(resultHtml, imageRender) : resultHtml;
}

function researchDossierBodyHtml(bodyText, dossierContext) {
  var escapedRaw = escapeHtml(bodyText || "");
  var rendered = renderSafeMarkdown(bodyText || "", dossierContext);
  return '<div class="research-dossier-body-wrap">' +
    '<div class="research-prose-bar">' +
      '<button type="button" class="ctl ctl-sm research-source-toggle" data-source-toggle>' + escapeHtml(uiLabel("research_show_source")) + '</button>' +
    '</div>' +
    '<div class="research-prose markdown-body research-dossier-body-rendered">' + rendered + '</div>' +
    '<pre class="research-dossier-body-source" hidden>' + escapedRaw + '</pre>' +
  '</div>';
}

function researchDossierDetailHtml(detail) {
  var reviewAlert = "";
  if (detail.review_needed && detail.decision_reviews && detail.decision_reviews.length) {
    var needed = detail.decision_reviews.filter(function(r) { return r.status === "review_needed"; });
    if (needed.length) {
      reviewAlert = '<div class="banner banner-warning" style="margin:.5rem 0 .8rem;padding:.4rem .7rem;font-size:.82rem;background:rgba(217,119,6,0.1);border-left:3px solid var(--warn, #d97706);border-radius:3px;">' +
        '<strong>⚠️ ' + escapeHtml(uiLabel("research_review_needed")) + ':</strong> ' +
        needed.map(function(n) { return escapeHtml(n.reason || n.title); }).join(" · ") +
        '</div>';
    }
  }
  var sections = detail.sections || [];
  if (!sections.length && detail.body) {
    var secMatches = detail.body.match(/^#{1,3}\s+(.+)$/gm);
    if (secMatches) {
      sections = secMatches.map(function(s) { return s.replace(/^#{1,3}\s+/, "").trim(); });
    }
  }
  var sectionsHtml = "";
  if (sections.length) {
    sectionsHtml = '<div class="research-dossier-outline" style="margin:.4rem 0 .8rem;padding:.3rem .6rem;background:var(--bg-subtle, rgba(0,0,0,0.03));border-radius:4px;font-size:.78rem;">' +
      '<strong>' + escapeHtml(uiLabel("research_sections")) + ':</strong> ' +
      sections.map(function(sec) { return '<span class="research-tag research-tag-section" style="margin-left:.3rem;">' + escapeHtml(sec) + '</span>'; }).join("") +
      '</div>';
  }
  var bodyHtml = "";
  if (detail.section_map && Object.keys(detail.section_map).length > 1) {
    var secKeys = Object.keys(detail.section_map);
    var secBlocks = secKeys.map(function(k) {
      return '<details class="research-dossier-section-block" open>' +
        '<summary><span>' + escapeHtml(k) + '</span></summary>' +
        researchDossierSectionAction(detail, k) +
        '<div class="research-prose markdown-body">' + renderSafeMarkdown(detail.section_map[k], detail) + '</div>' +
      '</details>';
    }).join("");
    bodyHtml = '<div class="research-dossier-body-wrap">' +
      '<div class="research-prose-bar">' +
        '<button type="button" class="ctl ctl-sm research-source-toggle" data-source-toggle>' + escapeHtml(uiLabel("research_show_source")) + '</button>' +
      '</div>' +
      '<div class="research-dossier-body-rendered">' + secBlocks + '</div>' +
      '<pre class="research-dossier-body-source" hidden>' + escapeHtml(detail.body || "") + '</pre>' +
    '</div>';
  } else {
    bodyHtml = (detail.editable_sections || []).map(function(section) { return researchDossierSectionAction(detail, section); }).join("") +
      researchDossierBodyHtml(detail.body, detail);
  }
  return reviewAlert + sectionsHtml +
    '<div class="row"><button type="button" class="ctl" data-dossier-claim="' + escapeHtml(detail.id) + '">' + escapeHtml(uiLabel("research_claim_heading")) + '</button>' +
    '<button type="button" class="ctl" data-dossier-decision="' + escapeHtml(detail.id) + '">' + escapeHtml(uiLabel("research_decision_heading")) + '</button></div>' +
    (window.LixityDossierImages ? window.LixityDossierImages.actionsHtml(detail) : "") + bodyHtml +
    '<h4>' + escapeHtml(uiLabel("research_citations")) + '</h4>' + (detail.citations || []).map(researchCitationHtml).join("");
}

function researchDossierSectionAction(detail, section) {
  if (!(detail.editable_sections || []).includes(section)) return "";
  return '<div class="row"><button type="button" class="ctl ctl-sm" data-research-revise="dossier" data-record-id="' +
    escapeHtml(detail.id) + '" data-dossier-section="' + escapeHtml(section).replace(/"/g, "&quot;") +
    '" data-base-revision="' + Number(detail.revision) + '">' + escapeHtml(uiLabel("research_section_edit")) + '</button></div>';
}

document.addEventListener("lixity:dossier-image-saved", async function(event) {
  var accepted = event.detail;
  if (!accepted || !accepted.record) return;
  var previousFocus = document.activeElement;
  var restoreFocus = previousFocus === document.body ||
    previousFocus && previousFocus.dataset.dossierAddImage === accepted.record.id;
  function movedFocus(event) {
    if (event.target !== previousFocus && event.target !== document.body) restoreFocus = false;
  }
  function movedPointer(event) {
    if (previousFocus === document.body || !previousFocus.contains(event.target)) restoreFocus = false;
  }
  document.addEventListener("focusin", movedFocus);
  document.addEventListener("pointerdown", movedPointer);
  try {
  // These list refreshes preserve form values, filter input and selected IDs.
  // The shared revision editor keeps its independent unsaved drafts.
  await Promise.all([refreshResearchSources(null, accepted.capture && accepted.capture.source_id),
    refreshResearchDossiers(null, accepted.record.id), refreshResearchProjectInfo()]);
  var detail = await researchApiGet("research/dossiers?id=" + encodeURIComponent(accepted.record.id));
  if (!detail.ok || detail.project_id !== accepted.project_id) return;
  var summary = Array.from(document.querySelectorAll('[data-research-detail="dossier"]')).find(function(button) {
    return button.dataset.recordId === accepted.record.id;
  });
  if (!summary) return;
  summary.parentElement.open = true;
  var host = summary.parentElement.querySelector(".research-details-body");
  host.innerHTML = researchDossierDetailHtml(detail);
  var add = host.querySelector("[data-dossier-add-image]");
  if (add && restoreFocus && (document.activeElement === previousFocus || document.activeElement === document.body)) add.focus();
  researchStatus(uiLabel("image_saved"), true);
  } finally {
    document.removeEventListener("focusin", movedFocus);
    document.removeEventListener("pointerdown", movedPointer);
  }
});


function researchPassageActions(passageId) {
  return '<div class="row research-passage-actions">' +
    '<button type="button" class="ctl" data-use-passage="claim" data-passage-id="' + escapeHtml(passageId) + '">' + escapeHtml(uiLabel("research_use_for_claim")) + '</button>' +
    '<button type="button" class="ctl" data-use-passage="dossier" data-passage-id="' + escapeHtml(passageId) + '">' + escapeHtml(uiLabel("research_use_for_dossier")) + '</button></div>';
}

function researchCitationHtml(cite, interactive) {
  var unavailable = Boolean(cite.error) || !["available", "withdrawn"].includes(cite.availability);
  var withdrawn = cite.availability === "withdrawn";
  var availability = unavailable ? uiLabel("research_evidence_unavailable") : (withdrawn ? uiLabel("research_evidence_withdrawn_context") : uiLabel("research_evidence_retained_unreviewed"));
  return '<div class="research-passage-card">' +
    '<span class="research-badge ' + (unavailable || withdrawn ? 'badge-warning' : 'badge-neutral') + '">' + escapeHtml(availability) + '</span>' +
    '<div class="ctl-note">' + escapeHtml(cite.source_title || cite.passage_id || cite.id || "") + '</div>' +
    '<div class="research-passage-quote">' + (!unavailable && cite.verbatim ? escapeHtml(cite.verbatim) : escapeHtml(uiLabel("research_no_quote"))) + '</div>' +
    (cite.passage_id ? '<code>' + escapeHtml(cite.passage_id) + '</code>' : '') +
    (cite.evidence_link_id ? '<div class="ctl-note">' + escapeHtml(uiLabel("research_revision_kind_evidence_link")) + ': ' +
      escapeHtml(cite.evidence_link_id) + ' · ' + escapeHtml(uiFormat("research_revision_number", {revision: cite.evidence_link_revision})) +
      ' · ' + escapeHtml(uiLabel("research_revision_kind_claim")) + ' · ' +
      escapeHtml(uiFormat("research_revision_number", {revision: cite.claim_revision})) + '</div>' : '') +
    (interactive !== false && !unavailable && !withdrawn && cite.passage_id ? researchPassageActions(cite.passage_id) : '') +
    '</div>';
}

function researchDetailsControl(kind, id) {
  return '<details class="research-details"><summary data-research-detail="' + kind + '" data-record-id="' + escapeHtml(id) + '">' + escapeHtml(uiLabel("research_view_details")) + '</summary><div class="research-details-body"></div></details>';
}

function researchRevisionActions(kind, id) {
  var attrs = ' data-record-id="' + escapeHtml(id) + '"';
  return '<div class="research-record-actions">' +
    '<button type="button" class="ctl" data-research-revise="' + kind + '"' + attrs + '>' + escapeHtml(uiLabel("research_revision_edit")) + '</button>' +
    '<button type="button" class="ctl" data-research-history="' + kind + '"' + attrs + '>' + escapeHtml(uiLabel("research_revision_history")) + '</button>' +
    '</div>';
}

// Zotero remains an external catalogue. Only explicit captures enter evidence storage.
var zoteroProjectId = null;
var zoteroSelection = null;
var zoteroNextRequest = null;
var zoteroRequestSerial = 0;

function zoteroLibraryIdentity(library) {
  return /^users\/(0|[1-9]\d*)$/.test(library || "") ? "users/0" : library;
}

function zoteroOpenLink(library, key) {
  if (!/^[A-Z0-9]{8}$/.test(key || "") || !/^(users\/\d+|groups\/[1-9]\d*)$/.test(library || "")) return "";
  var prefix = library.startsWith("groups/") ? library : "library";
  return '<a class="ctl" href="zotero://select/' + prefix + '/items/' + key + '">' + escapeHtml(uiLabel("zotero_open")) + '</a>';
}

function clearZoteroSelection() {
  zoteroRequestSerial++;
  zoteroSelection = null;
  zoteroNextRequest = null;
  var host = document.getElementById("r-zotero-results");
  if (host) host.textContent = "";
  var retention = document.getElementById("r-zotero-retention");
  if (retention) retention.checked = false;
}

async function browseZotero(request) {
  var serial = ++zoteroRequestSerial;
  var host = document.getElementById("r-zotero-results");
  host.textContent = uiLabel("research_loading");
  var result = await researchApiPost("research-zotero", request);
  if (serial !== zoteroRequestSerial || request.project_id !== zoteroProjectId) return;
  if (!result.ok) { host.textContent = result.message || uiLabel("research_search_failed"); return; }
  zoteroSelection = {request: request, result: result};
  zoteroNextRequest = result.next_start === null || result.next_start === undefined ? null : Object.assign({}, request, {start: result.next_start});
  var items = result.attachments || result.items || [];
  host.innerHTML = items.map(function(item, index) {
    var data = item.data || {};
    var capture = (result.captures || []).find(function(c) {
      return c.server_id === result.server_id && zoteroLibraryIdentity(c.library) === zoteroLibraryIdentity(request.library) && c.attachment_key === item.key;
    });
    var supported = ["application/pdf", "text/plain", "text/markdown"].includes(data.contentType) &&
      ["imported_file", "imported_url", "linked_file"].includes(data.linkMode);
    var changed = capture && (capture.attachment_version !== item.version ||
      (result.item && capture.item_version !== result.item.version));
    return '<div class="research-card"><strong>' + escapeHtml(data.title || item.key) + '</strong>' +
      '<p class="ctl-note">' + escapeHtml(data.contentType || data.itemType || "") + '</p>' +
      (capture ? '<p class="ctl-note">' + escapeHtml(uiLabel(changed ? "zotero_metadata_changed" : "zotero_linked")) + '</p>' : '') +
      '<div class="row">' + zoteroOpenLink(request.library, item.key) +
      (data.itemType === "attachment" ? (supported && result.server_id ? '<button type="button" class="ctl primary" data-zotero-capture="' + index + '">' +
        escapeHtml(uiLabel(capture ? "zotero_refresh" : "zotero_capture")) + '</button>' : '<span class="ctl-note">' + escapeHtml(uiLabel("zotero_media")) + '</span>') :
        '<button type="button" class="ctl" data-zotero-item="' + index + '">' + escapeHtml(uiLabel("research_view_details")) + '</button>') + '</div></div>';
  }).join("") + (zoteroNextRequest ? '<button type="button" class="ctl" id="r-zotero-more">' + escapeHtml(uiLabel("zotero_more")) + '</button>' : '');
  if (!items.length) host.textContent = uiFormat("research_hits_count", {count: 0});
}

document.addEventListener("change", function(event) {
  if (["r-zotero-library", "r-zotero-collection"].includes(event.target.id)) {
    clearZoteroSelection();
    if (event.target.id === "r-zotero-library") {
      document.getElementById("r-zotero-collection").innerHTML = '<option value="">' + escapeHtml(uiLabel("zotero_all")) + '</option>';
      document.getElementById("r-zotero-collections").dataset.start = "0";
    }
  }
});

document.addEventListener("click", async function(event) {
  var button = event.target.closest("#r-zotero-browse, #r-zotero-collections, #r-zotero-more, [data-zotero-item], [data-zotero-capture]");
  if (!button || button.disabled || !zoteroProjectId) return;
  button.disabled = true;
  try {
    var request = {project_id: zoteroProjectId, library: document.getElementById("r-zotero-library").value.trim()};
    if (button.id === "r-zotero-collections") {
      request.mode = "collections";
      request.start = Number(button.dataset.start || 0);
      var collections = await researchApiPost("research-zotero", request);
      if (!collections.ok) { researchStatus(collections.message, false); return; }
      if (request.project_id !== zoteroProjectId || request.library !== document.getElementById("r-zotero-library").value.trim()) return;
      var select = document.getElementById("r-zotero-collection");
      if (!request.start) select.innerHTML = '<option value="">' + escapeHtml(uiLabel("zotero_all")) + '</option>';
      (collections.collections || []).forEach(function(c) { select.add(new Option(c.data.name, c.key)); });
      button.dataset.start = String(collections.next_start || 0);
      button.textContent = uiLabel(collections.next_start ? "zotero_more" : "zotero_collections");
    } else if (button.id === "r-zotero-browse") {
      request.query = document.getElementById("r-zotero-query").value.trim();
      request.collection_key = document.getElementById("r-zotero-collection").value || null;
      await browseZotero(request);
    } else if (button.id === "r-zotero-more") {
      if (zoteroNextRequest) await browseZotero(zoteroNextRequest);
    } else if (zoteroSelection) {
      var selection = zoteroSelection;
      var items = selection.result.attachments || selection.result.items || [];
      var item = items[Number(button.dataset.zoteroItem || button.dataset.zoteroCapture)];
      if (!item) return;
      if (button.hasAttribute("data-zotero-item")) {
        await browseZotero({project_id: selection.request.project_id, library: selection.request.library, item_key: item.key});
      } else {
        if (!document.getElementById("r-zotero-retention").checked) { researchStatus(uiLabel("research_retention_required"), false); return; }
        var captured = (selection.result.captures || []).find(function(c) {
          return c.server_id === selection.result.server_id && zoteroLibraryIdentity(c.library) === zoteroLibraryIdentity(selection.request.library) && c.attachment_key === item.key;
        });
        var response = await researchApiPost("research-zotero-ingest", {project_id: selection.request.project_id,
          library: selection.request.library, attachment_key: item.key, expected_server_id: selection.result.server_id,
          source_id: captured ? captured.source_id : null, allow_retention: true});
        if (selection.request.project_id !== zoteroProjectId) return;
        var captureMessage = response.ok ? uiLabel("research_ingest_complete") : response.message;
        if (response.ok && Array.isArray(response.warnings) && response.warnings.length) {
          captureMessage += " " + response.warnings.join(" ");
        }
        researchStatus(captureMessage, response.ok);
        if (response.ok) {
          document.getElementById("r-zotero-retention").checked = false;
          await refreshResearchSources();
          await browseZotero(selection.request);
        }
      }
    }
  } finally { button.disabled = false; }
});

function filterResearchList(kind) {
  var input = document.getElementById("r-filter-" + kind);
  var list = document.getElementById("research-" + kind + "-list");
  var status = document.getElementById("r-filter-" + kind + "-status");
  if (!input || !list || !status) return;
  var query = input.value.trim();
  var normalized = query.toLowerCase();
  var cards = list.querySelectorAll(".research-card[data-filter-text]");
  var matches = 0;
  cards.forEach(function(card) {
    card.hidden = Boolean(normalized) && !card.dataset.filterText.includes(normalized);
    if (!card.hidden) matches++;
  });
  status.hidden = !normalized || !cards.length || matches > 0;
  status.textContent = status.hidden ? "" : uiFormat("research_no_hits", {query: query});
}

document.addEventListener("input", function(event) {
  if (event.target.id === "r-filter-sources") filterResearchList("sources");
  if (event.target.id === "r-filter-dossiers") filterResearchList("dossiers");
});

function replaceResearchCard(listHost, html, recordId) {
  var previous = Array.from(listHost.querySelectorAll("[data-research-detail]")).find(function(summary) {
    return summary.dataset.recordId === recordId;
  });
  var fresh = document.createElement("div");
  fresh.innerHTML = html;
  if (previous && fresh.firstElementChild) previous.closest(".research-card").replaceWith(fresh.firstElementChild);
  else if (fresh.firstElementChild) {
    if (!listHost.querySelector(".research-card")) listHost.replaceChildren();
    listHost.prepend(fresh.firstElementChild);
  }
}

async function refreshResearchSources(overview, changedId) {
  var listHost = document.getElementById("research-sources-list");
  var selectHost = document.getElementById("r-ground-source-select");
  if (!listHost) return;
  if (!listHost.children.length) {
    listHost.innerHTML = '<div class="loading-state"><span class="loading-spinner" aria-hidden="true"></span><span class="loading-text">' +
      escapeHtml(uiLabel("research_loading")) + '</span></div>';
  }
  var data = overview && Array.isArray(overview.sources) ? overview : await researchApiGet("research/sources");
  if (!data.ok) {
    listHost.innerHTML = '<p class="ctl-note">' + escapeHtml(data.message || uiLabel("research_load_sources_failed")) + '</p>';
    filterResearchList("sources");
    return;
  }
  var sources = data.sources || [];
  var localImport = document.getElementById("r-local-import");
  if (localImport) localImport.hidden = sources.length > 0 && sources.every(function(s) { return s.context && s.context.external_reference; });
  var external = sources.find(function(s) { return s.context && s.context.external_reference; });
  var libraryInput = document.getElementById("r-zotero-library");
  if (external && libraryInput && !zoteroSelection) libraryInput.value = external.context.external_reference.library;
  if (selectHost) {
    var selectedSource = selectHost.value;
    var textSources = sources.filter(function(source) { return !["image/png", "image/jpeg"].includes(source.media_type); });
    selectHost.innerHTML = '<option value="">' + escapeHtml(uiLabel("research_select_source")) + '</option>' +
      textSources.map(function(s) {
        return '<option value="' + escapeHtml(s.id) + '">' + escapeHtml(s.title) + ' (' + escapeHtml(uiFormat("research_passages_count", { count: s.passages })) + ')</option>';
      }).join("");
    if (textSources.some(function(s) { return s.id === selectedSource; })) selectHost.value = selectedSource;
  }
  if (!sources.length) {
    listHost.innerHTML = '<p class="ctl-note">' + escapeHtml(uiLabel("research_no_sources")) + '</p>';
    filterResearchList("sources");
    return;
  }
  var rendered = sources.filter(function(s) { return !changedId || s.id === changedId; }).map(function(s) {
    var tagsHtml = (s.tags || []).map(function(t) {
      return '<span class="research-tag">' + escapeHtml(t) + '</span>';
    }).join(" ");
    var filterText = [s.title, s.id].concat(s.tags || []).join(" ").toLowerCase();
    return '<div class="research-card" data-filter-text="' + escapeHtml(filterText).replace(/"/g, "&quot;") + '">' +
      '<div class="research-card-header">' +
        '<span class="research-card-title">' + escapeHtml(s.title) + '</span>' +
        '<span class="ctl-note">' + escapeHtml(["image/png", "image/jpeg"].includes(s.media_type) ? s.media_type : uiFormat("research_passages_count", { count: s.passages })) + ' · ' + Math.round((s.byte_length || 0) / 1024) + ' KB</span>' +
      '</div>' +
      '<div class="ctl-note" style="font-family:monospace;font-size:.7rem;margin-top:.2rem;">' + escapeHtml(s.id) + '</div>' +
      (tagsHtml ? '<div class="research-tags">' + tagsHtml + '</div>' : '') +
      (s.context && s.context.external_reference ? zoteroOpenLink(s.context.external_reference.library, s.context.external_reference.item_key) : "") +
      researchDetailsControl("source", s.id) +
    '</div>';
  }).join("");
  if (changedId) replaceResearchCard(listHost, rendered, changedId);
  else listHost.innerHTML = rendered;
  filterResearchList("sources");
}

async function refreshResearchDossiers(overview, changedId) {
  var listHost = document.getElementById("research-dossiers-list");
  if (!listHost) return;
  if (!listHost.children.length) {
    listHost.innerHTML = '<div class="loading-state"><span class="loading-spinner" aria-hidden="true"></span><span class="loading-text">' +
      escapeHtml(uiLabel("research_loading")) + '</span></div>';
  }
  var data = overview && Array.isArray(overview.dossiers) ? overview : await researchApiGet("research/dossiers");
  if (!data.ok) {
    listHost.innerHTML = '<p class="ctl-note">' + escapeHtml(data.message || uiLabel("research_load_dossiers_failed")) + '</p>';
    filterResearchList("dossiers");
    return;
  }
  var dossiers = data.dossiers || [];
  ["r-claim-dossier-select", "r-decision-dossier-select"].forEach(function(selectId) {
    var dossierSelect = document.getElementById(selectId);
    if (!dossierSelect) return;
    var selectedDossier = dossierSelect.value;
    dossierSelect.innerHTML = '<option value="">' + escapeHtml(uiLabel("research_no_dossier")) + '</option>' + dossiers.map(function(d) {
      return '<option value="' + escapeHtml(d.id) + '">' + escapeHtml(d.title) + '</option>';
    }).join("");
    if (dossiers.some(function(d) { return d.id === selectedDossier; })) dossierSelect.value = selectedDossier;
  });
  if (!dossiers.length) {
    listHost.innerHTML = '<p class="ctl-note">' + escapeHtml(uiLabel("research_no_dossiers")) + '</p>';
    filterResearchList("dossiers");
    return;
  }
  var rendered = dossiers.filter(function(d) { return !changedId || d.id === changedId; }).map(function(d) {
    var tagsHtml = (d.tags || []).map(function(t) {
      return '<span class="research-tag">' + escapeHtml(t) + '</span>';
    }).join(" ");
    var reviewBadge = d.review_needed
      ? '<span class="research-badge badge-warning" style="margin-left:.4rem;" title="' + escapeHtml(uiLabel("research_review_needed")) + '">' + escapeHtml(uiLabel("research_review_needed")) + '</span>'
      : '';
    var sectionsBadges = (d.sections && d.sections.length)
      ? '<div class="research-dossier-sections"><span class="ctl-note" style="font-size:.72rem;">' + escapeHtml(uiLabel("research_sections")) + ':</span> ' +
        d.sections.map(function(s) { return '<span class="research-tag research-tag-section">' + escapeHtml(s) + '</span>'; }).join(" ") + '</div>'
      : '';
    var filterText = [d.title, d.id, d.excerpt].concat(d.tags || [], d.sections || []).join(" ").toLowerCase();
    return '<div class="research-card" data-filter-text="' + escapeHtml(filterText).replace(/"/g, "&quot;") + '">' +
      '<div class="research-card-header">' +
        '<span class="research-card-title">' + escapeHtml(d.title) + '</span>' +
        reviewBadge +
        '<span class="ctl-note">' + escapeHtml(uiFormat("research_evidence_count", { count: d.evidence_count })) + '</span>' +
        (d.revision ? '<span class="ctl-note">' + escapeHtml(uiFormat("research_revision_number", { revision: d.revision })) + '</span>' : '') +
      '</div>' +
      (d.excerpt ? '<p class="ctl-note" style="margin:.3rem 0;color:var(--fg);">' + escapeHtml(d.excerpt) + '</p>' : '') +
      sectionsBadges +
      (tagsHtml ? '<div class="research-tags">' + tagsHtml + '</div>' : '') +
      researchDetailsControl("dossier", d.id) +
      researchRevisionActions("dossier", d.id) +
    '</div>';
  }).join("");
  if (changedId) replaceResearchCard(listHost, rendered, changedId);
  else listHost.innerHTML = rendered;
  filterResearchList("dossiers");
}

async function refreshResearchClaims(overview) {
  var listHost = document.getElementById("research-claims-list");
  var selectHost = document.getElementById("r-decision-claim-select");
  var linkClaimSelect = document.getElementById("r-link-claim-select");
  if (!listHost) return;
  if (!listHost.children.length) {
    listHost.innerHTML = '<div class="loading-state"><span class="loading-spinner" aria-hidden="true"></span><span class="loading-text">' +
      escapeHtml(uiLabel("research_loading")) + '</span></div>';
  }
  var data = overview && Array.isArray(overview.claims) ? overview : await researchApiGet("research/claims");
  if (!data.ok) {
    listHost.innerHTML = '<p class="ctl-note">' + escapeHtml(data.message || uiLabel("research_load_claims_failed")) + '</p>';
    return;
  }
  var claims = data.claims || [];
  if (selectHost) {
    var selectedDecisionClaim = selectHost.value;
    selectHost.innerHTML = '<option value="">' + escapeHtml(uiLabel("research_no_claim_linked")) + '</option>' +
      claims.map(function(c) {
        return '<option value="' + escapeHtml(c.id) + '">' + escapeHtml(c.title) + '</option>';
      }).join("");
    if (claims.some(function(c) { return c.id === selectedDecisionClaim; })) selectHost.value = selectedDecisionClaim;
  }
  if (linkClaimSelect) {
    var selectedEvidenceClaim = linkClaimSelect.value;
    linkClaimSelect.innerHTML = '<option value="">' + escapeHtml(uiLabel("research_select_claim")) + '</option>' +
      claims.map(function(c) {
        return '<option value="' + escapeHtml(c.id) + '">' + escapeHtml(c.title) + '</option>';
      }).join("");
    if (claims.some(function(c) { return c.id === selectedEvidenceClaim; })) linkClaimSelect.value = selectedEvidenceClaim;
  }
  if (!claims.length) {
    listHost.innerHTML = '<p class="ctl-note">' + escapeHtml(uiLabel("research_no_claims")) + '</p>';
    return;
  }
  listHost.innerHTML = claims.map(function(c) {
    var confClass = c.confidence === "evidenced" ? "badge-success" : (c.confidence === "disputed" ? "badge-warning" : "badge-neutral");
    var confLabel = c.confidence === "evidenced" ? uiLabel("research_confidence_evidenced") : (c.confidence === "disputed" ? uiLabel("research_confidence_disputed") : uiLabel("research_confidence_hypothetical"));
    var scopeParts = [];
    if (c.scope) {
      if (c.scope.time_period) scopeParts.push(escapeHtml(uiLabel("research_scope_time")) + " " + escapeHtml(c.scope.time_period));
      if (c.scope.place) scopeParts.push(escapeHtml(uiLabel("research_scope_place")) + " " + escapeHtml(c.scope.place));
      if (c.scope.actors && c.scope.actors.length) scopeParts.push(escapeHtml(uiLabel("research_scope_actors")) + " " + escapeHtml(c.scope.actors.join(", ")));
    }
    var tagsHtml = (c.tags || []).map(function(t) {
      return '<span class="research-tag">' + escapeHtml(t) + '</span>';
    }).join(" ");

    return '<div class="research-card">' +
      '<div class="research-card-header">' +
        '<span class="research-card-title">' + escapeHtml(c.title) + '</span>' +
        '<span class="research-badge ' + confClass + '">' + escapeHtml(confLabel) + '</span>' +
        (c.revision ? '<span class="ctl-note">' + escapeHtml(uiFormat("research_revision_number", { revision: c.revision })) + '</span>' : '') +
      '</div>' +
      '<div class="research-claim-statement research-prose markdown-body" style="margin:.4rem 0;">' + renderSafeMarkdown(c.statement) + '</div>' +
      (scopeParts.length ? '<div class="ctl-note" style="margin-bottom:.3rem;font-size:.76rem;">' + scopeParts.join(" · ") + '</div>' : '') +
      '<div class="ctl-note" style="font-family:monospace;font-size:.7rem;margin-top:.2rem;">' + escapeHtml(uiLabel("research_claim_id")) + ' ' + escapeHtml(c.id) + '</div>' +
      (c.dossier_id ? '<div class="ctl-note">' + escapeHtml(uiLabel("research_dossier")) + ': ' + escapeHtml(c.dossier_id) +
        (c.dossier_revision ? ' · ' + escapeHtml(uiFormat("research_revision_number", { revision: c.dossier_revision })) : '') + '</div>' : '') +
      (tagsHtml ? '<div class="research-tags">' + tagsHtml + '</div>' : '') +
      '<div class="claim-evidence-subpanel" id="claim-evidence-' + escapeHtml(c.id) + '" style="margin-top:.6rem;padding-top:.4rem;border-top:1px dashed var(--line);">' +
        '<button type="button" class="ctl" style="font-size:.74rem;padding:.2rem .5rem;" data-load-evidence="' + escapeHtml(c.id) + '">' + escapeHtml(uiLabel("research_load_evidence")) + '</button>' +
      '</div>' +
      researchRevisionActions("claim", c.id) +
    '</div>';
  }).join("");
}

async function refreshResearchDecisions(overview) {
  var listHost = document.getElementById("research-decisions-list");
  if (!listHost) return;
  if (!listHost.children.length) {
    listHost.innerHTML = '<div class="loading-state"><span class="loading-spinner" aria-hidden="true"></span><span class="loading-text">' +
      escapeHtml(uiLabel("research_loading")) + '</span></div>';
  }
  var data = overview && Array.isArray(overview.decisions) ? overview : await researchApiGet("research/decisions");
  if (!data.ok) {
    listHost.innerHTML = '<p class="ctl-note">' + escapeHtml(data.message || uiLabel("research_load_decisions_failed")) + '</p>';
    return;
  }
  var decisions = data.decisions || [];
  if (!decisions.length) {
    listHost.innerHTML = '<p class="ctl-note">' + escapeHtml(uiLabel("research_no_decisions")) + '</p>';
    return;
  }
  listHost.innerHTML = decisions.map(function(d) {
    var devBadge = d.deviation_from_fact
      ? '<span class="research-badge badge-warning">' + escapeHtml(uiLabel("research_deliberate_deviation")) + '</span>'
      : '<span class="research-badge badge-neutral">' + escapeHtml(uiLabel("research_no_deviation_recorded")) + '</span>';
    return '<div class="research-card">' +
      '<div class="research-card-header">' +
        '<span class="research-card-title">' + escapeHtml(d.title) + '</span>' +
        devBadge +
        (d.revision ? '<span class="ctl-note">' + escapeHtml(uiFormat("research_revision_number", { revision: d.revision })) + '</span>' : '') +
      '</div>' +
      '<div class="research-decision-rationale research-prose markdown-body" style="margin:.4rem 0;">' + renderSafeMarkdown(d.rationale) + '</div>' +
      (d.impact_on_plot ? '<div class="ctl-note" style="margin:.3rem 0;font-size:.78rem;"><strong>' + escapeHtml(uiLabel("research_decision_impact")) + ':</strong> <span class="research-prose markdown-body">' + renderSafeMarkdown(d.impact_on_plot) + '</span></div>' : '') +
      (d.claim_id ? '<div class="ctl-note" style="font-family:monospace;font-size:.7rem;margin-top:.2rem;">' + escapeHtml(uiLabel("research_decision_claim")) + ' ' + escapeHtml(d.claim_id) +
        (d.claim_revision ? ' · ' + escapeHtml(uiFormat("research_revision_number", { revision: d.claim_revision })) : '') + '</div>' : '') +
      '<details class="research-details"><summary data-decision-impact="' + escapeHtml(d.id) + '">' + escapeHtml(uiLabel("research_decision_affected")) + '</summary><div class="research-details-body"></div></details>' +
      researchRevisionActions("decision", d.id) +
    '</div>';
  }).join("");
}

function researchEditorialFlags(flags, decisionAfterDossier) {
  var after = decisionAfterDossier === undefined ? (flags || []).includes("decision_after_dossier") : decisionAfterDossier;
  return '<ul class="research-editorial-flags" data-decision-after-dossier="' + (after ? '1' : '0') + '">' + (flags || []).map(function(flag) {
    return '<li data-editorial-flag="' + escapeHtml(flag) + '">' + escapeHtml(uiLabel("research_editorial_" + flag)) + '</li>';
  }).join("") + '</ul>';
}

function acknowledgeEditorialFlags(pair, status) {
  var card = pair.closest(".research-card");
  var flags = card && card.querySelector(".research-editorial-flags");
  if (!flags) return;
  var names = Array.from(flags.querySelectorAll("[data-editorial-flag]")).map(function(item) {
    return item.dataset.editorialFlag;
  }).filter(function(name) {
    return !["decision_after_dossier", "author_review_needed", "stale_author_acknowledgement"].includes(name);
  });
  var after = flags.dataset.decisionAfterDossier === "1";
  if (status === "review_needed") {
    if (after) names.push("decision_after_dossier");
    names.push("author_review_needed");
  }
  var replacement = document.createElement("div");
  replacement.innerHTML = researchEditorialFlags(names, after);
  flags.replaceWith(replacement.firstElementChild);
}

function researchEditorialTime(timestamp) {
  return '<time datetime="' + escapeHtml(timestamp) + '">' +
    escapeHtml(new Date(timestamp).toLocaleString(document.documentElement.lang || "en", {timeZone: "UTC"})) + ' UTC</time>';
}

function researchDecisionAcknowledgement(context) {
  if (!context.dossierId || !context.snapshot || !Number.isInteger(context.decisionRevision) ||
      !Number.isInteger(context.dossierRevision)) return "";
  var ack = context.acknowledgement;
  var applied = Boolean(ack && ack.current === true && ack.status === "applied");
  var status = ack ? uiLabel(ack.current === true ?
    (applied ? "research_decision_applied" : "research_decision_review_needed") :
    "research_decision_earlier_assessment") : "";
  var blocked = (context.flags || []).includes("withdrawn_dossier");
  return '<div class="research-decision-acknowledgement" data-decision-ack-dossier="' + escapeHtml(context.dossierId) +
    '" data-decision-ack-decision="' + escapeHtml(context.decisionId) +
    '" data-decision-ack-decision-revision="' + context.decisionRevision +
    '" data-decision-ack-dossier-revision="' + context.dossierRevision +
    '" data-decision-ack-snapshot="' + escapeHtml(context.snapshot) + '">' +
    (status ? '<p class="ctl-note">' + escapeHtml(status) + '</p>' : '') +
    '<p class="ctl-note">' + escapeHtml(uiLabel("research_decision_ack_help")) + '</p>' +
    '<button type="button" class="ctl" data-decision-ack-status="' + (applied ? 'review_needed' : 'applied') + '"' +
    (blocked ? ' disabled' : '') + '>' + escapeHtml(uiLabel(applied ? "research_decision_reopen_review" : "research_decision_mark_applied")) + '</button>' +
    '<p class="ctl-status" data-decision-ack-feedback role="alert" aria-live="assertive" hidden></p></div>';
}

function researchAffectedDossier(dossier, impact) {
  return '<div class="research-card"><strong>' + escapeHtml(dossier.title) + '</strong>' +
    '<p class="ctl-note">' + escapeHtml(uiFormat("research_decision_dossier_versions", {
      pinned: dossier.pinned_revisions.join(", "), current: dossier.current_revision
    })) + '</p><p class="ctl-note">' + escapeHtml(uiLabel("research_editorial_dossier_date")) + ': ' +
    researchEditorialTime(dossier.created_at) + '</p>' + researchEditorialFlags(dossier.flags, dossier.decision_after_dossier) +
    (dossier.sections.length ? '<p class="ctl-note">' + dossier.sections.map(escapeHtml).join(" · ") + '</p>' : '') +
    (!dossier.withdrawn ? researchDetailsControl("dossier", dossier.id) : '') +
    researchDecisionAcknowledgement({decisionId: impact.decision.id, decisionRevision: impact.decision.revision,
      dossierId: dossier.id, dossierRevision: dossier.current_revision, snapshot: impact.snapshot,
      acknowledgement: dossier.acknowledgement, flags: dossier.flags}) + '</div>';
}

var researchReviewRequest = 0;
var researchAcknowledgementPending = false;
async function refreshResearchEditorialReview(preserve, expectedSnapshot) {
  var host = document.getElementById("research-editorial-review");
  if (!host) return;
  var request = ++researchReviewRequest;
  if (!preserve) host.textContent = uiLabel("research_loading");
  var report = await researchApiGet("research/review");
  if (request !== researchReviewRequest) return;
  if (preserve && report.ok && report.snapshot !== expectedSnapshot) {
    researchStatus(uiLabel("research_decision_ack_conflict"), false);
    return;
  }
  if (preserve && !report.ok) {
    researchStatus(report.message || uiLabel("research_status_unavailable"), false);
    return;
  }
  if (!report.ok) {
    host.textContent = report.message || uiLabel("research_status_unavailable");
    return;
  }
  if (!report.candidates.length) {
    host.textContent = uiLabel("research_editorial_empty");
    return;
  }
  var rendered = '<p class="ctl-note">' + escapeHtml(uiFormat("research_editorial_count", {count: report.candidate_count})) + '</p>' +
    report.candidates.map(function(candidate) {
      return '<div class="research-card"><strong>' + escapeHtml(candidate.title) + '</strong>' +
        (candidate.dossier_title ? '<p>' + escapeHtml(candidate.dossier_title) + '</p>' : '') +
        '<p class="ctl-note">' + escapeHtml(uiFormat("research_revision_number", {revision: candidate.decision_revision})) + ' · ' +
        escapeHtml(uiLabel("research_editorial_decision_date")) + ': ' + researchEditorialTime(candidate.decision_created_at) + '</p>' +
        (candidate.dossier_created_at ? '<p class="ctl-note">' + escapeHtml(uiLabel("research_editorial_dossier_date")) + ': ' +
          researchEditorialTime(candidate.dossier_created_at) + '</p>' : '') +
        researchEditorialFlags(candidate.flags, candidate.decision_created_at > candidate.dossier_created_at) +
        (candidate.dossier_id ? '<p class="ctl-note">' + escapeHtml(uiFormat("research_decision_dossier_versions", {
          pinned: candidate.pinned_revisions.join(", "), current: candidate.current_revision
        })) + '</p>' : '') +
        (candidate.sections.length ? '<p class="ctl-note">' + candidate.sections.map(escapeHtml).join(" · ") + '</p>' : '') +
        (candidate.dossier_id && !candidate.flags.includes("withdrawn_dossier") ? researchDetailsControl("dossier", candidate.dossier_id) : '') +
        researchRevisionActions("decision", candidate.decision_id) +
        researchDecisionAcknowledgement({decisionId: candidate.decision_id, decisionRevision: candidate.decision_revision,
          dossierId: candidate.dossier_id, dossierRevision: candidate.current_revision, snapshot: report.snapshot,
          acknowledgement: candidate.acknowledgement, flags: candidate.flags}) + '</div>';
    }).join("");
  if (!preserve) { host.innerHTML = rendered; return; }
  var focused = document.activeElement;
  var fresh = document.createElement("div");
  fresh.innerHTML = rendered;
  var retained = new Map();
  host.querySelectorAll(".research-card").forEach(function(card) {
    var pair = card.querySelector(".research-decision-acknowledgement");
    if (pair) retained.set(pair.dataset.decisionAckDecision + ":" + pair.dataset.decisionAckDossier, card);
  });
  fresh.querySelectorAll(".research-card").forEach(function(card) {
    var pair = card.querySelector(".research-decision-acknowledgement");
    var previous = pair && retained.get(pair.dataset.decisionAckDecision + ":" + pair.dataset.decisionAckDossier);
    if (!previous) return;
    previous.querySelector(".research-editorial-flags").replaceWith(card.querySelector(".research-editorial-flags"));
    var previousPair = previous.querySelector(".research-decision-acknowledgement");
    if (previousPair.contains(focused)) focused = pair.querySelector("[data-decision-ack-status]");
    previousPair.replaceWith(pair);
    card.replaceWith(previous);
  });
  host.replaceChildren.apply(host, Array.from(fresh.childNodes));
  if (focused && focused.isConnected && document.activeElement !== focused) focused.focus({preventScroll: true});
}

function ocrReading(ocr) {
  ocr = ocr || {};
    var ocrStatus = ocr.status === "ready (probed)" ? "ready" : ocr.status;
    var badgeClass = ocrStatus === "ready" ? "ok" : (ocrStatus === "native_only" ? "note" : "err");
    var ocrLabels = {
      ready: ocr.backend === "tesseract" ? ["research_ocr_tesseract_ready", "research_ocr_tesseract_ready_help"] : ["research_ocr_ready", "research_ocr_ready_help"],
      native_only: ["research_ocr_native", "research_ocr_native_help"],
      partial: ["research_ocr_partial", "research_ocr_partial_help"],
      misconfigured_worker: ["research_ocr_worker_error", "research_ocr_worker_error_help"],
      misconfigured_backend: ["research_ocr_tesseract_error", "research_ocr_tesseract_error_help"],
      missing_dependencies: ["research_ocr_missing", "research_ocr_missing_help"]
    };
    var ocrKeys = Object.prototype.hasOwnProperty.call(ocrLabels, ocrStatus)
      ? ocrLabels[ocrStatus] : ["research_ocr_unknown", "research_ocr_unknown_help"];
    var labelText = uiLabel(ocrKeys[0]);
    var guidanceText = uiLabel(ocrKeys[1]);
    if (ocr.requested_languages && ocr.requested_languages.length) {
      guidanceText += " " + uiFormat("research_ocr_languages", {languages: ocr.requested_languages.join(" + ")});
    }
    if (ocr.missing_languages && ocr.missing_languages.length) {
      guidanceText += " " + uiFormat("research_ocr_missing_languages", {languages: ocr.missing_languages.join(" + ")});
    }
  return {label: labelText, guidance: guidanceText, badge: badgeClass};
}

async function refreshResearchProjectInfo() {
  var activeRootEl = document.getElementById("r-active-root");
  if (activeRootEl && (!activeRootEl.textContent || activeRootEl.textContent.trim() === "")) {
    activeRootEl.className = "ctl-status loading";
    activeRootEl.textContent = uiLabel("research_loading");
  }
  var status = await researchApiGet("research/status");
  if (zoteroProjectId !== (status.project_id || null)) {
    clearZoteroSelection();
    zoteroProjectId = status.project_id || null;
  }
  if (activeRootEl && status && status.ok && status.project_root) {
    activeRootEl.className = "ctl-note";
    activeRootEl.textContent = uiLabel("research_project") + " " + status.project_root;
    if (status.initialized) {
      activeRootEl.textContent = uiFormat("research_project_summary", {
        root: status.project_root,
        sources: status.sources_count || 0,
        dossiers: status.dossiers_count || 0,
        claims: status.claims_count || 0,
        decisions: status.decisions_count || 0
      });
    }
  } else if (activeRootEl && status && !status.ok) {
    activeRootEl.className = "ctl-status err";
    activeRootEl.textContent = status.message || uiLabel("research_status_unavailable");
  }
  var ocrBox = document.getElementById("r-ocr-diagnostic-box");
  if (ocrBox && status && status.ocr) {
    var reading = ocrReading(status.ocr);
    var badgeClass = reading.badge;
    var labelText = reading.label;
    var guidanceText = reading.guidance;
    ocrBox.style.display = "flex";
    ocrBox.style.alignItems = "center";
    ocrBox.innerHTML = '<span class="badge ' + badgeClass + '" style="font-size:.75rem;padding:2px 6px;">' +
      escapeHtml(labelText) + '</span>' +
      (guidanceText ? '<small class="ctl-note" style="margin-left:.5rem;font-size:.72rem;">' + escapeHtml(guidanceText) + '</small>' : '');
  }
  return status;
}

(function initResearchSetup() {
  var button = document.getElementById("research-setup-check");
  if (!button) return;
  var ocrText = document.getElementById("setup-ocr-reading");
  var zoteroText = document.getElementById("setup-zotero-reading");
  var diagnostics = document.getElementById("setup-diagnostics");
  async function metadata(path) {
    try {
      var response = await fetch(API + "/research/" + path);
      if (!response.ok) return {ok: false};
      return await response.json();
    } catch (_) { return {ok: false}; }
  }
  button.addEventListener("click", async function() {
    if (button.disabled) return;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    ocrText.textContent = "OCR: " + uiLabel("research_loading");
    zoteroText.textContent = "Zotero: " + uiLabel("research_loading");
    try {
      var results = await Promise.all([metadata("ocr-status"), metadata("zotero-status")]);
      var ocr = results[0];
      var zotero = results[1];
      var reading = ocrReading(ocr.ok ? ocr : null);
      ocrText.textContent = "OCR: " + reading.label + " " + reading.guidance;
      var key = zotero.ok && zotero.status === "ready" ? "setup_zotero_ready"
        : zotero.ok && zotero.status === "connected" ? "setup_zotero_connected" : "setup_zotero_unavailable";
      zoteroText.textContent = uiLabel(key) + " " + uiLabel("setup_library_unchecked");
      var safeOcr = {};
      ["status", "backend", "pdftotext_available", "pdftoppm_available", "tesseract_available",
       "requested_languages", "available_languages", "missing_languages"].forEach(function(field) {
        if (Object.prototype.hasOwnProperty.call(ocr, field)) safeOcr[field] = ocr[field];
      });
      diagnostics.textContent = JSON.stringify({ocr: safeOcr, zotero: zotero}, null, 2);
    } finally {
      button.disabled = false;
      button.setAttribute("aria-busy", "false");
    }
  });
})();

async function initResearchUI() {
  researchStatus(uiLabel("research_loading"), "loading");
  var status = await refreshResearchProjectInfo();
  var initBox = document.getElementById("research-init-box");
  var tabs = document.getElementById("research-tabs");
  document.querySelectorAll(".research-tab-pane").forEach(function(p) { p.style.display = "none"; });

  if (!status || status.ok !== true) {
    if (initBox) initBox.style.display = "none";
    if (tabs) tabs.style.display = "none";
    researchStatus(uiFormat("research_api_unavailable", { reason: (status && status.message) || uiLabel("research_no_response") }), false);
    return;
  }

  if (!status.initialized) {
    if (initBox) initBox.style.display = "block";
    if (tabs) tabs.style.display = "none";
    document.querySelectorAll(".research-tab-pane").forEach(function(p) { p.style.display = "none"; });
    researchStatus("", true);
    return;
  }
  if (initBox) initBox.style.display = "none";
  if (tabs) tabs.style.display = "flex";
  var activeTab = document.querySelector(".research-tabs button.active");
  var targetPane = activeTab ? "rtab-" + activeTab.dataset.rtab : "rtab-sources";
  document.querySelectorAll(".research-tab-pane").forEach(function(p) {
    p.style.display = p.id === targetPane ? "block" : "none";
  });
  researchStatus("", true);
  refreshResearchSources(status);
  refreshResearchDossiers(status);
  refreshResearchClaims(status);
  refreshResearchDecisions(status);
  if (activeTab && activeTab.dataset.rtab === "review") refreshResearchEditorialReview();
}

document.addEventListener("click", async function (event) {
  var ackButton = event.target.closest("[data-decision-ack-status]");
  if (ackButton) {
    var pair = ackButton.closest(".research-decision-acknowledgement");
    if (!pair || ackButton.disabled || researchAcknowledgementPending || pair.dataset.decisionAckPending === "1") return;
    var payload = {decision_id: pair.dataset.decisionAckDecision, dossier_id: pair.dataset.decisionAckDossier,
      expected_snapshot: pair.dataset.decisionAckSnapshot,
      expected_decision_revision: Number(pair.dataset.decisionAckDecisionRevision),
      expected_dossier_revision: Number(pair.dataset.decisionAckDossierRevision), status: ackButton.dataset.decisionAckStatus};
    var feedback = pair.querySelector("[data-decision-ack-feedback]");
    var restoreFocus = document.activeElement === ackButton;
    var updatedPair;
    function movedFocus(event) {
      if (event.target !== ackButton && (!updatedPair || !updatedPair.contains(event.target))) restoreFocus = false;
    }
    function movedPointer(event) {
      if (!pair.contains(event.target) && (!updatedPair || !updatedPair.contains(event.target))) restoreFocus = false;
    }
    function stopTrackingFocus() {
      document.removeEventListener("focusin", movedFocus);
      document.removeEventListener("pointerdown", movedPointer);
    }
    document.addEventListener("focusin", movedFocus);
    document.addEventListener("pointerdown", movedPointer);
    researchAcknowledgementPending = true;
    pair.dataset.decisionAckPending = "1";
    ackButton.disabled = true;
    ackButton.setAttribute("aria-busy", "true");
    feedback.hidden = true;
    var acknowledged = await researchApiPost("research-decision-acknowledge", payload);
    if (!pair.isConnected) { researchAcknowledgementPending = false; stopTrackingFocus(); return; }
    delete pair.dataset.decisionAckPending;
    if (!acknowledged.ok) {
      ackButton.disabled = false;
      ackButton.removeAttribute("aria-busy");
      feedback.className = "ctl-status err";
      feedback.textContent = acknowledged.http_status === 409 ? uiLabel("research_decision_ack_conflict") :
        uiFormat("research_decision_ack_failed", {reason: acknowledged.message || uiLabel("wizard_unknown_error")});
      feedback.hidden = false;
      researchAcknowledgementPending = false;
      if (restoreFocus && (document.activeElement === ackButton || document.activeElement === document.body)) ackButton.focus();
      stopTrackingFocus();
      return;
    }
    var replacement = document.createElement("div");
    replacement.innerHTML = researchDecisionAcknowledgement({decisionId: payload.decision_id,
      decisionRevision: payload.expected_decision_revision, dossierId: payload.dossier_id,
      dossierRevision: payload.expected_dossier_revision, snapshot: acknowledged.snapshot,
      acknowledgement: {current: true, status: acknowledged.status}});
    document.querySelectorAll(".research-decision-acknowledgement").forEach(function(displayed) {
      if (displayed.dataset.decisionAckSnapshot !== payload.expected_snapshot) return;
      displayed.dataset.decisionAckSnapshot = acknowledged.snapshot;
      if (displayed.dataset.decisionAckDecision === payload.decision_id && displayed.dataset.decisionAckDossier === payload.dossier_id &&
          Number(displayed.dataset.decisionAckDecisionRevision) === payload.expected_decision_revision &&
          Number(displayed.dataset.decisionAckDossierRevision) === payload.expected_dossier_revision) {
        acknowledgeEditorialFlags(displayed, acknowledged.status);
        var next = replacement.firstElementChild.cloneNode(true);
        displayed.replaceWith(next);
        if (displayed === pair) updatedPair = next;
      }
    });
    if (restoreFocus && updatedPair && document.activeElement === document.body) updatedPair.querySelector("button").focus();
    await refreshResearchEditorialReview(true, acknowledged.snapshot);
    researchAcknowledgementPending = false;
    if (restoreFocus && updatedPair && !updatedPair.isConnected && document.activeElement === document.body) {
      var nextButton = document.querySelector("#research-editorial-review [data-decision-ack-status]");
      (nextButton || document.getElementById("r-review-refresh")).focus();
    }
    stopTrackingFocus();
    return;
  }
  var impactButton = event.target.closest("[data-decision-impact]");
  if (impactButton) {
    if (impactButton.parentElement.open) return;
    var impactHost = impactButton.parentElement.querySelector(".research-details-body");
    impactHost.textContent = uiLabel("research_loading");
    var impact = await researchApiGet("research/decision-impact?id=" + encodeURIComponent(impactButton.dataset.decisionImpact));
    impactHost.innerHTML = impact.ok ?
      '<p class="ctl-note">' + escapeHtml(uiLabel("research_editorial_decision_date")) + ': ' + researchEditorialTime(impact.decision.created_at) + '</p>' +
      (impact.unlinked ? '<p>' + escapeHtml(uiLabel("research_editorial_no_linked_dossier")) + '</p>' : impact.dossiers.map(function(dossier) {
        return researchAffectedDossier(dossier, impact);
      }).join("")) :
      '<p>' + escapeHtml(impact.message || uiLabel("research_status_unavailable")) + '</p>';
    return;
  }
  if (event.target.closest("#r-review-refresh")) {
    refreshResearchEditorialReview();
    return;
  }
  var contextualClaim = event.target.closest("[data-dossier-claim]");
  var contextualDecision = event.target.closest("[data-dossier-decision]");
  if (contextualClaim || contextualDecision) {
    var forContextClaim = Boolean(contextualClaim);
    var contextSelect = document.getElementById(forContextClaim ? "r-claim-dossier-select" : "r-decision-dossier-select");
    contextSelect.value = forContextClaim ? contextualClaim.dataset.dossierClaim : contextualDecision.dataset.dossierDecision;
    document.querySelector('[data-rtab="' + (forContextClaim ? "claims" : "decisions") + '"]').click();
    document.getElementById(forContextClaim ? "r-claim-options" : "r-decision-options").open = true;
    document.getElementById(forContextClaim ? "r-claim-title" : "r-decision-title").focus();
    return;
  }
  var passageBtn = event.target.closest("[data-use-passage]");
  if (passageBtn) {
    var forClaim = passageBtn.dataset.usePassage === "claim";
    var passageField = document.getElementById(forClaim ? "r-link-passage-id" : "r-dos-eids");
    if (!passageField) return;
    if (forClaim) {
      passageField.value = passageBtn.dataset.passageId;
    } else {
      var passageIds = passageField.value.split(",").map(function(id) { return id.trim(); }).filter(Boolean);
      if (!passageIds.includes(passageBtn.dataset.passageId)) passageIds.push(passageBtn.dataset.passageId);
      passageField.value = passageIds.join(", ");
    }
    document.querySelector('[data-rtab="' + (forClaim ? 'claims' : 'dossiers') + '"]').click();
    passageField.focus();
    return;
  }

  var detailsBtn = event.target.closest("[data-research-detail]");
  if (detailsBtn) {
    var detailHost = detailsBtn.parentElement.querySelector(".research-details-body");
    if (detailsBtn.parentElement.open) return;
    detailHost.textContent = uiLabel("research_details_loading");
    var isSource = detailsBtn.dataset.researchDetail === "source";
    var detail = await researchApiGet("research/" + (isSource ? "sources" : "dossiers") + "?id=" + encodeURIComponent(detailsBtn.dataset.recordId));
    if (!detail.ok) {
      detailHost.textContent = detail.message || uiLabel(isSource ? "research_load_sources_failed" : "research_load_dossiers_failed");
      return;
    }
    if (isSource) {
      var context = detail.context || {};
      var contextRows = ["genre", "created_period", "depicted_period", "place", "perspective", "original_language", "is_translation", "provenance_note", "origin_url"].filter(function(key) {
        return context[key] !== null && context[key] !== undefined && context[key] !== "";
      }).map(function(key) {
        var value = typeof context[key] === "boolean" ? uiLabel(context[key] ? "ctx_yes" : "ctx_no") : context[key];
        return '<dt>' + escapeHtml(uiLabel("ctx_" + key)) + '</dt><dd>' + escapeHtml(value) + '</dd>';
      }).join("");
      if (["image/png", "image/jpeg"].includes(detail.media_type)) {
        detailHost.innerHTML = '<p class="ctl-note">' + escapeHtml(uiLabel("research_context_unverified")) + '</p>' +
          '<p><strong>' + escapeHtml(detail.media_type) + '</strong> · ' + escapeHtml(uiLabel("image_text_unavailable")) + '</p>' +
          (contextRows ? '<h4>' + escapeHtml(uiLabel("research_source_context")) + '</h4><dl>' + contextRows + '</dl>' : '');
        return;
      }
      var fullDocText = detail.text || (detail.passages || []).map(function(p) { return p.verbatim; }).join("\n\n");
      var docRendered = fullDocText ? renderSafeMarkdown(fullDocText) : '<p class="ctl-note">' + escapeHtml(uiLabel("research_no_records")) + '</p>';
      var passagesCount = detail.passages ? detail.passages.length : 0;
      var passagesHtml = (detail.passages || []).map(function(p) {
        return researchCitationHtml({availability: "available", passage_id: p.id, verbatim: p.verbatim, source_title: detail.title});
      }).join("");

      detailHost.innerHTML = '<p class="ctl-note">' + escapeHtml(uiLabel("research_context_unverified")) + '</p>' +
        (contextRows ? '<h4>' + escapeHtml(uiLabel("research_source_context")) + '</h4><dl>' + contextRows + '</dl>' : '') +
        '<div class="research-source-view-bar">' +
          '<div class="row" style="gap:0.4rem;">' +
            '<button type="button" class="ctl ctl-sm active" data-source-view="doc">📄 ' + escapeHtml(uiLabel("research_doc_view")) + '</button>' +
            '<button type="button" class="ctl ctl-sm" data-source-view="passages">🔍 ' + escapeHtml(uiLabel("research_passages_view")) + ' (' + passagesCount + ')</button>' +
          '</div>' +
          '<button type="button" class="ctl ctl-sm research-source-toggle" data-source-toggle>' + escapeHtml(uiLabel("research_show_source")) + '</button>' +
        '</div>' +
        '<div class="research-source-doc-wrap">' +
          '<div class="research-prose markdown-body research-source-doc-rendered">' + docRendered + '</div>' +
          '<pre class="research-source-doc-raw" hidden>' + escapeHtml(fullDocText) + '</pre>' +
        '</div>' +
        '<div class="research-source-passages-wrap" hidden>' +
          '<h4>' + escapeHtml(uiLabel("research_passages")) + '</h4>' +
          passagesHtml +
        '</div>';
    } else {
      detailHost.innerHTML = researchDossierDetailHtml(detail);
    }
    return;
  }

  var sourceToggleBtn = event.target.closest("[data-source-toggle]");
  if (sourceToggleBtn) {
    var wrap = sourceToggleBtn.closest(".research-dossier-body-wrap");
    if (!wrap) wrap = sourceToggleBtn.parentElement.parentElement.querySelector(".research-source-doc-wrap");
    if (wrap) {
      var rendered = wrap.querySelector(".research-dossier-body-rendered, .research-source-doc-rendered");
      var source = wrap.querySelector(".research-dossier-body-source, .research-source-doc-raw");
      if (rendered && source) {
        var isSource = !source.hidden;
        source.hidden = isSource;
        rendered.hidden = !isSource;
        sourceToggleBtn.textContent = escapeHtml(uiLabel(isSource ? "research_show_source" : "research_show_preview"));
      }
    }
    return;
  }

  var sourceViewBtn = event.target.closest("[data-source-view]");
  if (sourceViewBtn) {
    var bar = sourceViewBtn.closest(".research-source-view-bar");
    if (bar) {
      var host = bar.parentElement;
      var docWrap = host.querySelector(".research-source-doc-wrap");
      var passWrap = host.querySelector(".research-source-passages-wrap");
      var toggleRawBtn = bar.querySelector("[data-source-toggle]");
      bar.querySelectorAll("[data-source-view]").forEach(function(b) { b.classList.remove("active"); });
      sourceViewBtn.classList.add("active");
      var isDoc = sourceViewBtn.dataset.sourceView === "doc";
      if (docWrap) docWrap.hidden = !isDoc;
      if (passWrap) passWrap.hidden = isDoc;
      if (toggleRawBtn) toggleRawBtn.style.display = isDoc ? "inline-block" : "none";
    }
    return;
  }

  var tabBtn = event.target.closest("[data-rtab]");
  if (tabBtn) {
    document.querySelectorAll(".research-tabs button").forEach(function(b) {
      b.classList.remove("active");
      b.setAttribute("aria-selected", "false");
    });
    tabBtn.classList.add("active");
    tabBtn.setAttribute("aria-selected", "true");
    var targetId = "rtab-" + tabBtn.dataset.rtab;
    document.querySelectorAll(".research-tab-pane").forEach(function(pane) {
      pane.style.display = pane.id === targetId ? "block" : "none";
    });
    if (tabBtn.dataset.rtab === "sources") refreshResearchSources();
    if (tabBtn.dataset.rtab === "dossiers") refreshResearchDossiers();
    if (tabBtn.dataset.rtab === "claims") refreshResearchClaims();
    if (tabBtn.dataset.rtab === "decisions") refreshResearchDecisions();
    if (tabBtn.dataset.rtab === "review") refreshResearchEditorialReview();
    return;
  }

  var initBtn = event.target.closest("#r-init-btn");
  if (initBtn) {
    var titleInput = document.getElementById("r-init-title");
    var res = await researchApiPost("research-init", { title: titleInput ? titleInput.value : "" });
    researchStatus(res.ok ? uiLabel("research_init_complete") : res.message, res.ok);
    if (res.ok) initResearchUI();
    return;
  }

  var ingestBtn = event.target.closest("#r-ingest-btn");
  if (ingestBtn) {
    var retCheck = document.getElementById("r-ingest-retention");
    if (!retCheck || !retCheck.checked) {
      researchStatus(uiLabel("research_retention_required"), false);
      return;
    }
    var originEl = document.getElementById("r-ingest-origin-url");
    var originUrl = originEl ? originEl.value.trim() : "";
    if (originUrl) {
      try {
        var parsedOrigin = new URL(originUrl);
        if (!["http:", "https:"].includes(parsedOrigin.protocol) || parsedOrigin.username || parsedOrigin.password || /[\s\\]/.test(originUrl)) throw new Error("invalid");
      } catch (_) {
        researchStatus(uiLabel("research_origin_url_invalid"), false);
        if (originEl) originEl.focus();
        return;
      }
    }
    var titleEl = document.getElementById("r-ingest-title");
    var tagsEl = document.getElementById("r-ingest-tags");
    var textEl = document.getElementById("r-ingest-text");
    var fileEl = document.getElementById("r-ingest-file");
    var tags = (tagsEl && tagsEl.value) ? tagsEl.value.split(",").map(function(t){ return t.trim(); }).filter(Boolean) : [];

    function sendIngest(content, filename, isBase64) {
      researchStatus(uiLabel("research_ingesting_extracting") || uiLabel("research_ingesting"), true);
      if (ingestBtn) ingestBtn.disabled = true;
      var payload = {
        title: (titleEl && titleEl.value.trim()) || filename || uiLabel("research_tab_sources"),
        filename: filename,
        origin_url: originUrl || null,
        tags: tags,
        allow_retention: true
      };
      if (isBase64) {
        payload.content_base64 = content;
      } else {
        payload.content = content;
      }
      researchApiPost("research-ingest", payload).then(function(res) {
        if (ingestBtn) ingestBtn.disabled = false;
        var msg = res.ok
          ? (uiLabel("research_ingest_complete") + (res.passages ? " (" + res.passages + " passages)" : ""))
          : (res.message || "Failed");
        if (res.ok && Array.isArray(res.warnings) && res.warnings.length) {
          msg += " " + res.warnings.join(" ");
        }
        researchStatus(msg, res.ok);
        if (res.ok) {
          if (titleEl) titleEl.value = "";
          if (originEl) originEl.value = "";
          if (tagsEl) tagsEl.value = "";
          if (textEl) textEl.value = "";
          if (fileEl) fileEl.value = "";
          retCheck.checked = false;
          refreshResearchSources();
        }
      }).catch(function(err) {
        if (ingestBtn) ingestBtn.disabled = false;
        researchStatus(String(err), false);
      });
    }

    if (fileEl && fileEl.files && fileEl.files.length) {
      var file = fileEl.files[0];
      researchStatus(uiLabel("research_ingesting_reading") || "Reading file…", true);
      var isPdf = file.name.toLowerCase().endsWith(".pdf");
      var reader = new FileReader();
      if (isPdf) {
        reader.onload = function() {
          var dataUrl = String(reader.result || "");
          var base64 = dataUrl.split(",")[1] || "";
          sendIngest(base64, file.name, true);
        };
        reader.readAsDataURL(file);
      } else {
        reader.onload = function() { sendIngest(reader.result, file.name, false); };
        reader.readAsText(file);
      }
    } else if (textEl && textEl.value.trim()) {
      sendIngest(textEl.value, "", false);
    } else {
      researchStatus(uiLabel("research_source_required"), false);
    }
    return;
  }

function highlightSearchTerms(text, query) {
  if (!text || !query) return escapeHtml(text || "");
  var terms = query.trim().split(/\s+/).filter(function(t) { return t.length > 0; });
  if (!terms.length) return escapeHtml(text);
  var escapedTerms = terms.map(function(t) { return t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); });
  var regex = new RegExp('(' + escapedTerms.join('|') + ')', 'gi');
  var escaped = escapeHtml(text);
  return escaped.replace(regex, '<mark class="search-hit">$1</mark>');
}

  var searchBtn = event.target.closest("#r-search-btn");
  if (searchBtn) {
    var qEl = document.getElementById("r-search-query");
    var query = qEl ? qEl.value.trim() : "";
    if (!query) { researchStatus(uiLabel("research_query_required"), false); return; }
    var resultsHost = document.getElementById("research-search-results");
    if (resultsHost) resultsHost.innerHTML = '<p class="ctl-note">' + escapeHtml(uiLabel("research_searching")) + '</p>';
    var scopeEl = document.getElementById("r-search-scope");
    var sres = await researchApiPost("research-search", { query: query, scope: scopeEl ? scopeEl.value : "sources" });
    if (!sres.ok) {
      if (resultsHost) resultsHost.innerHTML = '<p class="ctl-note">' + escapeHtml(sres.message || uiLabel("research_search_failed")) + '</p>';
      researchStatus(sres.message || uiLabel("research_search_failed"), false);
      return;
    }
    var hits = sres.hits || [];
    if (!hits.length) {
      var currentScope = scopeEl ? scopeEl.value : "sources";
      var scopeHint = "";
      if (currentScope !== "all") {
        scopeHint = '<div style="margin-top:.5rem;">' +
          '<span class="ctl-note">' + escapeHtml(uiLabel("research_search_scope_hint")) + ' </span>' +
          '<button type="button" class="ctl ctl-sm" id="r-search-all-btn">' + escapeHtml(uiLabel("research_search_all_records")) + '</button>' +
          '</div>';
      }
      if (resultsHost) resultsHost.innerHTML = '<p class="ctl-note">' + escapeHtml(uiFormat("research_no_hits", { query: query })) + '</p>' + scopeHint;
      researchStatus(uiFormat("research_no_hits", { query: query }), true);
      return;
    }
    if (resultsHost) {
      resultsHost.innerHTML = hits.map(function(h) {
        if (["dossier", "claim", "decision"].indexOf(h.kind) !== -1) {
          var statusLabel = h.kind === "claim"
            ? uiLabel("research_confidence_" + h.confidence)
            : h.kind === "decision" ? uiLabel(h.deviation_from_fact ? "research_deliberate_deviation" : "research_no_deviation_recorded") : "";
          return '<div class="research-passage-card">' +
            '<div class="research-card-title">' + escapeHtml(h.title || "") + '</div>' +
            '<div class="ctl-note">' + escapeHtml(uiLabel("research_revision_kind_" + h.kind)) + ' · ' +
              escapeHtml(uiFormat("research_revision_number", {revision: h.revision})) + '</div>' +
            (statusLabel ? '<div class="ctl-note">' + escapeHtml(statusLabel) + '</div>' : '') +
            '<p class="research-passage-quote">' + highlightSearchTerms(h.excerpt || "", query) + '</p>' +
            '<button type="button" class="ctl" data-research-history="' + h.kind + '" data-record-id="' + escapeHtml(h.record_id) + '">' +
              escapeHtml(uiLabel("research_view_details")) + '</button></div>';
        }
        return '<div class="research-passage-card">' +
          '<div class="research-passage-quote">„' + highlightSearchTerms(h.verbatim || "", query) + '“</div>' +
          '<div class="research-passage-cite">' +
            escapeHtml(uiLabel("research_source")) + ' <strong>' + escapeHtml(h.source_title || "") + '</strong> · ' +
            'Score: ' + (h.rank_score !== undefined ? Number(h.rank_score).toFixed(2) : 'n/a') + ' · ' +
            escapeHtml(uiLabel("research_id")) + ' <code style="user-select:all;cursor:pointer;" title="' + escapeHtml(uiLabel("research_select_id")) + '">' + escapeHtml(h.passage_id || "") + '</code>' +
          '</div>' +
          researchPassageActions(h.passage_id) +
        '</div>';
      }).join("");
    }
    researchStatus(uiFormat("research_hits_count", { count: hits.length }), true);
    return;
  }

  var searchAllBtn = event.target.closest("#r-search-all-btn");
  if (searchAllBtn) {
    var scopeSel = document.getElementById("r-search-scope");
    if (scopeSel) scopeSel.value = "all";
    var sBtn = document.getElementById("r-search-btn");
    if (sBtn) sBtn.click();
    return;
  }

  var dosBtn = event.target.closest("#r-dos-create-btn");
  if (dosBtn) {
    var dTitle = document.getElementById("r-dos-title");
    var dTags = document.getElementById("r-dos-tags");
    var dEids = document.getElementById("r-dos-eids");
    var dBody = document.getElementById("r-dos-body");
    var titleVal = dTitle ? dTitle.value.trim() : "";
    if (!titleVal) { researchStatus(uiLabel("research_dossier_title_required"), false); return; }
    var tagsArr = (dTags && dTags.value) ? dTags.value.split(",").map(function(t){ return t.trim(); }).filter(Boolean) : [];
    var eidsArr = (dEids && dEids.value) ? dEids.value.split(",").map(function(t){ return t.trim(); }).filter(Boolean) : [];
    var dres = await researchApiPost("research-dossier", {
      title: titleVal,
      body: dBody ? dBody.value : "",
      tags: tagsArr,
      evidence_ids: eidsArr
    });
    researchStatus(dres.ok ? uiLabel("research_dossier_complete") : dres.message, dres.ok);
    if (dres.ok) {
      if (dTitle) dTitle.value = "";
      if (dTags) dTags.value = "";
      if (dEids) dEids.value = "";
      if (dBody) dBody.value = "";
      refreshResearchDossiers();
    }
    return;
  }

  var groundBtn = event.target.closest("#r-ground-btn");
  if (groundBtn) {
    var srcSelect = document.getElementById("r-ground-source-select");
    var sid = srcSelect ? srcSelect.value : "";
    if (!sid) { researchStatus(uiLabel("research_select_source_required"), false); return; }
    var gHost = document.getElementById("research-grounding-results");
    if (gHost) gHost.innerHTML = '<p class="ctl-note">' + escapeHtml(uiLabel("research_grounding")) + '</p>';
    var gres = await researchApiPost("research-compare", { source_id: sid });
    if (!gres.ok) {
      if (gHost) gHost.innerHTML = '<p class="ctl-note">' + escapeHtml(gres.message || uiLabel("research_ground_failed")) + '</p>';
      researchStatus(gres.message || uiLabel("research_ground_failed"), false);
      return;
    }
    var sum = gres.summary || {};
    var comparisonMeta = gres.meta || {};
    var crossLanguage = comparisonMeta.source_language && comparisonMeta.manuscript_language &&
      comparisonMeta.source_language !== comparisonMeta.manuscript_language;
    var topShared = (gres.lexical_overlap && gres.lexical_overlap.top_shared_terms) || [];
    var sharedWordsHtml = topShared.slice(0, 15).map(function(w) {
      return '<span class="research-tag">' + escapeHtml(w.word) + ' (' + w.total_count + ')</span>';
    }).join(" ");

    var sourceKeyTerms = (gres.keyness && gres.keyness.source_key_terms) || [];
    var keyTermsHtml = sourceKeyTerms.slice(0, 15).map(function(k) {
      return '<span class="research-tag" style="border-color:var(--accent);">' + escapeHtml(k.word) + ' (G² ' + k.g2 + ')</span>';
    }).join(" ");

    var chapters = gres.chapter_grounding || [];
    var chRows = chapters.map(function(c) {
      return '<tr>' +
        '<td>' + escapeHtml(uiLabel("research_chapter_prefix")) + ' ' + c.chapter + ' (' + escapeHtml(c.title || "") + ')</td>' +
        '<td style="text-align:right;">' + c.overlap_tokens + '</td>' +
        '<td style="text-align:right;">' + (c.grounding_density ? c.grounding_density.toFixed(1) : '0') + '‰</td>' +
      '</tr>';
    }).join("");

    if (gHost) {
      gHost.innerHTML = '<div class="research-card" style="margin-top:.8rem;">' +
        '<div class="research-card-title" style="margin-bottom:.5rem;">' + escapeHtml(uiLabel("research_results_for")) + ' ' + escapeHtml(gres.provenance ? gres.provenance.source_title : "") + '</div>' +
        '<p class="ctl-note">' + escapeHtml(uiLabel("research_comparison_limit")) + '</p>' +
        (crossLanguage ? '<p class="ctl-note research-comparison-warning" role="status">' + escapeHtml(uiLabel("research_cross_language_limit")) + '</p>' : '') +
        '<div class="research-compare-metric"><span>' + escapeHtml(uiLabel("research_similarity")) + '</span><strong>' + (sum.jaccard_similarity !== undefined ? (sum.jaccard_similarity * 100).toFixed(1) + '%' : 'n/a') + '</strong></div>' +
        '<div class="research-compare-metric"><span>' + escapeHtml(uiLabel("research_shared_types")) + '</span><strong>' + (sum.shared_types || 0) + '</strong></div>' +
        '<div class="research-compare-metric"><span>' + escapeHtml(uiLabel("research_word_counts")) + '</span><span>' + (sum.source_content_words || 0) + ' / ' + (sum.manuscript_content_words || 0) + '</span></div>' +
        (sharedWordsHtml ? '<div style="margin-top:.6rem;"><div class="ctl-label" style="margin-bottom:.3rem;">' + escapeHtml(uiLabel("research_shared_words")) + '</div><div class="research-tags">' + sharedWordsHtml + '</div></div>' : '') +
        (keyTermsHtml ? '<div style="margin-top:.6rem;"><div class="ctl-label" style="margin-bottom:.3rem;">' + escapeHtml(uiLabel("research_source_key_terms")) + '</div><div class="research-tags">' + keyTermsHtml + '</div></div>' : '') +
        (chRows ? '<div style="margin-top:.8rem;"><div class="ctl-label" style="margin-bottom:.3rem;">' + escapeHtml(uiLabel("research_chapter_density")) + '</div><table style="width:100%;font-size:.8rem;"><thead><tr><th style="text-align:left;">' + escapeHtml(uiLabel("research_chapter")) + '</th><th style="text-align:right;">' + escapeHtml(uiLabel("research_tokens")) + '</th><th style="text-align:right;">' + escapeHtml(uiLabel("research_density")) + '</th></tr></thead><tbody>' + chRows + '</tbody></table></div>' : '') +
      '</div>';
    }
    researchStatus(uiLabel("research_ground_complete"), true);
    return;
  }

  var claimBtn = event.target.closest("#r-claim-create-btn");
  if (claimBtn) {
    var cTitle = document.getElementById("r-claim-title");
    var cConf = document.getElementById("r-claim-confidence");
    var cTags = document.getElementById("r-claim-tags");
    var cStmt = document.getElementById("r-claim-statement");
    var cTime = document.getElementById("r-claim-time");
    var cPlace = document.getElementById("r-claim-place");
    var cActors = document.getElementById("r-claim-actors");
    var cDossier = document.getElementById("r-claim-dossier-select");

    var titleVal = cTitle ? cTitle.value.trim() : "";
    var stmtVal = cStmt ? cStmt.value.trim() : "";
    if (!titleVal || !stmtVal) {
      researchStatus(uiLabel("research_claim_required"), false);
      return;
    }
    var tagsArr = (cTags && cTags.value) ? cTags.value.split(",").map(function(t){ return t.trim(); }).filter(Boolean) : [];
    var actorsArr = (cActors && cActors.value) ? cActors.value.split(",").map(function(a){ return a.trim(); }).filter(Boolean) : [];

    var cres = await researchApiPost("research-claim-add", {
      title: titleVal,
      statement: stmtVal,
      confidence: cConf ? cConf.value : "hypothetical",
      time_period: cTime ? cTime.value.trim() : "",
      place: cPlace ? cPlace.value.trim() : "",
      actors: actorsArr,
      dossier_id: cDossier ? cDossier.value : "",
      tags: tagsArr
    });
    researchStatus(cres.ok ? uiLabel("research_claim_complete") : cres.message, cres.ok);
    if (cres.ok) {
      if (cTitle) cTitle.value = "";
      if (cStmt) cStmt.value = "";
      if (cTags) cTags.value = "";
      if (cTime) cTime.value = "";
      if (cPlace) cPlace.value = "";
      if (cActors) cActors.value = "";
      refreshResearchClaims();
    }
    return;
  }

  var matrixBtn = event.target.closest("#r-claim-matrix-btn");
  if (matrixBtn) {
    try {
      var resp = await fetch((API || "/api") + "/research/matrix?format=md");
      if (!resp.ok) {
        researchStatus("Failed to generate claim matrix", false);
        return;
      }
      var mdText = await resp.text();
      var blob = new Blob([mdText], { type: "text/markdown;charset=utf-8" });
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = "claim-evidence-matrix.md";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      researchStatus("Claim matrix exported successfully", true);
    } catch (e) {
      researchStatus("Export failed: " + (e.message || e), false);
    }
    return;
  }

  var linkEvBtn = event.target.closest("#r-link-evidence-btn");
  if (linkEvBtn) {
    var lClaim = document.getElementById("r-link-claim-select");
    var lPassage = document.getElementById("r-link-passage-id");
    var lRel = document.getElementById("r-link-relation");
    var lRat = document.getElementById("r-link-rationale");

    var claimVal = lClaim ? lClaim.value.trim() : "";
    var passageVal = lPassage ? lPassage.value.trim() : "";
    if (!claimVal || !passageVal) {
      researchStatus(uiLabel("research_link_required"), false);
      return;
    }

    var lres = await researchApiPost("research-evidence-link", {
      claim_id: claimVal,
      passage_id: passageVal,
      relation: lRel ? lRel.value : "supports",
      rationale: lRat ? lRat.value.trim() : ""
    });
    researchStatus(lres.ok ? uiLabel("research_evidence_link_complete") : lres.message, lres.ok);
    if (lres.ok) {
      if (lPassage) lPassage.value = "";
      if (lRat) lRat.value = "";
      refreshResearchClaims();
    }
    return;
  }

  var decBtn = event.target.closest("#r-decision-create-btn");
  if (decBtn) {
    var decTitle = document.getElementById("r-decision-title");
    var decClaim = document.getElementById("r-decision-claim-select");
    var decRat = document.getElementById("r-decision-rationale");
    var decPlot = document.getElementById("r-decision-plot");
    var decDev = document.getElementById("r-decision-deviation");
    var decDossier = document.getElementById("r-decision-dossier-select");

    var dTitleVal = decTitle ? decTitle.value.trim() : "";
    var dRatVal = decRat ? decRat.value.trim() : "";
    if (!dTitleVal || !dRatVal) {
      researchStatus(uiLabel("research_decision_required"), false);
      return;
    }

    var dres = await researchApiPost("research-decision-add", {
      title: dTitleVal,
      rationale: dRatVal,
      claim_id: decClaim ? decClaim.value.trim() : "",
      dossier_ids: decDossier && decDossier.value ? [decDossier.value] : [],
      impact_on_plot: decPlot ? decPlot.value.trim() : "",
      deviation_from_fact: decDev ? decDev.checked : false
    });
    researchStatus(dres.ok ? uiLabel("research_decision_complete") : dres.message, dres.ok);
    if (dres.ok) {
      if (decTitle) decTitle.value = "";
      if (decRat) decRat.value = "";
      if (decPlot) decPlot.value = "";
      if (decDev) decDev.checked = false;
      refreshResearchDecisions();
    }
    return;
  }

  var loadEvBtn = event.target.closest("[data-load-evidence]");
  if (loadEvBtn) {
    var cid = loadEvBtn.dataset.loadEvidence;
    var subpanel = document.getElementById("claim-evidence-" + cid);
    if (!subpanel) return;
    subpanel.innerHTML = '<span class="ctl-note">' + escapeHtml(uiLabel("research_loading_evidence")) + '</span>';
    var evData = await researchApiGet("research/claims?claim_id=" + encodeURIComponent(cid));
    if (!evData.ok) {
      subpanel.innerHTML = '<span class="ctl-note">' + escapeHtml(evData.message || uiLabel("research_load_evidence_failed")) + '</span>';
      return;
    }
    var links = evData.evidence_links || [];
    if (!links.length) {
      subpanel.innerHTML = '<span class="ctl-note">' + escapeHtml(uiLabel("research_no_linked_evidence")) + '</span>';
      return;
    }
    subpanel.innerHTML = '<div style="font-size:.78rem;font-weight:600;margin-bottom:.3rem;color:var(--fg);">' + escapeHtml(uiFormat("research_linked_evidence_count", { count: links.length })) + '</div>' +
      links.map(function(l) {
        var relBadge = '<span class="research-badge badge-neutral" style="font-size:.7rem;">' + escapeHtml(uiLabel("research_relation_" + l.relation)) + '</span>';
        var cite = l.citation || {};
        var unavailable = Boolean(cite.error) || !cite.availability;
        var withdrawn = cite.availability === "withdrawn";
        var availability = unavailable ? uiLabel("research_evidence_unavailable") : (withdrawn ? uiLabel("research_evidence_withdrawn_context") : uiLabel("research_evidence_retained_unreviewed"));
        var quote = !unavailable && cite.verbatim ? '„' + escapeHtml(cite.verbatim) + '“' : '<em>' + escapeHtml(uiLabel("research_no_quote")) + '</em>';
        return '<div class="research-passage-card" style="margin:.3rem 0;padding:.4rem .6rem;">' +
          '<div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.2rem;">' +
            relBadge +
            '<span class="research-badge ' + (unavailable || withdrawn ? 'badge-warning' : 'badge-neutral') + '">' + escapeHtml(availability) + '</span>' +
            '<span class="ctl-note" style="font-size:.74rem;">' + escapeHtml(cite.source_title || l.passage_id) + '</span>' +
          '</div>' +
          '<div class="research-passage-quote" style="font-size:.78rem;margin:.2rem 0;">' + quote + '</div>' +
          (l.rationale ? '<div class="ctl-note" style="font-size:.72rem;">' + escapeHtml(l.rationale) + '</div>' : '') +
          (l.revision ? '<div class="ctl-note">' + escapeHtml(uiFormat("research_revision_number", { revision: l.revision })) + '</div>' : '') +
          (l.claim_revision && l.claim_latest_revision && Number(l.claim_revision) < Number(l.claim_latest_revision)
            ? '<div class="ctl-note">' + escapeHtml(uiFormat("research_revision_pinned_claim", { revision: l.claim_revision })) + '</div>' : '') +
          researchRevisionActions("evidence_link", l.id) +
        '</div>';
      }).join("");
    return;
  }
});

// One revision dialog serves all authored research records. References are
// edited by ID; the API preserves their pinned revisions when IDs are unchanged.
var researchRevisionDialog = document.getElementById("modal-research-revision");
if (researchRevisionDialog) {
  var revisionForm = document.getElementById("research-revision-form");
  var revisionFieldsHost = document.getElementById("research-revision-fields");
  var revisionEditTab = document.getElementById("research-revision-edit-tab");
  var revisionHistoryTab = document.getElementById("research-revision-history-tab");
  var revisionHistoryPane = document.getElementById("research-revision-history");
  var revisionHistoryList = document.getElementById("research-revision-history-list");
  var revisionHistoryDetail = document.getElementById("research-revision-history-detail");
  var revisionStatusHost = document.getElementById("research-revision-status");
  var revisionMeta = document.getElementById("research-revision-kind");
  var revisionIdentifier = document.getElementById("research-revision-identifier");
  var revisionSnapshot = document.getElementById("research-revision-snapshot");
  var revisionUpdates = document.getElementById("research-revision-source-updates");
  var revisionCitationsWrap = document.getElementById("research-revision-citations-wrap");
  var revisionCitations = document.getElementById("research-revision-citations");
  var revisionReason = document.getElementById("research-revision-reason");
  var revisionSave = document.getElementById("research-revision-save");
  var revisionReload = document.getElementById("research-revision-reload");
  var revisionMerge = document.getElementById("research-revision-merge");
  var revisionMergeFields = document.getElementById("research-revision-merge-fields");
  var revisionMergeApply = document.getElementById("research-revision-merge-apply");
  var revisionBatchAdd = document.getElementById("research-revision-batch-add");
  var revisionBatchReview = document.getElementById("research-revision-batch-review");
  var revisionBatchDialog = document.getElementById("modal-research-revision-batch");
  var revisionBatchList = document.getElementById("research-revision-batch-list");
  var revisionBatchStatusHost = document.getElementById("research-revision-batch-status");
  var revisionBatchCheck = document.getElementById("research-revision-batch-check");
  var revisionBatchApply = document.getElementById("research-revision-batch-apply");
  var revisionBatch = {projectId: null, entries: [], preview: null, pending: false, request: 0};
  var revisionState = {kind: "", id: "", session: 0, request: 0, historyRequest: 0,
    current: null, initial: {}, dossierPins: {}, mode: "edit", historyLoaded: false, pending: false, merge: null,
    section: null, sectionBase: null, sectionContent: null};

  function revisionEditableSpecs() {
    return (revisionSpecs[revisionState.kind] || []).filter(function(spec) { return !revisionState.section || spec.name === "body"; });
  }

  function revisionSectionEndpoint(number) {
    return "research/dossiers?id=" + encodeURIComponent(revisionState.id) + "&revision=" + encodeURIComponent(number) +
      "&section=" + encodeURIComponent(revisionState.section);
  }

  function revisionShowMeta(envelope) {
    var record = envelope && envelope.record;
    revisionMeta.textContent = uiLabel("research_revision_kind_" + revisionState.kind) +
      (record ? " · " + uiFormat("research_revision_number", {revision: record.revision}) : "") +
      (revisionState.section ? " · " + uiFormat("research_section_editing", {section: revisionState.section}) : "");
    revisionIdentifier.textContent = revisionState.id;
    revisionSnapshot.textContent = envelope ? envelope.snapshot || "" : "";
  }

  var revisionSpecs = {
    dossier: [
      {name: "title", label: "research_dossier_title", required: true},
      {name: "body", label: "research_dossier_body", type: "textarea", required: true},
      {name: "tags", label: "research_tags", type: "list"},
      {name: "evidence_ids", label: "research_evidence_ids", type: "list"}
    ],
    claim: [
      {name: "title", label: "research_claim_title", required: true},
      {name: "statement", label: "research_claim_statement", type: "textarea", required: true},
      {name: "confidence", label: "research_confidence_field", type: "select", options: [
        ["hypothetical", "research_confidence_hypothetical"], ["evidenced", "research_confidence_evidenced"], ["disputed", "research_confidence_disputed"]]},
      {name: "time_period", label: "research_claim_time"},
      {name: "place", label: "research_claim_place"},
      {name: "actors", label: "research_claim_actors", type: "list"},
      {name: "dossier_id", label: "research_dossier"},
      {name: "dossier_revision", label: "research_revision_dossier_revision", type: "number"},
      {name: "tags", label: "research_tags", type: "list"}
    ],
    evidence_link: [
      {name: "claim_id", label: "research_claim_id", required: true},
      {name: "claim_revision", label: "research_revision_claim_revision", type: "number"},
      {name: "passage_id", label: "research_passage_id", required: true},
      {name: "relation", label: "research_relation_field", type: "select", options: [
        ["supports", "research_relation_supports"], ["contradicts", "research_relation_contradicts"],
        ["qualifies", "research_relation_qualifies"], ["contextualizes", "research_relation_contextualizes"]]},
      {name: "rationale", label: "research_link_rationale", type: "textarea"},
      {name: "reviewer", label: "research_revision_reviewer", required: true}
    ],
    decision: [
      {name: "title", label: "research_decision_title", required: true},
      {name: "rationale", label: "research_decision_rationale", type: "textarea", required: true},
      {name: "claim_id", label: "research_claim_id"},
      {name: "claim_revision", label: "research_revision_claim_revision", type: "number"},
      {name: "deviation_from_fact", label: "research_deviation_checkbox", type: "checkbox"},
      {name: "impact_on_plot", label: "research_decision_plot", type: "textarea"},
      {name: "dossier_ids", label: "research_revision_dossier_ids", type: "list"}
    ]
  };

  function revisionRefText(ref, pinned) {
    if (!ref || !ref.id) return "";
    return ref.id + (pinned && ref.revision ? " · " + uiFormat("research_revision_number", {revision: ref.revision}) : "");
  }

  function revisionFieldValue(record, name, pinned) {
    if (name === "evidence_ids") return (record.evidence_refs || []).map(function(ref) { return revisionRefText(ref, pinned); });
    if (name === "dossier_ids") return (record.dossier_refs || []).map(function(ref) { return revisionRefText(ref, pinned); });
    if (name === "dossier_revisions") return Object.fromEntries((record.dossier_refs || []).map(function(ref) { return [ref.id, ref.revision]; }));
    if (name === "dossier_id") return revisionRefText(record.dossier_ref, pinned);
    if (name === "dossier_revision") return record.dossier_ref ? record.dossier_ref.revision : "";
    if (name === "claim_id") return revisionRefText(record.claim_ref, pinned);
    if (name === "claim_revision") return record.claim_ref ? record.claim_ref.revision : "";
    if (name === "passage_id") return revisionRefText(record.passage_ref, pinned);
    if (["time_period", "place", "actors"].includes(name)) return (record.scope || {})[name] || (name === "actors" ? [] : "");
    return record[name] === null || record[name] === undefined ? "" : record[name];
  }

  function revisionStatus(message, error) {
    revisionStatusHost.textContent = message || "";
    revisionStatusHost.hidden = !message;
    revisionStatusHost.className = "ctl-status" + (error ? " err" : "");
  }

  function revisionNotices(envelope) {
    revisionUpdates.replaceChildren();
    var updates = (envelope && envelope.source_updates) || [];
    var references = (envelope && envelope.reference_updates) || [];
    var scopedCitations = envelope && envelope.citation_scope === "current_links_to_pinned_claim_revision" &&
      envelope.citations && envelope.citations.length;
    revisionUpdates.hidden = !updates.length && !references.length && !scopedCitations;
    if (revisionUpdates.hidden) return;
    if (updates.length) {
      var note = document.createElement("p");
      note.textContent = uiLabel("research_revision_newer_source");
      var list = document.createElement("ul");
      updates.forEach(function(update) {
        var item = document.createElement("li");
        item.textContent = uiFormat("research_revision_source_versions", {
          source: update.source_title || update.source_id || "",
          cited: update.cited_sequence || "?", latest: update.latest_sequence || "?"
        });
        list.appendChild(item);
      });
      revisionUpdates.append(note, list);
    }
    references.forEach(function(ref) {
      var note = document.createElement("p");
      note.textContent = uiFormat("research_revision_reference_update", {
        kind: uiLabel("research_revision_kind_" + ref.kind),
        pinned: ref.pinned_revision, latest: ref.latest_revision
      });
      revisionUpdates.appendChild(note);
    });
    if (scopedCitations) {
      var scopeNote = document.createElement("p");
      scopeNote.textContent = uiLabel("research_revision_citation_scope");
      revisionUpdates.appendChild(scopeNote);
    }
  }

  function revisionShowCitations(citations) {
    revisionCitationsWrap.hidden = !citations || !citations.length;
    revisionCitations.innerHTML = (citations || []).map(function(cite) {
      return researchCitationHtml(cite, false);
    }).join("");
  }

  function revisionBuildFields(record) {
    revisionFieldsHost.replaceChildren();
    revisionState.merge = null;
    revisionMerge.hidden = true;
    revisionState.initial = {};
    revisionState.dossierPins = revisionFieldValue(record, "dossier_revisions", false);
    var options = document.createElement("details");
    options.className = "research-details";
    options.id = "research-revision-options";
    var summary = document.createElement("summary");
    summary.textContent = uiLabel("optional_details");
    options.appendChild(summary);
    revisionEditableSpecs().forEach(function(spec) {
      var raw = revisionState.section && spec.name === "body" ? revisionState.sectionContent : revisionFieldValue(record, spec.name, false);
      var value = Array.isArray(raw) ? raw.slice() : raw;
      revisionState.initial[spec.name] = value;
      var id = "research-revision-field-" + spec.name;
      var group = document.createElement("div");
      group.className = "form-group";
      var field;
      if (spec.type === "checkbox") {
        var checkLabel = document.createElement("label");
        checkLabel.className = "form-checkbox";
        field = document.createElement("input");
        field.type = "checkbox";
        field.checked = Boolean(value);
        var checkText = document.createElement("span");
        checkText.textContent = uiLabel(spec.label);
        checkLabel.append(field, checkText);
        group.appendChild(checkLabel);
      } else {
        var label = document.createElement("label");
        label.className = "form-label";
        label.htmlFor = id;
        label.textContent = uiLabel(spec.label);
        group.appendChild(label);
        field = spec.type === "textarea" ? document.createElement("textarea") :
          spec.type === "select" ? document.createElement("select") : document.createElement("input");
        field.className = "ctl";
        if (spec.type === "textarea") field.rows = spec.name === "body" ? 8 : 3;
        if (spec.type === "select") {
          (spec.options || []).forEach(function(option) {
            var item = document.createElement("option");
            item.value = option[0];
            item.textContent = uiLabel(option[1]);
            field.appendChild(item);
          });
        } else if (field.tagName === "INPUT") {
          field.type = spec.type === "number" ? "number" : "text";
          if (spec.type === "number") { field.min = "1"; field.step = "1"; }
        }
        field.value = Array.isArray(value) ? value.join(", ") : String(value || "");
        field.required = Boolean(spec.required);
        group.appendChild(field);
      }
      field.id = id;
      field.name = spec.name;
      var optional = !spec.required && !["confidence", "relation"].includes(spec.name);
      if (optional) options.appendChild(group);
      else revisionFieldsHost.appendChild(group);
    });
    if (options.children.length > 1) revisionFieldsHost.appendChild(options);
    ["claim", "dossier"].forEach(function(kind) {
      var idField = document.getElementById("research-revision-field-" + kind + "_id");
      var revisionField = document.getElementById("research-revision-field-" + kind + "_revision");
      if (idField && revisionField) idField.addEventListener("input", function() {
        if (idField.value.trim() !== revisionState.initial[kind + "_id"]) revisionField.value = "";
      });
    });
    revisionReason.value = "";
    revisionForm.querySelectorAll('input[name="research_revision_change_kind"]').forEach(function(input) { input.checked = false; });
    revisionReload.hidden = true;
    revisionUpdateQueueControls();
  }

  function revisionReadOnly(envelope) {
    var record = envelope.record || {};
    var fields = revisionSpecs[revisionState.kind] || [];
    var rows = fields.map(function(spec) {
      var value = revisionFieldValue(record, spec.name, true);
      if (Array.isArray(value)) value = value.join(", ");
      var valHtml = spec.name === "body" && value ?
        researchDossierBodyHtml(value, envelope) :
        escapeHtml(value || "—");
      return '<dt>' + escapeHtml(uiLabel(spec.label)) + '</dt><dd>' + valHtml + '</dd>';
    }).join("");
    var change = record.change;
    var changeText = change ? uiLabel("research_revision_" + change.change_kind) + ": " + change.reason : uiLabel("research_revision_original");
    return '<div class="research-revision-history-detail">' +
      '<h4>' + escapeHtml(uiFormat("research_revision_number", {revision: record.revision})) + '</h4>' +
      '<p class="ctl-note">' + escapeHtml(changeText) + ' · ' + escapeHtml(record.created_at || "") + ' · ' + escapeHtml(record.created_by || "") + '</p>' +
      '<dl class="research-revision-readonly">' + rows + '</dl>' +
      '<h4>' + escapeHtml(uiLabel("research_citations")) + '</h4>' +
      ((envelope.citations || []).length ? envelope.citations.map(function(cite) { return researchCitationHtml(cite, false); }).join("") :
        '<p class="ctl-note">' + escapeHtml(uiLabel("research_revision_no_citations")) + '</p>') +
      '</div>';
  }

  function revisionSetTab(mode) {
    revisionState.mode = mode;
    var editing = mode === "edit";
    revisionForm.hidden = !editing;
    revisionHistoryPane.hidden = editing;
    revisionEditTab.classList.toggle("active", editing);
    revisionHistoryTab.classList.toggle("active", !editing);
    revisionEditTab.setAttribute("aria-selected", String(editing));
    revisionHistoryTab.setAttribute("aria-selected", String(!editing));
    if (editing && revisionState.current) revisionNotices(revisionState.current);
    if (!editing && revisionState.current && !revisionState.historyLoaded) revisionLoadHistory();
  }

  async function revisionLoadHistory() {
    var request = ++revisionState.historyRequest;
    var session = revisionState.session;
    revisionHistoryList.textContent = uiLabel("research_revision_loading");
    revisionHistoryDetail.replaceChildren();
    var data = await researchApiGet("research/history?kind=" + encodeURIComponent(revisionState.kind) +
      "&id=" + encodeURIComponent(revisionState.id));
    if (session !== revisionState.session || request !== revisionState.historyRequest || !researchRevisionDialog.open) return;
    if (!data.ok || (revisionState.current && data.project_id !== revisionState.current.project_id)) {
      revisionHistoryList.textContent = uiFormat("research_revision_load_failed", {reason: data.message || uiLabel("wizard_unknown_error")});
      return;
    }
    revisionState.historyLoaded = true;
    revisionHistoryList.replaceChildren();
    if (!data.revisions || !data.revisions.length) {
      revisionHistoryList.textContent = uiLabel("research_revision_history_empty");
      return;
    }
    data.revisions.forEach(function(item) {
      var row = document.createElement("li");
      var button = document.createElement("button");
      button.type = "button";
      button.className = "ctl";
      button.dataset.researchRevision = String(item.revision);
      button.textContent = uiFormat("research_revision_number", {revision: item.revision}) +
        (item.revision === data.latest_revision ? " · " + uiLabel("research_revision_current") : "") +
        " · " + (item.change ? uiLabel("research_revision_" + item.change.change_kind) : uiLabel("research_revision_original"));
      row.appendChild(button);
      if (item.change && item.change.reason) {
        var reason = document.createElement("small");
        reason.textContent = item.change.reason;
        row.appendChild(reason);
      }
      revisionHistoryList.appendChild(row);
    });
    revisionLoadHistorical(data.revisions[0].revision);
  }

  async function revisionLoadHistorical(number) {
    var request = ++revisionState.historyRequest;
    var session = revisionState.session;
    revisionHistoryDetail.textContent = uiLabel("research_revision_loading");
    revisionHistoryList.querySelectorAll("button[data-research-revision]").forEach(function(button) {
      button.setAttribute("aria-current", String(Number(button.dataset.researchRevision) === Number(number)));
    });
    var data = await researchApiGet("research/record?kind=" + encodeURIComponent(revisionState.kind) +
      "&id=" + encodeURIComponent(revisionState.id) + "&revision=" + encodeURIComponent(number));
    if (session !== revisionState.session || request !== revisionState.historyRequest || !researchRevisionDialog.open) return;
    if (!data.ok || !revisionState.current || data.project_id !== revisionState.current.project_id) {
      revisionHistoryDetail.textContent = uiFormat("research_revision_load_failed", {reason: data.message || uiLabel("wizard_unknown_error")});
      return;
    }
    revisionHistoryDetail.innerHTML = revisionReadOnly(data);
    if (revisionState.mode === "history") revisionNotices(data);
  }

  async function revisionLoadCurrent(replaceDraft) {
    var request = ++revisionState.request;
    var session = revisionState.session;
    var data = await researchApiGet("research/record?kind=" + encodeURIComponent(revisionState.kind) +
      "&id=" + encodeURIComponent(revisionState.id) +
      (revisionState.section && revisionState.sectionBase ? "&revision=" + encodeURIComponent(revisionState.sectionBase) : ""));
    if (session !== revisionState.session || request !== revisionState.request || !researchRevisionDialog.open) return;
    if (!data.ok || !data.record || !data.snapshot || !data.project_id) {
      revisionStatus(uiFormat("research_revision_load_failed", {reason: data.message || uiLabel("wizard_unknown_error")}), true);
      return;
    }
    if (revisionState.section) {
      var sectionData = await researchApiGet(revisionSectionEndpoint(data.record.revision));
      if (session !== revisionState.session || request !== revisionState.request || !researchRevisionDialog.open) return;
      if (!sectionData.ok || sectionData.project_id !== data.project_id) {
        revisionStatus(uiFormat("research_revision_load_failed", {reason: sectionData.message || uiLabel("wizard_unknown_error")}), true);
        return;
      }
      revisionState.sectionBase = data.record.revision;
      revisionState.sectionContent = sectionData.content;
    }
    revisionState.current = data;
    revisionShowMeta(data);
    if (replaceDraft) {
      revisionBuildFields(data.record);
      revisionState.historyRequest++;
      revisionState.historyLoaded = false;
      revisionHistoryList.replaceChildren();
      revisionHistoryDetail.replaceChildren();
    }
    revisionNotices(data);
    revisionShowCitations(data.citations);
    revisionStatus("", false);
    revisionSave.disabled = false;
    if (revisionState.mode === "history" && !revisionState.historyLoaded) revisionLoadHistory();
  }

  function revisionChanges() {
    var changes = {};
    revisionEditableSpecs().forEach(function(spec) {
      var input = document.getElementById("research-revision-field-" + spec.name);
      var value = spec.type === "checkbox" ? input.checked : spec.type === "list" ?
        input.value.split(",").map(function(item) { return item.trim(); }).filter(Boolean) :
        spec.type === "number" ? (input.value ? Number(input.value) : "") :
        spec.type === "textarea" ? input.value : input.value.trim();
      var before = revisionState.initial[spec.name];
      if (spec.type === "number" && value === "") return;
      if (JSON.stringify(value) !== JSON.stringify(before)) {
        changes[spec.name] = value === "" && !spec.required && !revisionState.section ? null : value;
      }
    });
    ["claim", "dossier"].forEach(function(kind) {
      if (!Object.prototype.hasOwnProperty.call(changes, kind + "_id") || !changes[kind + "_id"]) return;
      var pin = document.getElementById("research-revision-field-" + kind + "_revision");
      if (pin && pin.value) changes[kind + "_revision"] = Number(pin.value);
    });
    if (revisionState.kind === "decision") {
      var ids = revisionFieldsHost.querySelector('[name="dossier_ids"]').value.split(",").map(function(id) { return id.trim(); }).filter(Boolean);
      var pins = {};
      ids.forEach(function(id) { if (revisionState.dossierPins[id]) pins[id] = revisionState.dossierPins[id]; });
      var initialPins = revisionFieldValue(revisionState.current.record, "dossier_revisions", false);
      if (Object.prototype.hasOwnProperty.call(changes, "dossier_ids") || Object.keys(pins).some(function(id) { return pins[id] !== initialPins[id]; })) {
        changes.dossier_ids = ids;
        changes.dossier_revisions = pins;
      }
    }
    return changes;
  }

  function revisionDraft() {
    var choice = revisionForm.querySelector('input[name="research_revision_change_kind"]:checked');
    if (!choice || !revisionReason.value.trim()) {
      revisionStatus(uiLabel("research_revision_reason_required"), true);
      if (!choice) revisionForm.querySelector('input[name="research_revision_change_kind"]').focus();
      else revisionReason.focus();
      return null;
    }
    if (!revisionForm.reportValidity()) return null;
    var changes = revisionChanges();
    if (!Object.keys(changes).length) {
      revisionStatus(uiLabel("research_revision_no_changes"), true);
      return null;
    }
    return {kind: revisionState.kind, id: revisionState.id, expected_revision: revisionState.current.record.revision,
      changes: changes, change_kind: choice.value, reason: revisionReason.value.trim()};
  }

  function revisionFillDraft(envelope, changes, reason, changeKind) {
    revisionState.current = envelope;
    revisionBuildFields(envelope.record);
    Object.keys(changes).forEach(function(name) {
      if (name === "dossier_revisions") {
        Object.assign(revisionState.dossierPins, changes[name]);
        return;
      }
      var field = document.getElementById("research-revision-field-" + name);
      if (!field) return;
      var value = changes[name];
      if (field.type === "checkbox") field.checked = Boolean(value);
      else field.value = Array.isArray(value) ? value.join(", ") : value === null ? "" : String(value);
    });
    revisionReason.value = reason;
    revisionForm.querySelectorAll('input[name="research_revision_change_kind"]').forEach(function(input) { input.checked = input.value === changeKind; });
    revisionState.historyRequest++;
    revisionState.historyLoaded = false;
    revisionNotices(envelope);
    revisionShowCitations(envelope.citations);
    revisionShowMeta(envelope);
  }

  function revisionPending(pending) {
    revisionState.pending = pending;
    revisionForm.setAttribute("aria-busy", String(pending));
    revisionFieldsHost.querySelectorAll("input, textarea, select").forEach(function(input) { input.disabled = pending; });
    revisionForm.querySelectorAll('input[name="research_revision_change_kind"]').forEach(function(input) { input.disabled = pending; });
    revisionReason.disabled = pending;
    revisionSave.disabled = pending || !revisionState.current || Boolean(revisionState.merge);
    revisionBatchAdd.disabled = pending || !revisionState.current || Boolean(revisionState.merge);
    revisionBatchAdd.hidden = Boolean(revisionState.section);
    revisionReload.disabled = pending;
    revisionEditTab.disabled = pending;
    revisionHistoryTab.disabled = pending;
    researchRevisionDialog.querySelectorAll("[data-close-modal]").forEach(function(button) { button.disabled = pending; });
    revisionMerge.querySelectorAll("input").forEach(function(input) { input.disabled = pending; });
    revisionMergeApply.disabled = pending || !revisionState.merge ||
      revisionState.merge.preview.conflicts.some(function(item) { return !revisionState.merge.resolutions[item.field]; });
  }

  function revisionMergeValue(value) {
    return value === null || value === undefined ? "—" : typeof value === "string" ? value : JSON.stringify(value, null, 2);
  }

  function revisionMergeLabel(name, kind) {
    if (name === "dossier_revisions") return uiLabel("research_revision_dossier_pins");
    var spec = (revisionSpecs[kind || revisionState.kind] || []).find(function(item) { return item.name === name; });
    return spec ? uiLabel(spec.label) : name;
  }

  function revisionRenderMerge() {
    var merge = revisionState.merge;
    revisionMergeFields.replaceChildren();
    var changed = Object.keys(merge.preview.changes);
    if (changed.length) {
      var heading = document.createElement("p");
      heading.textContent = uiLabel("research_revision_merge_changes");
      var list = document.createElement("dl");
      changed.forEach(function(name) {
        var term = document.createElement("dt"), value = document.createElement("dd");
        term.textContent = revisionMergeLabel(name);
        value.textContent = revisionMergeValue(revisionState.section && name === "body" ? merge.draft.body : merge.preview.changes[name]);
        list.append(term, value);
      });
      revisionMergeFields.append(heading, list);
    }
    if (revisionState.section) {
      var sectionNote = document.createElement("p");
      sectionNote.className = "ctl-note";
      sectionNote.textContent = uiLabel("research_section_preserved");
      revisionMergeFields.appendChild(sectionNote);
    }
    merge.preview.conflicts.forEach(function(conflict) {
      var group = document.createElement("fieldset"), legend = document.createElement("legend");
      legend.textContent = revisionMergeLabel(conflict.field);
      group.appendChild(legend);
      var base = document.createElement("p");
      base.textContent = uiLabel("research_revision_merge_base") + ": " + revisionMergeValue(conflict.base);
      group.appendChild(base);
      ["current", "mine"].forEach(function(choice) {
        var label = document.createElement("label"), input = document.createElement("input");
        var title = document.createElement("span"), value = document.createElement("pre");
        input.type = "radio";
        input.name = "research-merge-" + conflict.field;
        input.value = choice;
        input.checked = merge.resolutions[conflict.field] === choice;
        title.textContent = " " + uiLabel("research_revision_merge_" + choice);
        value.textContent = revisionMergeValue(conflict[choice]);
        input.addEventListener("change", function() {
          merge.resolutions[conflict.field] = choice;
          revisionPending(false);
        });
        label.append(input, title, value);
        group.appendChild(label);
      });
      revisionMergeFields.appendChild(group);
    });
    revisionMerge.hidden = false;
    revisionPending(revisionState.pending);
  }

  async function revisionPrepareMerge(changes, resolutions, applying) {
    var session = revisionState.session;
    var reviewedCurrent = applying && revisionState.merge ? revisionState.merge.preview.current : null;
    var baseRevision = revisionState.merge ? revisionState.merge.baseRevision : revisionState.current.record.revision;
    var response = await fetch(API + "/research-record-prepare", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(Object.assign({kind: revisionState.kind, id: revisionState.id,
        base_revision: baseRevision, changes: changes, resolutions: resolutions || {}},
        revisionState.section ? {section: revisionState.section} : {}))
    });
    var preview = await response.json();
    if (session !== revisionState.session || !researchRevisionDialog.open) return;
    // Choices belong to the exact preview shown to the author. A fresh HEAD
    // needs a new unresolved review, including when old conflicts disappeared.
    if (applying && (response.status === 400 || (response.ok && preview.ok && preview.current &&
        (!reviewedCurrent || preview.current.snapshot !== reviewedCurrent.snapshot ||
         preview.current.record.revision !== reviewedCurrent.record.revision)))) {
      await revisionPrepareMerge(changes, {}, false);
      if (session === revisionState.session && researchRevisionDialog.open) {
        revisionStatus(uiLabel("research_revision_conflict"), true);
      }
      return;
    }
    if (!response.ok || !preview.ok || !preview.current || preview.current.project_id !== revisionState.current.project_id) {
      revisionStatus(uiFormat("research_revision_load_failed", {reason: preview.message || uiLabel("wizard_unknown_error")}), true);
      return;
    }
    revisionState.merge = {baseRevision: baseRevision, draft: changes, resolutions: resolutions || {}, preview: preview};
    if (!applying || !preview.ready) {
      revisionRenderMerge();
      revisionMerge.scrollIntoView({block: "nearest"});
      return;
    }
    var reason = revisionReason.value;
    var choice = revisionForm.querySelector('input[name="research_revision_change_kind"]:checked');
    var changeKind = choice ? choice.value : "";
    if (revisionState.section) {
      var selected = await researchApiGet(revisionSectionEndpoint(preview.current.record.revision));
      if (session !== revisionState.session || !researchRevisionDialog.open) return;
      if (!selected.ok || selected.project_id !== revisionState.current.project_id) {
        revisionStatus(uiFormat("research_revision_load_failed", {reason: selected.message || uiLabel("wizard_unknown_error")}), true);
        return;
      }
      revisionState.sectionBase = preview.current.record.revision;
      revisionState.sectionContent = selected.content;
      revisionFillDraft(preview.current, {body: resolutions.body === "current" ? selected.content : changes.body}, reason, changeKind);
    } else revisionFillDraft(preview.current, preview.changes, reason, changeKind);
    revisionStatus(uiLabel(preview.has_changes ? "research_revision_merge_applied" : "research_revision_merge_no_changes"), false);
  }

  revisionMergeApply.addEventListener("click", async function() {
    if (!revisionState.merge || revisionState.pending) return;
    revisionPending(true);
    try {
      await revisionPrepareMerge(revisionState.merge.draft, revisionState.merge.resolutions, true);
    } catch (error) {
      revisionStatus(uiFormat("research_revision_load_failed", {reason: String(error)}), true);
    } finally { revisionPending(false); }
  });
  revisionFieldsHost.addEventListener("input", function() {
    revisionState.merge = null;
    revisionMerge.hidden = true;
    revisionPending(false);
  });

  function revisionUpdateQueueControls() {
    if (revisionBatchReview) {
      revisionBatchReview.hidden = Boolean(revisionState.section) || !revisionBatch.entries.length;
      revisionBatchReview.textContent = uiFormat("research_revision_batch_review", {count: revisionBatch.entries.length});
    }
    var queued = revisionBatch.entries.some(function(entry) {
      return entry.operation.kind === revisionState.kind && entry.operation.id === revisionState.id;
    });
    revisionBatchAdd.textContent = uiLabel(queued ? "research_revision_batch_replace" : "research_revision_batch_add");
  }

  function revisionBatchStatus(message, error) {
    revisionBatchStatusHost.textContent = message || "";
    revisionBatchStatusHost.hidden = !message;
    revisionBatchStatusHost.className = "ctl-status" + (error ? " err" : "");
  }

  function revisionBatchPending(pending) {
    revisionBatch.pending = pending;
    revisionBatchDialog.setAttribute("aria-busy", String(pending));
    revisionBatchDialog.querySelectorAll("button").forEach(function(button) { button.disabled = pending; });
    revisionBatchCheck.disabled = pending || !revisionBatch.entries.length;
    revisionBatchApply.disabled = pending || !revisionBatch.preview;
  }

  function revisionBatchRender() {
    revisionBatchList.replaceChildren();
    revisionBatch.entries.forEach(function(entry, index) {
      var operation = entry.operation, record = entry.envelope.record;
      var item = document.createElement("li"), heading = document.createElement("h4"), meta = document.createElement("p");
      heading.textContent = record.title || uiLabel("research_revision_kind_" + operation.kind);
      meta.className = "ctl-note";
      meta.textContent = uiLabel("research_revision_kind_" + operation.kind) + " · " +
        uiFormat("research_revision_number", {revision: operation.expected_revision}) + " · " + operation.id;
      var reason = document.createElement("p"), fields = document.createElement("dl");
      reason.textContent = uiLabel("research_revision_" + operation.change_kind) + ": " + operation.reason;
      Object.keys(operation.changes).forEach(function(name) {
        var term = document.createElement("dt"), value = document.createElement("dd");
        term.textContent = revisionMergeLabel(name, operation.kind);
        var before = document.createElement("p"), draft = document.createElement("pre");
        before.textContent = uiLabel("research_revision_merge_base") + ": " + revisionMergeValue(revisionFieldValue(record, name, true));
        draft.textContent = uiLabel("research_revision_merge_mine") + ": " + revisionMergeValue(operation.changes[name]);
        value.append(before, draft);
        fields.append(term, value);
      });
      var actions = document.createElement("div");
      actions.className = "row";
      ["edit", "remove"].forEach(function(action) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "ctl";
        button.dataset["batch" + (action === "edit" ? "Edit" : "Remove")] = String(index);
        button.textContent = uiLabel("research_revision_batch_" + action);
        actions.appendChild(button);
      });
      item.append(heading, meta, reason, fields, actions);
      revisionBatchList.appendChild(item);
    });
    revisionUpdateQueueControls();
    revisionBatchPending(revisionBatch.pending);
  }

  async function revisionBatchPrepare() {
    if (revisionBatch.pending || !revisionBatch.entries.length) return;
    var request = ++revisionBatch.request;
    revisionBatch.preview = null;
    revisionBatchPending(true);
    revisionBatchStatus(uiLabel("research_revision_batch_checking"), false);
    var preview = await researchApiPost("research-revision-batch-prepare", {
      operations: revisionBatch.entries.map(function(entry) { return entry.operation; })
    });
    if (request !== revisionBatch.request || !revisionBatchDialog.open) return;
    if (!preview.ok || !preview.ready || preview.project_id !== revisionBatch.projectId) {
      revisionBatchStatus(uiFormat("research_revision_batch_failed", {
        reason: preview.message || uiLabel(preview.project_id !== revisionBatch.projectId ? "research_revision_batch_project_changed" : "wizard_unknown_error")
      }), true);
    } else {
      revisionBatch.preview = preview;
      revisionBatchStatus(uiFormat("research_revision_batch_ready", {count: preview.operations.length}), false);
    }
    revisionBatchPending(false);
  }

  revisionBatchAdd.addEventListener("click", async function() {
    if (!revisionState.current || revisionState.pending || revisionState.merge || revisionState.section) return;
    if (revisionBatch.entries.length && revisionState.current.project_id !== revisionBatch.projectId) {
      revisionStatus(uiLabel("research_revision_batch_project_changed"), true);
      return;
    }
    var operation = revisionDraft();
    if (!operation) return;
    var index = revisionBatch.entries.findIndex(function(entry) { return entry.operation.kind === operation.kind && entry.operation.id === operation.id; });
    if (index < 0 && revisionBatch.entries.length >= 100) {
      revisionStatus(uiLabel("research_revision_batch_limit"), true);
      return;
    }
    var session = revisionState.session;
    revisionPending(true);
    var preview = await researchApiPost("research-record-prepare", {kind: operation.kind, id: operation.id,
      base_revision: operation.expected_revision, changes: operation.changes});
    if (session !== revisionState.session || !researchRevisionDialog.open) return;
    if (!preview.ok || !preview.current || preview.current.project_id !== revisionState.current.project_id) {
      revisionStatus(uiFormat("research_revision_load_failed", {reason: preview.message || uiLabel("wizard_unknown_error")}), true);
    } else if (!preview.ready || preview.current.record.revision !== operation.expected_revision) {
      revisionState.merge = {baseRevision: operation.expected_revision, draft: operation.changes, resolutions: {}, preview: preview};
      revisionRenderMerge();
      revisionStatus(uiLabel("research_revision_batch_reconcile"), true);
      revisionMerge.scrollIntoView({block: "nearest"});
    } else if (!preview.has_changes) {
      revisionStatus(uiLabel("research_revision_merge_no_changes"), false);
    } else {
      operation.changes = preview.changes;
      revisionBatch.projectId = preview.current.project_id;
      var entry = {operation: operation, envelope: preview.current};
      if (index < 0) revisionBatch.entries.push(entry);
      else revisionBatch.entries[index] = entry;
      revisionBatch.preview = null;
      revisionBatch.request++;
      revisionFillDraft(preview.current, preview.changes, operation.reason, operation.change_kind);
      revisionUpdateQueueControls();
      revisionStatus(uiLabel(index < 0 ? "research_revision_batch_added" : "research_revision_batch_replaced"), false);
    }
    revisionPending(false);
  });

  if (revisionBatchReview) revisionBatchReview.addEventListener("click", function() {
    revisionBatchRender();
    revisionBatchDialog.showModal();
    revisionBatchPrepare();
  });
  revisionBatchCheck.addEventListener("click", revisionBatchPrepare);
  revisionBatchDialog.addEventListener("click", async function(event) {
    if (revisionBatch.pending) return;
    var edit = event.target.closest("[data-batch-edit]"), remove = event.target.closest("[data-batch-remove]");
    if (remove) {
      revisionBatch.entries.splice(Number(remove.dataset.batchRemove), 1);
      revisionBatch.preview = null;
      revisionBatch.request++;
      if (!revisionBatch.entries.length) revisionBatch.projectId = null;
      revisionBatchRender();
      revisionBatchStatus(revisionBatch.entries.length ? "" : uiLabel("research_revision_batch_empty"), false);
    } else if (edit) {
      var entry = revisionBatch.entries[Number(edit.dataset.batchEdit)];
      revisionBatchDialog.close();
      await revisionOpen(entry.operation.kind, entry.operation.id, "edit");
      if (!researchRevisionDialog.open || !revisionState.current) return;
      if (revisionState.current.project_id !== revisionBatch.projectId) {
        revisionStatus(uiLabel("research_revision_batch_project_changed"), true);
        return;
      }
      var latestRevision = revisionState.current.record.revision;
      revisionFillDraft(entry.envelope, entry.operation.changes, entry.operation.reason, entry.operation.change_kind);
      revisionStatus(uiLabel("research_revision_batch_restored"), false);
      if (latestRevision !== entry.operation.expected_revision) {
        revisionPending(true);
        try { await revisionPrepareMerge(entry.operation.changes, {}, false); }
        catch (error) { revisionStatus(uiFormat("research_revision_load_failed", {reason: String(error)}), true); }
        finally { revisionPending(false); }
      }
    }
  });
  document.getElementById("research-revision-batch-clear").addEventListener("click", function() {
    if (revisionBatch.pending) return;
    revisionBatch.entries = [];
    revisionBatch.projectId = null;
    revisionBatch.preview = null;
    revisionBatch.request++;
    revisionBatchRender();
    revisionBatchStatus(uiLabel("research_revision_batch_empty"), false);
  });
  revisionBatchDialog.addEventListener("close", function() { revisionBatch.request++; });
  revisionBatchDialog.addEventListener("cancel", function(event) { if (revisionBatch.pending) event.preventDefault(); });
  revisionBatchDialog.addEventListener("click", function(event) {
    if (revisionBatch.pending && (event.target === revisionBatchDialog || event.target.closest("[data-close-modal]"))) {
      event.preventDefault();
      event.stopPropagation();
    }
  }, true);

  function revisionRefreshLists() {
    refreshResearchDossiers();
    refreshResearchClaims();
    refreshResearchDecisions();
    if (document.querySelector('[data-rtab="review"].active')) refreshResearchEditorialReview();
  }

  revisionBatchApply.addEventListener("click", async function() {
    if (revisionBatch.pending || !revisionBatch.preview) return;
    var preview = revisionBatch.preview;
    revisionBatch.preview = null;
    revisionBatchPending(true);
    try {
      var response = await fetch(API + "/research-revision-batch-apply", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({operations: preview.operations, expected_snapshot: preview.snapshot})
      });
      var result = await response.json();
      if (!response.ok || !result.ok || result.project_id !== revisionBatch.projectId) {
        revisionBatchStatus(uiFormat(response.status === 400 || response.status === 409 ? "research_revision_batch_failed" : "research_revision_batch_uncertain", {
          reason: result.message || uiLabel("wizard_unknown_error")
        }), true);
      } else {
        revisionBatch.entries = [];
        revisionBatch.projectId = null;
        revisionBatchPending(false);
        revisionBatchDialog.close();
        revisionUpdateQueueControls();
        researchStatus(uiFormat("research_revision_batch_saved", {count: result.records.length}), true);
        revisionRefreshLists();
      }
    } catch (error) {
      revisionBatchStatus(uiFormat("research_revision_batch_uncertain", {reason: String(error)}), true);
    } finally { revisionBatchPending(false); }
  });

  async function revisionOpen(kind, id, mode, section, baseRevision) {
    if (!revisionSpecs[kind] || !id) return;
    revisionState.session++;
    var session = revisionState.session;
    revisionState.request++;
    revisionState.historyRequest++;
    revisionState.kind = kind;
    revisionState.id = id;
    revisionState.section = kind === "dossier" && mode === "edit" ? section || null : null;
    revisionState.sectionBase = revisionState.section ? Number(baseRevision) || null : null;
    revisionState.sectionContent = null;
    revisionState.current = null;
    revisionState.historyLoaded = false;
    revisionState.initial = {};
    revisionState.merge = null;
    revisionMerge.hidden = true;
    revisionPending(false);
    revisionFieldsHost.replaceChildren();
    revisionHistoryList.replaceChildren();
    revisionHistoryDetail.replaceChildren();
    revisionShowMeta(null);
    document.getElementById("research-revision-technical").open = false;
    revisionReload.hidden = true;
    revisionSave.disabled = true;
    revisionNotices(null);
    revisionShowCitations([]);
    revisionStatus(uiLabel("research_revision_loading"), false);
    revisionSetTab(mode);
    researchRevisionDialog.showModal();
    await revisionLoadCurrent(true);
    if (session === revisionState.session && researchRevisionDialog.open) {
      revisionForm.scrollTop = 0;
      revisionHistoryPane.scrollTop = 0;
      var focusTarget = mode === "edit" ? revisionFieldsHost.querySelector("input, textarea, select") : revisionHistoryTab;
      if (focusTarget) focusTarget.focus();
    }
  }

  researchRevisionDialog.addEventListener("close", function() {
    revisionState.session++;
    revisionState.request++;
    revisionState.historyRequest++;
  });
  researchRevisionDialog.addEventListener("cancel", function(event) {
    if (revisionState.pending) event.preventDefault();
  });
  researchRevisionDialog.addEventListener("click", function(event) {
    if (revisionState.pending && (event.target === researchRevisionDialog || event.target.closest("[data-close-modal]"))) {
      event.preventDefault();
      event.stopPropagation();
    }
  }, true);

  document.addEventListener("click", function(event) {
    var edit = event.target.closest("[data-research-revise]");
    var history = event.target.closest("[data-research-history]");
    if (edit || history) {
      var button = edit || history;
      revisionOpen(edit ? edit.dataset.researchRevise : history.dataset.researchHistory,
        button.dataset.recordId, edit ? "edit" : "history", button.dataset.dossierSection, button.dataset.baseRevision);
      return;
    }
    if (!researchRevisionDialog.open) return;
    if (event.target.closest("#research-revision-edit-tab")) revisionSetTab("edit");
    else if (event.target.closest("#research-revision-history-tab")) revisionSetTab("history");
    else if (event.target.closest("[data-research-revision]"))
      revisionLoadHistorical(event.target.closest("[data-research-revision]").dataset.researchRevision);
    else if (event.target.closest("#research-revision-reload")) {
      revisionState.sectionBase = null;
      revisionLoadCurrent(true);
    }
  });

  revisionForm.addEventListener("submit", async function(event) {
    event.preventDefault();
    if (!revisionState.current || revisionState.pending || revisionState.merge) return;
    var operation = revisionDraft();
    if (!operation) return;
    var changes = operation.changes;
    revisionPending(true);
    var session = revisionState.session;
    var t0 = performance.now();
    var reviseUrl = API + "/research-record-revise";
    try {
      var expectedSnapshot = revisionState.current.snapshot;
      if (revisionState.section) {
        var sectionPreview = await researchApiPost("research-record-prepare", {
          kind: "dossier", id: revisionState.id, base_revision: revisionState.sectionBase,
          section: revisionState.section, changes: changes
        });
        if (session !== revisionState.session || !researchRevisionDialog.open) return;
        if (!sectionPreview.ok || !sectionPreview.current || sectionPreview.current.project_id !== revisionState.current.project_id) {
          revisionStatus(uiFormat("research_revision_save_failed", {reason: sectionPreview.message || uiLabel("wizard_unknown_error")}), true);
          return;
        }
        if (!sectionPreview.ready || sectionPreview.current.record.revision !== operation.expected_revision ||
            sectionPreview.current.snapshot !== revisionState.current.snapshot) {
          revisionState.merge = {baseRevision: revisionState.sectionBase, draft: changes, resolutions: {}, preview: sectionPreview};
          revisionRenderMerge();
          revisionStatus(uiLabel("research_revision_conflict"), true);
          return;
        }
        if (!sectionPreview.has_changes) { revisionStatus(uiLabel("research_revision_no_changes"), true); return; }
        operation.changes = sectionPreview.changes;
        operation.expected_revision = sectionPreview.current.record.revision;
        expectedSnapshot = sectionPreview.current.snapshot;
      }
      var response = await fetch(reviseUrl, {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify(Object.assign({}, operation, {expected_snapshot: expectedSnapshot}))
      });
      var data = await response.json();
      LixityLog.api("POST", reviseUrl, performance.now() - t0, response.status, data);
      if (session !== revisionState.session) return;
      if (response.status === 409) {
        revisionStatus(uiLabel("research_revision_conflict"), true);
        revisionReload.hidden = false;
        await revisionPrepareMerge(changes, {}, false);
      } else if (!response.ok || !data.ok) {
        LixityLog.error("research-record-revise failed:", data);
        revisionStatus(uiFormat("research_revision_save_failed", {reason: data.message || uiLabel("wizard_unknown_error")}), true);
      } else {
        revisionPending(false);
        researchRevisionDialog.close();
        researchStatus(uiLabel("research_revision_saved"), true);
        revisionRefreshLists();
      }
    } catch (error) {
      LixityLog.error("research-record-revise error:", error);
      if (session === revisionState.session)
        revisionStatus(uiFormat("research_revision_save_failed", {reason: String(error)}), true);
    } finally {
      if (session === revisionState.session) revisionPending(false);
    }
  });
}

if (document.getElementById("research-manager")) { initResearchUI(); }

// --- Workspace & Project Modals -------------------------------------------
var importedFileContent = "";
var importedFileRead = 0;
var researchTemplateChoice = null;
var manuscriptFile = null;
var manuscriptInput = document.getElementById("ms-file") || document.getElementById("manuscript-import-file");
var manuscriptButton = document.querySelector('[data-action="load"]') || document.getElementById("manuscript-import-btn");

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
  if (manuscriptInput.id === "manuscript-import-file") openManuscriptImport(manuscriptFile);
}

function openManuscriptImport(file) {
  var modal = document.getElementById("modal-project-create");
  if (!modal || typeof modal.showModal !== "function") return;
  switchModalTab("tab-pane-import");
  if (!modal.open) modal.showModal();
  processImportedFile(file);
}

function switchModalTab(targetPaneId) {
  document.querySelectorAll(".modal-tab-btn").forEach(function (btn) {
    var isTarget = btn.dataset.tabTarget === targetPaneId;
    btn.classList.toggle("active", isTarget);
    btn.setAttribute("aria-selected", isTarget ? "true" : "false");
  });
  document.querySelectorAll(".modal-tab-pane").forEach(function (pane) {
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
  var feedback = document.getElementById("import-project-status");
  if (feedback) {
    feedback.className = "ctl-status project-form-status loading";
    feedback.textContent = uiLabel("research_ingesting_reading");
    feedback.hidden = false;
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
  var manuscriptDrop = event.target.closest("#manuscript-dropzone");
  if (manuscriptDrop && event.target !== manuscriptInput) {
    if (manuscriptInput) manuscriptInput.click();
    return;
  }
  if (event.target.closest("#manuscript-import-btn") && manuscriptFile) {
    openManuscriptImport(manuscriptFile);
    return;
  }
  var tabBtn = event.target.closest(".modal-tab-btn");
  if (tabBtn && tabBtn.dataset.tabTarget) {
    switchModalTab(tabBtn.dataset.tabTarget);
    return;
  }

  var newBtn = event.target.closest("#btn-modal-new-project, #hero-btn-new-project");
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

    var submitBtn = document.getElementById("btn-submit-import-project");
    await submitProjectForm(formImport, "project-create", {
      title: title,
      language: lang,
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

    var submitBtn = document.getElementById("btn-submit-create-project");
    await submitProjectForm(formCreate, "project-create", {
      title: title,
      language: lang,
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
function switchActiveView(viewName) {
  if (!viewName) return;
  var tabs = document.querySelectorAll(".view-nav-tab");
  var panes = document.querySelectorAll(".view-pane");
  if (!panes.length) return;
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
}

function checkUrlHashView() {
  var hash = window.location.hash;
  if (!hash) return;
  if (hash.startsWith("#view-")) {
    var v = hash.replace("#view-", "");
    if (["research", "analysis", "project"].includes(v)) {
      switchActiveView(v);
      return;
    }
  }
  var target = document.querySelector(hash);
  if (!target) return;
  var parentPane = target.closest(".view-pane");
  if (parentPane && parentPane.dataset.viewPane) {
    switchActiveView(parentPane.dataset.viewPane);
    setTimeout(function() {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  }
}

document.addEventListener("click", function(event) {
  var viewTab = event.target.closest(".view-nav-tab[data-view]");
  if (viewTab) {
    switchActiveView(viewTab.dataset.view);
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
