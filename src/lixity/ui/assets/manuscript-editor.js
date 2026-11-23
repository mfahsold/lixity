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
  function setButtonLabel(b, newLabel) {
    b.setAttribute('aria-label', newLabel);
    b.setAttribute('title', newLabel);
    b.setAttribute('data-help', newLabel);
    const span = b.querySelector('.reader-control-label, .editor-tool-label');
    if (span) span.textContent = newLabel;
    else b.textContent = newLabel;
  }
  let editor, snapshot, dirty = false, paused = false, inflight = false, pending = null, timer, maximum, loading = false;
  let composing = false;
  let loaded = false, generation = 0, openingLine = 1, lastState = '';
  const closeWords = [L('editor_close_writing'), L('editor_close_writing_help')];
  const openButton = button(text(0), 'manuscript-write', open, null, {icon: 'pen-line', className: 'ctl reader-compact-control', labelClass: 'reader-control-label'});
  const closeButton = button(closeWords[0], 'manuscript-close', close, closeWords[1], {icon: 'book-open', className: 'ctl ctl-sm reader-compact-control', labelClass: 'reader-control-label'});
  closeButton.hidden = true;
  const companionControls = controls.querySelector('.reader-controls');
  const openAnchor = companionControls || controls.querySelector('#reader-teleprompter') || controls.querySelector('#workbench-overview-label') || controls.querySelector('#reader-analysis-settings');
  if (openAnchor) openAnchor.before(openButton);
  else controls.append(openButton);
  const section = document.createElement('section'); section.id = 'manuscript-editor'; section.hidden = true;
  section.setAttribute('aria-label', text(13)); chapters.before(section);
  const tools = document.createElement('div'); tools.className = 'manuscript-edit-tools manuscript-editor-toolbar'; section.append(tools);
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
  const fmtWords = ['editor_fmt_h2', 'editor_fmt_bold', 'editor_fmt_italic', 'editor_fmt_break'].map(L);
  const fmtH2 = button('H2', 'manuscript-fmt-h2', () => editor && editor.togglePrefix && editor.togglePrefix('## '), fmtWords[0], {className: 'ctl ctl-sm editor-fmt-btn', accessibleName: fmtWords[0]});
  const fmtBold = button('B', 'manuscript-fmt-bold', () => editor && editor.wrap && editor.wrap('**', '**', 'text'), fmtWords[1], {className: 'ctl ctl-sm editor-fmt-btn editor-fmt-bold', shortcut: 'Control+B', accessibleName: L('editor_bold')});
  const fmtItalic = button('I', 'manuscript-fmt-italic', () => editor && editor.wrap && editor.wrap('*', '*', 'text'), fmtWords[2], {className: 'ctl ctl-sm editor-fmt-btn editor-fmt-italic', shortcut: 'Control+I', accessibleName: L('editor_italic')});
  const fmtBreak = button('—', 'manuscript-fmt-break', () => editor && editor.insertBreak && editor.insertBreak(), fmtWords[3], {className: 'ctl ctl-sm editor-fmt-btn', accessibleName: fmtWords[3]});
  formatGroup.append(fmtH2, fmtBold, fmtItalic, fmtBreak);
  const status = document.createElement('span'); status.id = 'manuscript-save-status'; status.setAttribute('role', 'status');
  const freshness = document.createElement('aside'); freshness.id = 'manuscript-analysis-freshness'; freshness.className = 'status-strip'; freshness.hidden = true; freshness.setAttribute('role', 'status'); const freshnessText = document.createElement('span'); freshnessText.className = 'warn'; freshnessText.textContent = text(14); freshness.append(freshnessText);
  document.body.prepend(freshness);
  const host = document.createElement('div'); host.id = 'manuscript-editor-host'; host.setAttribute('spellcheck', 'false');
  const recoveryDate = new Intl.DateTimeFormat(language, {dateStyle: 'medium', timeStyle: 'short'});
  const pulseWrap = document.createElement('div'); pulseWrap.id = 'manuscript-session-pulse-wrap'; pulseWrap.hidden = true;
  const pulseBtn = document.createElement('button'); pulseBtn.type = 'button'; pulseBtn.id = 'manuscript-session-pulse'; pulseBtn.className = 'ctl manuscript-pulse-btn';
  pulseBtn.setAttribute('aria-expanded', 'false');
  const pulsePopover = document.createElement('div'); pulsePopover.id = 'manuscript-pulse-popover'; pulsePopover.hidden = true;
  pulseBtn.addEventListener('click', () => {
    const openState = pulsePopover.hidden;
    pulsePopover.hidden = !openState;
    pulseBtn.setAttribute('aria-expanded', String(openState));
  });
  pulseWrap.append(pulseBtn, pulsePopover);
  const recovery = document.createElement('select'); recovery.className = 'ctl ctl-sm'; recovery.id = 'manuscript-recovery'; recovery.setAttribute('aria-label', text(8));
  const retry = button(text(11), 'manuscript-save', () => {paused = false; flush();}, null, {icon: 'save', className: 'ctl ctl-sm primary'});
  const undoBtn = button(text(2), 'manuscript-undo', () => {if (editor) {editor.undo(); editor.focus();}}, text(2), {icon: 'undo', shortcut: 'Control+Z', iconOnly: true});
  const redoBtn = button(text(3), 'manuscript-redo', () => {if (editor) {editor.redo(); editor.focus();}}, text(3), {icon: 'redo', shortcut: 'Control+Y', iconOnly: true});
  historyGroup.append(undoBtn, redoBtn);
  statusGroup.append(status, retry, closeButton);
  const reload = button(text(1), 'manuscript-reload', () => {if (dirty) download(); location.reload();}, null, {icon: 'rotate-cw'});
  reload.hidden = true;
  const recoverBtn = button(text(9), 'manuscript-recover', async () => {
    if (!recovery.value || inflight) return;
    if (dirty) {download(); return;}
    try {
      const before = generation;
      const recovered = await request('/manuscript-edit?recovery=' + encodeURIComponent(recovery.value));
      if (generation !== before || dirty || inflight) return;
      if (recovered.document !== snapshot.document) throw new Error('Recovery document mismatch');
      paused = true; pending = null; editor.replace(recovered.text); dirty = true;
      show('unsaved', text(15)); versions.open = false; editor.focus();
    } catch (error) {show('error', error.message);}
  }, null, {icon: 'rotate-ccw'});
  const downloadBtn = button(text(10), 'manuscript-download', download, text(10), {icon: 'download'});
  const discardBtn = button(text(12), 'manuscript-discard', async () => {
    if (!recovery.value || !confirm(text(12) + '?')) return;
    try {await request('/manuscript-edit-discard', {document: snapshot.document, id: recovery.value}); await refreshRecovery();}
    catch (error) {show('error', error.message);}
  }, text(12), {icon: 'trash-2'});
  function syncRecoveryActions() {
    const hasSelection = Boolean(recovery.value);
    recoverBtn.hidden = !hasSelection;
    discardBtn.hidden = !hasSelection;
  }
  recovery.addEventListener('change', syncRecoveryActions);
  syncRecoveryActions();
  const comparisonWords = [
    'editor_find_replace', 'editor_compare_versions', 'editor_compare_base',
    'editor_compare_current', 'editor_compare_draft', 'editor_compare_use_draft',
    'editor_compare_cancel', 'editor_compare_note', 'editor_compare_changed',
  ].map(L);
  const searchBtn = button(comparisonWords[0], 'manuscript-search', () => editor && editor.search(), comparisonWords[0], {icon: 'search', shortcut: 'Control+F'});
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
    reference.href = metricGuide + '#revisions';
    reference.target = '_blank';
    reference.rel = 'noopener noreferrer';
    reference.textContent = L('metric_reference_link');
    comparisonNote.append(' ', reference);
  }
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
  let comparisonSnapshot = null, comparisonLoading = false, comparisonOriginal = '';
  let comparisonTimer = 0, comparisonRequest = null, comparisonSettings = null;
  const comparisonDirty = () => comparison.open && comparisonFields[2].field.value !== comparisonOriginal;
  function closeComparison() {
    if (!comparisonDirty() || confirm(L('editor_compare_discard_confirm'))) comparison.close();
  }
  comparisonClose.addEventListener('click', closeComparison);
  comparison.addEventListener('cancel', event => {event.preventDefault(); closeComparison();});
  comparison.addEventListener('close', cancelComparisonMeasurements);
  const comparisonUse = button(comparisonWords[5], 'manuscript-comparison-use', () => {
    if (!comparisonSnapshot || inflight) return;
    paused = true; pending = null; snapshot = comparisonSnapshot; comparisonSnapshot = null;
    editor.replace(comparisonFields[2].field.value); dirty = true;
    comparison.close(); versions.open = false; show('unsaved', L('editor_pending_changes')); editor.focus();
  }, null, {icon: 'check', className: 'ctl primary'});
  const comparisonCancel = button(comparisonWords[6], 'manuscript-comparison-cancel', closeComparison, comparisonWords[6], {icon: 'x', shortcut: 'Escape', className: 'ctl'});
  const comparisonActions = document.createElement('div'); comparisonActions.className = 'modal-footer'; comparisonActions.append(comparisonCancel,comparisonUse);
  comparisonHeader.append(comparisonTitle, comparisonClose);
  comparisonBody.append(comparisonNote, comparisonGrid, comparisonChapters);
  comparisonCard.append(comparisonHeader, comparisonBody, comparisonActions);
  comparison.append(comparisonCard); document.body.append(comparison);
  const compareBtn = button(comparisonWords[1], 'manuscript-compare', async () => {
    if (!editor || inflight || comparisonLoading) return;
    comparisonLoading = true;
    const before = generation, baseRevision = snapshot.revision, selected = recovery.value;
    try {
      const current = await request('/manuscript-edit');
      const recovered = selected ? await request('/manuscript-edit?recovery=' + encodeURIComponent(selected)) : null;
      if (generation !== before || inflight || snapshot.revision !== baseRevision) return;
      if (current.document !== snapshot.document || recovered && recovered.document !== snapshot.document) throw new Error(comparisonWords[8]);
      comparisonSnapshot = current;
      comparisonFields[0].field.value = snapshot.text; comparisonFields[0].identity.textContent = baseRevision.slice(0,12);
      comparisonFields[1].field.value = current.text; comparisonFields[1].identity.textContent = current.revision.slice(0,12);
      comparisonFields[2].field.value = recovered ? recovered.text : editor.text();
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
    } catch (error) {show('error',error.message);}
    finally {comparisonLoading = false;}
  }, null, {icon: 'git-compare'});
  versionActions.append(recoverBtn, discardBtn, compareBtn, downloadBtn);
  versionsGroup.append(recovery, versionActions);
  document.addEventListener('click', event => {
    if (versions.open && !versions.contains(event.target) && !comparison.contains(event.target)) versions.open = false;
  });
  contextGroup.append(reload);
  function dockCompanionTools(intoEditor) {
    if (!companionControls) return;
    if (intoEditor) contextGroup.prepend(companionControls);
    else openButton.after(companionControls);
  }
  section.append(host, pulseWrap);
  const css = document.createElement('style'); css.textContent = `
    #manuscript-comparison {width:min(1200px,95vw);max-width:min(1200px,95vw);max-height:min(92dvh,56rem);}
    #manuscript-comparison .modal-card {max-height:min(calc(92dvh - 2px),calc(56rem - 2px));}
    #manuscript-comparison .modal-body > .ctl-note {margin:0;}
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
    .editor-group-status {margin-inline-start:auto;padding-inline-start:6px;gap:6px;}
    .manuscript-editor-toolbar .reader-controls {display:inline-flex;align-items:center;flex-basis:auto;gap:4px;}
    .manuscript-editor-toolbar button.ctl {padding:.25rem .5rem;min-height:2rem;white-space:nowrap;}
    .manuscript-editor-toolbar button.editor-icon-only .editor-tool-label {display:none;}
    .manuscript-editor-toolbar button.editor-icon-only {padding-inline:.45rem;min-width:2rem;justify-content:center;}
    .manuscript-editor-toolbar button.ctl:not(.primary) {border-color:transparent;background:transparent;}
    .manuscript-editor-toolbar button.ctl:not(.primary):hover {background:var(--surface-hover);border-color:var(--line);color:var(--fg);}
    #manuscript-save-status {min-width:0;flex:0 1 auto;font-size:var(--text-micro,.8125rem);color:var(--muted);padding:3px 10px;border-radius:var(--radius-pill,999px);background:var(--surface-raised,var(--bg));border:1px solid var(--line);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:12rem;}
    #manuscript-save-status[data-state=saved] {color:var(--status-success-fg,var(--present-ink));background:var(--status-success-bg,var(--present-light));border-color:var(--status-success-border,transparent);}
    #manuscript-save-status[data-state=conflict],#manuscript-save-status[data-state=error] {color:var(--flag);background:var(--flag-light);border-color:color-mix(in srgb,var(--flag) 30%,transparent);font-weight:600;}
    #manuscript-recovery {width:100%;min-width:0;}
    .manuscript-editor-toolbar button.editor-fmt-btn {min-width:2rem;padding-inline:.45rem;font-size:.82rem;font-weight:650;}
    .manuscript-editor-toolbar button.editor-fmt-italic {font-style:italic;font-family:var(--font-title,serif);}
    .manuscript-editor-toolbar .editor-group-format {padding-inline-start:6px;border-inline-start:1px solid var(--line);}
    #manuscript-save-status[data-state="saved"] {background:transparent!important;border-color:transparent!important;color:var(--muted)!important;font-weight:400!important;box-shadow:none!important;}
    #manuscript-editor-host {min-width:0;max-width:min(100%,calc(var(--reader-measure,68ch) + 8rem));margin:0 auto;overflow:hidden;border-radius:var(--radius-lg,16px);box-shadow:0 6px 24px rgba(0,0,0,.05);}
    #manuscript-session-pulse-wrap {max-width:min(100%,calc(var(--reader-measure,68ch) + 8rem));margin:8px auto 0;display:flex;flex-direction:column;align-items:flex-end;gap:6px;}
    .manuscript-pulse-btn {max-width:100%;white-space:normal;text-align:right;line-height:1.35;font-size:var(--text-micro,.8125rem);color:var(--muted);background:transparent;border:1px solid transparent;border-radius:var(--radius-pill,999px);padding:3px 10px;cursor:pointer;}
    .manuscript-pulse-btn:hover {background:var(--surface-hover);border-color:var(--line);color:var(--fg);}
    #manuscript-pulse-popover {background:var(--surface);border:1px solid var(--line);border-radius:var(--radius,12px);padding:10px 14px;box-shadow:var(--shadow);font-size:var(--text-micro,.8125rem);color:var(--muted);max-width:100%;box-sizing:border-box;}
    #manuscript-pulse-popover svg {display:block;margin-top:6px;color:var(--accent,currentColor);}
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
      .editor-group-status {margin-inline-start:0;padding-inline-start:0;}
    }
    @media(max-width:600px) {
      .manuscript-editor-toolbar button.ctl, #manuscript-versions > summary {min-height:2.75rem;}
      #manuscript-session-pulse-wrap {align-items:stretch;}
      .manuscript-pulse-btn {text-align:center;min-height:2.75rem;}
      #manuscript-pulse-popover {width:100%;}
      #manuscript-comparison {width:calc(100vw - 16px);max-width:calc(100vw - 16px);}
    }
    body.manuscript-writing #chapters,body.manuscript-writing #text-search,body.manuscript-writing .toolbar {display:none!important;}
    body.manuscript-writing #manuscript-reader-controls {display:none!important;}
    body.workbench-overview #manuscript-write, body.workbench-overview #manuscript-close,
    body.reader-focus #manuscript-write, body.reader-focus #manuscript-close {display:none!important;}
  `; document.head.append(css);
  function show(state, message) {
    freshness.hidden = !dirty && (!snapshot || snapshot.revision === document.body.dataset.manuscriptSourceSha256);
    const changed = lastState !== state;
    lastState = state;
    status.dataset.state = state; status.textContent = message;
    if (changed && window.LixityMotion && window.LixityMotion.status) window.LixityMotion.status(status);
    retry.hidden = state === 'saved' || state === 'saving';
    reload.hidden = !paused;
  }
  let pulseGeneration = 0;
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
  async function refreshPulse() {
    const generation = ++pulseGeneration;
    const {document: documentId, revision} = snapshot;
    const isCurrent = () => generation === pulseGeneration &&
      snapshot.document === documentId && snapshot.revision === revision;
    try {
      const [deltaRes, tlRes] = await Promise.all([
        request('/manuscript-delta'),
        request('/manuscript-timeline?limit=14'),
      ]);
      if (!isCurrent()) return;
      if (deltaRes.document !== documentId || tlRes.document !== documentId ||
          deltaRes.current?.revision !== revision || !Array.isArray(tlRes.revisions)) {
        pulseWrap.hidden = true;
        return;
      }
      const revisions = tlRes.revisions;
      pulseBtn.textContent = formatMetricsLine(deltaRes.current, deltaRes.has_baseline ? deltaRes.deltas : null);
      const since = deltaRes.has_baseline ? baselineLabel(deltaRes.base) : '';
      if (since) pulseBtn.append(' · ' + since);
      pulseWrap.hidden = false;
      const head = document.createElement('div');
      head.textContent = L('editor_pulse_title') + ' (' + fmtNum(revisions.length, 0) + ' ' + L('editor_pulse_revisions') + ')';
      pulsePopover.replaceChildren(head);
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
      if (isCurrent()) pulseWrap.hidden = true;
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
  async function flush() {
    clearTimeout(timer); clearTimeout(maximum); maximum = null;
    if (!editor || !dirty || inflight || paused || composing) return;
    inflight = true; show('saving', text(4));
    if (!pending) pending = {document: snapshot.document, revision: snapshot.revision,
      operation: crypto.randomUUID().replaceAll('-', ''), text: editor.text()};
    const sent = pending;
    try {
      const result = await request('/manuscript-edit', sent);
      snapshot.revision = result.revision; snapshot.text = sent.text; pending = null; dirty = editor.text() !== sent.text;
      show(dirty ? 'unsaved' : 'saved', dirty ? L('editor_pending_changes') : text(5));
      refreshPulse().catch(() => {});
    } catch (error) {paused = true; show(error.conflict ? 'conflict' : 'error', text(error.conflict ? 7 : 6) + ': ' + error.message); await refreshRecovery().catch(() => {});}
    finally {
      inflight = false;
      if (dirty && !paused && !composing) timer = setTimeout(flush, 800);
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
  async function refreshRecovery() {
    const current = await request('/manuscript-edit');
    recovery.replaceChildren(new Option(text(16), ''));
    current.recovery.forEach(row => {
      const name = row.kind === 'draft' ? L('editor_compare_draft') : text(8);
      const option = new Option(name + ' · ' + recoveryDate.format(new Date(row.created * 1000)), row.id);
      option.dataset.kind = row.kind;
      recovery.append(option);
    });
    syncRecoveryActions();
  }
  function visibleReaderLine() {
    const controlsBottom = controls ? controls.getBoundingClientRect().bottom : 0;
    const visible = Array.from(chapters.querySelectorAll('[data-start]')).find(
      node => node.getClientRects().length > 0 && node.getBoundingClientRect().bottom > controlsBottom
    );
    return visible ? Number(visible.dataset.start) : 1;
  }
  async function open(targetLine) {
    if (loading) return;
    const requestedLine = Number.isInteger(targetLine) && targetLine > 0 ? targetLine : null;
    if (editor) {
      openingLine = requestedLine || visibleReaderLine();
      dockCompanionTools(true);
      section.hidden = false; document.body.classList.add('manuscript-writing');
      openButton.hidden = true; closeButton.hidden = false;
      if (window.LixityChrome && window.LixityChrome.reveal) window.LixityChrome.reveal();
      if (window.LixityMotion && window.LixityMotion.surface) window.LixityMotion.surface(section);
      editor.line(openingLine); editor.focus(); return;
    }
    loading = true; openButton.disabled = true; setButtonLabel(openButton, text(17));
    try {
      snapshot = await request('/manuscript-edit');
      openingLine = requestedLine || visibleReaderLine();
      if (!loaded) await new Promise((resolve, reject) => {const bundle = document.createElement('script'); bundle.nonce = nonce; bundle.src = api + '/editor-bundle.js'; bundle.onload = resolve; bundle.onerror = () => reject(new Error('Editor bundle unavailable')); document.head.append(bundle);});
      loaded = true;
      dockCompanionTools(true);
      section.hidden = false; document.body.classList.add('manuscript-writing');
      openButton.hidden = true; closeButton.hidden = false;
      if (window.LixityChrome && window.LixityChrome.reveal) window.LixityChrome.reveal();
      editor = window.LixityCodeMirror.mount(host, snapshot.text, changes, language, text(13));
      sessionBaselineLines = snapshot.text.split('\n');
      const cmContent = host.querySelector('.cm-content');
      if (cmContent) {
        cmContent.setAttribute('spellcheck', 'false');
        cmContent.setAttribute('autocorrect', 'off');
        cmContent.setAttribute('autocapitalize', 'off');
      }
      if (window.LixityMotion && window.LixityMotion.surface) window.LixityMotion.surface(section);
      editor.line(openingLine); show('saved', text(5)); await refreshRecovery(); refreshPulse().catch(() => {}); editor.focus();
    } catch (error) {section.hidden = false; show('error', error.message);}
    finally {loading = false; openButton.disabled = false; setButtonLabel(openButton, text(0));}
  }
  async function close() {
    if (comparison.open || composing) return;
    while (inflight) await new Promise(resolve => setTimeout(resolve, 25));
    if (composing) return;
    if (dirty && !paused) await flush();
    if (paused) return;
    if (snapshot && snapshot.revision !== document.body.dataset.manuscriptSourceSha256) {
      location.reload();
      return;
    }
    // Keep the mounted editor and its undo history; only leave the writing surface.
    versions.open = false;
    section.hidden = true; document.body.classList.remove('manuscript-writing');
    dockCompanionTools(false);
    closeButton.hidden = true; openButton.hidden = false;
    if (window.LixityChrome && window.LixityChrome.reveal) window.LixityChrome.reveal();
    if (window.LixityMotion && window.LixityMotion.surface) window.LixityMotion.surface(chapters);
    if (window.LixityLog && window.LixityLog.debug) window.LixityLog.debug('manuscript-editor:close', {dirty, paused});
    openButton.focus({preventScroll: true});
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
  window.addEventListener('beforeunload', event => {if (dirty || inflight || comparisonDirty()) {event.preventDefault(); event.returnValue = '';}});
  document.addEventListener('visibilitychange', () => {if (document.hidden) flush();});
  // Keep shortcuts from the read-only manuscript layer away from the editor.
  host.addEventListener('keydown', event => event.stopPropagation());
  window.LixityManuscriptEditor = { openAtLine: line => open(line) };
})();
