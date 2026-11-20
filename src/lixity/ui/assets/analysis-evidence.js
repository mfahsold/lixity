// Exact, verified evidence over existing prose. The component owns only its floating card.
(function() {
  "use strict";
  var chapters = document.getElementById("chapters"), select = document.getElementById("style-layer");
  if (!chapters || !select || !window.LixityComponents || !window.LixityWorkbench) return;
  var toggle = document.getElementById("analysis-evidence-enabled");
  var status = document.getElementById("analysis-evidence-status");
  var supported = Boolean(window.CSS && CSS.highlights && window.Highlight);
  var visible = new Set(), records = new Map(), epoch = 0, frame = 0, request = 0;
  var spanRequest = 0;
  var card = null, opening = null, dismissTimer = 0, down = null, hoverFrame = 0, pointer = null, hoverTimer = 0, candidate = null;
  var touchTap = null, touchFallback = 0, lateTouchClick = null;
  var host = document.createElement("div");
  host.id = "analysis-evidence-card"; host.className = "analysis-evidence-card"; host.hidden = true;
  document.body.appendChild(host);
  var html = LixityComponents.html;
  var textEncoder = null, zFormatters = Object.create(null);
  var lang = document.documentElement.lang || "en";
  var percentFormat = new Intl.NumberFormat(lang, {style:"percent", maximumFractionDigits:3});
  var tensePanel = null;
  function clearTense() {
    tensePanel = null;
    if (supported) CSS.highlights.delete("lixity-tense-current");
  }

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
  function clearSelectionHighlights() {
    if (!supported) return;
    CSS.highlights.delete("lixity-analysis-current");
    CSS.highlights.delete("lixity-analysis-related");
    CSS.highlights.delete("lixity-analysis-contribution");
  }
  function clearHighlight() {
    if (!supported) return;
    CSS.highlights.delete("lixity-analysis-evidence");
    clearSelectionHighlights();
  }
  function cancelTouchTap() {
    clearTimeout(touchFallback); touchFallback = 0; touchTap = null;
  }
  function close(restore, scrolling) {
    cancelTouchTap();
    request++; clearTimeout(dismissTimer); clearTimeout(hoverTimer); candidate = null;
    var previous = card || opening; card = null; host.hidden = true;
    if (!scrolling) opening = null;
    clearSelectionHighlights();
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
  function stickyDetails(span, rule, offsets) {
    if (!Array.isArray(rule) || !Number.isSafeInteger(rule[0]) || rule[0] < 1 ||
        !Number.isFinite(rule[1]) || rule[1] <= 0 || rule[1] > 100 ||
        !Number.isSafeInteger(span.words) || span.words < rule[0] ||
        !Number.isSafeInteger(span.function_words) || span.function_words < 0 || span.function_words > span.words ||
        !Array.isArray(span.function_spans) || span.function_spans.length > span.function_words) return null;
    var pct = span.function_words / span.words * 100;
    if (pct < rule[1]) return null;
    var ranges = span.function_spans.filter(function(hit) {
      return Array.isArray(hit) && Number.isSafeInteger(hit[0]) && Number.isSafeInteger(hit[1]) &&
        span.start <= hit[0] && hit[0] < hit[1] && hit[1] <= span.end;
    }).map(function(hit) { return [offsets[hit[0]], offsets[hit[1]]]; });
    return {count:span.function_words, pct:pct, minWords:rule[0], minPct:rule[1], ranges:ranges};
  }
  async function prepare(panel) {
    var prose = paragraph(panel), content = paragraphContent[panel.id], evidence = content && content[3];
    var old = records.get(panel);
    if (old && old.prose === prose && old.evidence === evidence && old.text === (content && content[0])) return old.promise;
    var record = {panel:panel, prose:prose, text:content && content[0], evidence:evidence, layers:{}, tense:{}, error:"evidence_unavailable"};
    records.set(panel, record);
    record.promise = (async function() {
      if (!prose || typeof record.text !== "string" || !evidence) return record;
      if (!window.crypto || !crypto.subtle) {record.error = "evidence_verification_unavailable"; return record;}
      record.error = "evidence_mismatch";
      if (evidence.schema_version !== "paragraph-evidence/1" || evidence.offset_unit !== "unicode_codepoint" ||
          !/^[a-f0-9]{64}$/.test(evidence.paragraph_sha256 || "") || prose.textContent !== record.text ||
          !evidence.layers || typeof evidence.layers !== "object") return record;
      var digest;
      try { digest = await crypto.subtle.digest("SHA-256", (textEncoder || (textEncoder = new TextEncoder())).encode(record.text)); }
      catch (_) { record.error = "evidence_verification_unavailable"; return record; }
      var hash = Array.from(new Uint8Array(digest), function(byte) { return byte.toString(16).padStart(2, "0"); }).join("");
      if (hash !== evidence.paragraph_sha256 || records.get(panel) !== record || prose.textContent !== record.text) return record;
      // Build one codepoint→UTF-16 table and text-node map per actual prose generation.
      var offsets = LixityComponents.cpOffsets(record.text), offset = 0, nodes = [], walker = document.createTreeWalker(prose, NodeFilter.SHOW_TEXT);
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
      record.rangeAt = function(left, right) {
        var range = document.createRange(), start = point(left), end = point(right);
        range.setStart(start.node, start.offset); range.setEnd(end.node, end.offset);
        return range;
      };
      function prepareLayers(values, target) {
        if (!values || typeof values !== "object") return;
        Object.keys(values).forEach(function(key) {
          var value = values[key];
          if (!validLayer(value, offsets.length - 1)) return;
          var spans = value.spans.map(function(span) {
            var qctx = typeof span.quotation_context === "string" &&
              ["in_quotation", "outside_quotation", "overlaps_quotation"].includes(span.quotation_context)
              ? span.quotation_context
              : null;
            return {range:record.rangeAt(offsets[span.start], offsets[span.end]),
              count:span.count, words:Number.isSafeInteger(span.words) && span.words >= 0 ? span.words : null,
              sticky:key === "sticky" ? stickyDetails(span, value.sticky_rule, offsets) : null,
              quotation_context:qctx,
              start:offsets[span.start], end:offsets[span.end],
              quote:record.text.slice(offsets[span.start], offsets[span.end])};
          });
          target[key] = {value:value, spans:spans};
        });
      }
      prepareLayers(evidence.layers, record.layers);
      prepareLayers(evidence.tense, record.tense);
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
      if (ranges.length > 0) {
        var highlight = new Highlight(); ranges.forEach(function(range) {highlight.add(range);}); highlight.priority = -1;
        CSS.highlights.set("lixity-analysis-evidence", highlight);
      } else {
        CSS.highlights.delete("lixity-analysis-evidence");
      }
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
    var contextPanel = document.getElementById("workspace-context-panel");
    var maxRight = innerWidth - bounds.width - 8;
    if (contextPanel && !contextPanel.hidden && contextPanel.offsetWidth > 0) {
      var panelRect = contextPanel.getBoundingClientRect();
      if (panelRect.left > bounds.width + 24) {
        maxRight = panelRect.left - bounds.width - 12;
      }
      if (card && card.trigger && contextPanel.contains(card.trigger)) {
        if (panelRect.left > bounds.width + 24) {
          left = panelRect.left - bounds.width - 16;
          if (card.record && card.record.panel && card.record.panel.isConnected) {
            var pRect = card.record.panel.getBoundingClientRect();
            if (pRect.bottom > 0 && pRect.top < innerHeight) {
              top = Math.max(12, Math.min(innerHeight - bounds.height - 12, pRect.top));
            }
          }
        }
      }
    } else if ((!card || card.pointerX === undefined) && card && card.record && card.record.panel && card.record.panel.isConnected) {
      var proseBox = card.record.panel.getBoundingClientRect();
      if (proseBox.right + 14 <= maxRight) {
        left = proseBox.right + 14;
        top = Math.max(12, Math.min(innerHeight - bounds.height - 12, rect.top - 12));
      } else if (proseBox.left - bounds.width - 14 >= 8) {
        left = proseBox.left - bounds.width - 14;
        top = Math.max(12, Math.min(innerHeight - bounds.height - 12, rect.top - 12));
      }
    }
    LixityComponents.placeClampedOverlay(host, left, top, {bounds: bounds, gutter: 8});
  }
  function scrollPosition(containers, trigger) {
    if (trigger) containers = Array.from(new Set(containers.concat(passageScrollContainers(trigger))));
    return {x:scrollX, y:scrollY, containers:containers.map(function(container) {
      return {node:container, x:container.scrollLeft, y:container.scrollTop};
    })};
  }
  function markedQuote(span) {
    if (!span.sticky || !span.sticky.ranges.length) return span.quote;
    var parts = [], cursor = span.start;
    var ranges = span.sticky.ranges.slice().sort(function(left, right) {return left[0] - right[0];});
    // Merge overlaps within the quote without losing the original token counts.
    var merged = [];
    ranges.forEach(function(hit) {
      var last = merged[merged.length - 1];
      if (last && hit[0] < last[1]) last[1] = Math.max(last[1], hit[1]);
      else merged.push(hit.slice());
    });
    merged.forEach(function(hit) {
      parts.push(span.quote.slice(cursor - span.start, hit[0] - span.start));
      parts.push(html`<mark class="analysis-evidence-contribution">${span.quote.slice(hit[0] - span.start, hit[1] - span.start)}</mark>`);
      cursor = hit[1];
    });
    parts.push(span.quote.slice(cursor - span.start));
    return parts;
  }
  function paint() {
    if (!card) return;
    var record = card.record, layer = record.layers[select.value];
    var spans = layer ? layer.spans : [], span = spans[card.index];
    var chip = paragraphChips[record.panel.id], info = chip && chipLayers(chip)[select.value];
    var option = (select.selectedIndex >= 0 ? select.options[select.selectedIndex] : null) || (select.value ? select.querySelector('option[value="' + select.value + '"]') : null) || {textContent: "", dataset: {}};
    var content = paragraphContent[record.panel.id], summaries = content[4];
    var key = select.value;
    var sticky = span && span.sticky;
    var quoteCtx = span && (span.quotation_context || "unknown");
    var normalizedQuote = span && span.quote ? span.quote.normalize().toLowerCase() : "";
    var sameWordSpans = normalizedQuote && key === "echo"
      ? spans.filter(function(item) { return item.quote.normalize().toLowerCase() === normalizedQuote; })
      : [];
    var hasMetricSummary = Boolean(summaries && typeof summaries[select.value] === "string");
    var summary = hasMetricSummary ? summaries[key] : "";
    var allParagraphValues = content[2] && content[2] !== summary ? content[2] : "";
    var canEditPassage = Boolean(window.LixityManuscriptEditor && typeof window.LixityManuscriptEditor.openAtLine === "function" &&
      record.panel.dataset.start && Number(record.panel.dataset.start) > 0);
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
    var zFmt = zFormatters[lang] || (zFormatters[lang] = new Intl.NumberFormat(lang, {
      minimumFractionDigits:2, maximumFractionDigits:2, signDisplay:"always"
    }));
    var z = comparison && zFmt.format(comparison[2]);
    // Position comes from the backend's SSOT colour scale; fall back to the
    // legacy computation for cached/older payloads without element 5.
    var marker = comparison && (Number.isFinite(comparison[5])
      ? comparison[5]
      : Math.max(0, Math.min(100, 50 + comparison[2] / 2.5 * 50)));
    var reason = sticky
      ? uiCountFormat("evidence_sticky_rule", sticky.minWords, {
          words:sticky.minWords, percent:percentFormat.format(sticky.minPct / 100)
        })
      : message("evidence_reason_" + key);
    var matchSummary = sticky
      ? uiCountFormat("evidence_sticky_count", sticky.count, {words:span.words, percent:percentFormat.format(sticky.pct / 100)})
      : sameWordSpans.length ? uiCountFormat("evidence_echo_summary", sameWordSpans.length, {
          word:span.quote, total:spans.length
        }) : "";
    LixityComponents.mount(host, html`<div class="analysis-evidence-heading">
      <div class="analysis-evidence-heading-text">
        <strong id="analysis-evidence-title">${option.textContent}</strong>
        ${quoteCtx ? html`<span class="badge badge-neutral analysis-evidence-quote-context" data-quote-context=${quoteCtx}>${message("evidence_quote_" + quoteCtx)}</span>` : null}
      </div>
      <button type="button" class="ctl analysis-evidence-close" aria-label=${message("evidence_close")} onClick=${function() {close(true);}}>✕</button>
      </div>
      ${span || counted !== null ? html`<div class=${"analysis-evidence-selection" + (span && !matchSummary ? " analysis-evidence-has-quote" : "")}>
        ${span ? html`<blockquote aria-live=${card.pinned ? "polite" : "off"} aria-atomic="true">${markedQuote(span)}</blockquote>` : null}
        ${counted !== null && !matchSummary ? html`<div class="analysis-evidence-measure">
          <span class="analysis-evidence-scope">${message(span ? sentenceWords ? "evidence_sentence_scope" : "evidence_selected_scope" : "evidence_paragraph_scope")}</span>
          <div class=${"analysis-evidence-count" + (sentenceWords ? " analysis-evidence-sentence-words" : "")}><strong class="analysis-evidence-number">${counted}</strong>${" "}<span class="analysis-evidence-unit">${unit}</span></div>
        </div>` : null}
      </div>` : null}
      ${span ? html`<section class="analysis-evidence-explanation">
        <strong class="analysis-evidence-scope">${message("evidence_reason_heading")}</strong>
        ${matchSummary ? html`<p class="analysis-evidence-value">${matchSummary}</p>` : null}
        <p>${reason}</p>
        ${sticky && sticky.ranges.length ? html`<p class="analysis-evidence-key-note">
          <mark class="analysis-evidence-contribution">${message("evidence_sticky_key")}</mark>
        </p>` : null}
        ${key === "sticky" && (!sticky || sticky.ranges.length < sticky.count) ? html`<p class="analysis-evidence-warning">${message("evidence_sticky_unmapped")}</p>` : null}
        <strong class="analysis-evidence-scope">${message("evidence_review_heading")}</strong>
        <p>${message("evidence_review_" + key)}</p>
      </section>` : null}
      ${summary || comparison || allParagraphValues ? html`<section class="analysis-evidence-paragraph">
        ${summary ? html`<strong class="analysis-evidence-scope">${message("evidence_paragraph_scope")}</strong>
        <p class="analysis-evidence-value">${summary}</p>` : null}
        ${comparison ? html`<div class="analysis-evidence-comparison" style=${{"--evidence-comparison-color":comparison[0], "--evidence-comparison-position":marker + "%"}}>
          <strong class="analysis-evidence-scope">${message("evidence_comparison_scope")}</strong>
          <div class="analysis-evidence-comparison-label"><span>${message(comparison[2] < 0 ? "layer_below" : comparison[2] > 0 ? "layer_above" : "layer_at")}</span><strong>${uiFormat("evidence_comparison_z", {value:z})}</strong></div>
          <div class="analysis-evidence-scale" role="img" aria-label=${comparison[1]}><span></span></div>
        </div>` : null}
        ${allParagraphValues ? html`<details class="analysis-evidence-all-values" onToggle=${function() {if (card) position(card.rect);}}><summary>${message("evidence_all_values")}</summary>
          <p class="analysis-evidence-value">${allParagraphValues}</p></details>` : null}
      </section>` : null}
      ${warning ? html`<p class="analysis-evidence-warning" role="status">${message(warning)}</p>` : null}
      ${!supported ? html`<p class="analysis-evidence-warning">${message("evidence_unsupported")}</p>` : null}
      ${spans.length > 1 ? html`<div class="analysis-evidence-actions">
        <button type="button" class="ctl" aria-label=${message("evidence_previous")} onClick=${function() {step(-1);}}><span aria-hidden="true">←</span><span class="analysis-evidence-navigation-label">${message("evidence_previous")}</span></button>
        <span class="analysis-evidence-progress">${card.index + 1} / ${spans.length}</span>
        <button type="button" class="ctl" aria-label=${message("evidence_next")} onClick=${function() {step(1);}}><span class="analysis-evidence-navigation-label">${message("evidence_next")}</span><span aria-hidden="true">→</span></button>
      </div>` : null}
      ${canEditPassage ? html`<div class="analysis-evidence-edit-row">
        <button type="button" class="ctl" id="analysis-evidence-edit" onClick=${function() {
          var targetLine = Number(record.panel.dataset.start);
          close(false);
          window.LixityManuscriptEditor.openAtLine(targetLine);
        }}>${message("evidence_edit_passage")}</button>
      </div>` : null}
      <details class="analysis-evidence-guide" onToggle=${function() {if (card) position(card.rect);}}><summary>${message("layer_guide")}</summary>
        ${!comparison && option.dataset.inlineEvidence !== "1" ? html`<p class="analysis-evidence-unavailable">${message("evidence_comparison_missing")}</p>` : null}
        ${layer && layer.value.status !== "unavailable" ? html`<p>${uiCountFormat("evidence_coverage", layer.value.count, {mapped:layer.value.mapped_count})}</p>` : null}
        ${key === "sticky" ? html`<p>${message("evidence_reason_function")}</p>` : null}
        <p>${option.dataset.hint || ""}</p><p>${message("evidence_limit")}</p></details>`);
    host.hidden = false;
    clearSelectionHighlights();
    if (supported && span && enabled()) {
      CSS.highlights.set("lixity-analysis-current", new Highlight(span.range));
      var relatedRanges = sameWordSpans.filter(function(item) { return item !== span && item.range; }).map(function(item) { return item.range; });
      if (relatedRanges.length) {
        var related = new Highlight();
        relatedRanges.forEach(function(range) {related.add(range);});
        CSS.highlights.set("lixity-analysis-related", related);
      }
      if (sticky && sticky.ranges.length) {
        var contributions = new Highlight();
        sticky.ranges.forEach(function(hit) {contributions.add(record.rangeAt(hit[0], hit[1]));});
        contributions.priority = 1;
        CSS.highlights.set("lixity-analysis-contribution", contributions);
      }
    }
    position(card.rect);
    host.scrollTop = 0;
  }
  function step(direction) {
    if (!card) return;
    var spans = card.record.layers[select.value].spans;
    card.index = (card.index + direction + spans.length) % spans.length; card.pinned = true;
    delete card.pointerX;
    var range = spans[card.index].range, panel = card.record.panel;
    var containers = revealRange(panel, range);
    // Retain this explicit arrival across its queued scroll events only while
    // all actual positions still match. Any subsequent user scroll closes it.
    card.arrival = scrollPosition(containers, card.trigger);
    card.rect = range.getClientRects()[0] || panel.getBoundingClientRect(); paint();
  }
  function revealRange(panel, range) {
    var containers = passageScrollContainers(panel);
    setPassageScrollMargin(panel);
    var margin = parseFloat(getComputedStyle(panel).scrollMarginTop) || 12;
    containers.forEach(function(container, index) {
      var rect = range.getClientRects()[0], bounds = container.getBoundingClientRect();
      if (!rect) return;
      var top = bounds.top + container.clientTop + (index === 0 ? margin : 12);
      var bottom = bounds.top + container.clientTop + container.clientHeight - 12;
      if (rect.top < top || rect.bottom > bottom) container.scrollBy({top:rect.top - top, behavior:"instant"});
    });
    var rect = range.getClientRects()[0], top = margin;
    if (rect && (rect.top < top || rect.bottom > innerHeight - 12)) window.scrollBy({top:rect.top - top, behavior:"instant"});
    return containers;
  }
  function currentRecord(record) {
    var content = paragraphContent[record.panel.id];
    return available() && records.get(record.panel) === record && record.panel.isConnected &&
      paragraph(record.panel) === record.prose && record.prose.textContent === record.text &&
      content && content[0] === record.text && content[3] === record.evidence && !record.error;
  }
  async function tenseEvidence(panel) {
    var record = await prepare(panel);
    if (!currentRecord(record)) return null;
    var result = {};
    ["present", "past"].forEach(function(key) {
      var layer = record.tense[key];
      if (layer) result[key] = {status:layer.value.status, count:layer.value.count,
        mapped_count:layer.value.mapped_count, cues:layer.spans.map(function(span, index) {return {quote:span.quote, index:index};})};
    });
    if (record.evidence.tense && record.evidence.tense.grammar &&
        record.evidence.tense.grammar.schema_version === "grammatical-tense/1") {
      var grammar = record.evidence.tense.grammar;
      if (Array.isArray(grammar.groups)) result.grammar = grammar;
    }
    return result;
  }
  async function revealTense(panel, key, index) {
    var record = await prepare(panel), layer = record.tense[key];
    if (!currentRecord(record) || !layer || !Number.isSafeInteger(index) || index < 0 || index >= layer.spans.length) return false;
    var range = layer.spans[index].range;
    close(false); clearTense(); revealRange(panel, range); tensePanel = panel;
    if (supported) CSS.highlights.set("lixity-tense-current", new Highlight(range));
    else {
      var selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range.cloneRange());
    }
    return true;
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
    // per pointer frame. Reuse only while actual prose geometry is unchanged.
    var bounds = record.prose.getBoundingClientRect();
    if (record.boundsLeft !== bounds.left || record.boundsTop !== bounds.top ||
        record.boundsWidth !== bounds.width || record.boundsHeight !== bounds.height) {
      record.boundsLeft = bounds.left; record.boundsTop = bounds.top;
      record.boundsWidth = bounds.width; record.boundsHeight = bounds.height;
      record.rects = new Map();
    }
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
  chapters.addEventListener("click", function(event) {
    if (!event.defaultPrevented && event.pointerType === "mouse" && event.detail === 1 &&
        event.target.closest(".ptext-inner > p") && !event.target.closest("a, button, .manuscript-claim-hit")) hover(event, true);
  });
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
      var tap = touchTap = {event:event, x:event.clientX, y:event.clientY, scrollX:scrollX, scrollY:scrollY};
      // Some environments suppress the compatibility click. A bounded fallback
      // still opens the card unless a later interaction cancels the request.
      touchFallback = setTimeout(function() {finishTouchTap(tap, true);}, 500);
    }
  }, {passive:true});
  function finishTouchTap(tap, fallback) {
    if (tap !== touchTap) return;
    cancelTouchTap();
    if (scrollX !== tap.scrollX || scrollY !== tap.scrollY) return;
    if (fallback) lateTouchClick = {x:tap.x, y:tap.y, until:Date.now() + 1500};
    hover(tap.event, true);
  }
  // Open only after the matching click has acquired its original target. A
  // frame after pointerup alone can precede touchend and retarget that click.
  document.addEventListener("click", function(event) {
    if (lateTouchClick) {
      var late = lateTouchClick; lateTouchClick = null;
      if (Date.now() <= late.until && event.detail !== 0 &&
          Math.hypot(event.clientX - late.x, event.clientY - late.y) < 8) {
        event.preventDefault(); event.stopImmediatePropagation(); return;
      }
    }
    var tap = touchTap;
    if (!tap || event.detail === 0) return;
    if (!chapters.contains(event.target) || Math.hypot(event.clientX - tap.x, event.clientY - tap.y) >= 8) {
      cancelTouchTap(); return;
    }
    clearTimeout(touchFallback); touchFallback = 0;
    requestAnimationFrame(function() {finishTouchTap(tap, false);});
  }, true);
  chapters.addEventListener("pointercancel", function() {down = null; cancelTouchTap();}, {passive:true});
  host.addEventListener("pointerenter", function() {clearTimeout(dismissTimer);});
  host.addEventListener("pointerleave", function() {if (card && !card.pinned) dismissTimer = setTimeout(function() {close(false);}, 180);});
  host.addEventListener("focusin", function() {if (card) card.pinned = true;});
  host.addEventListener("focusout", function(event) {if (event.relatedTarget && !host.contains(event.relatedTarget)) close(false);});
  document.addEventListener("pointerdown", function(event) {lateTouchClick = null; cancelTouchTap(); clearTense(); if (!host.contains(event.target)) close(false);}, {passive:true});
  document.addEventListener("focusin", function(event) {if (event.target.closest("dialog[open]")) close(false);});
  window.addEventListener("keydown", function(event) {
    cancelTouchTap();
    if (event.key === "Escape") clearTense();
    if (opening && !event.defaultPrevented && !event.isComposing &&
        ["PageDown", "PageUp", "ArrowDown", "ArrowUp", "Home", "End", " "].includes(event.key) &&
        !event.target.isContentEditable && !event.target.closest("input, textarea, select")) close(false);
    if (event.key === "Escape" && (card || opening)) {event.preventDefault(); event.stopImmediatePropagation(); close(true);}
  }, true);
  document.addEventListener("wheel", function(event) {if ((opening || touchTap) && !host.contains(event.target)) close(false);}, {passive:true});
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
  document.addEventListener("visibilitychange", function() {if (document.hidden) {close(false); clearTense(); clearHighlight();} else schedule();});
  function changed() {epoch++; close(false); clearTense(); clearHighlight(); schedule();}
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
    dirty.forEach(function(panel) {records.delete(panel); if (tensePanel === panel) clearTense(); if (card && card.record.panel === panel) close(false);});
    if (dirty.size) {epoch++; clearHighlight(); schedule();}
  }).observe(chapters, {childList:true, subtree:true, characterData:true});
  var observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {if (entry.isIntersecting) visible.add(entry.target); else visible.delete(entry.target);});
    schedule();
  }, {rootMargin:"128px"});
  chapters.querySelectorAll(".ptext").forEach(function(panel) {observer.observe(panel);});
  async function inspectSpan(panel, layerKey, spanIndex, options) {
    if (!panel || !panel.isConnected || !Number.isSafeInteger(spanIndex) || spanIndex < 0) return false;
    var content = paragraphContent[panel.id], evidence = content && content[3];
    var candidateLayer = evidence && evidence.layers && evidence.layers[layerKey];
    if (!candidateLayer || !Array.isArray(candidateLayer.spans) || spanIndex >= candidateLayer.spans.length) return false;
    var serial = ++spanRequest;
    if (window.LixityWorkbench) {
      var wbState = LixityWorkbench.state();
      if (wbState.surface !== "document") {
        LixityWorkbench.dispatch({type:"surface", value:"document", analysisVisible:true});
      } else if (!wbState.analysisVisible) {
        LixityWorkbench.dispatch({type:"analysis", value:true});
      }
    }
    if (typeof revealChapter === "function") revealChapter(panel);
    var chip = paragraphChips[panel.id];
    if (chip && typeof toggleParagraph === "function") toggleParagraph(chip, true, true);
    if (layerKey && select.value !== layerKey) {
      select.value = layerKey;
      select.dispatchEvent(new Event("change", {bubbles:true}));
    }
    if (toggle && !toggle.checked) {
      toggle.checked = true;
      toggle.dispatchEvent(new Event("change", {bubbles:true}));
    }
    await new Promise(function(resolve) {requestAnimationFrame(function() {requestAnimationFrame(resolve);});});
    var record = await prepare(panel), layer = record.layers[layerKey];
    if (serial !== spanRequest || !currentRecord(record) || select.value !== layerKey || !layer || spanIndex >= layer.spans.length) return false;
    request++;
    var idx = spanIndex;
    var span = layer.spans[idx];
    var containers = revealRange(panel, span.range);
    var sourceRect = span.range.getClientRects()[0];
    var preserveFocus = options && options.preserveFocus;
    var trigger = preserveFocus && document.activeElement || panel.querySelector(".reader-paragraph-actions") || panel;
    card = {record:record, index:idx, pinned:true, trigger:trigger,
      rect:sourceRect || trigger.getBoundingClientRect(),
      arrival:scrollPosition(containers, trigger)};
    paint();
    var closeBtn = host.querySelector("button");
    if (closeBtn && !preserveFocus) closeBtn.focus({preventScroll:true});
    return true;
  }
  function available() {
    var state = LixityWorkbench.state();
    return !document.hidden && state.view === "analysis" && state.surface === "document";
  }
  window.LixityAnalysisEvidence = {inspect:inspect, inspectSpan:inspectSpan, available:available, tense:tenseEvidence, revealTense:revealTense};
  schedule();
})();
