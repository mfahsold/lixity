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
from lixity.dialogue import dialogue_report
from lixity.language import get_language_profile
from lixity.pacing import pacing_report
from lixity.pipeline import analyze_document, resolve_document_config
from lixity.style_fingerprint import FEATURE_UNITS, FingerprintThresholds
from lixity.ui import render_dashboard
text = '\n\n'.join(
    f'## Synthetic chapter {number}\n\n' +
    ('"Come here." ' * number if number < 17 else '') +
    'Rain fell across the garden. The path was quiet. ' * 20
    for number in range(1, 18))
config, _ = resolve_document_config(text, 'en')
analysis = analyze_document(text, config, FingerprintThresholds())
dialogue = dialogue_report(text, config).to_dict()
pacing = pacing_report(text, config).to_dict()
documents = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = get_language_profile(locale).labels
    documents[locale] = {
        'html': render_dashboard(analysis.chapters, analysis.paragraphs, metrics=analysis.metrics,
            fingerprint=analysis.fingerprint, dialogue=dialogue, pacing=pacing,
            labels=labels, language_key=locale, title='Synthetic narration coverage', controls=True),
        'turns': labels['dlg_turns'], 'unit': FEATURE_UNITS[locale]['asl'],
        'hook_help': labels['help_pacing_hook'].replace('{max_words}', '8'),
        'scale': labels['pacing_scale'],
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
        await page.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: fixture.html}));
        await page.goto('http://lixity.test/');
        assert.match(await page.title(), /Synthetic narration coverage/);
        assert.equal(await page.locator('h1').textContent(), 'Synthetic narration coverage');
        await page.locator('#workbench-overview-open').click();
        const chart = page.locator('#dialogue .dist.scrollable');
        const rows = chart.locator('.row');
        assert.deepEqual(await rows.evaluateAll(items => items.map(item => item.dataset.jump)),
          Array.from({length: 17}, (_, index) => '#ch-' + (index + 1)));
        assert.equal(await page.locator('#dialogue .kpi b').first().textContent(), '136');
        assert.equal(await rows.last().locator('.bar i').evaluate(element => element.style.width), '0%');
        assert.ok((await rows.last().locator('.val').textContent()).endsWith('0 ' + fixture.turns));
        await chart.scrollIntoViewIfNeeded();
        assert.equal(await chart.evaluate(element => element.scrollHeight > element.clientHeight), true);
        await rows.first().focus(); await page.keyboard.press('PageDown');
        await page.waitForFunction(() => document.querySelector('#dialogue .dist.scrollable').scrollTop > 0);
        await rows.last().focus();
        assert.equal(await chart.evaluate(element => {
          const box = element.getBoundingClientRect(), last = element.lastElementChild.getBoundingClientRect();
          return last.bottom <= box.bottom + 1 && last.top >= box.top - 1;
        }), true);
        await chart.screenshot({path: path.join(artifacts, `dialogue-${locale}-${width}.png`)});
        await page.keyboard.press('Enter');
        assert.equal(await page.locator('#ch-17').isVisible(), true);
        await page.locator('#workbench-overview-open').click();
        const pacing = page.locator('#pacing');
        assert.ok((await pacing.locator('.panel-guide').textContent()).includes(fixture.unit));
        assert.ok((await pacing.locator('.panel-guide').textContent()).includes(fixture.scale));
        assert.equal(await pacing.locator('.dist .row').count(), 17);
        assert.ok((await pacing.locator('.dist .val').last().textContent()).includes('ASL'));
        const hook = pacing.locator('.kpi [data-help]');
        assert.equal(await hook.getAttribute('data-help'), fixture.hook_help);
        await hook.focus();
        await page.waitForFunction(text => document.querySelector('#lixity-tooltip .tooltip-copy')?.textContent === text, fixture.hook_help);
        assert.equal(await page.locator('#lixity-tooltip').getAttribute('aria-hidden'), 'false');
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('#lixity-tooltip').getAttribute('aria-hidden'), 'true');
        await pacing.screenshot({path: path.join(artifacts, `pacing-${locale}-${width}.png`)});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      } finally { await page.close(); }
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(warnings, []);
    await nativeEchoes(browser);
    console.log('Narration: complete dialogue coverage, pacing help, and native local echo counts/word bounds with chapter-only navigation passed in seven locales at desktop/mobile. ' + artifacts);
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
          const panel = page.locator('#motifs'), local = panel.locator('.motif-echoes');
          await panel.scrollIntoViewIfNeeded();
          assert.equal(await panel.isVisible(), true, 'An echo-only report has a visible native motifs panel');
          assert.equal(await panel.locator('h3').textContent(), server.fixture.labels.mot_echoes);
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
          const method = panel.locator('details');
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
