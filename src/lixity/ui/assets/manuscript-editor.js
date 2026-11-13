/* Native-only manuscript authoring. CodeMirror is fetched only on entering Write. */
(function () {
  'use strict';
  const script = document.currentScript, nonce = script.nonce;
  const api = new URL('.', script.src).href.replace(/\/$/, '');
  const controls = document.getElementById('manuscript-reader-controls');
  const chapters = document.getElementById('chapters');
  if (!controls || !chapters) return;
  const language = (document.documentElement.lang || 'en').split('-')[0];
  const translations = {
    en: ['Write', 'Read and refresh', 'Undo', 'Redo', 'Saving…', 'Saved locally', 'Unsaved — retry', 'Conflict — draft retained', 'Recovery', 'Load as draft', 'Download draft', 'Save this draft', 'Remove recovery copy', 'Manuscript', 'Earlier analysis is outdated while editing.', 'Recovery loaded for review. Save explicitly to apply.', 'Choose a recovery copy', 'Loading…'],
    de: ['Schreiben', 'Lesen und aktualisieren', 'Rückgängig', 'Wiederholen', 'Speichert…', 'Lokal gespeichert', 'Ungespeichert — erneut versuchen', 'Konflikt — Entwurf gesichert', 'Wiederherstellung', 'Als Entwurf laden', 'Entwurf herunterladen', 'Diesen Entwurf speichern', 'Sicherung entfernen', 'Manuskript', 'Die bisherige Analyse ist während der Bearbeitung veraltet.', 'Sicherung zur Prüfung geladen. Zum Übernehmen ausdrücklich speichern.', 'Sicherung auswählen', 'Lädt…'],
    fr: ['Écrire', 'Lire et actualiser', 'Annuler', 'Rétablir', 'Enregistrement…', 'Enregistré localement', 'Non enregistré — réessayer', 'Conflit — brouillon conservé', 'Récupération', 'Charger un brouillon', 'Télécharger le brouillon', 'Enregistrer ce brouillon', 'Supprimer la copie', 'Manuscrit', 'L’analyse précédente est obsolète pendant la modification.', 'Copie chargée pour révision. Enregistrez pour appliquer.', 'Choisir une copie', 'Chargement…'],
    es: ['Escribir', 'Leer y actualizar', 'Deshacer', 'Rehacer', 'Guardando…', 'Guardado localmente', 'Sin guardar — reintentar', 'Conflicto — borrador conservado', 'Recuperación', 'Cargar borrador', 'Descargar borrador', 'Guardar este borrador', 'Eliminar copia', 'Manuscrito', 'El análisis anterior está desactualizado durante la edición.', 'Copia cargada para revisar. Guarda para aplicar.', 'Elegir copia', 'Cargando…'],
    it: ['Scrivi', 'Leggi e aggiorna', 'Annulla', 'Ripeti', 'Salvataggio…', 'Salvato localmente', 'Non salvato — riprova', 'Conflitto — bozza conservata', 'Recupero', 'Carica bozza', 'Scarica bozza', 'Salva questa bozza', 'Elimina copia', 'Manoscritto', 'L’analisi precedente non è aggiornata durante la modifica.', 'Copia caricata per revisione. Salva per applicare.', 'Scegli una copia', 'Caricamento…'],
    pt: ['Escrever', 'Ler e atualizar', 'Desfazer', 'Refazer', 'A guardar…', 'Guardado localmente', 'Não guardado — tentar novamente', 'Conflito — rascunho preservado', 'Recuperação', 'Carregar rascunho', 'Transferir rascunho', 'Guardar este rascunho', 'Eliminar cópia', 'Manuscrito', 'A análise anterior está desatualizada durante a edição.', 'Cópia carregada para revisão. Guarde para aplicar.', 'Escolher cópia', 'A carregar…'],
    nl: ['Schrijven', 'Lezen en vernieuwen', 'Ongedaan maken', 'Opnieuw', 'Opslaan…', 'Lokaal opgeslagen', 'Niet opgeslagen — opnieuw proberen', 'Conflict — concept bewaard', 'Herstel', 'Concept laden', 'Concept downloaden', 'Dit concept opslaan', 'Kopie verwijderen', 'Manuscript', 'De eerdere analyse is tijdens het bewerken verouderd.', 'Kopie geladen ter controle. Sla expliciet op om toe te passen.', 'Kies een kopie', 'Laden…'],
  };
  const words = translations[language] || translations.en;
  const text = i => words[i];
  function button(label, id, action, help, opts) {
    opts = opts || {};
    const b = document.createElement('button');
    b.type = 'button';
    b.className = opts.className || 'ctl';
    b.id = id;
    b.setAttribute('aria-label', label);
    if (opts.icon && window.LixityIcons && typeof window.LixityIcons.svg === 'function') {
      const iconWrap = document.createElement('span');
      iconWrap.className = 'reader-control-icon';
      iconWrap.setAttribute('aria-hidden', 'true');
      iconWrap.innerHTML = window.LixityIcons.svg(opts.icon, {size: 15});
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
    b.setAttribute('data-help', newLabel);
    const span = b.querySelector('.reader-control-label, .editor-tool-label');
    if (span) span.textContent = newLabel;
    else b.textContent = newLabel;
  }
  let editor, snapshot, dirty = false, paused = false, inflight = false, pending = null, timer, maximum, loading = false;
  let loaded = false, generation = 0, openingLine = 1, lastState = '';
  const closeLabels = {
    en: ['Close writing', 'Return to reading. The editor keeps undo history; unsaved work is saved automatically, a conflict keeps your draft.'],
    de: ['Schreiben schließen', 'Zurück zum Lesen. Der Editor behält den Verlauf; ungespeicherte Arbeit wird automatisch gesichert, ein Konflikt behält deinen Entwurf.'],
    fr: ['Quitter l’écriture', 'Retour à la lecture. L’historique est conservé ; le travail est enregistré automatiquement, un conflit garde le brouillon.'],
    es: ['Cerrar escritura', 'Volver a la lectura. Se conserva el historial; el trabajo se guarda automáticamente, un conflicto conserva el borrador.'],
    it: ['Chiudi scrittura', 'Torna alla lettura. La cronologia è conservata; il lavoro è salvato automaticamente, un conflitto conserva la bozza.'],
    pt: ['Fechar escrita', 'Voltar à leitura. O histórico é mantido; o trabalho é guardado automaticamente, um conflito mantém o rascunho.'],
    nl: ['Schrijven sluiten', 'Terug naar lezen. De geschiedenis blijft bewaard; werk wordt automatisch opgeslagen, een conflict behoudt het concept.'],
  };
  const closeWords = closeLabels[language] || closeLabels.en;
  const openButton = button(text(0), 'manuscript-write', open, null, {icon: 'pen-line', className: 'ctl reader-compact-control', labelClass: 'reader-control-label'});
  const closeButton = button(closeWords[0], 'manuscript-close', close, closeWords[1], {icon: 'book-open', className: 'ctl reader-compact-control', labelClass: 'reader-control-label'});
  closeButton.hidden = true;
  const companionControls = controls.querySelector('.reader-controls');
  const openAnchor = companionControls || controls.querySelector('#reader-teleprompter') || controls.querySelector('#workbench-overview-label') || controls.querySelector('#reader-analysis-settings');
  if (openAnchor) openAnchor.before(openButton);
  else controls.append(openButton);
  const section = document.createElement('section'); section.id = 'manuscript-editor'; section.hidden = true;
  section.setAttribute('aria-label', text(13)); chapters.before(section);
  const tools = document.createElement('div'); tools.className = 'manuscript-edit-tools manuscript-editor-toolbar'; section.append(tools);
  const historyGroup = document.createElement('div'); historyGroup.className = 'editor-tool-group editor-group-history';
  const versionsGroup = document.createElement('div'); versionsGroup.className = 'editor-tool-group editor-group-versions manuscript-edit-secondary';
  const contextGroup = document.createElement('div'); contextGroup.className = 'editor-tool-group editor-group-context';
  const statusGroup = document.createElement('div'); statusGroup.className = 'editor-tool-group editor-group-status';
  tools.append(historyGroup, versionsGroup, contextGroup, statusGroup);
  const status = document.createElement('span'); status.id = 'manuscript-save-status'; status.setAttribute('role', 'status');
  const freshness = document.createElement('aside'); freshness.id = 'manuscript-analysis-freshness'; freshness.className = 'status-strip'; freshness.hidden = true; freshness.setAttribute('role', 'status'); const freshnessText = document.createElement('span'); freshnessText.className = 'warn'; freshnessText.textContent = text(14); freshness.append(freshnessText);
  document.body.prepend(freshness);
  const note = document.createElement('p'); note.className = 'ctl-note'; note.textContent = text(14);
  const host = document.createElement('div'); host.id = 'manuscript-editor-host'; host.setAttribute('spellcheck', 'false');
  const pulseLabels = {
    en: ['words', 'today', 'ASL', 'Dialogue', 'revisions', 'Session evolution', 'Baseline recorded — save an edit to see deltas.'],
    de: ['Wörter', 'heute', 'ASL', 'Dialog', 'Fassungen', 'Sitzungsverlauf', 'Basis erfasst — nach der nächsten Speicherung erscheinen Deltas.'],
    fr: ['mots', 'aujourd’hui', 'LMP', 'Dialogue', 'révisions', 'Évolution de session', 'Base enregistrée — enregistrez une modification pour voir les écarts.'],
    es: ['palabras', 'hoy', 'LMO', 'Diálogo', 'revisiones', 'Evolución de sesión', 'Base registrada — guarda un cambio para ver las diferencias.'],
    it: ['parole', 'oggi', 'LMF', 'Dialogo', 'revisioni', 'Andamento sessione', 'Base registrata — salva una modifica per vedere i delta.'],
    pt: ['palavras', 'hoje', 'CMF', 'Diálogo', 'revisões', 'Evolução da sessão', 'Base registada — guarde uma edição para ver os deltas.'],
    nl: ['woorden', 'vandaag', 'GZL', 'Dialoog', 'revisies', 'Sessie-evolutie', 'Basis vastgelegd — sla een wijziging op om delta’s te zien.'],
  };
  const pulseWords = pulseLabels[language] || pulseLabels.en;
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
  const recovery = document.createElement('select'); recovery.className = 'ctl'; recovery.id = 'manuscript-recovery'; recovery.setAttribute('aria-label', text(8));
  const retry = button(text(11), 'manuscript-save', () => {paused = false; flush();}, null, {icon: 'save', className: 'ctl primary'});
  const undoBtn = button(text(2), 'manuscript-undo', () => {if (editor) {editor.undo(); editor.focus();}}, text(2), {icon: 'undo', shortcut: 'Control+Z', iconOnly: true});
  const redoBtn = button(text(3), 'manuscript-redo', () => {if (editor) {editor.redo(); editor.focus();}}, text(3), {icon: 'redo', shortcut: 'Control+Y', iconOnly: true});
  const readBtn = button(text(1), 'manuscript-read', read, null, {icon: 'book-open'});
  historyGroup.append(undoBtn, redoBtn);
  contextGroup.append(readBtn);
  statusGroup.append(status, retry, closeButton);
  const readingLabels = {
    en: ['Back to writing', 'Reading saved revision', 'Could not open this revision. Return to writing and retry.', 'Source changed while reading. Your editor text is preserved; review before saving.'],
    de: ['Zurück zum Schreiben', 'Gespeicherte Fassung lesen', 'Diese Fassung konnte nicht geöffnet werden. Zum Schreiben zurückkehren und erneut versuchen.', 'Die Quelle wurde beim Lesen geändert. Dein Editorinhalt bleibt erhalten; vor dem Speichern prüfen.'],
    fr: ['Retour à l’écriture', 'Lecture de la version enregistrée', 'Impossible d’ouvrir cette version. Revenez à l’écriture et réessayez.', 'La source a changé pendant la lecture. Le texte de l’éditeur est conservé ; vérifiez avant d’enregistrer.'],
    es: ['Volver a escribir', 'Leer la versión guardada', 'No se pudo abrir esta versión. Vuelve a escribir e inténtalo de nuevo.', 'La fuente cambió durante la lectura. El texto del editor se conserva; revísalo antes de guardar.'],
    it: ['Torna alla scrittura', 'Lettura della versione salvata', 'Impossibile aprire questa versione. Torna alla scrittura e riprova.', 'La fonte è cambiata durante la lettura. Il testo dell’editor è conservato; verifica prima di salvare.'],
    pt: ['Voltar à escrita', 'Ler a versão guardada', 'Não foi possível abrir esta versão. Volte à escrita e tente novamente.', 'A fonte mudou durante a leitura. O texto do editor foi preservado; reveja antes de guardar.'],
    nl: ['Terug naar schrijven', 'Opgeslagen versie lezen', 'Deze versie kon niet worden geopend. Ga terug naar schrijven en probeer opnieuw.', 'De bron is tijdens het lezen gewijzigd. Je editortekst is bewaard; controleer voor het opslaan.'],
  };
  const readingWords = readingLabels[language] || readingLabels.en;
  const reading = document.createElement('dialog'); reading.id = 'manuscript-reading';
  reading.setAttribute('aria-label', readingWords[1]);
  const readingBar = document.createElement('div'); readingBar.className = 'manuscript-edit-tools manuscript-reading-bar';
  const readingStatus = document.createElement('span'); readingStatus.id = 'manuscript-reading-status'; readingStatus.setAttribute('role', 'status');
  const reviewLabels = {en:'Review research links', de:'Recherchebezüge prüfen', fr:'Vérifier les liens de recherche', es:'Revisar vínculos de investigación', it:'Verifica i collegamenti di ricerca', pt:'Rever ligações de pesquisa', nl:'Onderzoeksverwijzingen controleren'};
  const reviewLinks = button(reviewLabels[language] || reviewLabels.en, 'manuscript-review-links', () => {
    const bridge = frame && frame.contentWindow && frame.contentWindow.LixityManuscriptLinks;
    if (bridge && bridge.review) bridge.review(null);
  }, null, {icon: 'link'});
  reviewLinks.hidden = true;
  const exitLabels = {
    en: ['Discard unsaved research work and return to writing?', 'Research is still saving. Wait before returning.', 'This selection cannot be mapped exactly to the source. Your writing position is unchanged.'],
    de: ['Ungespeicherte Recherche verwerfen und zum Schreiben zurückkehren?', 'Die Recherche wird noch gespeichert. Bitte warten.', 'Diese Auswahl lässt sich nicht exakt der Quelle zuordnen. Die Schreibposition bleibt erhalten.'],
    fr: ['Abandonner la recherche non enregistrée et revenir à l’écriture ?', 'La recherche est en cours d’enregistrement. Patientez.', 'Cette sélection ne correspond pas exactement à la source. La position reste inchangée.'],
    es: ['¿Descartar la investigación sin guardar y volver a escribir?', 'La investigación se está guardando. Espera.', 'No se puede ubicar esta selección exactamente en la fuente. La posición no cambia.'],
    it: ['Scartare la ricerca non salvata e tornare alla scrittura?', 'Salvataggio della ricerca in corso. Attendi.', 'La selezione non corrisponde esattamente alla fonte. La posizione non cambia.'],
    pt: ['Descartar a pesquisa não guardada e voltar à escrita?', 'A pesquisa está a ser guardada. Aguarde.', 'Não é possível localizar exatamente esta seleção na fonte. A posição mantém-se.'],
    nl: ['Niet opgeslagen onderzoek verwerpen en terug naar schrijven?', 'Onderzoek wordt nog opgeslagen. Wacht even.', 'Deze selectie is niet exact terug te vinden in de bron. De schrijfpositie blijft behouden.'],
  };
  const exitWords = exitLabels[language] || exitLabels.en;
  function closeReading() {
    const drafts = frame && frame.contentWindow && frame.contentWindow.LixityResearchDrafts;
    if (drafts && drafts.busy()) {readingStatus.textContent = exitWords[1]; return;}
    if (drafts && drafts.hasPendingWork() && !confirm(exitWords[0])) return;
    reading.close();
  }
  const returnWrite = button(readingWords[0], 'manuscript-return-write', closeReading, readingWords[0], {icon: 'arrow-left', shortcut: 'Escape'});
  readingBar.append(returnWrite, reviewLinks, readingStatus);
  readingBar.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !event.isComposing && !event.defaultPrevented) {
      event.preventDefault(); event.stopPropagation(); closeReading();
    }
  });
  let frame = null;
  reading.append(readingBar); document.body.append(reading);
  reading.addEventListener('cancel', event => {event.preventDefault(); closeReading();});
  let readGeneration = 0, readingRevision = '', closingRead = false, readerScroll = 0, selectedReading = null;
  const sourceBlocks = '#chapters .ptext[data-start], #chapters .reader-structural[data-start]';
  async function read() {
    if (!editor || paused || inflight || reading.open || closingRead) return;
    await flush(); if (dirty || inflight || paused) return;
    readGeneration = generation; readingRevision = snapshot.revision; selectedReading = null;
    frame = document.createElement('iframe'); frame.id = 'manuscript-reading-frame';
    frame.title = readingWords[1]; frame.addEventListener('load', loadedReading);
    readingStatus.textContent = text(17); frame.hidden = true; reviewLinks.hidden = true;
    frame.src = api + '/manuscript-view?' + new URLSearchParams({document: snapshot.document, revision: readingRevision});
    reading.append(frame);
    reading.showModal();
    if (window.LixityMotion && window.LixityMotion.surface) window.LixityMotion.surface(readingBar);
    returnWrite.focus();
  }
  function loadedReading(event) {
    if (!reading.open || event.target !== frame) return;
    const body = frame.contentDocument && frame.contentDocument.body;
    if (readGeneration !== generation || !body || body.dataset.editorRevision !== readingRevision ||
        body.dataset.editorDocument !== snapshot.document) {
      frame.hidden = true; readingStatus.textContent = readingWords[2]; return;
    }
    frame.contentDocument.documentElement.style.colorScheme = getComputedStyle(document.documentElement).colorScheme;
    frame.hidden = false;
    // Firefox clears the native iframe selection when focus returns to the
    // parent. Retain its range while the reader still owns focus, then validate
    // the source context again when returning to writing.
    frame.contentDocument.addEventListener('selectionchange', () => {
      if (frame && document.activeElement === frame) {
        const selection = frame.contentWindow.getSelection();
        selectedReading = selection && !selection.isCollapsed && selection.rangeCount ? selection.getRangeAt(0).cloneRange() : null;
      }
    });
    reviewLinks.hidden = !(frame.contentWindow.LixityManuscriptLinks && frame.contentWindow.LixityManuscriptLinks.review);
    readingStatus.textContent = readingWords[1];
    const line = editor.currentLine();
    const target = Array.from(body.querySelectorAll(sourceBlocks)).find(node => Number(node.dataset.end || node.dataset.start) >= line);
    if (target) target.scrollIntoView({block: 'center'});
    readerScroll = frame.contentWindow.scrollY;
  }
  function readerSelection() {
    const selection = frame.contentWindow.getSelection();
    const range = selection && !selection.isCollapsed && selection.rangeCount ? selection.getRangeAt(0) : selectedReading;
    if (!range) return null;
    const node = range.startContainer;
    const prose = (node.nodeType === 1 ? node : node.parentElement).closest('.ptext-inner > p');
    if (!prose || !prose.contains(range.endContainer)) return {invalid: true};
    const block = prose.closest('.ptext[data-start][data-end]');
    if (!block || readGeneration !== generation || snapshot.revision !== readingRevision) return {invalid: true};
    // Source line bounds disambiguate repeated paragraphs; complete literal
    // context disambiguates repeated quotations inside one paragraph. Markdown
    // transformations are deliberately rejected instead of guessed.
    const value = editor.text(), lines = value.split('\n');
    const first = Number(block.dataset.start), last = Number(block.dataset.end);
    if (!Number.isInteger(first) || !Number.isInteger(last) || first < 1 || last < first || last > lines.length) return {invalid: true};
    const context = prose.textContent, source = lines.slice(first - 1, last).join('\n');
    const offset = source.indexOf(context);
    if (!context || offset < 0 || source.indexOf(context, offset + 1) !== -1) return {invalid: true};
    const prefix = range.cloneRange(); prefix.selectNodeContents(prose); prefix.setEnd(range.startContainer, range.startOffset);
    const quote = range.toString(), start = prefix.toString().length;
    const from = lines.slice(0, first - 1).reduce((sum, line) => sum + line.length + 1, 0) + offset + start;
    if (!quote || value.slice(from, from + quote.length) !== quote) return {invalid: true};
    return {from, to: from + quote.length};
  }
  reading.addEventListener('close', async () => {
    closingRead = true; document.getElementById('manuscript-read').disabled = true;
    const validatingRevision = snapshot.revision, validatingGeneration = generation;
    // Retain the editor's selection/history. Only map the reader position when
    // it is still displaying the exact revision opened by this editor.
    try {
      const body = frame.contentDocument && frame.contentDocument.body;
      const selected = body && body.dataset.editorRevision === readingRevision && body.dataset.editorDocument === snapshot.document && readGeneration === generation ? readerSelection() : {invalid: true};
      selectedReading = null;
      let visibleLine = null;
      if (!selected && body && body.dataset.editorRevision === readingRevision && Math.abs(frame.contentWindow.scrollY - readerScroll) > 2) {
        const visible = Array.from(body.querySelectorAll(sourceBlocks)).find(node => node.getBoundingClientRect().bottom > 80);
        if (visible) visibleLine = Number(visible.dataset.start);
      }
      // Dispose only the reading session (including media/timers). The editor
      // and its undo history remain mounted. Each revision gets a fresh frame.
      frame.remove(); frame = null;
      const current = await request('/manuscript-edit');
      if (generation !== validatingGeneration || snapshot.revision !== validatingRevision) return;
      if (current.document !== snapshot.document || current.revision !== snapshot.revision) {
        paused = true; show('conflict', readingWords[3]);
      } else if (selected) {
        if (selected.invalid || !editor.selectRange(selected.from, selected.to)) show('saved', exitWords[2]);
      } else if (visibleLine !== null) editor.line(visibleLine);
    } catch (error) {if (generation === validatingGeneration && snapshot.revision === validatingRevision) {paused = true; show('error', error.message);}}
    finally {closingRead = false; document.getElementById('manuscript-read').disabled = paused || inflight; editor.focus();}
  });
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
      note.textContent = text(14); show('unsaved', text(15)); editor.focus();
    } catch (error) {show('error', error.message);}
  }, null, {icon: 'rotate-ccw'});
  const downloadBtn = button(text(10), 'manuscript-download', download, text(10), {icon: 'download', iconOnly: true});
  const discardBtn = button(text(12), 'manuscript-discard', async () => {
    if (!recovery.value || !confirm(text(12) + '?')) return;
    try {await request('/manuscript-edit-discard', {document: snapshot.document, id: recovery.value}); await refreshRecovery();}
    catch (error) {show('error', error.message);}
  }, text(12), {icon: 'trash-2', iconOnly: true});
  function syncRecoveryActions() {
    const hasSelection = Boolean(recovery.value);
    recoverBtn.hidden = !hasSelection;
    discardBtn.hidden = !hasSelection;
  }
  recovery.addEventListener('change', syncRecoveryActions);
  syncRecoveryActions();
  const comparisonLabels = {
    en:['Find / replace','Compare versions','Last acknowledged text','Current file','Draft to review','Use as draft','Cancel','Review the text before saving. Using it as a draft does not write the manuscript.','The document changed. Reload before comparing.'],
    de:['Suchen / Ersetzen','Fassungen vergleichen','Zuletzt bestätigter Text','Aktuelle Datei','Entwurf zur Prüfung','Als Entwurf übernehmen','Abbrechen','Prüfe den Text vor dem Speichern. Die Übernahme als Entwurf schreibt das Manuskript noch nicht.','Das Dokument hat sich geändert. Vor dem Vergleich neu laden.'],
    fr:['Rechercher / remplacer','Comparer les versions','Dernier texte confirmé','Fichier actuel','Brouillon à vérifier','Utiliser comme brouillon','Annuler','Vérifiez avant d’enregistrer. Utiliser le brouillon ne modifie pas encore le manuscrit.','Le document a changé. Rechargez avant de comparer.'],
    es:['Buscar / reemplazar','Comparar versiones','Último texto confirmado','Archivo actual','Borrador para revisar','Usar como borrador','Cancelar','Revisa antes de guardar. Usar el borrador todavía no modifica el manuscrito.','El documento ha cambiado. Recarga antes de comparar.'],
    it:['Cerca / sostituisci','Confronta versioni','Ultimo testo confermato','File attuale','Bozza da verificare','Usa come bozza','Annulla','Verifica prima di salvare. Usare la bozza non modifica ancora il manoscritto.','Il documento è cambiato. Ricarica prima del confronto.'],
    pt:['Procurar / substituir','Comparar versões','Último texto confirmado','Ficheiro atual','Rascunho a rever','Usar como rascunho','Cancelar','Revê antes de guardar. Usar o rascunho ainda não altera o manuscrito.','O documento mudou. Recarrega antes de comparar.'],
    nl:['Zoeken / vervangen','Versies vergelijken','Laatst bevestigde tekst','Huidig bestand','Concept ter controle','Als concept gebruiken','Annuleren','Controleer voor het opslaan. Het concept gebruiken wijzigt het manuscript nog niet.','Het document is veranderd. Herlaad voor het vergelijken.'],
  };
  const comparisonWords = comparisonLabels[language] || comparisonLabels.en;
  const searchBtn = button(comparisonWords[0], 'manuscript-search', () => editor && editor.search(), comparisonWords[0], {icon: 'search', shortcut: 'Control+F'});
  historyGroup.append(searchBtn);
  const comparison = document.createElement('dialog'); comparison.id = 'manuscript-comparison'; comparison.setAttribute('aria-label', comparisonWords[1]);
  const comparisonTitle = document.createElement('h2'); comparisonTitle.textContent = comparisonWords[1];
  const comparisonNote = document.createElement('p'); comparisonNote.textContent = comparisonWords[7];
  const comparisonGrid = document.createElement('div'); comparisonGrid.className = 'manuscript-comparison-grid';
  const comparisonFields = ['base','current','draft'].map((name, index) => {
    const label = document.createElement('label'); label.textContent = comparisonWords[index+2];
    const identity = document.createElement('small'); identity.style.display = 'block';
    const summary = document.createElement('small'); summary.className = 'manuscript-compare-metrics'; summary.style.display = 'block';
    const field = document.createElement('textarea'); field.id = 'manuscript-comparison-' + name; field.readOnly = index !== 2;
    label.append(identity,summary,field); comparisonGrid.append(label); return {field,identity,summary};
  });
  let comparisonSnapshot = null, comparisonLoading = false, comparisonOriginal = '';
  const discardComparison = {en:'Discard changes to this comparison draft?',de:'Änderungen an diesem Vergleichsentwurf verwerfen?',fr:'Abandonner les modifications de ce brouillon ?',es:'¿Descartar los cambios de este borrador?',it:'Scartare le modifiche a questa bozza?',pt:'Descartar as alterações deste rascunho?',nl:'Wijzigingen aan dit concept verwerpen?'};
  const comparisonDirty = () => comparison.open && comparisonFields[2].field.value !== comparisonOriginal;
  function closeComparison() {
    if (!comparisonDirty() || confirm(discardComparison[language] || discardComparison.en)) comparison.close();
  }
  comparison.addEventListener('cancel', event => {event.preventDefault(); closeComparison();});
  const comparisonUse = button(comparisonWords[5], 'manuscript-comparison-use', () => {
    if (!comparisonSnapshot || inflight) return;
    paused = true; pending = null; snapshot = comparisonSnapshot; comparisonSnapshot = null;
    editor.replace(comparisonFields[2].field.value); dirty = true;
    comparison.close(); show('unsaved', text(15)); editor.focus();
  }, null, {icon: 'check', className: 'ctl primary'});
  const comparisonCancel = button(comparisonWords[6], 'manuscript-comparison-cancel', closeComparison, comparisonWords[6], {icon: 'x', shortcut: 'Escape'});
  const comparisonActions = document.createElement('div'); comparisonActions.className = 'manuscript-edit-tools'; comparisonActions.append(comparisonCancel,comparisonUse);
  comparison.append(comparisonTitle,comparisonNote,comparisonGrid,comparisonActions); document.body.append(comparison);
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
      comparisonFields[2].field.value = recovered ? recovered.text : editor.text(); comparisonFields[2].identity.textContent = recovered ? recovered.revision.slice(0,12) : text(6);
      comparisonOriginal = comparisonFields[2].field.value;
      updateComparisonSummaries(baseRevision, current.revision);
      comparison.showModal();
      if (window.LixityMotion && window.LixityMotion.surface) window.LixityMotion.surface(comparisonGrid);
      comparisonCancel.focus();
    } catch (error) {show('error',error.message);}
    finally {comparisonLoading = false;}
  }, null, {icon: 'git-compare'});
  versionsGroup.append(recovery, recoverBtn, discardBtn, compareBtn, downloadBtn);
  contextGroup.append(reload);
  function dockCompanionTools(intoEditor) {
    if (!companionControls) return;
    if (intoEditor) contextGroup.prepend(companionControls);
    else openButton.after(companionControls);
  }
  section.append(host, pulseWrap);
  const css = document.createElement('style'); css.textContent = `
    #manuscript-comparison {width:min(1200px,95vw);max-height:92dvh;box-sizing:border-box;overflow:auto;background:var(--surface);color:var(--fg);border:1px solid var(--line);border-radius:var(--radius-lg,16px);box-shadow:var(--shadow-modal);padding:24px;}
    .manuscript-comparison-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:16px 0;}
    .manuscript-comparison-grid label {font-weight:var(--weight-semibold,600);font-size:var(--text-small,.875rem);}
    .manuscript-comparison-grid small {color:var(--muted);font-family:var(--font-mono,monospace);margin-top:2px;}
    .manuscript-comparison-grid textarea {display:block;box-sizing:border-box;width:100%;height:48vh;margin-top:8px;padding:12px;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:var(--radius-sm,8px);font-family:var(--font-title,serif);font-size:1rem;line-height:1.6;resize:vertical;}
    @media(max-width:700px) {.manuscript-comparison-grid {grid-template-columns:1fr;}.manuscript-comparison-grid textarea {height:24vh;}}
    #manuscript-analysis-freshness {position:relative;z-index:20;margin:0;padding:.2rem .5rem;background:transparent;border:0;box-shadow:none;font-size:var(--text-note,.8125rem);color:var(--muted);}
    #manuscript-analysis-freshness[hidden] {display:none;}
    #manuscript-reading {width:100vw;max-width:none;height:100dvh;max-height:none;margin:0;padding:8px 12px;box-sizing:border-box;border:0;background:var(--bg);color:var(--fg);}
    #manuscript-reading[open] {display:flex;flex-direction:column;}
    #manuscript-reading .manuscript-reading-bar {flex:none;margin:0 0 8px;padding:6px 12px;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius,12px);box-shadow:var(--shadow);}
    #manuscript-reading-status {margin-inline-start:auto;font-size:var(--text-small,.8125rem);color:var(--muted);font-weight:500;}
    #manuscript-reading-frame {flex:1;width:100%;min-height:0;border:0;border-radius:var(--radius,12px);background:var(--bg);}
    #manuscript-reading-frame[hidden] {display:none;}
    #manuscript-editor {min-width:0;padding:4px 0 24px;width:100%;}
    .manuscript-edit-tools {display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:0;}
    .manuscript-editor-toolbar {container:editor-tools / inline-size;position:sticky;top:0;z-index:14;flex-wrap:nowrap;gap:6px;padding:5px 8px;margin-bottom:14px;background:color-mix(in srgb,var(--surface) 92%,transparent);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border:1px solid var(--line);border-radius:var(--radius,12px);box-shadow:var(--shadow);}
    .editor-tool-group {display:inline-flex;align-items:center;gap:4px;min-width:0;flex-shrink:0;}
    .editor-group-versions,.editor-group-context {padding-inline-start:6px;border-inline-start:1px solid var(--line);}
    .editor-group-status {margin-inline-start:auto;padding-inline-start:6px;gap:6px;}
    .manuscript-editor-toolbar .reader-controls {display:inline-flex;align-items:center;flex-basis:auto;gap:4px;}
    .manuscript-editor-toolbar button.ctl {padding:.3rem .5rem;min-height:2.25rem;white-space:nowrap;}
    .manuscript-editor-toolbar button.editor-icon-only .editor-tool-label {display:none;}
    .manuscript-editor-toolbar button.editor-icon-only {padding-inline:.45rem;min-width:2.25rem;justify-content:center;}
    .manuscript-editor-toolbar button.ctl:not(.primary),
    .manuscript-reading-bar button.ctl:not(.primary) {border-color:transparent;background:transparent;}
    .manuscript-editor-toolbar button.ctl:not(.primary):hover,
    .manuscript-reading-bar button.ctl:not(.primary):hover {background:var(--surface-hover);border-color:var(--line);color:var(--fg);}
    #manuscript-save-status {font-size:var(--text-micro,.8125rem);color:var(--muted);padding:3px 10px;border-radius:var(--radius-pill,999px);background:var(--surface-raised,var(--bg));border:1px solid var(--line);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:14rem;}
    #manuscript-save-status[data-state=saved] {color:var(--status-success-fg,var(--present-ink));background:var(--status-success-bg,var(--present-light));border-color:var(--status-success-border,transparent);}
    #manuscript-save-status[data-state=conflict],#manuscript-save-status[data-state=error] {color:var(--flag);background:var(--flag-light);border-color:color-mix(in srgb,var(--flag) 30%,transparent);font-weight:600;}
    #manuscript-recovery {max-width:11rem;min-width:6.5rem;flex:0 1 11rem;min-height:2.25rem;padding-block:.25rem;}
    #manuscript-editor-host {min-width:0;max-width:min(100%,calc(var(--reader-measure,68ch) + 8rem));margin:0 auto;overflow:hidden;border-radius:var(--radius-lg,16px);box-shadow:0 6px 24px rgba(0,0,0,.05);}
    #manuscript-session-pulse-wrap {max-width:min(100%,calc(var(--reader-measure,68ch) + 8rem));margin:8px auto 0;display:flex;flex-direction:column;align-items:flex-end;gap:6px;}
    .manuscript-pulse-btn {max-width:100%;white-space:normal;text-align:right;line-height:1.35;font-size:var(--text-micro,.8125rem);color:var(--muted);background:transparent;border:1px solid transparent;border-radius:var(--radius-pill,999px);padding:3px 10px;cursor:pointer;}
    .manuscript-pulse-btn:hover {background:var(--surface-hover);border-color:var(--line);color:var(--fg);}
    #manuscript-pulse-popover {background:var(--surface);border:1px solid var(--line);border-radius:var(--radius,12px);padding:10px 14px;box-shadow:var(--shadow);font-size:var(--text-micro,.8125rem);color:var(--muted);max-width:100%;box-sizing:border-box;}
    #manuscript-pulse-popover svg {display:block;margin-top:6px;color:var(--accent,currentColor);}
    .manuscript-compare-metrics {font-weight:400;color:var(--muted);margin-top:2px;}
    #manuscript-editor-host .cm-line.lixity-session-edited {box-shadow:inset 2px 0 0 var(--accent,#2f5aa8);}
    @container editor-tools (max-width: 76rem) {
      #manuscript-search .editor-tool-label,
      .manuscript-editor-toolbar #workspace-reader-toggle .reader-control-label {display:none;}
      #manuscript-search,
      .manuscript-editor-toolbar #workspace-reader-toggle {padding-inline:.45rem;min-width:2.25rem;justify-content:center;}
      #manuscript-recovery {max-width:9rem;flex-basis:9rem;}
    }
    @container editor-tools (max-width: 60rem) {
      #manuscript-read .editor-tool-label,
      #manuscript-recover .editor-tool-label,
      .manuscript-editor-toolbar #manuscript-close .reader-control-label {display:none;}
      #manuscript-read,
      #manuscript-recover,
      .manuscript-editor-toolbar #manuscript-close {padding-inline:.45rem;min-width:2.25rem;justify-content:center;}
      #manuscript-recovery {max-width:7.5rem;flex-basis:7.5rem;}
      #manuscript-save-status {max-width:9rem;padding-inline:7px;}
    }
    @media(max-width:760px) {
      .manuscript-editor-toolbar {flex-wrap:wrap;}
      .editor-tool-group {flex-wrap:wrap;flex-shrink:1;max-width:100%;}
      .editor-group-versions,.editor-group-context {padding-inline-start:0;border-inline-start:0;}
      .editor-group-status {margin-inline-start:0;padding-inline-start:0;}
      #manuscript-compare .editor-tool-label {display:none;}
    }
    @media(max-width:600px) {
      .manuscript-editor-toolbar button.ctl, #manuscript-recovery {min-height:2.75rem;}
      #manuscript-recovery {min-width:0;flex:1 1 8rem;max-width:100%;}
      #manuscript-session-pulse-wrap {align-items:stretch;}
      .manuscript-pulse-btn {text-align:center;min-height:2.75rem;}
      #manuscript-pulse-popover {width:100%;}
      #manuscript-comparison {width:calc(100vw - 16px);padding:14px;}
      .manuscript-comparison-actions {flex-wrap:wrap;gap:8px;}
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
    readBtn.disabled = paused || inflight || closingRead;
    readBtn.hidden = paused;
    reload.hidden = !paused;
  }
  let latestTimeline = [];
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
  function fmtSigned(v, digits) {
    if (v === null || v === undefined || Number.isNaN(v)) return '';
    const sign = v > 0 ? '+' : '';
    return sign + fmtNum(v, digits);
  }
  function quickTextStats(raw) {
    const clean = (raw || '').replace(/<!--[\s\S]*?-->/g, '').replace(/^#+.*$/gm, '');
    const tokens = clean.match(/[\p{L}\p{N}_]+/gu) || [];
    const sents = clean.split(/[.!?]+(?:\s|$)/).filter(s => s.trim().length > 0);
    const dlg = (clean.match(/[„"«»‹›‚‘'][^"”»›’']+[“"»«›‹’']/g) || []).join(' ').match(/[\p{L}\p{N}_]+/gu) || [];
    return {
      words: tokens.length,
      asl: sents.length ? tokens.length / sents.length : null,
      dialogue_ratio: tokens.length ? (dlg.length / tokens.length) * 100 : null,
    };
  }
  function formatMetricsLine(snap, deltas) {
    if (!snap) return '';
    const parts = [fmtNum(snap.words, 0) + ' ' + pulseWords[0]];
    if (deltas && deltas.words !== null && deltas.words !== undefined && deltas.words !== 0) {
      parts[0] += ' (' + fmtSigned(deltas.words, 0) + ' ' + pulseWords[1] + ')';
    }
    if (snap.asl !== null && snap.asl !== undefined) {
      let aslPart = pulseWords[2] + ' ' + fmtNum(snap.asl, 1);
      if (deltas && deltas.asl !== null && deltas.asl !== undefined && Math.abs(deltas.asl) >= 0.05) {
        aslPart += ' (Δ ' + fmtSigned(deltas.asl, 1) + ')';
      }
      parts.push(aslPart);
    }
    if (snap.dialogue_ratio !== null && snap.dialogue_ratio !== undefined) {
      parts.push(pulseWords[3] + ' ' + fmtNum(snap.dialogue_ratio, 0) + ' %');
    }
    return parts.join(' · ');
  }
  function updateComparisonSummaries(baseRev, currentRev) {
    const byRev = new Map(latestTimeline.map(r => [r.revision, r]));
    const baseSnap = byRev.get(baseRev) || quickTextStats(comparisonFields[0].field.value);
    const curSnap = byRev.get(currentRev) || quickTextStats(comparisonFields[1].field.value);
    const draftSnap = quickTextStats(comparisonFields[2].field.value);
    comparisonFields[0].summary.textContent = formatMetricsLine(baseSnap, null);
    comparisonFields[1].summary.textContent = formatMetricsLine(curSnap, {
      words: curSnap.words - baseSnap.words,
      asl: curSnap.asl !== null && baseSnap.asl !== null ? curSnap.asl - baseSnap.asl : null,
    });
    comparisonFields[2].summary.textContent = formatMetricsLine(draftSnap, {
      words: draftSnap.words - curSnap.words,
      asl: draftSnap.asl !== null && curSnap.asl !== null ? draftSnap.asl - curSnap.asl : null,
    });
  }
  comparisonFields[2].field.addEventListener('input', () => {
    if (comparison.open && snapshot && comparisonSnapshot) {
      updateComparisonSummaries(snapshot.revision, comparisonSnapshot.revision);
    }
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
    try {
      const [deltaRes, tlRes] = await Promise.all([
        request('/manuscript-delta'),
        request('/manuscript-timeline?limit=14'),
      ]);
      latestTimeline = tlRes.revisions || [];
      if (!deltaRes.current) {pulseWrap.hidden = true; return;}
      pulseBtn.textContent = formatMetricsLine(deltaRes.current, deltaRes.has_baseline ? deltaRes.deltas : null);
      pulseWrap.hidden = false;
      const head = document.createElement('div');
      head.textContent = pulseWords[5] + ' (' + String(latestTimeline.length) + ' ' + pulseWords[4] + ')';
      pulsePopover.replaceChildren(head);
      if (latestTimeline.length >= 2) {
        const chart = document.createElement('div');
        chart.innerHTML = renderSparklineSvg(latestTimeline);
        pulsePopover.append(chart);
      } else {
        const noteEl = document.createElement('div');
        noteEl.textContent = pulseWords[6];
        pulsePopover.append(noteEl);
      }
    } catch (_) {
      pulseWrap.hidden = true;
    }
  }
  async function request(path, payload) {
    const response = await fetch(api + path, payload ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)} : {});
    const data = await response.json(); if (!response.ok || !data.ok) {const error = new Error(data.message || text(6)); error.conflict = response.status === 409; throw error;} return data;
  }
  function changes() {
    generation++;
    dirty = true; show('unsaved', text(6));
    scheduleGutterMark();
    if (paused) return;
    clearTimeout(timer); timer = setTimeout(flush, 800);
    if (!maximum) maximum = setTimeout(flush, 4000);
  }
  async function flush() {
    clearTimeout(timer); clearTimeout(maximum); maximum = null;
    if (!editor || !dirty || inflight || paused) return;
    inflight = true; show('saving', text(4));
    if (!pending) pending = {document: snapshot.document, revision: snapshot.revision,
      operation: crypto.randomUUID().replaceAll('-', ''), text: editor.text()};
    const sent = pending;
    try {
      const result = await request('/manuscript-edit', sent);
      snapshot.revision = result.revision; snapshot.text = sent.text; pending = null; dirty = editor.text() !== sent.text;
      show(dirty ? 'unsaved' : 'saved', text(dirty ? 6 : 5));
      refreshPulse().catch(() => {});
    } catch (error) {paused = true; show(error.conflict ? 'conflict' : 'error', text(error.conflict ? 7 : 6) + ': ' + error.message); await refreshRecovery().catch(() => {});}
    finally {inflight = false; document.getElementById('manuscript-read').disabled = paused || closingRead;
      if (dirty && !paused) timer = setTimeout(flush, 800);}
  }
  function download() {
    if (!editor) return;
    const url = URL.createObjectURL(new Blob([editor.text()], {type: 'text/markdown;charset=utf-8'}));
    const a = document.createElement('a'); a.href = url; a.download = 'manuscript-draft.md'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function refreshRecovery() {
    const current = await request('/manuscript-edit');
    recovery.replaceChildren(new Option(text(16), ''));
    current.recovery.forEach(row => {const option = new Option((row.kind === 'draft' ? text(6) : text(8)) + ' · ' + new Date(row.created * 1000).toLocaleString(), row.id); option.dataset.kind = row.kind; recovery.append(option);});
    syncRecoveryActions();
  }
  async function open() {
    if (loading) return;
    if (editor) {
      dockCompanionTools(true);
      section.hidden = false; document.body.classList.add('manuscript-writing');
      openButton.hidden = true; closeButton.hidden = false;
      if (window.LixityChrome && window.LixityChrome.reveal) window.LixityChrome.reveal();
      if (window.LixityMotion && window.LixityMotion.surface) window.LixityMotion.surface(section);
      editor.focus(); return;
    }
    loading = true; openButton.disabled = true; setButtonLabel(openButton, text(17));
    try {
      snapshot = await request('/manuscript-edit');
      const visible = Array.from(chapters.querySelectorAll('[data-start]')).find(node => node.getBoundingClientRect().bottom > controls.getBoundingClientRect().bottom);
      openingLine = visible ? Number(visible.dataset.start) : 1;
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
    if (reading.open || comparison.open) return;
    if (inflight) return;
    if (dirty && !paused) await flush();
    if (paused) return;
    // Keep the mounted editor and its undo history; only leave the writing surface.
    section.hidden = true; document.body.classList.remove('manuscript-writing');
    dockCompanionTools(false);
    closeButton.hidden = true; openButton.hidden = false;
    if (window.LixityChrome && window.LixityChrome.reveal) window.LixityChrome.reveal();
    if (window.LixityMotion && window.LixityMotion.surface) window.LixityMotion.surface(chapters);
    if (window.LixityLog && window.LixityLog.debug) window.LixityLog.debug('manuscript-editor:close', {dirty, paused});
    openButton.focus();
  }
  window.addEventListener('beforeunload', event => {if (dirty || inflight || comparisonDirty()) {event.preventDefault(); event.returnValue = '';}});
  document.addEventListener('visibilitychange', () => {if (document.hidden) flush();});
  // Keep shortcuts from the read-only manuscript layer away from the editor.
  host.addEventListener('keydown', event => event.stopPropagation());
})();
