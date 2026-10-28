const {openAnalysisSettings, selectMetric} = require('./support/analysis-controls.cjs');
// Metric and comparison controls preserve canonical prose and source anchors.
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
from lixity.style_fingerprint import LAYER_PARAGRAPH_ATTR, layer_stats, z_color
from dashboard_fixtures import full_dashboard
reading_html = full_dashboard()
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
# Deliberately large display data exercises wrapping, not statistical plausibility.
def large_value(*args, **kwargs):
    for index, paragraph in enumerate(args[1]):
        paragraph.asl = [0, 1, 2, 3, 8, 30, 6e24][index % 7]
    return original(*args, **{**kwargs, 'labels': {**get_language_profile('en').labels, **WORKSPACE_LABELS['en']}, 'language_key': 'en'})
full_dashboard.__globals__['render_dashboard'] = large_value
large_value_html = full_dashboard()
def paint_values(*args, **kwargs):
    for index, paragraph in enumerate(args[1]):
        paragraph.asl = [0, 50, 51, 52, 53, 54, 100][index % 7]
    return original(*args, **{**kwargs, 'labels': {**get_language_profile('en').labels, **WORKSPACE_LABELS['en']}, 'language_key': 'en'})
full_dashboard.__globals__['render_dashboard'] = paint_values
paint_html = full_dashboard()
print(json.dumps({'locales': fixtures, 'extra': extra, 'large_value_html': large_value_html, 'reading_html': reading_html,
                  'paint_html': paint_html, 'palette': [z_color(z) for z in (-2.5, -1.75, -1, -.5, 0, .5, 1, 1.75, 2.5)]}))
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
async function paintedPixels(target, positions) {
  const image = await target.screenshot({animations: 'disabled'});
  return target.page().evaluate(async ({image, positions}) => {
    const picture = new Image(); picture.src = 'data:image/png;base64,' + image;
    await picture.decode();
    const canvas = document.createElement('canvas'); canvas.width = picture.width; canvas.height = picture.height;
    const context = canvas.getContext('2d'); context.drawImage(picture, 0, 0);
    return positions.map(position => Array.from(context.getImageData(
      Math.min(picture.width - 1, Math.floor(position * picture.width)), Math.floor(picture.height / 2), 1, 1).data));
  }, {image: image.toString('base64'), positions});
}
async function verifyComparisonPaint(browser) {
  for (const width of [1440, 320]) for (const colorScheme of ['light', 'dark']) {
    const page = await browser.newPage({viewport: {width, height: width === 320 ? 480 : 900}, colorScheme, reducedMotion: 'reduce'});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    try {
      await page.route('**/*', route => route.fulfill(new URL(route.request().url()).pathname.startsWith('/api/')
        ? {json: {ok: true, locked: true, records: [], candidates: []}} : {contentType: 'text/html', body: generated.paint_html}));
      await page.goto('http://lixity.test/');
      await page.locator('#tab-view-analysis').click();
      await page.locator('#manuscript-analysis-toggle').click(); await selectMetric(page, 'asl');
      const target = page.locator('#p-0');
      for (const paragraph of [target, page.locator('#p-6')]) {
        const paint = await paragraph.evaluate(node => {
          const prose = node.querySelector('.ptext-inner > p'), style = getComputedStyle(node);
          return {gradient: style.backgroundImage, opacity: style.opacity, inkOpacity: getComputedStyle(prose).opacity,
            ink: getComputedStyle(prose).color, hue: style.getPropertyValue('--paragraph-layer-color').trim()};
        });
        assert.equal(paint.gradient, 'none', 'Paragraph comparison uses a uniform wash distinct from the statistical scale');
        assert.equal(paint.opacity, '1'); assert.equal(paint.inkOpacity, '1');
        // Hide ink only for a paint sample: the browser must composite the real
        // wash over its actual reader surface, not merely report backgroundColor.
        await paragraph.evaluate(node => node.querySelectorAll(':scope > *').forEach(child => { child.style.visibility = 'hidden'; }));
        const samples = await paintedPixels(paragraph, [0, .325, .65, .95]);
        await paragraph.evaluate(node => {node.style.background = 'transparent';});
        const [base] = await paintedPixels(paragraph, [.325]);
        await paragraph.evaluate(node => {
          node.style.removeProperty('background');
          node.querySelectorAll(':scope > *').forEach(child => { child.style.removeProperty('visibility'); });
        });
        const hue = paint.hue.match(/\w\w/g).map(value => parseInt(value, 16));
        for (const sample of samples) {
          assert.ok(sample.slice(0, 3).every((channel, i) => Math.abs(channel - samples[0][i]) <= 1),
            'The comparison wash is uniform across the prose');
          const distance = rgb => rgb.slice(0, 3).reduce((sum, channel, i) => sum + (channel - hue[i]) ** 2, 0);
          assert.ok(distance(sample) < distance(base), 'The wash carries the direction color');
          assert.ok(sample.slice(0, 3).every((channel, i) => Math.abs(channel - base[i]) < 32),
            'The comparison tint stays restrained');
        }
        const ink = paint.ink.match(/[\d.]+/g).slice(0, 3).map(Number);
        function luminance(rgb) { return rgb.slice(0, 3).map(n => n / 255).map(n => n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4).reduce((sum, n, i) => sum + n * [.2126, .7152, .0722][i], 0); }
        for (const sample of samples) {
          const values = [luminance(ink), luminance(sample)].sort((a, b) => a - b);
          assert.ok((values[1] + .05) / (values[0] + .05) >= 4.5, 'Prose retains contrast across the comparison wash');
        }
      }
      await target.scrollIntoViewIfNeeded(); await frames(page);
      await target.locator(':scope > .reader-comparison-value').click();
      const scale = page.locator('#analysis-evidence-card .analysis-evidence-scale');
      await scale.waitFor();
      assert.equal(await scale.evaluate(node => getComputedStyle(node).backgroundImage),
        await page.locator('.z-gradient').first().evaluate(node => getComputedStyle(node).backgroundImage),
        'Chapter and paragraph legends share the exact statistical gradient');
      await page.locator('#analysis-evidence-card').evaluate(node => { node.scrollTop = node.scrollHeight; });
      const hideMarker = await page.addStyleTag({content: '.analysis-evidence-scale { border-radius: 0; } .analysis-evidence-scale::before, .analysis-evidence-scale span { visibility: hidden !important; }'});
      const colors = await paintedPixels(scale, [.01, .15, .3, .4, .5, .6, .7, .85, .99]);
      await hideMarker.evaluate(node => node.remove());
      generated.palette.forEach((color, index) => {
        const expected = color.match(/\w\w/g).map(value => parseInt(value, 16));
        assert.ok(expected.every((channel, i) => Math.abs(channel - colors[index][i]) <= 3), JSON.stringify({colorScheme, color, actual: colors[index]}));
      });
      await page.keyboard.press('Escape');
      await page.screenshot({path: path.join(artifacts, `comparison-wash-${width}-${colorScheme}.png`)});
      await page.locator('#analysis-comparison-enabled').uncheck();
      assert.equal(await target.evaluate(node => getComputedStyle(node).backgroundImage), 'none');
      await page.locator('#analysis-comparison-enabled').check();
      await page.locator('#reader-focus').click();
      assert.equal(await target.evaluate(node => getComputedStyle(node).backgroundImage), 'none');
      await page.locator('#reader-focus').click();
      await page.locator('#manuscript-analysis-toggle').click();
      assert.equal(await target.evaluate(node => getComputedStyle(node).backgroundImage), 'none');
      await page.locator('#manuscript-analysis-toggle').click();
      await page.locator('#workbench-overview-open').click();
      assert.equal(await target.evaluate(node => getComputedStyle(node).backgroundImage), 'none');
      await page.locator('#workbench-overview-back').click();
      await target.locator('.reader-paragraph-actions').click();
      await page.locator('#manuscript-context-menu [data-reader-action="values"]').click();
      const selected = await target.evaluate(node => {
        const probe = document.createElement('span'); probe.style.color = 'var(--accent)'; document.body.appendChild(probe);
        const result = {gutter: getComputedStyle(node, '::before').backgroundColor, accent: getComputedStyle(probe).color,
          comparison: getComputedStyle(node.querySelector('.reader-comparison-value')).borderInlineStartColor};
        probe.remove(); return result;
      });
      assert.equal(selected.gutter, selected.accent, 'Inspection uses the separate blue selection gutter');
      assert.notEqual(selected.comparison, selected.accent, 'The comparison marker retains its statistical direction');
      await page.emulateMedia({forcedColors: 'active'});
      const forced = await target.evaluate(node => ({gradient: getComputedStyle(node).backgroundImage,
        gutter: getComputedStyle(node, '::before').backgroundColor,
        marker: getComputedStyle(node.querySelector('.reader-comparison-value')).borderInlineStartColor}));
      assert.equal(forced.gradient, 'none');
      assert.equal(forced.gutter, forced.marker, 'Forced colors preserve a visible system-color gutter and comparison edge');
      assert.match(await target.locator('.reader-comparison-value').textContent(), /^[↓↑] /);
      assert.deepEqual(errors, []);
    } catch (error) {
      await page.screenshot({path: path.join(artifacts, `comparison-paint-failure-${width}-${colorScheme}.png`)});
      throw error;
    } finally { await page.close(); }
  }
}
async function comparisonRegression(browser, width, name, check, html = fixtures.en.html) {
  const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion: 'reduce'});
  const errors = [], writes = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.route('**/*', route => {
      if (route.request().method() !== 'GET') writes.push(route.request().url());
      const url = new URL(route.request().url());
      if (url.origin !== 'http://lixity.test') return route.abort();
      return route.fulfill(url.pathname.startsWith('/api/')
        ? {json: {ok: true, locked: true, records: [], candidates: []}}
        : {contentType: 'text/html', body: html});
    });
    await page.goto('http://lixity.test/');
    await page.locator('#tab-view-analysis').click();
    const original = await identity(page);
    await page.locator('#manuscript-analysis-toggle').click();
    await selectMetric(page, 'asl');
    await check(page);
    assert.deepEqual(await identity(page), original, name + ' preserves canonical prose and anchors');
    assert.deepEqual(errors, []); assert.deepEqual(writes, []);
  } finally {
    await page.screenshot({path: path.join(artifacts, name + '.png')});
    await page.close();
  }
}

