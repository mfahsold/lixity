// Research workspace: revision dialogs, batch review and startup call.
// Split of the former research.js; _JS_FILES concatenates the parts in
// the original order, so load-time behaviour is unchanged.
// One revision dialog serves all authored research records. References are
// edited by ID; the API preserves their pinned revisions when IDs are unchanged.
var researchRevisionDialog = document.getElementById("modal-research-revision");
if (researchRevisionDialog) {
  var revisionForm = document.getElementById("research-revision-form");
  var revisionFieldsHost = document.getElementById("research-revision-fields");
  var revisionEditTab = document.getElementById("research-revision-edit-tab");
  var revisionHistoryTab = document.getElementById("research-revision-history-tab");
  var revisionHistoryPane = document.getElementById("research-revision-history");
  var revisionVersions = document.getElementById("research-revision-versions");
  var revisionHistoryList = document.getElementById("research-revision-history-list");
  var revisionHistoryDetail = document.getElementById("research-revision-history-detail");
  var revisionStatusHost = document.getElementById("research-revision-status");
  var revisionMeta = document.getElementById("research-revision-kind");
  var revisionIdentifier = document.getElementById("research-revision-identifier");
  var revisionSnapshot = document.getElementById("research-revision-snapshot");
  var revisionUpdates = document.getElementById("research-revision-source-updates");
  var revisionCitationsWrap = document.getElementById("research-revision-citations-wrap");
  var revisionCitations = document.getElementById("research-revision-citations");
  var revisionReason = document.getElementById("research-revision-reason");
  var revisionSave = document.getElementById("research-revision-save");
  var revisionReload = document.getElementById("research-revision-reload");
  var revisionMerge = document.getElementById("research-revision-merge");
  var revisionMergeFields = document.getElementById("research-revision-merge-fields");
  var revisionMergeApply = document.getElementById("research-revision-merge-apply");
  var revisionBatchAdd = document.getElementById("research-revision-batch-add");
  var revisionBatchReview = document.getElementById("research-revision-batch-review");
  var revisionBatchDialog = document.getElementById("modal-research-revision-batch");
  var revisionBatchList = document.getElementById("research-revision-batch-list");
  var revisionBatchStatusHost = document.getElementById("research-revision-batch-status");
  var revisionBatchCheck = document.getElementById("research-revision-batch-check");
  var revisionBatchApply = document.getElementById("research-revision-batch-apply");
  var revisionBatch = {projectId: null, entries: [], preview: null, pending: false, request: 0};
  var revisionState = {kind: "", id: "", session: 0, request: 0, historyRequest: 0, historyListRequest: 0,
    current: null, initial: {}, dossierPins: {}, mode: "edit", historyLoaded: false, pending: false, loading: false, merge: null,
    section: null, sectionBase: null, sectionContent: null, historyInitialRevision: null,
    historyView: null, historyEnvelope: null, historySelectionRevision: null, context: null};

  function revisionContextMatches(data) {
    var context = revisionState.context;
    return context && context.token === researchContextToken() &&
      (!context.projectId || context.projectId === researchSelectionProjectId) &&
      (!data.project_id || !context.projectId || data.project_id === context.projectId);
  }

  function revisionEditableSpecs() {
    return (revisionSpecs[revisionState.kind] || []).filter(function(spec) { return !revisionState.section || spec.name === "body"; });
  }

  function revisionSectionEndpoint(number) {
    return "research/dossiers?id=" + encodeURIComponent(revisionState.id) + "&revision=" + encodeURIComponent(number) +
      "&section=" + encodeURIComponent(revisionState.section);
  }

  function revisionViewedRecord(envelope, historical) {
    var record = envelope && envelope.record;
    return record ? {kind: revisionState.kind, title: record.title || record.id, revision: record.revision,
      pinned: historical && revisionState.historyInitialRevision === record.revision,
      current: record.revision === envelope.latest_revision} : null;
  }

  function revisionShowMeta(envelope) {
    var record = envelope && envelope.record;
    revisionMeta.textContent = uiLabel("research_revision_kind_" + revisionState.kind) +
      (record ? " · " + uiFormat("research_revision_number", {revision: record.revision}) + " · " +
        uiLabel(record.revision === envelope.latest_revision ? "research_revision_current" : "research_revision_earlier") : "") +
      (revisionState.section ? " · " + uiFormat("research_section_editing", {section: revisionState.section}) : "");
    revisionIdentifier.textContent = revisionState.id;
    revisionSnapshot.textContent = envelope ? envelope.snapshot || "" : "";
    // Only envelopes accepted by the viewer's context/session guards reach here.
    document.dispatchEvent(new CustomEvent("lixity:research-record-view", {
      detail: revisionViewedRecord(envelope, revisionState.mode === "history")}));
  }

  var revisionSpecs = {
    dossier: [
      {name: "title", label: "research_dossier_title", required: true},
      {name: "body", label: "research_dossier_body", readLabel: "research_read_notes", type: "textarea", required: true},
      {name: "geography", label: "geography_title", type: "geography"},
      {name: "tags", label: "research_tags", readLabel: "research_read_tags", type: "list"},
      {name: "evidence_ids", label: "research_evidence_ids", readLabel: "research_passages", type: "list"}
    ],
    claim: [
      {name: "title", label: "research_claim_title", readLabel: "research_read_title", required: true},
      {name: "statement", label: "research_claim_statement", readLabel: "research_read_statement", type: "textarea", required: true},
      {name: "confidence", label: "research_confidence_field", type: "select", options: [
        ["hypothetical", "research_confidence_hypothetical"], ["evidenced", "research_confidence_evidenced"], ["disputed", "research_confidence_disputed"]]},
      {name: "time_period", label: "research_claim_time", readLabel: "research_read_period"},
      {name: "place", label: "research_claim_place", readLabel: "research_read_place"},
      {name: "actors", label: "research_claim_actors", readLabel: "research_read_actors", type: "list"},
      {name: "dossier_id", label: "research_dossier"},
      {name: "dossier_revision", label: "research_revision_dossier_revision", type: "number"},
      {name: "tags", label: "research_tags", readLabel: "research_read_tags", type: "list"}
    ],
    evidence_link: [
      {name: "claim_id", label: "research_claim_id", required: true},
      {name: "claim_revision", label: "research_revision_claim_revision", type: "number"},
      {name: "passage_id", label: "research_passage_id", readLabel: "research_read_passage", required: true},
      {name: "relation", label: "research_relation_field", type: "select", options: [
        ["supports", "research_relation_supports"], ["contradicts", "research_relation_contradicts"],
        ["qualifies", "research_relation_qualifies"], ["contextualizes", "research_relation_contextualizes"]]},
      {name: "rationale", label: "research_link_rationale", readLabel: "research_read_rationale", type: "textarea"},
      {name: "reviewer", label: "research_revision_reviewer", required: true}
    ],
    claim_relation: [
      {name: "from_claim_id", label: "research_relation_from", type: "claim", required: true},
      {name: "from_claim_revision", label: "research_revision_from_claim_revision", type: "number"},
      {name: "to_claim_id", label: "research_relation_to", type: "claim", required: true},
      {name: "to_claim_revision", label: "research_revision_to_claim_revision", type: "number"},
      {name: "relation", label: "research_relation_field", type: "select", options: [["causes", "research_relation_causes"]]},
      {name: "state", label: "research_relation_state", required: true, type: "select", options: [
        ["active", "research_relation_active"], ["retracted", "research_relation_retracted"]]},
      {name: "rationale", label: "research_link_rationale", readLabel: "research_read_rationale", type: "textarea"}
    ],
    decision: [
      {name: "title", label: "research_decision_title", readLabel: "research_read_title", required: true},
      {name: "rationale", label: "research_decision_rationale", readLabel: "research_read_rationale", type: "textarea", required: true},
      {name: "claim_id", label: "research_claim_id"},
      {name: "claim_revision", label: "research_revision_claim_revision", type: "number"},
      {name: "deviation_from_fact", label: "research_deviation_checkbox", type: "checkbox"},
      {name: "impact_on_plot", label: "research_decision_plot", readLabel: "research_read_plot_impact", type: "textarea"},
      {name: "dossier_ids", label: "research_revision_dossier_ids", readLabel: "research_read_dossiers", type: "list"}
    ]
  };

  function revisionRefText(ref, pinned) {
    if (!ref || !ref.id) return "";
    return ref.id + (pinned && ref.revision ? " · " + uiFormat("research_revision_number", {revision: ref.revision}) : "");
  }

  function revisionFieldValue(record, name, pinned) {
    if (name === "geography") return record.geography || null;
    if (name === "evidence_ids") return (record.evidence_refs || []).map(function(ref) { return revisionRefText(ref, pinned); });
    if (name === "dossier_ids") return (record.dossier_refs || []).map(function(ref) { return revisionRefText(ref, pinned); });
    if (name === "dossier_revisions") return Object.fromEntries((record.dossier_refs || []).map(function(ref) { return [ref.id, ref.revision]; }));
    if (name === "dossier_id") return revisionRefText(record.dossier_ref, pinned);
    if (name === "dossier_revision") return record.dossier_ref ? record.dossier_ref.revision : "";
    if (name === "claim_id") return revisionRefText(record.claim_ref, pinned);
    if (name === "claim_revision") return record.claim_ref ? record.claim_ref.revision : "";
    if (name === "passage_id") return revisionRefText(record.passage_ref, pinned);
    for (var role of ["from", "to"]) {
      var ref = record[role + "_claim_ref"];
      if (name === role + "_claim_id") return revisionRefText(ref, pinned);
      if (name === role + "_claim_revision") return ref ? ref.revision : "";
    }
    if (["time_period", "place", "actors"].includes(name)) {
      var scoped = (record.scope || {})[name];
      return scoped === null || scoped === undefined ? (name === "actors" ? [] : "") : scoped;
    }
    return record[name] === null || record[name] === undefined ? "" : record[name];
  }

  function revisionStatus(message, error) {
    revisionStatusHost.textContent = message || "";
    revisionStatusHost.hidden = !message;
    revisionStatusHost.className = "ctl-status" + (error ? " err" : "");
  }

  function revisionNotices(envelope) {
    revisionUpdates.replaceChildren();
    var updates = (envelope && envelope.source_updates) || [];
    var references = (envelope && envelope.reference_updates) || [];
    var scopedCitations = envelope && envelope.citation_scope === "current_links_to_pinned_claim_revision" &&
      envelope.citations && envelope.citations.length;
    var relationEndpoints = envelope && revisionState.mode === "edit" &&
      revisionState.kind === "claim_relation" && envelope.from_claim && envelope.to_claim;
    revisionUpdates.hidden = !updates.length && !references.length && !scopedCitations && !relationEndpoints;
    if (revisionUpdates.hidden) return;
    if (updates.length) {
      var note = document.createElement("p");
      note.textContent = uiLabel("research_revision_newer_source");
      var list = document.createElement("ul");
      updates.forEach(function(update) {
        var item = document.createElement("li");
        item.textContent = uiFormat("research_revision_source_versions", {
          source: update.source_title || update.source_id || "",
          cited: update.cited_sequence || "?", latest: update.latest_sequence || "?"
        });
        list.appendChild(item);
      });
      revisionUpdates.append(note, list);
    }
    if (relationEndpoints) {
      ["from", "to"].forEach(function(role) {
        var endpoint = envelope[role + "_claim"], note = document.createElement("p");
        note.textContent = uiLabel("research_relation_" + role) + ": " + endpoint.title + " · " +
          uiFormat("research_revision_number", {revision: endpoint.revision});
        revisionUpdates.appendChild(note);
      });
    }
    references.forEach(function(ref) {
      var note = document.createElement("p");
      note.textContent = uiFormat("research_revision_reference_update", {
        kind: uiLabel("research_revision_kind_" + ref.kind),
        pinned: ref.pinned_revision, latest: ref.latest_revision
      });
      revisionUpdates.appendChild(note);
    });
    if (scopedCitations) {
      var scopeNote = document.createElement("p");
      scopeNote.textContent = uiLabel("research_revision_citation_scope");
      revisionUpdates.appendChild(scopeNote);
    }
  }

  function revisionShowCitations(citations) {
    revisionCitationsWrap.hidden = !citations || !citations.length;
    revisionCitations.innerHTML = (citations || []).map(function(cite) {
      return researchCitationHtml(cite, false);
    }).join("");
  }

  function revisionBuildFields(record) {
    revisionFieldsHost.replaceChildren();
    revisionState.merge = null;
    revisionMerge.hidden = true;
    revisionState.initial = {};
    revisionState.dossierPins = revisionFieldValue(record, "dossier_revisions", false);
    var options = document.createElement("details");
    options.className = "research-details";
    options.id = "research-revision-options";
    var summary = document.createElement("summary");
    summary.textContent = uiLabel("optional_details");
    options.appendChild(summary);
    revisionEditableSpecs().forEach(function(spec) {
      var raw = revisionState.section && spec.name === "body" ? revisionState.sectionContent : revisionFieldValue(record, spec.name, false);
      var value = Array.isArray(raw) ? raw.slice() : raw;
      revisionState.initial[spec.name] = value;
      var id = "research-revision-field-" + spec.name;
      var group = document.createElement("div");
      group.className = "form-group";
      var field;
      if (spec.type === "geography") {
        field = window.LixityDossierGeography.mount(group, id, value);
        revisionState.initial[spec.name] = field._geographyEditor.read();
      } else if (spec.type === "checkbox") {
        var checkLabel = document.createElement("label");
        checkLabel.className = "form-checkbox";
        field = document.createElement("input");
        field.type = "checkbox";
        field.checked = Boolean(value);
        var checkText = document.createElement("span");
        checkText.textContent = uiLabel(spec.label);
        checkLabel.append(field, checkText);
        group.appendChild(checkLabel);
      } else {
        var label = document.createElement("label");
        label.className = "form-label";
        label.htmlFor = id;
        label.textContent = uiLabel(spec.label);
        group.appendChild(label);
        field = spec.type === "textarea" ? document.createElement("textarea") :
          ["select", "claim"].includes(spec.type) ? document.createElement("select") : document.createElement("input");
        field.className = "ctl";
        if (spec.type === "textarea") field.rows = spec.name === "body" ? 8 : 3;
        if (spec.type === "claim") {
          Object.values(researchClaimChoices).forEach(function(claim) {
            var option = document.createElement("option"); option.value = claim.id;
            option.textContent = researchClaimChoiceLabel(claim); field.appendChild(option);
          });
          if (!researchClaimChoices[value]) {
            var pinnedEndpoint = revisionState.current[spec.name.startsWith("from") ? "from_claim" : "to_claim"];
            var pinnedOption = document.createElement("option"); pinnedOption.value = value;
            pinnedOption.textContent = pinnedEndpoint ? pinnedEndpoint.title : value; field.appendChild(pinnedOption);
          }
        } else if (spec.type === "select") {
          (spec.options || []).forEach(function(option) {
            var item = document.createElement("option");
            item.value = option[0];
            item.textContent = uiLabel(option[1]);
            field.appendChild(item);
          });
        } else if (field.tagName === "INPUT") {
          field.type = spec.type === "number" ? "number" : "text";
          if (spec.type === "number") { field.min = "1"; field.step = "1"; }
        }
        field.value = Array.isArray(value) ? value.join(", ") : String(value || "");
        field.required = Boolean(spec.required);
        group.appendChild(field);
      }
      field.id = id;
      field.name = spec.name;
      var optional = !spec.required && spec.type !== "geography" && !["confidence", "relation"].includes(spec.name);
      if (optional) options.appendChild(group);
      else revisionFieldsHost.appendChild(group);
    });
    if (options.children.length > 1) revisionFieldsHost.appendChild(options);
    ["claim", "dossier", "from_claim", "to_claim"].forEach(function(kind) {
      var idField = document.getElementById("research-revision-field-" + kind + "_id");
      var revisionField = document.getElementById("research-revision-field-" + kind + "_revision");
      if (idField && revisionField) idField.addEventListener("input", function() {
        if (idField.value.trim() !== revisionState.initial[kind + "_id"]) revisionField.value = "";
      });
    });
    revisionReason.value = "";
    revisionForm.querySelectorAll('input[name="research_revision_change_kind"]').forEach(function(input) { input.checked = false; });
    revisionReload.hidden = true;
    revisionUpdateQueueControls();
  }

  function revisionReadOnly(envelope) {
    var record = envelope.record || {};
    var fields = revisionSpecs[revisionState.kind] || [];
    var rows = fields.map(function(spec) {
      // Reference IDs already include their exact pin in read-only mode.
      // Keep the separate numeric controls exclusively in the edit form.
      if (["dossier_revision", "claim_revision", "from_claim_revision", "to_claim_revision"].includes(spec.name)) return "";
      var value = revisionFieldValue(record, spec.name, true);
      if (!spec.required && (value === null || value === undefined ||
          typeof value === "string" && !value.trim() || Array.isArray(value) && !value.length)) return "";
      if (Array.isArray(value)) value = value.join(", ");
      if (spec.type === "select") {
        var option = spec.options.find(function(item) {return item[0] === value;});
        if (option) value = uiLabel(option[1]);
      }
      if (spec.type === "checkbox") value = uiLabel(value ? "research_value_yes" : "research_value_no");
      if (revisionState.kind === "claim_relation" && spec.type === "claim") {
        var endpoint = envelope[spec.name.startsWith("from") ? "from_claim" : "to_claim"];
        if (endpoint) value = endpoint.title + (endpoint.time_period ? " · " + endpoint.time_period : "") +
          " · " + uiFormat("research_revision_number", {revision: endpoint.revision});
      }
      var valHtml = spec.type === "geography" ? window.LixityDossierGeography.html(value, envelope.geography_summary) : spec.name === "body" && value ?
        researchDossierBodyHtml(value, envelope) :
        escapeHtml(String(value === null || value === undefined || value === "" ? "—" : value));
      if (spec.name === "dossier_id" && record.dossier_ref) {
        valHtml = '<button type="button" class="ctl" data-research-history="dossier" data-record-id="' +
          escapeHtml(record.dossier_ref.id) + '" data-record-revision="' + Number(record.dossier_ref.revision) + '">' + valHtml + '</button>';
      }
      return '<dt>' + escapeHtml(uiLabel(spec.readLabel || spec.label)) + '</dt><dd>' + valHtml + '</dd>';
    }).join("");
    var change = record.change;
    var changeText = change ? uiLabel("research_revision_" + change.change_kind) + ": " + change.reason : uiLabel("research_revision_original");
    var provenance = [escapeHtml(changeText)];
    if (record.created_at) {
      var timestamp = String(record.created_at);
      provenance.push(Number.isFinite(new Date(timestamp).getTime()) ?
        '<span title="' + escapeHtml(timestamp) + '">' + researchEditorialTime(timestamp) + '</span>' : escapeHtml(timestamp));
    }
    if (record.created_by) provenance.push(escapeHtml(record.created_by));
    var manuscriptRoute = revisionState.kind === "claim" && window.LixityManuscriptLinks && typeof window.LixityManuscriptLinks.review === "function" ?
      '<p><button type="button" class="ctl" data-manuscript-links-claim="' + escapeHtml(record.id) +
        '" data-record-revision="' + Number(record.revision) + '">' + escapeHtml(uiLabel("manuscript_link_review")) + '</button></p>' : '';
    return '<div class="research-revision-history-detail">' +
      '<dl class="research-revision-readonly">' + rows + '</dl>' +
      '<p class="ctl-note research-revision-provenance">' + provenance.join(" · ") + '</p>' +
      manuscriptRoute +
      '<h4>' + escapeHtml(uiLabel("research_citations")) + '</h4>' +
      ((envelope.citations || []).length ? envelope.citations.map(function(cite) { return researchCitationHtml(cite, false); }).join("") :
        '<p class="ctl-note">' + escapeHtml(uiLabel("research_revision_no_citations")) + '</p>') +
      '</div>';
  }

  function revisionSetTab(mode) {
    revisionState.mode = mode;
    var editing = mode === "edit";
    revisionForm.hidden = !editing;
    revisionHistoryPane.hidden = editing;
    revisionEditTab.classList.toggle("active", editing);
    revisionHistoryTab.classList.toggle("active", !editing);
    revisionEditTab.setAttribute("aria-selected", String(editing));
    revisionHistoryTab.setAttribute("aria-selected", String(!editing));
    revisionEditTab.tabIndex = editing ? 0 : -1;
    revisionHistoryTab.tabIndex = editing ? -1 : 0;
    if (editing && revisionState.current) {
      if (revisionState.current.record.revision < revisionState.current.latest_revision) {
        revisionLoadCurrent(true);
        return;
      }
      revisionShowMeta(revisionState.current);
      revisionNotices(revisionState.current);
      revisionShowCitations(revisionState.current.citations);
    }
    revisionPending(revisionState.pending);
    if (!editing && revisionState.current) {
      var selected = revisionState.historySelectionRevision || revisionState.historyInitialRevision || revisionState.current.record.revision;
      var viewed = revisionState.historyEnvelope;
      if (!revisionContextMatches(revisionState.current) || viewed && !revisionContextMatches(viewed)) {
        revisionShowMeta(null);
        revisionHistoryDetail.textContent = uiLabel("research_revision_conflict");
      } else {
        if (viewed && viewed.record.revision === selected) {
          revisionShowMeta(viewed);
          revisionNotices(viewed);
          revisionShowCitations(viewed.citations);
        } else if (selected === revisionState.current.record.revision) revisionShowReadOnly(revisionState.current);
        else revisionLoadHistorical(selected);
        if (revisionVersions.open && !revisionState.historyLoaded) revisionLoadHistory();
      }
    }
  }

  async function revisionLoadHistory() {
    var request = ++revisionState.historyListRequest;
    var session = revisionState.session;
    revisionHistoryList.textContent = uiLabel("research_revision_loading");
    var data = await researchApiGet("research/history?kind=" + encodeURIComponent(revisionState.kind) +
      "&id=" + encodeURIComponent(revisionState.id));
    if (session !== revisionState.session || request !== revisionState.historyListRequest || !researchRevisionDialog.open || !revisionContextMatches(data)) return;
    if (!data.ok || (revisionState.current && data.project_id !== revisionState.current.project_id)) {
      revisionHistoryList.textContent = uiFormat("research_revision_load_failed", {reason: data.message || uiLabel("wizard_unknown_error")});
      return;
    }
    revisionState.historyLoaded = true;
    revisionHistoryList.replaceChildren();
    if (!data.revisions || !data.revisions.length) {
      revisionHistoryList.textContent = uiLabel("research_revision_history_empty");
      return;
    }
    data.revisions.forEach(function(item) {
      var row = document.createElement("li");
      var button = document.createElement("button");
      button.type = "button";
      button.className = "ctl";
      button.dataset.researchRevision = String(item.revision);
      button.setAttribute("aria-current", String(Boolean(revisionState.historyEnvelope && revisionState.historyEnvelope.record.revision === item.revision)));
      button.setAttribute("aria-description", item.change ? uiLabel("research_revision_" + item.change.change_kind) : uiLabel("research_revision_original"));
      button.textContent = uiFormat("research_revision_number", {revision: item.revision}) +
        (item.revision === data.latest_revision ? " · " + uiLabel("research_revision_current") : "");
      row.appendChild(button);
      revisionHistoryList.appendChild(row);
    });
  }

  function revisionShowReadOnly(data) {
    revisionHistoryDetail.innerHTML = revisionReadOnly(data);
    revisionState.historyEnvelope = data;
    revisionState.historyView = revisionViewedRecord(data, true);
    revisionHistoryList.querySelectorAll("button[data-research-revision]").forEach(function(button) {
      button.setAttribute("aria-current", String(Number(button.dataset.researchRevision) === data.record.revision));
    });
    if (revisionState.mode === "history") {
      revisionShowMeta(data);
      revisionNotices(data);
      revisionShowCitations(data.citations);
    }
  }

  async function revisionLoadHistorical(number) {
    var request = ++revisionState.historyRequest;
    var session = revisionState.session;
    revisionState.historyView = null;
    revisionState.historyEnvelope = null;
    revisionHistoryDetail.textContent = uiLabel("research_revision_loading");
    if (revisionState.mode === "history") revisionShowMeta(null);
    revisionHistoryList.querySelectorAll("button[data-research-revision]").forEach(function(button) {
      button.setAttribute("aria-current", String(Number(button.dataset.researchRevision) === Number(number)));
    });
    var data = await researchApiGet("research/record?kind=" + encodeURIComponent(revisionState.kind) +
      "&id=" + encodeURIComponent(revisionState.id) + "&revision=" + encodeURIComponent(number));
    if (session !== revisionState.session || request !== revisionState.historyRequest || !researchRevisionDialog.open || !revisionContextMatches(data)) return;
    if (!data.ok || !revisionState.current || data.project_id !== revisionState.current.project_id) {
      revisionHistoryDetail.textContent = uiFormat("research_revision_load_failed", {reason: data.message || uiLabel("wizard_unknown_error")});
      return;
    }
    revisionShowReadOnly(data);
  }

  async function revisionLoadCurrent(replaceDraft) {
    var request = ++revisionState.request;
    var session = revisionState.session;
    revisionState.loading = true;
    document.dispatchEvent(new CustomEvent("lixity:research-record-view", {detail: null}));
    revisionPending(revisionState.pending);
    revisionStatus(uiLabel("research_revision_loading"), false);
    try {
      var data = await researchApiGet("research/record?kind=" + encodeURIComponent(revisionState.kind) +
        "&id=" + encodeURIComponent(revisionState.id) +
        (revisionState.section && revisionState.sectionBase ? "&revision=" + encodeURIComponent(revisionState.sectionBase) :
          revisionState.mode === "history" && revisionState.historyInitialRevision ? "&revision=" + encodeURIComponent(revisionState.historyInitialRevision) : ""));
      if (session !== revisionState.session || request !== revisionState.request || !researchRevisionDialog.open || !revisionContextMatches(data)) return;
      if (!data.ok || !data.record || !data.snapshot || !data.project_id) {
        revisionStatus(uiFormat("research_revision_load_failed", {reason: data.message || uiLabel("wizard_unknown_error")}), true);
        revisionReload.hidden = false;
        return;
      }
      if (revisionState.section) {
        var sectionData = await researchApiGet(revisionSectionEndpoint(data.record.revision));
        if (session !== revisionState.session || request !== revisionState.request || !researchRevisionDialog.open || !revisionContextMatches(sectionData)) return;
        if (!sectionData.ok || sectionData.project_id !== data.project_id) {
          revisionStatus(uiFormat("research_revision_load_failed", {reason: sectionData.message || uiLabel("wizard_unknown_error")}), true);
          revisionReload.hidden = false;
          return;
        }
        revisionState.sectionBase = data.record.revision;
        revisionState.sectionContent = sectionData.content;
      }
      revisionState.current = data;
      if (revisionState.mode !== "history") revisionShowMeta(data);
      if (replaceDraft) {
        revisionBuildFields(data.record);
        revisionState.historyRequest++;
        revisionState.historyListRequest++;
        revisionState.historyLoaded = false;
        revisionState.historyEnvelope = null;
        revisionHistoryList.replaceChildren();
        revisionHistoryDetail.replaceChildren();
      }
      revisionNotices(data);
      revisionShowCitations(data.citations);
      revisionStatus("", false);
      if (revisionState.mode === "history") revisionSetTab("history");
    } finally {
      if (session === revisionState.session && request === revisionState.request) {
        revisionState.loading = false;
        revisionPending(revisionState.pending);
      }
    }
  }

  function revisionChanges() {
    var changes = {};
    revisionEditableSpecs().forEach(function(spec) {
      var input = document.getElementById("research-revision-field-" + spec.name);
      var value = spec.type === "geography" ? input._geographyEditor.read() : spec.type === "checkbox" ? input.checked : spec.type === "list" ?
        input.value.split(",").map(function(item) { return item.trim(); }).filter(Boolean) :
        spec.type === "number" ? (input.value ? Number(input.value) : "") :
        spec.type === "textarea" ? input.value : input.value.trim();
      var before = revisionState.initial[spec.name];
      if (spec.type === "number" && value === "") return;
      if (JSON.stringify(value) !== JSON.stringify(before)) {
        changes[spec.name] = value === "" && !spec.required && !revisionState.section ? null : value;
      }
    });
    ["claim", "dossier", "from_claim", "to_claim"].forEach(function(kind) {
      if (!Object.prototype.hasOwnProperty.call(changes, kind + "_id") || !changes[kind + "_id"]) return;
      var pin = document.getElementById("research-revision-field-" + kind + "_revision");
      if (pin && pin.value) changes[kind + "_revision"] = Number(pin.value);
    });
    if (revisionState.kind === "decision") {
      var ids = revisionFieldsHost.querySelector('[name="dossier_ids"]').value.split(",").map(function(id) { return id.trim(); }).filter(Boolean);
      var pins = {};
      ids.forEach(function(id) { if (revisionState.dossierPins[id]) pins[id] = revisionState.dossierPins[id]; });
      var initialPins = revisionFieldValue(revisionState.current.record, "dossier_revisions", false);
      if (Object.prototype.hasOwnProperty.call(changes, "dossier_ids") || Object.keys(pins).some(function(id) { return pins[id] !== initialPins[id]; })) {
        changes.dossier_ids = ids;
        changes.dossier_revisions = pins;
      }
    }
    return changes;
  }

  function revisionDraft() {
    var choice = revisionForm.querySelector('input[name="research_revision_change_kind"]:checked');
    if (!choice || !revisionReason.value.trim()) {
      revisionStatus(uiLabel("research_revision_reason_required"), true);
      if (!choice) revisionForm.querySelector('input[name="research_revision_change_kind"]').focus();
      else revisionReason.focus();
      return null;
    }
    if (!revisionForm.reportValidity()) return null;
    var changes;
    try { changes = revisionChanges(); }
    catch (error) { revisionStatus(error.message || uiLabel("geography_invalid"), true); return null; }
    if (!Object.keys(changes).length) {
      revisionStatus(uiLabel("research_revision_no_changes"), true);
      return null;
    }
    return {kind: revisionState.kind, id: revisionState.id, expected_revision: revisionState.current.record.revision,
      changes: changes, change_kind: choice.value, reason: revisionReason.value.trim()};
  }

  function revisionFillDraft(envelope, changes, reason, changeKind) {
    revisionState.current = envelope;
    revisionBuildFields(envelope.record);
    Object.keys(changes).forEach(function(name) {
      if (name === "dossier_revisions") {
        Object.assign(revisionState.dossierPins, changes[name]);
        return;
      }
      var field = document.getElementById("research-revision-field-" + name);
      if (!field) return;
      var value = changes[name];
      if (field._geographyEditor) field._geographyEditor.set(value);
      else if (field.type === "checkbox") field.checked = Boolean(value);
      else field.value = Array.isArray(value) ? value.join(", ") : value === null ? "" : String(value);
    });
    revisionReason.value = reason;
    revisionForm.querySelectorAll('input[name="research_revision_change_kind"]').forEach(function(input) { input.checked = input.value === changeKind; });
    revisionState.historyRequest++;
    revisionState.historyListRequest++;
    revisionState.historyLoaded = false;
    revisionState.historyEnvelope = null;
    revisionNotices(envelope);
    revisionShowCitations(envelope.citations);
    revisionShowMeta(envelope);
  }

  function revisionEditBlocked() {
    return revisionState.loading || (!revisionState.section && revisionState.current &&
      revisionState.current.record.revision < revisionState.current.latest_revision);
  }

  function revisionPending(pending) {
    revisionState.pending = pending;
    var fieldsPending = pending || revisionEditBlocked();
    revisionForm.setAttribute("aria-busy", String(pending || revisionState.loading));
    revisionFieldsHost.querySelectorAll("input, textarea, select, button").forEach(function(input) { input.disabled = fieldsPending; });
    revisionForm.querySelectorAll('input[name="research_revision_change_kind"]').forEach(function(input) { input.disabled = fieldsPending; });
    revisionReason.disabled = fieldsPending;
    revisionSave.disabled = fieldsPending || !revisionState.current || Boolean(revisionState.merge);
    revisionBatchAdd.disabled = fieldsPending || !revisionState.current || Boolean(revisionState.merge);
    revisionBatchAdd.hidden = Boolean(revisionState.section);
    revisionReload.disabled = pending || revisionState.loading;
    revisionEditTab.disabled = pending;
    revisionHistoryTab.disabled = pending;
    researchRevisionDialog.querySelectorAll("[data-close-modal]").forEach(function(button) { button.disabled = pending; });
    revisionMerge.querySelectorAll("input").forEach(function(input) { input.disabled = pending; });
    revisionMergeApply.disabled = pending || !revisionState.merge ||
      revisionState.merge.preview.conflicts.some(function(item) { return !revisionState.merge.resolutions[item.field]; });
  }

  function revisionMergeValue(value) {
    return value === null || value === undefined ? "—" : typeof value === "string" ? value : JSON.stringify(value, null, 2);
  }

  function revisionMergeLabel(name, kind) {
    if (name === "dossier_revisions") return uiLabel("research_revision_dossier_pins");
    var spec = (revisionSpecs[kind || revisionState.kind] || []).find(function(item) { return item.name === name; });
    return spec ? uiLabel(spec.label) : name;
  }

  function revisionRenderMerge() {
    var merge = revisionState.merge;
    revisionMergeFields.replaceChildren();
    var changed = Object.keys(merge.preview.changes);
    if (changed.length) {
      var heading = document.createElement("p");
      heading.textContent = uiLabel("research_revision_merge_changes");
      var list = document.createElement("dl");
      changed.forEach(function(name) {
        var term = document.createElement("dt"), value = document.createElement("dd");
        term.textContent = revisionMergeLabel(name);
        value.textContent = revisionMergeValue(revisionState.section && name === "body" ? merge.draft.body : merge.preview.changes[name]);
        list.append(term, value);
      });
      revisionMergeFields.append(heading, list);
    }
    if (revisionState.section) {
      var sectionNote = document.createElement("p");
      sectionNote.className = "ctl-note";
      sectionNote.textContent = uiLabel("research_section_preserved");
      revisionMergeFields.appendChild(sectionNote);
    }
    merge.preview.conflicts.forEach(function(conflict) {
      var group = document.createElement("fieldset"), legend = document.createElement("legend");
      legend.textContent = revisionMergeLabel(conflict.field);
      group.appendChild(legend);
      var base = document.createElement("p");
      base.textContent = uiLabel("research_revision_merge_base") + ": " + revisionMergeValue(conflict.base);
      group.appendChild(base);
      ["current", "mine"].forEach(function(choice) {
        var label = document.createElement("label"), input = document.createElement("input");
        var title = document.createElement("span"), value = document.createElement("pre");
        input.type = "radio";
        input.name = "research-merge-" + conflict.field;
        input.value = choice;
        input.checked = merge.resolutions[conflict.field] === choice;
        title.textContent = " " + uiLabel("research_revision_merge_" + choice);
        value.textContent = revisionMergeValue(conflict[choice]);
        input.addEventListener("change", function() {
          merge.resolutions[conflict.field] = choice;
          revisionPending(false);
        });
        label.append(input, title, value);
        group.appendChild(label);
      });
      revisionMergeFields.appendChild(group);
    });
    revisionMerge.hidden = false;
    revisionPending(revisionState.pending);
  }

  async function revisionPrepareMerge(changes, resolutions, applying) {
    var session = revisionState.session;
    var reviewedCurrent = applying && revisionState.merge ? revisionState.merge.preview.current : null;
    var baseRevision = revisionState.merge ? revisionState.merge.baseRevision : revisionState.current.record.revision;
    var response = await fetch(API + "/research-record-prepare", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(researchBoundPayload(Object.assign({kind: revisionState.kind, id: revisionState.id,
        base_revision: baseRevision, changes: changes, resolutions: resolutions || {}},
        revisionState.section ? {section: revisionState.section} : {})))
    });
    var preview = await response.json();
    if (session !== revisionState.session || !researchRevisionDialog.open) return;
    // Choices belong to the exact preview shown to the author. A fresh HEAD
    // needs a new unresolved review, including when old conflicts disappeared.
    if (applying && (response.status === 400 || (response.ok && preview.ok && preview.current &&
        (!reviewedCurrent || preview.current.snapshot !== reviewedCurrent.snapshot ||
         preview.current.record.revision !== reviewedCurrent.record.revision)))) {
      await revisionPrepareMerge(changes, {}, false);
      if (session === revisionState.session && researchRevisionDialog.open) {
        revisionStatus(uiLabel("research_revision_conflict"), true);
      }
      return;
    }
    if (!response.ok || !preview.ok || !preview.current || preview.current.project_id !== revisionState.current.project_id) {
      revisionStatus(uiFormat("research_revision_load_failed", {reason: preview.message || uiLabel("wizard_unknown_error")}), true);
      return;
    }
    revisionState.merge = {baseRevision: baseRevision, draft: changes, resolutions: resolutions || {}, preview: preview};
    if (!applying || !preview.ready) {
      revisionRenderMerge();
      revisionMerge.scrollIntoView({block: "nearest"});
      return;
    }
    var reason = revisionReason.value;
    var choice = revisionForm.querySelector('input[name="research_revision_change_kind"]:checked');
    var changeKind = choice ? choice.value : "";
    if (revisionState.section) {
      var selected = await researchApiGet(revisionSectionEndpoint(preview.current.record.revision));
      if (session !== revisionState.session || !researchRevisionDialog.open) return;
      if (!selected.ok || selected.project_id !== revisionState.current.project_id) {
        revisionStatus(uiFormat("research_revision_load_failed", {reason: selected.message || uiLabel("wizard_unknown_error")}), true);
        return;
      }
      revisionState.sectionBase = preview.current.record.revision;
      revisionState.sectionContent = selected.content;
      revisionFillDraft(preview.current, {body: resolutions.body === "current" ? selected.content : changes.body}, reason, changeKind);
    } else revisionFillDraft(preview.current, preview.changes, reason, changeKind);
    revisionStatus(uiLabel(preview.has_changes ? "research_revision_merge_applied" : "research_revision_merge_no_changes"), false);
  }

  revisionMergeApply.addEventListener("click", async function() {
    if (!revisionState.merge || revisionState.pending) return;
    revisionPending(true);
    try {
      await revisionPrepareMerge(revisionState.merge.draft, revisionState.merge.resolutions, true);
    } catch (error) {
      revisionStatus(uiFormat("research_revision_load_failed", {reason: String(error)}), true);
    } finally { revisionPending(false); }
  });
  revisionFieldsHost.addEventListener("input", function() {
    revisionState.merge = null;
    revisionMerge.hidden = true;
    revisionPending(false);
  });

  function revisionUpdateQueueControls() {
    if (revisionBatchReview) {
      revisionBatchReview.hidden = Boolean(revisionState.section) || !revisionBatch.entries.length;
      revisionBatchReview.textContent = uiFormat("research_revision_batch_review", {count: revisionBatch.entries.length});
    }
    var queued = revisionBatch.entries.some(function(entry) {
      return entry.operation.kind === revisionState.kind && entry.operation.id === revisionState.id;
    });
    revisionBatchAdd.textContent = uiLabel(queued ? "research_revision_batch_replace" : "research_revision_batch_add");
  }

  function revisionBatchStatus(message, error) {
    revisionBatchStatusHost.textContent = message || "";
    revisionBatchStatusHost.hidden = !message;
    revisionBatchStatusHost.className = "ctl-status" + (error ? " err" : "");
  }

  function revisionBatchPending(pending) {
    revisionBatch.pending = pending;
    revisionBatchDialog.setAttribute("aria-busy", String(pending));
    revisionBatchDialog.querySelectorAll("button").forEach(function(button) { button.disabled = pending; });
    revisionBatchCheck.disabled = pending || !revisionBatch.entries.length;
    revisionBatchApply.disabled = pending || !revisionBatch.preview;
  }

  function revisionBatchRender() {
    revisionBatchList.replaceChildren();
    revisionBatch.entries.forEach(function(entry, index) {
      var operation = entry.operation, record = entry.envelope.record;
      var item = document.createElement("li"), heading = document.createElement("h4"), meta = document.createElement("p");
      heading.textContent = record.title || uiLabel("research_revision_kind_" + operation.kind);
      meta.className = "ctl-note";
      meta.textContent = uiLabel("research_revision_kind_" + operation.kind) + " · " +
        uiFormat("research_revision_number", {revision: operation.expected_revision}) + " · " + operation.id;
      var reason = document.createElement("p"), fields = document.createElement("dl");
      reason.textContent = uiLabel("research_revision_" + operation.change_kind) + ": " + operation.reason;
      Object.keys(operation.changes).forEach(function(name) {
        var term = document.createElement("dt"), value = document.createElement("dd");
        term.textContent = revisionMergeLabel(name, operation.kind);
        var before = document.createElement("p"), draft = document.createElement("pre");
        before.textContent = uiLabel("research_revision_merge_base") + ": " + revisionMergeValue(revisionFieldValue(record, name, true));
        draft.textContent = uiLabel("research_revision_merge_mine") + ": " + revisionMergeValue(operation.changes[name]);
        value.append(before, draft);
        fields.append(term, value);
      });
      var actions = document.createElement("div");
      actions.className = "row";
      ["edit", "remove"].forEach(function(action) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "ctl";
        button.dataset["batch" + (action === "edit" ? "Edit" : "Remove")] = String(index);
        button.textContent = uiLabel("research_revision_batch_" + action);
        actions.appendChild(button);
      });
      item.append(heading, meta, reason, fields, actions);
      revisionBatchList.appendChild(item);
    });
    revisionUpdateQueueControls();
    revisionBatchPending(revisionBatch.pending);
  }

  async function revisionBatchPrepare() {
    if (revisionBatch.pending || !revisionBatch.entries.length) return;
    var request = ++revisionBatch.request;
    revisionBatch.preview = null;
    revisionBatchPending(true);
    revisionBatchStatus(uiLabel("research_revision_batch_checking"), false);
    var preview = await researchApiPost("research-revision-batch-prepare", {
      operations: revisionBatch.entries.map(function(entry) { return entry.operation; })
    });
    if (request !== revisionBatch.request || !revisionBatchDialog.open) return;
    if (!preview.ok || !preview.ready || preview.project_id !== revisionBatch.projectId) {
      revisionBatchStatus(uiFormat("research_revision_batch_failed", {
        reason: preview.message || uiLabel(preview.project_id !== revisionBatch.projectId ? "research_revision_batch_project_changed" : "wizard_unknown_error")
      }), true);
    } else {
      revisionBatch.preview = preview;
      revisionBatchStatus(uiFormat("research_revision_batch_ready", {count: preview.operations.length}), false);
    }
    revisionBatchPending(false);
  }

  revisionBatchAdd.addEventListener("click", async function() {
    if (!revisionState.current || revisionState.pending || revisionEditBlocked() || revisionState.merge || revisionState.section) return;
    if (revisionBatch.entries.length && revisionState.current.project_id !== revisionBatch.projectId) {
      revisionStatus(uiLabel("research_revision_batch_project_changed"), true);
      return;
    }
    var operation = revisionDraft();
    if (!operation) return;
    var index = revisionBatch.entries.findIndex(function(entry) { return entry.operation.kind === operation.kind && entry.operation.id === operation.id; });
    if (index < 0 && revisionBatch.entries.length >= 100) {
      revisionStatus(uiLabel("research_revision_batch_limit"), true);
      return;
    }
    var session = revisionState.session;
    revisionPending(true);
    var preview = await researchApiPost("research-record-prepare", {kind: operation.kind, id: operation.id,
      base_revision: operation.expected_revision, changes: operation.changes});
    if (session !== revisionState.session || !researchRevisionDialog.open) return;
    if (!preview.ok || !preview.current || preview.current.project_id !== revisionState.current.project_id) {
      revisionStatus(uiFormat("research_revision_load_failed", {reason: preview.message || uiLabel("wizard_unknown_error")}), true);
    } else if (!preview.ready || preview.current.record.revision !== operation.expected_revision) {
      revisionState.merge = {baseRevision: operation.expected_revision, draft: operation.changes, resolutions: {}, preview: preview};
      revisionRenderMerge();
      revisionStatus(uiLabel("research_revision_batch_reconcile"), true);
      revisionMerge.scrollIntoView({block: "nearest"});
    } else if (!preview.has_changes) {
      revisionStatus(uiLabel("research_revision_merge_no_changes"), false);
    } else {
      operation.changes = preview.changes;
      revisionBatch.projectId = preview.current.project_id;
      var entry = {operation: operation, envelope: preview.current};
      if (index < 0) revisionBatch.entries.push(entry);
      else revisionBatch.entries[index] = entry;
      revisionBatch.preview = null;
      revisionBatch.request++;
      revisionFillDraft(preview.current, preview.changes, operation.reason, operation.change_kind);
      revisionUpdateQueueControls();
      revisionStatus(uiLabel(index < 0 ? "research_revision_batch_added" : "research_revision_batch_replaced"), false);
    }
    revisionPending(false);
  });

  if (revisionBatchReview) revisionBatchReview.addEventListener("click", function() {
    revisionBatchRender();
    revisionBatchDialog.showModal();
    revisionBatchPrepare();
  });
  revisionBatchCheck.addEventListener("click", revisionBatchPrepare);
  revisionBatchDialog.addEventListener("click", async function(event) {
    if (revisionBatch.pending) return;
    var edit = event.target.closest("[data-batch-edit]"), remove = event.target.closest("[data-batch-remove]");
    if (remove) {
      revisionBatch.entries.splice(Number(remove.dataset.batchRemove), 1);
      revisionBatch.preview = null;
      revisionBatch.request++;
      if (!revisionBatch.entries.length) revisionBatch.projectId = null;
      revisionBatchRender();
      revisionBatchStatus(revisionBatch.entries.length ? "" : uiLabel("research_revision_batch_empty"), false);
    } else if (edit) {
      var entry = revisionBatch.entries[Number(edit.dataset.batchEdit)];
      revisionBatchDialog.close();
      await revisionOpen(entry.operation.kind, entry.operation.id, "edit");
      if (!researchRevisionDialog.open || !revisionState.current) return;
      if (revisionState.current.project_id !== revisionBatch.projectId) {
        revisionStatus(uiLabel("research_revision_batch_project_changed"), true);
        return;
      }
      var latestRevision = revisionState.current.record.revision;
      revisionFillDraft(entry.envelope, entry.operation.changes, entry.operation.reason, entry.operation.change_kind);
      revisionStatus(uiLabel("research_revision_batch_restored"), false);
      if (latestRevision !== entry.operation.expected_revision) {
        revisionPending(true);
        try { await revisionPrepareMerge(entry.operation.changes, {}, false); }
        catch (error) { revisionStatus(uiFormat("research_revision_load_failed", {reason: String(error)}), true); }
        finally { revisionPending(false); }
      }
    }
  });
  document.getElementById("research-revision-batch-clear").addEventListener("click", function() {
    if (revisionBatch.pending) return;
    revisionBatch.entries = [];
    revisionBatch.projectId = null;
    revisionBatch.preview = null;
    revisionBatch.request++;
    revisionBatchRender();
    revisionBatchStatus(uiLabel("research_revision_batch_empty"), false);
  });
  revisionBatchDialog.addEventListener("close", function() { revisionBatch.request++; });
  revisionBatchDialog.addEventListener("cancel", function(event) { if (revisionBatch.pending) event.preventDefault(); });
  revisionBatchDialog.addEventListener("click", function(event) {
    if (revisionBatch.pending && (event.target === revisionBatchDialog || event.target.closest("[data-close-modal]"))) {
      event.preventDefault();
      event.stopPropagation();
    }
  }, true);

  function revisionRefreshLists() {
    refreshResearchDossiers(null, null, true);
    refreshResearchClaims();
    refreshResearchDecisions();
    if (document.querySelector('[data-rtab="review"].active')) refreshResearchEditorialReview();
  }

  revisionBatchApply.addEventListener("click", async function() {
    if (revisionBatch.pending || !revisionBatch.preview) return;
    var preview = revisionBatch.preview;
    revisionBatch.preview = null;
    revisionBatchPending(true);
    try {
      var response = await fetch(API + "/research-revision-batch-apply", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify(researchBoundPayload({operations: preview.operations, expected_snapshot: preview.snapshot}))
      });
      var result = await response.json();
      if (!response.ok || !result.ok || result.project_id !== revisionBatch.projectId) {
        revisionBatchStatus(uiFormat(response.status === 400 || response.status === 409 ? "research_revision_batch_failed" : "research_revision_batch_uncertain", {
          reason: result.message || uiLabel("wizard_unknown_error")
        }), true);
      } else {
        revisionBatch.entries = [];
        revisionBatch.projectId = null;
        revisionBatchPending(false);
        revisionBatchDialog.close();
        revisionUpdateQueueControls();
        researchStatus(uiFormat("research_revision_batch_saved", {count: result.records.length}), true);
        revisionRefreshLists();
      }
    } catch (error) {
      revisionBatchStatus(uiFormat("research_revision_batch_uncertain", {reason: String(error)}), true);
    } finally { revisionBatchPending(false); }
  });

  async function revisionOpen(kind, id, mode, section, baseRevision, historyRevision) {
    if (!revisionSpecs[kind] || !id) return;
    revisionState.session++;
    var session = revisionState.session;
    revisionState.request++;
    revisionState.historyRequest++;
    revisionState.historyListRequest++;
    revisionState.kind = kind;
    revisionState.id = id;
    revisionState.context = researchReadContext();
    var pin = Number(historyRevision);
    revisionState.historyInitialRevision = mode === "history" && Number.isInteger(pin) && pin > 0 ? pin : null;
    revisionState.historySelectionRevision = null;
    revisionState.historyView = null;
    revisionState.historyEnvelope = null;
    revisionState.section = kind === "dossier" && mode === "edit" ? section || null : null;
    revisionState.sectionBase = revisionState.section ? Number(baseRevision) || null : null;
    revisionState.sectionContent = null;
    revisionState.current = null;
    revisionState.loading = false;
    revisionState.historyLoaded = false;
    revisionState.initial = {};
    revisionState.merge = null;
    revisionMerge.hidden = true;
    revisionPending(false);
    revisionFieldsHost.replaceChildren();
    revisionHistoryList.replaceChildren();
    revisionHistoryDetail.replaceChildren();
    revisionShowMeta(null);
    document.getElementById("research-revision-technical").open = false;
    revisionVersions.open = false;
    revisionReload.hidden = true;
    revisionSave.disabled = true;
    revisionNotices(null);
    revisionShowCitations([]);
    revisionStatus(uiLabel("research_revision_loading"), false);
    revisionSetTab(mode);
    researchRevisionDialog.showModal();
    await revisionLoadCurrent(true);
    if (session === revisionState.session && researchRevisionDialog.open) {
      revisionForm.scrollTop = 0;
      revisionHistoryPane.scrollTop = 0;
      var focusTarget = mode === "edit" ? revisionFieldsHost.querySelector("input, textarea, select") : revisionHistoryTab;
      if (focusTarget) focusTarget.focus();
    }
  }

  researchRevisionDialog.addEventListener("close", function() {
    revisionState.session++;
    revisionState.request++;
    revisionState.historyRequest++;
    revisionState.historyListRequest++;
    revisionState.historyEnvelope = null;
  });
  researchRevisionDialog.addEventListener("cancel", function(event) {
    if (revisionState.pending) event.preventDefault();
  });
  researchRevisionDialog.querySelector('[role="tablist"]').addEventListener("keydown", function(event) {
    if (revisionState.pending || !event.target.matches("#research-revision-edit-tab, #research-revision-history-tab")) return;
    var tabs = [revisionHistoryTab, revisionEditTab], index = tabs.indexOf(event.target);
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") index = 1 - index;
    else if (event.key === "Home") index = 0;
    else if (event.key === "End") index = 1;
    else return;
    event.preventDefault();
    revisionSetTab(index === 0 ? "history" : "edit");
    tabs[index].focus();
  });
  researchRevisionDialog.addEventListener("click", function(event) {
    if (revisionState.pending && (event.target === researchRevisionDialog || event.target.closest("[data-close-modal]"))) {
      event.preventDefault();
      event.stopPropagation();
    }
  }, true);

  revisionVersions.addEventListener("toggle", function() {
    if (revisionVersions.open && revisionState.current && !revisionState.historyLoaded &&
        researchRevisionDialog.open && revisionContextMatches(revisionState.current)) revisionLoadHistory();
  });

  document.addEventListener("click", function(event) {
    var edit = event.target.closest("[data-research-revise]");
    var history = event.target.closest("[data-research-history]");
    if (edit || history) {
      var button = edit || history;
      revisionOpen(edit ? edit.dataset.researchRevise : history.dataset.researchHistory,
        button.dataset.recordId, edit ? "edit" : "history", button.dataset.dossierSection, button.dataset.baseRevision,
        button.dataset.recordRevision);
      return;
    }
    if (!researchRevisionDialog.open) return;
    if (event.target.closest("#research-revision-edit-tab")) revisionSetTab("edit");
    else if (event.target.closest("#research-revision-history-tab")) revisionSetTab("history");
    else if (event.target.closest("[data-research-revision]")) {
      var revision = Number(event.target.closest("[data-research-revision]").dataset.researchRevision);
      if (Number.isInteger(revision) && revision > 0) {
        revisionState.historySelectionRevision = revision;
        revisionLoadHistorical(revision);
      }
    }
    else if (event.target.closest("#research-revision-reload")) {
      revisionState.sectionBase = null;
      revisionLoadCurrent(true);
    }
  });

  revisionForm.addEventListener("submit", async function(event) {
    event.preventDefault();
    if (!revisionState.current || revisionState.pending || revisionEditBlocked() || revisionState.merge) return;
    var operation = revisionDraft();
    if (!operation) return;
    var changes = operation.changes;
    revisionPending(true);
    var session = revisionState.session;
    var t0 = performance.now();
    var reviseUrl = API + "/research-record-revise";
    try {
      var expectedSnapshot = revisionState.current.snapshot;
      if (revisionState.section) {
        var sectionPreview = await researchApiPost("research-record-prepare", {
          kind: "dossier", id: revisionState.id, base_revision: revisionState.sectionBase,
          section: revisionState.section, changes: changes
        });
        if (session !== revisionState.session || !researchRevisionDialog.open) return;
        if (!sectionPreview.ok || !sectionPreview.current || sectionPreview.current.project_id !== revisionState.current.project_id) {
          revisionStatus(uiFormat("research_revision_save_failed", {reason: sectionPreview.message || uiLabel("wizard_unknown_error")}), true);
          return;
        }
        if (!sectionPreview.ready || sectionPreview.current.record.revision !== operation.expected_revision ||
            sectionPreview.current.snapshot !== revisionState.current.snapshot) {
          revisionState.merge = {baseRevision: revisionState.sectionBase, draft: changes, resolutions: {}, preview: sectionPreview};
          revisionRenderMerge();
          revisionStatus(uiLabel("research_revision_conflict"), true);
          return;
        }
        if (!sectionPreview.has_changes) { revisionStatus(uiLabel("research_revision_no_changes"), true); return; }
        operation.changes = sectionPreview.changes;
        operation.expected_revision = sectionPreview.current.record.revision;
        expectedSnapshot = sectionPreview.current.snapshot;
      }
      var response = await fetch(reviseUrl, {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify(researchBoundPayload(Object.assign({}, operation, {expected_snapshot: expectedSnapshot})))
      });
      var data = await response.json();
      LixityLog.api("POST", reviseUrl, performance.now() - t0, response.status, data);
      if (session !== revisionState.session) return;
      if (response.status === 409) {
        revisionStatus(uiLabel("research_revision_conflict"), true);
        revisionReload.hidden = false;
        await revisionPrepareMerge(changes, {}, false);
      } else if (!response.ok || !data.ok) {
        LixityLog.error("research-record-revise failed:", data);
        revisionStatus(uiFormat("research_revision_save_failed", {reason: data.message || uiLabel("wizard_unknown_error")}), true);
      } else {
        revisionPending(false);
        researchRevisionDialog.close();
        researchStatus(uiLabel("research_revision_saved"), true);
        revisionRefreshLists();
      }
    } catch (error) {
      LixityLog.error("research-record-revise error:", error);
      if (session === revisionState.session)
        revisionStatus(uiFormat("research_revision_save_failed", {reason: String(error)}), true);
    } finally {
      if (session === revisionState.session) revisionPending(false);
    }
  });
}

if (document.getElementById("research-manager")) { initResearchUI(); }
