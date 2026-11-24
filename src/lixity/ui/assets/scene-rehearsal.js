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
  const submit = form.querySelector('[type="submit"]');
  const scene = form.elements.namedItem("scene_id");
  const editor = document.getElementById("scene-intent-editor");
  const editSummary = editor.querySelector("summary");
  const editWarning = document.getElementById("scene-intent-edit-conflict");
  const recoverDraft = editWarning.querySelector("button");
  const preview = document.getElementById("scene-intent-preview");
  const back = document.getElementById("scene-intent-return");
  const returnButton = back.querySelector("button");
  const orderActions = document.getElementById("scene-rehearsal-order-actions");
  const empty = document.getElementById("scene-rehearsal-empty");
  const reload = board.querySelector('[data-intent-action="load"]');
  const sceneLinks = new Map(Array.from(document.querySelectorAll(".scene-overview [data-scene-row]"), row => [
    row.dataset.sceneRow, row.querySelector("a[data-jump]").getAttribute("href")
  ]));
  let state = null;
  let pending = false;
  let requireReload = false;
  let order = [];
  let editing = null;
  const fieldNames = ["scene_id", "kind", "intent", "voice", "hypothesis"];
  const readFields = () => Object.fromEntries(fieldNames.map(key => [key, form.elements.namedItem(key).value]));
  let initialFields = readFields();
  const status = (message, type) => setStatus("scene-rehearsal-status", message, type);
  const token = () => document.getElementById("scene-intents-token").value;
  const savedOrder = data => data.cards.map(card => card.id);
  const sameOrder = (left, right) => left.length === right.length && left.every((id, index) => id === right[index]);
  const isDraftOrder = () => Boolean(state && !sameOrder(order, savedOrder(state)));
  const hasDraft = () => fieldNames.some(key => form.elements.namedItem(key).value !== initialFields[key]);
  const canWrite = () => !pending && state && !requireReload;

  function editConflict() {
    if (!editing || !state) return false;
    const latest = state.cards.find(card => card.id === editing.id);
    return !latest || [...fieldNames, "scene_title", "review_status"].some(key => latest[key] !== editing[key]);
  }

  function updateEditor() {
    const conflict = editConflict();
    fields.disabled = pending || !state;
    submit.disabled = !canWrite() || conflict;
    editWarning.hidden = !conflict;
    recoverDraft.disabled = !canWrite();
  }

  function focusInBoard(target) {
    if (board.open && target.getClientRects().length &&
        (document.activeElement === document.body || board.contains(document.activeElement))) {
      target.focus();
    }
  }

  function render() {
    updateEditor();
    const dirty = isDraftOrder();
    empty.hidden = !state || state.cards.length > 0;
    orderActions.hidden = !dirty;
    orderActions.querySelectorAll("button").forEach(button => {
      button.disabled = pending || (requireReload && button.dataset.intentAction === "save_order");
    });
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
      const editButton = node.querySelector('[data-intent-action="edit"]');
      if (editButton && stale) editButton.textContent = label("reanchor");
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
        const action = button.dataset.intentAction;
        button.disabled = pending || Boolean(disabled[action]) || (action === "delete" && requireReload);
      });
      return node;
    }));
  }

  function accept(data, requestedToken, keepDraft) {
    if (!data.ok || data.schema_version !== "lixity-analysis-intents/1" || !Array.isArray(data.cards) ||
        requestedToken !== token() || data.source_sha256 !== document.body.dataset.manuscriptSourceSha256) {
      requireReload = requireReload || data.http_status === 409 || Boolean(data.ok);
      reload.hidden = false;
      status(label(data.http_status === 409 || data.ok ? "conflict" : "unavailable"), "err");
      return false;
    }
    const ids = savedOrder(data);
    order = keepDraft
      ? order.filter(id => ids.includes(id)).concat(ids.filter(id => !order.includes(id)))
      : ids.slice();
    state = data;
    requireReload = false;
    reload.hidden = true;
    return true;
  }

  async function load() {
    if (pending) return;
    const focusAfterLoad = document.activeElement === reload;
    pending = true;
    render();
    const selected = token();
    status(uiLabel("editor_loading"), "loading");
    const data = await jsonApi(API + "/analysis-intents?project_token=" + encodeURIComponent(selected));
    pending = false;
    const draftOrder = isDraftOrder();
    const orderChanged = draftOrder && Array.isArray(data.cards) && !sameOrder(savedOrder(state), savedOrder(data));
    const ok = accept(data, selected, draftOrder && !orderChanged);
    if (ok) status(orderChanged ? label("order_conflict") : "");
    render();
    if (focusAfterLoad) {
      const destination = editConflict() ? recoverDraft : board.querySelector("summary");
      focusInBoard(ok ? destination : reload);
    }
  }

  async function save(fields) {
    if (!canWrite()) return false;
    const keepDraft = fields.action !== "save_order" && isDraftOrder();
    const active = document.activeElement;
    const card = active.closest("[data-intent-id]")?.dataset.intentId;
    const action = active.dataset.intentAction;
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
    if (!ok) {
      const retry = requireReload ? reload :
        card ? Array.from(list.children).find(row => row.dataset.intentId === card)
          ?.querySelector('[data-intent-action="' + action + '"]') : active;
      if (retry) focusInBoard(retry);
    }
    return ok;
  }

  function clearPreview() {
    back.hidden = true;
    if (back.parentElement !== board) board.append(back);
  }

  function updatePreview() {
    clearPreview();
    preview.hidden = !sceneLinks.has(scene.value);
  }

  scene.addEventListener("change", updatePreview);
  preview.addEventListener("click", () => {
    const hash = sceneLinks.get(scene.value);
    const target = hash && document.getElementById(hash.slice(1));
    if (!target) return;
    target.prepend(back);
    back.hidden = false;
    scrollAndFlash(target);
    target.focus({preventScroll: true});
  });
  returnButton.addEventListener("click", () => {
    clearPreview();
    scrollAndFlash(preview, {behavior: "instant", block: "center"});
    preview.focus({preventScroll: true});
  });

  function edit(card) {
    editing = card || null;
    const reanchor = card?.review_status === "stale";
    const inputs = form.elements;
    inputs.namedItem("kind").selectedIndex = 0;
    scene.value = card && !reanchor ? card.scene_id : "";
    if (card) inputs.namedItem("kind").value = card.kind;
    for (const key of ["intent", "voice", "hypothesis"]) inputs.namedItem(key).value = card?.[key] || "";
    initialFields = readFields();
    editSummary.textContent = label(reanchor ? "reanchor" : card ? "edit" : "add");
    editor.open = Boolean(card);
    updateEditor();
    updatePreview();
    if (card) (reanchor ? scene : inputs.namedItem("intent")).focus();
  }

  board.addEventListener("toggle", () => {
    if (board.open && !state) load();
    if (!board.open) clearPreview();
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!canWrite() || editConflict()) return;
    const fields = readFields();
    if (!(fields.intent || "").trim()) {
      form.elements.namedItem("intent").focus();
      return;
    }
    const ok = await save({action: "save", ...fields, ...(editing ? {id: editing.id} : {})});
    if (ok) {
      edit(null);
      focusInBoard(editSummary);
    }
  });
  board.addEventListener("click", async event => {
    const button = event.target.closest("button[data-intent-action]");
    if (!button || pending) return;
    const action = button.dataset.intentAction;
    if (action === "load") { load(); return; }
    if (!state) return;
    if (action === "cancel") { edit(null); editSummary.focus(); return; }
    if (action === "save_as_new") {
      if (!canWrite() || !editConflict()) return;
      editing = null;
      editSummary.textContent = label("add");
      updateEditor();
      form.elements.namedItem("intent").focus();
      return;
    }
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
    if (action === "edit") {
      if (editing?.id === id) {
        editor.open = true;
        focusInBoard(editWarning.hidden ? scene : recoverDraft);
        return;
      }
      if (!hasDraft() || window.confirm(label("discard_draft"))) edit(state.cards.find(card => card.id === id));
      return;
    }
    if (action === "delete") {
      if (window.confirm(label("delete_confirm")) && await save({action, id})) {
        if (editing?.id === id && !hasDraft()) edit(null);
        focusInBoard(board.querySelector("summary"));
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
