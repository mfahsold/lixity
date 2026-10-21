const {openAnalysisSettings, selectMetric} = require('./support/analysis-controls.cjs');
// A selected metric paints behind canonical prose, without changing its identity.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-metric-overlays-'));
const generated = pythonFixture(`
import json
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
from lixity.style_fingerprint import LAYER_PARAGRAPH_ATTR, layer_stats
from dashboard_fixtures import full_dashboard
full_dashboard.__globals__['SAMPLE'] = '## Measured paragraphs\\n\\n' + '\\n\\n'.join(
    'A synthetic paragraph %d. ' % n + 'The archive holds letters beside the quiet courtyard. ' * 8
    for n in range(7)) + '\\n\\n## Constant chapter\\n\\nOne sentence.\\n\\nTwo words.\\n\\nThree words.'
original = full_dashboard.__globals__['render_dashboard']
fixtures = {}
for locale in ('en','de','fr','es','it','pt','nl'):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    def rendered(*args, **kwargs):
        # Controlled display fixtures exercise every metric and unavailable spread.
        for index, paragraph in enumerate(args[1]):
            for field in LAYER_PARAGRAPH_ATTR.values():
                setattr(paragraph, field, [0, 1, 2, 3, 8, 30, 60][index % 7] if paragraph.chapter_num == 1 else 0)
        expected = {key: [f'p-{i}' for i, (_, z) in layer_stats(args[1], key).items() if abs(round(z, 2)) >= 1.5]
                    for key in LAYER_PARAGRAPH_ATTR}
        fixtures[locale] = {'expected': expected, 'labels': labels}
        return original(*args, **{**kwargs, 'labels': labels, 'language_key': locale})
    full_dashboard.__globals__['render_dashboard'] = rendered
    fixtures[locale]['html'] = full_dashboard()
extra = {}
for kind, values in (('unavailable', [0]), ('zero', [0, 1, 2])):
    def alternate(*args, **kwargs):
        for index, paragraph in enumerate(args[1]):
            for field in LAYER_PARAGRAPH_ATTR.values():
                setattr(paragraph, field, values[index % len(values)])
        html = original(*args, **{**kwargs, 'labels': {**get_language_profile('en').labels, **WORKSPACE_LABELS['en']}, 'language_key': 'en'})
        extra[kind] = {'html': html, 'comparable': len(layer_stats(args[1], 'asl')), 'total': len(args[1])}
        return html
    full_dashboard.__globals__['render_dashboard'] = alternate
    full_dashboard()
print(json.dumps({'locales': fixtures, 'extra': extra}))
`, {root});
const fixtures = generated.locales;
async function frames(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}
async function identity(page) {
  return page.locator('#chapters .ptext').evaluateAll(nodes => nodes.map(node => ({
    id: node.id, start: node.dataset.start, end: node.dataset.end,
    hash: node.dataset.paragraphSha256, text: node.querySelector('.ptext-inner > p').textContent,
  })));
}
(async () => {
  const browser = await launchChromium();
  try {
    const cases = Object.keys(fixtures).flatMap(locale => [1440, 320].map(width => ({locale, width, height: width === 320 ? 480 : 900, colorScheme: 'light', reducedMotion: 'reduce'})));
    for (const colorScheme of ['light', 'dark']) for (const reducedMotion of ['no-preference', 'reduce']) {
      cases.push({locale: 'en', width: 1440, height: 900, colorScheme, reducedMotion});
    }
    for (const options of cases) {
      const {locale, ...viewportOptions} = options, fixture = fixtures[locale];
      const {width, height, colorScheme, reducedMotion} = viewportOptions;
      const page = await browser.newPage({viewport: {width, height}, colorScheme, reducedMotion, hasTouch: width === 320});
      const errors = [], writes = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/*', route => {
        if (route.request().method() !== 'GET') writes.push(route.request().url());
        const url = new URL(route.request().url());
        if (url.origin !== 'http://lixity.test') return route.abort();
        if (url.pathname.startsWith('/api/')) return route.fulfill({json: {ok: true, locked: true, records: [], candidates: []}});
        return route.fulfill({contentType: 'text/html', body: fixture.html});
      });
      await page.goto('http://lixity.test/');
      await page.locator('#tab-view-analysis').click();
      const original = await identity(page);
      await page.evaluate(() => { window.originalMetricProse = document.querySelector('#chapters .ptext-inner > p'); });
      assert.equal(await page.locator('#style-layer').isVisible(), false, 'Reading starts unpainted');
      await page.locator('#manuscript-analysis-toggle').click();
      assert.equal(await page.locator('#reader-analysis-settings > summary').isVisible(), true, 'Named metric choice is directly available beside enabled Analysis');
      assert.equal(await page.locator('#reader-metric-state').textContent(), fixture.labels.layer_asl);
      await openAnalysisSettings(page);
      assert.equal(await page.locator('#style-layer').isVisible(), true, 'one visible disclosure click exposes the actual selector');
      for (const key of Object.keys(fixture.expected)) {
        await selectMetric(page, key);
        await frames(page);
        assert.deepEqual(await page.locator('#chapters .metric-notable').evaluateAll(nodes => nodes.map(node => node.id)), fixture.expected[key]);
        assert.ok((await page.locator('#layer-legend-count').textContent()).includes(String(fixture.expected[key].length)));
        assert.equal(await page.locator('#chapters .metric-notable [data-layer-symbol]').count(), fixture.expected[key].length);
        const painted = page.locator('#' + fixture.expected[key][0]);
        await painted.evaluate(node => Promise.all(node.getAnimations().map(animation => animation.finished.catch(() => {}))));
        const style = await painted.evaluate(node => {
          const prose = node.querySelector('.ptext-inner > p'), css = getComputedStyle(node), ink = getComputedStyle(prose);
          const canvas = document.createElement('canvas'); canvas.width = canvas.height = 1;
          const ctx = canvas.getContext('2d');
          ctx.fillStyle = getComputedStyle(document.body).backgroundColor; ctx.fillRect(0, 0, 1, 1);
          ctx.fillStyle = css.backgroundColor; ctx.fillRect(0, 0, 1, 1);
          const background = [...ctx.getImageData(0, 0, 1, 1).data];
          ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = ink.color; ctx.fillRect(0, 0, 1, 1);
          const foreground = [...ctx.getImageData(0, 0, 1, 1).data];
          function lum(rgb) { return rgb.slice(0, 3).map(n => n / 255).map(n => n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4).reduce((sum, n, i) => sum + n * [.2126, .7152, .0722][i], 0); }
          const a = lum(background), b = lum(foreground);
          return {background: css.backgroundColor, opacity: ink.opacity, contrast: (Math.max(a, b) + .05) / (Math.min(a, b) + .05)};
        });
        assert.notEqual(style.background, 'rgba(0, 0, 0, 0)');
        assert.equal(style.opacity, '1');
        assert.ok(style.contrast >= 4.5, JSON.stringify({options, key, style}));
      }
      const retainedSelection = await page.evaluate(() => {
        const prose = window.originalMetricProse, text = prose.firstChild;
        const selection = getSelection(); selection.setBaseAndExtent(text, 12, text, 2);
        const control = document.getElementById('style-layer');
        control.value = 'asl'; control.dispatchEvent(new Event('change', {bubbles: true}));
        const intact = {same: selection.anchorNode === text && selection.focusNode === text, anchor: selection.anchorOffset, focus: selection.focusOffset};
        control.value = 'passive'; control.dispatchEvent(new Event('change', {bubbles: true}));
        return intact;
      });
      assert.deepEqual(retainedSelection, {same: true, anchor: 12, focus: 2});
      const expected = fixture.expected.passive;
      if (locale === 'en' || locale === 'de') await page.locator('#chapters').screenshot({path: path.join(artifacts, `painted-${locale}-${width}-${colorScheme}-${reducedMotion}.png`)});
      await page.locator('#layer-next').click();
      await frames(page);
      assert.equal(await page.locator('#' + expected[0]).isVisible(), true);
      await page.locator('#' + expected[0] + ' [data-reader-paragraph]').click();
      assert.ok((await page.locator('#manuscript-context-menu').textContent()).includes(fixture.labels.paragraph_values));
      await page.keyboard.press('Escape');
      await page.locator('#manuscript-analysis-toggle').click();
      assert.equal(await page.locator('#layer-legend').isVisible(), false);
      assert.equal(await page.locator('#style-layer').isVisible(), false);
      assert.equal(await page.locator('[data-layer-symbol]').count(), 0);
      assert.equal(await page.locator('#' + expected[0] + ' [data-reader-paragraph]').getAttribute('aria-label'), fixture.labels.reading_actions);
      assert.equal(await page.locator('#' + expected[0] + ' [data-reader-paragraph]').getAttribute('data-help'), fixture.labels.reading_help_actions);
      assert.equal(await page.locator('#' + expected[0]).evaluate(node => getComputedStyle(node).backgroundColor), 'rgba(0, 0, 0, 0)');
      await page.locator('#manuscript-analysis-toggle').click();
      assert.equal(await page.locator('#style-layer').inputValue(), 'passive');
      await page.locator('#layer-clear').click();
      assert.equal(await page.locator('#style-layer').inputValue(), '');
      assert.equal(await page.locator('.metric-notable').count(), 0);
      assert.equal(await page.locator('[data-layer-symbol]').count(), 0);
      assert.equal(await page.locator('#layer-legend').isVisible(), false);
      assert.deepEqual(await identity(page), original);
      assert.equal(await page.evaluate(() => window.originalMetricProse === document.querySelector('#chapters .ptext-inner > p')), true);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      assert.deepEqual(errors, []); assert.deepEqual(writes, []);
      if (locale === 'en' && width === 1440) {
        await selectMetric(page, 'passive');
        await page.reload();
        await page.locator('#manuscript-analysis-toggle').click();
        assert.equal(await page.locator('#style-layer').inputValue(), 'passive');
        assert.deepEqual(await page.locator('#chapters .metric-notable').evaluateAll(nodes => nodes.map(node => node.id)), fixture.expected.passive, 'restored metric reapplies the same shared paragraph comparison');
        assert.equal(await page.locator('#layer-legend').isVisible(), true);
        assert.equal(await page.locator('#reader-metric-state').textContent(), fixture.labels.layer_passive);
      }
      if (locale === 'en' || locale === 'de') await page.screenshot({path: path.join(artifacts, `${locale}-${width}-${colorScheme}-${reducedMotion}.png`)});
      await page.close();
    }
    for (const [kind, fixture] of Object.entries(generated.extra)) {
      const page = await browser.newPage({viewport: {width: 320, height: 480}, reducedMotion: 'reduce'});
      await page.route('**/*', route => route.fulfill(new URL(route.request().url()).pathname.startsWith('/api/')
        ? {json: {ok: true, locked: true, records: [], candidates: []}}
        : {contentType: 'text/html', body: fixture.html}));
      await page.goto('http://lixity.test/');
      await page.locator('#tab-view-analysis').click();
      await page.locator('#manuscript-analysis-toggle').click();
      await selectMetric(page, 'asl');
      assert.equal(await page.locator('#layer-next').isDisabled(), true);
      assert.equal(await page.locator('.metric-notable').count(), 0);
      assert.equal(await page.locator('#layer-only').isDisabled(), kind === 'unavailable');
      assert.equal(await page.locator('#layer-legend-count').textContent(), kind === 'unavailable'
        ? fixtures.en.labels.layer_unavailable
        : fixtures.en.labels.layer_coverage.replace('{notable}', '0').replace('{comparable}', String(fixture.comparable)).replace('{total}', String(fixture.total)));
      await page.close();
    }
    console.log('Metric overlays: seven locales, desktop/short touch mobile, themes/motion, all seven metrics, exact prose/anchors, coverage, clear and Analysis states passed. ' + artifacts);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
