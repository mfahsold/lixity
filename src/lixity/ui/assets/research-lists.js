// Research workspace: list filtering, sources, dossiers, timeline, claims, decisions.
// Split of the former research.js; _JS_FILES concatenates the parts in
// the original order, so load-time behaviour is unchanged.
var RESEARCH_LIST_PAGE_SIZE = 40;
var researchWindowState = {
  sources: {items: [], limit: RESEARCH_LIST_PAGE_SIZE},
  claims: {items: [], limit: RESEARCH_LIST_PAGE_SIZE, filter: "all"},
  decisions: {items: [], limit: RESEARCH_LIST_PAGE_SIZE, filter: "all"}
};

function renderWindowedResearchList(kind, listHost, items, emptyMessage) {
  var moreHost = document.getElementById("research-" + kind + "-more");
  if (!items.length) {
    if (emptyMessage) LixityResearchCards.render(listHost, {message: emptyMessage});
    else LixityResearchCards.render(listHost, {items: []});
    if (moreHost) {
      moreHost.hidden = true;
      moreHost.replaceChildren();
    }
    return;
  }
  var state = researchWindowState[kind] || {limit: RESEARCH_LIST_PAGE_SIZE};
  var limit = state.limit || RESEARCH_LIST_PAGE_SIZE;
  var visible = items.slice(0, limit);
  var remaining = items.length - visible.length;
  LixityResearchCards.render(listHost, {items: visible});
  if (moreHost) {
    if (remaining > 0) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ctl ctl-sm";
      btn.dataset.researchShowMore = kind;
      btn.textContent = (uiLabel("research_show_more") || "Show more") + " (+" + remaining + ")";
      moreHost.replaceChildren(btn);
      moreHost.hidden = false;
    } else {
      moreHost.hidden = true;
      moreHost.replaceChildren();
    }
  }
}

function syncResearchTagCloud(kind, query) {
  var host = document.getElementById("r-filter-" + kind + "-tags");
  if (!host) return;
  var active = String(query || "").trim().toLowerCase();
  host.querySelectorAll("[data-cloud-tag]").forEach(function(btn) {
    var match = Boolean(active) && btn.dataset.cloudTag.toLowerCase() === active;
    btn.classList.toggle("active", match);
    btn.setAttribute("aria-pressed", String(match));
  });
}

function syncResearchFilterTags(kind, query) {
  var list = document.getElementById("research-" + kind + "-list");
  if (!list) return;
  var active = String(query || "").trim().toLowerCase();
  list.querySelectorAll("[data-filter-tag]").forEach(function(btn) {
    var match = Boolean(active) && String(btn.dataset.filterTag || "").trim().toLowerCase() === active;
    btn.classList.toggle("active", match);
    btn.setAttribute("aria-pressed", String(match));
  });
}

function renderResearchTagCloud(kind, records) {
  var host = document.getElementById("r-filter-" + kind + "-tags");
  if (!host) return;
  var counts = Object.create(null);
  (records || []).forEach(function(item) {
    (item.tags || []).forEach(function(raw) {
      var tag = String(raw || "").trim();
      if (tag) counts[tag] = (counts[tag] || 0) + 1;
    });
  });
  var tags = Object.keys(counts).sort(function(a, b) {
    return counts[b] - counts[a] || a.localeCompare(b);
  }).slice(0, 20);
  if (!tags.length) {
    host.hidden = true;
    host.replaceChildren();
    return;
  }
  var frag = document.createDocumentFragment();
  tags.forEach(function(tag) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "research-tag";
    btn.dataset.cloudKind = kind;
    btn.dataset.cloudTag = tag;
    btn.setAttribute("aria-pressed", "false");
    btn.textContent = tag + " (" + counts[tag] + ")";
    frag.appendChild(btn);
  });
  host.replaceChildren(frag);
  host.hidden = false;
  var input = document.getElementById("r-filter-" + kind);
  syncResearchTagCloud(kind, input ? input.value : "");
}

function filterResearchList(kind) {
  var input = document.getElementById("r-filter-" + kind);
  var list = document.getElementById("research-" + kind + "-list");
  var status = document.getElementById("r-filter-" + kind + "-status");
  if (!input || !list || !status) return;
  var query = input.value.trim();
  var normalized = query.toLowerCase();
  var state = researchListRefreshes[kind];
  // Keep a query and its focus available when the last record disappears.
  input.hidden = Boolean(state && state.count === 0 && !normalized && document.activeElement !== input);
  syncResearchTagCloud(kind, query);
  if (kind === "sources" && researchWindowState.sources.items.length) {
    var allItems = researchWindowState.sources.items;
    var limit = researchWindowState.sources.limit || RESEARCH_LIST_PAGE_SIZE;
    if (allItems.length <= limit) {
      // All items fit in the current window: ensure all are rendered once and
      // filter in-place via `card.hidden` so open details/DOM state survive.
      if (list.querySelectorAll(".research-card").length !== allItems.length) {
        renderWindowedResearchList("sources", list, allItems, null);
      }
      var domCards = list.querySelectorAll(".research-card[data-filter-text]");
      var domMatches = 0;
      domCards.forEach(function(card) {
        card.hidden = Boolean(normalized) && !card.dataset.filterText.includes(normalized);
        if (!card.hidden) domMatches++;
      });
      status.hidden = !normalized || !domCards.length || domMatches > 0;
      status.textContent = status.hidden ? "" : uiFormat("research_no_hits", {query: query});
      syncResearchFilterTags(kind, query);
      return;
    }
    var matched = normalized
      ? allItems.filter(function(item) { return item.filterText && item.filterText.includes(normalized); })
      : allItems;
    renderWindowedResearchList("sources", list, matched, null);
    list.querySelectorAll(".research-card[data-filter-text]").forEach(function(card) {
      card.hidden = false;
    });
    status.hidden = !normalized || !allItems.length || matched.length > 0;
    status.textContent = status.hidden ? "" : uiFormat("research_no_hits", {query: query});
    syncResearchFilterTags(kind, query);
    return;
  }
  var cards = list.querySelectorAll(".research-card[data-filter-text]");
  var matches = 0;
  cards.forEach(function(card) {
    card.hidden = Boolean(normalized) && !card.dataset.filterText.includes(normalized);
    if (!card.hidden) matches++;
  });
  status.hidden = !normalized || !cards.length || matches > 0;
  status.textContent = status.hidden ? "" : uiFormat("research_no_hits", {query: query});
  syncResearchFilterTags(kind, query);
}

