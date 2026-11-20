const {openAnalysisSection} = require('./support/analysis-workflow.cjs');
// Complete manuscript-order dialogue charts and explained pacing measurements.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-analysis-narration-'));
const fixtures = pythonFixture(String.raw`
import json
from lixity.format import pct
from lixity.language import get_language_profile
from lixity.pipeline import analyze_document, resolve_document_config, supplementary_reports
from lixity.style_fingerprint import FEATURE_UNITS, FingerprintThresholds
from lixity.ui import render_dashboard
text = '\n\n'.join(
    f'## Synthetic chapter {number}\n\n' +
    ('"Come here." ' * number if number < 17 else '') +
    'Rain fell across the garden. The path was quiet. ' * 20 +
    ('In the garden she said that it was in the way and that it would be there.' if number == 17 else '')
    for number in range(1, 18))
config, _ = resolve_document_config(text, 'en', sticky_min_words=9, sticky_glue_pct=55.125,
    short_sentence_max=8, medium_sentence_max=12, long_sentence_max=17)
analysis = analyze_document(text, config, FingerprintThresholds(), include_evidence=True)
reports = supplementary_reports(text, config, analysis)
documents = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = get_language_profile(locale).labels
    documents[locale] = {
        'html': render_dashboard(analysis.chapters, analysis.paragraphs, metrics=analysis.metrics,
            fingerprint=analysis.fingerprint, dialogue=reports['dialogue'], pacing=reports['pacing'],
            showing=reports['showing'], motifs=reports['motifs'],
            labels=labels, language_key=locale, title='Synthetic narration coverage', controls=True,
            paragraph_evidence=analysis.evidence),
        'turns': labels['dlg_turns'], 'unit': FEATURE_UNITS[locale]['asl'], 'words': labels['words'],
        'counted_text': labels['legend_counted_text'],
        'hook_help': labels['help_pacing_hook'].replace('{max_words}', '8'),
        'scale': labels['pacing_scale'],
        'sticky_rule': labels['pac_sticky_rule'].format(min_words='9', min_pct=pct(55.125, locale, 2, precise=True)),
        'sticky_evidence': labels['pac_sticky_evidence'].format(function_words='13', words='17', percent=pct(76.47, locale, 2)),
    }
print(json.dumps(documents))
`);

