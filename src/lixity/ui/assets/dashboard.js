(function () {
  var tip = document.createElement("div");
  tip.id = "lixity-tooltip";
  tip.className = "tooltip-popup";
  tip.setAttribute("role", "tooltip");
  tip.setAttribute("aria-hidden", "true");
  document.body.appendChild(tip);
  document.body.classList.add("has-js-tooltips");

  var activeEl = null;

  function show(el) {
    var text = el.getAttribute("data-help") || el.getAttribute("data-tip") || el.getAttribute("title");
    if (!text || !text.trim()) return;
    if (el.hasAttribute("title")) {
      el.setAttribute("data-tip", text);
      el.removeAttribute("title");
    }
    if (activeEl && activeEl !== el) hide();
    activeEl = el;
    var descriptions = (el.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
    if (descriptions.indexOf(tip.id) === -1) descriptions.push(tip.id);
    el.setAttribute("aria-describedby", descriptions.join(" "));
    tip.textContent = text;
    tip.setAttribute("aria-hidden", "false");
    tip.classList.add("visible");
    updatePos(el);
  }

  function hide() {
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
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }

  document.addEventListener("mouseover", function (e) {
    var el = e.target.closest("[data-help], [data-tip], [title]");
    if (el && !el.closest(".tooltip-popup")) show(el);
  }, { passive: true });

  document.addEventListener("mouseout", function (e) {
    var el = e.target.closest("[data-help], [data-tip]");
    if (el) hide();
  }, { passive: true });

  document.addEventListener("focusin", function(e) {
    var el = e.target.closest("[data-help], [data-tip], [title]");
    if (el) show(el);
  });
  document.addEventListener("focusout", hide);

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
    if (e.key === "Escape" && activeEl) hide();
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
  var target = document.querySelector(el.getAttribute("data-jump") || "");
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
  if (el && !el.closest(".controls") && !isMarkerControl(event.target)) {
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
async function markerApi(payload) {
  try {
    var res = await fetch(API + "/marker-" + payload._action, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    var data = await res.json();
    if (data.ok) { setTimeout(function () { location.reload(); }, 800); }
    return data;
  } catch (err) {
    return { ok: false, message: String(err) };
  }
}
function closeNoteField() {
  var field = document.querySelector(".marker-note");
  if (field) {
    field.classList.add("gone");
    setTimeout(function () { field.remove(); }, 160);
  }
}

function openNoteField(button) {
  closeNoteField();
  var row = button.closest(".marker-row");
  var slot = row && row.querySelector(".marker-note-slot");
  if (!slot) return;
  var input = document.createElement("input");
  input.className = "ctl marker-note";
  input.type = "text";
  input.placeholder = slot.dataset.placeholder || "";
  input.setAttribute("aria-label", slot.dataset.placeholder || "");
  slot.appendChild(input);
  requestAnimationFrame(function () { input.classList.add("visible"); });
  input.focus();
  input.addEventListener("keydown", function (event) {
    if (event.key === "Escape") { closeNoteField(); return; }
    if (event.key !== "Enter") return;
    var kind = button.dataset.markerKind;
    var line = parseInt(button.dataset.line, 10);
    var note = input.value.trim();
    button.disabled = true;
    input.disabled = true;
    markerApi({ _action: "add", kind: kind, line: line, note: note }).then(function (data) {
      button.disabled = false;
      input.disabled = false;
      if (data.ok) {
        input.value = "";
        input.classList.add("saved");
        input.placeholder = "✓";
      } else {
        input.classList.add("failed");
        input.placeholder = "✗ " + (data.message || "");
      }
    });
  });
}

document.addEventListener("click", async function (event) {
  var add = event.target.closest("[data-marker-kind]");
  if (add) { openNoteField(add); return; }
  var resolve = event.target.closest("[data-marker-resolve]");
  if (resolve) {
    markerApi({ _action: "resolve", id: resolve.dataset.markerResolve });
    return;
  }
});
var API = document.body.dataset.api || "";
// NDA statuses come from the server-rendered data attribute (single source: lixity.status.NdaStatus).
function ndaStatuses() {
  var el = document.getElementById("nda-status");
  try {
    var raw = el && el.getAttribute("data-nda-statuses");
    if (raw) return JSON.parse(raw);
  } catch (e) { /* fall through */ }
  return ["entwurf", "versendet", "bestaetigt", "unterschrieben"];
}
function ndaStatus(message, ok) {
  var el = document.getElementById("nda-status");
  if (!el) return;
  el.className = "ctl-status " + (ok ? "ok" : "err");
  el.textContent = (ok ? "✓ " : "✗ ") + (message || "");
}
async function ndaApi(path, payload) {
  try {
    var res = await fetch(API + "/" + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {})
    });
    return await res.json();
  } catch (err) {
    return { ok: false, message: String(err) };
  }
}
function ndaRender(records) {
  var host = document.getElementById("nda-table");
  var hint = document.getElementById("nda-hint");
  var unlockRow = document.getElementById("nda-unlock-row");
  var addRow = document.getElementById("nda-add-row");
  if (!host) return;
  if (unlockRow) unlockRow.hidden = true;
  if (addRow) addRow.hidden = false;
  if (hint) hint.textContent = records.length + (records.length === 1 ? " entry" : " entries");
  host.replaceChildren();
  if (!records.length) return;
  var table = document.createElement("table");
  var header = table.createTHead().insertRow();
  ["ID", document.getElementById("nda-new-name").placeholder,
    document.getElementById("nda-new-contact").placeholder, "Status", "PDF", ""].forEach(function(text) {
    var cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = text;
    header.appendChild(cell);
  });
  var body = table.createTBody();
  records.forEach(function(record) {
    var row = body.insertRow();
    [record.id, record.name, record.contact || "–"].forEach(function(value) {
      row.insertCell().textContent = String(value == null ? "" : value);
    });
    var select = document.createElement("select");
    select.className = "ctl";
    select.dataset.ndaStatus = String(record.id);
    ndaStatuses().forEach(function(status) {
      var option = document.createElement("option");
      option.value = status;
      option.textContent = status;
      option.selected = status === record.status;
      select.appendChild(option);
    });
    row.insertCell().appendChild(select);
    row.insertCell().textContent = String(record.pdf || "–");
    var actions = row.insertCell();
    actions.className = "nda-actions";
    [["ndaExport", "PDF"], ["ndaDelete", "✕"]].forEach(function(action) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "ctl";
      button.dataset[action[0]] = String(record.id);
      button.textContent = action[1];
      actions.appendChild(button);
    });
  });
  host.appendChild(table);
}
async function ndaRefresh() {
  var data = await ndaApi("nda-list", {});
  if (!data.ok) {
    var hint = document.getElementById("nda-hint");
    if (hint) hint.textContent = data.message || "";
    var unlockRow = document.getElementById("nda-unlock-row");
    if (unlockRow) unlockRow.hidden = false;
    return;
  }
  ndaRender(data.records || []);
}
document.addEventListener("click", async function (event) {
  var unlock = event.target.closest("#nda-unlock-btn");
  if (unlock) {
    var pass = document.getElementById("nda-passphrase");
    var data = await ndaApi("nda-unlock", { passphrase: pass ? pass.value : "" });
    ndaStatus(data.message, data.ok);
    if (data.ok) { if (pass) pass.value = ""; ndaRender(data.records || []); }
    return;
  }
  var add = event.target.closest("#nda-add-btn");
  if (add) {
    var payload = {
      name: document.getElementById("nda-new-name").value,
      contact: document.getElementById("nda-new-contact").value,
      notes: document.getElementById("nda-new-notes").value
    };
    var res = await ndaApi("nda-add", payload);
    ndaStatus(res.message, res.ok);
    if (res.ok) ndaRefresh();
    return;
  }
  var exp = event.target.closest("[data-nda-export]");
  if (exp) {
    var res2 = await ndaApi("nda-export", { id: exp.dataset.ndaExport });
    ndaStatus(res2.message, res2.ok);
    if (res2.ok) ndaRefresh();
    return;
  }
  var del = event.target.closest("[data-nda-delete]");
  if (del) {
    var res3 = await ndaApi("nda-delete", { id: del.dataset.ndaDelete });
    ndaStatus(res3.message, res3.ok);
    if (res3.ok) ndaRefresh();
    return;
  }
});
document.addEventListener("change", async function (event) {
  var sel = event.target.closest("[data-nda-status]");
  if (sel) {
    var res = await ndaApi("nda-update", { id: sel.dataset.ndaStatus, status: sel.value });
    ndaStatus(res.message, res.ok);
  }
});
if (document.getElementById("nda-manager")) { ndaRefresh(); }
var settingsForm = document.getElementById("settings-form");
if (settingsForm) {
  settingsForm.addEventListener("submit", function(event) {
    event.preventDefault();
    settingsForm.querySelector('[data-action="settings"]').click();
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
  if (!status) return;
  status.className = "ctl-status";
  status.textContent = "…";
  if (button) { button.disabled = true; button.classList.add("busy"); button.setAttribute("aria-busy", "true"); }
  try {
    var res = await fetch(API + "/" + action, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {})
    });
    var data = await res.json();
    status.className = "ctl-status " + (data.ok ? "ok" : "err");
    status.textContent = (data.ok ? "✓ " : "✗ ") + (data.message || "");
    if (data.reload) { setTimeout(function () { location.reload(); }, 1200); }
  } catch (err) {
    status.className = "ctl-status err";
    status.textContent = "✗ " + err;
  } finally {
    if (button) { button.disabled = false; button.classList.remove("busy"); button.removeAttribute("aria-busy"); }
  }
}
document.querySelectorAll("[data-action]").forEach(function (btn) {
  btn.addEventListener("click", function () {
    var payload = {};
    if (btn.dataset.payload === "format") {
      payload.format = document.getElementById("fmt").value;
    }
    if (btn.dataset.payload === "settings") {
      var settings = document.getElementById("settings-form");
      var mild = document.getElementById("set-z-mild");
      var strong = document.getElementById("set-z-strong");
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
    }
    if (btn.dataset.payload === "load") {
      var input = document.getElementById("ms-file");
      if (!input.files || !input.files.length) {
        var status = document.getElementById("ctl-status");
        status.className = "ctl-status err";
        status.textContent = "✗ " + (input.getAttribute("accept") || "File");
        return;
      }
      var file = input.files[0];
      var reader = new FileReader();
      reader.onload = function () {
        runAction("load", { name: file.name, content: reader.result });
      };
      reader.readAsText(file);
      return;
    }
    runAction(btn.dataset.action, payload, btn);
  });
});

// --- Research & Dossier Management -----------------------------------------
function researchStatus(message, ok) {
  var el = document.getElementById("research-status-bar");
  if (!el) return;
  el.className = "ctl-status " + (ok ? "ok" : "err");
  el.textContent = (ok ? "✓ " : "✗ ") + (message || "");
}

async function researchApiPost(action, payload) {
  try {
    var res = await fetch(API + "/" + action, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {})
    });
    return await res.json();
  } catch (err) {
    return { ok: false, message: String(err) };
  }
}