document.addEventListener("input", function(event) {
  if (event.target.id === "r-filter-sources") {
    researchWindowState.sources.limit = RESEARCH_LIST_PAGE_SIZE;
    filterResearchList("sources");
  }
  if (event.target.id === "r-filter-dossiers") filterResearchList("dossiers");
});

document.addEventListener("focusout", function(event) {
  if (event.target.id === "r-filter-sources") filterResearchList("sources");
  if (event.target.id === "r-filter-dossiers") filterResearchList("dossiers");
});

document.addEventListener("click", function(event) {
  var showMore = event.target.closest("[data-research-show-more]");
  if (showMore) {
    var moreKind = showMore.dataset.researchShowMore;
    if (researchWindowState[moreKind]) {
      researchWindowState[moreKind].limit += RESEARCH_LIST_PAGE_SIZE;
      if (moreKind === "sources") filterResearchList("sources");
      else if (moreKind === "claims") renderResearchClaimCards();
      else if (moreKind === "decisions") renderResearchDecisionCards();
    }
    return;
  }
  var cloudTag = event.target.closest("[data-cloud-tag]");
  if (cloudTag) {
    var cloudKind = cloudTag.dataset.cloudKind;
    var cloudInput = document.getElementById("r-filter-" + cloudKind);
    if (cloudInput) {
      var tagVal = cloudTag.dataset.cloudTag;
      cloudInput.value = cloudInput.value.trim().toLowerCase() === tagVal.toLowerCase() ? "" : tagVal;
      if (researchWindowState[cloudKind]) researchWindowState[cloudKind].limit = RESEARCH_LIST_PAGE_SIZE;
      filterResearchList(cloudKind);
    }
    return;
  }
  var filterTag = event.target.closest("[data-filter-tag]");
  if (filterTag) {
    var list = filterTag.closest("#research-sources-list, #research-dossiers-list");
    var kind = list && list.id === "research-dossiers-list" ? "dossiers" : "sources";
    var input = document.getElementById("r-filter-" + kind);
    if (input) {
      input.value = filterTag.dataset.filterTag;
      if (researchWindowState[kind]) researchWindowState[kind].limit = RESEARCH_LIST_PAGE_SIZE;
      filterResearchList(kind);
    }
    return;
  }
  var zoteroTag = event.target.closest("[data-zotero-tag]");
  if (zoteroTag) {
    var query = document.getElementById("r-zotero-query");
    var browse = document.getElementById("r-zotero-browse");
    if (query && browse) {
      query.value = zoteroTag.dataset.zoteroTag;
      browse.click();
    }
  }
});

// Coalesce ordinary in-flight reads only; post-write refreshes supersede older reads.
var researchListRefreshes = {};
function researchListRead(kind, overview, changedId, freshRead) {
  var state = researchListRefreshes[kind];
  // An earlier root/project observation cannot own this context's first read.
  if (!state || !acceptResearchContext(state.context, {})) {
    state = researchListRefreshes[kind] = {sequence: 0, pending: null, context: researchReadContext()};
  }
  if (overview && Array.isArray(overview[kind])) {
    // Startup's shared overview must not replace a newer tab/post-write request.
    return Promise.resolve(state.sequence && !freshRead ? null : {state: state, sequence: ++state.sequence, data: overview});
  }
  if (state.pending && !changedId && !freshRead) return state.pending;
  var sequence = ++state.sequence;
  var pending = researchApiGet("research/" + kind).then(function(data) {
    return {state: state, sequence: sequence, data: data};
  });
  state.pending = pending;
  pending.then(function() {
    if (state.pending === pending) state.pending = null;
  });
  return pending;
}

function acceptResearchList(kind, reading) {
  var state = researchListRefreshes[kind];
  return Boolean(state && reading && reading.state === state && reading.sequence === state.sequence);
}

async function refreshResearchSources(overview, changedId, freshRead) {
  var sourceListProject = researchSelectionProjectId;
  clearResearchSourceSelections();
  var listHost = document.getElementById("research-sources-list");
  if (!listHost) return;
  if (!listHost.children.length) LixityResearchCards.render(listHost, {loading: true});
  var reading = await researchListRead("sources", overview, changedId, freshRead);
  if (!acceptResearchList("sources", reading)) return;
  var data = reading.data;
  if (sourceListProject !== researchSelectionProjectId && data.project_id &&
      data.project_id !== researchSelectionProjectId) return;
  if (data.ok && data.project_id && data.project_id !== researchSelectionProjectId) {
    clearResearchSourceSelections(); discardResearchEvidenceDraft();
    researchPassageContexts = Object.create(null);
    researchSelectionProjectId = data.project_id;
    ++researchProjectStatusRead;
  }
  if (!data.ok || !Array.isArray(data.sources)) {
    researchWindowState.sources.items = [];
    renderResearchTagCloud("sources", []);
    renderWindowedResearchList("sources", listHost, [], data.message || uiLabel("research_load_sources_failed"));
    filterResearchList("sources");
    return;
  }
  var sources = data.sources;
  reading.state.count = sources.length;
  var external = sources.find(function(s) { return s.context && s.context.external_reference; });
  var libraryInput = document.getElementById("r-zotero-library");
  if (external && libraryInput && !zoteroSelection) libraryInput.value = external.context.external_reference.library;
  if (!sources.length) {
    researchWindowState.sources.items = [];
    renderResearchTagCloud("sources", []);
    renderWindowedResearchList("sources", listHost, [], uiLabel("research_no_sources"));
    filterResearchList("sources");
    return;
  }
  researchWindowState.sources.items = sources.map(function(s) {
    var external = s.context && s.context.external_reference;
    var mediaOrPassages = ["image/png", "image/jpeg", "video/mp4", "video/webm"].includes(s.media_type)
      ? s.media_type
      : uiCountFormat("research_passages_count", s.passages);
    var sizeKb = Math.round((s.byte_length || 0) / 1024) + " KB";
    return {
      key: JSON.stringify(s),
      id: s.id,
      title: s.title,
      metaRight: [{
        text: mediaOrPassages + " · " + sizeKb,
        title: uiLabel("research_tab_sources_help") || "Gespeicherte Quellenkopie"
      }],
      tags: s.tags || [],
      tagsInteractive: true,
      zotero: external ? {library: external.library, key: external.item_key} : null,
      details: "source",
      filterText: [s.title, s.id].concat(s.tags || []).join(" ").toLowerCase(),
    };
  });
  renderResearchTagCloud("sources", sources);
  if (researchWindowState.sources.items.length <= (researchWindowState.sources.limit || RESEARCH_LIST_PAGE_SIZE)) {
    renderWindowedResearchList("sources", listHost, researchWindowState.sources.items, null);
  }
  filterResearchList("sources");
}

