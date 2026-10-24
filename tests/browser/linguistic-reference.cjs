// Browser plugin unavailable: use the repository's real Chromium/rendering helpers.
// Independent hand-transcribed literary gold checks counting, not grammatical
// classification, readability calibration, or representative language accuracy.
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

(async () => {
  const browser = await launchChromium();
  try {
    for (const form of ['NFC', 'NFD']) {
      for (const caseData of reference.fixtures) verifyCLI(caseData, form, fixtures[caseData.language + '-' + form]);
      for (const caseData of reference.fixtures) for (const width of [1440, 320]) {
        await checkBrowser(browser, caseData, form, width);
      }
    }
    await checkCorpusScope(browser);
  } finally {await browser.close();}
  console.log('linguistic-reference passed; artifacts: ' + artifacts);
})().catch(error => {console.error(error); process.exitCode = 1;});
