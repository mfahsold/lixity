/* Native-only manuscript authoring. CodeMirror is fetched only on entering Write. */
(function () {
  'use strict';
  const script = document.currentScript, nonce = script.nonce;
  const api = new URL('.', script.src).href.replace(/\/$/, '');
  const controls = document.getElementById('manuscript-reader-controls');
  const chapters = document.getElementById('chapters');
  if (!controls || !chapters) return;
  const language = (document.documentElement.lang || 'en').split('-')[0];
  const L = key => (typeof window.uiLabel === 'function' ? window.uiLabel(key) : key);
  const macKeyboard = /Mac/.test(navigator.platform);
  const editorShortcut = key => (macKeyboard ? 'Meta+' : 'Control+') + key;
  const redoShortcut = macKeyboard ? 'Meta+Shift+Z' : /Linux/.test(navigator.platform) ? 'Control+Y Control+Shift+Z' : 'Control+Y';
  const {formatSigned, visibleChange, percentagePointChange, chapterChanges, baselineLabel} = LixityRevisionMeasurements;
  const words = [
    'editor_write', 'editor_read_refresh', 'editor_undo', 'editor_redo',
    'editor_saving', 'editor_saved_locally', 'editor_unsaved_retry', 'editor_conflict_retained',
    'editor_recovery', 'editor_load_draft', 'editor_download_draft', 'editor_save_draft',
    'editor_discard_recovery', 'editor_manuscript', 'editor_analysis_outdated',
    'editor_recovery_loaded', 'editor_choose_recovery', 'editor_loading',
  ];
  const text = i => L(words[i]);
  function button(label, id, action, help, opts) {
    opts = opts || {};
    const b = document.createElement('button');
    b.type = 'button';
    b.className = opts.className || 'ctl ctl-sm';
    b.id = id;
    b.setAttribute('aria-label', opts.accessibleName || label);
    b.setAttribute('title', help || label);
    if (opts.icon && window.LixityIcons && typeof window.LixityIcons.svg === 'function') {
      const iconWrap = document.createElement('span');
      iconWrap.className = 'reader-control-icon';
      iconWrap.setAttribute('aria-hidden', 'true');
      iconWrap.innerHTML = window.LixityIcons.svg(opts.icon, {size: 16});
      const labelWrap = document.createElement('span');
      labelWrap.className = opts.labelClass || 'editor-tool-label';
      labelWrap.textContent = label;
      b.append(iconWrap, labelWrap);
      if (opts.iconOnly) b.classList.add('editor-icon-only');
    } else {
      b.textContent = label;
    }
    if (opts.shortcut) b.setAttribute('aria-keyshortcuts', opts.shortcut);
    b.setAttribute('data-help', help || label);
    b.addEventListener('click', action);
    return b;
  }
  function setButtonLabel(b, newLabel, help = newLabel) {
    b.setAttribute('aria-label', newLabel);
    b.setAttribute('title', help);
    b.setAttribute('data-help', help);
    const span = b.querySelector('.reader-control-label, .editor-tool-label');
    if (span) span.textContent = newLabel;
    else b.textContent = newLabel;
  }
  let editor, snapshot, dirty = false, paused = false, inflight = null, pending = null, timer, maximum;
  let composing = false, closing = false, opening = null, editorBundle = null;
  let generation = 0, workspaceGeneration = 0, lastState = '', readerPosition = null;
  const closeWords = [L('editor_close_writing'), L('editor_close_writing_help')];
  const writeHelp = L('editor_write_help');
  const openButton = button(text(0), 'manuscript-write', open, writeHelp, {icon: 'pen-line', className: 'ctl reader-compact-control', labelClass: 'reader-control-label'});
  const closeButton = button(closeWords[0], 'manuscript-close', close, closeWords[1], {icon: 'book-open', className: 'ctl ctl-sm reader-compact-control', labelClass: 'reader-control-label'});
  closeButton.hidden = true;
  const companionControls = controls.querySelector('.reader-controls');
  const openAnchor = companionControls || controls.querySelector('#reader-teleprompter') || controls.querySelector('#workbench-overview-label') || controls.querySelector('#reader-analysis-settings');
  if (openAnchor) openAnchor.before(openButton);
  else controls.append(openButton);
  const openingError = document.createElement('p');
  openingError.id = 'manuscript-opening-error';
  openingError.className = 'ctl-note warn';
  openingError.setAttribute('role', 'alert');
  openingError.hidden = true;
  openButton.after(openingError);
  const section = document.createElement('section'); section.id = 'manuscript-editor'; section.hidden = true;
  section.setAttribute('aria-label', text(13)); chapters.before(section);
  const tools = document.createElement('div'); tools.className = 'manuscript-edit-tools manuscript-editor-toolbar';
  tools.setAttribute('role', 'group');
  tools.setAttribute('aria-label', text(0));
  section.append(tools);
  const historyGroup = document.createElement('div'); historyGroup.className = 'editor-tool-group editor-group-history';
  const formatGroup = document.createElement('div'); formatGroup.className = 'editor-tool-group editor-group-format';
  formatGroup.setAttribute('role', 'group'); formatGroup.setAttribute('aria-label', L('editor_formatting'));
  const versions = document.createElement('details'); versions.id = 'manuscript-versions'; versions.className = 'panel-disclosure';
  const versionsSummary = document.createElement('summary'); versionsSummary.className = 'ctl ctl-sm'; versionsSummary.textContent = L('editor_versions');
  const versionsGroup = document.createElement('div'); versionsGroup.className = 'panel editor-versions-panel';
  const versionActions = document.createElement('div'); versionActions.className = 'row';
  versions.append(versionsSummary, versionsGroup);
  const contextGroup = document.createElement('div'); contextGroup.className = 'editor-tool-group editor-group-context';
  const statusGroup = document.createElement('div'); statusGroup.className = 'editor-tool-group editor-group-status';
  tools.append(historyGroup, formatGroup, contextGroup, versions, statusGroup);
  const writingCommands = {
    bold: {label: L('editor_bold'), help: L('editor_fmt_bold'), shortcut: editorShortcut('B'), run: () => editor.wrap('**', '**', 'text')},
    italic: {label: L('editor_italic'), help: L('editor_fmt_italic'), shortcut: editorShortcut('I'), run: () => editor.wrap('*', '*', 'text')},
    heading: {label: L('editor_fmt_h2'), run: () => editor.togglePrefix('## ')},
    scene: {label: L('editor_fmt_break'), run: () => editor.insertBreak()},
    undo: {label: text(2), shortcut: editorShortcut('Z'), run: () => editor.undo()},
    redo: {label: text(3), shortcut: redoShortcut, run: () => editor.redo()},
    find: {label: L('editor_find_replace'), shortcut: editorShortcut('F'), run: () => editor.search()},
  };
  function runWritingCommand(command) {
    if (!editor || section.hidden || composing) return;
    editor.focus();
    command.run();
  }
  function writingCommandButton(name, id, label, options) {
    const command = writingCommands[name];
    return button(label || command.label, id, () => runWritingCommand(command), command.help || command.label, {
      ...options, shortcut: command.shortcut, accessibleName: command.label,
    });
  }
  const formatClass = 'ctl ctl-sm editor-fmt-btn';
  formatGroup.append(
    writingCommandButton('heading', 'manuscript-fmt-h2', 'H2', {className: formatClass}),
    writingCommandButton('bold', 'manuscript-fmt-bold', 'B', {className: formatClass + ' editor-fmt-bold'}),
    writingCommandButton('italic', 'manuscript-fmt-italic', 'I', {className: formatClass + ' editor-fmt-italic'}),
    writingCommandButton('scene', 'manuscript-fmt-break', '—', {className: formatClass}),
  );
  const status = document.createElement('span'); status.id = 'manuscript-save-status'; status.setAttribute('role', 'status');
  const freshness = document.createElement('aside'); freshness.id = 'manuscript-analysis-freshness'; freshness.className = 'status-strip'; freshness.hidden = true; freshness.setAttribute('role', 'status'); const freshnessText = document.createElement('span'); freshnessText.className = 'warn'; freshnessText.textContent = text(14); freshness.append(freshnessText);
  document.body.prepend(freshness);
  const host = document.createElement('div'); host.id = 'manuscript-editor-host'; host.setAttribute('spellcheck', 'false');
  const recoveryDate = new Intl.DateTimeFormat(language, {dateStyle: 'medium', timeStyle: 'short'});
  const pulse = document.createElement('details'); pulse.className = 'panel-disclosure';
  const pulseSummary = document.createElement('summary');
  pulseSummary.id = 'manuscript-session-pulse'; pulseSummary.textContent = L('editor_pulse_title');
  const pulsePopover = document.createElement('div'); pulsePopover.id = 'manuscript-pulse-popover';
  pulsePopover.setAttribute('aria-live', 'polite');
  pulse.append(pulseSummary, pulsePopover);
  let versionRead = null;
  function cancelVersionRead() {
    versionRead?.abort();
    versionRead = null;
  }
  async function readVersion(action) {
    if (!editor || section.hidden || !versions.open || inflight || versionRead) return;
    const controller = new AbortController();
    const before = generation, revision = snapshot.revision, selected = recovery.value;
    versionRead = controller;
    const isCurrent = () => versionRead === controller && versions.open && !section.hidden &&
      !inflight && generation === before && snapshot.revision === revision && recovery.value === selected;
    try {
      await action({signal: controller.signal, revision, selected, isCurrent});
    } catch (error) {
      if (isCurrent()) show('error', error.message);
    } finally {
      if (versionRead === controller) versionRead = null;
    }
  }
  function readRecovery(selected, signal) {
    return request('/manuscript-edit?recovery=' + encodeURIComponent(selected), null, {signal});
  }
  // Escape and the native summary both mutate `open`, and toggle events can be coalesced.
  new MutationObserver(records => {
    if (records.some(record => record.oldValue !== null)) cancelVersionRead();
  }).observe(versions, {attributeFilter: ['open'], attributeOldValue: true});
  pulse.addEventListener('toggle', () => {
    if (pulse.open && versions.open && snapshot) refreshPulse();
    else cancelPulse();
  });
  versions.addEventListener('toggle', () => {
    if (!versions.open) {
      pulse.open = false;
      cancelPulse();
    }
  });
  const recovery = document.createElement('select'); recovery.className = 'ctl ctl-sm'; recovery.id = 'manuscript-recovery'; recovery.setAttribute('aria-label', text(8));
  const recoveryNote = document.createElement('p'); recoveryNote.id = 'manuscript-recovery-note'; recoveryNote.className = 'ctl-note';
  recoveryNote.textContent = L('editor_recovery_unsaved');
  const retry = button(text(11), 'manuscript-save', saveDraft, null, {icon: 'save', shortcut: editorShortcut('S'), className: 'ctl ctl-sm primary'});
  const undoBtn = writingCommandButton('undo', 'manuscript-undo', null, {icon: 'undo', iconOnly: true});
  const redoBtn = writingCommandButton('redo', 'manuscript-redo', null, {icon: 'redo', iconOnly: true});
  historyGroup.append(undoBtn, redoBtn);
  statusGroup.append(status, retry, closeButton);
  const reload = button(text(1), 'manuscript-reload', () => {if (dirty) download(); location.reload();}, null, {icon: 'rotate-cw'});
  reload.hidden = true;
  const recoverBtn = button(text(9), 'manuscript-recover', () => {
    if (dirty || !recovery.value) return;
    return readVersion(async ({selected, signal, isCurrent}) => {
      const recovered = await readRecovery(selected, signal);
      if (!isCurrent() || dirty) return;
      if (recovered.document !== snapshot.document) throw new Error(L('editor_compare_changed'));
      paused = true; pending = null; editor.replace(recovered.text); dirty = true;
      show('unsaved', text(15)); versions.open = false; editor.focus();
    });
  }, L('editor_review_draft_help'), {icon: 'rotate-ccw'});
  const downloadBtn = button(text(10), 'manuscript-download', download, L('editor_download_draft_help'), {icon: 'download'});
  const discardBtn = button(text(12), 'manuscript-discard', async () => {
    if (!recovery.value || !confirm(text(12) + '?')) return;
    try {await request('/manuscript-edit-discard', {document: snapshot.document, id: recovery.value}); await refreshRecovery();}
    catch (error) {show('error', error.message);}
  }, text(12), {icon: 'trash-2'});
  function syncRecoveryActions() {
    const hasSelection = Boolean(recovery.value);
    recoverBtn.hidden = !hasSelection;
    recoverBtn.disabled = dirty;
    discardBtn.hidden = !hasSelection;
    recoveryNote.hidden = !hasSelection || !dirty;
    if (recoveryNote.hidden) recovery.removeAttribute('aria-describedby');
    else recovery.setAttribute('aria-describedby', recoveryNote.id);
  }
  recovery.addEventListener('change', () => {
    cancelVersionRead();
    syncRecoveryActions();
  });
  syncRecoveryActions();
  const comparisonWords = [
    'editor_find_replace', 'editor_compare_versions', 'editor_compare_base',
    'editor_compare_current', 'editor_compare_draft', 'editor_compare_use_draft',
    'editor_compare_cancel', 'editor_compare_note', 'editor_compare_changed',
  ].map(L);
  const searchBtn = writingCommandButton('find', 'manuscript-search', null, {icon: 'search'});
  historyGroup.append(searchBtn);
  const comparison = document.createElement('dialog'); comparison.id = 'manuscript-comparison'; comparison.className = 'lixity-modal'; comparison.setAttribute('closedby', 'any'); comparison.setAttribute('aria-label', comparisonWords[1]);
  const comparisonCard = document.createElement('div'); comparisonCard.className = 'modal-card';
  const comparisonHeader = document.createElement('div'); comparisonHeader.className = 'modal-header';
  const comparisonTitle = document.createElement('h2'); comparisonTitle.textContent = comparisonWords[1];
  const comparisonClose = document.createElement('button'); comparisonClose.type = 'button'; comparisonClose.className = 'modal-close'; comparisonClose.textContent = '✕'; comparisonClose.setAttribute('aria-label', comparisonWords[6]); comparisonClose.title = comparisonWords[6];
  const comparisonBody = document.createElement('div'); comparisonBody.className = 'modal-body';
  const comparisonNote = document.createElement('p'); comparisonNote.className = 'ctl-note';
  comparisonNote.textContent = comparisonWords[7] + ' ' + L('editor_compare_metrics_reference');
  const metricGuide = document.body.dataset.metricGuide;
  if (metricGuide) {
    const reference = document.createElement('a');
    reference.className = "ctl metric-guide-action";
    reference.href = metricGuide + '#revisions';
    reference.target = '_blank';
    reference.rel = 'noopener noreferrer';
    reference.textContent = L('metric_reference_link');
    comparisonNote.append(' ', reference);
  }
  const comparisonBuffer = document.createElement('details'); comparisonBuffer.className = 'panel-disclosure';
  const comparisonBufferSummary = document.createElement('summary');
  comparisonBufferSummary.id = 'manuscript-comparison-buffer-label';
  comparisonBufferSummary.textContent = L('editor_compare_unsaved_text');
  const comparisonBufferText = document.createElement('textarea'); comparisonBufferText.id = 'manuscript-comparison-buffer';
  comparisonBufferText.className = 'ctl'; comparisonBufferText.readOnly = true; comparisonBufferText.rows = 5;
  comparisonBufferText.setAttribute('aria-labelledby', comparisonBufferSummary.id);
  comparisonBuffer.append(comparisonBufferSummary, comparisonBufferText);
  const comparisonGrid = document.createElement('div'); comparisonGrid.className = 'manuscript-comparison-grid';
  const comparisonFields = ['base','current','draft'].map((name, index) => {
    const label = document.createElement('label'); label.textContent = comparisonWords[index+2];
    const identity = document.createElement('small'); identity.style.display = 'block';
    const summary = document.createElement('small'); summary.className = 'manuscript-compare-metrics'; summary.style.display = 'block';
    const field = document.createElement('textarea'); field.id = 'manuscript-comparison-' + name; field.readOnly = index !== 2;
    label.append(identity,summary,field); comparisonGrid.append(label); return {field,identity,summary};
  });
  const comparisonChapters = document.createElement('div');
  comparisonChapters.id = 'manuscript-comparison-chapters';
  comparisonChapters.className = 'manuscript-comparison-chapters';
  comparisonChapters.hidden = true;
  let comparisonSnapshot = null, comparisonOriginal = '';
  let comparisonTimer = 0, comparisonRequest = null, comparisonSettings = null;
  const comparisonDirty = () => comparison.open && comparisonFields[2].field.value !== comparisonOriginal;
  function closeComparison() {
    if (!comparisonDirty() || confirm(L('editor_compare_discard_confirm'))) {
      comparison.close();
      if (versions.open && !section.hidden) compareBtn.focus({preventScroll: true});
    }
  }
  comparisonClose.addEventListener('click', closeComparison);
  comparison.addEventListener('cancel', event => {event.preventDefault(); closeComparison();});
  comparison.addEventListener('close', () => {
    cancelComparisonMeasurements();
    notifyDesktopDirty();
  });
  const comparisonUse = button(comparisonWords[5], 'manuscript-comparison-use', () => {
    if (!comparisonSnapshot || inflight) return;
    const proposed = comparisonFields[2].field.value;
    if (dirty && editor.text() !== proposed && !confirm(L('editor_compare_replace_unsaved'))) return;
    paused = true; pending = null; snapshot = comparisonSnapshot; comparisonSnapshot = null;
    editor.replace(proposed); dirty = true;
    comparison.close(); versions.open = false; show('unsaved', L('editor_pending_changes')); editor.focus();
  }, L('editor_review_draft_help'), {icon: 'check', className: 'ctl primary'});
  const comparisonCancel = button(comparisonWords[6], 'manuscript-comparison-cancel', closeComparison, comparisonWords[6], {icon: 'x', shortcut: 'Escape', className: 'ctl'});
  const comparisonActions = document.createElement('div'); comparisonActions.className = 'modal-footer'; comparisonActions.append(comparisonCancel,comparisonUse);
  comparisonHeader.append(comparisonTitle, comparisonClose);
  comparisonBody.append(comparisonNote, comparisonBuffer, comparisonGrid, comparisonChapters);
  comparisonCard.append(comparisonHeader, comparisonBody, comparisonActions);
  comparison.append(comparisonCard); document.body.append(comparison);
  const compareBtn = button(comparisonWords[1], 'manuscript-compare', () => readVersion(async ({signal, revision, selected, isCurrent}) => {
    const current = await request('/manuscript-edit', null, {signal});
    if (!isCurrent()) return;
    const recovered = selected ? await readRecovery(selected, signal) : null;
    if (!isCurrent()) return;
    if (current.document !== snapshot.document || recovered && recovered.document !== snapshot.document) throw new Error(comparisonWords[8]);
    comparisonSnapshot = current;
    const buffer = editor.text();
    comparisonBuffer.open = false;
    comparisonBuffer.hidden = !dirty;
    comparisonBufferText.value = dirty ? buffer : '';
    comparisonFields[0].field.value = snapshot.text; comparisonFields[0].identity.textContent = revision.slice(0,12);
    comparisonFields[1].field.value = current.text; comparisonFields[1].identity.textContent = current.revision.slice(0,12);
    comparisonFields[2].field.value = recovered ? recovered.text : buffer;
    comparisonFields[2].identity.textContent = recovered ? recovered.revision.slice(0,12) : '';
    comparisonFields[2].identity.hidden = !recovered;
    comparisonOriginal = comparisonFields[2].field.value;
    comparisonSettings = null;
    comparisonFields.forEach(({summary}) => {summary.textContent = L('editor_compare_metrics_loading');});
    comparisonChapters.hidden = true;
    comparison.showModal();
    refreshComparisonMeasurements();
    if (window.LixityMotion && window.LixityMotion.surface) window.LixityMotion.surface(comparisonGrid);
    comparisonCancel.focus();
  }), L('editor_compare_versions_help'), {icon: 'git-compare'});
  versionActions.append(recoverBtn, discardBtn, compareBtn, downloadBtn);
  versionsGroup.append(recovery, recoveryNote, versionActions, pulse);
  document.addEventListener('click', event => {
    if (versions.open && !versions.contains(event.target) && !comparison.contains(event.target)) versions.open = false;
  });
  contextGroup.append(reload);
  function dockCompanionTools(intoEditor) {
    if (!companionControls) return;
    if (intoEditor) contextGroup.prepend(companionControls);
    else openButton.after(companionControls);
  }
  section.append(host);
  function revealWritingTools() {
    if (section.hidden || document.body.dataset.workspaceView !== 'analysis') return;
    const bounds = tools.getBoundingClientRect();
    if (bounds.bottom <= 0 || (bounds.bottom > window.innerHeight && bounds.top > 0)) {
      section.scrollIntoView({block: 'start', behavior: 'instant'});
    }
  }
  function keepFocusedWritingToolsInView() {
    if (section.contains(document.activeElement)) revealWritingTools();
  }
  window.addEventListener('resize', keepFocusedWritingToolsInView, {passive: true});
  if (typeof ResizeObserver === 'function') {
    new ResizeObserver(keepFocusedWritingToolsInView).observe(tools);
  }
  const editMenuLabel = L('editor_edit_actions');
  const editMenu = document.createElement('div');
  editMenu.id = 'manuscript-edit-menu';
  editMenu.className = 'manuscript-context-menu';
  editMenu.setAttribute('role', 'menu');
  editMenu.setAttribute('aria-label', editMenuLabel);
  editMenu.hidden = true;
  document.body.append(editMenu);
  const editActions = button('…', 'manuscript-edit-actions', () => {
    if (!editMenu.hidden) closeEditMenu(true);
    else openEditMenu(editActions.getBoundingClientRect(), editActions);
  }, L('editor_edit_actions_help'), {accessibleName: editMenuLabel, shortcut: 'Shift+F10'});
  editActions.setAttribute('aria-haspopup', 'menu');
  editActions.setAttribute('aria-controls', editMenu.id);
  editActions.setAttribute('aria-expanded', 'false');
  versions.before(editActions);
  let editMenuOpener;
  const menuItems = Object.entries(writingCommands).map(([name, command]) => {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'ctl';
    item.id = 'manuscript-edit-menu-' + name;
    item.setAttribute('role', 'menuitem');
    item.tabIndex = -1;
    item.textContent = command.label;
    item.addEventListener('click', () => {
      closeEditMenu(false);
      runWritingCommand(command);
    });
    return item;
  });
  editMenu.append(...menuItems);
  function closeEditMenu(restoreFocus) {
    if (editMenu.hidden) return;
    editMenu.hidden = true;
    editActions.setAttribute('aria-expanded', 'false');
    if (restoreFocus && !section.hidden) {
      if (editMenuOpener) editMenuOpener.focus({preventScroll: true});
      else editor.focus();
    }
    editMenuOpener = null;
  }
  function focusEditMenuItem(index) {
    menuItems.forEach((item, i) => {item.tabIndex = i === index ? 0 : -1;});
    menuItems[index].focus();
  }
  function openEditMenu(anchor, opener = null, last = false) {
    if (!editor || section.hidden || composing) return;
    versions.open = false;
    editMenuOpener = opener;
    editActions.setAttribute('aria-expanded', 'true');
    LixityComponents.measureOverlay(editMenu, () => {
      editMenu.hidden = false;
      const bounds = editMenu.getBoundingClientRect();
      const top = anchor.bottom + bounds.height + 8 <= innerHeight || anchor.top < innerHeight / 2
        ? anchor.bottom + 4 : anchor.top - bounds.height - 4;
      LixityComponents.placeClampedOverlay(editMenu, anchor.left, top, {bounds, gutter: 8});
    });
    focusEditMenuItem(last ? menuItems.length - 1 : 0);
  }
  host.addEventListener('contextmenu', event => {
    // The native clipboard menu remains available with Shift+right-click.
    if (!event.target.closest('.cm-content') || event.shiftKey || !editor || composing) return;
    event.preventDefault();
    openEditMenu({left: event.clientX, top: event.clientY, bottom: event.clientY});
  });
  function isEditMenuKey(event) {
    return event.key === 'ContextMenu' || (event.key === 'F10' && event.shiftKey);
  }
  host.addEventListener('keydown', event => {
    if (!isEditMenuKey(event) || event.isComposing || !event.target.closest('.cm-content')) return;
    event.preventDefault();
    const selection = window.getSelection();
    let anchor = host.getBoundingClientRect();
    if (selection?.focusNode && event.target.contains(selection.focusNode)) {
      const caret = document.createRange();
      caret.setStart(selection.focusNode, selection.focusOffset);
      caret.collapse(true);
      if (caret.getClientRects().length) anchor = caret.getBoundingClientRect();
    }
    openEditMenu(anchor);
  });
  editActions.addEventListener('keydown', event => {
    if (!isEditMenuKey(event) && event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    event.preventDefault();
    openEditMenu(editActions.getBoundingClientRect(), editActions, event.key === 'ArrowUp');
  });
  editMenu.addEventListener('keydown', event => {
    if (event.key === 'Tab' || event.key === 'Escape') {
      if (event.key === 'Escape') event.preventDefault();
      event.stopPropagation();
      closeEditMenu(true);
      return;
    }
    const current = menuItems.indexOf(document.activeElement);
    let next;
    if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = menuItems.length - 1;
    else if (event.key === 'ArrowDown') next = (current + 1) % menuItems.length;
    else if (event.key === 'ArrowUp') next = (current - 1 + menuItems.length) % menuItems.length;
    else return;
    event.preventDefault();
    event.stopPropagation();
    focusEditMenuItem(next);
  });
  function closeEditMenuOutside(event) {
    if (!editMenu.contains(event.target) && !editActions.contains(event.target)) closeEditMenu(false);
  }
  document.addEventListener('pointerdown', closeEditMenuOutside);
  document.addEventListener('focusin', closeEditMenuOutside);
  document.addEventListener('scroll', event => {
    if (event.target !== editMenu) closeEditMenu(true);
  }, {capture: true, passive: true});
  window.addEventListener('resize', () => closeEditMenu(true));
  document.addEventListener('lixity:workbench-change', () => closeEditMenu(false));
  new MutationObserver(() => {
    if (section.hidden) closeEditMenu(false);
  }).observe(section, {attributeFilter: ['hidden']});
  const css = document.createElement('style'); css.textContent = `
    #manuscript-comparison {width:min(1200px,95vw);max-width:min(1200px,95vw);max-height:min(92dvh,56rem);}
    #manuscript-comparison .modal-card {max-height:min(calc(92dvh - 2px),calc(56rem - 2px));}
    #manuscript-comparison .modal-body > .ctl-note {margin:0;}
    #manuscript-comparison-buffer {inline-size:100%;box-sizing:border-box;}
    .manuscript-comparison-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--space-4,16px);}
    .manuscript-comparison-grid label {display:flex;flex-direction:column;min-width:0;font-weight:var(--weight-semibold,600);font-size:var(--text-small,.875rem);}
    .manuscript-comparison-grid small {color:var(--muted);font-family:var(--font-mono,monospace);margin-top:2px;}
    .manuscript-comparison-grid textarea {display:block;box-sizing:border-box;width:100%;flex:1 1 auto;min-height:clamp(14rem,42dvh,30rem);margin-top:8px;padding:12px;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:var(--radius-sm,8px);font-family:var(--font-title,serif);font-size:1rem;line-height:1.6;resize:vertical;}
    @media(max-width:760px) {.manuscript-comparison-grid {grid-template-columns:1fr;}.manuscript-comparison-grid textarea {min-height:clamp(9rem,22dvh,15rem);}}
    #manuscript-analysis-freshness {position:relative;z-index:20;margin:0;padding:.2rem .5rem;background:transparent;border:0;box-shadow:none;font-size:var(--text-note,.8125rem);color:var(--muted);}
    #manuscript-analysis-freshness[hidden] {display:none;}
    #manuscript-editor {container:editor-tools / inline-size;min-width:0;padding:4px 0 24px;width:100%;}
    .manuscript-edit-tools {display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:0;}
    .manuscript-editor-toolbar {position:sticky;top:0;z-index:14;flex-wrap:nowrap;gap:6px;padding:5px 8px;margin-bottom:14px;background:color-mix(in srgb,var(--surface) 92%,transparent);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border:1px solid var(--line);border-radius:var(--radius-sm,8px);box-shadow:var(--shadow);box-sizing:border-box;max-width:100%;}
    .editor-tool-group {display:inline-flex;align-items:center;gap:4px;min-width:0;flex:0 1 auto;}
    .editor-group-history,.editor-group-format {flex-shrink:0;}
    .editor-group-context {padding-inline-start:var(--space-2);border-inline-start:1px solid var(--line);}
    .editor-group-context:not(:has(> :not([hidden]))) {display:none;}
    #manuscript-versions > summary {min-block-size:2rem;gap:var(--space-2);padding:var(--space-1) var(--space-2);white-space:nowrap;}
    .editor-versions-panel {position:absolute;inset-block-start:calc(100% + var(--space-1));inset-inline-end:0;width:min(27rem,100%);margin:0;display:grid;gap:var(--space-2);max-height:60dvh;overflow:auto;}
    .manuscript-editor-toolbar .editor-versions-panel button.ctl {white-space:normal;text-align:start;line-height:var(--line-control);}
    #manuscript-recovery-note {margin:0;}
    .editor-group-status {margin-inline-start:auto;padding-inline-start:6px;gap:6px;}
    .editor-group-status > button {flex-shrink:0;}
    .manuscript-editor-toolbar .reader-controls {display:inline-flex;align-items:center;flex-basis:auto;gap:4px;}
    .manuscript-editor-toolbar button.ctl {padding:.25rem .5rem;min-height:2rem;white-space:nowrap;}
    .manuscript-editor-toolbar button.editor-icon-only .editor-tool-label {display:none;}
    .manuscript-editor-toolbar button.editor-icon-only {padding-inline:.45rem;min-width:2rem;justify-content:center;}
    .manuscript-editor-toolbar button.ctl:not(.primary) {border-color:transparent;background:transparent;}
    .manuscript-editor-toolbar button.ctl:not(.primary):hover {background:var(--surface-hover);border-color:var(--line);color:var(--fg);}
    #manuscript-save-status {min-width:0;flex:0 1 auto;font-size:var(--text-micro,.8125rem);color:var(--muted);padding:3px 10px;border-radius:var(--radius-pill,999px);background:var(--surface-raised,var(--bg));border:1px solid var(--line);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:12rem;}
    #manuscript-save-status[data-state=saved] {color:var(--status-success-fg,var(--present-ink));background:var(--status-success-bg,var(--present-light));border-color:var(--status-success-border,transparent);}
    #manuscript-save-status:is([data-state=conflict],[data-state=error]) {color:var(--flag);background:var(--flag-light);border-color:color-mix(in srgb,var(--flag) 30%,transparent);font-weight:600;max-inline-size:24rem;white-space:normal;overflow-wrap:anywhere;}
    #manuscript-recovery {width:100%;min-width:0;}
    .manuscript-editor-toolbar button.editor-fmt-btn {min-width:2rem;padding-inline:.45rem;font-size:.82rem;font-weight:650;}
    .manuscript-editor-toolbar button.editor-fmt-italic {font-style:italic;font-family:var(--font-title,serif);}
    .manuscript-editor-toolbar .editor-group-format {padding-inline-start:6px;border-inline-start:1px solid var(--line);}
    #manuscript-save-status[data-state="saved"] {background:transparent!important;border-color:transparent!important;color:var(--muted)!important;font-weight:400!important;box-shadow:none!important;}
    #manuscript-editor-host {min-width:0;max-width:min(100%,calc(var(--reader-measure,68ch) + 8rem));margin:0 auto;overflow:hidden;border-radius:var(--radius-lg,16px);box-shadow:0 6px 24px rgba(0,0,0,.05);}
    #manuscript-pulse-popover {padding:var(--space-2);font-size:var(--text-small);color:var(--muted);overflow-wrap:anywhere;}
    #manuscript-pulse-popover svg {display:block;margin-block-start:var(--space-2);color:var(--accent);max-inline-size:100%;}
    .manuscript-compare-metrics {font-weight:400;color:var(--muted);margin-top:2px;}
    .manuscript-comparison-chapters {margin-top:var(--space-3,12px);padding-top:var(--space-3,12px);border-top:1px solid var(--line);font-size:var(--text-small,.875rem);}
    .manuscript-comparison-chapters h3 {margin:0 0 6px;font-size:var(--text-small,.875rem);font-weight:var(--weight-semibold,600);}
    .manuscript-comparison-chapters ul {margin:4px 0 0;padding-inline-start:18px;display:grid;gap:4px;}
    .manuscript-comparison-chapters li {color:var(--fg);}
    .manuscript-comparison-chapters li small {color:var(--muted);margin-inline-start:6px;}
    #manuscript-editor-host .cm-line.lixity-session-edited {box-shadow:inset 2px 0 0 var(--accent,#2f5aa8);}
    @container editor-tools (max-width: 60rem) {
      #manuscript-search .editor-tool-label,
      .manuscript-editor-toolbar #workspace-reader-toggle .reader-control-label {display:none;}
      #manuscript-search,
      .manuscript-editor-toolbar #workspace-reader-toggle {padding-inline:.45rem;min-width:2rem;justify-content:center;}
      #manuscript-save .editor-tool-label,
      .manuscript-editor-toolbar #manuscript-close .reader-control-label {display:none;}
      #manuscript-save,.manuscript-editor-toolbar #manuscript-close {padding-inline:.45rem;min-width:2rem;justify-content:center;}
      .editor-tool-group {gap:var(--space-1);}
      .manuscript-editor-toolbar .editor-group-format,.editor-group-context,.editor-group-status {padding-inline-start:var(--space-1);}
      #manuscript-save-status {padding-inline:var(--space-1);}
    }
    @container editor-tools (max-width: 42rem) {
      .manuscript-editor-toolbar .editor-tool-group > button,
      .manuscript-editor-toolbar .editor-tool-group .reader-controls > button {min-inline-size:2rem;padding-inline:var(--space-1);}
      #manuscript-versions > summary {gap:var(--space-1);padding-inline:var(--space-1);}
      #manuscript-save-status[data-state=saved] {flex-shrink:0;}
    }
    @container editor-tools (max-width: 36rem) {
      .manuscript-editor-toolbar {flex-wrap:wrap;}
      .editor-tool-group {flex-wrap:wrap;flex-shrink:1;max-width:100%;}
      .editor-group-context {padding-inline-start:0;border-inline-start:0;}
      .editor-group-status {flex:1 1 100%;margin-inline-start:0;padding-inline-start:0;}
      #manuscript-save-status {flex:1 1 0;max-inline-size:none;white-space:normal;overflow-wrap:anywhere;}
      #manuscript-save-status[data-state=saved] {flex-shrink:1;}
    }
    @container editor-tools (max-width: 24rem) {
      /* Editing actions exposes these commands when the direct buttons no longer fit. */
      .manuscript-editor-toolbar:has(#manuscript-edit-actions) :is(.editor-group-history,.editor-group-format) {display:none;}
      .manuscript-editor-toolbar:has(#manuscript-versions[open]) {position:relative;}
      #manuscript-versions[open] {flex:1 1 100%;min-inline-size:0;}
      .editor-versions-panel {position:static;box-sizing:border-box;inline-size:100%;margin-block-start:var(--space-2);}
    }
    @media(max-width:600px) {
      .manuscript-editor-toolbar button.ctl, #manuscript-versions > summary {min-height:2.75rem;}
      #manuscript-comparison {width:calc(100vw - 16px);max-width:calc(100vw - 16px);}
    }
    body.manuscript-writing #chapters,body.manuscript-writing #text-search,body.manuscript-writing .toolbar {display:none!important;}
    body.manuscript-writing #manuscript-reader-controls {display:none!important;}
    body.workbench-overview #manuscript-write, body.reader-focus #manuscript-write {display:none!important;}
  `; document.head.append(css);
  const hasUnsavedText = () => Boolean(dirty || inflight || comparisonDirty());
  let desktopDirtyState, desktopDirtyRequest;
  function notifyDesktopDirty() {
    const bridge = window.lixityDesktop;
    const next = hasUnsavedText();
    if (!bridge || typeof bridge.setDirtyState !== 'function' || desktopDirtyState === next || desktopDirtyRequest) return;
    const failed = () => {
      // Browser beforeunload remains active if the desktop bridge is unavailable.
      desktopDirtyRequest = null;
      desktopDirtyState = undefined;
    };
    try {
      desktopDirtyState = next;
      desktopDirtyRequest = Promise.resolve(bridge.setDirtyState({unsavedEditor: next})).then(() => {
        desktopDirtyRequest = null;
        notifyDesktopDirty();
      }, failed);
    } catch (_) { failed(); }
  }
  function show(state, message) {
    freshness.hidden = !dirty && (!snapshot || snapshot.revision === document.body.dataset.manuscriptSourceSha256);
    const changed = lastState !== state;
    lastState = state;
    if (changed) status.dataset.state = state;
    if (status.textContent !== message) status.textContent = message;
    if (changed && window.LixityMotion && window.LixityMotion.status) window.LixityMotion.status(status);
    retry.hidden = state === 'saved' || state === 'saving';
    reload.hidden = !paused;
    syncRecoveryActions();
    notifyDesktopDirty();
  }
  let pulseRequest = null;
  let sessionBaselineLines = [];
  let gutterRaf = 0;
  function markEditedLines() {
    gutterRaf = 0;
    if (!editor || !sessionBaselineLines.length) return;
    const currentLines = editor.text().split('\n');
    const domLines = host.querySelectorAll('.cm-content > .cm-line');
    domLines.forEach((node, idx) => {
      // Match rendered lines against session baseline to highlight modified paragraphs subtly.
      const txt = node.textContent || '';
      const changed = idx < currentLines.length && currentLines[idx] !== sessionBaselineLines[idx] && txt === currentLines[idx];
      node.classList.toggle('lixity-session-edited', changed);
    });
  }
  function scheduleGutterMark() {
    if (!gutterRaf) gutterRaf = requestAnimationFrame(markEditedLines);
  }
  function fmtNum(v, digits) {
    if (v === null || v === undefined || Number.isNaN(v)) return '–';
    return Number(v).toLocaleString(language, {minimumFractionDigits: digits, maximumFractionDigits: digits});
  }
  function fmtPercent(value, digits) {
    return (value / 100).toLocaleString(language, {
      style: 'percent', minimumFractionDigits: digits, maximumFractionDigits: digits,
    });
  }
  function formatMetricsLine(snap, deltas) {
    if (!snap) return '';
    const parts = [fmtNum(snap.words, 0) + ' ' + L(snap.words === 1 ? 'words_one' : 'words')];
    if (visibleChange(deltas?.words, 0)) {
      parts[0] += ' (Δ ' + formatSigned(deltas.words, 0) + ')';
    }
    if (snap.asl !== null && snap.asl !== undefined) {
      let aslPart = L('measurement_words_per_sentence') + ' ' + fmtNum(snap.asl, 1);
      if (visibleChange(deltas?.asl, 1)) {
        aslPart += ' (Δ ' + formatSigned(deltas.asl, 1) + ')';
      }
      parts.push(aslPart);
    }
    if (snap.dialogue_ratio !== null && snap.dialogue_ratio !== undefined) {
      let dialoguePart = L('editor_pulse_dialogue') + ' ' + fmtPercent(snap.dialogue_ratio, 0);
      if (visibleChange(deltas?.dialogue_ratio, 1)) {
        dialoguePart += ' (Δ ' + percentagePointChange(deltas.dialogue_ratio) + ')';
      }
      parts.push(dialoguePart);
    }
    if (snap.length_entropy !== null && snap.length_entropy !== undefined) {
      let entPart = L('editor_pulse_entropy') + ' ' + fmtNum(snap.length_entropy, 2);
      if (visibleChange(deltas?.length_entropy, 2)) {
        entPart += ' (Δ ' + formatSigned(deltas.length_entropy, 2) + ')';
      }
      parts.push(entPart);
    }
    if (snap.sticky_pct !== null && snap.sticky_pct !== undefined) {
      let stickyPart = L('editor_pulse_sticky') + ' ' + fmtPercent(snap.sticky_pct, 1);
      if (visibleChange(deltas?.sticky_pct, 1)) {
        stickyPart += ' (Δ ' + percentagePointChange(deltas.sticky_pct) + ')';
      }
      parts.push(stickyPart);
    }
    if (snap.indirect_speech_per_1000 !== null && snap.indirect_speech_per_1000 !== undefined) {
      let indPart = L('editor_pulse_indirect') + ' ' + fmtNum(snap.indirect_speech_per_1000, 1);
      if (visibleChange(deltas?.indirect_speech_per_1000, 1)) {
        indPart += ' (Δ ' + formatSigned(deltas.indirect_speech_per_1000, 1) + ')';
      }
      parts.push(indPart);
    }
    return parts.join(' · ');
  }
  function formatChapterDelta(ch) {
    const {words_delta: words, asl_delta: average, dialog_pct_delta: dialogue} = chapterChanges(ch);
    return [
      words && words + ' ' + L(Math.abs(ch.words_delta) === 1 ? 'words_one' : 'words'),
      average && L('measurement_words_per_sentence') + ' Δ ' + average,
      dialogue && L('editor_pulse_dialogue') + ' Δ ' + dialogue,
    ].filter(Boolean).join(' · ');
  }
  function renderComparisonResults(data) {
    const m = (data && data.measurements) || {};
    const b2c = data && data.base_to_current ? data.base_to_current.deltas : null;
    const c2d = data && data.current_to_draft ? data.current_to_draft.deltas : null;
    const pairs = [
      [m.base, null],
      [m.current, b2c],
      [m.draft, c2d],
    ];
    comparisonFields.forEach(({summary}, index) => {
      const [metrics, deltas] = pairs[index];
      summary.textContent = metrics
        ? L('editor_compare_metrics_measured') + ' · ' + formatMetricsLine(metrics, deltas)
        : L('editor_compare_metrics_unavailable');
    });
    const diffKey = data && data.primary_diff;
    const diff = diffKey && data[diffKey] ? data[diffKey] : null;
    comparisonChapters.replaceChildren();
    if (!diff || !Array.isArray(diff.chapter_deltas) || !diff.chapter_deltas.length) {
      comparisonChapters.hidden = true;
      return;
    }
    const matched = diff.chapter_deltas.filter(ch => ch.match_status === 'matched' && ch.changed);
    const {ambiguous, unmatched} = diff.chapter_matching || {};
    if (!matched.length && !ambiguous && !unmatched) {
      comparisonChapters.hidden = true;
      return;
    }
    const heading = document.createElement('h3');
    const [from, to] = diffKey === 'base_to_current' ? [2, 3] : [3, 4];
    heading.textContent = `${L('editor_compare_chapters_heading')} · ${comparisonWords[from]} → ${comparisonWords[to]}`;
    comparisonChapters.append(heading);
    if (matched.length) {
      const list = document.createElement('ul');
      matched.forEach(ch => {
        const li = document.createElement('li');
        const numText = ch.base_num && ch.base_num !== ch.num
          ? `${ch.base_num} → ${ch.num}`
          : String(ch.num);
        const titlePart = ch.title ? ` · ${ch.title}` : '';
        const strong = document.createElement('strong');
        strong.textContent = `${L('chapter')} ${numText}${titlePart}`;
        li.append(strong);
        const deltaText = formatChapterDelta(ch);
        if (deltaText) {
          const detail = document.createElement('small');
          detail.textContent = deltaText;
          li.append(detail);
        }
        list.append(li);
      });
      comparisonChapters.append(list);
    }
    if (ambiguous) {
      const noteEl = document.createElement('p');
      noteEl.className = 'ctl-note';
      noteEl.textContent = L('editor_compare_chapters_unclear');
      comparisonChapters.append(noteEl);
    }
    if (unmatched) {
      const noteEl = document.createElement('p');
      noteEl.className = 'ctl-note';
      noteEl.textContent = L('editor_compare_chapters_unmatched');
      comparisonChapters.append(noteEl);
    }
    comparisonChapters.hidden = false;
  }
  function cancelComparisonMeasurements() {
    clearTimeout(comparisonTimer);
    if (comparisonRequest) comparisonRequest.abort();
    comparisonRequest = null;
  }
  async function refreshComparisonMeasurements() {
    if (!comparison.open || !comparisonSnapshot) return;
    const controller = new AbortController();
    comparisonRequest = controller;
    try {
      const data = await request('/manuscript-compare', {
        document: comparisonSnapshot.document,
        revision: comparisonSnapshot.revision,
        settings_sha256: comparisonSettings,
        base_text: comparisonFields[0].field.value,
        draft_text: comparisonFields[2].field.value,
      }, {signal: controller.signal});
      if (comparisonRequest !== controller || !comparison.open) return;
      comparisonSettings = data.settings_sha256;
      renderComparisonResults(data);
    } catch (error) {
      if (comparisonRequest !== controller || !comparison.open) return;
      comparisonFields.forEach(({summary}) => {
        summary.textContent = L(error.conflict ? 'editor_compare_metrics_stale' : 'editor_compare_metrics_unavailable');
      });
      comparisonChapters.hidden = true;
    } finally {
      if (comparisonRequest === controller) comparisonRequest = null;
    }
  }
  comparisonFields[2].field.addEventListener('input', () => {
    if (!comparison.open || !comparisonSnapshot) return;
    notifyDesktopDirty();
    cancelComparisonMeasurements();
    comparisonFields[2].summary.textContent = L('editor_compare_metrics_loading');
    comparisonChapters.hidden = true;
    comparisonTimer = setTimeout(refreshComparisonMeasurements, 300);
  });
  function renderSparklineSvg(revisions) {
    if (!revisions || revisions.length < 2) return '';
    const w = 220, h = 40, pad = 4;
    const vals = revisions.map(r => Number(r.words || 0));
    const min = Math.min(...vals), max = Math.max(...vals);
    const span = max - min || 1;
    const pts = vals.map((v, i) => {
      const x = pad + (i / (vals.length - 1)) * (w - pad * 2);
      const y = h - pad - ((v - min) / span) * (h - pad * 2);
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    return '<svg width="220" height="40" viewBox="0 0 220 40" aria-hidden="true">' +
      '<polyline fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="' + pts + '"/>' +
      '</svg>';
  }
  function cancelPulse() {
    pulseRequest?.abort();
    pulseRequest = null;
  }
  async function refreshPulse() {
    cancelPulse();
    const controller = new AbortController();
    pulseRequest = controller;
    const {document: documentId, revision} = snapshot;
    const isCurrent = () => pulseRequest === controller && pulse.open && versions.open &&
      snapshot.document === documentId && snapshot.revision === revision;
    pulsePopover.textContent = L('editor_compare_metrics_loading');
    try {
      const [deltaRes, tlRes] = await Promise.all([
        request('/manuscript-delta', null, {signal: controller.signal}),
        request('/manuscript-timeline?limit=14', null, {signal: controller.signal}),
      ]);
      if (!isCurrent()) return;
      if (deltaRes.document !== documentId || tlRes.document !== documentId ||
          deltaRes.current?.revision !== revision || !Array.isArray(tlRes.revisions)) {
        pulsePopover.textContent = L('editor_compare_metrics_stale');
        return;
      }
      const revisions = tlRes.revisions;
      const values = document.createElement('p');
      values.textContent = formatMetricsLine(deltaRes.current, deltaRes.has_baseline ? deltaRes.deltas : null);
      const since = deltaRes.has_baseline ? baselineLabel(deltaRes.base) : '';
      if (since) values.append(' · ' + since);
      const head = document.createElement('div');
      head.textContent = L('editor_pulse_title') + ' (' + fmtNum(revisions.length, 0) + ' ' + L('editor_pulse_revisions') + ')';
      pulsePopover.replaceChildren(values, head);
      if (revisions.length >= 2) {
        const chart = document.createElement('div');
        chart.innerHTML = renderSparklineSvg(revisions);
        pulsePopover.append(chart);
      } else {
        const noteEl = document.createElement('div');
        noteEl.textContent = L('editor_pulse_baseline');
        pulsePopover.append(noteEl);
      }
    } catch (_) {
      if (isCurrent()) pulsePopover.textContent = L('editor_compare_metrics_unavailable');
    } finally {
      if (pulseRequest === controller) pulseRequest = null;
    }
  }
  async function request(path, payload, {signal} = {}) {
    const options = payload ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)} : {};
    const response = await fetch(api + path, {...options, signal});
    const data = await response.json(); if (!response.ok || !data.ok) {const error = new Error(data.message || text(6)); error.conflict = response.status === 409; throw error;} return data;
  }
  function changes() {
    generation++;
    dirty = true; show('unsaved', L('editor_pending_changes'));
    scheduleGutterMark();
    scheduleSave();
  }
  function scheduleSave() {
    if (paused || composing) return;
    clearTimeout(timer); timer = setTimeout(flush, 800);
    if (!maximum) maximum = setTimeout(flush, 4000);
  }
  host.addEventListener('compositionstart', () => {
    composing = true;
    clearTimeout(timer); clearTimeout(maximum); maximum = null;
  }, true);
  host.addEventListener('compositionend', () => {
    composing = false;
    if (dirty) scheduleSave();
  }, true);
  function saveDraft() {
    if (composing) return;
    paused = false;
    return flush();
  }
  function flush() {
    if (inflight) return inflight;
    clearTimeout(timer); clearTimeout(maximum); maximum = null;
    if (!editor || !dirty || paused || composing) return;
    if (!pending) pending = {document: snapshot.document, revision: snapshot.revision,
      operation: crypto.randomUUID().replaceAll('-', ''), text: editor.text()};
    inflight = save(pending);
    show('saving', text(4));
    return inflight;
  }
  async function save(sent) {
    try {
      const result = await request('/manuscript-edit', sent);
      snapshot.revision = result.revision; snapshot.text = sent.text; pending = null; dirty = editor.text() !== sent.text;
      show(dirty ? 'unsaved' : 'saved', dirty ? L('editor_pending_changes') : text(5));
      if (versions.open && pulse.open) refreshPulse();
    } catch (error) {
      paused = true;
      show(error.conflict ? 'conflict' : 'error', text(error.conflict ? 7 : 6) + ': ' + error.message);
      refreshRecovery().catch(() => {});
    }
    finally {
      inflight = null;
      notifyDesktopDirty();
      if (dirty) scheduleSave();
    }
  }
  function download() {
    if (!editor) return;
    const blob = new Blob([editor.text()], {type: 'text/markdown;charset=utf-8'});
    if (window.LixityComponents && typeof window.LixityComponents.downloadBlob === 'function') {
      window.LixityComponents.downloadBlob(blob, 'manuscript-draft.md', 1000);
      return;
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'manuscript-draft.md'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function showRecovery(current) {
    const selected = recovery.value;
    recovery.replaceChildren(new Option(text(16), ''));
    current.recovery.forEach(row => {
      const name = row.kind === 'draft' ? L('editor_compare_draft') : text(8);
      const option = new Option(name + ' · ' + recoveryDate.format(new Date(row.created * 1000)), row.id);
      option.dataset.kind = row.kind;
      recovery.append(option);
      if (row.id === selected) recovery.value = selected;
    });
    syncRecoveryActions();
  }
  let recoveryRefresh = null;
  async function refreshRecovery() {
    recoveryRefresh?.abort();
    const controller = new AbortController();
    recoveryRefresh = controller;
    const requestedDocument = snapshot?.document;
    try {
      const current = await request('/manuscript-edit', null, {signal: controller.signal});
      if (recoveryRefresh === controller && snapshot?.document === requestedDocument &&
          current.document === requestedDocument) showRecovery(current);
    } catch (error) {
      if (!controller.signal.aborted) throw error;
    } finally {
      if (recoveryRefresh === controller) recoveryRefresh = null;
    }
  }
  function captureReaderPosition() {
    const controlsBottom = controls ? controls.getBoundingClientRect().bottom : 0;
    const visible = Array.from(chapters.querySelectorAll('.ptext[data-start]')).find(node => {
      const rect = node.getBoundingClientRect();
      return rect.height > 0 && rect.bottom > controlsBottom && rect.top < window.innerHeight;
    });
    return {
      line: visible ? Number(visible.dataset.start) : 1,
      offset: visible ? visible.getBoundingClientRect().top : null,
      left: window.scrollX,
      top: window.scrollY,
    };
  }
  const readerReturnKey = 'lixity:editor-return:' + location.pathname + location.search;
  function restoreReaderPosition(position) {
    openButton.focus({preventScroll: true});
    const passage = position.offset === null ? null :
      chapters.querySelector('.ptext[data-start="' + position.line + '"]');
    const top = passage?.getClientRects().length
      ? window.scrollY + passage.getBoundingClientRect().top - position.offset
      : position.top;
    window.scrollTo({top, left: position.left, behavior: 'instant'});
  }
  window.addEventListener('pageshow', () => {
    try {
      const position = JSON.parse(sessionStorage.getItem(readerReturnKey) || 'null');
      sessionStorage.removeItem(readerReturnKey);
      if (!position || position.revision !== document.body.dataset.manuscriptSourceSha256) return;
      const before = workspaceGeneration, identity = projectIdentity(), focused = document.activeElement;
      // Browser and workspace navigation settle their scroll positions after pageshow.
      requestAnimationFrame(() => requestAnimationFrame(() => {
        if (before === workspaceGeneration && identity === projectIdentity() &&
            focused === document.activeElement && writingContextAvailable()) restoreReaderPosition(position);
      }));
    } catch (_) { /* The reader remains usable with browser storage disabled. */ }
  });
  function writingContextAvailable(state = window.LixityWorkbench?.state()) {
    return !state || state.view === 'analysis' && state.surface === 'document' && !state.focus;
  }
  function projectIdentity() {
    const {manuscriptProjectToken, manuscriptSourceSha256} = document.body.dataset;
    return [manuscriptProjectToken, manuscriptSourceSha256].join(':');
  }
  function showWritingMode(position, requestedLine, shouldFocus) {
    const samePosition = readerPosition && (readerPosition.line === position.line ||
      Math.abs(readerPosition.top - position.top) <= 1);
    const moveToLine = requestedLine ?? (samePosition ? null : position.line);
    readerPosition = position;
    dockCompanionTools(true);
    section.hidden = false;
    document.body.classList.add('manuscript-writing');
    openButton.hidden = true;
    closeButton.hidden = false;
    window.LixityChrome?.reveal?.();
    window.LixityMotion?.surface?.(section);
    revealWritingTools();
    if (moveToLine !== null) editor.line(moveToLine);
    else editor.revealSelection();
    if (shouldFocus) editor.focus();
  }
  function setOpening(value) {
    if (value) {
      openButton.setAttribute('aria-disabled', 'true');
      openButton.setAttribute('aria-busy', 'true');
      openButton.removeAttribute('aria-describedby');
      openingError.hidden = true;
    } else {
      openButton.removeAttribute('aria-disabled');
      openButton.removeAttribute('aria-busy');
    }
    setButtonLabel(openButton, text(value ? 17 : 0), value ? text(17) : writeHelp);
  }
  function cancelOpening() {
    if (!opening) return;
    opening.abort();
    opening = null;
    setOpening(false);
  }
  window.LixityWorkbench?.subscribe((current, previous) => {
    if (current.view !== previous.view || current.surface !== previous.surface || current.focus !== previous.focus) {
      workspaceGeneration++;
      cancelOpening();
      cancelVersionRead();
    }
  });
  function loadEditor() {
    if (!editorBundle) editorBundle = new Promise((resolve, reject) => {
      const bundle = document.createElement('script');
      bundle.nonce = nonce;
      bundle.src = api + '/editor-bundle.js';
      bundle.onload = resolve;
      bundle.onerror = () => {
        bundle.remove();
        reject(new Error('Editor bundle unavailable'));
      };
      document.head.append(bundle);
    }).catch(error => {
      editorBundle = null;
      throw error;
    });
    return editorBundle;
  }
  async function open(targetLine) {
    if (!writingContextAvailable() || closing) return;
    const requestedLine = Number.isInteger(targetLine) && targetLine > 0 ? targetLine : null;
    if (opening && requestedLine === null) return;
    const position = captureReaderPosition();
    if (editor) {
      showWritingMode(position, requestedLine, true);
      return;
    }
    cancelOpening();
    const controller = new AbortController(), identity = projectIdentity();
    const focused = document.activeElement;
    const current = () => opening === controller && identity === projectIdentity() && writingContextAvailable();
    opening = controller;
    setOpening(true);
    try {
      const result = await request('/manuscript-edit', null, {signal: controller.signal});
      if (!current()) return;
      await loadEditor();
      if (!current()) return;
      snapshot = result;
      const shouldFocus = document.activeElement === focused;
      editor = window.LixityCodeMirror.mount(host, snapshot.text, changes, language, text(13));
      sessionBaselineLines = snapshot.text.split('\n');
      showRecovery(snapshot);
      showWritingMode(position, requestedLine, shouldFocus);
      show('saved', text(5));
    } catch (_) {
      if (current()) {
        openingError.textContent = L('editor_open_error');
        openingError.hidden = false;
        openButton.setAttribute('aria-describedby', openingError.id);
      }
    } finally {
      if (opening === controller) { opening = null; setOpening(false); }
    }
  }
  async function close() {
    if (!editor || section.hidden || closing || comparison.open || composing) return;
    const before = workspaceGeneration, identity = projectIdentity();
    const current = () => before === workspaceGeneration && identity === projectIdentity() && writingContextAvailable();
    closing = true;
    cancelVersionRead();
    try {
      while (current() && !composing && !paused && (inflight || dirty)) await flush();
      if (!current() || composing || paused) return;
      if (snapshot.revision !== document.body.dataset.manuscriptSourceSha256) {
        try {
          sessionStorage.setItem(readerReturnKey, JSON.stringify({...readerPosition, revision: snapshot.revision}));
        } catch (_) { /* Browser storage is optional. */ }
        location.reload();
        return;
      }
      // Keep the document, selection and undo history mounted across a clean exit.
      versions.open = false;
      section.hidden = true; document.body.classList.remove('manuscript-writing');
      dockCompanionTools(false);
      closeButton.hidden = true; openButton.hidden = false;
      window.LixityChrome?.reveal?.();
      window.LixityMotion?.surface?.(chapters);
      window.LixityLog?.debug?.('manuscript-editor:close', {dirty, paused});
      restoreReaderPosition(readerPosition);
      // Compare the next entry with the rendered reader, whose chrome can reflow on return.
      readerPosition = captureReaderPosition();
    } finally {
      closing = false;
    }
  }
  let nudgeTimer = 0;
  function nudgeWriteButton() {
    if (document.body.classList.contains('manuscript-writing')) return;
    if (openButton.hidden || openButton.getClientRects().length === 0) return;
    const sel = window.getSelection();
    if (sel && !sel.isCollapsed) return;
    openButton.classList.remove('write-nudge');
    void openButton.offsetWidth;
    openButton.classList.add('write-nudge');
    clearTimeout(nudgeTimer);
    nudgeTimer = setTimeout(() => openButton.classList.remove('write-nudge'), 1250);
  }
  chapters.addEventListener('click', event => {
    if (!event.target.closest('#chapters .ptext p')) return;
    if (event.target.closest('a, button, input, select, textarea')) return;
    nudgeWriteButton();
  });
  document.addEventListener('keydown', event => {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (!event.key || event.key.length !== 1) return;
    const t = event.target;
    if (t && t.closest && t.closest('input, textarea, select, [contenteditable]')) return;
    if (!t || !t.closest || (!t.closest('#chapters') && t !== document.body)) return;
    nudgeWriteButton();
  });
  document.addEventListener('keydown', event => {
    if (section.hidden || !section.contains(event.target) || !writingContextAvailable() ||
        !(macKeyboard ? event.metaKey : event.ctrlKey) || event.shiftKey || event.altKey ||
        event.key.toLowerCase() !== 's') return;
    event.preventDefault();
    if (!event.isComposing) saveDraft();
  }, true);
  window.addEventListener('beforeunload', event => {if (hasUnsavedText()) {event.preventDefault(); event.returnValue = '';}});
  document.addEventListener('visibilitychange', () => {if (document.hidden) flush();});
  // Keep shortcuts from the read-only manuscript layer away from the editor.
  host.addEventListener('keydown', event => event.stopPropagation());
  window.LixityManuscriptEditor = { openAtLine: line => open(line) };
})();
