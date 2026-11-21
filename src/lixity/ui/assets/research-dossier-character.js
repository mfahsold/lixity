// Read the manuscript-derived character evidence of a current native dossier.
(function() {
  "use strict";

  function researchDossierCharacterUpdateHtml(detail) {
    if (detail.character_analysis_available !== true || detail.availability || !researchContextToken() ||
        !detail.id || !Number.isInteger(detail.revision) || detail.revision < 1) return "";
    return '<div class="research-record-actions"><button type="button" class="ctl ctl-sm" data-update-character-dossier' +
      ' data-record-id="' + escapeHtml(detail.id) + '">' +
      escapeHtml(uiLabel("research_dossier_draft_stage_existing")) + '</button>' +
      '<p class="ctl-note" data-character-update-status role="status" hidden></p></div>';
  }

  function researchDossierCharacterHtml() {
    function label(key) { return escapeHtml(uiLabel("research_dossier_character_" + key)); }
    return '<details class="research-dossier-character" data-dossier-character><summary><h4>' + label("heading") + '</h4></summary>' +
      '<div class="research-character-body" data-character-content hidden>' +
        '<div data-character-overview></div>' +
        '<h5>' + label("distribution") + '</h5>' +
        '<div class="table-wrap" data-character-distribution role="region" tabindex="0" aria-label="' + label("distribution") + '"></div>' +
        '<h5>' + label("passages") + '</h5>' +
        '<p class="ctl-note">' + label("context_hint") + '</p>' +
        '<label class="research-character-filter"><span>' + escapeHtml(uiLabel("research_chapter")) + '</span>' +
          '<select class="ctl" data-character-chapter></select></label>' +
        '<div data-character-passages></div>' +
      '</div>' +
      '<p class="ctl-note" data-character-status role="status"></p>' +
      '<button class="ctl" type="button" data-character-more hidden>' + label("more") + '</button>' +
      '<button class="ctl" type="button" data-character-reload hidden>' + label("reload") + '</button></details>';
  }

  function mountResearchDossierCharacter(host, detail, reading) {
    var panel = host.querySelector("[data-dossier-character]");
    if (!panel) return;
    panel._characterCurrent = reading.current;
    if (panel._characterMounted) return;
    panel._characterMounted = true;
    var content = panel.querySelector("[data-character-content]");
    var overview = panel.querySelector("[data-character-overview]");
    var distribution = panel.querySelector("[data-character-distribution]");
    var filter = panel.querySelector("[data-character-chapter]");
    var passages = panel.querySelector("[data-character-passages]");
    var status = panel.querySelector("[data-character-status]");
    var more = panel.querySelector("[data-character-more]");
    var reload = panel.querySelector("[data-character-reload]");
    var locale = document.documentElement.lang || undefined;
    var format = new Intl.NumberFormat(locale, {maximumFractionDigits: 1});
    var percent = new Intl.NumberFormat(locale, {style: "percent", maximumFractionDigits: 1});
    var digest = null, nextOffset = null, started = false, busy = false, activeChapter = "", serial = 0;
    function key(suffix) { return "research_dossier_character_" + suffix; }
    function textLabel(suffix) { return escapeHtml(uiLabel(key(suffix))); }
    function chapterLabel(chapter) {
      var number = uiFormat("publication_chapter", {number: format.format(chapter.chapter)});
      var title = chapter.chapter_title;
      return title && title.toLocaleLowerCase(locale) !== number.toLocaleLowerCase(locale) ? number + " · " + title : number;
    }
    function renderOverview(data) {
      var summary = uiCountFormat(key("summary"), data.mentions, {
        name: data.character, mentions: format.format(data.mentions),
        covered: format.format(data.chapters_with_mentions), chapters: format.format(data.chapters.length)
      });
      function fact(suffix, value) { return '<div><dt>' + textLabel(suffix) + '</dt><dd>' + escapeHtml(value) + '</dd></div>'; }
      var facts = [];
      if (Array.isArray(data.aliases) && data.aliases.length) facts.push(fact("aliases", data.aliases.join(", ")));
      if (data.longest_gap > 0) facts.push(fact("gap", format.format(data.longest_gap)));
      if (Array.isArray(data.declared_pov_chapters) && data.declared_pov_chapters.length) {
        facts.push(fact("pov", data.declared_pov_chapters.map(function(chapter) { return format.format(chapter); }).join(", ")));
      }
      var voice = data.dialogue, dialogue = "";
      if (voice && voice.turns > 0) {
        var voiceFacts = fact("turns", format.format(voice.turns));
        if (Number.isFinite(voice.mean_sentence_words)) voiceFacts += fact("sentence_words", format.format(voice.mean_sentence_words));
        if (Number.isFinite(voice.question_excl_pct)) voiceFacts += fact("questions", percent.format(voice.question_excl_pct / 100));
        dialogue = '<h5>' + textLabel("dialogue") + '</h5><dl>' + voiceFacts + '</dl>' +
          (voice.status === "insufficient_turns" ? '<p class="ctl-note">' +
            escapeHtml(uiFormat(key("dialogue_sample"), {minimum: format.format(voice.min_turns)})) + '</p>' : "");
      }
      overview.innerHTML = '<p><strong>' + escapeHtml(summary) + '</strong></p><p class="ctl-note">' + textLabel("scope") + '</p>' +
        (facts.length ? '<dl>' + facts.join("") + '</dl>' : "") + dialogue;
    }
    function renderDistribution(chapters) {
      distribution.innerHTML = '<table><thead><tr><th scope="col">' + escapeHtml(uiLabel("research_chapter")) +
        '</th><th scope="col" class="num">' + textLabel("mentions") + '</th></tr></thead><tbody>' +
        chapters.map(function(chapter) {
          return '<tr><th scope="row">' + escapeHtml(chapterLabel(chapter)) + '</th><td class="num">' +
            escapeHtml(format.format(chapter.mentions)) + '</td></tr>';
        }).join("") + '</tbody></table>';
      filter.replaceChildren(new Option(uiLabel("analysis_scope_all"), ""));
      chapters.forEach(function(chapter) {
        filter.add(new Option(chapterLabel(chapter), String(chapter.chapter)));
      });
      filter.value = activeChapter;
    }
    function excerptText(passage) {
      var points = Array.from(passage.text), cursor = 0, html = "";
      for (var match of passage.matches || []) {
        if (!Number.isInteger(match.start) || !Number.isInteger(match.end) ||
            match.start < cursor || match.end < match.start || match.end > points.length) return escapeHtml(passage.text);
        if (match.end === match.start) continue;
        html += escapeHtml(points.slice(cursor, match.start).join("")) +
          '<mark>' + escapeHtml(points.slice(match.start, match.end).join("")) + '</mark>';
        cursor = match.end;
      }
      return html + escapeHtml(points.slice(cursor).join(""));
    }
    function contextText(text, side) {
      if (typeof text !== "string" || !text) return "";
      return '<div class="research-character-context" data-character-context="' + side + '">' +
        '<p class="research-character-context-caption">' + textLabel("context_" + side) + '</p>' +
        '<p>' + escapeHtml(text) + '</p></div>';
    }
    function renderPassages(items, append, lineScope) {
      if (!append) passages.replaceChildren();
      var group = passages.lastElementChild, first = null;
      items.forEach(function(passage) {
        if (!group || group.dataset.characterPassageChapter !== String(passage.chapter)) {
          group = document.createElement("section");
          group.dataset.characterPassageChapter = String(passage.chapter);
          var heading = document.createElement("h6");
          heading.textContent = chapterLabel(passage);
          group.appendChild(heading);
          passages.appendChild(group);
        }
        var figure = document.createElement("figure");
        figure.dataset.characterPassage = "";
        var values = {start: format.format(passage.start_line), end: format.format(passage.end_line)};
        var lines = lineScope === "chapter_body" ? uiCountFormat(key("lines"), passage.end_line - passage.start_line + 1, values) :
          lineScope === "manuscript" ? uiFormat("reading_passage_lines", values) : "";
        figure.innerHTML = (lines ? '<figcaption class="ctl-note">' + escapeHtml(lines) + '</figcaption>' : "") +
          contextText(passage.context_before, "before") + '<blockquote>' + excerptText(passage) + '</blockquote>' +
          contextText(passage.context_after, "after");
        group.appendChild(figure);
        if (!first) first = figure;
      });
      return first;
    }
    async function load(offset, refresh) {
      if (!panel.isConnected || !panel._characterCurrent()) return;
      busy = started = true;
      var request = ++serial;
      var chapter = activeChapter;
      var expected = refresh ? null : digest;
      var query = new URLSearchParams({id: detail.id, offset: String(offset)});
      if (chapter) query.set("chapter", chapter);
      if (expected) query.set("analysis_sha256", expected);
      var trigger = document.activeElement;
      status.textContent = uiLabel(key("loading"));
      if (!offset) passages.hidden = true;
      passages.setAttribute("aria-busy", "true");
      more.setAttribute("aria-disabled", "true");
      reload.setAttribute("aria-disabled", "true");
      var data = await researchApiGet("research/dossier-character?" + query);
      if (request !== serial) return;
      busy = false;
      if (!panel.isConnected || !panel._characterCurrent()) return;
      passages.removeAttribute("aria-busy");
      more.removeAttribute("aria-disabled");
      reload.removeAttribute("aria-disabled");
      if (!data.ok || data.schema_version !== "dossier-character-local/1" || data.project_id !== detail.project_id ||
          data.offset !== offset || !Array.isArray(data.chapters) || !Array.isArray(data.passages) ||
          !/^[a-f0-9]{64}$/.test(data.analysis_sha256) || expected && data.analysis_sha256 !== expected) {
        digest = nextOffset = null;
        activeChapter = "";
        content.hidden = more.hidden = true;
        reload.hidden = false;
        status.textContent = uiLabel(key(data.http_status === 409 || data.ok && expected && data.analysis_sha256 !== expected ? "changed" : "unavailable"));
        if (panel.contains(trigger) && (document.activeElement === trigger || document.activeElement === document.body)) reload.focus();
        return;
      }
      if (!expected) {
        renderOverview(data);
        renderDistribution(data.chapters);
      }
      digest = data.analysis_sha256;
      nextOffset = Number.isInteger(data.next_offset) && data.next_offset > offset ? data.next_offset : null;
      var first = renderPassages(data.passages, offset > 0, data.line_scope);
      passages.hidden = false;
      content.hidden = false;
      more.hidden = nextOffset === null;
      reload.hidden = true;
      status.textContent = data.passage_count ? uiFormat(key("loaded"), {
        loaded: format.format(offset + data.passages.length), total: format.format(data.passage_count)
      }) : uiLabel(key("empty"));
      if (trigger === more && (document.activeElement === trigger || document.activeElement === document.body) && first) {
        first.tabIndex = -1;
        first.focus({preventScroll: true});
        setPassageScrollMargin(first);
        window.LixityComponents.scrollIntoViewSafe(first);
      } else if (trigger === reload && (document.activeElement === trigger || document.activeElement === document.body)) {
        panel.querySelector("summary").focus();
      }
    }
    panel.addEventListener("toggle", function() { if (panel.open && !started) load(0, false); });
    filter.addEventListener("change", function() {
      activeChapter = filter.value;
      load(0, false);
    });
    more.addEventListener("click", function() { if (!busy && nextOffset !== null) load(nextOffset, false); });
    reload.addEventListener("click", function() { if (!busy) load(0, true); });
    if (panel.open) load(0, false);
  }

  window.LixityDossierCharacter = {
    html: researchDossierCharacterHtml, mount: mountResearchDossierCharacter, updateHtml: researchDossierCharacterUpdateHtml
  };
})();
