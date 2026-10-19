// Research workspace: markdown, mermaid and dossier rendering.
// Split of the former research.js; _JS_FILES concatenates the parts in
// the original order, so load-time behaviour is unchanged.
function renderMermaidSvg(escapedCode) {
  return '<figure class="research-diagram-wrap" data-research-diagram>' +
    '<div class="research-diagram-canvas" aria-busy="true"></div>' +
    '<button type="button" class="ctl" data-diagram-enlarge hidden>' + escapeHtml(uiLabel("diagram_enlarge")) + '</button>' +
    '<details class="research-diagram-source"><summary>' + escapeHtml(uiLabel("research_diagram_source")) +
    '</summary><pre class="language-mermaid"><code>' + escapedCode.trim() + '</code></pre></details></figure>';
}

// Mermaid owns syntax and layout. Render only visible diagrams, retaining their
// inert source on failure; never execute diagram click bindings or load images.
(function () {
  var sequence = 0;
  var nonce = document.currentScript && document.currentScript.nonce;
  function renderer() {
    if (window.mermaid) return window.mermaid;
    var bundled = document.getElementById("research-diagram-library");
    if (!bundled) throw new Error("Diagram library unavailable");
    var script = document.createElement("script");
    if (nonce) script.nonce = nonce;
    script.textContent = JSON.parse(bundled.textContent);
    document.head.appendChild(script);
    script.remove(); bundled.remove();
    mermaid.initialize({
    startOnLoad: false, securityLevel: "strict", suppressErrorRendering: true,
    theme: "base", themeVariables: {primaryColor: "#eef4f8", primaryBorderColor: "#35516b",
      primaryTextColor: "#1f2d3a", lineColor: "#53697b", secondaryColor: "#f8fafc",
      tertiaryColor: "#f1f5f9", clusterBkg: "#f4f7fa", clusterBorder: "#bac9d6"},
    maxTextSize: 50000, maxEdges: 500, htmlLabels: false,
    flowchart: {htmlLabels: false, useMaxWidth: true},
    secure: ["secure", "securityLevel", "startOnLoad", "maxTextSize", "maxEdges", "suppressErrorRendering", "htmlLabels", "flowchart", "theme", "themeVariables"],
    });
    return window.mermaid;
  }
  async function render(host) {
    if (host.dataset.diagramState || !host.isConnected) return;
    host.dataset.diagramState = "pending";
    var canvas = host.querySelector(".research-diagram-canvas");
    var code = host.querySelector("code").textContent;
    var header = code.split("\n").find(function(line) { return line.trim() && !/^\s*%%/.test(line); }) || "";
    var restricted = false;
    try {
      // Rendering itself creates temporary DOM. Reject resource-bearing and
      // configurable syntax before calling Mermaid, not only after its output.
      restricted = !/^(?:graph|flowchart|sequenceDiagram|classDiagram|stateDiagram(?:-v2)?|erDiagram|gantt|journey|pie|timeline|gitGraph|quadrantChart|requirementDiagram|xychart(?:-beta)?)\b/i.test(header.trim()) ||
        /%%\s*\{|@\s*\{|!\[|<(?:img|image|svg|iframe|foreignObject|script|style)\b/i.test(code) ||
        /(?:^|[;\r\n])\s*(?:classDef|style|linkStyle|click|links?)\b/i.test(code);
      if (restricted) throw new Error("Disabled diagram features");
      if (code.length > 50000) throw new Error("Diagram size limit");
      var result = await renderer().render("lixity-diagram-" + (++sequence), code);
      if (!host.isConnected) { delete host.dataset.diagramState; return; }
      var parsed = new DOMParser().parseFromString(result.svg, "image/svg+xml");
      var svg = parsed.documentElement;
      if (svg.localName !== "svg") throw new Error("Invalid diagram output");
      svg.querySelectorAll("script, foreignObject, image").forEach(function(node) { node.remove(); });
      svg.querySelectorAll("*").forEach(function(node) {
        Array.from(node.attributes).forEach(function(attribute) {
          if (/^on/i.test(attribute.name) || (/href$/i.test(attribute.name) && !attribute.value.startsWith("#")))
            node.removeAttribute(attribute.name);
        });
      });
      svg.classList.add("research-diagram");
      svg.setAttribute("role", "img");
      if (!svg.hasAttribute("aria-label") && !svg.hasAttribute("aria-labelledby")) svg.setAttribute("aria-label", uiLabel("research_diagram_source"));
      svg.querySelectorAll(".node").forEach(function(node) { node.classList.add("rd-node"); });
      canvas.replaceChildren(document.importNode(svg, true));
      host.querySelector("[data-diagram-enlarge]").hidden = false;
      host.dataset.diagramState = "ready";
    } catch (_) {
      canvas.textContent = uiLabel(restricted ? "diagram_restricted" : "diagram_failed");
      host.querySelector("details").open = true;
      host.dataset.diagramState = "failed";
    } finally { canvas.setAttribute("aria-busy", "false"); }
  }
  var visible = "IntersectionObserver" in window ? new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) { if (entry.isIntersecting) { visible.unobserve(entry.target); render(entry.target); } });
  }, {rootMargin: "150px"}) : null;
  function observe(root, removed) {
    if (!(root instanceof Element)) return;
    var hosts = root.matches("[data-research-diagram]") ? [root] : root.querySelectorAll("[data-research-diagram]");
    hosts.forEach(function(host) {
      if (removed) { if (visible) visible.unobserve(host); }
      else if (!host.dataset.diagramState) { if (visible) visible.observe(host); else render(host); }
    });
  }
  new MutationObserver(function(records) { records.forEach(function(record) {
    record.removedNodes.forEach(function(node) { observe(node, true); });
    record.addedNodes.forEach(function(node) { observe(node, false); });
  }); })
    .observe(document.body, {childList: true, subtree: true});
  observe(document.body);
  document.addEventListener("click", function(event) {
    var button = event.target.closest("[data-diagram-enlarge]");
    if (!button || !window.LixityResearchMedia) return;
    var host = button.closest("[data-research-diagram]"), svg = host.querySelector("svg");
    if (!svg) return;
    var clone = svg.cloneNode(true), box = svg.viewBox.baseVal;
    clone.setAttribute("width", Math.max(1, box.width));
    clone.setAttribute("height", Math.max(1, box.height));
    var url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], {type: "image/svg+xml"}));
    var opened = window.LixityResearchMedia.open([{src: url, width: Math.max(1, box.width), height: Math.max(1, box.height),
      alt: svg.getAttribute("aria-label") || uiLabel("diagram_enlarge"), caption: uiLabel("research_diagram_source")}], 0, button,
      function() { URL.revokeObjectURL(url); });
    if (!opened) URL.revokeObjectURL(url);
  });
})();