async function researchApiGet(endpoint) {
  try {
    var res = await fetch(API + "/" + endpoint);
    return await res.json();
  } catch (err) {
    return { ok: false, message: String(err) };
  }
}

function escapeHtml(str) {
  var div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

async function refreshResearchSources() {
  var listHost = document.getElementById("research-sources-list");
  var selectHost = document.getElementById("r-ground-source-select");
  if (!listHost) return;
  var data = await researchApiGet("research/sources");
  if (!data.ok) {
    listHost.innerHTML = '<p class="ctl-note">' + escapeHtml(data.message || "Failed to load sources") + '</p>';
    return;
  }
  var sources = data.sources || [];
  if (selectHost) {
    selectHost.innerHTML = '<option value="">Quelle auswählen...</option>' +
      sources.map(function(s) {
        return '<option value="' + escapeHtml(s.id) + '">' + escapeHtml(s.title) + ' (' + s.passages + ' Passagen)</option>';
      }).join("");
  }
  if (!sources.length) {
    listHost.innerHTML = '<p class="ctl-note">Noch keine Quellen erfasst.</p>';
    return;
  }
  listHost.innerHTML = sources.map(function(s) {
    var tagsHtml = (s.tags || []).map(function(t) {
      return '<span class="research-tag">' + escapeHtml(t) + '</span>';
    }).join(" ");
    return '<div class="research-card">' +
      '<div class="research-card-header">' +
        '<span class="research-card-title">' + escapeHtml(s.title) + '</span>' +
        '<span class="ctl-note">' + s.passages + ' Passagen · ' + Math.round((s.byte_length || 0) / 1024) + ' KB</span>' +
      '</div>' +
      '<div class="ctl-note" style="font-family:monospace;font-size:.7rem;margin-top:.2rem;">' + escapeHtml(s.id) + '</div>' +
      (tagsHtml ? '<div class="research-tags">' + tagsHtml + '</div>' : '') +
    '</div>';
  }).join("");
}

async function refreshResearchDossiers() {
  var listHost = document.getElementById("research-dossiers-list");
  if (!listHost) return;
  var data = await researchApiGet("research/dossiers");
  if (!data.ok) {
    listHost.innerHTML = '<p class="ctl-note">' + escapeHtml(data.message || "Failed to load dossiers") + '</p>';
    return;
  }
  var dossiers = data.dossiers || [];
  if (!dossiers.length) {
    listHost.innerHTML = '<p class="ctl-note">Noch keine Dossiers angelegt.</p>';
    return;
  }
  listHost.innerHTML = dossiers.map(function(d) {
    var tagsHtml = (d.tags || []).map(function(t) {
      return '<span class="research-tag">' + escapeHtml(t) + '</span>';
    }).join(" ");
    return '<div class="research-card">' +
      '<div class="research-card-header">' +
        '<span class="research-card-title">' + escapeHtml(d.title) + '</span>' +
        '<span class="ctl-note">' + d.evidence_count + ' Evidenzen</span>' +
      '</div>' +
      (d.excerpt ? '<p class="ctl-note" style="margin:.3rem 0;color:var(--fg);">' + escapeHtml(d.excerpt) + '</p>' : '') +
      (tagsHtml ? '<div class="research-tags">' + tagsHtml + '</div>' : '') +
    '</div>';
  }).join("");
}

async function refreshResearchClaims() {
  var listHost = document.getElementById("research-claims-list");
  var selectHost = document.getElementById("r-decision-claim-select");
  var linkClaimSelect = document.getElementById("r-link-claim-select");
  if (!listHost) return;
  var data = await researchApiGet("research/claims");
  if (!data.ok) {
    listHost.innerHTML = '<p class="ctl-note">' + escapeHtml(data.message || "Failed to load claims") + '</p>';
    return;
  }
  var claims = data.claims || [];
  if (selectHost) {
    selectHost.innerHTML = '<option value="">Keine These verknüpft (allgemeine Entscheidung)</option>' +
      claims.map(function(c) {
        return '<option value="' + escapeHtml(c.id) + '">' + escapeHtml(c.title) + '</option>';
      }).join("");
  }
  if (linkClaimSelect) {
    linkClaimSelect.innerHTML = '<option value="">These auswählen...</option>' +
      claims.map(function(c) {
        return '<option value="' + escapeHtml(c.id) + '">' + escapeHtml(c.title) + '</option>';
      }).join("");
  }
  if (!claims.length) {
    listHost.innerHTML = '<p class="ctl-note">Noch keine Thesen / Aussagen erfasst.</p>';
    return;
  }
  listHost.innerHTML = claims.map(function(c) {
    var confClass = c.confidence === "evidenced" ? "badge-success" : (c.confidence === "disputed" ? "badge-warning" : "badge-neutral");
    var confLabel = c.confidence === "evidenced" ? "Belegt" : (c.confidence === "disputed" ? "Umstritten" : "Hypothetisch");
    var scopeParts = [];
    if (c.scope) {
      if (c.scope.time_period) scopeParts.push("Zeit: " + escapeHtml(c.scope.time_period));
      if (c.scope.place) scopeParts.push("Ort: " + escapeHtml(c.scope.place));
      if (c.scope.actors && c.scope.actors.length) scopeParts.push("Akteure: " + escapeHtml(c.scope.actors.join(", ")));
    }
    var tagsHtml = (c.tags || []).map(function(t) {
      return '<span class="research-tag">' + escapeHtml(t) + '</span>';
    }).join(" ");

    return '<div class="research-card">' +
      '<div class="research-card-header">' +
        '<span class="research-card-title">' + escapeHtml(c.title) + '</span>' +
        '<span class="research-badge ' + confClass + '">' + confLabel + '</span>' +
      '</div>' +
      '<p style="margin:.4rem 0;font-size:.85rem;line-height:1.45;color:var(--fg);">' + escapeHtml(c.statement) + '</p>' +
      (scopeParts.length ? '<div class="ctl-note" style="margin-bottom:.3rem;font-size:.76rem;">' + scopeParts.join(" · ") + '</div>' : '') +
      '<div class="ctl-note" style="font-family:monospace;font-size:.7rem;margin-top:.2rem;">These-ID: ' + escapeHtml(c.id) + '</div>' +
      (tagsHtml ? '<div class="research-tags">' + tagsHtml + '</div>' : '') +
      '<div class="claim-evidence-subpanel" id="claim-evidence-' + escapeHtml(c.id) + '" style="margin-top:.6rem;padding-top:.4rem;border-top:1px dashed var(--line);">' +
        '<button type="button" class="ctl" style="font-size:.74rem;padding:.2rem .5rem;" data-load-evidence="' + escapeHtml(c.id) + '">Verknüpfte Belege laden</button>' +
      '</div>' +
    '</div>';
  }).join("");
}

async function refreshResearchDecisions() {
  var listHost = document.getElementById("research-decisions-list");
  if (!listHost) return;
  var data = await researchApiGet("research/decisions");
  if (!data.ok) {
    listHost.innerHTML = '<p class="ctl-note">' + escapeHtml(data.message || "Failed to load decisions") + '</p>';
    return;
  }
  var decisions = data.decisions || [];
  if (!decisions.length) {
    listHost.innerHTML = '<p class="ctl-note">Noch keine Autorenentscheidungen erfasst.</p>';
    return;
  }
  listHost.innerHTML = decisions.map(function(d) {
    var devBadge = d.deviation_from_fact
      ? '<span class="research-badge badge-warning" title="Bewusste Abweichung von historischer Evidenz">Dichterische Freiheit / Abweichung</span>'
      : '<span class="research-badge badge-success">Faktentreu</span>';
    return '<div class="research-card">' +
      '<div class="research-card-header">' +
        '<span class="research-card-title">' + escapeHtml(d.title) + '</span>' +
        devBadge +
      '</div>' +
      '<div style="margin:.4rem 0;font-size:.85rem;line-height:1.45;color:var(--fg);">' + escapeHtml(d.rationale) + '</div>' +
      (d.impact_on_plot ? '<div class="ctl-note" style="margin:.3rem 0;font-size:.78rem;"><strong>Dramaturgische Wirkung:</strong> ' + escapeHtml(d.impact_on_plot) + '</div>' : '') +
      (d.claim_id ? '<div class="ctl-note" style="font-family:monospace;font-size:.7rem;margin-top:.2rem;">Betrifft These: ' + escapeHtml(d.claim_id) + '</div>' : '') +
    '</div>';
  }).join("");
}

async function initResearchUI() {
  var status = await researchApiGet("research/status");
  var initBox = document.getElementById("research-init-box");
  var tabs = document.getElementById("research-tabs");
  var activeRootEl = document.getElementById("r-active-root");
  var statusBar = document.getElementById("research-status-bar");

  if (!status || status.ok === false) {
    if (initBox) initBox.style.display = "none";
    if (tabs) tabs.style.display = "none";
    if (statusBar) statusBar.textContent = "Fehler bei Verbindung mit der Recherche-API: " + ((status && status.message) || "Server antwortet nicht");
    return;
  }

  if (activeRootEl && status.project_root) {
    activeRootEl.textContent = "Projekt: " + status.project_root;
    if (status.initialized) {
      activeRootEl.textContent += " (" + (status.sources_count || 0) + " Quellen, " + (status.dossiers_count || 0) + " Dossiers, " + (status.claims_count || 0) + " Thesen, " + (status.decisions_count || 0) + " Entscheidungen)";
    }
  }

  if (!status.initialized) {
    if (initBox) initBox.style.display = "block";
    if (tabs) tabs.style.display = "none";
    document.querySelectorAll(".research-tab-pane").forEach(function(p) { p.style.display = "none"; });
    return;
  }
  if (initBox) initBox.style.display = "none";
  if (tabs) tabs.style.display = "flex";
  var activeTab = document.querySelector(".research-tabs button.active");
  var targetPane = activeTab ? "rtab-" + activeTab.dataset.rtab : "rtab-sources";
  document.querySelectorAll(".research-tab-pane").forEach(function(p) {
    p.style.display = p.id === targetPane ? "block" : "none";
  });
  refreshResearchSources();
  refreshResearchDossiers();
  refreshResearchClaims();
  refreshResearchDecisions();
}

document.addEventListener("click", async function (event) {
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
    return;
  }

  var initBtn = event.target.closest("#r-init-btn");
  if (initBtn) {
    var titleInput = document.getElementById("r-init-title");
    var res = await researchApiPost("research-init", { title: titleInput ? titleInput.value : "" });
    researchStatus(res.message, res.ok);
    if (res.ok) initResearchUI();
    return;
  }

  var ingestBtn = event.target.closest("#r-ingest-btn");
  if (ingestBtn) {
    var retCheck = document.getElementById("r-ingest-retention");
    if (!retCheck || !retCheck.checked) {
      researchStatus("Lokale Speicherung muss bestätigt werden (--allow-retention)", false);
      return;
    }
    var titleEl = document.getElementById("r-ingest-title");
    var tagsEl = document.getElementById("r-ingest-tags");
    var textEl = document.getElementById("r-ingest-text");
    var fileEl = document.getElementById("r-ingest-file");
    var tags = (tagsEl && tagsEl.value) ? tagsEl.value.split(",").map(function(t){ return t.trim(); }).filter(Boolean) : [];

    function sendIngest(content, filename) {
      researchStatus("Erfasse und indiziere Quelle...", true);
      researchApiPost("research-ingest", {
        content: content,
        title: (titleEl && titleEl.value.trim()) || filename || "Quelle",
        tags: tags,
        allow_retention: true
      }).then(function(res) {
        researchStatus(res.message, res.ok);
        if (res.ok) {
          if (titleEl) titleEl.value = "";
          if (tagsEl) tagsEl.value = "";
          if (textEl) textEl.value = "";
          if (fileEl) fileEl.value = "";
          retCheck.checked = false;
          refreshResearchSources();
        }
      });
    }

    if (fileEl && fileEl.files && fileEl.files.length) {
      var file = fileEl.files[0];
      var reader = new FileReader();
      reader.onload = function() { sendIngest(reader.result, file.name); };
      reader.readAsText(file);
    } else if (textEl && textEl.value.trim()) {
      sendIngest(textEl.value, "");
    } else {
      researchStatus("Bitte Datei auswählen oder Text eingeben", false);
    }
    return;
  }

  var searchBtn = event.target.closest("#r-search-btn");
  if (searchBtn) {
    var qEl = document.getElementById("r-search-query");
    var query = qEl ? qEl.value.trim() : "";
    if (!query) { researchStatus("Suchbegriff eingeben", false); return; }
    var resultsHost = document.getElementById("research-search-results");
    if (resultsHost) resultsHost.innerHTML = '<p class="ctl-note">Suche läuft...</p>';
    var sres = await researchApiPost("research-search", { query: query });
    if (!sres.ok) {
      if (resultsHost) resultsHost.innerHTML = '<p class="ctl-note">' + escapeHtml(sres.message || "Suche fehlgeschlagen") + '</p>';
      return;
    }
    var hits = sres.hits || [];
    if (!hits.length) {
      if (resultsHost) resultsHost.innerHTML = '<p class="ctl-note">Keine Treffer für „' + escapeHtml(query) + '“ gefunden.</p>';
      return;
    }
    if (resultsHost) {
      resultsHost.innerHTML = hits.map(function(h) {
        return '<div class="research-passage-card">' +
          '<div class="research-passage-quote">„' + escapeHtml(h.verbatim || "") + '“</div>' +
          '<div class="research-passage-cite">' +
            'Quelle: <strong>' + escapeHtml(h.source_title || "") + '</strong> · ' +
            'Score: ' + (h.rank_score !== undefined ? Number(h.rank_score).toFixed(2) : 'n/a') + ' · ' +
            'ID: <code style="user-select:all;cursor:pointer;" title="Klicken zum Auswählen">' + escapeHtml(h.passage_id || "") + '</code>' +
          '</div>' +
        '</div>';
      }).join("");
    }
    researchStatus(hits.length + " Treffer gefunden", true);
    return;
  }

  var dosBtn = event.target.closest("#r-dos-create-btn");
  if (dosBtn) {
    var dTitle = document.getElementById("r-dos-title");
    var dTags = document.getElementById("r-dos-tags");
    var dEids = document.getElementById("r-dos-eids");
    var dBody = document.getElementById("r-dos-body");
    var titleVal = dTitle ? dTitle.value.trim() : "";
    if (!titleVal) { researchStatus("Titel für Dossier erforderlich", false); return; }
    var tagsArr = (dTags && dTags.value) ? dTags.value.split(",").map(function(t){ return t.trim(); }).filter(Boolean) : [];
    var eidsArr = (dEids && dEids.value) ? dEids.value.split(",").map(function(t){ return t.trim(); }).filter(Boolean) : [];
    var dres = await researchApiPost("research-dossier", {
      title: titleVal,
      body: dBody ? dBody.value : "",
      tags: tagsArr,
      evidence_ids: eidsArr
    });
    researchStatus(dres.message, dres.ok);
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
    if (!sid) { researchStatus("Bitte eine Quelle auswählen", false); return; }
    var gHost = document.getElementById("research-grounding-results");
    if (gHost) gHost.innerHTML = '<p class="ctl-note">Abgleich wird berechnet...</p>';
    var gres = await researchApiPost("research-compare", { source_id: sid });
    if (!gres.ok) {
      if (gHost) gHost.innerHTML = '<p class="ctl-note">' + escapeHtml(gres.message || "Abgleich fehlgeschlagen") + '</p>';
      return;
    }
    var sum = gres.summary || {};
    var topShared = (gres.lexical_overlap && gres.lexical_overlap.top_shared_terms) || [];
    var sharedWordsHtml = topShared.slice(0, 15).map(function(w) {
      return '<span class="research-tag">' + escapeHtml(w.word) + ' (' + w.total_count + ')</span>';
    }).join(" ");

    var chapters = gres.chapter_grounding || [];
    var chRows = chapters.map(function(c) {
      return '<tr>' +
        '<td>Kap. ' + c.chapter + ' (' + escapeHtml(c.title || "") + ')</td>' +
        '<td style="text-align:right;">' + c.overlap_tokens + '</td>' +
        '<td style="text-align:right;">' + (c.grounding_density ? c.grounding_density.toFixed(1) : '0') + '‰</td>' +
      '</tr>';
    }).join("");

    if (gHost) {
      gHost.innerHTML = '<div class="research-card" style="margin-top:.8rem;">' +
        '<div class="research-card-title" style="margin-bottom:.5rem;">Ergebnisse: ' + escapeHtml(gres.provenance ? gres.provenance.source_title : "") + '</div>' +
        '<div class="research-compare-metric"><span>Jaccard-Ähnlichkeit (Typen):</span><strong>' + (sum.jaccard_similarity !== undefined ? (sum.jaccard_similarity * 100).toFixed(1) + '%' : 'n/a') + '</strong></div>' +
        '<div class="research-compare-metric"><span>Gemeinsame Lexem-Typen:</span><strong>' + (sum.shared_types || 0) + '</strong></div>' +
        '<div class="research-compare-metric"><span>Quell-Wörter / Manuskript-Wörter:</span><span>' + (sum.source_content_words || 0) + ' / ' + (sum.manuscript_content_words || 0) + '</span></div>' +
        (sharedWordsHtml ? '<div style="margin-top:.6rem;"><div class="ctl-label" style="margin-bottom:.3rem;">Gemeinsame Kernbegriffe</div><div class="research-tags">' + sharedWordsHtml + '</div></div>' : '') +
        (chRows ? '<div style="margin-top:.8rem;"><div class="ctl-label" style="margin-bottom:.3rem;">Kapiteldichte</div><table style="width:100%;font-size:.8rem;"><thead><tr><th style="text-align:left;">Kapitel</th><th style="text-align:right;">Tokens</th><th style="text-align:right;">Dichte</th></tr></thead><tbody>' + chRows + '</tbody></table></div>' : '') +
      '</div>';
    }
    researchStatus("Abgleich erfolgreich abgeschlossen", true);
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

    var titleVal = cTitle ? cTitle.value.trim() : "";
    var stmtVal = cStmt ? cStmt.value.trim() : "";
    if (!titleVal || !stmtVal) {
      researchStatus("Kurztitel und historische Aussage sind erforderlich", false);
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
      tags: tagsArr
    });
    researchStatus(cres.message, cres.ok);
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

  var linkEvBtn = event.target.closest("#r-link-evidence-btn");
  if (linkEvBtn) {
    var lClaim = document.getElementById("r-link-claim-select");
    var lPassage = document.getElementById("r-link-passage-id");
    var lRel = document.getElementById("r-link-relation");
    var lRat = document.getElementById("r-link-rationale");

    var claimVal = lClaim ? lClaim.value.trim() : "";
    var passageVal = lPassage ? lPassage.value.trim() : "";
    if (!claimVal || !passageVal) {
      researchStatus("These und Passagen-ID erforderlich", false);
      return;
    }

    var lres = await researchApiPost("research-evidence-link", {
      claim_id: claimVal,
      passage_id: passageVal,
      relation: lRel ? lRel.value : "supports",
      rationale: lRat ? lRat.value.trim() : ""
    });
    researchStatus(lres.message, lres.ok);
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

    var dTitleVal = decTitle ? decTitle.value.trim() : "";
    var dRatVal = decRat ? decRat.value.trim() : "";
    if (!dTitleVal || !dRatVal) {
      researchStatus("Titel und Begründung der Entscheidung sind erforderlich", false);
      return;
    }

    var dres = await researchApiPost("research-decision-add", {
      title: dTitleVal,
      rationale: dRatVal,
      claim_id: decClaim ? decClaim.value.trim() : "",
      impact_on_plot: decPlot ? decPlot.value.trim() : "",
      deviation_from_fact: decDev ? decDev.checked : false
    });
    researchStatus(dres.message, dres.ok);
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
    subpanel.innerHTML = '<span class="ctl-note">Lade Belege...</span>';
    var evData = await researchApiGet("research/claims?claim_id=" + encodeURIComponent(cid));
    if (!evData.ok) {
      subpanel.innerHTML = '<span class="ctl-note">' + escapeHtml(evData.message || "Fehler beim Laden") + '</span>';
      return;
    }
    var links = evData.evidence_links || [];
    if (!links.length) {
      subpanel.innerHTML = '<span class="ctl-note">Keine Belege mit dieser These verknüpft.</span>';
      return;
    }
    subpanel.innerHTML = '<div style="font-size:.78rem;font-weight:600;margin-bottom:.3rem;color:var(--fg);">Verknüpfte Belege (' + links.length + '):</div>' +
      links.map(function(l) {
        var relBadge = '<span class="research-badge badge-neutral" style="font-size:.7rem;">' + escapeHtml(l.relation) + '</span>';
        var cite = l.citation || {};
        var quote = cite.verbatim ? '„' + escapeHtml(cite.verbatim) + '“' : '<em>(Kein Volltextzitat)</em>';
        return '<div class="research-passage-card" style="margin:.3rem 0;padding:.4rem .6rem;">' +
          '<div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.2rem;">' +
            relBadge +
            '<span class="ctl-note" style="font-size:.74rem;">' + escapeHtml(cite.source_title || l.passage_id) + '</span>' +
          '</div>' +
          '<div class="research-passage-quote" style="font-size:.78rem;margin:.2rem 0;">' + quote + '</div>' +
          (l.rationale ? '<div class="ctl-note" style="font-size:.72rem;">' + escapeHtml(l.rationale) + '</div>' : '') +
        '</div>';
      }).join("");
    return;
  }
});