var researchDossiersPayload = null, researchDossiersContext = null;
function renderResearchDossiersView(data) {
  var listHost = document.getElementById("research-dossiers-list");
  if (!listHost || !data) return;
  var dossiers = data.dossiers || [];
  var collections = data.collections || data.dossier_collections || [];
  var unassignedIds = data.unassigned_dossier_ids || [];
  var bar = document.getElementById("r-dos-collection-bar");
  var colSelect = document.getElementById("r-dos-collection-select");
  var colNote = document.getElementById("r-dos-collection-note");
  var selectedCol = colSelect ? (colSelect.value || "all") : "all";
  if (bar && colSelect) {
    bar.hidden = !collections.length;
    colSelect.innerHTML = '<option value="all">' + escapeHtml(uiLabel("research_dossier_collection_all")) + '</option>' +
      collections.map(function(col) {
        return '<option value="' + escapeHtml(col.id) + '">' + escapeHtml(col.name) + ' (' + (col.available_count || 0) + ')</option>';
      }).join("") +
      '<option value="unassigned">' + escapeHtml(uiLabel("research_dossier_collection_unassigned")) + ' (' + unassignedIds.length + ')</option>';
    if (selectedCol !== "all" && selectedCol !== "unassigned" && !collections.some(function(c) { return c.id === selectedCol; })) {
      selectedCol = "all";
    }
    colSelect.value = selectedCol;
    Array.from(colSelect.options).forEach(function(option) { option.defaultSelected = option.value === selectedCol; });
  }
  var byId = Object.fromEntries(dossiers.map(function(d) { return [d.id, d]; }));
  var activeCollection = collections.find(function(c) { return c.id === selectedCol; }) || null;
  var visibleDossiers = dossiers;
  if (activeCollection) {
    visibleDossiers = (activeCollection.entries || []).filter(function(entry) { return entry.status === "available"; }).map(function(entry) { return byId[entry.dossier_id]; }).filter(Boolean);
  } else if (selectedCol === "unassigned") {
    var unassignedSet = new Set(unassignedIds);
    visibleDossiers = dossiers.filter(function(d) { return unassignedSet.has(d.id); });
  }
  if (colNote) {
    var unavailableCount = activeCollection ? (activeCollection.unavailable_count || 0) : 0;
    colNote.hidden = !unavailableCount;
    colNote.textContent = unavailableCount ? uiCountFormat("research_dossier_collection_unavailable", unavailableCount) : "";
  }
  if (!dossiers.length) {
    renderResearchTagCloud("dossiers", []);
    LixityResearchCards.render(listHost, {message: uiLabel("research_no_dossiers")});
    filterResearchList("dossiers");
    return;
  }
  renderResearchTagCloud("dossiers", visibleDossiers);
  if (!visibleDossiers.length) {
    LixityResearchCards.render(listHost, {message: uiLabel("research_dossier_collection_empty")});
    filterResearchList("dossiers");
    return;
  }
  LixityResearchCards.render(listHost, {items: visibleDossiers.map(function(d) {
    var badges = d.review_needed
      ? [{label: uiLabel("research_review_needed"), cls: "badge-warning ml-2", title: uiLabel("research_review_needed_hint")}]
      : [];
    var metaRight = [{
      text: uiCountFormat("research_evidence_count", d.evidence_count),
      title: uiLabel("research_dossier_evidence_help")
    }];
    if (d.revision) {
      metaRight.push({
        text: uiFormat("research_revision_number", { revision: d.revision }),
        title: uiLabel("research_dossier_revision_help")
      });
    }
    if (Array.isArray(d.collections) && d.collections.length) {
      metaRight.push({
        text: d.collections.map(function(m) { return m.name + " #" + m.position; }).join(", "),
        title: uiLabel("research_dossier_collection_membership_help")
      });
    }
    return {
      key: JSON.stringify(d),
      id: d.id,
      title: d.title,
      badges: badges,
      metaRight: metaRight,
      excerpt: d.excerpt,
      sections: d.sections || [],
      tags: d.tags || [],
      tagsInteractive: true,
      details: "dossier",
      reader: Boolean(document.getElementById("workspace-reader")),
      revision: "dossier",
      filterText: [d.title, d.id, d.excerpt].concat(d.tags || [], d.sections || []).join(" ").toLowerCase(),
    };
  })});
  filterResearchList("dossiers");
}

function topResearchTags(items) {
  var counts = Object.create(null);
  (items || []).forEach(function(item) {
    (item.tags || []).forEach(function(raw) {
      var tag = String(raw || "").trim();
      if (tag) counts[tag] = (counts[tag] || 0) + 1;
    });
  });
  return Object.keys(counts).sort(function(a, b) {
    return counts[b] - counts[a] || a.localeCompare(b);
  }).slice(0, 12);
}

