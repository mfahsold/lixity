// Research workspace: editorial review and decision acknowledgements.
// Split of the former research.js; _JS_FILES concatenates the parts in
// the original order, so load-time behaviour is unchanged.
function researchEditorialFlags(flags, decisionAfterDossier) {
  var after = decisionAfterDossier === undefined ? (flags || []).includes("decision_after_dossier") : decisionAfterDossier;
  return '<ul class="research-editorial-flags" data-decision-after-dossier="' + (after ? '1' : '0') + '">' + (flags || []).map(function(flag) {
    return '<li data-editorial-flag="' + escapeHtml(flag) + '">' + escapeHtml(uiLabel("research_editorial_" + flag)) + '</li>';
  }).join("") + '</ul>';
}

function acknowledgeEditorialFlags(pair, status) {
  var card = pair.closest(".research-card");
  var flags = card && card.querySelector(".research-editorial-flags");
  if (!flags) return;
  var names = Array.from(flags.querySelectorAll("[data-editorial-flag]")).map(function(item) {
    return item.dataset.editorialFlag;
  }).filter(function(name) {
    return !["decision_after_dossier", "author_review_needed", "stale_author_acknowledgement"].includes(name);
  });
  var after = flags.dataset.decisionAfterDossier === "1";
  if (status === "review_needed") {
    if (after) names.push("decision_after_dossier");
    names.push("author_review_needed");
  }
  var replacement = document.createElement("div");
  replacement.innerHTML = researchEditorialFlags(names, after);
  flags.replaceWith(replacement.firstElementChild);
}

function researchEditorialTime(timestamp) {
  return '<time datetime="' + escapeHtml(timestamp) + '">' +
    escapeHtml(new Date(timestamp).toLocaleString(document.documentElement.lang || "en", {timeZone: "UTC"})) + ' UTC</time>';
}

function researchDecisionAcknowledgement(context) {
  if (!context.dossierId || !context.snapshot || !Number.isInteger(context.decisionRevision) ||
      !Number.isInteger(context.dossierRevision)) return "";
  var ack = context.acknowledgement;
  var applied = Boolean(ack && ack.current === true && ack.status === "applied");
  var status = ack ? uiLabel(ack.current === true ?
    (applied ? "research_decision_applied" : "research_decision_review_needed") :
    "research_decision_earlier_assessment") : "";
  var blocked = (context.flags || []).includes("withdrawn_dossier");
  return '<div class="research-decision-acknowledgement" data-decision-ack-dossier="' + escapeHtml(context.dossierId) +
    '" data-decision-ack-decision="' + escapeHtml(context.decisionId) +
    '" data-decision-ack-decision-revision="' + context.decisionRevision +
    '" data-decision-ack-dossier-revision="' + context.dossierRevision +
    '" data-decision-ack-snapshot="' + escapeHtml(context.snapshot) +
    '" data-decision-ack-project="' + escapeHtml(researchSelectionProjectId) +
    '" data-decision-ack-token="' + escapeHtml(researchContextToken()) + '">' +
    (status ? '<p class="ctl-note">' + escapeHtml(status) + '</p>' : '') +
    '<p class="ctl-note">' + escapeHtml(uiLabel("research_decision_ack_help")) + '</p>' +
    '<button type="button" class="ctl" data-decision-ack-status="' + (applied ? 'review_needed' : 'applied') + '"' +
    (blocked ? ' disabled' : '') + '>' + escapeHtml(uiLabel(applied ? "research_decision_reopen_review" : "research_decision_mark_applied")) + '</button>' +
    '<p class="ctl-status" data-decision-ack-feedback role="alert" aria-live="assertive" hidden></p></div>';
}

