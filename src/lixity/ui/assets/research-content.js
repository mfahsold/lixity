// Research workspace: markdown, mermaid and dossier rendering.
// Split of the former research.js; _JS_FILES concatenates the parts in
// the original order, so load-time behaviour is unchanged.
function renderMermaidSvg(escapedCode) {
  var temp = document.createElement("textarea");
  temp.innerHTML = escapedCode;
  var code = temp.value.trim();

  try {
    var lines = code.split("\n").map(function(l) { return l.trim(); }).filter(function(l) {
      return l && !l.startsWith("%%");
    });
    if (!lines.length) return "";

    var header = lines[0].toLowerCase();

    // 1. Flowchart / Graph
    if (/^(graph|flowchart)\s+(td|tb|lr|rl)/i.test(header)) {
      var dirMatch = header.match(/^(?:graph|flowchart)\s+(td|tb|lr|rl)/i);
      var dir = dirMatch ? dirMatch[1].toUpperCase() : "TD";
      var isLR = dir === "LR" || dir === "RL";

      var nodes = {};
      var edges = [];

      function getOrCreateNode(id, label, shape) {
        if (!nodes[id]) {
          nodes[id] = { id: id, label: label || id, shape: shape || "rect" };
        } else {
          if (label) nodes[id].label = label;
          if (shape) nodes[id].shape = shape;
        }
        return nodes[id];
      }

      for (var i = 1; i < lines.length; i++) {
        var line = lines[i];

        var edgePattern = /^([a-zA-Z0-9_\-]+)(?:\[(.*?)\]|\((.*?)\)|\{(.*?)\})?\s*(-->|---|==>|-\.->)\s*(?:\|(.*?)\|)?\s*([a-zA-Z0-9_\-]+)(?:\[(.*?)\]|\((.*?)\)|\{(.*?)\})?$/;
        var m = line.match(edgePattern);
        if (m) {
          var fromId = m[1];
          var fromLabel = m[2] || m[3] || m[4];
          var fromShape = m[4] ? "diamond" : (m[3] ? "round" : "rect");
          var edgeLabel = m[6] || "";
          var toId = m[7];
          var toLabel = m[8] || m[9] || m[10];
          var toShape = m[10] ? "diamond" : (m[9] ? "round" : "rect");

          getOrCreateNode(fromId, fromLabel, fromShape);
          getOrCreateNode(toId, toLabel, toShape);
          edges.push({ from: fromId, to: toId, label: edgeLabel });
          continue;
        }

        var nodePattern = /^([a-zA-Z0-9_\-]+)(?:\[(.*?)\]|\((.*?)\)|\{(.*?)\})$/;
        var nm = line.match(nodePattern);
        if (nm) {
          var nId = nm[1];
          var nLabel = nm[2] || nm[3] || nm[4];
          var nShape = nm[4] ? "diamond" : (nm[3] ? "round" : "rect");
          getOrCreateNode(nId, nLabel, nShape);
        }
      }

      var nodeIds = Object.keys(nodes);
      if (nodeIds.length) {
        var inDegrees = {};
        var adj = {};
        nodeIds.forEach(function(id) { inDegrees[id] = 0; adj[id] = []; });
        edges.forEach(function(e) {
          if (inDegrees[e.to] !== undefined) inDegrees[e.to]++;
          if (adj[e.from]) adj[e.from].push(e.to);
        });

        var ranks = {};
        var maxRank = 0;
        var queue = [];
        nodeIds.forEach(function(id) {
          if (inDegrees[id] === 0) {
            ranks[id] = 0;
            queue.push(id);
          }
        });
        if (!queue.length && nodeIds.length) {
          ranks[nodeIds[0]] = 0;
          queue.push(nodeIds[0]);
        }

        while (queue.length) {
          var curr = queue.shift();
          var curRank = ranks[curr] || 0;
          adj[curr].forEach(function(next) {
            var nRank = (ranks[next] === undefined) ? curRank + 1 : Math.max(ranks[next], curRank + 1);
            ranks[next] = nRank;
            if (nRank > maxRank) maxRank = nRank;
            inDegrees[next]--;
            if (inDegrees[next] <= 0) queue.push(next);
          });
        }
        nodeIds.forEach(function(id) {
          if (ranks[id] === undefined) ranks[id] = 0;
        });

        var rankGroups = [];
        for (var r = 0; r <= maxRank; r++) rankGroups.push([]);
        nodeIds.forEach(function(id) {
          rankGroups[ranks[id]].push(id);
        });

        var nodePos = {};
        var padX = 25, padY = 25;
        var rankSep = isLR ? 150 : 80;
        var nodeSep = isLR ? 60 : 120;
        var totalWidth = 0, totalHeight = 0;

        rankGroups.forEach(function(group, rIdx) {
          group.forEach(function(id, idx) {
            var label = nodes[id].label;
            var w = Math.max(85, label.length * 8 + 20);
            var h = 36;
            var x, y;
            if (isLR) {
              x = padX + rIdx * rankSep;
              y = padY + idx * nodeSep;
              totalWidth = Math.max(totalWidth, x + w + padX);
              totalHeight = Math.max(totalHeight, y + h + padY);
            } else {
              x = padX + idx * nodeSep;
              y = padY + rIdx * rankSep;
              totalWidth = Math.max(totalWidth, x + w + padX);
              totalHeight = Math.max(totalHeight, y + h + padY);
            }
            nodePos[id] = { x: x, y: y, w: w, h: h };
          });
        });

        totalWidth = Math.max(totalWidth, 180);
        totalHeight = Math.max(totalHeight, 90);

        var svgParts = [
          '<div class="research-diagram-wrap"><svg class="research-diagram" viewBox="0 0 ' + totalWidth + ' ' + totalHeight + '" role="img" aria-label="Flowchart">',
          '<defs><marker id="rd-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
          '<path d="M 0 1 L 10 5 L 0 9 z" fill="var(--muted, #64748b)" /></marker></defs>'
        ];

        edges.forEach(function(e) {
          var p1 = nodePos[e.from];
          var p2 = nodePos[e.to];
          if (!p1 || !p2) return;

          var startX = isLR ? (p1.x + p1.w) : (p1.x + p1.w / 2);
          var startY = isLR ? (p1.y + p1.h / 2) : (p1.y + p1.h);
          var endX = isLR ? p2.x : (p2.x + p2.w / 2);
          var endY = isLR ? (p2.y + p2.h / 2) : p2.y;

          var midX = (startX + endX) / 2;
          var midY = (startY + endY) / 2;
          var d = 'M ' + startX + ' ' + startY + ' C ' + (isLR ? midX : startX) + ' ' + (isLR ? startY : midY) + ', ' + (isLR ? midX : endX) + ' ' + (isLR ? endY : midY) + ', ' + endX + ' ' + endY;

          svgParts.push('<path d="' + d + '" fill="none" stroke="var(--muted, #64748b)" stroke-width="1.5" marker-end="url(#rd-arrow)" />');
          if (e.label) {
            svgParts.push('<rect x="' + (midX - (e.label.length * 4)) + '" y="' + (midY - 8) + '" width="' + (e.label.length * 8) + '" height="16" fill="var(--bg, #fff)" rx="3" />');
            svgParts.push('<text x="' + midX + '" y="' + (midY + 4) + '" fill="var(--muted, #64748b)" font-size="10" text-anchor="middle">' + escapeHtml(e.label) + '</text>');
          }
        });

        nodeIds.forEach(function(id) {
          var pos = nodePos[id];
          var n = nodes[id];
          var rx = (n.shape === "round") ? "18" : (n.shape === "diamond" ? "0" : "6");
          svgParts.push('<g class="rd-node" tabindex="0" role="group" aria-label="' + escapeHtml(n.label) + '">');
          svgParts.push('<rect x="' + pos.x + '" y="' + pos.y + '" width="' + pos.w + '" height="' + pos.h + '" rx="' + rx + '" fill="var(--surface, #f8fafc)" stroke="var(--accent, #3b82f6)" stroke-width="1.5" />');
          svgParts.push('<text x="' + (pos.x + pos.w / 2) + '" y="' + (pos.y + pos.h / 2 + 4) + '" fill="var(--fg, #0f172a)" font-size="12" font-weight="500" text-anchor="middle">' + escapeHtml(n.label) + '</text>');
          svgParts.push('</g>');
        });

        svgParts.push('</svg></div>');
        return svgParts.join("");
      }
    }

    // 2. Sequence diagram
    if (/^sequencediagram/i.test(header)) {
      var participants = [];
      var pIndices = {};
      var messages = [];

      for (var s = 1; s < lines.length; s++) {
        var sline = lines[s];
        var pMatch = sline.match(/^participant\s+([a-zA-Z0-9_\-]+)(?:\s+as\s+(.*))?$/i);
        if (pMatch) {
          var pId = pMatch[1];
          var pName = pMatch[2] || pId;
          if (pIndices[pId] === undefined) {
            pIndices[pId] = participants.length;
            participants.push({ id: pId, label: pName });
          }
          continue;
        }

        var msgMatch = sline.match(/^([a-zA-Z0-9_\-]+)\s*(->>|-->>|->|-->)\s*([a-zA-Z0-9_\-]+)\s*:\s*(.*)$/);
        if (msgMatch) {
          var fromP = msgMatch[1];
          var arrType = msgMatch[2];
          var toP = msgMatch[3];
          var msgText = msgMatch[4];

          [fromP, toP].forEach(function(pid) {
            if (pIndices[pid] === undefined) {
              pIndices[pid] = participants.length;
              participants.push({ id: pid, label: pid });
            }
          });
          messages.push({ from: fromP, to: toP, text: msgText, dashed: arrType.includes("--") });
        }
      }

      if (participants.length >= 2) {
        var colWidth = 140;
        var pWidth = 100;
        var pHeight = 32;
        var sWidth = Math.max(280, participants.length * colWidth + 40);
        var msgSep = 45;
        var topY = 30;
        var sHeight = topY + (messages.length + 1) * msgSep + 30;

        var seqSvg = [
          '<div class="research-diagram-wrap"><svg class="research-diagram" viewBox="0 0 ' + sWidth + ' ' + sHeight + '" role="img" aria-label="Sequence diagram">',
          '<defs><marker id="rd-seq-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
          '<path d="M 0 1 L 10 5 L 0 9 z" fill="var(--accent, #3b82f6)" /></marker></defs>'
        ];

        participants.forEach(function(p, pIdx) {
          var centerX = 30 + pIdx * colWidth + pWidth / 2;
          seqSvg.push('<line x1="' + centerX + '" y1="' + (topY + pHeight) + '" x2="' + centerX + '" y2="' + (sHeight - 15) + '" stroke="var(--line, #e2e8f0)" stroke-dasharray="4" stroke-width="1.5" />');
          seqSvg.push('<rect x="' + (centerX - pWidth / 2) + '" y="' + topY + '" width="' + pWidth + '" height="' + pHeight + '" rx="4" fill="var(--surface, #f8fafc)" stroke="var(--accent, #3b82f6)" stroke-width="1.5" />');
          seqSvg.push('<text x="' + centerX + '" y="' + (topY + pHeight / 2 + 4) + '" fill="var(--fg, #0f172a)" font-size="12" font-weight="500" text-anchor="middle">' + escapeHtml(p.label) + '</text>');
        });

        messages.forEach(function(msg, mIdx) {
          var y = topY + pHeight + (mIdx + 1) * msgSep;
          var x1 = 30 + pIndices[msg.from] * colWidth + pWidth / 2;
          var x2 = 30 + pIndices[msg.to] * colWidth + pWidth / 2;
          var midX = (x1 + x2) / 2;
          var strokeDash = msg.dashed ? ' stroke-dasharray="4"' : '';

          seqSvg.push('<line x1="' + x1 + '" y1="' + y + '" x2="' + x2 + '" y2="' + y + '" stroke="var(--accent, #3b82f6)" stroke-width="1.5"' + strokeDash + ' marker-end="url(#rd-seq-arrow)" />');
          seqSvg.push('<text x="' + midX + '" y="' + (y - 6) + '" fill="var(--fg, #0f172a)" font-size="11" text-anchor="middle">' + escapeHtml(msg.text) + '</text>');
        });

        seqSvg.push('</svg></div>');
        return seqSvg.join("");
      }
    }
  } catch (err) {
    // Fallback on parse failure
  }

  return '<div class="research-diagram-wrap"><div class="research-diagram-note">' + escapeHtml(uiLabel("research_diagram_source")) + '</div><pre class="language-mermaid"><code>' + escapedCode.trim() + '</code></pre></div>';
}

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