(async () => {
  const browser = await launchChromium();
  const errors = [], warnings = [];
  try {
    for (const [locale, fixture] of Object.entries(fixtures)) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion: 'reduce'});
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => { if (['error', 'warning'].includes(message.type())) warnings.push(message.text()); });
      try {
        await page.route('http://localhost/**', route => route.fulfill({contentType: 'text/html', body: fixture.html}));
        await page.goto('http://localhost/');
        assert.match(await page.title(), /Synthetic narration coverage/);
        assert.equal(await page.locator('h1').textContent(), 'Synthetic narration coverage');
        await page.locator('#workbench-overview-open').click();
        await openAnalysisSection(page, 'dialogue');
        const chart = page.locator('#dialogue .dist.scrollable');
        const rows = chart.locator('.row');
        assert.deepEqual(await rows.evaluateAll(items => items.map(item => item.dataset.jump)),
          Array.from({length: 17}, (_, index) => '#ch-' + (index + 1)));
        assert.equal(await page.locator('#dialogue > .kpi-row .kpi').count(), 2);
        assert.equal(await page.locator('#dialogue .kpi b').first().textContent(), '136');
        assert.ok((await page.locator('#dialogue > .panel-guide').last().textContent()).includes(fixture.counted_text));
        const corpusDetails = page.locator('#dialogue-corpus-details');
        assert.equal(await corpusDetails.locator('.kpi-row').isVisible(), false);
        if (locale === 'de')
          await page.locator('#dialogue').screenshot({path: path.join(artifacts, `dialogue-overview-${width}.png`)});
        await corpusDetails.locator('summary').focus();
        await page.keyboard.press('Enter');
        assert.ok(await corpusDetails.locator('.kpi-row').isVisible());
        const clipped = await page.locator('#dialogue .panel-guide, #dialogue .kpi > span, #dialogue summary')
          .evaluateAll(items => items.filter(node => node.scrollWidth > node.clientWidth + 1).map(node => node.textContent));
        assert.deepEqual(clipped, [], `${locale}/${width}: dialogue labels fit`);
        assert.equal(await rows.last().locator('.bar i').evaluate(element => element.style.width), '0%');
        assert.ok((await rows.last().locator('.val').textContent()).endsWith('0 ' + fixture.turns));
        await chart.scrollIntoViewIfNeeded();
        assert.equal(await chart.evaluate(element => element.scrollHeight > element.clientHeight), true);
        await rows.first().locator('a[href^="#ch-"]').focus(); await page.keyboard.press('PageDown');
        await page.waitForFunction(() => document.querySelector('#dialogue .dist.scrollable').scrollTop > 0);
        await rows.last().locator('a[href^="#ch-"]').focus();
        assert.equal(await chart.evaluate(element => {
          const box = element.getBoundingClientRect(), last = element.lastElementChild.getBoundingClientRect();
          return last.bottom <= box.bottom + 1 && last.top >= box.top - 1;
        }), true);
        await chart.screenshot({path: path.join(artifacts, `dialogue-${locale}-${width}.png`)});
        await page.keyboard.press('Enter');
        assert.equal(await page.locator('#ch-17').isVisible(), true);
        assert.equal(await page.locator('#style-layer').inputValue(), 'dialogue');
        assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'true');
        await page.locator('#workbench-overview-open').click();
        await openAnalysisSection(page, 'pacing');
        const pacing = page.locator('#pacing');
        assert.ok((await pacing.locator(':scope > .panel-guide').textContent()).includes(fixture.scale));
        assert.equal(await pacing.locator(':scope > .dist .row').count(), 17);
        assert.equal(await pacing.locator('.dist .row a').first().getAttribute('data-layer'), 'asl');
        assert.ok((await pacing.locator(':scope > .dist .val').last().textContent()).includes(fixture.unit));
        const measures = pacing.locator('.pacing-measurements');
        assert.equal(await measures.evaluate(detail => detail.open), false);
        assert.equal(await measures.locator('.kpi-row').first().isVisible(), false);
        await measures.locator('summary').focus();
        await page.keyboard.press('Enter');
        assert.equal(await measures.evaluate(detail => detail.open), true);
        const rhythms = await measures.locator('#pacing-rhythm-buckets .kpi > span').allTextContents();
        assert.equal(rhythms.length, 3);
        for (const [index, range] of ['≤ 8', '9–20', '> 20'].entries()) {
          assert.ok(rhythms[index].includes(`${range} ${fixture.words}`));
        }
        const hook = measures.locator('.kpi [data-help]');
        assert.equal(await hook.getAttribute('data-help'), fixture.hook_help);
        await hook.focus();
        await page.waitForFunction(text => document.querySelector('#lixity-tooltip .tooltip-copy')?.textContent === text, fixture.hook_help);
        assert.equal(await page.locator('#lixity-tooltip').getAttribute('aria-hidden'), 'false');
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('#lixity-tooltip').getAttribute('aria-hidden'), 'true');
        await measures.locator('summary').focus();
        await page.keyboard.press('Enter');
        const sticky = pacing.locator('.pacing-sticky-items');
        assert.equal(await sticky.evaluate(detail => detail.open), false);
        await sticky.locator('summary').focus();
        await page.keyboard.press('Enter');
        assert.equal(await sticky.evaluate(detail => detail.open), true);
        assert.ok((await sticky.textContent()).includes(fixture.sticky_rule));
        assert.ok((await sticky.locator('li').textContent()).includes(fixture.sticky_evidence));
        assert.equal(await sticky.locator('li a').getAttribute('href'), '#ch-17');
        assert.equal(await sticky.evaluate(detail => detail.scrollWidth <= detail.clientWidth + 1), true);
        await pacing.screenshot({path: path.join(artifacts, `pacing-${locale}-${width}.png`)});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        await sticky.locator('.sticky-jump-btn').click();
        assert.equal(await page.locator('#ch-17').isVisible(), true);
        assert.equal(await page.locator('#style-layer').inputValue(), 'sticky');
        await page.locator('#workbench-overview-open').click();
        await openAnalysisSection(page, 'pacing');
        assert.equal(await page.locator('section.panel#dist').count(), 0, 'Standalone #dist panel is removed when #pacing is active');
        assert.equal(await page.locator('#pacing #dist.rhythm-sentence-dist').count(), 1, 'Sentence lengths are merged inside #pacing');
        const distBlock = pacing.locator('#dist.rhythm-sentence-dist');
        assert.equal(await distBlock.isVisible(), true);
        const lengths = await distBlock.locator('.dist .row .label').allTextContents();
        assert.equal(lengths.length, 4);
        for (const [index, range] of ['≤ 8', '9–12', '13–17', '> 17'].entries()) {
          assert.ok(lengths[index].includes(`${range} ${fixture.words}`));
        }
        assert.ok(await distBlock.locator('.dist .bar').evaluateAll(bars => {
          const columns = bars.map(bar => bar.getBoundingClientRect());
          return columns.every(box => Math.abs(box.left - columns[0].left) <= 1 &&
            Math.abs(box.right - columns[0].right) <= 1);
        }), 'Sentence distribution bars share a scale when some groups have example actions');
        const pacingScope = pacing.locator('[data-evidence-chapter]');
        await pacingScope.selectOption('2');
        assert.equal(await pacingScope.evaluate(select => select.scrollWidth <= select.clientWidth + 1), true);
        const rhythmOrigin = distBlock.locator('.rhythm-jump-btn:not([hidden])').first();
        await rhythmOrigin.click();
        assert.equal(await page.locator('#craft-jump-bar').isVisible(), true);
        const evidenceCard = page.locator('#analysis-evidence-card');
        await evidenceCard.waitFor({state: 'visible'});
        assert.equal(await evidenceCard.locator('[data-quote-context]').getAttribute('data-quote-context'), 'in_quotation');
        assert.match(await evidenceCard.locator('blockquote').textContent(), /Come here\./);
        assert.ok(await page.locator('#ch-2 .ptext.open').count() >= 1);
        const firstOffset = await page.evaluate(() => [...CSS.highlights.get('lixity-analysis-current')][0].startOffset);
        assert.ok(await page.evaluate(() => {
          const range = [...CSS.highlights.get('lixity-analysis-current')][0];
          const toolbar = document.getElementById('craft-jump-bar').closest('.toolbar');
          return range.getClientRects()[0].top >= toolbar.getBoundingClientRect().bottom - 1;
        }), 'The sticky navigation clears the selected sentence');
        assert.equal(await evidenceCard.locator('[data-quote-context]').evaluate(node => node.scrollWidth <= node.clientWidth + 1), true);
        const nextEvidence = page.locator('#craft-jump-bar button').nth(1);
        await nextEvidence.focus();
        await page.keyboard.press('Enter');
        await page.waitForFunction(offset => {
          const [range] = CSS.highlights.get('lixity-analysis-current') || [];
          return range && range.startOffset !== offset;
        }, firstOffset);
        assert.equal(await nextEvidence.evaluate(node => document.activeElement === node), true);
        await page.locator('#craft-jump-bar button').last().press('Enter');
        assert.ok(await rhythmOrigin.evaluate(node => document.activeElement === node), 'Closing the rhythm list restores its overview control');
        assert.equal(await evidenceCard.isVisible(), false);
        assert.equal(await page.evaluate(async () => LixityAnalysisEvidence.inspectSpan(
          document.querySelector('#ch-2 .ptext'), 'asl', 999999)), false, 'An invalid match index never opens the first sentence');
        // Word pattern jump from #showing opens concrete hits in #chapters
        await openAnalysisSection(page, 'showing');
        if (locale === 'en' && width === 320) {
          const largeText = await page.addStyleTag({content:'html { font-size: 200% !important; }'});
          const actions = page.locator('#showing .chapter-evidence-actions');
          assert.equal(await actions.locator('.rhythm-jump-btn').isVisible(), true);
          assert.ok(await actions.evaluate(strip => document.documentElement.scrollWidth <= innerWidth &&
            [...strip.querySelectorAll('button:not([hidden])')].every(button => button.scrollWidth <= button.clientWidth + 1)),
          'Chapter example actions reflow at 320px with 200% text');
          await largeText.evaluate(node => node.remove());
        }
        await page.locator('#showing [data-evidence-chapter]').selectOption('2');
        await page.locator('#showing [data-pattern-jump][data-layer="dialogue"]').click();
        await evidenceCard.waitFor({state: 'visible'});
        assert.equal(await evidenceCard.locator('[data-quote-context]').getAttribute('data-quote-context'), 'in_quotation');
        assert.equal(await page.evaluate(() => [...CSS.highlights.get('lixity-analysis-current')][0]
          .startContainer.parentElement.closest('.chapter').id), 'ch-2');
      } finally { await page.close(); }
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(warnings, []);
    await nativeEchoes(browser);
    await nativeMotifHighlights(browser);
    console.log('Narration: unified rhythm/dist jumps, sticky sentence jumps, uniform motif/custom-phrase highlights and native echoes passed in seven locales at desktop/mobile. ' + artifacts);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

