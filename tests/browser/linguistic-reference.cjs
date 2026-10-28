// Browser plugin unavailable: use the repository's real Chromium/rendering helpers.
// Default literary gold checks counting, not grammatical classification.
// Optional installed-model construction checks are not representative language
// accuracy or readability calibration benchmarks.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const {selectMetric} = require('./support/analysis-controls.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-linguistic-reference-'));
const reference = JSON.parse(fs.readFileSync(path.join(root, 'tests/fixtures/literary_reference.json'), 'utf8'));
// Manually inspected literal suffix hits under the declared profiles. These
// are not annotations of syntactic nominalization or an assessment of prose.
const nominalGold = {
  de: [['Klugheit']], en: [['truth', 'possession'], ['neighbourhood', 'truth']],
  fr: [['Proviseur']], es: [['añadidura']], it: [[]], pt: [[]], nl: [['ondervinding']],
};
const units = {
  de: ['Wörter', 'Wörter je Satz', 'je 1.000 Wörter'],
  en: ['words', 'words per sentence', 'per 1,000 words'],
  fr: ['mots', 'mots par phrase', 'pour 1 000 mots'],
  es: ['palabras', 'palabras por frase', 'por 1.000 palabras'],
  it: ['parole', 'parole per frase', 'ogni 1.000 parole'],
  pt: ['palavras', 'palavras por frase', 'por 1.000 palavras'],
  nl: ['woorden', 'woorden per zin', 'per 1.000 woorden'],
};
const matchUnits = {
  de:['Treffer', 'Treffer'], en:['match', 'matches'], fr:['occurrence', 'occurrences'],
  es:['coincidencia', 'coincidencias'], it:['riscontro', 'riscontri'],
  pt:['ocorrência', 'ocorrências'], nl:['treffer', 'treffers'],
};
const grammarGold = {
  de:['übt', 'ging'], en:['writes', 'wrote'], fr:['écrit', 'écrivait'],
  es:['escribe', 'escribía'], it:['scrive', 'scriveva'],
  pt:['escreve', 'escrevia'], nl:['schrijft', 'schreef'],
};
const fixtures = pythonFixture(`
import contextlib, io, json, tempfile, unicodedata
from pathlib import Path
from lixity.cli import main
from lixity.models import CorpusConfig
from lixity.language import get_language_profile
from lixity.pipeline import analyze_document
from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui import render_dashboard
from lixity.workspace_labels import WORKSPACE_LABELS
reference = json.loads(Path('tests/fixtures/literary_reference.json').read_text(encoding='utf-8'))
result = {}
with tempfile.TemporaryDirectory(prefix='lixity-literary-cli-') as directory:
    source = Path(directory) / 'reference.md'
    for case in reference['fixtures']:
        language = case['language']
        labels = {**get_language_profile(language).labels, **WORKSPACE_LABELS[language]}
        for form in ('NFC', 'NFD'):
            paragraphs = [' '.join(sentence['text'] for sentence in p['sentences']) for p in case['paragraphs']]
            # An astral prefix exposes codepoint/UTF-16 mistakes before accents.
            if form == 'NFD': paragraphs[0] = '😀 ' + paragraphs[0]
            paragraphs = [unicodedata.normalize(form, paragraph) for paragraph in paragraphs]
            text = '## Reference\\n\\n' + '\\n\\n'.join(paragraphs) + '\\n'
            source.write_text(text, encoding='utf-8')
            original = source.read_bytes()
            reports = {}
            for name, arguments in (
                ('analyze', ['analyze', str(source), '--language', language, '--json']),
                ('asl', ['profile', str(source), '--language', language, '--layer', 'asl', '--evidence', '--json']),
                ('nominal', ['profile', str(source), '--language', language, '--layer', 'nominal', '--evidence', '--json']),
            ):
                output, errors = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                    status = main(arguments)
                assert status == 0, (name, status, errors.getvalue())
                assert not errors.getvalue(), errors.getvalue()
                reports[name] = json.loads(output.getvalue())
            analysis = analyze_document(text, CorpusConfig(language=language), FingerprintThresholds(), include_evidence=True)
            html = render_dashboard(analysis.chapters, analysis.paragraphs, metrics=analysis.metrics,
                fingerprint=analysis.fingerprint, paragraph_evidence=analysis.evidence,
                title=case['title'], controls=True, labels=labels, language_key=language)
            assert source.read_bytes() == original
            result[language + '-' + form] = {'html':html, 'paragraphs':paragraphs, 'reports':reports,
                'labels':{key: labels[key] for key in ('evidence_next', 'evidence_paragraph_scope',
                    'evidence_sentence_scope', 'evidence_comparison_missing')}}
    for scope, text in (
        ('preamble', '# Titel\\n\\nVor dem Kapitel.\\n\\n## Kapitel\\n\\nSie geht heim.'),
        ('blockquote', '## Kapitel\\n\\n> Vor dem Absatz.\\n\\nSie geht heim.'),
    ):
        analysis = analyze_document(text, CorpusConfig(language='de'), FingerprintThresholds(), include_evidence=True)
        labels = {**get_language_profile('de').labels, **WORKSPACE_LABELS['de']}
        result['scope-' + scope] = {'html':render_dashboard(analysis.chapters, analysis.paragraphs,
            metrics=analysis.metrics, fingerprint=analysis.fingerprint, paragraph_evidence=analysis.evidence,
            title='Corpus scope', controls=True, labels=labels, language_key='de'),
            'tokens':analysis.metrics.tokens, 'sentences':analysis.metrics.total_sentences,
            'profile_words':sum(chapter.words for chapter in analysis.chapters),
            'profile_help':labels['help_words']}
print(json.dumps(result))
`, {root});