async function verifyComparisonRegressions(browser) {
  // Independent cases keep layout, magnification and state failures visible together.
  const checks = await Promise.allSettled([
    ...[1440, 320].map(width => comparisonRegression(browser, width, `comparison-prose-retention-${width}`, async page => {
      if (width === 320) await page.setViewportSize({width, height: 480});
      const target = page.locator('#p-4');
      assert.equal(await target.locator(':scope > .reader-comparison-value').isVisible(), true);
      await target.evaluate(node => {
        const prose = node.querySelector('.ptext-inner > p');
        window.retainedMetricProse = prose;
        window.retainedMetricText = prose.firstChild;
        getSelection().setBaseAndExtent(prose.firstChild, 12, prose.firstChild, 2);
      });
      for (const action of ['focus on', 'focus off', 'analysis off', 'analysis on']) {
        // Each transition starts with this marked passage directly below the
        // current toolbar; Focus can expose an earlier panel after its resize.
        await target.evaluate(node => {
          const boundary = document.querySelector('.manuscript-reader-controls').getBoundingClientRect().bottom;
          window.scrollBy(0, node.getBoundingClientRect().top - boundary - 3);
        });
        await frames(page);
        const before = await page.evaluate(() => {
          const anchor = window.LixityReader.capture();
          const prose = anchor.panel.querySelector('.ptext-inner > p');
          return {panel: anchor.panel.id, top: prose.getBoundingClientRect().top};
        });
        assert.equal(before.panel, 'p-4', action + ' captures the visible marked passage');
        // Dispatch through the real control without a pointer clearing the selection.
        const control = action.startsWith('focus') ? '#reader-focus' : '#manuscript-analysis-toggle';
        await page.locator(control).evaluate(node => node.click());
        await frames(page);
        const after = await page.evaluate(id => {
          const prose = document.querySelector('#' + id + ' .ptext-inner > p');
          const selection = getSelection();
          return {top: prose.getBoundingClientRect().top,
            sameProse: prose === window.retainedMetricProse,
            sameSelection: selection.anchorNode === window.retainedMetricText && selection.focusNode === window.retainedMetricText,
            anchor: selection.anchorOffset, focus: selection.focusOffset};
        }, before.panel);
        assert.ok(Math.abs(after.top - before.top) <= 2, JSON.stringify({width, action, before, after}));
        assert.deepEqual({...after, top: undefined}, {top: undefined, sameProse: true, sameSelection: true, anchor: 12, focus: 2});
      }
      // Existing callers can still explicitly request the panel's original position.
      const manualTop = await target.evaluate(node => node.getBoundingClientRect().top);
      await page.locator('#reader-focus').evaluate(node => node.click());
      await frames(page);
      await target.evaluate((node, top) => window.LixityReader.restore({panel: node, top}), manualTop);
      await frames(page);
      assert.ok(Math.abs((await target.boundingBox()).y - manualTop) <= 2, 'Manual panel/top anchors retain their existing meaning');
    }, generated.reading_html)),
    comparisonRegression(browser, 1100, 'comparison-badge-inspector', async page => {
      await page.locator('#analysis-evidence-enabled').uncheck();
      await page.locator('#chapters [data-reader-paragraph]').first().click();
      await page.locator('#manuscript-context-menu [data-reader-action="values"]').click();
      await page.locator('#reader-inspector').waitFor({state: 'visible'});
      const marker = page.locator('#' + fixtures.en.expected.asl[0] + ' > .reader-comparison-value');
      await marker.scrollIntoViewIfNeeded(); await frames(page);
      // Use a normal pointer click: a visible badge covered by navigation is unusable.
      await marker.click({timeout: 2000});
      await page.locator('#analysis-evidence-card').waitFor({state: 'visible'});
      assert.equal(await page.locator('#analysis-evidence-title').textContent(), fixtures.en.labels.layer_asl);
      assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), false,
        'Explaining a comparison does not enable counted-text marks');
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#analysis-evidence-card').isVisible(), false);
      assert.equal(await marker.evaluate(node => node === document.activeElement), true,
        'Escape returns focus to the comparison badge');
    }),
    comparisonRegression(browser, 1440, 'comparison-off-chip-semantics', async page => {
      const chip = page.locator('.chip[data-target="' + fixtures.en.expected.asl[0] + '"]');
      const metric = await chip.getAttribute('data-tip');
      const base = await chip.getAttribute('data-tip-base');
      assert.ok(metric && base && metric !== base, 'The fixture distinguishes metric and tense descriptions');
      await page.locator('#analysis-comparison-enabled').uncheck();
      await page.locator('#workbench-overview-open').click();
      assert.equal(await page.locator('body').evaluate(node => node.classList.contains('comparison-on')), false);
      assert.equal(await chip.getAttribute('aria-label'), base, 'Comparison-off chips describe their displayed tense colors');
      assert.equal(await chip.getAttribute('title'), base);
      assert.equal(await chip.getAttribute('data-tip'), null);
      await page.locator('#workbench-overview-back').click();
      await page.locator('#analysis-comparison-enabled').check();
      await page.locator('#workbench-overview-open').click();
      assert.equal(await page.locator('body').evaluate(node => node.classList.contains('comparison-on')), true);
      assert.equal(await chip.getAttribute('aria-label'), metric, 'Re-enabling comparison restores its selected metric description');
      assert.equal(await chip.getAttribute('data-tip'), metric);
      assert.equal(await chip.getAttribute('title'), null);
    }),
    ...[1440, 1100].flatMap(width => [
      {name: 'enlarged', target: fixtures.en.expected.asl[0], html: fixtures.en.html},
      {name: 'large-value', target: 'p-6', html: generated.large_value_html},
    ].map(value => comparisonRegression(browser, width, `comparison-badge-${value.name}-${width}`, async page => {
      await page.locator('#analysis-evidence-enabled').uncheck();
      const marker = page.locator('#' + value.target + ' > .reader-comparison-value');
      if (value.name === 'large-value') assert.ok((await marker.textContent()).length > 30, 'The fixture has a long formatted value to wrap');
      for (const scale of [200, 100]) {
        await page.evaluate(value => { document.documentElement.style.fontSize = value + '%'; }, scale);
        for (const inspector of [false, true]) {
          if (inspector) {
            await page.locator('#chapters [data-reader-paragraph]').first().click();
            await page.locator('#manuscript-context-menu [data-reader-action="values"]').click();
            await page.locator('#reader-inspector').waitFor({state: 'visible'});
          }
          await marker.scrollIntoViewIfNeeded(); await frames(page);
          await marker.click({timeout: 2000});
          await page.locator('#analysis-evidence-card').waitFor({state: 'visible'});
          await page.keyboard.press('Escape');
          assert.equal(await marker.evaluate(node => node === document.activeElement), true);
          const bounds = await marker.evaluate(node => {
            const box = node.getBoundingClientRect(), panel = node.parentNode.getBoundingClientRect();
            return {inside: box.left >= panel.left - .5 && box.right <= panel.right + .5,
              textFits: node.scrollWidth <= node.clientWidth, height: box.height,
              coarse: matchMedia('(pointer: coarse)').matches};
          });
          assert.ok(bounds.inside && bounds.textFits && bounds.height >= (bounds.coarse ? 44 : 24),
            JSON.stringify({width, scale, inspector, bounds}));
          if (value.name === 'large-value' && width === 1100 && scale === 200 && inspector) {
            assert.ok(bounds.height > 44, 'The long value wraps within the enlarged split pane');
          }
          assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), false);
          await page.screenshot({path: path.join(artifacts, `comparison-${value.name}-${width}-${scale}-${inspector ? 'inspector' : 'plain'}.png`)});
          if (inspector) await page.locator('#reader-inspector-close').click();
        }
      }
    }, value.html))),
    comparisonRegression(browser, 1440, 'comparison-focus-chapter-reading', async page => {
      assert.equal(await page.locator('#chapters .strip').first().isVisible(), true);
      assert.equal(await page.locator('#chapters .chapter-head .meta').first().isVisible(), true);
      await page.locator('#reader-focus').click();
      assert.equal(await page.locator('#chapters .strip:visible').count(), 0, 'Focus hides paragraph-comparison strips');
      assert.equal(await page.locator('#chapters .chapter-head .meta:visible').count(), 0, 'Focus hides chapter measurements');
      await page.locator('#reader-focus').click();
      assert.equal(await page.locator('#chapters .strip').first().isVisible(), true);
      assert.equal(await page.locator('#chapters .chapter-head .meta').first().isVisible(), true);
    }),
  ]);
  const failed = checks.filter(check => check.status === 'rejected').map(check => check.reason);
  if (failed.length) throw new AggregateError(failed, 'Paragraph comparison regressions failed');
}
(async () => {
  const browser = await launchChromium();
  try {
    await verifyComparisonPaint(browser);
    if (process.env.LIXITY_PAINT_ONLY) { console.log('Comparison paint: composited gradients, prose contrast, exact statistical palette and independent states passed. ' + artifacts); return; }
    await verifyComparisonRegressions(browser);
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
      assert.equal(await page.locator('#analysis-comparison-enabled').isVisible(), true, 'Paragraph comparison has its own directly available switch');
      assert.equal(await page.locator('#analysis-evidence-enabled').isVisible(), true, 'Counted text can be switched independently without a disclosure');
      assert.equal(await page.locator('#style-layer').isVisible(), true, 'The active metric is a direct control');
      assert.equal(await page.locator('#style-layer option:checked').textContent(), fixture.labels.layer_asl);
      await openAnalysisSettings(page);
      assert.equal(await page.locator('#style-layer').isVisible(), true, 'the selector needs no settings disclosure');
      await page.locator('#analysis-evidence-enabled').check();
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
          return {background: ink.backgroundColor, opacity: ink.opacity, contrast: (Math.max(a, b) + .05) / (Math.min(a, b) + .05)};
        });
        assert.equal(style.background, 'rgba(0, 0, 0, 0)', 'Paragraph comparison leaves the prose background clear');
        assert.equal(await painted.locator(':scope > .reader-comparison-value').isVisible(), true);
        assert.match(await painted.locator(':scope > .reader-comparison-value').textContent(), /^[↓↑] /);
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
      await page.locator('#analysis-comparison-enabled').uncheck();
      assert.equal(await page.locator('.reader-comparison-value:visible').count(), 0);
      assert.equal(await page.locator('#layer-comparison-legend').isVisible(), false);
      assert.equal(await page.locator('#layer-evidence-legend').isVisible(), true);
      assert.equal(await page.locator('#layer-next').isEnabled(), false);
      await page.locator('#analysis-comparison-enabled').check();
      await page.locator('#analysis-evidence-enabled').uncheck();
      assert.equal(await page.locator('#layer-comparison-legend').isVisible(), true);
      assert.equal(await page.locator('#layer-evidence-legend').isVisible(), false);
      await page.locator('#analysis-evidence-enabled').check();
      await page.locator('#reader-focus').click();
      assert.equal(await page.locator('#layer-legend').isVisible(), false, 'Focus hides both analysis legends');
      assert.equal(await page.locator('.reader-comparison-value:visible').count(), 0, 'Focus hides comparison markers');
      assert.equal(await page.locator('#chapters .strip:visible').count(), 0, 'Focus hides paragraph-comparison strips');
      assert.equal(await page.locator('#chapters .chapter-head .meta:visible').count(), 0, 'Focus hides chapter measurements');
      await page.locator('#reader-focus').click();
      assert.equal(await page.locator('#chapters .strip').first().isVisible(), true);
      assert.equal(await page.locator('#chapters .chapter-head .meta').first().isVisible(), true);
      assert.equal(await page.locator('#analysis-comparison-enabled').isChecked(), true);
      assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), true);
      assert.equal(await page.locator('.reader-comparison-value:visible').count(), expected.length);
      if (locale === 'en' || locale === 'de') await page.locator('#chapters').screenshot({path: path.join(artifacts, `painted-${locale}-${width}-${colorScheme}-${reducedMotion}.png`)});
      await page.locator('#layer-next').click();
      await frames(page);
      assert.equal(await page.locator('#' + expected[0]).isVisible(), true);
      await page.locator('#' + expected[0] + ' [data-reader-paragraph]').click();
      assert.ok((await page.locator('#manuscript-context-menu').textContent()).includes(fixture.labels.reading_explore_passage));
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
      await selectMetric(page, '');
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
        await page.locator('#analysis-comparison-enabled').uncheck();
        await page.locator('#analysis-evidence-enabled').uncheck();
        await page.reload();
        await page.locator('#manuscript-analysis-toggle').click();
        assert.equal(await page.locator('#style-layer').inputValue(), 'passive');
        assert.deepEqual(await page.locator('#chapters .metric-notable').evaluateAll(nodes => nodes.map(node => node.id)), fixture.expected.passive, 'restored metric reapplies the same shared paragraph comparison');
        assert.equal(await page.locator('#layer-legend').isVisible(), false);
        assert.equal(await page.locator('#style-layer option:checked').textContent(), fixture.labels.layer_passive);
        assert.equal(await page.locator('#analysis-comparison-enabled').isChecked(), false);
        assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), false);
        await page.locator('#analysis-comparison-enabled').check();
        assert.equal(await page.locator('#layer-comparison-legend').isVisible(), true);
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
    console.log('Metric overlays: seven locales, desktop/short touch mobile, themes/motion, all seven metrics, exact prose/anchors, 200% text and large-value clicks, Focus, coverage, clear and Analysis states passed. ' + artifacts);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
