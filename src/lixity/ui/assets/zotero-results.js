// Zotero catalogue results as components on the vendored Preact + HTM stack.
//
// The first panel migrated to the component layer (docs/ARCHITECTURE.md, "UI
// stack"). DOM classes and data-* attributes stay stable: the delegated
// click handlers and the browser suites keep working unchanged, and the
// component renders only.
(function () {
  "use strict";
  var html = LixityComponents.html;

  function catalogueHref(library, key) {
    if (!/^[A-Z0-9]{8}$/.test(key || "") || !/^(users\/\d+|groups\/[1-9]\d*)$/.test(library || "")) return null;
    var prefix = library.startsWith("groups/") ? library : "library";
    return "zotero://select/" + prefix + "/items/" + key;
  }

  function CatalogueLink(props) {
    var href = catalogueHref(props.library, props.itemKey);
    if (!href) return null;
    return html`<a class="research-zotero-link" href=${href} title=${uiLabel("zotero_open")}>Zotero ↗</a>`;
  }

  function typeText(data) {
    return data.itemType === "attachment"
      ? (data.contentType || "")
      : (uiLabel("zotero_type") + ": " + (data.itemType || ""));
  }

  function ParentCard(props) {
    var parent = props.item.data || {};
    var tags = (parent.tags || []).map(function (tag) { return tag.tag; }).filter(Boolean);
    return html`<div class="research-card research-zotero-parent">
      <div class="research-card-header">
        <span class="research-card-title">${parent.title || props.item.key}</span>
        <span class="ctl-note" title=${uiLabel("zotero_type_help")}>${uiLabel("zotero_type") + ": " + (parent.itemType || "")}</span>
      </div>
      ${parent.date ? html`<div class="ctl-note">${parent.date}</div>` : null}
      ${tags.length ? html`<div class="research-tags">${tags.map(function (tag) {
        return html`<button key=${tag} type="button" class="research-tag" data-zotero-tag=${tag}
          title=${uiLabel("zotero_tag_filter")}>${tag}</button>`;
      })}</div>` : null}
      <p class="ctl-note">${uiLabel("zotero_external_note")}</p>
      <div class="row"><${CatalogueLink} library=${props.library} itemKey=${props.item.key} /></div>
    </div>`;
  }

  function ItemCard(props) {
    var data = props.item.data || {};
    var capture = props.item.capture;
    var supported = ["application/pdf", "text/plain", "text/markdown"].includes(data.contentType) &&
      ["imported_file", "imported_url", "linked_file"].includes(data.linkMode);
    var changed = capture && (capture.attachment_version !== props.item.version ||
      (props.parent && capture.item_version !== props.parent.version));
    var isAttachment = data.itemType === "attachment";
    return html`<div class="research-card">
      <div class="research-card-header">
        <span class="research-card-title">${data.title || props.item.key}</span>
        <span class="ctl-note" title=${isAttachment ? null : uiLabel("zotero_type_help")}>${typeText(data)}</span>
      </div>
      ${capture ? html`<p class="ctl-note">${uiLabel(changed ? "zotero_metadata_changed" : "zotero_linked")}</p>` : null}
      ${data.itemType === "note" ? html`<p class="ctl-note">${uiLabel("zotero_note_hint")}</p>` : null}
      <div class="row">
        ${isAttachment
          ? (supported && props.serverId
              ? html`<button type="button" class="ctl primary" data-zotero-capture=${props.index}>${uiLabel(capture ? "zotero_refresh" : "zotero_capture")}</button>`
              : html`<span class="ctl-note">${uiLabel("zotero_media")}</span>`)
          : html`<button type="button" class="ctl" data-zotero-item=${props.index}>${uiLabel("research_view_details")}</button>`}
        <${CatalogueLink} library=${props.library} itemKey=${props.item.key} />
      </div>
    </div>`;
  }

  function Results(props) {
    if (props.message) return html`<p class="ctl-note">${props.message}</p>`;
    return html`<div>
      ${props.item ? html`<${ParentCard} item=${props.item} library=${props.library} />` : null}
      ${props.items.map(function (item, index) {
        return html`<${ItemCard} key=${item.key || index} item=${item} index=${index}
          library=${props.library} parent=${props.item} serverId=${props.serverId} />`;
      })}
      ${props.item && !props.items.length
        ? html`<p class="ctl-note">${uiLabel("zotero_no_attachments")}</p>` : null}
      ${props.next
        ? html`<button type="button" class="ctl" id="r-zotero-more">${uiLabel("zotero_more")}</button>` : null}
    </div>`;
  }

  window.LixityZoteroResults = {
    render: function (host, model) {
      LixityComponents.mount(host, html`<${Results} ...${model} />`);
    },
    clear: function (host) {
      LixityComponents.unmount(host);
    },
  };
})();