// Opt in only with explicitly installed local models; never download resources.
const grammarFixtures = process.env.LIXITY_TEST_GRAMMATICAL_MODELS === '1' ? pythonFixture(`
import contextlib, io, json, tempfile
from pathlib import Path
from lixity.cli import main
from lixity.models import CorpusConfig
from lixity.language import get_language_profile
from lixity.pipeline import analyze_document
from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui import render_dashboard
from lixity.workspace_labels import WORKSPACE_LABELS
cases = {
    'de': ('de_core_news_md', 'Sie übt.', 'Sie ging.'),
    'en': ('en_core_web_md', 'She writes.', 'She wrote.'),
    'fr': ('stanza:fr_gsd', 'Elle écrit.', 'Elle écrivait.'),
    'es': ('es_core_news_md', 'Ella escribe.', 'Ella escribía.'),
    'it': ('stanza:it_markit', 'Lei scrive.', 'Lei scriveva.'),
    'pt': ('pt_core_news_md', 'Ela escreve.', 'Ela escrevia.'),
    'nl': ('nl_core_news_md', 'Zij schrijft.', 'Zij schreef.'),
}
result = []
with tempfile.TemporaryDirectory(prefix='lixity-grammar-browser-') as directory:
    source = Path(directory) / 'synthetic.md'
    for language, (model, present, past) in cases.items():
        # ASCII quotation marks are recognized by every explicit language profile.
        paragraph = ' '.join([present] * 3) + ' "' + ' '.join([past] * 3) + '"'
        text = '## Reference\\n\\n' + paragraph + '\\n'
        source.write_text(text, encoding='utf-8')
        original = source.read_bytes()
        for scope in ('all', 'narration'):
            config = CorpusConfig(language=language, tense_model=model, tense_scope=scope)
            analysis = analyze_document(text, config, FingerprintThresholds(), include_evidence=True)
            row = analysis.paragraphs[0]
            output, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                status = main(['profile', str(source), '--language', language,
                    '--tense-model', model, '--tense-scope', scope, '--layer', 'asl', '--evidence', '--json'])
            assert status == 0, (language, scope, errors.getvalue())
            assert not errors.getvalue(), errors.getvalue()
            report = json.loads(output.getvalue())
            labels = {**get_language_profile(language).labels, **WORKSPACE_LABELS[language]}
            html = render_dashboard(analysis.chapters, analysis.paragraphs, metrics=analysis.metrics,
                fingerprint=analysis.fingerprint, paragraph_evidence=analysis.evidence,
                title='Synthetic grammar reference', controls=True, labels=labels, language_key=language)
            assert source.read_bytes() == original
            result.append({'language':language, 'model':model, 'scope':scope, 'paragraph':paragraph,
                'html':html, 'cli':report['paragraphs'][0]['evidence']['tense'],
                'evidence':analysis.evidence[0]['tense'],
                'present':row.present_hits, 'past':row.past_hits, 'flagged':row.is_flagged})
print(json.dumps(result))
`, {root}) : [];