function researchDecisionComparison(context) {
  if (!context.dossierId || !context.snapshot || !Number.isInteger(context.decisionRevision) ||
      !Number.isInteger(context.dossierRevision) || (context.flags || []).includes("withdrawn_dossier")) return "";
  var ack = context.acknowledgement || {};
  return '<details class="research-decision-review" data-decision-review' +
    ' data-review-decision="' + escapeHtml(context.decisionId) + '" data-review-dossier="' + escapeHtml(context.dossierId) +
    '" data-review-decision-revision="' + context.decisionRevision + '" data-review-dossier-revision="' + context.dossierRevision +
    '" data-review-snapshot="' + escapeHtml(context.snapshot) + '" data-review-project="' + escapeHtml(researchSelectionProjectId) +
    '" data-review-token="' + escapeHtml(researchContextToken()) + '" data-review-ack-decision="' + (ack.decision_revision || "") +
    '" data-review-ack-dossier="' + (ack.dossier_revision || "") + '">' +
    '<summary>' + escapeHtml(uiLabel("research_decision_compare")) + '</summary>' +
    '<div data-decision-review-body aria-live="polite"></div>' +
    '<button type="button" class="ctl ctl-compact" data-decision-review-close>' +
    escapeHtml(uiLabel("research_decision_review_close")) + '</button></details>';
}

function researchDecisionComparisonContext(disclosure) {
  return {projectId: disclosure.dataset.reviewProject || null, token: disclosure.dataset.reviewToken};
}

function researchDecisionComparisonAssessment(disclosure) {
  var decision = Number(disclosure.dataset.reviewAckDecision), dossier = Number(disclosure.dataset.reviewAckDossier);
  return decision && dossier ? uiFormat("research_decision_review_assessment", {decision: decision, dossier: dossier}) :
    uiLabel("research_decision_review_no_assessment");
}

function researchDecisionComparisonError(disclosure, message) {
  var body = disclosure.querySelector("[data-decision-review-body]");
  disclosure._decisionReviewLoaded = false;
  body.removeAttribute("aria-busy");
  body.innerHTML = '<p class="ctl-status err" role="status">' + escapeHtml(message) + '</p>' +
    '<button type="button" class="ctl ctl-compact" data-decision-review-retry>' +
    escapeHtml(uiLabel("research_decision_review_retry")) + '</button>';
}

function researchDecisionComparisonHistory(kind, id, revision) {
  return '<button type="button" class="ctl ctl-compact" data-research-history="' + kind + '" data-record-id="' +
    escapeHtml(id) + '" data-record-revision="' + revision + '">' + escapeHtml(uiLabel("research_revision_history")) + '</button>';
}

