// Local attachment state is ephemeral. Exact version metadata is supplied only
// by dossier reads; ordinary source/claim/decision Markdown stays inert.
(function () {
  "use strict";
  var uuid = "urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}";
  var target = new RegExp("^lixity:image/(" + uuid + ")/(" + uuid + ")$");
  var reads = new Map();
  var state = {generation: 0, pending: false, bytes: null, url: null, current: null, review: null};
  var dialog, form, enlarger;
  function label(key) {
    var shared = {close: "modal_close", cancel: "modal_cancel", permission: "research_retention", source_title: "research_source_title"};
    return uiLabel(shared[key] || "image_" + key);
  }
  function safe(value) { return escapeHtml(String(value == null ? "" : value)).replace(/"/g, "&quot;").replace(/'/g, "&#39;"); }
  function limits() {
    try { return JSON.parse(document.body.dataset.imageLimits || "{}"); } catch (_) { return {}; }
  }
  function capable() {
    var bounds = limits();
    return document.body.dataset.dossierImageCapable === "true" &&
      bounds.bytes > 0 && bounds.pixels > 0 && bounds.alt > 0 && bounds.caption > 0;
  }
  function escaped(text, offset) {
    var start = offset - 1;
    while (start >= 0 && text[start] === "\\") start--;
    return (offset - start - 1) % 2 === 1;
  }
  // Match the backend's code mask, including tilde fences, indented code and
  // equal-length inline backtick runs. This is a resolver, not a new renderer.
  function codeMask(text) {
    var chars = text.split(""), fence = null, offset = 0;
    (text.match(/[^\r\n]*(?:\r\n|\r|\n|$)/g) || []).forEach(function(line) {
      var content = line.replace(/[\r\n]+$/, "");
      var delimiter = content.match(/^ {0,3}(`{3,}|~{3,})(.*)$/);
      var masked = Boolean(fence) || /^(    |\t)/.test(line);
      if (fence) {
        if (delimiter && delimiter[1][0] === fence[0] && delimiter[1].length >= fence[1] && !delimiter[2].trim()) fence = null;
      } else if (delimiter && (delimiter[1][0] !== "`" || delimiter[2].indexOf("`") === -1)) {
        fence = [delimiter[1][0], delimiter[1].length]; masked = true;
      }
      if (masked) for (var n = offset; n < offset + content.length; n++) chars[n] = " ";
      offset += line.length;
    });
    var maskedText = chars.join(""), runs = Array.from(maskedText.matchAll(/`+/g));
    for (var i = 0; i < runs.length; i++) {
      if (escaped(maskedText, runs[i].index)) continue;
      var end = i + 1;
      while (end < runs.length && runs[end][0] !== runs[i][0]) end++;
      if (end === runs.length) continue;
      for (var p = runs[i].index; p < runs[end].index + runs[end][0].length; p++) {
        if (chars[p] !== "\r" && chars[p] !== "\n") chars[p] = " ";
      }
      i = end;
    }
    return chars.join("");
  }
  function imageUrl(image, context) {
    if (!image || image.project_id !== context.project_id || image.availability !== "available" ||
        !["image/png", "image/jpeg"].includes(image.media_type)) return null;
    var pin = target.exec("lixity:image/" + image.source_id + "/" + image.source_version_id);
    if (!pin) return null;
    return "/api/research/image?project_id=" + encodeURIComponent(context.project_id) +
      "&source_id=" + encodeURIComponent(pin[1]) + "&version_id=" + encodeURIComponent(pin[2]);
  }
  function sourceContextHtml(image) {
    if (!image || !image.context) return "";
    var note = image.context.provenance_note, origin = image.context.origin_url;
    var html = note ? '<p class="ctl-note">' + safe(note) + '</p>' : "";
    if (origin) {
      try {
        var parsed = new URL(origin);
        if (["http:", "https:"].includes(parsed.protocol)) html += '<p class="ctl-note"><a href="' + safe(origin) +
          '" target="_blank" rel="noopener noreferrer nofollow">' + safe(uiLabel("ctx_origin_url")) + '</a></p>';
      } catch (_) { /* Unverified metadata stays text and never initiates a fetch. */ }
    }
    return html;
  }
  function figure(alt, pin, context) {
    var image = (context.images || []).find(function(item) {
      return item.source_id === pin[1] && item.source_version_id === pin[2];
    });
    var url = imageUrl(image, context);
    if (!url) {
      var status = image && image.project_id === context.project_id ? image.availability : "missing";
      if (!["withdrawn", "purged", "missing"].includes(status)) status = "unavailable";
      return '<figure class="dossier-image dossier-image-unavailable"><figcaption><strong>' + safe(alt || label("attachment")) +
        '</strong><p>' + safe(label(status)) + '</p>' +
        (image && image.project_id === context.project_id && image.reason ? '<p class="ctl-note">' + safe(image.reason) + '</p>' : '') +
        (image && image.project_id === context.project_id ? sourceContextHtml(image) : '') +
        '</figcaption></figure>';
    }
    return '<figure class="dossier-image"><button type="button" class="dossier-image-enlarge" data-dossier-enlarge aria-label="' +
      safe(label("enlarge") + (alt ? ": " + alt : "")) + '"><img src="' + safe(url) + '" alt="' + safe(alt) +
      '" loading="lazy" decoding="async"></button><figcaption>' + safe(image.title || alt || label("attachment")) +
      ' <span class="ctl-note">' + safe(label("retained")) + '</span></figcaption></figure>';
  }
  function prepareMarkdown(raw, context) {
    var text = String(raw || ""), html = [], masked = codeMask(text);
    // A per-render token cannot collide with hostile manuscript placeholders.
    var token = "LIXITYIMAGE" + Array.from(crypto.getRandomValues(new Uint32Array(4))).join("") + "TOKEN";
    if (!context || !context.project_id || !Array.isArray(context.images)) return {text: text, html: html, token: token};
    text = text.replace(/!\[((?:\\[^\r\n]|[^\]\\\r\n])*)\]\((lixity:image[^\r\n)]*)\)/g, function(match, alt, destination, offset) {
      var pin = target.exec(destination);
      if (!pin || masked[offset] !== "!" || escaped(text, offset)) return match;
      var replacement = token + html.length + "END";
      html.push(figure(alt.replace(/\\([\\\[\]])/g, "$1"), pin, context));
      return replacement;
    });
    return {text: text, html: html, token: token};
  }
  function restoreMarkdown(html, prepared) {
    prepared.html.forEach(function(figureHtml, index) {
      var token = prepared.token + index + "END";
      html = html.replace("<p>" + token + "</p>", figureHtml).replace(token, figureHtml);
    });
    return html;
  }
  function actionsHtml(detail) {
    if (!capable() || !detail || !detail.id || !detail.project_id || !detail.snapshot || !detail.revision) return "";
    reads.set(detail.id, detail);
    return '<div class="row dossier-image-actions"><button type="button" class="ctl" data-dossier-add-image="' +
      safe(detail.id) + '">' + safe(label("add")) + '</button></div>';
  }
  function field(id) { return document.getElementById("dossier-image-" + id); }
  function status(message, error) {
    field("status").textContent = message || "";
    field("status").className = "ctl-status " + (error ? "err" : "");
  }
  function releasePreview() {
    if (state.url) URL.revokeObjectURL(state.url);
    state.url = null; state.bytes = null; state.file = null;
    if (field("preview")) field("preview").replaceChildren();
  }
  function updateSave() {
    field("save").disabled = state.pending || !state.bytes || !field("alt").value.trim() ||
      !field("retention").checked || Boolean(state.conflict);
  }
  function setBusy(busy) {
    state.pending = busy;
    form.setAttribute("aria-busy", String(busy));
    form.querySelectorAll("input, textarea, select, button").forEach(function(control) { control.disabled = busy; });
    dialog.querySelector("[data-image-close]").disabled = busy;
    if (!busy) { field("accept-current").disabled = !state.review; updateSave(); }
  }
  function makeDialog() {
    if (dialog) return;
    var bounds = limits();
    dialog = document.createElement("dialog");
    dialog.id = "modal-dossier-image"; dialog.className = "lixity-modal";
    dialog.setAttribute("aria-labelledby", "dossier-image-title");
    dialog.innerHTML = '<div class="modal-card"><div class="modal-header"><h3 id="dossier-image-title">' + safe(label("add")) +
      '</h3><button type="button" class="modal-close" data-image-close aria-label="' + safe(label("close")) + '">×</button></div>' +
      '<form id="dossier-image-form" class="modal-body"><p id="dossier-image-target" class="ctl-note"></p>' +
      '<label class="form-label" for="dossier-image-file">' + safe(label("file")) + '</label><input class="ctl" id="dossier-image-file" type="file" accept="image/png,image/jpeg,.png,.jpg,.jpeg">' +
      '<p class="ctl-note">' + safe(uiFormat("image_limits", {bytes: bounds.bytes / 1048576, pixels: bounds.pixels / 1000000})) + '</p><div id="dossier-image-preview" aria-live="polite"></div>' +
      '<label class="form-label" for="dossier-image-alt">' + safe(label("alt")) + '</label><input class="ctl" id="dossier-image-alt" type="text" required maxlength="' + bounds.alt + '">' +
      '<details id="dossier-image-options" class="research-form-options"><summary>' + safe(uiLabel("optional_details")) + '</summary>' +
      '<label class="form-label" for="dossier-image-caption">' + safe(label("caption")) + '</label><textarea class="ctl" id="dossier-image-caption" rows="3" maxlength="' + bounds.caption + '"></textarea>' +
      '<label class="form-label" for="dossier-image-source-title">' + safe(label("source_title")) + '</label><input class="ctl" id="dossier-image-source-title" type="text">' +
      '<label class="form-label" for="dossier-image-origin">' + safe(uiLabel("ctx_origin_url")) + '</label><input class="ctl" id="dossier-image-origin" type="url" maxlength="' + bounds.url + '">' +
      '<label class="form-label" for="dossier-image-note">' + safe(uiLabel("ctx_provenance_note")) + '</label><textarea class="ctl" id="dossier-image-note" rows="3" maxlength="' + bounds.note + '"></textarea>' +
      '<label class="form-label" for="dossier-image-section">' + safe(label("location")) + '</label><select class="ctl" id="dossier-image-section"></select></details>' +
      '<label class="research-check"><input id="dossier-image-retention" type="checkbox" required><span>' + safe(label("permission")) + '</span></label>' +
      '<div id="dossier-image-status" class="ctl-status" role="status" aria-live="polite"></div>' +
      '<div id="dossier-image-conflict" hidden><button type="button" class="ctl" id="dossier-image-review">' + safe(label("review")) + '</button>' +
      '<div id="dossier-image-current"></div><button type="button" class="ctl" id="dossier-image-accept-current" hidden>' + safe(label("accept_current")) + '</button></div>' +
      '<div class="modal-actions"><button type="button" class="ctl" data-image-close>' + safe(label("cancel")) + '</button><button type="submit" class="ctl ctl-primary" id="dossier-image-save" disabled>' + safe(label("save")) + '</button></div></form></div>';
    document.body.appendChild(dialog); form = field("form");
    dialog.addEventListener("cancel", function(event) { if (state.pending) event.preventDefault(); });
    dialog.addEventListener("close", function() {
      if (dialog.open) return;
      state.generation++; releasePreview(); state.current = null; state.review = null;
      if (state.trigger && state.trigger.isConnected) state.trigger.focus();
    });
    dialog.querySelectorAll("[data-image-close]").forEach(function(button) { button.addEventListener("click", function() { if (!state.pending) dialog.close(); }); });
    field("file").addEventListener("change", selectFile);
    form.addEventListener("input", updateSave);
    form.addEventListener("submit", saveAttachment);
    field("review").addEventListener("click", reviewCurrent);
    field("accept-current").addEventListener("click", function() {
      if (!state.review || state.pending) return;
      state.current = state.review; state.conflict = false; field("conflict").hidden = true;
      populateSections(state.current);
      status(label("reviewed")); updateSave();
    });
  }
  function populateSections(detail) {
    var select = field("section"), previous = select.value;
    select.replaceChildren(new Option(label("end"), ""));
    (Array.isArray(detail.editable_sections) ? detail.editable_sections : []).forEach(function(title) {
      if (typeof title === "string" && title) select.add(new Option(title, title));
    });
    if (Array.from(select.options).some(function(option) { return option.value === previous; })) select.value = previous;
  }
  function openAttachment(detail, trigger) {
    if (!capable() || state.pending || !detail || dialog && dialog.open) return;
    makeDialog(); form.reset(); releasePreview(); state.generation++;
    state.current = detail; state.trigger = trigger || document.activeElement; state.review = null; state.conflict = false;
    field("target").textContent = detail.title || (detail.record && detail.record.title) || detail.id;
    field("conflict").hidden = true; field("accept-current").hidden = true; field("current").replaceChildren();
    populateSections(detail); status(""); setBusy(false); dialog.showModal(); field("file").focus();
  }
  function preflight(bytes, filename) {
    var view = new DataView(bytes), data = new Uint8Array(bytes), bounds = limits(), width, height, type;
    if (!data.length || data.length > bounds.bytes) throw new Error(label("invalid"));
    if (data.length >= 33 && [137,80,78,71,13,10,26,10].every(function(value, index) { return data[index] === value; }) &&
        view.getUint32(8) === 13 && String.fromCharCode.apply(null, data.slice(12,16)) === "IHDR") {
      width = view.getUint32(16); height = view.getUint32(20); type = "image/png";
      // Bound the container scan before decoding: animation frames may multiply
      // memory beyond the static header's pixel count. The server checks CRCs.
      var chunkOffset = 8;
      while (chunkOffset + 12 <= data.length) {
        var chunkLength = view.getUint32(chunkOffset);
        if (chunkLength > data.length - chunkOffset - 12) throw new Error(label("invalid"));
        var chunkType = String.fromCharCode.apply(null, data.subarray(chunkOffset + 4, chunkOffset + 8));
        if (["acTL", "fcTL", "fdAT"].includes(chunkType)) throw new Error(label("invalid"));
        chunkOffset += chunkLength + 12;
        if (chunkType === "IEND") break;
      }
      if (chunkOffset !== data.length) throw new Error(label("invalid"));
    } else if (data[0] === 255 && data[1] === 216) {
      var offset = 2;
      while (offset + 4 <= data.length) {
        if (data[offset++] !== 255) throw new Error(label("invalid"));
        while (data[offset] === 255) offset++;
        var marker = data[offset++];
        if (marker === 217 || marker === 218) break;
        if (marker === 1 || marker >= 208 && marker <= 215) continue;
        if (offset + 2 > data.length) break;
        var length = view.getUint16(offset);
        if (length < 2 || offset + length > data.length) break;
        if ([192,193,194,195,197,198,199,201,202,203,205,206,207].includes(marker) && length >= 8) {
          height = view.getUint16(offset + 3); width = view.getUint16(offset + 5); type = "image/jpeg"; break;
        }
        offset += length;
      }
    }
    var suffix = /\.png$/i.test(filename) ? "image/png" : /\.jpe?g$/i.test(filename) ? "image/jpeg" : null;
    if (!type || type !== suffix || !width || !height || width * height > bounds.pixels) throw new Error(label("invalid"));
    return {width: width, height: height, type: type};
  }
  async function selectFile() {
    var generation = ++state.generation, file = field("file").files[0];
    releasePreview(); status(""); updateSave();
    if (!file) return;
    if (file.size > limits().bytes || !/\.(png|jpe?g)$/i.test(file.name)) { status(label("invalid"), true); return; }
    try {
      var bytes = await file.arrayBuffer();
      if (generation !== state.generation || !dialog.open) return;
      var info = preflight(bytes, file.name), url = URL.createObjectURL(new Blob([bytes], {type: info.type}));
      var image = new Image(); image.alt = label("preview"); image.src = url;
      try { await image.decode(); } catch (_) { URL.revokeObjectURL(url); throw new Error(label("invalid")); }
      if (generation !== state.generation || !dialog.open) { URL.revokeObjectURL(url); return; }
      if (image.naturalWidth !== info.width || image.naturalHeight !== info.height) { URL.revokeObjectURL(url); throw new Error(label("invalid")); }
      state.bytes = bytes; state.url = url; state.file = file;
      var caption = document.createElement("p"); caption.className = "ctl-note";
      caption.textContent = file.name + " · " + info.width + " × " + info.height;
      field("preview").replaceChildren(image, caption); updateSave();
    } catch (error) { if (generation === state.generation && dialog.open) { status(error.message || label("invalid"), true); updateSave(); } }
  }
  function base64(bytes) {
    var data = new Uint8Array(bytes), chunks = [];
    for (var offset = 0; offset < data.length; offset += 32768) chunks.push(String.fromCharCode.apply(null, data.subarray(offset, offset + 32768)));
    return btoa(chunks.join(""));
  }
  async function saveAttachment(event) {
    event.preventDefault();
    if (state.pending || field("save").disabled || !form.reportValidity()) return;
    var current = state.current, record = current.record || current;
    var payload = {project_id: current.project_id, dossier_id: record.id, filename: state.file.name,
      content_base64: base64(state.bytes), allow_retention: true, expected_snapshot: current.snapshot,
      expected_revision: record.revision, alt: field("alt").value.trim()};
    if (field("caption").value) payload.caption = field("caption").value;
    if (field("source-title").value.trim()) payload.title = field("source-title").value.trim();
    if (field("note").value.trim()) payload.context = {provenance_note: field("note").value.trim()};
    if (field("origin").value.trim()) {
      try { var origin = new URL(field("origin").value.trim()); if (!["https:","http:"].includes(origin.protocol)) throw new Error(); }
      catch (_) { status(label("invalid_origin"), true); return; }
      payload.origin_url = field("origin").value.trim();
    }
    if (field("section").value) payload.section = field("section").value;
    setBusy(true); status(label("saving"));
    var result;
    try { result = await researchApiPost("research-dossier-image", payload); }
    catch (_) { result = {ok: false, message: label("failed")}; }
    if (!result.ok) {
      state.conflict = result.http_status === 409;
      status(state.conflict ? label("conflict") : result.message || label("failed"), true);
      field("conflict").hidden = !state.conflict; state.review = null; field("accept-current").hidden = true;
      setBusy(false); return;
    }
    setBusy(false); dialog.close();
    document.dispatchEvent(new CustomEvent("lixity:dossier-image-saved", {detail: result}));
  }
  async function reviewCurrent() {
    if (state.pending || !state.current) return;
    var current = state.current, id = (current.record || current).id;
    setBusy(true);
    var result;
    try { result = await researchApiGet("research/dossiers?id=" + encodeURIComponent(id)); }
    catch (_) { result = {ok: false}; }
    if (result.ok && result.project_id === current.project_id) {
      state.review = result;
      field("current").innerHTML = '<p class="ctl-note">' + safe(uiFormat("research_revision_number", {revision: result.revision})) +
        '</p><div class="research-prose markdown-body">' + renderSafeMarkdown(result.body, result) + '</div>';
      field("accept-current").hidden = false;
    } else status(result.message || label("failed"), true);
    setBusy(false);
  }
  function enlarge(button) {
    var source = button.querySelector("img");
    if (!source || !source.complete || !source.naturalWidth) return;
    if (!enlarger) {
      enlarger = document.createElement("dialog"); enlarger.id = "modal-dossier-image-enlarge"; enlarger.className = "lixity-modal";
      enlarger.setAttribute("aria-label", label("enlarge"));
      enlarger.innerHTML = '<div class="modal-card"><div class="modal-header"><h3>' + safe(label("attachment")) +
        '</h3><button type="button" class="modal-close" aria-label="' + safe(label("close")) + '">×</button></div><div class="modal-body"></div></div>';
      document.body.appendChild(enlarger);
      enlarger.querySelector("button").addEventListener("click", function() { enlarger.close(); });
      enlarger.addEventListener("close", function() { enlarger.querySelector(".modal-body").replaceChildren(); if (enlarger.trigger && enlarger.trigger.isConnected) enlarger.trigger.focus(); });
    }
    enlarger.trigger = button;
    var image = source.cloneNode(); image.loading = "eager";
    enlarger.querySelector(".modal-body").replaceChildren(image); enlarger.showModal();
  }
  document.addEventListener("click", function(event) {
    var add = event.target.closest("[data-dossier-add-image]");
    if (add) openAttachment(reads.get(add.dataset.dossierAddImage), add);
    var button = event.target.closest("[data-dossier-enlarge]");
    if (button) enlarge(button);
  });
  document.addEventListener("error", function(event) {
    var image = event.target;
    if (!(image instanceof HTMLImageElement) || !image.closest(".dossier-image")) return;
    var figureNode = image.closest(".dossier-image"), note = document.createElement("p");
    note.textContent = label("unavailable"); note.className = "ctl-note";
    image.closest("button").replaceWith(note); figureNode.classList.add("dossier-image-unavailable");
  }, true);
  window.LixityDossierImages = {prepareMarkdown: prepareMarkdown, restoreMarkdown: restoreMarkdown,
    actionsHtml: actionsHtml, openAttachment: openAttachment};
})();