function closeEnough(actual, expected, message, tolerance = 0.011) {
  assert.ok(Math.abs(actual - expected) <= tolerance, `${message}: ${actual} != ${expected}`);
}
function wordCount(paragraph) {return paragraph.sentences.reduce((sum, sentence) => sum + sentence.tokens.length, 0);}
function sentenceTexts(gold, form, paragraphIndex) {
  return gold.sentences.map((sentence, index) =>
    ((form === 'NFD' && paragraphIndex === 0 && index === 0 ? '😀 ' : '') + sentence.text).normalize(form));
}
function verifyCLI(caseData, form, fixture) {
  const counts = caseData.paragraphs.map(wordCount);
  const words = counts.reduce((sum, count) => sum + count, 0);
  const sentences = caseData.paragraphs.reduce((sum, p) => sum + p.sentences.length, 0);
  const metrics = fixture.reports.analyze.metrics;
  assert.equal(metrics.tokens, words, `${caseData.language}/${form}: CLI tokens vs annotated gold`);
  assert.equal(metrics.total_sentences, sentences);
  closeEnough(metrics.asl, words / sentences, 'CLI corpus mean vs gold');
  for (const layer of ['asl', 'nominal']) {
    const report = fixture.reports[layer];
    assert.equal(report.selection.comparable_count, 0, 'one or two paragraphs cannot supply a chapter comparison');
    assert.equal(report.comparison.reference_scope, 'all_measurable_paragraphs_within_each_chapter');
    caseData.paragraphs.forEach((paragraph, index) => {
      const row = report.paragraphs[index];
      assert.equal(row.words, counts[index]);
      assert.equal(row.sentences, paragraph.sentences.length);
      assert.equal(row.z, null, 'unavailable comparison is not zero deviation');
      assert.equal(row.comparable, false);
      assert.equal(row.notable, null);
      const evidence = row.evidence.layers[layer];
      assert.equal(evidence.status, 'available', `${caseData.language}/${form}/${layer}/${index}: counted evidence remains available without a comparison`);
      const actualQuotes = evidence.spans.map(span => Array.from(fixture.paragraphs[index]).slice(span.start, span.end).join(''));
      if (layer === 'asl') {
        closeEnough(row.value, counts[index] / paragraph.sentences.length, 'CLI paragraph mean vs gold');
        assert.deepEqual(actualQuotes, sentenceTexts(paragraph, form, index));
        assert.deepEqual(evidence.spans.map(span => span.words), paragraph.sentences.map(sentence => sentence.tokens.length));
      } else {
        assert.deepEqual(actualQuotes.map(text => text.normalize('NFC')), nominalGold[caseData.language][index]);
        closeEnough(row.value, nominalGold[caseData.language][index].length * 1000 / counts[index], 'CLI nominal density vs literal gold', 0.051);
      }
    });
  }
}
async function identity(page) {
  return page.locator('#chapters .ptext').evaluateAll(nodes => nodes.map(node => ({
    id:node.id, start:node.dataset.start, end:node.dataset.end, hash:node.dataset.paragraphSha256,
    text:node.querySelector('.ptext-inner > p')?.textContent,
  })));
}
async function openCard(page, panel) {
  await panel.locator('.reader-paragraph-actions').click();
  await page.locator('#manuscript-context-menu [data-reader-action="values"]').click();
  await page.locator('#reader-inspector-body [data-reader-action="evidence"]').click();
  await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
}
async function panelRanges(page, id) {
  return page.evaluate(id => [...(CSS.highlights.get('lixity-analysis-evidence') || [])]
    .filter(range => range.startContainer.parentElement.closest('.ptext')?.id === id)
    .map(range => range.toString()), id);
}
async function waitForRanges(page, id, expected) {
  await page.waitForFunction(({id, expected}) => {
    const actual = [...(CSS.highlights.get('lixity-analysis-evidence') || [])]
      .filter(range => range.startContainer.parentElement.closest('.ptext')?.id === id)
      .map(range => range.toString().normalize('NFC'));
    return JSON.stringify(actual) === JSON.stringify(expected.map(text => text.normalize('NFC')));
  }, {id, expected});
}
async function checkComparison(card, fixture) {
  assert.equal(await card.locator('.analysis-evidence-paragraph > .analysis-evidence-scope').textContent(), fixture.labels.evidence_paragraph_scope);
  assert.equal(await card.locator('.analysis-evidence-unavailable').textContent(), fixture.labels.evidence_comparison_missing);
  assert.equal(await card.locator('.analysis-evidence-comparison').count(), 0);
  assert.equal(await card.locator('.analysis-evidence-scale').count(), 0, 'unknown comparison has no zero marker');
  assert.equal(await card.locator('.analysis-evidence-warning').count(), 0, 'valid mapped text has no degradation warning');
}
async function checkBrowser(browser, caseData, form, width) {
  const language = caseData.language, fixture = fixtures[language + '-' + form];
  const page = await browser.newPage({viewport:{width, height:width === 320 ? 480 : 950},
    hasTouch:width === 320, colorScheme:width === 320 ? 'dark' : 'light', reducedMotion:'reduce'});
  page.setDefaultTimeout(10000);
  const errors = [], writes = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => {if (['error', 'warning'].includes(message.type())) errors.push(message.text());});
  page.on('request', request => {if (!['GET', 'HEAD'].includes(request.method())) writes.push(request.method() + ' ' + request.url());});
  try {
    await page.route('**/*', route => route.fulfill({contentType:'text/html', body:fixture.html}));
    await page.goto('http://localhost/');
    assert.equal(await page.title(), caseData.title + ' – Lixity');
    assert.equal(await page.locator('html').getAttribute('lang'), language);
    await page.locator('#manuscript-analysis-toggle').click();
    await selectMetric(page, 'asl');
    await page.locator('#analysis-evidence-enabled').check();
    // Open each native paragraph before recording its original DOM identity.
    for (const panel of await page.locator('#chapters .ptext').all()) await panel.scrollIntoViewIfNeeded();
    const before = await identity(page);
    assert.deepEqual(before.map(row => row.text), fixture.paragraphs, 'the displayed manuscript retains exact source normalization');
    await page.locator('#chapters .ptext-inner > p').evaluateAll(nodes => {
      window.referenceProse = nodes.map(node => ({node, children:[...node.childNodes]}));
    });
    for (let index = 0; index < caseData.paragraphs.length; index++) {
      const gold = caseData.paragraphs[index], panel = page.locator('#p-' + index), id = 'p-' + index;
      const sentences = sentenceTexts(gold, form, index);
      await panel.scrollIntoViewIfNeeded();
      await waitForRanges(page, id, sentences);
      assert.deepEqual(await panelRanges(page, id), sentences, 'CSS ranges retain exact accented source spelling and astral prefix');
      await openCard(page, panel);
      const card = page.locator('#analysis-evidence-card');
      for (let sentence = 0; sentence < sentences.length; sentence++) {
        assert.equal(await card.locator('blockquote').textContent(), sentences[sentence]);
        assert.equal(await card.locator('.analysis-evidence-sentence-words').textContent(),
          gold.sentences[sentence].tokens.length + ' ' + units[language][0], 'rendered sentence word count vs manual gold');
        const countVisible = await card.evaluate(node => {
          const number = node.querySelector('.analysis-evidence-number').getBoundingClientRect();
          const heading = node.querySelector('.analysis-evidence-heading').getBoundingClientRect();
          const bounds = node.getBoundingClientRect();
          return number.top >= Math.max(bounds.top, heading.bottom) - 1 && number.bottom <= Math.min(bounds.bottom, innerHeight) + 1;
        });
        if (!countVisible) await page.screenshot({path:path.join(artifacts, `${language}-${form}-${width}-count-obscured.png`)});
        assert.equal(countVisible, true, `${language}/${form}/${width}/paragraph-${index}/sentence-${sentence}: selected sentence count remains readable after navigation inside a long mobile explanation`);
        assert.equal(await card.locator('.analysis-evidence-selection .analysis-evidence-scope').textContent(), fixture.labels.evidence_sentence_scope);
        const mean = new Intl.NumberFormat(language, {minimumFractionDigits:1, maximumFractionDigits:1}).format(wordCount(gold) / sentences.length);
        assert.ok((await card.locator('.analysis-evidence-value').textContent()).endsWith(mean + ' ' + units[language][1]),
          'rendered paragraph mean and localized unit match independent gold');
        await checkComparison(card, fixture);
        if (sentence + 1 < sentences.length) await card.getByRole('button', {name:fixture.labels.evidence_next, exact:true}).click();
      }
      if (index === 0) await page.screenshot({path:path.join(artifacts, `${language}-${form}-${width}-sentence.png`)});
      await page.keyboard.press('Escape');
      await selectMetric(page, 'nominal');
      await panel.scrollIntoViewIfNeeded();
      const nominal = nominalGold[language][index];
      await waitForRanges(page, id, nominal);
      assert.deepEqual((await panelRanges(page, id)).map(text => text.normalize('NFC')), nominal, 'real suffix evidence vs manually inspected literal hits');
      await openCard(page, panel);
      if (nominal.length) {
        for (let match = 0; match < nominal.length; match++) {
          assert.equal((await card.locator('blockquote').textContent()).normalize('NFC'), nominal[match]);
          assert.equal(await card.locator('.analysis-evidence-number').textContent(), '1');
          assert.equal(await card.locator('.analysis-evidence-unit').textContent(), matchUnits[language][0]);
          if (match + 1 < nominal.length) await card.getByRole('button', {name:fixture.labels.evidence_next, exact:true}).click();
        }
      } else {
        assert.equal(await card.locator('blockquote').count(), 0);
        assert.equal(await card.locator('.analysis-evidence-number').textContent(), '0', 'measured zero cues remains distinct from unavailable comparison');
        assert.equal(await card.locator('.analysis-evidence-unit').textContent(), matchUnits[language][1]);
      }
      const density = new Intl.NumberFormat(language, {minimumFractionDigits:1, maximumFractionDigits:1})
        .format(Math.round(nominal.length * 10000 / wordCount(gold)) / 10);
      assert.ok((await card.locator('.analysis-evidence-value').textContent()).endsWith(density + ' ' + units[language][2]));
      await checkComparison(card, fixture);
      await page.keyboard.press('Escape');
      await selectMetric(page, 'asl');
    }
    assert.deepEqual(await identity(page), before, 'analysis and inspection preserve prose, anchors, and identity');
    assert.equal(await page.locator('#chapters .ptext-inner > p').evaluateAll(nodes => nodes.every((node, index) =>
      node === referenceProse[index].node && node.childNodes.length === referenceProse[index].children.length &&
      referenceProse[index].children.every((child, childIndex) => node.childNodes[childIndex] === child))),
    true, 'CSS counting highlights preserve original prose text nodes');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'no horizontal page overflow');
    assert.deepEqual(errors, []);
    assert.deepEqual(writes, []);
    console.log(`${language}/${form}/${width}: annotated literary words/sentences, CLI, CSS evidence, localized cards and unknown comparisons passed`);
  } finally {await page.close();}
}

