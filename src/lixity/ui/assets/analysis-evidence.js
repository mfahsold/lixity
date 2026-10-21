// Exact, verified evidence over existing prose. The component owns only its floating card.
(function() {
  "use strict";
  var chapters = document.getElementById("chapters"), select = document.getElementById("style-layer");
  if (!chapters || !select || !window.LixityComponents || !window.LixityWorkbench) return;
  var toggle = document.getElementById("analysis-evidence-enabled");
  var status = document.getElementById("analysis-evidence-status");
  var supported = Boolean(window.CSS && CSS.highlights && window.Highlight);
  var visible = new Set(), records = new Map(), epoch = 0, frame = 0, request = 0;
  var card = null, dismissTimer = 0, down = null, hoverFrame = 0, pointer = null, hoverTimer = 0, candidate = null;
  var host = document.createElement("div");
  host.id = "analysis-evidence-card"; host.className = "analysis-evidence-card"; host.hidden = true;
  document.body.appendChild(host);
  var html = LixityComponents.html;

  function active() {
    var state = LixityWorkbench.state();
    return !document.hidden && state.view === "analysis" && state.surface === "document" && state.analysisVisible &&
      !state.focus && Boolean(select.value);
  }
  function enabled() { return active() && (!toggle || toggle.checked); }
  function shown(panel) {
    if (!panel.isConnected || !panel.getClientRects().length || panel.closest("[hidden]")) return false;
    var rect = panel.getBoundingClientRect();
    return rect.bottom > 0 && rect.top < innerHeight && rect.right > 0 && rect.left < innerWidth;
  }
  function message(key) { return uiLabel(key); }
  function setStatus(value) { if (status && status.textContent !== value) status.textContent = value; }
  function clearHighlight() {
    if (!supported) return;
    CSS.highlights.delete("lixity-analysis-evidence"); CSS.highlights.delete("lixity-analysis-current");
  }
  function close(restore) {
    request++; clearTimeout(dismissTimer); clearTimeout(hoverTimer); candidate = null;
    var previous = card; card = null; host.hidden = true;
    if (supported) CSS.highlights.delete("lixity-analysis-current");
    if (restore && previous && previous.pinned && previous.trigger && previous.trigger.isConnected) previous.trigger.focus({preventScroll:true});
  }
  function paragraph(panel) { return panel.querySelector(".ptext-inner > p"); }
  function validLayer(value, length) {
    if (value && value.status === "unavailable" && value.count === null) {
      return ["sentence", "word", "pattern", "dialogue"].includes(value.kind) && value.mapped_count === 0 &&
        Array.isArray(value.spans) && value.spans.length === 0;
    }
    if (!value || !["available", "partial", "unavailable"].includes(value.status) ||
        !["sentence", "word", "pattern", "dialogue"].includes(value.kind) ||
        !Number.isSafeInteger(value.count) || value.count < 0 || !Number.isSafeInteger(value.mapped_count) ||
        value.mapped_count < 0 || value.mapped_count > value.count || !Array.isArray(value.spans)) return false;
    var count = 0;
    if (!value.spans.every(function(span) {
      if (!span || !Number.isSafeInteger(span.start) || !Number.isSafeInteger(span.end) || span.start < 0 ||
          span.end <= span.start || span.end > length || !Number.isSafeInteger(span.count) || span.count < 1) return false;
      count += span.count; return true;
    })) return false;
    return count === value.mapped_count && (value.status !== "available" || count === value.count) &&
      (value.status !== "unavailable" || value.spans.length === 0);
  }
  async function prepare(panel) {
    var prose = paragraph(panel), content = paragraphContent[panel.id], evidence = content && content[3];
    var old = records.get(panel);
    if (old && old.prose === prose && old.evidence === evidence && old.text === (content && content[0])) return old.promise;
    var record = {panel:panel, prose:prose, text:content && content[0], evidence:evidence, layers:{}, error:"evidence_unavailable"};
    records.set(panel, record);
    record.promise = (async function() {
      if (!prose || typeof record.text !== "string" || !evidence) return record;
      record.error = "evidence_mismatch";
      if (evidence.schema_version !== "paragraph-evidence/1" || evidence.offset_unit !== "unicode_codepoint" ||
          !/^[a-f0-9]{64}$/.test(evidence.paragraph_sha256 || "") || prose.textContent !== record.text ||
          !window.crypto || !crypto.subtle || !evidence.layers || typeof evidence.layers !== "object") return record;
      var digest;
      try { digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(record.text)); }
      catch (_) { return record; }
      var hash = Array.from(new Uint8Array(digest), function(byte) { return byte.toString(16).padStart(2, "0"); }).join("");
      if (hash !== evidence.paragraph_sha256 || records.get(panel) !== record || prose.textContent !== record.text) return record;
      // Build one codepoint→UTF-16 table and text-node map per actual prose generation.
      var offsets = [0], offset = 0, nodes = [], walker = document.createTreeWalker(prose, NodeFilter.SHOW_TEXT);
      for (var character of record.text) { offset += character.length; offsets.push(offset); }
      offset = 0;
      while (walker.nextNode()) {
        nodes.push({node:walker.currentNode, start:offset, end:offset + walker.currentNode.length});
        offset += walker.currentNode.length;
      }
      function point(at) {
        var low = 0, high = nodes.length - 1;
        while (low < high) {
          var middle = Math.floor((low + high) / 2);
          if (nodes[middle].end < at) low = middle + 1; else high = middle;
        }
        return {node:nodes[low].node, offset:at - nodes[low].start};
      }
      Object.keys(evidence.layers).forEach(function(key) {
        var value = evidence.layers[key];
        if (!validLayer(value, offsets.length - 1)) return;
        var spans = value.spans.map(function(span) {
          var range = document.createRange(), start = point(offsets[span.start]), end = point(offsets[span.end]);
          range.setStart(start.node, start.offset); range.setEnd(end.node, end.offset);
          return {range:range, count:span.count, words:Number.isSafeInteger(span.words) && span.words >= 0 ? span.words : null,
            quote:record.text.slice(offsets[span.start], offsets[span.end])};
        });
        record.layers[key] = {value:value, spans:spans};
      });
      record.error = null; return record;
    })();
    return record.promise;
  }
  function schedule() {
    if (frame) return;
    frame = requestAnimationFrame(function() { frame = 0; refresh(); });
  }
  async function refresh() {
    var generation = ++epoch, key = select.value;
    if (!enabled()) { clearHighlight(); setStatus(""); return; }
    var panels = Array.from(visible).filter(shown);
    var prepared = await Promise.all(panels.map(prepare));
    if (generation !== epoch || !enabled() || key !== select.value) return;
    var ranges = [], failures = [], partial = false;
    prepared.forEach(function(record) {
      if (records.get(record.panel) !== record || !shown(record.panel)) return;
      var layer = record.layers[key];
      if (record.error) failures.push(record.error);
      else if (!layer || layer.value.status === "unavailable") failures.push("evidence_unavailable");
      else {
        partial = partial || layer.value.status === "partial";
        layer.spans.forEach(function(span) { ranges.push(span.range); });
      }
    });
    if (supported) {
      var highlight = new Highlight(); ranges.forEach(function(range) {highlight.add(range);}); highlight.priority = -1;
      CSS.highlights.set("lixity-analysis-evidence", highlight);
    }
    setStatus(!supported ? message("evidence_unsupported") : failures.includes("evidence_mismatch") ? message("evidence_mismatch") :
      partial ? message("evidence_partial") : failures.length ? message("evidence_unavailable") : "");
  }
  function position(rect) {
    host.style.left = "8px"; host.style.top = "8px";
    var bounds = host.getBoundingClientRect();
    var below = innerHeight - rect.bottom - 12, above = rect.top - 12;
    var top = below >= bounds.height || below >= above ? rect.bottom + 8 : rect.top - bounds.height - 8;
    host.style.left = Math.max(8, Math.min(innerWidth - bounds.width - 8, rect.left)) + "px";
    host.style.top = Math.max(8, Math.min(innerHeight - bounds.height - 8, top)) + "px";
  }
  function paint() {
    if (!card) return;
    var record = card.record, layer = record.layers[select.value];
    var spans = layer ? layer.spans : [], span = spans[card.index];
    var chip = paragraphChips[record.panel.id], info = chip && chipLayers(chip)[select.value];
    var option = select.options[select.selectedIndex];
    var content = paragraphContent[record.panel.id], summaries = content[4];
    var summary = summaries && typeof summaries[select.value] === "string" ? summaries[select.value] : content[2];
    var warning = record.error || (!layer || layer.value.status === "unavailable" ? "evidence_unavailable" :
      layer.value.status === "partial" ? "evidence_partial" : null);
    host.setAttribute("role", "dialog"); host.setAttribute("aria-modal", "false");
    host.setAttribute("aria-labelledby", "analysis-evidence-title");
    LixityComponents.mount(host, html`<div class="analysis-evidence-heading">
      <strong id="analysis-evidence-title">${option.textContent}</strong>
      <button type="button" class="ctl" onClick=${function() {close(true);}}>${message("evidence_close")}</button>
      </div>
      ${span ? html`<blockquote aria-live=${card.pinned ? "polite" : "off"} aria-atomic="true">${span.quote}</blockquote><p>${uiCountFormat("evidence_" + layer.value.kind, span.count)}</p>` : null}
      ${span && layer.value.kind === "sentence" && span.words !== null ? html`<p class="analysis-evidence-sentence-words">${span.words} ${message(span.words === 1 ? "words_one" : "words")}</p>` : null}
      ${layer && layer.value.status !== "unavailable" ? html`<p>${uiCountFormat("evidence_coverage", layer.value.count, {mapped:layer.value.mapped_count})}</p>` : null}
      <p class="analysis-evidence-value">${info ? info[1] : summary}</p>
      ${!info ? html`<p>${message("layer_unavailable")}</p>` : null}
      ${warning ? html`<p role="status">${message(warning)}</p>` : null}
      ${!supported ? html`<p>${message("evidence_unsupported")}</p>` : null}
      <details class="analysis-evidence-guide" onToggle=${function() {if (card) position(card.rect);}}><summary>${message("layer_guide")}</summary>
        <p>${option.dataset.hint || ""}</p><p>${message("evidence_limit")}</p></details>
      ${spans.length > 1 ? html`<div class="analysis-evidence-actions">
        <button type="button" class="ctl" onClick=${function() {step(-1);}}>${message("evidence_previous")}</button>
        <span>${card.index + 1} / ${spans.length}</span>
        <button type="button" class="ctl" onClick=${function() {step(1);}}>${message("evidence_next")}</button>
      </div>` : null}`);
    host.hidden = false;
    if (supported && span && enabled()) CSS.highlights.set("lixity-analysis-current", new Highlight(span.range));
    else if (supported) CSS.highlights.delete("lixity-analysis-current");
    position(card.rect);
  }
  function step(direction) {
    if (!card) return;
    var spans = card.record.layers[select.value].spans;
    card.index = (card.index + direction + spans.length) % spans.length; card.pinned = true;
    var range = spans[card.index].range, panel = card.record.panel;
    var containers = passageScrollContainers(panel);
    setPassageScrollMargin(panel);
    var margin = parseFloat(getComputedStyle(panel).scrollMarginTop) || 12;
    containers.forEach(function(container, index) {
      var rect = range.getClientRects()[0], bounds = container.getBoundingClientRect();
      var top = bounds.top + container.clientTop + (index === 0 ? margin : 12);
      var bottom = bounds.top + container.clientTop + container.clientHeight - 12;
      if (rect.top < top || rect.bottom > bottom) container.scrollBy({top:rect.top - top, behavior:"instant"});
    });
    var rect = range.getClientRects()[0], top = containers.length ? 12 : margin;
    if (rect.top < top || rect.bottom > innerHeight - 12) window.scrollBy({top:rect.top - top, behavior:"instant"});
    // Retain this explicit arrival across its queued scroll events only while
    // all actual positions still match. Any subsequent user scroll closes it.
    card.arrival = {x:scrollX, y:scrollY, containers:containers.map(function(container) {
      return {node:container, x:container.scrollLeft, y:container.scrollTop};
    })};
    card.rect = range.getClientRects()[0]; paint();
  }
  async function inspect(panel, trigger) {
    if (!active()) return;
    var serial = ++request, key = select.value, record = await prepare(panel);
    if (serial !== request || !active() || key !== select.value || !shown(panel) || records.get(panel) !== record) return;
    card = {record:record, index:0, pinned:true, trigger:trigger || panel.querySelector(".reader-paragraph-actions"),
      rect:(trigger || panel).getBoundingClientRect()};
    paint(); host.querySelector("button").focus({preventScroll:true});
  }
  function hit(event) {
    var panel = event.target.closest(".ptext"), record = panel && records.get(panel);
    var layer = record && record.layers[select.value];
    if (!layer || !shown(panel)) return null;
    // A thousand word spans otherwise require a thousand layout rectangle reads
    // per pointer frame. Reuse only while actual prose geometry/type is unchanged;
    // search/claim DOM replacement invalidates the entire record separately.
    var bounds = record.prose.getBoundingClientRect(), style = getComputedStyle(record.prose);
    var geometry = [bounds.left, bounds.top, bounds.width, bounds.height, style.font,
      style.lineHeight, style.letterSpacing, style.wordSpacing].join("|");
    if (record.geometry !== geometry) {record.geometry = geometry; record.rects = new Map();}
    for (var index = 0; index < layer.spans.length; index++) {
      var range = layer.spans[index].range, boxes = record.rects.get(range);
      if (!boxes) {boxes = Array.from(range.getClientRects()); record.rects.set(range, boxes);}
      for (var rect of boxes) {
        if (event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom) {
          return {record:record, index:index, rect:rect};
        }
      }
    }
    return null;
  }
  function hover(event, pinned) {
    if (!enabled() || (card && card.pinned && !pinned) || !window.getSelection().isCollapsed) return;
    var match = hit(event);
    if (!match) {
      clearTimeout(hoverTimer); candidate = null;
      if (card && !card.pinned) { clearTimeout(dismissTimer); dismissTimer = setTimeout(function() {close(false);}, 180); }
      return;
    }
    clearTimeout(dismissTimer);
    if (card && card.record === match.record && card.index === match.index && !pinned) {
      clearTimeout(hoverTimer); candidate = null;
      if (card.rect.top !== match.rect.top || card.rect.left !== match.rect.left) {card.rect = match.rect; position(card.rect);}
      return;
    }
    function show() {
      candidate = null;
      if (!enabled() || records.get(match.record.panel) !== match.record || !shown(match.record.panel) ||
          !window.getSelection().isCollapsed || (!pinned && card && card.pinned)) return;
      request++; card = Object.assign(match, {pinned:Boolean(pinned), trigger:match.record.panel.querySelector(".reader-paragraph-actions")});
      paint();
    }
    if (pinned) {clearTimeout(hoverTimer); show();}
    else if (!candidate || candidate.record !== match.record || candidate.index !== match.index) {
      clearTimeout(hoverTimer); candidate = match; hoverTimer = setTimeout(show, 100);
    }
  }
  chapters.addEventListener("pointermove", function(event) {
    if (event.pointerType !== "mouse" || event.buttons) return;
    pointer = event;
    if (!hoverFrame) hoverFrame = requestAnimationFrame(function() {hoverFrame = 0; hover(pointer, false);});
  }, {passive:true});
  chapters.addEventListener("pointerleave", function(event) {
    clearTimeout(hoverTimer); candidate = null;
    if (card && !card.pinned && !host.contains(event.relatedTarget)) dismissTimer = setTimeout(function() {close(false);}, 180);
  });
  chapters.addEventListener("pointerdown", function(event) {
    if (event.pointerType !== "touch") return;
    down = {id:event.pointerId, x:event.clientX, y:event.clientY, time:Date.now(), scroll:window.scrollY};
  }, {passive:true});
  chapters.addEventListener("pointerup", function(event) {
    var start = down; down = null;
    if (start && start.id === event.pointerId && Date.now() - start.time < 500 && window.scrollY === start.scroll &&
        Math.hypot(event.clientX - start.x, event.clientY - start.y) < 8 && window.getSelection().isCollapsed) hover(event, true);
  }, {passive:true});
  chapters.addEventListener("pointercancel", function() {down = null;}, {passive:true});
  host.addEventListener("pointerenter", function() {clearTimeout(dismissTimer);});
  host.addEventListener("pointerleave", function() {if (card && !card.pinned) dismissTimer = setTimeout(function() {close(false);}, 180);});
  host.addEventListener("focusin", function() {if (card) card.pinned = true;});
  host.addEventListener("focusout", function(event) {if (event.relatedTarget && !host.contains(event.relatedTarget)) close(false);});
  document.addEventListener("pointerdown", function(event) {if (!host.contains(event.target)) close(false);}, {passive:true});
  document.addEventListener("focusin", function(event) {if (event.target.closest("dialog[open]")) close(false);});
  window.addEventListener("keydown", function(event) {
    if (event.key === "Escape" && card) {event.preventDefault(); event.stopImmediatePropagation(); close(true);}
  }, true);
  document.addEventListener("scroll", function(event) {
    if (host.contains(event.target)) return;
    down = null;
    var arrival = card && card.arrival;
    if (!arrival || arrival.x !== scrollX || arrival.y !== scrollY || arrival.containers.some(function(item) {
      return item.node.scrollLeft !== item.x || item.node.scrollTop !== item.y;
    })) close(false);
    schedule();
  }, {passive:true, capture:true});
  window.addEventListener("resize", function() {close(false); schedule();}, {passive:true});
  document.addEventListener("visibilitychange", function() {if (document.hidden) {close(false); clearHighlight();} else schedule();});
  function changed() {epoch++; close(false); clearHighlight(); schedule();}
  document.addEventListener("lixity:analysis-layer-change", changed);
  document.addEventListener("lixity:workbench-change", changed);
  document.addEventListener("lixity:viewchange", changed);
  if (toggle) toggle.addEventListener("change", changed);
  // A search/claim mark replaces text nodes. Invalidate their ranges, never the prose itself.
  new MutationObserver(function(mutations) {
    var dirty = new Set();
    mutations.forEach(function(mutation) {
      var element = mutation.target.nodeType === Node.ELEMENT_NODE ? mutation.target : mutation.target.parentElement;
      var panel = element && element.closest(".ptext");
      if (panel && (element.matches(".ptext-inner") || element.closest(".ptext-inner > p"))) dirty.add(panel);
    });
    dirty.forEach(function(panel) {records.delete(panel); if (card && card.record.panel === panel) close(false);});
    if (dirty.size) {epoch++; clearHighlight(); schedule();}
  }).observe(chapters, {childList:true, subtree:true, characterData:true});
  var observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {if (entry.isIntersecting) visible.add(entry.target); else visible.delete(entry.target);});
    schedule();
  }, {rootMargin:"128px"});
  chapters.querySelectorAll(".ptext").forEach(function(panel) {observer.observe(panel);});
  window.LixityAnalysisEvidence = {inspect:inspect, available:active};
  schedule();
})();