async function refreshResearchDossiers(overview, changedId, freshRead) {
  var context = researchReadContext();
  var listHost = document.getElementById("research-dossiers-list");
  if (!listHost) return;
  if (!listHost.children.length) LixityResearchCards.render(listHost, {loading: true});
  var reading = await researchListRead("dossiers", overview, changedId, freshRead);
  if (!acceptResearchList("dossiers", reading) || !acceptResearchContext(context, reading.data)) return;
  var data = reading.data;
  if (!data.ok || !Array.isArray(data.dossiers)) {
    LixityResearchCards.render(listHost, {message: data.message || uiLabel("research_load_dossiers_failed")});
    filterResearchList("dossiers");
    return;
  }
  var dossiers = data.dossiers;
  reading.state.count = dossiers.length;
  researchDossiersPayload = data;
  researchDossiersContext = context;
  ["r-claim-dossier-select", "r-decision-dossier-select"].forEach(function(selectId) {
    var dossierSelect = document.getElementById(selectId);
    if (!dossierSelect) return;
    var selectedDossier = dossierSelect.value;
    dossierSelect.innerHTML = '<option value="">' + escapeHtml(uiLabel("research_no_dossier")) + '</option>' + dossiers.map(function(d) {
      return '<option value="' + escapeHtml(d.id) + '">' + escapeHtml(d.title) + '</option>';
    }).join("");
    if (dossiers.some(function(d) { return d.id === selectedDossier; })) dossierSelect.value = selectedDossier;
  });
  if (window.LixityComponents) {
    var dosTags = topResearchTags(dossiers);
    window.LixityComponents.renderTagSuggestions("r-dos-tag-suggestions", dosTags, uiLabel("research_tag_suggestions"));
    window.LixityComponents.renderTagSuggestions("r-ingest-tag-suggestions", dosTags, uiLabel("research_tag_suggestions"));
    window.LixityComponents.syncEmptySelect("r-dos-eids");
  }
  syncAllSearchableSelects();
  if (typeof refreshResearchCollectionEditor === "function") refreshResearchCollectionEditor(data);
  renderResearchDossiersView(data);
  return data;
}

document.addEventListener("change", function(event) {
  if (event.target.id === "r-dos-collection-select" && researchDossiersPayload) {
    var collections = researchDossiersPayload.collections || researchDossiersPayload.dossier_collections || [];
    var chosen = collections.find(function(c) { return c.id === event.target.value; });
    if (typeof selectResearchCollectionEditor === "function") selectResearchCollectionEditor(event, chosen);
    renderResearchDossiersView(researchDossiersPayload);
  }
});

function researchClaimChoiceLabel(claim) {
  function label(item) {
    return researchRecordLabel(item, "claim") + (item.scope && item.scope.time_period ? " · " + item.scope.time_period : "") +
      " · " + uiFormat("research_revision_number", {revision: item.revision});
  }
  var text = label(claim);
  // Names, dates and versions can all match. Keep the remaining choices
  // explicitly distinguishable without requiring anyone to type an ID.
  var matches = Object.values(researchClaimChoices).filter(function(other) { return label(other) === text; });
  var index = matches.findIndex(function(other) { return other.id === claim.id; });
  return text + (matches.length > 1 && index >= 0 ? " · " + uiFormat("research_choice_number", {number: index + 1}) : "");
}

function updateResearchRelationControls() {
  var save = document.getElementById("r-relation-save");
  if (!save) return;
  var from = document.getElementById("r-relation-from").value;
  var to = document.getElementById("r-relation-to").value;
  save.disabled = researchRelationPending || !researchContextToken() || !researchClaimsSnapshot ||
    !researchClaimChoices[from] || !researchClaimChoices[to] || from === to;
}

function researchTimelineScale(entry) {
  var period = entry.period;
  if (!period) return "";
  function part(iso) {
    if (period.precision === "year") return iso.slice(0, 4);
    if (period.precision === "month") return iso.slice(5, 7) + "/" + iso.slice(0, 4);
    return iso;
  }
  var start = part(period.start), end = part(period.end);
  return start === end ? start : start + " – " + end;
}

function researchTimelineAnchor(claimId) {
  return "research-timeline-" + String(claimId).replace(/[^A-Za-z0-9]+/g, "-");
}

function researchTimelineStrip(rows) {
  if (!rows.length) return "";
  function day(iso) { return Date.parse(iso + "T00:00:00Z") / 86400000; }
  var earliest = rows.reduce(function(best, entry) { return entry.period.start < best ? entry.period.start : best; }, rows[0].period.start);
  var latest = rows.reduce(function(best, entry) { return entry.period.end > best ? entry.period.end : best; }, rows[0].period.end);
  var low = day(earliest), high = day(latest), span = Math.max(high - low, 1);
  var body = rows.map(function(entry) {
    var start = day(entry.period.start), end = day(entry.period.end);
    var left = (start - low) / span * 100;
    var width = Math.max((end - start) / span * 100, 0.8);
    return '<li><a class="research-timeline-strip-row" href="#' + researchTimelineAnchor(entry.claim_id) + '">' +
      '<span class="research-timeline-strip-label"><span class="research-timeline-strip-badge">' +
      escapeHtml(researchTimelineScale(entry)) + '</span>' + escapeHtml(entry.title) + '</span>' +
      '<span class="research-timeline-strip-track"><span class="research-timeline-strip-bar" style="left:' +
      left.toFixed(3) + '%;width:' + width.toFixed(3) + '%"></span></span></a></li>';
  }).join("");
  return '<div class="research-timeline-strip"><h4>' + escapeHtml(uiLabel("research_timeline_strip_heading")) + '</h4>' +
    '<p class="ctl-note">' + escapeHtml(uiCountFormat("research_timeline_span", rows.length,
      {start: earliest.slice(0, 4), end: latest.slice(0, 4)})) + '</p>' +
    '<ol>' + body + '</ol>' +
    '<p class="ctl-note">' + escapeHtml(uiLabel("research_timeline_strip_hint")) + '</p></div>';
}

function researchTimelineEntry(entry) {
  var scale = researchTimelineScale(entry);
  var scope = [entry.place, (entry.actors || []).join(", ")].filter(Boolean).join(" · ");
  var authored = entry.time_period ? uiLabel("research_scope_time") + " " + entry.time_period : "";
  var details = [authored, scope].filter(Boolean).join(" · ");
  return '<li id="' + researchTimelineAnchor(entry.claim_id) + '" data-claim-id="' + escapeHtml(entry.claim_id) +
    '"><article class="research-card">' +
    (scale ? '<p class="research-timeline-scale"><span>' + escapeHtml(scale) + '</span></p>' : '') +
    '<h4>' + escapeHtml(entry.title) + '</h4>' +
    (details ? '<p class="ctl-note">' + escapeHtml(details) + '</p>' : '') +
    '<p class="research-timeline-statement">' + escapeHtml(entry.statement) + '</p>' +
    '<p class="ctl-note">' + escapeHtml(uiLabel("research_confidence_" + entry.confidence)) + ' · ' +
      escapeHtml(uiFormat("research_revision_number", {revision: entry.revision})) + '</p>' +
    (entry.reason ? '<p class="research-timeline-reason">' + escapeHtml(uiLabel("research_timeline_" + entry.reason)) + '</p>' : '') +
    researchRevisionActions("claim", entry.claim_id) + '</article></li>';
}