async function nativeEchoes(browser) {
  const source = String.raw`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.language import get_language_profile
from lixity.server import LixityServerHandler
project = Path(sys.argv[1])
manuscript = project / 'synthetic.md'
text = '## First chapter\n\nsilver lantern shines. blue river flows. silver lantern shines.\n'
if GLOBAL:
    text += '\n## Second chapter\n\nsilver lantern shines.\n'
manuscript.write_text(text, encoding='utf-8')
(project / 'lixity.toml').write_text('title = "Synthetic echo coverage"\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.language = LOCALE
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
labels = get_language_profile(LOCALE).labels
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}',
    'labels': {key: labels[key] for key in ('mot_echoes', 'mot_echo_count', 'mot_echo_words', 'mot_echo_note', 'mot_echo_limits', 'mot_global_count')}}), flush=True)
server.serve_forever()
`;
  for (const locale of ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl']) for (const global of [false, true]) {
    const directory = fs.mkdtempSync(path.join(artifacts, 'echo-' + locale + '-'));
    const server = await startNativeServer(source.replaceAll('LOCALE', JSON.stringify(locale)).replace('if GLOBAL:', 'if ' + (global ? 'True' : 'False') + ':'), directory);
    try {
      for (const width of [1440, 320]) {
        const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion: 'reduce'});
        const errors = [], writes = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('console', message => { if (['error', 'warning'].includes(message.type())) errors.push(message.text()); });
        page.on('request', request => { if (request.method() !== 'GET') writes.push(request.url()); });
        try {
          await page.goto(server.fixture.url);
          assert.equal(new URL(page.url()).origin, server.fixture.url);
          assert.match(await page.title(), /Synthetic echo coverage/);
          assert.equal(await page.locator('h1').textContent(), 'Synthetic echo coverage');
          const before = await page.locator('#chapters .ptext-inner > p').allTextContents();
          await page.locator('#workbench-overview-open').click();
          await openAnalysisSection(page, 'motifs');
          const panel = page.locator('#motifs'), local = panel.locator('.motif-echoes');
          await panel.scrollIntoViewIfNeeded();
          assert.equal(await panel.isVisible(), true, 'An echo-only report has a visible native motifs panel');
          assert.equal(await panel.locator('h3').first().textContent(), server.fixture.labels.mot_echoes);
          assert.equal(await panel.locator('.panel-guide').textContent(), server.fixture.labels.mot_echo_note);
          assert.deepEqual(await local.locator('tbody td').allTextContents(), ['silver lantern shines', '1', '2', '1–9']);
          assert.ok((await local.locator('thead').textContent()).includes(server.fixture.labels.mot_echo_count));
          assert.ok((await local.locator('thead').textContent()).includes(server.fixture.labels.mot_echo_words));
          assert.equal(await local.getAttribute('tabindex'), '0');
          for (const header of await local.locator('th').all()) {
            assert.equal(await header.evaluate(element => {
              const range = document.createRange(); range.selectNodeContents(element);
              return range.getClientRects().length;
            }), 1, 'Echo headings remain readable without splitting words across narrow columns');
          }
          if (width === 320) {
            assert.equal(await local.evaluate(element => element.scrollWidth > element.clientWidth), true);
            await local.focus(); await page.keyboard.press('ArrowRight');
            await page.waitForFunction(() => document.querySelector('.motif-echoes').scrollLeft > 0);
          }
          const phrases = panel.locator('.motif-phrases');
          assert.equal(await phrases.count(), global ? 1 : 0);
          if (global) {
            assert.deepEqual(await phrases.locator('tbody td').allTextContents(), ['silver lantern shines', '3', '1, 2']);
            assert.ok((await phrases.locator('thead').textContent()).includes(server.fixture.labels.mot_global_count));
          }
          const method = panel.locator('.motif-echo-method');
          await method.locator('summary').focus(); await page.keyboard.press('Enter');
          assert.equal(await method.getAttribute('open'), '');
          assert.equal(await method.locator('p').textContent(), server.fixture.labels.mot_echo_limits);
          assert.equal(await method.locator('p').isVisible(), true);
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
          await panel.screenshot({path: path.join(artifacts, `echoes-${locale}-${global ? 'global' : 'local'}-${width}.png`)});
          const chapter = local.locator('a');
          assert.equal(await chapter.getAttribute('href'), '#ch-1');
          assert.equal(await local.locator('[data-line], [data-start], [data-target]').count(), 0);
          await chapter.focus(); await page.keyboard.press('Enter');
          assert.equal(await page.locator('#ch-1').isVisible(), true);
          assert.deepEqual(await page.locator('#chapters .ptext-inner > p').allTextContents(), before);
          assert.deepEqual(writes, []);
          assert.deepEqual(errors, []);
        } finally { await page.close(); }
      }
    } finally { await server.close(); }
  }
}

