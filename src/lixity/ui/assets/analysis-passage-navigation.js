// Route verified analysis and motif locations to the manuscript reader.
(function initCraftNavigationAndMotifs() {
  var chapters = document.getElementById("chapters");
  if (!chapters || typeof paragraphContent !== "object") return;
  var C = window.LixityComponents;
  var el = C.el.bind(C);
  var chapterForPanel = new Map();
  var panelIds = Array.from(chapters.querySelectorAll(".ptext[id]")).map(function (node) {
    var chapter = node.closest(".chapter");
    if (chapter) chapterForPanel.set(node.id, chapter.id.slice(3));
    return node.id;
  });
  var L = function (key) { return typeof uiLabel === "function" ? uiLabel(key) : key; };

  var pacingPanel = document.getElementById("pacing");
  var sentenceGroupMatches = null;
  if (pacingPanel && pacingPanel.dataset.sentenceGroupMatches) {
    try { sentenceGroupMatches = JSON.parse(pacingPanel.dataset.sentenceGroupMatches); } catch (_) { sentenceGroupMatches = null; }
  }

  // --- Step 2: Rhythm sentences, sticky sentences & word-pattern jumps ----
  var craftBar = C.ensureJumpBar("craft-jump-bar", "craft-jump-bar", chapters);
  var activeJump = null;
  var craftRequest = 0;

  function restoreJumpOrigin(origin) {
    if (!origin || !origin.isConnected) origin = document.getElementById("workbench-overview-open");
    if (!origin) return;
    scrollAndFlash(origin, {behavior:"auto", block:"center"});
    origin.focus({preventScroll:true});
  }

  function clearCraftJump(restore) {
    var origin = activeJump && activeJump.origin;
    craftRequest++;
    activeJump = null;
    renderCraftBar();
    if (restore) restoreJumpOrigin(origin);
  }

  function renderCraftBar() {
    C.renderJumpBar(craftBar, activeJump && activeJump.items.length ? {
      visible: true,
      labelClass: "craft-jump-label",
      label: activeJump.label + " · " + (activeJump.index + 1) + " / " + activeJump.items.length +
        (activeJump.unavailable ? " · " + L("evidence_unavailable") : ""),
      onPrev: function () { stepCraftJump(-1); },
      onNext: function () { stepCraftJump(1); },
      onClose: function () { clearCraftJump(true); }
    } : null);
  }

  async function openCraftItem(item, preserveFocus) {
    var panel = document.getElementById(item.paragraphId);
    if (!panel) return;
    var serial = ++craftRequest;
    if (window.LixityAnalysisEvidence && typeof window.LixityAnalysisEvidence.inspectSpan === "function") {
      var opened = await window.LixityAnalysisEvidence.inspectSpan(
        panel, item.layerKey, item.spanIndex, {preserveFocus:preserveFocus}
      );
      if (opened) return;
    }
    if (serial !== craftRequest) return;
    if (activeJump) {
      activeJump.unavailable = true;
      renderCraftBar();
    }
    var chip = paragraphChips[panel.id];
    if (chip) toggleParagraph(chip, true, true);
    scrollAndFlash(panel, { analysisVisible: true });
  }

  function stepCraftJump(dir) {
    if (!activeJump || !activeJump.items.length) return;
    activeJump.index = (activeJump.index + dir + activeJump.items.length) % activeJump.items.length;
    activeJump.unavailable = false;
    renderCraftBar();
    openCraftItem(activeJump.items[activeJump.index], true);
  }

  function evidenceChapter(control) {
    var section = control.closest("#pacing, #showing");
    var select = section && section.querySelector("[data-evidence-chapter]");
    return select ? select.value : "";
  }
  function inChapter(panelId, chapter) {
    return !chapter || chapterForPanel.get(panelId) === chapter;
  }

  function collectSentenceMatches(minWords, maxWords, chapter) {
    var items = [];
    panelIds.forEach(function (pid) {
      if (!inChapter(pid, chapter)) return;
      var content = paragraphContent[pid], ev = content && content[3];
      var asl = ev && ev.layers && ev.layers.asl;
      if (!asl || !Array.isArray(asl.spans)) return;
      asl.spans.forEach(function (span, idx) {
        if (!Number.isSafeInteger(span.words)) return;
        if (span.words < minWords) return;
        if (maxWords !== null && span.words > maxWords) return;
        items.push({ paragraphId: pid, layerKey: "asl", spanIndex: idx });
      });
    });
    return items;
  }

  function resolveRhythmMatches(target) {
    var chapter = evidenceChapter(target);
    var groupKey = target && target.dataset && target.dataset.rhythmGroup;
    if (groupKey && sentenceGroupMatches) {
      var bucket = target.closest("#pacing-rhythm-buckets") ? sentenceGroupMatches.rhythm : sentenceGroupMatches.distribution;
      var list = bucket && bucket[groupKey];
      if (Array.isArray(list)) {
        return list.filter(function (m) { return inChapter(m.paragraph_id, chapter); }).map(function (m) {
          return { paragraphId: m.paragraph_id, layerKey: "asl", spanIndex: m.span_index };
        });
      }
    }
    var minW = Number(target.dataset.rhythmMinWords);
    var maxW = target.dataset.rhythmMaxWords ? Number(target.dataset.rhythmMaxWords) : null;
    if (!Number.isFinite(minW)) return [];
    return collectSentenceMatches(minW, maxW, chapter);
  }

  function collectLayerMatches(layerKey, chapter) {
    var items = [];
    panelIds.forEach(function (pid) {
      if (!inChapter(pid, chapter)) return;
      var content = paragraphContent[pid], ev = content && content[3];
      var layerObj = ev && ev.layers && ev.layers[layerKey];
      if (!layerObj || !Array.isArray(layerObj.spans)) return;
      layerObj.spans.forEach(function (_span, idx) {
        items.push({ paragraphId: pid, layerKey: layerKey, spanIndex: idx });
      });
    });
    return items;
  }

  function jumpToRhythmGroup(elTarget) {
    var items = resolveRhythmMatches(elTarget);
    if (!items.length) return;
    if (activeMotif) clearMotifSelection();
    activeJump = { label: elTarget.dataset.rhythmLabel || L("sentence_dist"), items: items, index: 0, origin: elTarget };
    renderCraftBar();
    openCraftItem(items[0]);
  }
  window.LixityJumpToRhythmGroup = jumpToRhythmGroup;

  function refreshEvidenceActions(root) {
    root.querySelectorAll(".rhythm-jump-btn[data-rhythm-min-words]").forEach(function (btn) {
      btn.hidden = !resolveRhythmMatches(btn).length;
    });
    root.querySelectorAll("[data-pattern-jump]").forEach(function (btn) {
      btn.disabled = !collectLayerMatches(btn.dataset.layer, evidenceChapter(btn)).length;
    });
  }
  refreshEvidenceActions(document);
  document.querySelectorAll(".chapter-evidence-actions").forEach(function (strip) {
    var picker = strip.querySelector("[data-evidence-chapter]");
    if (!picker) return;
    strip.hidden = !strip.querySelector("[data-pattern-jump]:not([disabled]), .rhythm-jump-btn:not([hidden])");
    picker.addEventListener("change", function () { refreshEvidenceActions(strip.closest(".panel")); });
  });

  document.addEventListener("click", function (event) {
    var rhythmBtn = event.target.closest(".rhythm-jump-btn[data-rhythm-min-words]");
    if (rhythmBtn) { jumpToRhythmGroup(rhythmBtn); return; }
    var stickyBtn = event.target.closest("[data-sticky-jump]");
    if (stickyBtn) {
      var targetId = stickyBtn.dataset.target;
      var sIdx = Number(stickyBtn.dataset.spanIndex || 0);
      var allSticky = collectLayerMatches("sticky");
      var found = allSticky.findIndex(function (item) {
        return item.paragraphId === targetId && item.spanIndex === sIdx;
      });
      if (found >= 0) {
        if (activeMotif) clearMotifSelection();
        activeJump = { label: L("pac_sticky_items"), items: allSticky, index: found, origin: stickyBtn };
        renderCraftBar();
      }
      openCraftItem({ paragraphId: targetId, layerKey: "sticky", spanIndex: sIdx });
      return;
    }
    var patternBtn = event.target.closest("[data-pattern-jump]");
    if (patternBtn) {
      var key = patternBtn.dataset.layer;
      var items = collectLayerMatches(key, evidenceChapter(patternBtn));
      if (!items.length) return;
      if (activeMotif) clearMotifSelection();
      activeJump = { label: patternBtn.textContent.trim(), items: items, index: 0, origin: patternBtn };
      renderCraftBar();
      openCraftItem(items[0]);
    }
  });

  // --- Step 3: Recurring word sequences & custom search patterns ----------
  var motifBar = C.ensureJumpBar("motif-selection-bar", "motif-selection-bar", chapters);
  var activeMotif = null;

  function renderMotifBar() {
    if (!activeMotif || !activeMotif.occurrences.length) {
      C.renderJumpBar(motifBar, null);
      return;
    }
    var pos = (activeMotif.index + 1) + " / " + activeMotif.occurrences.length;
    C.renderJumpBar(motifBar, {
      visible: true,
      labelClass: "motif-selection-label",
      label: L("mot_selected_prefix") + " " + activeMotif.label + " · " + pos,
      closeLabel: L("mot_clear_selection"),
      onPrev: function () { stepMotifOccurrence(-1); },
      onNext: function () { stepMotifOccurrence(1); },
      onClose: function () { clearMotifSelection(true); }
    });
    var status = motifBar.querySelector("[role='status']");
    status.id = "motif-selection-status";
    motifBar.querySelectorAll("button").forEach(function (control) {
      control.setAttribute("aria-describedby", status.id);
    });
  }

  function refreshParagraphMotifMarks() {
    var changed = new Set(Object.keys(manuscriptMotifMarks));
    changed.forEach(function (pid) {
      var chip = paragraphChips[pid];
      if (chip) chip.classList.remove("motif-hit");
    });
    Object.keys(manuscriptMotifMarks).forEach(function (k) { delete manuscriptMotifMarks[k]; });
    if (activeMotif && activeMotif.occurrences.length) {
      activeMotif.occurrences.forEach(function (occ, idx) {
        var pid = occ.paragraph_id;
        changed.add(pid);
        if (!manuscriptMotifMarks[pid]) manuscriptMotifMarks[pid] = [];
        manuscriptMotifMarks[pid].push({
          start: occ.startU16,
          end: occ.endU16,
          motif: true,
          current: idx === activeMotif.index,
        });
        var chip = paragraphChips[pid];
        if (chip) chip.classList.add("motif-hit");
      });
    }
    changed.forEach(function (pid) {
      var panel = document.getElementById(pid);
      var p = panel && panel.querySelector(".ptext-inner > p");
      if (p) renderParagraphText(p, p.dataset.searchQuery || "");
    });
  }

  function clearMotifSelection(restore) {
    var origin = activeMotif && activeMotif.origin;
    activeMotif = null;
    refreshParagraphMotifMarks();
    renderMotifBar();
    document.querySelectorAll("[data-motif-select]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", "false");
    });
    if (restore) restoreJumpOrigin(origin);
  }

  function jumpToMotifOccurrence(index) {
    if (!activeMotif || !activeMotif.occurrences.length) return;
    activeMotif.index = ((index % activeMotif.occurrences.length) + activeMotif.occurrences.length) % activeMotif.occurrences.length;
    var occ = activeMotif.occurrences[activeMotif.index];
    var panel = document.getElementById(occ.paragraph_id);
    if (!panel) return;
    revealChapter(panel);
    var chip = paragraphChips[panel.id];
    if (chip) toggleParagraph(chip, true, true);
    refreshParagraphMotifMarks();
    renderMotifBar();
    var targetMark = panel.querySelector("mark.motif-hit-current") || panel.querySelector("mark.motif-hit") || panel;
    scrollAndFlash(targetMark, { block: "center" });
  }

  function stepMotifOccurrence(dir) {
    if (!activeMotif || !activeMotif.occurrences.length) return;
    jumpToMotifOccurrence(activeMotif.index + dir);
  }

  function verifiedMotifOccurrences(occurrences) {
    var offsetCache = Object.create(null), verified = [];
    occurrences.forEach(function (occ, sourceIndex) {
      if (!occ || !Number.isSafeInteger(occ.start) || !Number.isSafeInteger(occ.end) ||
          !Number.isSafeInteger(occ.start_line) || typeof occ.quote !== "string") return;
      var pid = occ.paragraph_id, content = paragraphContent[pid], panel = document.getElementById(pid);
      if (!content || typeof content[0] !== "string" || !panel || !chapters.contains(panel) ||
          Number(panel.dataset.start) !== occ.start_line) return;
      var start = occ.start, end = occ.end;
      if (occ.offset_unit === "unicode_codepoint") {
        var offsets = offsetCache[pid] || (offsetCache[pid] = C.cpOffsets(content[0]));
        start = offsets[start]; end = offsets[end];
      } else if (occ.offset_unit !== "utf16") return;
      if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 0 || start >= end ||
          end > content[0].length || content[0].slice(start, end) !== occ.quote) return;
      verified.push(Object.assign({}, occ, {startU16:start, endU16:end, sourceIndex:sourceIndex}));
    });
    return verified;
  }

  function selectMotifSequence(group, labelText, occurrences, jumpIndex, origin) {
    if (!occurrences.length) return;
    clearCraftJump();
    activeMotif = {
      group: group,
      label: labelText,
      occurrences: occurrences,
      index: jumpIndex,
      origin: origin,
    };
    document.querySelectorAll("[data-motif-select]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", String(btn.closest("[data-motif-group]").dataset.motifGroup === group));
    });
    jumpToMotifOccurrence(jumpIndex);
    // The match remains visible while Tab advances from Previous to Next.
    motifBar.querySelector("button").focus({preventScroll:true});
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-motif-select], [data-motif-jump]");
    var group = button && button.closest("[data-motif-group]");
    if (!group || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    var key = group.dataset.motifGroup, selecting = button.hasAttribute("data-motif-select");
    if (selecting && activeMotif && activeMotif.group === key) {
      clearMotifSelection();
      return;
    }
    var occurrences;
    try { occurrences = JSON.parse(group.dataset.motifOccurrences || "[]"); }
    catch (_) { occurrences = []; }
    if (!Array.isArray(occurrences)) occurrences = [];
    var verified = verifiedMotifOccurrences(occurrences);
    var index = selecting ? 0 : verified.findIndex(function (occurrence) {
      return occurrence.sourceIndex === Number(button.dataset.occurrenceIndex);
    });
    var status = group.querySelector("[data-motif-status]");
    if (status) C.setStatus(status, verified.length < occurrences.length ? L("mot_locations_stale") : "", "");
    if (index >= 0) selectMotifSequence(key, group.dataset.motifLabel || "", verified, index, button);
  });

  var customForm = document.getElementById("motif-custom-search");
  if (customForm && API) {
    var customInput = document.getElementById("motif-pattern-input");
    var customRegex = document.getElementById("motif-pattern-regex");
    var customSubmit = document.getElementById("motif-pattern-submit");
    var customClear = document.getElementById("motif-pattern-clear");
    var customStatus = document.getElementById("motif-pattern-status");
    var customResults = document.getElementById("motif-custom-results");
    var locationLimit = Number(customForm.dataset.locationLimit);
    var previewLimit = Number(customForm.dataset.previewLimit);
    var savedCustomPatterns = [];
    var searchSerial = 0;

    function renderCustomResults() {
      customResults.replaceChildren();
      if (customClear) customClear.hidden = savedCustomPatterns.length === 0 && !activeMotif;
      savedCustomPatterns.forEach(function (entry) {
        var markBtn = el("button", {
          type: "button",
          className: "ctl ctl-sm motif-select-btn",
          text: L("mot_highlight_all"),
          dataset: {motifSelect: "1"},
          attrs: { "aria-pressed": String(Boolean(activeMotif && activeMotif.group === entry.key)) }
        });
        var groupChildren = [
          el("summary", null, entry.label + " (" + entry.total + ")"),
          el("p", {className: "ctl-status", dataset: {motifStatus: ""}, attrs: {role: "status"}})
        ];
        if (entry.partial) groupChildren.push(el("p", "ctl-note", L("mot_locations_stale")));
        if (entry.total > entry.occurrences.length && !entry.partial) {
          groupChildren.push(el("p", "ctl-note", uiFormat("mot_locations_limit", {
            shown: entry.occurrences.length, mapped: entry.total
          })));
        }
        if (entry.occurrences.length) {
          if (entry.occurrences.length > previewLimit) {
            groupChildren.push(el("p", "ctl-note", uiFormat("mot_locations_preview", {preview: previewLimit})));
          }
          groupChildren.push(el("div", "motif-occurrence-actions", markBtn));
          var listItems = entry.occurrences.slice(0, previewLimit).map(function (occ, idx) {
            var locText = (occ.chapter ? L("chapter") + " " + occ.chapter + " · " : "") + L("line") + " " + occ.start_line;
            var qBadge = occ.quotation_context
              ? el("span", "badge badge-neutral", L("evidence_quote_" + occ.quotation_context))
              : null;
            var jBtn = el("button", {
              type: "button",
              className: "ctl ctl-sm motif-jump-btn",
              text: L("mot_open_occurrence"),
              dataset: {
                motifJump: "1",
                occurrenceIndex: String(idx)
              }
            });
            return el("li", null,
              el("span", "ctl-note", locText),
              qBadge ? " " : null,
              qBadge,
              " ",
              el("span", "motif-occ-excerpt", occ.excerpt),
              " ",
              jBtn
            );
          });
          groupChildren.push(el("ul", "motif-occurrence-list", listItems));
        }
        var group = el("details", {
          className: "panel-disclosure motif-occurrence-group motif-custom-group",
          attrs: { open: "" },
          dataset: { motifGroup: entry.key, motifLabel: entry.label, motifOccurrences: JSON.stringify(entry.occurrences) }
        }, groupChildren);
        customResults.append(group);
      });
    }

    customForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      var raw = customInput ? customInput.value.trim() : "";
      if (!raw) {
        C.setStatus(customStatus, "", "");
        return;
      }
      var asRegex = Boolean(customRegex && customRegex.checked);
      var reqId = ++searchSerial;
      if (customSubmit) customSubmit.disabled = true;
      C.setStatus(customStatus, L("research_loading"), "loading");
      var token = document.body.dataset.manuscriptProjectToken || "";
      var payload = { query: raw, regex: asRegex, limit: locationLimit };
      if (/^[a-f0-9]{64}$/.test(token)) payload.project_token = token;
      var result = await C.postJson(API + "/motif-search", payload);
      if (reqId !== searchSerial) return;
      if (customSubmit) customSubmit.disabled = false;
      if (!result.ok) {
        var message = result.code === "invalid-regex" ? L("mot_custom_invalid")
          : result.code === "stale-context" ? L("mot_locations_stale")
          : result.message || L("research_search_failed");
        C.setStatus(customStatus, message, "err");
        return;
      }
      var source = document.body.dataset.manuscriptSourceSha256;
      if (source && result.source_sha256 !== source) {
        C.setStatus(customStatus, L("mot_locations_stale"), "err");
        return;
      }
      var hits = Array.isArray(result.occurrences) ? result.occurrences : [];
      var verified = verifiedMotifOccurrences(hits);
      var key = "custom:" + Number(asRegex) + ":" + raw;
      var total = Number.isSafeInteger(result.total_matches) ? result.total_matches : hits.length;
      savedCustomPatterns = savedCustomPatterns.filter(function (p) { return p.key !== key; });
      savedCustomPatterns.unshift({ key: key, label: raw, occurrences: verified, total: total, partial: verified.length < hits.length });
      C.setStatus(
        customStatus,
        verified.length ? uiCountFormat("mot_custom_matches", verified.length) : total ? L("mot_locations_stale") : L("mot_custom_none"),
        ""
      );
      if (customForm.getClientRects().length) {
        if (verified.length) selectMotifSequence(key, raw, verified, 0, customInput);
        else clearMotifSelection();
      }
      renderCustomResults();
    });

    if (customClear) {
      customClear.addEventListener("click", function () {
        ++searchSerial;
        if (customInput) customInput.value = "";
        if (customSubmit) customSubmit.disabled = false;
        C.setStatus(customStatus, "", "");
        savedCustomPatterns = [];
        clearMotifSelection();
        if (customInput) customInput.focus();
        renderCustomResults();
      });
    }
  }
})();
