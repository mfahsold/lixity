// The scene report stays in manuscript order. A rehearsal only moves saved intent cards.
(() => {
  "use strict";
  const board = document.getElementById("scene-rehearsal");
  if (!board || window.LixitySite.readOnly) return;
  const components = window.LixityComponents;
  const {setStatus, jsonApi} = components;
  const label = window.LixityComponents.scopedLabel("scene_intent_");
  const list = document.getElementById("scene-intent-order");
  const template = document.getElementById("scene-intent-card");
  const form = document.getElementById("scene-intent-form");
  const fields = form.querySelector("fieldset");
  const editor = document.getElementById("scene-intent-editor");
  const orderActions = document.getElementById("scene-rehearsal-order-actions");
  const empty = document.getElementById("scene-rehearsal-empty");
  const reload = board.querySelector('[data-intent-action="load"]');
  const sceneLinks = new Map(Array.from(document.querySelectorAll(".scene-overview [data-scene-row]"), row => [
    row.dataset.sceneRow, row.querySelector("a[data-jump]").getAttribute("href")
  ]));
  let state = null;
  let pending = false;
  let order = [];
  let editing = null;
  const status = (message, type) => setStatus("scene-rehearsal-status", message, type);
  const token = () => document.getElementById("scene-intents-token").value;
  const isDraftOrder = () => state && order.some((id, index) => id !== state.cards[index].id);

  function render() {
    fields.disabled = pending || !state;
    const dirty = isDraftOrder();
    empty.hidden = !state || state.cards.length > 0;
    orderActions.hidden = !dirty;
    orderActions.querySelectorAll("button").forEach(button => { button.disabled = pending; });
    const cards = new Map(state ? state.cards.map(card => [card.id, card]) : []);
    list.replaceChildren(...order.map((id, index) => {
      const card = cards.get(id);
      const node = template.content.firstElementChild.cloneNode(true);
      node.dataset.intentId = id;
      function field(key, text) {
        const el = node.querySelector('[data-intent-field="' + key + '"]');
        el.textContent = text;
        el.hidden = !text;
      }
      const stale = card.review_status === "stale";
      field("kind", label(card.kind));
      field("status", label(card.review_status));
      field("intent", card.intent);
      field("voice", card.voice && uiFormat("scene_intent_voice_value", {value: card.voice}));
      field("hypothesis", card.hypothesis && uiFormat("scene_intent_hypothesis_value", {value: card.hypothesis}));
      field("scene", card.scene_title);
      const link = node.querySelector('[data-intent-field="scene-link"]');
      const target = !stale && card.scene_available && sceneLinks.get(card.scene_id);
      link.hidden = !target;
      if (target) {
        link.href = target;
        link.dataset.jump = target;
      }
      const disabled = {up: index === 0, down: index === order.length - 1};
      node.querySelectorAll("button").forEach(button => {
        button.disabled = pending || Boolean(disabled[button.dataset.intentAction]);
      });
      return node;
    }));
  }

  function accept(data, requestedToken, keepDraft) {
    if (!data.ok || data.schema_version !== "lixity-analysis-intents/1" || !Array.isArray(data.cards) ||
        requestedToken !== token() || data.source_sha256 !== document.body.dataset.manuscriptSourceSha256) {
      reload.hidden = false;
      status(label(data.http_status === 409 || data.ok ? "conflict" : "unavailable"), "err");
      return false;
    }
    const ids = data.cards.map(card => card.id);
    order = keepDraft
      ? order.filter(id => ids.includes(id)).concat(ids.filter(id => !order.includes(id)))
      : ids.slice();
    state = data;
    reload.hidden = true;
    return true;
  }

  async function load() {
    if (pending) return;
    pending = true;
    render();
    const selected = token();
    status(uiLabel("editor_loading"), "loading");
    const data = await jsonApi(API + "/analysis-intents?project_token=" + encodeURIComponent(selected));
    pending = false;
    if (accept(data, selected, Boolean(isDraftOrder()))) status("");
    render();
  }

  async function save(fields) {
    if (pending || !state) return false;
    const keepDraft = fields.action !== "save_order" && Boolean(isDraftOrder());
    const selected = token();
    pending = true;
    render();
    status(uiLabel("form_saving"), "loading");
    const data = await components.postJson(API + "/analysis-intents", {
      ...fields,
      project_token: selected,
      expected_source_sha256: state.source_sha256,
      expected_analysis_sha256: state.analysis_sha256,
      expected_intents_sha256: state.intents_sha256
    });
    pending = false;
    const ok = accept(data, selected, keepDraft);
    if (ok) status(label(fields.action === "save_order" ? "order_saved" : "saved"), "ok");
    render();
    return ok;
  }

  function edit(card) {
    editing = card ? card.id : null;
    const inputs = form.elements;
    inputs.namedItem("kind").selectedIndex = 0;
    inputs.namedItem("scene_id").value = card && card.review_status === "current" ? card.scene_id : "";
    if (card) inputs.namedItem("kind").value = card.kind;
    for (const key of ["intent", "voice", "hypothesis"]) inputs.namedItem(key).value = card?.[key] || "";
    editor.querySelector("summary").textContent = label(card ? "edit" : "add");
    editor.open = Boolean(card);
    if (card) inputs.namedItem(card.review_status === "stale" ? "scene_id" : "intent").focus();
  }

  board.addEventListener("toggle", () => { if (board.open && !state) load(); });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const fields = Object.fromEntries(new FormData(form));
    if (!(fields.intent || "").trim()) {
      form.elements.namedItem("intent").focus();
      return;
    }
    const ok = await save({action: "save", ...fields, ...(editing ? {id: editing} : {})});
    if (ok) {
      edit(null);
      editor.querySelector("summary").focus({preventScroll: true});
    }
  });
  board.addEventListener("click", async event => {
    const button = event.target.closest("button[data-intent-action]");
    if (!button || pending) return;
    const action = button.dataset.intentAction;
    if (action === "load") { load(); return; }
    if (!state) return;
    if (action === "cancel") { edit(null); editor.querySelector("summary").focus(); return; }
    if (action === "save_order") {
      if (await save({action, ids: order.slice()})) board.querySelector("summary").focus({preventScroll: true});
      return;
    }
    if (action === "reset_order") {
      order = state.cards.map(card => card.id);
      render();
      status(label("order_reset"));
      board.querySelector("summary").focus({preventScroll: true});
      return;
    }
    const id = button.closest("[data-intent-id]").dataset.intentId;
    if (action === "edit") { edit(state.cards.find(card => card.id === id)); return; }
    if (action === "delete") {
      if (window.confirm(label("delete_confirm")) && await save({action, id})) {
        if (editing === id) edit(null);
        board.querySelector("summary").focus({preventScroll: true});
      }
      return;
    }
    const index = order.indexOf(id);
    const next = index + (action === "up" ? -1 : 1);
    if (next < 0 || next >= order.length) return;
    [order[index], order[next]] = [order[next], order[index]];
    render();
    const row = list.children[next];
    const focus = row.querySelector('[data-intent-action="' + action + '"]:enabled') ||
      row.querySelector('[data-intent-action="' + (action === "up" ? "down" : "up") + '"]');
    focus.focus({preventScroll: true});
    status(uiFormat("scene_intent_position", {current: next + 1, total: order.length}));
  });
})();