if (document.getElementById("research-manager")) { initResearchUI(); }

// --- Workspace & Project Modals -------------------------------------------
var importedFileContent = "";

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

function detectManuscriptLanguage(text) {
  var sample = text.slice(0, 10000).toLowerCase();
  var deWords = (sample.match(/\b(der|die|das|und|nicht|ein|eine|dem|den|mit|fuer|auf)\b/g) || []).length;
  var enWords = (sample.match(/\b(the|and|that|have|for|not|with|you|this|but|his|from)\b/g) || []).length;
  return deWords >= enWords ? "de" : "en";
}

function processImportedFile(file) {
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function (e) {
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

    // Language detection
    var detectedLang = detectManuscriptLanguage(text);

    // Update UI Preview
    var previewBox = document.getElementById("import-preview-box");
    if (previewBox) previewBox.style.display = "flex";

    var fNameEl = document.getElementById("import-fpc-filename");
    if (fNameEl) fNameEl.textContent = file.name;

    var statsEl = document.getElementById("import-fpc-stats");
    if (statsEl) {
      statsEl.textContent = words.toLocaleString() + " Wörter · " + chapterCount + (chapterCount === 1 ? " Kapitel" : " Kapitel");
    }

    var langEl = document.getElementById("import-fpc-lang");
    if (langEl) {
      langEl.textContent = detectedLang === "de" ? "Deutsch" : "English";
    }

    var titleInput = document.getElementById("import-proj-title");
    if (titleInput) {
      titleInput.value = detectedTitle;
    }

    var langSelect = document.getElementById("import-proj-lang");
    if (langSelect) {
      langSelect.value = detectedLang;
    }

    var submitBtn = document.getElementById("btn-submit-import-project");
    if (submitBtn) {
      submitBtn.disabled = false;
    }
  };
  reader.readAsText(file);
}

