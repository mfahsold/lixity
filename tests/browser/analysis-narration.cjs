// Complete manuscript-order dialogue charts and explained pacing measurements.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
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
        await page.waitForFunction(text => document.querySelector('#lixity-tooltip')?.textContent === text, fixture.hook_help);
        assert.equal(await page.locator('#lixity-tooltip').getAttribute('aria-hidden'), 'false');
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('#lixity-tooltip').getAttribute('aria-hidden'), 'true');
        await pacing.screenshot({path: path.join(artifacts, `pacing-${locale}-${width}.png`)});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      } finally { await page.close(); }
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(warnings, []);
    console.log('Narration: all 17 dialogue chapters, measured zero, bounded keyboard scrolling and chapter navigation; pacing units and localized heuristic help passed in seven locales at desktop/mobile. ' + artifacts);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