async function loadResearchDecisionComparison(disclosure) {
  if (!disclosure.open) return;
  var context = researchDecisionComparisonContext(disclosure);
  if (!acceptResearchContext(context, {})) {
    researchDecisionComparisonError(disclosure, uiLabel("research_decision_ack_conflict"));
    return;
  }
  if (disclosure._decisionReviewLoaded || disclosure._decisionReviewPending) return;
  var request = disclosure._decisionReviewRequest = (disclosure._decisionReviewRequest || 0) + 1;
  var snapshot = disclosure.dataset.reviewSnapshot;
  var specs = [{kind: "decision", id: disclosure.dataset.reviewDecision, revision: Number(disclosure.dataset.reviewDecisionRevision)},
    {kind: "dossier", id: disclosure.dataset.reviewDossier, revision: Number(disclosure.dataset.reviewDossierRevision)}];
  var acknowledgedRevision = Number(disclosure.dataset.reviewAckDossier);
  if (acknowledgedRevision && acknowledgedRevision !== specs[1].revision)
    specs.push({kind: "dossier", id: specs[1].id, revision: acknowledgedRevision});
  var body = disclosure.querySelector("[data-decision-review-body]");
  disclosure._decisionReviewPending = true;
  body.textContent = uiLabel("research_revision_loading");
  body.setAttribute("aria-busy", "true");
  var records = await Promise.all(specs.map(function(spec) {
    return researchApiGet("research/record?kind=" + spec.kind + "&id=" + encodeURIComponent(spec.id) + "&revision=" + spec.revision);
  }));
  if (request !== disclosure._decisionReviewRequest || !disclosure.isConnected || !disclosure.open) return;
  disclosure._decisionReviewPending = false;
  if (snapshot !== disclosure.dataset.reviewSnapshot || !acceptResearchContext(context, {})) {
    researchDecisionComparisonError(disclosure, uiLabel("research_decision_ack_conflict"));
    return;
  }
  var invalid = records.findIndex(function(data, index) {
    var spec = specs[index], record = data.record;
    return !data.ok || data.schema_version !== "research-record-local/1" || !acceptResearchContext(context, data) ||
      data.project_id !== context.projectId || data.snapshot !== snapshot || data.kind !== spec.kind ||
      data.record_id !== spec.id || !record || record.kind !== spec.kind || record.id !== spec.id || record.project_id !== context.projectId ||
      record.revision !== spec.revision || typeof record.title !== "string" ||
      (spec.kind === "decision" ? typeof record.rationale !== "string" ||
        (record.impact_on_plot !== null && typeof record.impact_on_plot !== "string") :
        typeof record.body !== "string") || data.latest_revision !== (spec.kind === "decision" ? specs[0].revision : specs[1].revision);
  });
  if (invalid !== -1) {
    var failed = records[invalid];
    researchDecisionComparisonError(disclosure, failed.ok ? uiLabel("research_decision_ack_conflict") :
      uiFormat("research_decision_review_failed", {reason: failed.message || uiLabel("research_status_unavailable")}));
    return;
  }
  var decision = records[0].record, dossier = records[1].record;
  body.removeAttribute("aria-busy");
  body.innerHTML = '<p class="ctl-note">' + escapeHtml(uiLabel("research_decision_review_scope")) + '</p>' +
    '<p class="ctl-note" data-decision-review-assessment>' + escapeHtml(researchDecisionComparisonAssessment(disclosure)) + '</p>' +
    '<div class="research-decision-review-grid"><section data-decision-review-latest="decision">' +
    '<h4>' + escapeHtml(uiFormat("research_decision_review_latest_decision", {revision: decision.revision})) + '</h4>' +
    '<p class="research-decision-review-title">' + escapeHtml(decision.title) + '</p>' +
    '<div class="research-prose markdown-body">' + renderSafeMarkdown(decision.rationale) + '</div>' +
    (decision.impact_on_plot ? '<p class="ctl-note">' + escapeHtml(uiLabel("research_decision_plot")) + '</p>' +
      '<div class="research-prose markdown-body">' + renderSafeMarkdown(decision.impact_on_plot) + '</div>' : '') +
    (decision.deviation_from_fact ? '<p class="ctl-note">' + escapeHtml(uiLabel("research_deviation_checkbox")) + '</p>' : '') +
    researchDecisionComparisonHistory("decision", decision.id, decision.revision) +
    '</section><section data-decision-review-latest="dossier"><h4>' +
    escapeHtml(uiFormat("research_decision_review_latest_dossier", {revision: dossier.revision})) + '</h4>' +
    '<p class="research-decision-review-title">' + escapeHtml(dossier.title) + '</p>' +
    researchDossierBodyHtml(dossier.body, records[1]) + researchDecisionComparisonHistory("dossier", dossier.id, dossier.revision) +
    (records[2] ? '<details class="research-decision-review-earlier" data-decision-review-earlier open><summary>' +
      escapeHtml(uiFormat("research_decision_review_earlier_dossier", {revision: acknowledgedRevision})) + '</summary>' +
      '<p class="research-decision-review-title">' + escapeHtml(records[2].record.title) + '</p>' +
      researchDossierBodyHtml(records[2].record.body, records[2]) +
      researchDecisionComparisonHistory("dossier", dossier.id, acknowledgedRevision) + '</details>' : '') + '</section></div>';
  disclosure._decisionReviewLoaded = true;
}