async function nativeMotifHighlights(browser) {
  const source = String.raw`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
project = Path(sys.argv[1])
manuscript = project / 'motifs.md'
text = (
    '## Kapitel 1\n\n'
    '🌿 Es ist so, dass der kalte Brunnen glänzt. Der kalte Brunnen glänzt im Licht.\n\n'
    '## Kapitel 2\n\n'
    'Am Abend blieb es ist so, dass der kalte Brunnen glänzt.\n'
)
manuscript.write_text(text, encoding='utf-8')
(project / 'lixity.toml').write_text(
    'title = "Synthetic motif search"\nlanguage = "de"\n[motif_regexes]\nWater = "Brunnen|Licht"\n', encoding='utf-8'
)
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.language = LOCALE
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}'}), flush=True)
server.serve_forever()
`;
  for (const locale of ['de', 'en', 'fr', 'es', 'it', 'pt', 'nl']) {
    const directory = fs.mkdtempSync(path.join(artifacts, 'motif-search-' + locale + '-'));
    const server = await startNativeServer(source.replaceAll('LOCALE', JSON.stringify(locale)), directory);
    try {
      for (const width of [1440, 320]) {
        const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion: 'reduce'});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        try {
          await page.goto(server.fixture.url);
          await page.locator('#workbench-overview-open').click();
          await openAnalysisSection(page, 'motifs');
          const panel = page.locator('#motifs');
          const occGroup = panel.locator('.motif-occurrence-group:has([data-motif-group^="phrase-"])').first();
          await occGroup.locator('summary').click();
          assert.ok(await occGroup.locator('.motif-jump-btn').count() >= 2);
          assert.equal(await occGroup.locator('.motif-jump-btn, .motif-select-btn, .motif-occ-excerpt')
            .evaluateAll(nodes => nodes.every(node => node.scrollWidth <= node.clientWidth + 1)), true);
          const motifOrigin = occGroup.locator('.motif-select-btn');
          await motifOrigin.click();
          const bar = page.locator('#motif-selection-bar');
          assert.equal(await bar.isVisible(), true);
          assert.ok(await page.locator('#chapters mark.motif-hit').count() >= 2);
          const markedTexts = await page.locator('#chapters mark.motif-hit').allTextContents();
          assert.equal(new Set(markedTexts.map(s => s.toLowerCase())).size, 1, 'Same selected sequence marks uniformly');
          assert.equal(await page.locator('#chapters mark.motif-hit').evaluateAll(nodes =>
            new Set(nodes.map(node => getComputedStyle(node).backgroundColor)).size), 1);
          const next = bar.locator('button').nth(1);
          await next.focus(); await page.keyboard.press('Enter');
          assert.equal(await next.evaluate(node => node === document.activeElement), true);
          assert.match(await bar.textContent(), /2 \/ [2-9]/);
          await page.keyboard.press('Enter');
          assert.equal(await page.locator('#ch-2 mark.motif-hit-current').count(), 1);
          await page.waitForFunction(() => {
            const mark = document.querySelector('mark.motif-hit-current').getBoundingClientRect();
            const nav = document.querySelector('#motif-selection-bar').getBoundingClientRect();
            return nav.top >= 0 && nav.bottom <= mark.top + 1 && mark.bottom <= innerHeight;
          });
          await bar.locator('button').last().press('Enter');
          assert.equal(await page.locator('mark.motif-hit').count(), 0);
          assert.ok(await motifOrigin.evaluate(node => document.activeElement === node), 'Closing the motif list restores its overview control');

          await openAnalysisSection(page, 'motifs');
          const configured = panel.locator('.motif-occurrence-group:has([data-motif-group="motif-0"])');
          await configured.locator('summary').click();
          assert.equal(await configured.locator('[data-motif-jump]').count(), 4);
          await configured.locator('[data-motif-jump]').nth(2).click();
          assert.equal(await page.locator('mark.motif-hit-current').textContent(), 'Licht');
          assert.deepEqual(await page.locator('mark.motif-hit').allTextContents(), ['Brunnen', 'Brunnen', 'Licht', 'Brunnen']);

          await page.locator('#workbench-overview-open').click();
          await openAnalysisSection(page, 'motifs');
          const input = panel.locator('#motif-pattern-input');
          const regex = panel.locator('#motif-pattern-regex');
          const invalidMessage = await page.evaluate(() => uiLabel('mot_custom_invalid'));
          await regex.check();
          await input.fill('[');
          await input.press('Enter');
          await panel.locator('#motif-pattern-status').getByText(invalidMessage, {exact:true}).waitFor();
          await regex.uncheck();
          await input.fill('es ist so, dass');
          await input.press('Enter');
          await page.locator('#motif-selection-bar').waitFor({state: 'visible'});
          assert.equal(await page.locator('#motif-selection-bar').isVisible(), true);
          const customMarks = await page.locator('#chapters mark.motif-hit').allTextContents();
          assert.equal(customMarks.length, 2);
          assert.deepEqual(customMarks.map(s => s.toLowerCase()), ['es ist so, dass', 'es ist so, dass']);
          await page.keyboard.press('Tab');
          assert.ok(await next.evaluate(node => document.activeElement === node), 'Tab reaches the next result after entering a custom search');
          assert.match(await next.getAttribute('aria-describedby'), /motif-selection-status/);
          await page.keyboard.press('Enter');
          assert.match(await bar.locator('[role="status"]').textContent(), /2 \/ 2/);
          assert.equal(await page.locator('#ch-2 mark.motif-hit-current').count(), 1);
          assert.ok(await next.evaluate(node => document.activeElement === node), 'Moving to the next result retains keyboard focus');
          await page.keyboard.press('Shift+Tab');
          const previous = bar.locator('button').first();
          assert.ok(await previous.evaluate(node => document.activeElement === node));
          await page.keyboard.press('Enter');
          assert.match(await bar.locator('[role="status"]').textContent(), /1 \/ 2/);
          assert.ok(await previous.evaluate(node => document.activeElement === node), 'Moving to the previous result retains keyboard focus');
          await bar.locator('button').last().press('Enter');
          assert.ok(await input.evaluate(node => document.activeElement === node), 'Closing a custom search returns to the original input');
          await input.press('Enter');
          await bar.waitFor();
          await openAnalysisSection(page, 'pacing');
          await page.locator('#pacing .rhythm-jump-btn:not([hidden])').first().click();
          assert.equal(await page.locator('#craft-jump-bar').isVisible(), true);
          assert.equal(await bar.isVisible(), false);
          assert.equal(await page.locator('mark.motif-hit').count(), 0);
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
          assert.deepEqual(errors, []);
        } finally { await page.close(); }
      }
    } finally { await server.close(); }
  }
}
