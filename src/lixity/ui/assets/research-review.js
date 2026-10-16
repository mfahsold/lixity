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
    '" data-decision-ack-snapshot="' + escapeHtml(context.snapshot) + '">' +
    (status ? '<p class="ctl-note">' + escapeHtml(status) + '</p>' : '') +
    '<p class="ctl-note">' + escapeHtml(uiLabel("research_decision_ack_help")) + '</p>' +
    '<button type="button" class="ctl" data-decision-ack-status="' + (applied ? 'review_needed' : 'applied') + '"' +
    (blocked ? ' disabled' : '') + '>' + escapeHtml(uiLabel(applied ? "research_decision_reopen_review" : "research_decision_mark_applied")) + '</button>' +
    '<p class="ctl-status" data-decision-ack-feedback role="alert" aria-live="assertive" hidden></p></div>';
}

function researchAffectedDossier(dossier, impact) {
  return '<div class="research-card"><strong>' + escapeHtml(dossier.title) + '</strong>' +
    '<p class="ctl-note">' + escapeHtml(uiFormat("research_decision_dossier_versions", {
      pinned: dossier.pinned_revisions.join(", "), current: dossier.current_revision
    })) + '</p><p class="ctl-note">' + escapeHtml(uiLabel("research_editorial_dossier_date")) + ': ' +
    researchEditorialTime(dossier.created_at) + '</p>' + researchEditorialFlags(dossier.flags, dossier.decision_after_dossier) +
    (dossier.sections.length ? '<p class="ctl-note">' + dossier.sections.map(escapeHtml).join(" · ") + '</p>' : '') +
    (!dossier.withdrawn ? researchDetailsControl("dossier", dossier.id) : '') +
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
  if (!preserve) host.textContent = uiLabel("research_loading");
  var report = await researchApiGet("research/review");
  if (request !== researchReviewRequest) return;
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
    previous.querySelector(".research-editorial-flags").replaceWith(card.querySelector(".research-editorial-flags"));
    var previousPair = previous.querySelector(".research-decision-acknowledgement");
    if (previousPair.contains(focused)) focused = pair.querySelector("[data-decision-ack-status]");
    previousPair.replaceWith(pair);
    card.replaceWith(previous);
  });
  host.replaceChildren.apply(host, Array.from(fresh.childNodes));
  if (focused && focused.isConnected && document.activeElement !== focused) focused.focus({preventScroll: true});
}