function updateResearchDecisionComparison(comparison, snapshot, decisionRevision, dossierRevision) {
  comparison.dataset.reviewSnapshot = snapshot;
  comparison.dataset.reviewAckDecision = decisionRevision;
  comparison.dataset.reviewAckDossier = dossierRevision;
  var assessment = comparison.querySelector("[data-decision-review-assessment]");
  if (assessment) assessment.textContent = researchDecisionComparisonAssessment(comparison);
  var earlier = comparison.querySelector("[data-decision-review-earlier]");
  if (earlier && comparison.dataset.reviewAckDossier === comparison.dataset.reviewDossierRevision) earlier.remove();
  if (comparison._decisionReviewPending) {
    ++comparison._decisionReviewRequest;
    comparison._decisionReviewPending = false;
    researchDecisionComparisonError(comparison, uiLabel("research_decision_ack_conflict"));
  }
}

function advanceResearchDecisionComparisons(payload, acknowledged) {
  document.querySelectorAll("[data-decision-review]").forEach(function(comparison) {
    if (comparison.dataset.reviewSnapshot !== payload.expected_snapshot ||
        !acceptResearchContext(researchDecisionComparisonContext(comparison), acknowledged)) return;
    var matching = comparison.dataset.reviewDecision === payload.decision_id && comparison.dataset.reviewDossier === payload.dossier_id &&
      Number(comparison.dataset.reviewDecisionRevision) === payload.expected_decision_revision &&
      Number(comparison.dataset.reviewDossierRevision) === payload.expected_dossier_revision;
    updateResearchDecisionComparison(comparison, acknowledged.snapshot,
      matching ? String(payload.expected_decision_revision) : comparison.dataset.reviewAckDecision,
      matching ? String(payload.expected_dossier_revision) : comparison.dataset.reviewAckDossier);
  });
}

function researchAffectedDossier(dossier, impact) {
  return '<div class="research-card"><strong>' + escapeHtml(dossier.title) + '</strong>' +
    '<p class="ctl-note">' + escapeHtml(uiFormat("research_decision_dossier_versions", {
      pinned: dossier.pinned_revisions.join(", "), current: dossier.current_revision
    })) + '</p><p class="ctl-note">' + escapeHtml(uiLabel("research_editorial_dossier_date")) + ': ' +
    researchEditorialTime(dossier.created_at) + '</p>' + researchEditorialFlags(dossier.flags, dossier.decision_after_dossier) +
    (dossier.sections.length ? '<p class="ctl-note">' + dossier.sections.map(escapeHtml).join(" · ") + '</p>' : '') +
    (!dossier.withdrawn ? researchDetailsControl("dossier", dossier.id) : '') +
    researchDecisionComparison({decisionId: impact.decision.id, decisionRevision: impact.decision.revision,
      dossierId: dossier.id, dossierRevision: dossier.current_revision, snapshot: impact.snapshot,
      acknowledgement: dossier.acknowledgement, flags: dossier.flags}) +
    researchDecisionAcknowledgement({decisionId: impact.decision.id, decisionRevision: impact.decision.revision,
      dossierId: dossier.id, dossierRevision: dossier.current_revision, snapshot: impact.snapshot,
      acknowledgement: dossier.acknowledgement, flags: dossier.flags}) + '</div>';
}