async function checkCorpusScope(browser) {
  for (const scope of ['preamble', 'blockquote']) for (const width of [1440, 320]) {
    const fixture = fixtures['scope-' + scope];
    assert.equal(fixture.tokens, 6);
    assert.equal(fixture.sentences, 2);
    assert.equal(fixture.profile_words, 3, 'narrow paragraph/chapter view remains explicit');
    const page = await browser.newPage({viewport:{width, height:width === 320 ? 480 : 950}, reducedMotion:'reduce'});
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    try {
      await page.route('**/*', route => route.fulfill({contentType:'text/html', body:fixture.html}));
      await page.goto('http://localhost/');
      await page.locator('#workbench-overview-open').click();
      const measurements = page.locator('#analysis-measurements');
      await measurements.locator(':scope > summary').click();
      const scopeTiles = measurements.locator('.kpi-group').first().locator('.kpi');
      assert.equal(await scopeTiles.nth(0).locator('b').textContent(), '6', `${scope}: global word KPI must share corpus scope with sentences and ASL`);
      assert.equal(await scopeTiles.nth(3).locator('b').textContent(), '2');
      const wordHelp = await scopeTiles.nth(0).locator('[data-help]').getAttribute('data-help');
      assert.ok(wordHelp && wordHelp.length > 0, 'corpus word scope has contextual help');
      assert.notEqual(wordHelp, fixture.profile_help, 'corpus KPI help must distinguish the narrower paragraph-view help');
      assert.match(await page.locator('.chapter-head .meta').first().textContent(), /^3 Wörter/);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
      await page.screenshot({path:path.join(artifacts, `scope-${scope}-${width}.png`)});
      assert.deepEqual(errors, []);
    } finally {await page.close();}
  }
}