document.addEventListener("click", function (event) {
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

  var openBtn = event.target.closest("#btn-modal-open-project, #hero-btn-open-project");
  if (openBtn) {
    var modalOpen = document.getElementById("modal-project-open");
    if (modalOpen && typeof modalOpen.showModal === "function") {
      modalOpen.showModal();
      var inputOpen = document.getElementById("open-proj-path");
      if (inputOpen) inputOpen.focus();
    }
    return;
  }

  var importDrop = event.target.closest("#import-dropzone");
  if (importDrop) {
    var fileInput = document.getElementById("import-file-input");
    if (fileInput) fileInput.click();
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
  var importDrop = e.target.closest("#import-dropzone");
  if (importDrop && e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
    e.preventDefault();
    processImportedFile(e.dataTransfer.files[0]);
    return;
  }
});

document.addEventListener("change", function (event) {
  if (event.target.id === "import-file-input" && event.target.files && event.target.files.length) {
    processImportedFile(event.target.files[0]);
    return;
  }

  if (event.target.name === "proj_template") {
    document.querySelectorAll(".template-card").forEach(function (card) {
      card.classList.toggle("active", card.contains(event.target));
    });
    var rBox = document.getElementById("new-proj-research");
    if (rBox && event.target.value === "research") {
      rBox.checked = true;
    }
  }
});

// Form: Import existing manuscript
var formImport = document.getElementById("form-project-import");
if (formImport) {
  formImport.addEventListener("submit", function (e) {
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
    var modal = document.getElementById("modal-project-create");
    if (modal && typeof modal.close === "function") modal.close();

    runAction("project-create", {
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
  formCreate.addEventListener("submit", function (e) {
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
    var modal = document.getElementById("modal-project-create");
    if (modal && typeof modal.close === "function") modal.close();

    runAction("project-create", {
      title: title,
      language: lang,
      path: folder,
      template: template,
      init_research: initResearch
    }, submitBtn);
  });
}

// Form: Open existing path
var formOpen = document.getElementById("form-project-open");
if (formOpen) {
  formOpen.addEventListener("submit", function (e) {
    e.preventDefault();
    var pathEl = document.getElementById("open-proj-path");
    var path = pathEl ? pathEl.value.trim() : "";
    if (!path) return;

    var submitBtn = document.getElementById("btn-submit-open-project");
    var modal = document.getElementById("modal-project-open");
    if (modal && typeof modal.close === "function") modal.close();

    runAction("project-open", { path: path }, submitBtn);
  });
}

