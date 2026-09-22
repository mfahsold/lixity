(function () {
  var tip = document.createElement("div");
  tip.id = "lixity-tooltip";
  tip.className = "tooltip-popup";
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
    activeEl = el;
    tip.textContent = text;
    tip.classList.add("visible");
    updatePos(el);
  }

  function hide() {
    activeEl = null;
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

  window.addEventListener("scroll", function () {
    if (activeEl) updatePos(activeEl);
  }, { passive: true });

  window.addEventListener("resize", function () {
    if (activeEl) updatePos(activeEl);
  }, { passive: true });

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

function activate(el) {
  if (el.matches("td.z[data-chapter]")) { jumpToChapter(el); return; }
  if (el.hasAttribute("data-line")) { jumpToLine(el); return; }
  var key = el.getAttribute("data-layer");
  if (key && layer) { layer.value = key; applyLayer(); }
  var target = document.querySelector(el.getAttribute("data-jump") || "");
  if (target) scrollAndFlash(target);
}

function jumpToLine(row) {
  var line = parseInt(row.getAttribute("data-line"), 10);
  var chapters = document.querySelectorAll(".chapter[data-start]");
  for (var i = 0; i < chapters.length; i++) {
    var start = parseInt(chapters[i].getAttribute("data-start"), 10);
    var end = parseInt(chapters[i].getAttribute("data-end"), 10);
    if (line >= start && line <= end) { scrollAndFlash(chapters[i]); return; }
  }
}

document.addEventListener("click", function (event) {
  var chip = event.target.closest(".chip");
  if (chip) { toggleParagraph(chip); return; }
  var target = event.target.closest("[data-jump], [data-line]");
  if (target) activate(target);
});
document.addEventListener("keydown", function (event) {
  if (event.key !== "Enter" && event.key !== " ") return;
  var el = event.target.closest
    ? event.target.closest("[data-jump], [data-line], td.z[data-chapter]")
    : null;
  if (el) { event.preventDefault(); activate(el); }
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
document.addEventListener("click", async function (event) {
  var add = event.target.closest("[data-marker-add]");
  if (add) {
    markerApi({
      _action: "add",
      kind: add.dataset.markerAdd,
      line: parseInt(add.dataset.line, 10),
      note: ""
    });
    return;
  }
  var resolve = event.target.closest("[data-marker-resolve]");
  if (resolve) {
    markerApi({ _action: "resolve", id: resolve.dataset.markerResolve });
    return;
  }
});
var API = document.body.dataset.api || "";
var NDA_STATUSES = ["entwurf", "versendet", "bestaetigt", "unterschrieben"];
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
  if (hint) hint.textContent = records.length + " Einträge";
  var rows = records.map(function (r) {
    var options = NDA_STATUSES.map(function (s) {
      return '<option value="' + s + '"' + (s === r.status ? " selected" : "") + ">" + s + "</option>";
    }).join("");
    return "<tr><td><b>" + r.id + "</b></td><td>" + r.name + "</td><td>" + (r.contact || "–") +
      '</td><td><select class="ctl" data-nda-status="' + r.id + '">' + options + "</select></td>" +
      "<td>" + (r.pdf || "–") + "</td><td>" +
      '<button class="ctl" data-nda-export="' + r.id + '">PDF</button> ' +
      '<button class="ctl" data-nda-delete="' + r.id + '">✕</button></td></tr>';
  }).join("");
  host.innerHTML = records.length
    ? "<table><thead><tr><th>ID</th><th>Name</th><th>Kontakt</th><th>Status</th><th>PDF</th><th></th></tr></thead><tbody>" + rows + "</tbody></table>"
    : "";
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
async function runAction(action, payload) {
  var status = document.getElementById("ctl-status");
  if (!status) return;
  status.className = "ctl-status";
  status.textContent = "…";
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
  }
}
document.querySelectorAll("[data-action]").forEach(function (btn) {
  btn.addEventListener("click", function () {
    var payload = {};
    if (btn.dataset.payload === "format") {
      payload.format = document.getElementById("fmt").value;
    }
    if (btn.dataset.payload === "nda") {
      payload.name = document.getElementById("nda-name").value;
      payload.contact = document.getElementById("nda-contact").value;
    }
    if (btn.dataset.payload === "settings") {
      payload.language = document.getElementById("set-language").value;
      payload.title = document.getElementById("set-title").value;
    }
    if (btn.dataset.payload === "load") {
      var input = document.getElementById("ms-file");
      if (!input.files || !input.files.length) {
        var status = document.getElementById("ctl-status");
        status.className = "ctl-status err";
        status.textContent = "✗ " + (input.getAttribute("accept") || "Datei");
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
    runAction(btn.dataset.action, payload);
  });
});
