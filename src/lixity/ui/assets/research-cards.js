// Research record cards (sources, dossiers, claims, decisions) as components.
//
// Part of the component layer documented in docs/ARCHITECTURE.md ("Stateful
// panels"). Callers build a plain item model; this file renders. DOM classes
// and data-* hooks stay identical to the previous string renderer, so the
// delegated handlers, filters and browser suites keep working.
//
// Cards are keyed through `item.key`; callers pass the serialized record for
// sources, dossiers and claims, matching the previous renderer's identity
// check: an unchanged record is patched in place, so an open details element
// and manually loaded content survive a refresh; a changed record gets a
// fresh card, dropping stale content. Decisions pass a per-refresh key
// because their impact panel loads on demand and could keep stale state.
(function () {
  "use strict";
  var html = htm.bind(preact.h);

  function CatalogueLink(props) {
    var key = props.itemKey || "";
    var library = props.library || "";
    if (!/^[A-Z0-9]{8}$/.test(key) || !/^(users\/\d+|groups\/[1-9]\d*)$/.test(library)) return null;
    var prefix = library.startsWith("groups/") ? library : "library";
    return html`<a class="research-zotero-link" href=${"zotero://select/" + prefix + "/items/" + key}
      title=${uiLabel("zotero_open")}>Zotero ↗</a>`;
  }

  function Tag(props) {
    if (props.interactive) {
      return html`<button type="button" class="research-tag" data-filter-tag=${props.value}
        title=${uiLabel("research_filter_tag")}>${props.value}</button>`;
    }
    return html`<span class="research-tag">${props.value}</span>`;
  }

  function SectionTag(props) {
    return html`<button type="button" class="research-tag research-tag-section" data-filter-tag=${props.value}
      title=${uiLabel("research_filter_tag")}>${props.value}</button>`;
  }

  function Card(props) {
    var item = props.item;
    var filterAttr = item.filterText ? {"data-filter-text": item.filterText} : {};
    return html`<div class="research-card" ...${filterAttr}>
      <div class="research-card-header">
        <span class="research-card-title">${item.title}</span>
        ${(item.badges || []).map(function (badge, index) {
          var extra = badge.title ? {title: badge.title} : {};
          return html`<span key=${"b" + index} class=${"research-badge " + badge.cls} ...${extra}>${badge.label}</span>`;
        })}
        ${(item.metaRight || []).map(function (text, index) {
          return html`<span key=${"m" + index} class="ctl-note">${text}</span>`;
        })}
      </div>
      ${item.excerpt ? html`<p class="ctl-note research-excerpt">${item.excerpt}</p>` : null}
      ${item.statementHtml
        ? html`<div class="research-claim-statement research-prose markdown-body my-2"
            dangerouslySetInnerHTML=${{__html: item.statementHtml}} />` : null}
      ${item.rationaleHtml
        ? html`<div class="research-decision-rationale research-prose markdown-body my-2"
            dangerouslySetInnerHTML=${{__html: item.rationaleHtml}} />` : null}
      ${item.impactHtml
        ? html`<div class="ctl-note my-1 text-small"><strong>${item.impactLabel}:</strong>
            <span class="research-prose markdown-body" dangerouslySetInnerHTML=${{__html: item.impactHtml}} /></div>` : null}
      ${item.scopeText ? html`<div class="ctl-note research-claim-scope">${item.scopeText}</div>` : null}
      ${item.idLine ? html`<div class="ctl-note research-record-id">${item.idLine}</div>` : null}
      ${item.dossierLine ? html`<div class="ctl-note">${item.dossierLine}</div>` : null}
      ${item.sections && item.sections.length ? html`<div class="research-dossier-sections">
        <span class="ctl-note text-note">${uiLabel("research_sections")}:</span>
        ${item.sections.map(function (section) {
          return html`<${SectionTag} key=${section} value=${section} />`;
        })}
      </div>` : null}
      ${item.tags && item.tags.length ? html`<div class="research-tags">
        ${item.tags.map(function (tag) {
          return html`<${Tag} key=${tag} value=${tag} interactive=${Boolean(item.tagsInteractive)} />`;
        })}
      </div>` : null}
      ${item.zotero ? html`<${CatalogueLink} library=${item.zotero.library} itemKey=${item.zotero.key} />` : null}
      ${item.details ? html`<details class="research-details">
        <summary data-research-detail=${item.details} data-record-id=${item.id}>${uiLabel("research_view_details")}</summary>
        <div class="research-details-body"></div>
      </details>` : null}
      ${item.decisionImpact ? html`<details class="research-details">
        <summary data-decision-impact=${item.id}>${uiLabel("research_decision_affected")}</summary>
        <div class="research-details-body"></div>
      </details>` : null}
      ${item.reader ? html`<button type="button" class="ctl" data-workspace-dossier=${item.id}>${uiLabel("reader_toggle")}</button>` : null}
      ${item.evidence ? (item.evidenceHtml
        ? html`<div class="claim-evidence-subpanel research-subpanel" id=${"claim-evidence-" + item.id}
            dangerouslySetInnerHTML=${{__html: item.evidenceHtml}}></div>`
        : html`<div class="claim-evidence-subpanel research-subpanel" id=${"claim-evidence-" + item.id}>
            <button type="button" class="ctl ctl-compact" data-load-evidence=${item.id}>${uiLabel("research_load_evidence")}</button>
          </div>`) : null}
      ${item.revision ? html`<div class="research-record-actions">
        <button type="button" class="ctl" data-research-revise=${item.revision} data-record-id=${item.id}>${uiLabel("research_revision_edit")}</button>
        <button type="button" class="ctl" data-research-history=${item.revision} data-record-id=${item.id}>${uiLabel("research_revision_history")}</button>
      </div>` : null}
    </div>`;
  }

  function ResearchList(props) {
    if (props.message) return html`<p class="ctl-note">${props.message}</p>`;
    if (props.loading) {
      return html`<div class="loading-state"><span class="loading-spinner" aria-hidden="true"></span>
        <span class="loading-text">${uiLabel("research_loading")}</span></div>`;
    }
    return html`<div>${props.items.map(function (item) {
      return html`<${Card} key=${item.key || item.id} item=${item} />`;
    })}</div>`;
  }

  window.LixityResearchCards = {
    render: function (host, model) {
      preact.render(html`<${ResearchList} ...${model} />`, host);
    },
  };
})();