async function checkGrammaticalModels(browser) {
  for (const fixture of grammarFixtures) {
    const {language, scope, evidence} = fixture;
    const expectedPast = scope === 'all' ? 3 : 0;
    assert.deepEqual([fixture.present, fixture.past, fixture.flagged], [3, expectedPast, scope === 'all'],
      `${language}/${scope}: actual model classification vs hand-written synthetic reference`);
    assert.deepEqual(fixture.cli, evidence, `${language}/${scope}: explicit CLI model/scope matches backend evidence`);
    assert.equal(evidence.grammar.scope, scope);
    assert.equal(evidence.grammar.groups.length, 6);
    assert.equal(evidence.grammar.groups.filter(group => !group.selected).length, scope === 'all' ? 0 : 3);
    if (['en', 'nl'].includes(language)) {
      assert.ok(evidence.grammar.groups.some(group => group.mood === 'unmarked'),
        `${language}: absent model mood is preserved explicitly, not inferred indicative`);
    }
    const originalQuotes = [...evidence.present.spans, ...evidence.past.spans]
      .map(span => Array.from(fixture.paragraph).slice(span.start, span.end).join(''));
    // Direct inspection of the installed Italian markit tokenizer confirms it
    // attaches periods to the first five verbs; preserve those original spans.
    const expectedOriginalQuotes = language === 'it' ? [
      ...Array(3).fill('scrive.'),
      ...(expectedPast ? ['scriveva.', 'scriveva.', 'scriveva'] : []),
    ] : [
      ...Array(3).fill(grammarGold[language][0]),
      ...Array(expectedPast).fill(grammarGold[language][1]),
    ];
    assert.deepEqual(originalQuotes, expectedOriginalQuotes,
      `${language}/${scope}: original predicate cues match the synthetic verb forms`);
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport:{width, height:width === 320 ? 480 : 950}, reducedMotion:'reduce'});
      const errors = [], writes = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => {if (['error', 'warning'].includes(message.type())) errors.push(message.text());});
      page.on('request', request => {if (!['GET', 'HEAD'].includes(request.method())) writes.push(request.method());});
      try {
        await page.route('**/*', route => route.fulfill({contentType:'text/html', body:fixture.html}));
        await page.goto('http://localhost/');
        assert.equal(await page.title(), 'Synthetic grammar reference – Lixity');
        assert.equal(await page.locator('html').getAttribute('lang'), language);
        const panel = page.locator('#p-0');
        await panel.scrollIntoViewIfNeeded();
        const before = await identity(page);
        assert.deepEqual(before.map(row => row.text), [fixture.paragraph]);
        await panel.locator('.ptext-inner > p').evaluate(node => {
          window.grammarProse = {node, children:[...node.childNodes]};
        });
        assert.equal(await panel.getAttribute('data-pre'), '3');
        assert.equal(await panel.getAttribute('data-pas'), String(expectedPast));
        assert.equal(await panel.locator('.reader-review-flag').count(), scope === 'all' ? 1 : 0);
        await panel.locator('.reader-paragraph-actions').click();
        await page.locator('#manuscript-context-menu [data-reader-action="values"]').click();
        const host = page.locator('#reader-inspector .reader-tense-evidence');
        await page.waitForFunction(() => document.querySelector('#reader-inspector .reader-tense-evidence')?.getAttribute('aria-busy') === 'false');
        const summary = await page.evaluate(excluded => uiFormat('reading_tense_grammar_summary',
          {groups:6, excluded, other:0, unresolved:0}), scope === 'all' ? 0 : 3);
        const summaryNote = host.getByText(summary, {exact:true});
        await summaryNote.scrollIntoViewIfNeeded();
        assert.equal(await summaryNote.isVisible(), true,
          `${language}/${scope}/${width}: grammatical summary remains visible even without a review flag`);
        assert.equal(await summaryNote.evaluate(node => {
          const bounds = node.getBoundingClientRect();
          return bounds.top >= 0 && bounds.bottom <= innerHeight;
        }), true, 'the actual grammar summary fits in the viewport');
        await page.screenshot({path:path.join(artifacts, `grammar-${language}-${scope}-${width}-summary.png`)});
        const expectedSpans = [...evidence.present.spans, ...evidence.past.spans];
        const expectedQuotes = expectedSpans
          .map(span => Array.from(fixture.paragraph).slice(span.start, span.end).join(''));
        const cues = host.locator('.reader-tense-cue');
        assert.deepEqual(await cues.allTextContents(), expectedQuotes);
        for (let index = 0; index < expectedQuotes.length; index++) {
          await cues.nth(index).click();
          await page.waitForFunction(({quote, start, end}) => {
            const ranges = [...(CSS.highlights.get('lixity-tense-current') || [])];
            if (ranges.length !== 1 || ranges[0].toString() !== quote) return false;
            const prose = document.querySelector('#p-0 .ptext-inner > p');
            const prefix = document.createRange(); prefix.selectNodeContents(prose);
            prefix.setEnd(ranges[0].startContainer, ranges[0].startOffset);
            const offset = Array.from(prefix.toString()).length;
            return offset === start && offset + Array.from(ranges[0].toString()).length === end;
          }, {quote:expectedQuotes[index], start:expectedSpans[index].start, end:expectedSpans[index].end});
        }
        assert.deepEqual(await identity(page), before, 'cue navigation preserves source text and paragraph identity');
        assert.equal(await panel.locator('.ptext-inner > p').evaluate(node =>
          node === grammarProse.node && node.childNodes.length === grammarProse.children.length &&
          [...node.childNodes].every((child, index) => child === grammarProse.children[index])), true,
        'grammatical evidence leaves original manuscript text nodes intact');
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
        await page.screenshot({path:path.join(artifacts, `grammar-${language}-${scope}-${width}.png`)});
        assert.deepEqual(errors, []);
        assert.deepEqual(writes, []);
        console.log(`${language}/${scope}/${width}: installed model, CLI counts, grammatical summary, exact cue highlights and source identity passed`);
      } finally {await page.close();}
    }
  }
}

(async () => {
  const browser = await launchChromium();
  try {
    if (process.env.LIXITY_TEST_GRAMMATICAL_MODELS === '1') {
      await checkGrammaticalModels(browser);
    } else {
      for (const form of ['NFC', 'NFD']) {
        for (const caseData of reference.fixtures) verifyCLI(caseData, form, fixtures[caseData.language + '-' + form]);
        for (const caseData of reference.fixtures) for (const width of [1440, 320]) {
          await checkBrowser(browser, caseData, form, width);
        }
      }
      await checkCorpusScope(browser);
    }
  } finally {await browser.close();}
  console.log('linguistic-reference passed; artifacts: ' + artifacts);
})().catch(error => {console.error(error); process.exitCode = 1;});