function renderSafeMarkdown(rawText, dossierContext) {
  if (!rawText) return "";
  var imageRender = window.LixityDossierImages && dossierContext ? window.LixityDossierImages.prepareMarkdown(rawText, dossierContext) : null;
  var text = escapeHtml(imageRender ? imageRender.text : rawText);

  var codeBlocks = [];
  text = text.replace(/```([a-zA-Z0-9_\-]*)\n([\s\S]*?)```/g, function(match, lang, code) {
    var placeholder = "@@@CODE_BLOCK_" + codeBlocks.length + "@@@";
    if (lang && lang.toLowerCase() === "mermaid") {
      codeBlocks.push(renderMermaidSvg(code));
    } else {
      codeBlocks.push('<pre><code' + (lang ? ' class="language-' + lang + '"' : '') + '>' + code.trim() + '</code></pre>');
    }
    return placeholder;
  });

  var blocks = text.split(/\n\s*\n/);
  var htmlBlocks = [];

  function parseInline(str) {
    var inlineCodes = [];
    str = str.replace(/`([^`]+)`/g, function(m, c) {
      var p = "@@@INLINE_CODE_" + inlineCodes.length + "@@@";
      inlineCodes.push('<code>' + c + '</code>');
      return p;
    });

    // Graceful Math notation
    str = str.replace(/\$\$([\s\S]+?)\$\$/g, '<div class="math-display">$1</div>');
    str = str.replace(/\$([^$\n]+?)\$/g, '<span class="math-inline">$1</span>');

    str = str.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function(m, label, url) {
      var cleanUrl = url.trim();
      if (/^lixity:/i.test(cleanUrl)) {
        return '<code class="lixity-ref" title="Internal reference: ' + cleanUrl.replace(/"/g, "&quot;") + '">' + label + ' (' + cleanUrl.replace(/^lixity:/i, "") + ')</code>';
      }
      if (/^(javascript|data|vbscript):/i.test(cleanUrl)) {
        return label + ' (' + cleanUrl + ')';
      }
      if (/^(https?:\/\/|\/|#)/i.test(cleanUrl)) {
        return '<a href="' + cleanUrl.replace(/"/g, "&quot;") + '" target="_blank" rel="noopener noreferrer nofollow">' + label + '</a>';
      }
      return label + ' (' + cleanUrl + ')';
    });

    str = str.replace(/~~(.+?)~~/g, '<del>$1</del>');
    str = str.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    str = str.replace(/___(.+?)___/g, '<strong><em>$1</em></strong>');
    str = str.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    str = str.replace(/__(.+?)__/g, '<strong>$1</strong>');
    str = str.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    str = str.replace(/_([^_]+)_/g, '<em>$1</em>');

    inlineCodes.forEach(function(codeHtml, i) {
      str = str.replace("@@@INLINE_CODE_" + i + "@@@", codeHtml);
    });

    return str;
  }

  for (var b = 0; b < blocks.length; b++) {
    var block = blocks[b].trim();
    if (!block) continue;

    if (/^@@@CODE_BLOCK_\d+@@@$/.test(block)) {
      htmlBlocks.push(block);
      continue;
    }

    var headingMatch = block.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch && !headingMatch[2].includes("\n")) {
      var level = headingMatch[1].length;
      htmlBlocks.push('<h' + level + '>' + parseInline(headingMatch[2]) + '</h' + level + '>');
      continue;
    }

    if (/^(\*{3,}|-{3,}|_{3,})$/.test(block)) {
      htmlBlocks.push('<hr>');
      continue;
    }

    var lines = block.split("\n");
    var isBlockquote = lines.every(function(l) { return /^\s*&gt;/.test(l); });
    if (isBlockquote) {
      var bqContent = lines.map(function(l) { return l.replace(/^\s*&gt;\s?/, ""); }).join("\n");
      htmlBlocks.push('<blockquote><p>' + parseInline(bqContent).replace(/\n/g, '<br>') + '</p></blockquote>');
      continue;
    }

    if (lines.length >= 2 && lines[1].includes("-") && lines[1].includes("|")) {
      var sepCells = lines[1].trim().replace(/^\||\|$/g, "").split("|");
      var isTable = sepCells.every(function(c) { return /^[\s:-]+$/.test(c) && c.includes("-"); });
      if (isTable) {
        var alignments = sepCells.map(function(c) {
          var trimmed = c.trim();
          var left = trimmed.startsWith(":");
          var right = trimmed.endsWith(":");
          if (left && right) return "center";
          if (right) return "right";
          if (left) return "left";
          return "";
        });

        var headerCells = lines[0].trim().replace(/^\||\|$/g, "").split("|");
        var thHtml = headerCells.map(function(cell, idx) {
          var align = alignments[idx] ? ' style="text-align:' + alignments[idx] + '"' : '';
          return '<th' + align + '>' + parseInline(cell.trim()) + '</th>';
        }).join("");

        var tbRowsHtml = [];
        for (var r = 2; r < lines.length; r++) {
          if (!lines[r].trim()) continue;
          var rowCells = lines[r].trim().replace(/^\||\|$/g, "").split("|");
          var tdHtml = rowCells.map(function(cell, idx) {
            var align = alignments[idx] ? ' style="text-align:' + alignments[idx] + '"' : '';
            return '<td' + align + '>' + parseInline(cell.trim()) + '</td>';
          }).join("");
          tbRowsHtml.push('<tr>' + tdHtml + '</tr>');
        }

        htmlBlocks.push('<div class="table-wrap"><table class="research-table"><thead><tr>' + thHtml + '</tr></thead><tbody>' + tbRowsHtml.join("") + '</tbody></table></div>');
        continue;
      }
    }

    var isUnordered = lines.every(function(l) { return /^\s*[-*+]\s+/.test(l); });
    var isOrdered = lines.every(function(l) { return /^\s*\d+\.\s+/.test(l); });
    if (isUnordered) {
      var liHtml = lines.map(function(l) {
        var rawContent = l.replace(/^\s*[-*+]\s+/, "");
        var isTask = false;
        var content = rawContent;
        if (/^\[\s\]\s+/.test(rawContent)) {
          content = '<input type="checkbox" disabled class="task-list-item-checkbox"> ' + parseInline(rawContent.replace(/^\[\s\]\s+/, ""));
          isTask = true;
        } else if (/^\[[xX]\]\s+/.test(rawContent)) {
          content = '<input type="checkbox" checked disabled class="task-list-item-checkbox"> ' + parseInline(rawContent.replace(/^\[[xX]\]\s+/, ""));
          isTask = true;
        } else {
          content = parseInline(rawContent);
        }
        return '<li' + (isTask ? ' class="task-list-item"' : '') + '>' + content + '</li>';
      }).join("");
      htmlBlocks.push('<ul>' + liHtml + '</ul>');
      continue;
    }
    if (isOrdered) {
      var liOrdHtml = lines.map(function(l) {
        return '<li>' + parseInline(l.replace(/^\s*\d+\.\s+/, "")) + '</li>';
      }).join("");
      htmlBlocks.push('<ol>' + liOrdHtml + '</ol>');
      continue;
    }

    htmlBlocks.push('<p>' + parseInline(lines.join("\n")).replace(/\n/g, '<br>') + '</p>');
  }

  var resultHtml = htmlBlocks.join("\n");
  codeBlocks.forEach(function(cbHtml, i) {
    resultHtml = resultHtml.replace("@@@CODE_BLOCK_" + i + "@@@", cbHtml);
  });

  return imageRender ? window.LixityDossierImages.restoreMarkdown(resultHtml, imageRender) : resultHtml;
}

function researchDossierBodyHtml(bodyText, dossierContext) {
  var escapedRaw = escapeHtml(bodyText || "");
  var rendered = renderSafeMarkdown(bodyText || "", dossierContext);
  return '<div class="research-dossier-body-wrap">' +
    '<div class="research-prose-bar">' +
      '<button type="button" class="ctl ctl-sm research-source-toggle" data-source-toggle>' + escapeHtml(uiLabel("research_show_source")) + '</button>' +
    '</div>' +
    '<div class="research-prose markdown-body research-dossier-body-rendered">' + rendered + '</div>' +
    '<pre class="research-dossier-body-source" hidden>' + escapedRaw + '</pre>' +
  '</div>';
}

function researchDossierDetailHtml(detail, readOnly) {
  var reviewAlert = "";
  if (detail.review_needed && detail.decision_reviews && detail.decision_reviews.length) {
    var needed = detail.decision_reviews.filter(function(r) { return r.status === "review_needed"; });
    if (needed.length) {
      reviewAlert = '<div class="research-warning-box">' +
        '<strong>⚠️ ' + escapeHtml(uiLabel("research_review_needed")) + ':</strong> ' +
        needed.map(function(n) { return escapeHtml(n.reason || n.title); }).join(" · ") +
        '</div>';
    }
  }
  var sections = detail.sections || [];
  if (!sections.length && detail.body) {
    var secMatches = detail.body.match(/^#{1,3}\s+(.+)$/gm);
    if (secMatches) {
      sections = secMatches.map(function(s) { return s.replace(/^#{1,3}\s+/, "").trim(); });
    }
  }
  var sectionsHtml = "";
  if (sections.length) {
    sectionsHtml = '<div class="research-dossier-outline research-dossier-outline">' +
      '<strong>' + escapeHtml(uiLabel("research_sections")) + ':</strong> ' +
      sections.map(function(sec) { return '<span class="research-tag research-tag-section ml-1">' + escapeHtml(sec) + '</span>'; }).join("") +
      '</div>';
  }
  var bodyHtml = "";
  if (detail.section_map && Object.keys(detail.section_map).length > 1) {
    var secKeys = Object.keys(detail.section_map);
    var secBlocks = secKeys.map(function(k) {
      return '<details class="research-dossier-section-block" open>' +
        '<summary><span>' + escapeHtml(k) + '</span></summary>' +
        (readOnly ? "" : researchDossierSectionAction(detail, k)) +
        '<div class="research-prose markdown-body">' + renderSafeMarkdown(detail.section_map[k], detail) + '</div>' +
      '</details>';
    }).join("");
    bodyHtml = '<div class="research-dossier-body-wrap">' +
      '<div class="research-prose-bar">' +
        '<button type="button" class="ctl ctl-sm research-source-toggle" data-source-toggle>' + escapeHtml(uiLabel("research_show_source")) + '</button>' +
      '</div>' +
      '<div class="research-dossier-body-rendered">' + secBlocks + '</div>' +
      '<pre class="research-dossier-body-source" hidden>' + escapeHtml(detail.body || "") + '</pre>' +
    '</div>';
  } else {
    bodyHtml = (readOnly ? "" : (detail.editable_sections || []).map(function(section) { return researchDossierSectionAction(detail, section); }).join("")) +
      researchDossierBodyHtml(detail.body, detail);
  }
  return reviewAlert + sectionsHtml +
    (readOnly ? "" : '<div class="row"><button type="button" class="ctl" data-dossier-claim="' + escapeHtml(detail.id) + '">' + escapeHtml(uiLabel("research_claim_heading")) + '</button>' +
    '<button type="button" class="ctl" data-dossier-decision="' + escapeHtml(detail.id) + '">' + escapeHtml(uiLabel("research_decision_heading")) + '</button></div>') +
    (!readOnly && window.LixityDossierImages ? window.LixityDossierImages.actionsHtml(detail) : "") + bodyHtml +
    (window.LixityDossierGeography ? window.LixityDossierGeography.html(detail.geography) : "") +
    (researchContextToken() ? '<section class="research-dossier-claims"><h4>' +
      escapeHtml(uiLabel("research_dossier_claims")) + '</h4><p class="ctl-note">' +
      escapeHtml(uiLabel("research_loading")) + '</p></section>' : '') +
    '<h4>' + escapeHtml(uiLabel("research_citations")) + '</h4>' + (detail.citations || []).map(function(citation) {
      return researchCitationHtml(citation, !readOnly);
    }).join("");
}

// This reverse list projects current Claim.dossier_ref associations and
// counts explicitly retained links against their pinned dossier association.
// It never infers unwritten prose use or reconstructs historical dossier claims.
async function enhanceResearchDossierClaims(host, detail, stillCurrent) {
  var slot = host.querySelector(".research-dossier-claims");
  if (!slot || !researchContextToken() || !detail.id || !detail.project_id) return;
  var context = researchReadContext();
  var serial = slot._claimsRead = (slot._claimsRead || 0) + 1;
  function current() {
    return slot.isConnected && host.contains(slot) && serial === slot._claimsRead &&
      context.token === researchContextToken() &&
      (!researchSelectionProjectId || researchSelectionProjectId === detail.project_id) &&
      (!stillCurrent || stillCurrent());
  }
  slot.setAttribute("aria-busy", "true");
  var results = await Promise.all([
    researchApiGet("research/claims?dossier_id=" + encodeURIComponent(detail.id)),
    researchApiGet("research/manuscript-links")
  ]);
  var data = results[0], manuscriptLinks = results[1];
  if (!current()) return;
  slot.setAttribute("aria-busy", "false");
  var heading = '<h4>' + escapeHtml(uiLabel("research_dossier_claims")) + '</h4>';
  if (!data.ok || data.project_id !== detail.project_id || !Array.isArray(data.claims)) {
    slot.innerHTML = heading + '<p class="ctl-note" role="status">' +
      escapeHtml(data.message || uiLabel("research_load_claims_failed")) + '</p>' +
      '<button type="button" class="ctl ctl-sm">' + escapeHtml(uiLabel("research_dossier_claims_retry")) + '</button>';
    slot.querySelector("button").addEventListener("click", function() {
      enhanceResearchDossierClaims(host, detail, stillCurrent);
    });
    return;
  }
  // The API filters the stored reference; reject unrelated rows defensively.
  var claims = data.claims.filter(function(claim) { return claim.dossier_id === detail.id; });
  var linksAvailable = manuscriptLinks.ok && manuscriptLinks.project_id === detail.project_id &&
    manuscriptLinks.snapshot === data.snapshot && Array.isArray(manuscriptLinks.links);
  slot.innerHTML = heading + '<p class="ctl-note">' + escapeHtml(uiLabel("research_dossier_claims_hint")) + '</p>' +
    (claims.length ? '<ul class="research-dossier-claims-list">' + claims.map(function(claim) {
      var confidence = ["evidenced", "disputed"].includes(claim.confidence) ? claim.confidence : "hypothetical";
      var badge = confidence === "evidenced" ? "badge-success" : confidence === "disputed" ? "badge-warning" : "badge-neutral";
      var linked = linksAvailable ? manuscriptLinks.links.filter(function(link) {
        return link.state === "active" && link.claim_id === claim.id && link.dossier_id === detail.id;
      }) : [];
      var usage = linksAvailable ? '<p class="ctl-note" data-manuscript-link-count="' + linked.length + '">' +
        escapeHtml(linked.length ? uiCountFormat("research_manuscript_quote_count", linked.length) :
          uiLabel("research_manuscript_quote_none")) + '</p>' :
        '<p class="ctl-note">' + escapeHtml(uiLabel("research_manuscript_quote_unavailable")) + '</p>';
      if (linked.some(function(link) { return link.claim_changed || link.claim_withdrawn; }))
        usage += '<p class="ctl-note">' + escapeHtml(uiLabel("research_manuscript_quote_review")) + '</p>';
      if (linked.some(function(link) { return link.dossier_revision !== detail.revision; }))
        usage += '<p class="ctl-note" data-dossier-version-review>' + escapeHtml(uiLabel("research_manuscript_quote_dossier_version")) + '</p>';
      return '<li><strong>' + escapeHtml(claim.title || uiLabel("research_revision_kind_claim")) + '</strong>' +
        '<div class="row"><span class="research-badge ' + badge + '">' +
        escapeHtml(uiLabel("research_confidence_" + confidence)) + '</span>' +
        '<span class="ctl-note" data-claim-revision="' + Number(claim.revision) + '">' +
        escapeHtml(uiFormat("research_revision_number", {revision: claim.revision})) + '</span>' +
        '<button type="button" class="ctl ctl-sm" data-research-history="claim" data-record-id="' +
        escapeHtml(claim.id) + '">' + escapeHtml(uiLabel("research_claim_open")) + '</button></div>' + usage +
        '<details><summary>' + escapeHtml(uiLabel("research_revision_technical")) + '</summary>' +
        '<code class="research-record-id">' + escapeHtml(claim.id) + '</code></details></li>';
    }).join("") + '</ul>' : '<p class="ctl-note">' + escapeHtml(uiLabel("research_dossier_claims_empty")) + '</p>');
}

function researchDossierSectionAction(detail, section) {
  if (!(detail.editable_sections || []).includes(section)) return "";
  return '<div class="row"><button type="button" class="ctl ctl-sm" data-research-revise="dossier" data-record-id="' +
    escapeHtml(detail.id) + '" data-dossier-section="' + escapeHtml(section).replace(/"/g, "&quot;") +
    '" data-base-revision="' + Number(detail.revision) + '">' + escapeHtml(uiLabel("research_section_edit")) + '</button></div>';
}

document.addEventListener("lixity:dossier-image-saved", async function(event) {
  var accepted = event.detail;
  if (!accepted || !accepted.record) return;
  var previousFocus = document.activeElement;
  var restoreFocus = previousFocus === document.body ||
    previousFocus && previousFocus.dataset.dossierAddImage === accepted.record.id;
  function movedFocus(event) {
    if (event.target !== previousFocus && event.target !== document.body) restoreFocus = false;
  }
  function movedPointer(event) {
    if (previousFocus === document.body || !previousFocus.contains(event.target)) restoreFocus = false;
  }
  document.addEventListener("focusin", movedFocus);
  document.addEventListener("pointerdown", movedPointer);
  try {
  // These list refreshes preserve form values, filter input and selected IDs.
  // The shared revision editor keeps its independent unsaved drafts.
  await Promise.all([refreshResearchSources(null, accepted.capture && accepted.capture.source_id, true),
    refreshResearchDossiers(null, accepted.record.id, true), refreshResearchProjectInfo()]);
  var detail = await researchApiGet("research/dossiers?id=" + encodeURIComponent(accepted.record.id));
  if (!detail.ok || detail.project_id !== accepted.project_id) return;
  var summary = Array.from(document.querySelectorAll('[data-research-detail="dossier"]')).find(function(button) {
    return button.dataset.recordId === accepted.record.id;
  });
  if (!summary) return;
  summary.parentElement.open = true;
  var host = summary.parentElement.querySelector(".research-details-body");
  host.innerHTML = researchDossierDetailHtml(detail);
  enhanceResearchDossierClaims(host, detail, function() { return summary.parentElement.open; });
  var add = host.querySelector("[data-dossier-add-image]");
  if (add && restoreFocus && (document.activeElement === previousFocus || document.activeElement === document.body)) add.focus();
  researchStatus(uiLabel("image_saved"), true);
  } finally {
    document.removeEventListener("focusin", movedFocus);
    document.removeEventListener("pointerdown", movedPointer);
  }
});