function researchRelationEndpoint(endpoint) {
  return escapeHtml(endpoint.title || "") + (endpoint.time_period ? " · " + escapeHtml(endpoint.time_period) : "") +
    ' · ' + escapeHtml(uiFormat("research_revision_number", {revision: endpoint.revision})) +
    ' · ' + escapeHtml(uiLabel("research_confidence_" + endpoint.confidence));
}

async function refreshResearchClaimProjections() {
  var request = ++researchProjectionRead;
  var activeResearchTab = document.querySelector('.research-tabs [data-rtab].active');
  if (!activeResearchTab || (activeResearchTab.dataset.rtab !== "claims" && activeResearchTab.dataset.rtab !== "timeline")) return;
  var context = researchReadContext();
  var timelineHost = document.getElementById("research-claims-timeline");
  var relationsHost = document.getElementById("research-claim-relations");
  if (!timelineHost || !relationsHost) return;
  ["from", "to"].forEach(function(role) {
    var select = document.getElementById("r-relation-" + role), previous = select.value;
    select.innerHTML = '<option value="">' + escapeHtml(uiLabel("research_select_claim")) + '</option>' +
      Object.values(researchClaimChoices).map(function(claim) {
        return '<option value="' + escapeHtml(claim.id) + '">' + escapeHtml(researchClaimChoiceLabel(claim)) + '</option>';
      }).join("");
    if (researchClaimChoices[previous]) select.value = previous;
  });
  syncAllSearchableSelects();
  updateResearchRelationControls();
  var include = document.getElementById("r-relation-retracted").checked;
  var responses = await Promise.all([researchApiGet("research/timeline"),
    researchApiGet("research/claim-relations?include_retracted=" + include)]);
  if (request !== researchProjectionRead || !responses.every(function(data) {return acceptResearchContext(context, data);})) return;
  var timeline = responses[0], relations = responses[1];
  var datedRows = timeline.dated || [], unplacedRows = timeline.unplaced || [];
  timelineHost.innerHTML = timeline.ok ?
    '<p class="ctl-note">' + escapeHtml(uiLabel("research_timeline_hint")) + '</p>' +
    '<p class="ctl-note">' + escapeHtml(uiLabel("research_timeline_examples")) +
      ' <code>1912 · 1912-03 · 1912-05-01 · 1912–1914</code></p>' +
    researchTimelineStrip(datedRows) +
    '<h3>' + escapeHtml(uiLabel("research_timeline_dated")) + ' (' + datedRows.length + ')</h3>' +
    (datedRows.length ? '<ol class="research-timeline research-timeline-dated">' +
      datedRows.map(researchTimelineEntry).join("") + '</ol>' :
      '<p class="ctl-note">' + escapeHtml(uiLabel("research_timeline_no_dated")) + '</p>') +
    '<h3>' + escapeHtml(uiLabel("research_timeline_unplaced")) + ' (' + unplacedRows.length + ')</h3>' +
    (unplacedRows.length ? '<p class="ctl-note">' + escapeHtml(uiLabel("research_timeline_placement_hint")) + '</p>' +
      '<ol class="research-timeline research-timeline-unplaced">' +
      unplacedRows.map(researchTimelineEntry).join("") + '</ol>' :
      '<p class="ctl-note">' + escapeHtml(uiLabel("research_timeline_no_unplaced")) + '</p>') :
    '<p class="ctl-note">' + escapeHtml(timeline.message || uiLabel("research_load_claims_failed")) + '</p>';
  var callout = document.getElementById("r-timeline-callout");
  if (callout && timeline.ok) {
    callout.textContent = uiFormat("research_timeline_callout", {
      dated: datedRows.length, total: datedRows.length + unplacedRows.length});
    callout.hidden = false;
  }
  if (!relations.ok) {
    relationsHost.textContent = relations.message || uiLabel("research_load_claims_failed");
    return;
  }
  var schema = Number(String(relations.archive_schema_version || "").split("/").pop());
  document.getElementById("r-relation-compatibility").hidden = schema >= 6;
  if (!researchContextToken()) document.getElementById("r-relation-status").textContent = uiLabel("research_relation_unavailable");
  relationsHost.innerHTML = (relations.relations || []).map(function(relation) {
    return '<article class="research-card research-relation-card" data-relation-id="' + escapeHtml(relation.relation_id) + '">' +
      '<p class="research-relation-endpoints"><span>' + researchRelationEndpoint(relation.from_claim) + '</span><strong>' +
      escapeHtml(uiLabel("research_relation_causes")) + '</strong><span>' + researchRelationEndpoint(relation.to_claim) + '</span></p>' +
      '<p class="ctl-note">' + escapeHtml(uiLabel("research_relation_" + relation.state)) + '</p>' +
      (relation.rationale ? '<p class="research-timeline-statement">' + escapeHtml(relation.rationale) + '</p>' : '') +
      (relation.review_needed ? '<p class="ctl-status err">' + escapeHtml(uiLabel("research_relation_review")) + '</p>' : '') +
      researchRevisionActions("claim_relation", relation.relation_id) + '</article>';
  }).join("") || '<p class="ctl-note">' + escapeHtml(uiLabel("research_relation_empty")) + '</p>';
}

