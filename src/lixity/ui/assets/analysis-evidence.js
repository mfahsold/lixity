// Exact, verified evidence over existing prose. The component owns only its floating card.
(function() {
  "use strict";
  var chapters = document.getElementById("chapters"), select = document.getElementById("style-layer");
  if (!chapters || !select || !window.LixityComponents || !window.LixityWorkbench) return;
  var toggle = document.getElementById("analysis-evidence-enabled");
  var status = document.getElementById("analysis-evidence-status");
  var supported = Boolean(window.CSS && CSS.highlights && window.Highlight);
  var visible = new Set(), records = new Map(), epoch = 0, frame = 0, request = 0;
  var card = null, opening = null, dismissTimer = 0, down = null, hoverFrame = 0, pointer = null, hoverTimer = 0, candidate = null;
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
  function close(restore, scrolling) {
    request++; clearTimeout(dismissTimer); clearTimeout(hoverTimer); candidate = null;
    var previous = card || opening; card = null; host.hidden = true;
    if (!scrolling) opening = null;
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
      if (!window.crypto || !crypto.subtle) {record.error = "evidence_verification_unavailable"; return record;}
      record.error = "evidence_mismatch";
      if (evidence.schema_version !== "paragraph-evidence/1" || evidence.offset_unit !== "unicode_codepoint" ||
          !/^[a-f0-9]{64}$/.test(evidence.paragraph_sha256 || "") || prose.textContent !== record.text ||
          !evidence.layers || typeof evidence.layers !== "object") return record;
      var digest;
      try { digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(record.text)); }
      catch (_) { record.error = "evidence_verification_unavailable"; return record; }
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
            start:offsets[span.start], end:offsets[span.end],
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
      failures.includes("evidence_verification_unavailable") ? message("evidence_verification_unavailable") :
      partial ? message("evidence_partial") : failures.length ? message("evidence_unavailable") : "");
  }
  function position(rect) {
    host.style.left = "8px"; host.style.top = "8px";
    var bounds = host.getBoundingClientRect();
    var below = innerHeight - rect.bottom - 12, above = rect.top - 12;
    var top = below >= bounds.height || below >= above ? rect.bottom + 8 : rect.top - bounds.height - 8;
    var left = card && card.pointerX !== undefined ? card.pointerX + 12 : rect.left;
    host.style.left = Math.max(8, Math.min(innerWidth - bounds.width - 8, left)) + "px";
    host.style.top = Math.max(8, Math.min(innerHeight - bounds.height - 8, top)) + "px";
  }
  function scrollPosition(containers, trigger) {
    if (trigger) containers = Array.from(new Set(containers.concat(passageScrollContainers(trigger))));
    return {x:scrollX, y:scrollY, containers:containers.map(function(container) {
      return {node:container, x:container.scrollLeft, y:container.scrollTop};
    })};
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
    var sentenceWords = span && layer.value.kind === "sentence" && span.words !== null;
    var counted = span ? (sentenceWords ? span.words : span.count) :
      !record.error && layer && layer.value.status !== "unavailable" && layer.value.count === 0 ? 0 : null;
    var unitKey = sentenceWords || layer && layer.value.kind === "dialogue" ? "words" :
      layer && layer.value.kind === "sentence" ? "evidence_sentence_unit" : "evidence_match_unit";
    var unit = counted === 1 ? message(unitKey === "words" ? "words_one" : unitKey + "_one") : message(unitKey);
    var comparison = info && Number.isFinite(info[2]) ? info : null;
    var z = comparison && new Intl.NumberFormat(document.documentElement.lang, {
      minimumFractionDigits:2, maximumFractionDigits:2, signDisplay:"always"
    }).format(comparison[2]);
    var marker = comparison && Math.max(0, Math.min(100, 50 + comparison[2] / 2.5 * 50));
    LixityComponents.mount(host, html`<div class="analysis-evidence-heading">
      <strong id="analysis-evidence-title">${option.textContent}</strong>
      <button type="button" class="ctl analysis-evidence-close" aria-label=${message("evidence_close")} onClick=${function() {close(true);}}>✕</button>
      </div>
      ${span || counted !== null ? html`<div class=${"analysis-evidence-selection" + (span ? " analysis-evidence-has-quote" : "")}>
        ${span ? html`<blockquote aria-live=${card.pinned ? "polite" : "off"} aria-atomic="true">${span.quote}</blockquote>` : null}
        ${counted !== null ? html`<div class="analysis-evidence-measure">
          <span class="analysis-evidence-scope">${message(span ? sentenceWords ? "evidence_sentence_scope" : "evidence_selected_scope" : "evidence_paragraph_scope")}</span>
          <div class=${"analysis-evidence-count" + (sentenceWords ? " analysis-evidence-sentence-words" : "")}><strong class="analysis-evidence-number">${counted}</strong>${" "}<span class="analysis-evidence-unit">${unit}</span></div>
        </div>` : null}
      </div>` : null}
      <section class="analysis-evidence-paragraph">
        <strong class="analysis-evidence-scope">${message("evidence_paragraph_scope")}</strong>
        <p class="analysis-evidence-value">${summary}</p>
        ${comparison ? html`<div class="analysis-evidence-comparison" style=${{"--evidence-comparison-color":comparison[0], "--evidence-comparison-position":marker + "%"}}>
          <strong class="analysis-evidence-scope">${message("evidence_comparison_scope")}</strong>
          <div class="analysis-evidence-comparison-label"><span>${message(comparison[2] < 0 ? "layer_below" : comparison[2] > 0 ? "layer_above" : "layer_at")}</span><strong>${uiFormat("evidence_comparison_z", {value:z})}</strong></div>
          <div class="analysis-evidence-scale" role="img" aria-label=${comparison[1]}><span></span></div>
        </div>` : html`<p class="analysis-evidence-unavailable">${message("evidence_comparison_missing")}</p>`}
      </section>
      ${warning ? html`<p class="analysis-evidence-warning" role="status">${message(warning)}</p>` : null}
      ${!supported ? html`<p class="analysis-evidence-warning">${message("evidence_unsupported")}</p>` : null}
      ${spans.length > 1 ? html`<div class="analysis-evidence-actions">
        <button type="button" class="ctl" aria-label=${message("evidence_previous")} onClick=${function() {step(-1);}}><span aria-hidden="true">←</span><span class="analysis-evidence-navigation-label">${message("evidence_previous")}</span></button>
        <span class="analysis-evidence-progress">${card.index + 1} / ${spans.length}</span>
        <button type="button" class="ctl" aria-label=${message("evidence_next")} onClick=${function() {step(1);}}><span class="analysis-evidence-navigation-label">${message("evidence_next")}</span><span aria-hidden="true">→</span></button>
      </div>` : null}
      <details class="analysis-evidence-guide" onToggle=${function() {if (card) position(card.rect);}}><summary>${message("layer_guide")}</summary>
        ${layer && layer.value.status !== "unavailable" ? html`<p>${uiCountFormat("evidence_coverage", layer.value.count, {mapped:layer.value.mapped_count})}</p>` : null}
        <p>${option.dataset.hint || ""}</p><p>${message("evidence_limit")}</p></details>`);
    host.hidden = false;
    if (supported && span && enabled()) CSS.highlights.set("lixity-analysis-current", new Highlight(span.range));
    else if (supported) CSS.highlights.delete("lixity-analysis-current");
    position(card.rect);
    host.scrollTop = 0;
  }
  function step(direction) {
    if (!card) return;
    var spans = card.record.layers[select.value].spans;
    card.index = (card.index + direction + spans.length) % spans.length; card.pinned = true;
    delete card.pointerX;
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
    card.arrival = scrollPosition(containers, card.trigger);
    card.rect = range.getClientRects()[0]; paint();
  }
  async function inspect(panel, trigger, point) {
    opening = null;
    if (!available()) return;
    var settleLayout = trigger && trigger.closest("#reader-inspector") && trigger.dataset.readerEvidenceParagraph === panel.id;
    if (!active() && window.LixityReader) {
      window.LixityReader.enableEvidence();
      settleLayout = true;
    }
    if (settleLayout) {
      var intent = {key:select.value, pinned:true, trigger:trigger || panel.querySelector(".reader-paragraph-actions")};
      opening = intent;
      // Settle the reader's queued passage/dock arrival before anchoring the card.
      await new Promise(function(resolve) {requestAnimationFrame(function() {requestAnimationFrame(resolve);});});
      if (opening !== intent || select.value !== intent.key) return;
      opening = null;
    }
    if (!active()) return;
    var verification = {key:select.value, pinned:true, trigger:trigger || panel.querySelector(".reader-paragraph-actions"),
      arrival:scrollPosition(passageScrollContainers(panel), trigger)};
    opening = verification;
    var serial = ++request, key = select.value, record = await prepare(panel);
    var inspectorTrigger = trigger && trigger.isConnected && trigger.closest("#reader-inspector") && trigger.dataset.readerEvidenceParagraph === panel.id &&
      panel.classList.contains("reader-inspector-target") && shown(trigger) &&
      panel.isConnected && panel.getClientRects().length && !panel.closest("[hidden]");
    if (serial !== request || opening !== verification || !active() || key !== select.value ||
        (!shown(panel) && !inspectorTrigger) || records.get(panel) !== record) {
      if (opening === verification) opening = null;
      return;
    }
    opening = null;
    var layer = record.layers[key], index = -1;
    if (point && !record.error && point.hash === record.evidence.paragraph_sha256 && Number.isSafeInteger(point.offset) && layer) {
      index = layer.spans.findIndex(function(span) {return span.start <= point.offset && point.offset < span.end;});
      if (index < 0) index = layer.spans.findIndex(function(span) {return point.offset === span.end;});
    }
    var span = index >= 0 && layer.spans[index];
    var sourceRect = span && span.range.getClientRects()[0];
    var rangeVisible = sourceRect && sourceRect.bottom > 0 && sourceRect.top < innerHeight && sourceRect.right > 0 && sourceRect.left < innerWidth;
    card = {record:record, index:index >= 0 ? index : 0, pinned:true, trigger:trigger || panel.querySelector(".reader-paragraph-actions"),
      rect:rangeVisible ? sourceRect : (trigger || panel).getBoundingClientRect(),
      arrival:scrollPosition(passageScrollContainers(panel), trigger)};
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
          return {record:record, index:index, rect:rect, pointerX:event.clientX};
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
      if (card.rect.top !== match.rect.top || card.rect.left !== match.rect.left) {
        card.rect = match.rect; card.pointerX = match.pointerX; position(card.rect);
      }
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
    } else {
      // The dwell may finish on a later line of the same sentence.
      candidate.rect = match.rect; candidate.pointerX = match.pointerX;
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
        Math.hypot(event.clientX - start.x, event.clientY - start.y) < 8 && window.getSelection().isCollapsed) {
      // Finish the tap's synthetic click before inserting a card beneath the finger.
      requestAnimationFrame(function() {hover(event, true);});
    }
  }, {passive:true});
  chapters.addEventListener("pointercancel", function() {down = null;}, {passive:true});
  host.addEventListener("pointerenter", function() {clearTimeout(dismissTimer);});
  host.addEventListener("pointerleave", function() {if (card && !card.pinned) dismissTimer = setTimeout(function() {close(false);}, 180);});
  host.addEventListener("focusin", function() {if (card) card.pinned = true;});
  host.addEventListener("focusout", function(event) {if (event.relatedTarget && !host.contains(event.relatedTarget)) close(false);});
  document.addEventListener("pointerdown", function(event) {if (!host.contains(event.target)) close(false);}, {passive:true});
  document.addEventListener("focusin", function(event) {if (event.target.closest("dialog[open]")) close(false);});
  window.addEventListener("keydown", function(event) {
    if (opening && !event.defaultPrevented && !event.isComposing &&
        ["PageDown", "PageUp", "ArrowDown", "ArrowUp", "Home", "End", " "].includes(event.key) &&
        !event.target.isContentEditable && !event.target.closest("input, textarea, select")) close(false);
    if (event.key === "Escape" && (card || opening)) {event.preventDefault(); event.stopImmediatePropagation(); close(true);}
  }, true);
  document.addEventListener("wheel", function(event) {if (opening && !host.contains(event.target)) close(false);}, {passive:true});
  document.addEventListener("scroll", function(event) {
    if (host.contains(event.target)) return;
    down = null;
    var arrival = card && card.arrival || opening && opening.arrival;
    // Reader restoration emits scroll while an explicit opening settles. Actual
    // pointer, wheel, keyboard and state changes cancel that opening separately.
    if (!arrival || arrival.x !== scrollX || arrival.y !== scrollY || arrival.containers.some(function(item) {
      return item.node.scrollLeft !== item.x || item.node.scrollTop !== item.y;
    })) close(false, true);
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
  function available() {
    var state = LixityWorkbench.state();
    return !document.hidden && state.view === "analysis" && state.surface === "document";
  }
  window.LixityAnalysisEvidence = {inspect:inspect, available:available};
  schedule();
})();
