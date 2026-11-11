import {EditorState} from '@codemirror/state';
import {EditorView, keymap} from '@codemirror/view';
import {defaultKeymap, history, historyKeymap, undo, redo} from '@codemirror/commands';
import {markdown} from '@codemirror/lang-markdown';
import {search, searchKeymap, openSearchPanel} from '@codemirror/search';

const searchTerms = ['Find','Replace','next','previous','all','match case','regexp','by word','replace','replace all','close','current match','on line','replaced $ matches','replaced match on line $','Go to line','go'];
const searchTranslations = {
  de:['Suchen','Ersetzen','Weiter','Zurück','Alle','Groß-/Kleinschreibung','Regulärer Ausdruck','Ganzes Wort','Ersetzen','Alle ersetzen','Schließen','Aktueller Treffer','in Zeile','$ Treffer ersetzt','Treffer in Zeile $ ersetzt','Zur Zeile','Los'],
  fr:['Rechercher','Remplacer','Suivant','Précédent','Tous','Respecter la casse','Expression régulière','Mot entier','Remplacer','Tout remplacer','Fermer','Résultat actuel','à la ligne','$ résultats remplacés','Résultat remplacé à la ligne $','Aller à la ligne','Aller'],
  es:['Buscar','Reemplazar','Siguiente','Anterior','Todos','Distinguir mayúsculas','Expresión regular','Palabra completa','Reemplazar','Reemplazar todo','Cerrar','Coincidencia actual','en la línea','$ coincidencias reemplazadas','Coincidencia reemplazada en la línea $','Ir a la línea','Ir'],
  it:['Cerca','Sostituisci','Successivo','Precedente','Tutti','Maiuscole/minuscole','Espressione regolare','Parola intera','Sostituisci','Sostituisci tutto','Chiudi','Risultato attuale','alla riga','$ risultati sostituiti','Risultato sostituito alla riga $','Vai alla riga','Vai'],
  pt:['Procurar','Substituir','Seguinte','Anterior','Todos','Distinguir maiúsculas','Expressão regular','Palavra inteira','Substituir','Substituir tudo','Fechar','Resultado atual','na linha','$ resultados substituídos','Resultado substituído na linha $','Ir para a linha','Ir'],
  nl:['Zoeken','Vervangen','Volgende','Vorige','Alle','Hoofdlettergevoelig','Reguliere expressie','Heel woord','Vervangen','Alles vervangen','Sluiten','Huidige treffer','op regel','$ treffers vervangen','Treffer op regel $ vervangen','Ga naar regel','Ga'],
};

export function mount(parent, text, onChange, language, label) {
  const view = new EditorView({parent, state: EditorState.create({doc: text, extensions: [
    history(), search({top:true}), keymap.of([...searchKeymap, ...defaultKeymap, ...historyKeymap]), markdown(), EditorView.lineWrapping,
    EditorState.phrases.of(Object.fromEntries(searchTerms.map((term,i) => [term, (searchTranslations[language] || searchTerms)[i]]))),
    EditorView.contentAttributes.of({spellcheck: 'false', autocorrect: 'off', autocapitalize: 'off', lang: language, 'aria-label': label}),
    EditorView.theme({
      '&': {backgroundColor: 'var(--surface)', color: 'var(--fg)', borderRadius: 'var(--radius-lg, 16px)', border: '1px solid var(--line, transparent)'},
      '.cm-scroller': {fontFamily: 'var(--font-title)', fontSize: 'var(--reader-font-size, 1.125rem)', lineHeight: 'var(--reader-leading, 1.8)', overflow: 'auto', height: '66vh'},
      '.cm-content': {padding: '28px max(24px, calc((100% - 68ch) / 2))', caretColor: 'var(--accent, var(--fg))'},
      '&.cm-focused': {outline: 'none', borderColor: 'color-mix(in srgb, var(--accent) 45%, var(--line))', boxShadow: '0 0 0 3px var(--accent-focus, rgba(41, 73, 204, 0.18))'},
      '.cm-line': {padding: '0'},
      '.cm-selectionBackground': {backgroundColor: 'var(--accent-light)'},
      '.cm-panels': {backgroundColor: 'var(--surface-raised, var(--surface))', color: 'var(--fg)', borderBottom: '1px solid var(--line)'},
      '.cm-search': {padding: '8px 12px', fontFamily: 'var(--font, sans-serif)', fontSize: 'var(--text-control, .875rem)', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '6px'},
      '.cm-search input': {maxWidth: '100%', backgroundColor: 'var(--surface)', color: 'var(--fg)', border: '1px solid var(--line-strong)', borderRadius: 'var(--radius-sm, 8px)', padding: '4px 8px'},
      '.cm-search button': {background: 'var(--surface)', color: 'var(--fg)', border: '1px solid var(--line)', borderRadius: 'var(--radius-sm, 8px)', padding: '4px 10px', cursor: 'pointer'},
    }),
    EditorView.updateListener.of(update => {if (update.docChanged) onChange();}),
  ]})});
  return {
    destroy: () => view.destroy(),
    text: () => view.state.doc.toString(),
    focus: () => view.focus(),
    undo: () => undo(view), redo: () => redo(view),
    search: () => openSearchPanel(view),
    selectRange: (from, to) => {
      if (!Number.isInteger(from) || !Number.isInteger(to) || from < 0 || to < from || to > view.state.doc.length) return false;
      view.dispatch({selection:{anchor:from,head:to},effects:EditorView.scrollIntoView(from,{y:'center'})});
      return true;
    },
    replace: text => view.dispatch({changes: {from: 0, to: view.state.doc.length, insert: text}}),
    line: line => {const pos = view.state.doc.line(Math.min(Math.max(1, line), view.state.doc.lines)).from;
      view.dispatch({selection: {anchor: pos}, effects: EditorView.scrollIntoView(pos, {y: 'center'})});},
    currentLine: () => view.state.doc.lineAt(view.state.selection.main.head).number,
  };
}