var researchReviewRequest = 0;
var researchAcknowledgementPending = false;
async function refreshResearchEditorialReview(preserve, expectedSnapshot) {
  var host = document.getElementById("research-editorial-review");
  if (!host) return;
  var request = ++researchReviewRequest;
  var context = researchReadContext();
  if (!preserve) host.textContent = uiLabel("research_loading");
  var report = await researchApiGet("research/review");
  if (request !== researchReviewRequest || !acceptResearchContext(context, report)) return;
  if (preserve && report.ok && report.snapshot !== expectedSnapshot) {
    researchStatus(uiLabel("research_decision_ack_conflict"), false);
    return;
  }
  if (preserve && !report.ok) {
    researchStatus(report.message || uiLabel("research_status_unavailable"), false);
    return;
  }
  if (!report.ok) {
    host.textContent = report.message || uiLabel("research_status_unavailable");
    return;
  }
  if (report.schema_version !== "research-editorial-review-local/1" || !Array.isArray(report.candidates)) {
    host.textContent = report.message || uiLabel("research_status_unavailable");
    return;
  }
  if (!report.candidates.length) {
    host.textContent = uiLabel("research_editorial_empty");
    return;
  }
  var rendered = '<p class="ctl-note">' + escapeHtml(uiCountFormat("research_editorial_count", report.candidate_count)) + '</p>' +
    report.candidates.map(function(candidate) {
      return '<div class="research-card"><strong>' + escapeHtml(candidate.title) + '</strong>' +
        (candidate.dossier_title ? '<p>' + escapeHtml(candidate.dossier_title) + '</p>' : '') +
        '<p class="ctl-note">' + escapeHtml(uiFormat("research_revision_number", {revision: candidate.decision_revision})) + ' · ' +
        escapeHtml(uiLabel("research_editorial_decision_date")) + ': ' + researchEditorialTime(candidate.decision_created_at) + '</p>' +
        (candidate.dossier_created_at ? '<p class="ctl-note">' + escapeHtml(uiLabel("research_editorial_dossier_date")) + ': ' +
          researchEditorialTime(candidate.dossier_created_at) + '</p>' : '') +
        researchEditorialFlags(candidate.flags, candidate.decision_created_at > candidate.dossier_created_at) +
        (candidate.dossier_id ? '<p class="ctl-note">' + escapeHtml(uiFormat("research_decision_dossier_versions", {
          pinned: candidate.pinned_revisions.join(", "), current: candidate.current_revision
        })) + '</p>' : '') +
        (candidate.sections.length ? '<p class="ctl-note">' + candidate.sections.map(escapeHtml).join(" · ") + '</p>' : '') +
        (candidate.dossier_id && !candidate.flags.includes("withdrawn_dossier") ? researchDetailsControl("dossier", candidate.dossier_id) : '') +
        researchRevisionActions("decision", candidate.decision_id) +
        researchDecisionComparison({decisionId: candidate.decision_id, decisionRevision: candidate.decision_revision,
          dossierId: candidate.dossier_id, dossierRevision: candidate.current_revision, snapshot: report.snapshot,
          acknowledgement: candidate.acknowledgement, flags: candidate.flags}) +
        researchDecisionAcknowledgement({decisionId: candidate.decision_id, decisionRevision: candidate.decision_revision,
          dossierId: candidate.dossier_id, dossierRevision: candidate.current_revision, snapshot: report.snapshot,
          acknowledgement: candidate.acknowledgement, flags: candidate.flags}) + '</div>';
    }).join("");
  if (!preserve) { host.innerHTML = rendered; return; }
  var focused = document.activeElement;
  var fresh = document.createElement("div");
  fresh.innerHTML = rendered;
  var retained = new Map();
  host.querySelectorAll(".research-card").forEach(function(card) {
    var pair = card.querySelector(".research-decision-acknowledgement");
    if (pair) retained.set(pair.dataset.decisionAckDecision + ":" + pair.dataset.decisionAckDossier, card);
  });
  fresh.querySelectorAll(".research-card").forEach(function(card) {
    var pair = card.querySelector(".research-decision-acknowledgement");
    var previous = pair && retained.get(pair.dataset.decisionAckDecision + ":" + pair.dataset.decisionAckDossier);
    if (!previous) return;
    var previousPair = previous.querySelector(".research-decision-acknowledgement");
    if (previousPair.dataset.decisionAckDecisionRevision !== pair.dataset.decisionAckDecisionRevision ||
        previousPair.dataset.decisionAckDossierRevision !== pair.dataset.decisionAckDossierRevision ||
        previousPair.dataset.decisionAckProject !== pair.dataset.decisionAckProject ||
        previousPair.dataset.decisionAckToken !== pair.dataset.decisionAckToken) return;
    previous.querySelector(".research-editorial-flags").replaceWith(card.querySelector(".research-editorial-flags"));
    if (previousPair.contains(focused)) focused = pair.querySelector("[data-decision-ack-status]");
    previousPair.replaceWith(pair);
    card.replaceWith(previous);
  });
  host.replaceChildren.apply(host, Array.from(fresh.childNodes));
  if (focused && focused.isConnected && document.activeElement !== focused) focused.focus({preventScroll: true});
}