document.addEventListener("change", function(event) {
  if (["r-relation-from", "r-relation-to"].includes(event.target.id)) updateResearchRelationControls();
  if (event.target.id === "r-relation-retracted") refreshResearchClaimProjections();
});
document.addEventListener("click", function(event) {
  if (event.target.id === "r-find-passage") {
    if (!researchEvidenceDraft) researchEvidenceReview = reviewedEvidenceClaim();
    document.getElementById("r-search-scope").value = "sources";
    if (window.LixityResearchTools) window.LixityResearchTools.open("search", event.target);
    else document.querySelector('[data-rtab="search"]').click();
    document.getElementById("r-search-query").focus();
  }
});
var researchRelationForm = document.getElementById("r-relation-form");
if (researchRelationForm) researchRelationForm.addEventListener("submit", async function(event) {
  event.preventDefault();
  if (researchRelationPending) return;
  var from = document.getElementById("r-relation-from"), to = document.getElementById("r-relation-to");
  var rationale = document.getElementById("r-relation-rationale"), reading = document.getElementById("r-relation-status");
  var fromClaim = researchClaimChoices[from.value], toClaim = researchClaimChoices[to.value];
  if (!fromClaim || !toClaim || from.value === to.value || !researchContextToken() || !researchClaimsSnapshot) {
    reading.textContent = uiLabel("research_relation_required"); return;
  }
  var context = researchReadContext(), submitted = {from: from.value, to: to.value, rationale: rationale.value};
  researchRelationPending = true; updateResearchRelationControls();
  document.getElementById("r-relation-save").setAttribute("aria-busy", "true");
  try {
    var result = await researchApiPost("research-claim-relation", {project_id: context.projectId,
      expected_snapshot: researchClaimsSnapshot, from_claim_id: from.value, to_claim_id: to.value,
      from_claim_revision: fromClaim.revision, to_claim_revision: toClaim.revision,
      relation: "causes", rationale: rationale.value.trim() || null});
    if (!acceptResearchContext(context, result)) return;
    reading.textContent = result.ok ? uiLabel("research_relation_saved") : result.message || uiLabel("research_relation_unavailable");
    if (result.ok) {
      if (from.value === submitted.from && to.value === submitted.to && rationale.value === submitted.rationale) {
        from.value = ""; to.value = ""; rationale.value = "";
      }
      await refreshResearchClaims();
    }
  } finally {
    researchRelationPending = false; updateResearchRelationControls();
    document.getElementById("r-relation-save").removeAttribute("aria-busy");
  }
});

var researchClaimCardItems = [];
var researchDecisionsRender = 0;

function renderResearchFilterPills(hostId, attrName, options, activeValue, onSelect) {
  var host = document.getElementById(hostId);
  if (!host) return;
  if (!options || !options.length) {
    host.hidden = true;
    host.replaceChildren();
    return;
  }
  var frag = document.createDocumentFragment();
  options.forEach(function(opt) {
    var btn = document.createElement("button");
    btn.type = "button";
    var isActive = opt.value === activeValue;
    btn.className = "ctl ctl-sm" + (isActive ? " active" : "");
    btn.setAttribute(attrName, opt.value);
    btn.setAttribute("aria-pressed", String(isActive));
    btn.textContent = opt.label + " (" + opt.count + ")";
    btn.addEventListener("click", function() { onSelect(opt.value); });
    frag.appendChild(btn);
  });
  host.replaceChildren(frag);
  host.hidden = false;
}

function renderResearchClaimFilterPills() {
  var items = researchClaimCardItems;
  if (!items.length) {
    renderResearchFilterPills("r-claims-filter-pills", "data-claim-filter", [], "all", function() {});
    return;
  }
  var counts = {evidenced: 0, disputed: 0, hypothetical: 0};
  items.forEach(function(item) {
    var conf = item.confidence === "evidenced" || item.confidence === "disputed" ? item.confidence : "hypothetical";
    counts[conf] += 1;
  });
  var options = [
    {value: "all", label: uiLabel("research_filter_all") || "All", count: items.length},
    {value: "evidenced", label: uiLabel("research_confidence_evidenced"), count: counts.evidenced},
    {value: "disputed", label: uiLabel("research_confidence_disputed"), count: counts.disputed},
    {value: "hypothetical", label: uiLabel("research_confidence_hypothetical"), count: counts.hypothetical}
  ];
  renderResearchFilterPills("r-claims-filter-pills", "data-claim-filter", options, researchWindowState.claims.filter, function(val) {
    researchWindowState.claims.filter = val;
    researchWindowState.claims.limit = RESEARCH_LIST_PAGE_SIZE;
    renderResearchClaimFilterPills();
    renderResearchClaimCards();
  });
}

function renderResearchClaimCards() {
  var host = document.getElementById("research-claims-list");
  if (!host) return;
  if (!researchClaimCardItems.length) {
    renderWindowedResearchList("claims", host, [], uiLabel("research_no_claims"));
    return;
  }
  var activeFilter = researchWindowState.claims.filter || "all";
  var filtered = activeFilter === "all"
    ? researchClaimCardItems
    : researchClaimCardItems.filter(function(item) { return item.confidence === activeFilter; });
  renderWindowedResearchList("claims", host, filtered, filtered.length ? null : uiLabel("research_no_claims"));
}

