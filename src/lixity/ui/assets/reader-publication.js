// Explicit reading progress belongs to this exported publication, not its author project.
(function () {
  "use strict";
  var root = document.getElementById("reader-publication");
  if (!root) return;
  var publication = window.LixitySite.publication;
  if (!publication || publication.schema_version !== "lixity-reader-publication/1" || !Array.isArray(publication.entries)) return;
  var cap = publication.max_chapter;
  if (!Number.isInteger(cap) || cap < 0) return;
  var progress = root.querySelector("#publication-progress");
  var previewProgress = root.querySelector("#publication-preview-progress");
  var previewForm = root.querySelector("#publication-preview-form");
  var previewOpen = root.querySelector("#publication-preview-open");
  var status = root.querySelector("#publication-progress-status");
  var entries = root.querySelector("#publication-entries");
  var contents = root.querySelector("#publication-contents");
  var search = root.querySelector("#publication-context-search");
  var storageKey = "lixity_publication_progress:" + publication.profile + ":" + publication.identity + ":" + publication.source_sha256 + ":" + cap;
  var saved = 0, preview = null, storageFailed = false;
  try {
    var stored = JSON.parse(localStorage.getItem(storageKey));
    if (typeof stored === "number" && Number.isInteger(stored) && stored >= 0 && stored <= cap) saved = stored;
  } catch (_) { /* Missing, corrupt and unavailable storage start before chapter one. */ }
  progress.value = String(saved);
  function selected(control) {
    var value = Number(control.value);
    return Number.isInteger(value) && value >= 0 && value <= cap &&
      Array.from(control.options).some(function(option) { return !option.disabled && option.value === control.value; }) ? value : null;
  }
  function chapter(value) {
    return value === 0 ? uiLabel("publication_before") : uiFormat("publication_chapter", {number:value});
  }
  function announce() {
    status.textContent = (preview === null ? uiFormat("publication_status", {chapter:chapter(saved)}) :
      uiFormat("publication_preview_status", {chapter:chapter(preview)})) +
      (storageFailed ? " " + uiLabel("publication_storage") : "");
  }
  function sourceLink(citation) {
    if (!citation.source_id || !citation.source_version_id) return "";
    var href = window.LixitySite.resourceUrl("/api/site-resource?" + new URLSearchParams({
      source_id:citation.source_id, version_id:citation.source_version_id}));
    return href ? '<p><a href="' + escapeHtml(href) + '" download>' + escapeHtml(uiLabel("site_source_original")) + '</a></p>' : '';
  }
  function render() {
    // Detaching a revealed card must never leave keyboard focus on the body.
    if (entries.contains(document.activeElement)) progress.focus({preventScroll:true});
    var through = preview === null ? saved : preview;
    var query = search.value.trim().toLocaleLowerCase();
    var available = publication.entries.filter(function(entry) {
      return entry.reveal_after_chapter <= through && (!query ||
        (entry.title + "\n" + entry.body).toLocaleLowerCase().includes(query));
    });
    contents.replaceChildren(); entries.replaceChildren();
    var list = document.createElement("ul");
    available.forEach(function(entry) {
      var id = "publication-" + entry.id;
      var link = document.createElement("a"), item = document.createElement("li");
      link.href = "#" + id; link.textContent = entry.title;
      item.appendChild(link); list.appendChild(item);
      var article = document.createElement("article"), heading = document.createElement("h3");
      article.id = id; heading.textContent = entry.title; heading.tabIndex = -1;
      var body = document.createElement("div"); body.className = "research-prose markdown-body";
      var context = {project_id:publication.project_id, images:entry.images || []};
      body.innerHTML = renderSafeMarkdown(entry.body, context) +
        (entry.citations || []).map(function(citation) { return researchCitationHtml(citation, false) + sourceLink(citation); }).join("") +
        (entry.geography && window.LixityDossierGeography ? window.LixityDossierGeography.html(entry.geography) : "");
      article.append(heading, body); entries.appendChild(article);
      link.addEventListener("click", function(event) {
        event.preventDefault(); heading.focus({preventScroll:true}); scrollAndFlash(article);
      });
    });
    if (available.length) contents.appendChild(list);
    else {
      var empty = document.createElement("p"); empty.className = "ctl-note";
      empty.textContent = query ? uiFormat("research_no_hits", {query:search.value.trim()}) : uiLabel("publication_empty"); entries.appendChild(empty);
    }
    root.querySelector("#publication-context-count").textContent = uiCountFormat("publication_available", available.length);
    announce();
  }
  function save(value) {
    saved = value; preview = null; progress.value = String(saved);
    previewForm.hidden = true; previewOpen.setAttribute("aria-expanded", "false");
    try { localStorage.setItem(storageKey, JSON.stringify(saved)); storageFailed = false; }
    catch (_) { storageFailed = true; }
    render();
  }
  root.querySelector("#publication-progress-form").addEventListener("submit", function(event) {
    event.preventDefault(); var value = selected(progress); if (value !== null) save(value);
  });
  root.querySelector("#publication-progress-reset").addEventListener("click", function() { save(0); });
  previewOpen.addEventListener("click", function() {
    previewForm.hidden = false; previewOpen.setAttribute("aria-expanded", "true");
    previewProgress.value = String(saved); previewProgress.focus();
  });
  previewForm.addEventListener("submit", function(event) {
    event.preventDefault(); var value = selected(previewProgress);
    if (value !== null) { preview = value; render(); }
  });
  root.querySelector("#publication-preview-close").addEventListener("click", function() {
    preview = null; previewForm.hidden = true; previewOpen.setAttribute("aria-expanded", "false");
    previewOpen.focus(); render();
  });
  search.addEventListener("input", render);
  var chapterChoice = root.querySelector("#publication-reader-chapter");
  if (chapterChoice) chapterChoice.addEventListener("change", function() {
    var target = document.getElementById(chapterChoice.value);
    if (target && root.contains(target)) scrollAndFlash(target);
  });
  var introduction = root.querySelector(".publication-introduction");
  if (introduction) introduction.innerHTML = renderSafeMarkdown(publication.introduction || "");
  render();
})();