async function refreshResearchClaims(overview) {
  var request = ++researchClaimsRead;
  var context = researchReadContext();
  var listHost = document.getElementById("research-claims-list");
  var selectHost = document.getElementById("r-decision-claim-select");
  var linkClaimSelect = document.getElementById("r-link-claim-select");
  if (!listHost) return;
  if (!listHost.children.length) LixityResearchCards.render(listHost, {loading: true});
  // Startup's overview has no archive snapshot. Evidence actions need the
  // versioned catalogue before their result can survive an unchanged refresh.
  var versionedOverview = overview && Array.isArray(overview.claims) &&
    typeof overview.snapshot === "string" && overview.snapshot;
  var data = versionedOverview ? overview : await researchApiGet("research/claims");
  if (request !== researchClaimsRead || !acceptResearchContext(context, data)) return;
  if (!data.ok) {
    researchClaimCardItems = [];
    renderResearchClaimFilterPills();
    renderWindowedResearchList("claims", listHost, [], data.message || uiLabel("research_load_claims_failed"));
    return;
  }
  var claims = data.claims || [];
  if (window.LixityComponents) {
    window.LixityComponents.renderTagSuggestions("r-claim-tag-suggestions", topResearchTags(claims), uiLabel("research_tag_suggestions"));
  }
  researchClaimsSnapshot = typeof data.snapshot === "string" && data.snapshot || null;
  researchClaimChoices = Object.fromEntries(claims.map(function(claim) {return [claim.id, claim];}));
  refreshResearchClaimProjections();
  if (selectHost) {
    var selectedDecisionClaim = selectHost.value;
    selectHost.innerHTML = '<option value="">' + escapeHtml(uiLabel("research_no_claim_linked")) + '</option>' +
      claims.map(function(c) {
        return '<option value="' + escapeHtml(c.id) + '">' + escapeHtml(researchClaimChoiceLabel(c)) + '</option>';
      }).join("");
    if (claims.some(function(c) { return c.id === selectedDecisionClaim; })) selectHost.value = selectedDecisionClaim;
  }
  if (linkClaimSelect) {
    var selectedEvidenceClaim = linkClaimSelect.value;
    linkClaimSelect.innerHTML = '<option value="">' + escapeHtml(uiLabel("research_select_claim")) + '</option>' +
      claims.map(function(c) {
        return '<option value="' + escapeHtml(c.id) + '">' + escapeHtml(researchClaimChoiceLabel(c)) + '</option>';
      }).join("");
    if (claims.some(function(c) { return c.id === selectedEvidenceClaim; })) linkClaimSelect.value = selectedEvidenceClaim;
  }
  syncAllSearchableSelects();
  if (!claims.length) {
    researchClaimCardItems = [];
    renderResearchClaimFilterPills();
    renderWindowedResearchList("claims", listHost, [], uiLabel("research_no_claims"));
    return;
  }
  var catalogueContext = researchClaimsSnapshot ? JSON.stringify([context.projectId, context.token, researchClaimsSnapshot]) : null;
  var previousItems = new Map(researchClaimCardItems.map(function(item) {return [item.id, item];}));
  researchClaimCardItems = claims.map(function(c) {
    var key = JSON.stringify(c), previous = previousItems.get(c.id);
    // Evidence/source changes can leave the claim bytes unchanged. Reuse its
    // pending or loaded panel only for the same accepted archive and context.
    if (catalogueContext && previous && previous.key === key && previous.catalogueContext === catalogueContext) return previous;
    var confKey = c.confidence === "evidenced" ? "evidenced" : (c.confidence === "disputed" ? "disputed" : "hypothetical");
    var confClass = confKey === "evidenced" ? "badge-success" : (confKey === "disputed" ? "badge-warning" : "badge-neutral");
    var confLabel = confKey === "evidenced" ? uiLabel("research_confidence_evidenced")
      : (confKey === "disputed" ? uiLabel("research_confidence_disputed") : uiLabel("research_confidence_hypothetical"));
    var scopeParts = [];
    if (c.scope) {
      if (c.scope.time_period) scopeParts.push(uiLabel("research_scope_time") + " " + c.scope.time_period);
      if (c.scope.place) scopeParts.push(uiLabel("research_scope_place") + " " + c.scope.place);
      if (c.scope.actors && c.scope.actors.length) scopeParts.push(uiLabel("research_scope_actors") + " " + c.scope.actors.join(", "));
    }
    var metaRight = [];
    if (c.revision) {
      metaRight.push({
        text: uiFormat("research_revision_number", { revision: c.revision }),
        title: "Revisionsstand und Fassungsnummer dieser These"
      });
    }
    var dossierLine = null;
    if (c.dossier_id) {
      dossierLine = uiLabel("research_dossier") + ": " + researchReferenceLabel("dossier", {id:c.dossier_id, revision:c.dossier_revision});
    }
    return {
      key: key,
      catalogueContext: catalogueContext,
      id: c.id,
      confidence: confKey,
      title: c.title,
      badges: [{label: confLabel, cls: confClass}],
      metaRight: metaRight,
      statementHtml: renderSafeMarkdown(c.statement),
      scopeText: scopeParts.join(" · "),
      dossierLine: dossierLine,
      tags: c.tags || [],
      evidence: true,
      revision: "claim",
    };
  });
  renderResearchClaimFilterPills();
  renderResearchClaimCards();
}

function renderResearchDecisionFilterPills() {
  var items = researchWindowState.decisions.items;
  if (!items.length) {
    renderResearchFilterPills("r-decisions-filter-pills", "data-decision-filter", [], "all", function() {});
    return;
  }
  var devCount = 0, noDevCount = 0;
  items.forEach(function(item) {
    if (item.deviation) devCount += 1;
    else noDevCount += 1;
  });
  var options = [
    {value: "all", label: uiLabel("research_filter_all") || "All", count: items.length},
    {value: "deviation", label: uiLabel("research_deliberate_deviation"), count: devCount},
    {value: "no_deviation", label: uiLabel("research_no_deviation_recorded"), count: noDevCount}
  ];
  renderResearchFilterPills("r-decisions-filter-pills", "data-decision-filter", options, researchWindowState.decisions.filter, function(val) {
    researchWindowState.decisions.filter = val;
    researchWindowState.decisions.limit = RESEARCH_LIST_PAGE_SIZE;
    renderResearchDecisionFilterPills();
    renderResearchDecisionCards();
  });
}

function renderResearchDecisionCards() {
  var host = document.getElementById("research-decisions-list");
  if (!host) return;
  var items = researchWindowState.decisions.items;
  if (!items.length) {
    renderWindowedResearchList("decisions", host, [], uiLabel("research_no_decisions"));
    return;
  }
  var activeFilter = researchWindowState.decisions.filter || "all";
  var filtered = activeFilter === "all"
    ? items
    : items.filter(function(item) { return activeFilter === "deviation" ? item.deviation : !item.deviation; });
  renderWindowedResearchList("decisions", host, filtered, filtered.length ? null : uiLabel("research_no_decisions"));
}

async function refreshResearchDecisions(overview) {
  var listHost = document.getElementById("research-decisions-list");
  if (!listHost) return;
  if (!listHost.children.length) LixityResearchCards.render(listHost, {loading: true});
  var data = overview && Array.isArray(overview.decisions) ? overview : await researchApiGet("research/decisions");
  if (!data.ok) {
    researchWindowState.decisions.items = [];
    renderResearchDecisionFilterPills();
    renderWindowedResearchList("decisions", listHost, [], data.message || uiLabel("research_load_decisions_failed"));
    return;
  }
  var decisions = data.decisions || [];
  if (!decisions.length) {
    researchWindowState.decisions.items = [];
    renderResearchDecisionFilterPills();
    renderWindowedResearchList("decisions", listHost, [], uiLabel("research_no_decisions"));
    return;
  }
  // The previous string renderer replaced the whole list, so a refresh closed
  // any open decision impact panel and dropped its loaded content. Keep that:
  // the impact view can hold stale acknowledgement state. Sources and dossiers
  // keep their open details via identity keys.
  var decisionsRender = ++researchDecisionsRender;
  researchWindowState.decisions.items = decisions.map(function(d) {
    var badges = [d.deviation_from_fact
      ? {label: uiLabel("research_deliberate_deviation"), cls: "badge-warning"}
      : {label: uiLabel("research_no_deviation_recorded"), cls: "badge-neutral"}];
    var metaRight = [];
    if (d.revision) {
      metaRight.push({
        text: uiFormat("research_revision_number", { revision: d.revision }),
        title: "Revisionsstand und Fassungsnummer dieser Entscheidung"
      });
    }
    var claimLine = null;
    if (d.claim_id) {
      claimLine = uiLabel("research_decision_claim") + " " + researchReferenceLabel("claim", {id:d.claim_id, revision:d.claim_revision});
    }
    return {
      key: "decision:" + decisionsRender + ":" + d.id,
      id: d.id,
      deviation: Boolean(d.deviation_from_fact),
      title: d.title,
      badges: badges,
      metaRight: metaRight,
      rationaleHtml: renderSafeMarkdown(d.rationale),
      impactHtml: d.impact_on_plot ? renderSafeMarkdown(d.impact_on_plot) : null,
      impactLabel: uiLabel("research_decision_impact"),
      relatedLine: claimLine,
      decisionImpact: true,
      revision: "decision",
    };
  });
  renderResearchDecisionFilterPills();
  renderResearchDecisionCards();
}

var SEARCHABLE_SELECT_IDS = [
  "r-dos-eids",
  "r-claim-dossier-select",
  "r-decision-claim-select",
  "r-decision-dossier-select",
  "r-link-claim-select",
  "r-relation-from",
  "r-relation-to"
];

function filterSelectOptions(select, rawQuery) {
  var query = String(rawQuery || "").trim().toLowerCase();
  Array.from(select.options).forEach(function(opt) {
    var keep = opt.value === "" || opt.selected || !query || opt.textContent.toLowerCase().includes(query);
    opt.hidden = !keep;
    opt.disabled = !keep;
  });
}

function renderSelectChips(select) {
  var chipsHost = document.getElementById(select.id + "-chips");
  if (!chipsHost) return;
  var selected = Array.from(select.options).filter(function(opt) { return opt.selected && opt.value !== ""; });
  if (!selected.length) {
    chipsHost.hidden = true;
    chipsHost.replaceChildren();
    return;
  }
  var frag = document.createDocumentFragment();
  selected.forEach(function(opt) {
    var chip = document.createElement("button");
    chip.type = "button";
    chip.className = "research-tag";
    chip.dataset.selectChipSelect = select.id;
    chip.dataset.selectChipValue = opt.value;
    chip.textContent = opt.textContent + " ×";
    frag.appendChild(chip);
  });
  chipsHost.replaceChildren(frag);
  chipsHost.hidden = false;
}

function syncSearchableSelect(select) {
  if (!select || !select.id) return;
  var searchInput = document.getElementById(select.id + "-search");
  if (!searchInput) return;
  var isMultiEids = select.id === "r-dos-eids";
  var shouldShowSearch = !select.hidden && (isMultiEids ? select.options.length > 0 : select.options.length > 10);
  searchInput.hidden = !shouldShowSearch;
  if (!shouldShowSearch && searchInput.value) searchInput.value = "";
  filterSelectOptions(select, searchInput.value);
  renderSelectChips(select);
}

function ensureSearchableSelect(selectId) {
  var select = document.getElementById(selectId);
  if (!select || select.dataset.searchableMounted === "1") return select;
  select.dataset.searchableMounted = "1";
  var search = document.createElement("input");
  search.type = "search";
  search.className = "ctl ctl-sm mb-1";
  search.id = select.id + "-search";
  search.placeholder = uiLabel("research_filter_select") || "Filter options…";
  search.setAttribute("aria-label", search.placeholder);
  search.dataset.selectSearchFor = select.id;
  search.hidden = true;
  search.addEventListener("input", function() {
    filterSelectOptions(select, search.value);
  });
  var chips = document.createElement("div");
  chips.className = "research-tags mt-1";
  chips.id = select.id + "-chips";
  chips.dataset.selectChipsFor = select.id;
  chips.hidden = true;
  select.parentNode.insertBefore(search, select);
  select.parentNode.insertBefore(chips, select.nextSibling);
  select.addEventListener("change", function() {
    filterSelectOptions(select, search.value);
    renderSelectChips(select);
  });
  if (typeof MutationObserver === "function") {
    var syncing = false;
    new MutationObserver(function() {
      if (syncing) return;
      syncing = true;
      try { syncSearchableSelect(select); }
      finally { syncing = false; }
    }).observe(select, {childList: true, attributes: true, attributeFilter: ["hidden"]});
  }
  syncSearchableSelect(select);
  return select;
}

function syncAllSearchableSelects() {
  SEARCHABLE_SELECT_IDS.forEach(function(id) {
    var select = ensureSearchableSelect(id);
    if (select) syncSearchableSelect(select);
  });
}

document.addEventListener("click", function(event) {
  var chip = event.target.closest("[data-select-chip-select]");
  if (!chip) return;
  var select = document.getElementById(chip.dataset.selectChipSelect);
  if (!select) return;
  var val = chip.dataset.selectChipValue;
  if (select.multiple) {
    Array.from(select.options).forEach(function(opt) {
      if (opt.value === val) opt.selected = false;
    });
  } else {
    select.value = "";
  }
  select.dispatchEvent(new Event("change", {bubbles: true}));
  syncSearchableSelect(select);
});

syncAllSearchableSelects();
