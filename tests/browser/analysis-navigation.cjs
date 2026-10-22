// Overview navigation reveals its destination and preserves the manuscript journey.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');

const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-analysis-navigation-'));
const fixtures = pythonFixture(`
import json
from lixity import CorpusConfig
from lixity.config import resolve_thresholds
from lixity.language import get_language_profile
from lixity.pipeline import analyze_document
from lixity.scenes import scene_report_for_display
from lixity.ui import render_dashboard
from lixity.workspace_labels import WORKSPACE_LABELS

voices = (
    'A quiet garden gives this scene room to continue. ',
    'Beyond the garden wall, a patient keeper watches branches moving slowly through the cold evening air. ',
    'The gate was opened. The narrow path was cleared. Rain fell. ',
    '"Will you wait?" she asks. "I will stay here," he answers. ')
text = '\\n\\n'.join(
    '## Synthetic chapter %d\\n\\n' % chapter + '\\n\\n---\\n\\n'.join(
        'Synthetic passage %d. ' % paragraph +
        (voices[chapter - 1] * (6 + paragraph % 4))
        for paragraph in range(10))
    for chapter in range(1, 5))
config = CorpusConfig(language='en', chapter_regex=r'(?m)^##\\s+')
analysis = analyze_document(text, config, resolve_thresholds(project_config={}))
analysis.paragraphs[0].severity = 3
analysis.chapters[0].flagged = sum(paragraph.is_flagged for paragraph in analysis.paragraphs
                                if paragraph.chapter_num == analysis.chapters[0].num)
scenes = scene_report_for_display(text, config, premeasured_chapters=analysis.metrics.chapters)
result = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    result[locale] = render_dashboard(
        analysis.chapters, analysis.paragraphs, metrics=analysis.metrics,
        fingerprint=analysis.fingerprint, scenes=scenes, title='Synthetic navigation',
        labels={**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]},
        language_key=locale, controls=True, enabled_actions=['analyze'])
print(json.dumps(result))
`, {root});

async function settle(page) {
  await page.evaluate(() => new Promise(resolve => {
    let previous = scrollY, stable = 0;
    function frame() {
      stable = scrollY === previous ? stable + 1 : 0; previous = scrollY;
      if (stable >= 4) resolve(); else requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }));
  await page.waitForFunction(() => !document.querySelector('.view-pane.active')?.getAnimations()
    .some(animation => animation.playState === 'running'));
}

async function createPage(browser, locale, width, motion = 'reduce') {
  const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion: motion});
  page.setDefaultTimeout(10000);
  const errors = [], writes = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => {
    if (['error', 'warning'].includes(message.type())) errors.push(message.text());
  });
  await page.route('**/*', route => {
    const request = route.request(), url = new URL(request.url());
    if (request.method() !== 'GET') {
      writes.push(url.pathname);
      return route.fulfill({status: 400, json: {ok: false, message: 'Read-only navigation fixture'}});
    }
    if (url.origin !== 'http://lixity.test') return route.abort();
    if (url.pathname.startsWith('/api/')) return route.fulfill({json: {
      ok: true, initialized: false, records: [], sources: [], dossiers: [], claims: [], decisions: [],
    }});
    return route.fulfill({contentType: 'text/html', body: fixtures[locale]});
  });
  await page.goto('http://lixity.test/');
  assert.match(await page.title(), /^Synthetic navigation – /);
  await page.locator('#tab-view-analysis').click();
  return {page, errors, writes};
}

async function openOverview(page) {
  await page.locator('#workbench-overview-open').click();
  await page.mouse.move(0, 0);
  await page.waitForFunction(() => document.getElementById('lixity-tooltip').getAttribute('aria-hidden') === 'true');
  await settle(page);
  assert.equal(await page.locator('#manuscript-analysis-panels').isVisible(), true);
}

async function finish(page, errors, writes) {
  assert.deepEqual(errors, []);
  assert.deepEqual(writes, []);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
}

(async () => {
  const browser = await launchChromium(), failures = [];
  async function check(name, operation) {
    try { await operation(); }
    catch (error) { failures.push(new Error(name + ': ' + error.message, {cause: error})); }
  }
  try {
    for (const width of [1440, 320]) {
      await check('bottom selection ' + width, async () => {
        const {page, errors, writes} = await createPage(browser, 'en', width);
        try {
          await openOverview(page);
          await page.locator('#analysis-sections [data-section-link=matrix]').click();
          await settle(page);
          assert.equal(await page.locator('#matrix').isVisible(), true);
          assert.equal(await page.locator('#analysis-sections [aria-current=true]').getAttribute('data-section-link'),
            'matrix', 'The final chapter matrix remains current at the bottom of the page');
          const alignment = await page.locator('#analysis-sections').evaluate(nav => {
            const link = nav.querySelector('[aria-current=true]').getBoundingClientRect();
            const dot = nav.querySelector('[data-section-indicator]').getBoundingClientRect();
            return Math.max(Math.abs(dot.x + dot.width / 2 - (link.x + link.width / 2)),
              Math.abs(dot.y + dot.height / 2 - (link.bottom - 2)));
          });
          assert.ok(alignment < 1, 'The measured indicator belongs to the current horizontal link');
          await page.evaluate(() => { document.getElementById('matrix').hidden = true; dispatchEvent(new Event('resize')); });
          await settle(page);
          assert.notEqual(await page.locator('#analysis-sections [aria-current=true]').getAttribute('data-section-link'),
            'matrix', 'A hidden analysis section cannot become the current destination');
          await finish(page, errors, writes);
        } finally { await page.close(); }
      });

      await check('keyboard manuscript destinations ' + width, async () => {
        const {page, errors, writes} = await createPage(browser, 'en', width);
        try {
          await openOverview(page);
          const flag = page.locator('#flags .flag-row').first(), paragraph = await flag.getAttribute('data-target');
          await flag.focus(); await flag.press('Enter'); await settle(page);
          assert.equal(await page.locator('#' + paragraph).isVisible(), true);
          assert.equal(await page.evaluate(() => document.activeElement.id), paragraph,
            'A keyboard flag drill moves focus from its hidden row to the revealed paragraph');
          await openOverview(page);
          const chapter = page.locator('#matrix tbody [data-jump]').last(), target = await chapter.getAttribute('data-jump');
          await chapter.focus(); await chapter.press('Enter'); await settle(page);
          assert.equal(await page.locator(target).isVisible(), true);
          assert.equal(await page.evaluate(() => document.activeElement.id), target.slice(1),
            'A keyboard matrix drill focuses its revealed chapter');
          await finish(page, errors, writes);
        } finally { await page.close(); }
      });

      await check('nested disclosure destination ' + width, async () => {
        const {page, errors, writes} = await createPage(browser, 'en', width);
        try {
          await openOverview(page);
          // A descendant in nested native disclosures must work even without
          // the browser's separate native-fragment reveal after a mouse click.
          await page.evaluate(() => {
            const host = document.createElement('details'); host.id = 'synthetic-outer';
            host.innerHTML = '<summary>Synthetic scene measurements</summary><details id="synthetic-inner"><summary>Synthetic scene</summary><div id="synthetic-scene-values">Synthetic scene values</div></details>';
            document.getElementById('scenes').appendChild(host);
            const link = document.createElement('a'); link.href = '#synthetic-scene-values';
            link.dataset.jump = '#synthetic-scene-values'; link.id = 'synthetic-scene-jump'; link.textContent = 'Synthetic scene values';
            document.getElementById('analysis-review').appendChild(link);
          });
          await page.locator('#synthetic-scene-jump').focus();
          await page.locator('#synthetic-scene-jump').press('Enter'); await settle(page);
          assert.equal(await page.locator('#synthetic-outer').evaluate(node => node.open), true,
            'A shared analysis jump opens the outer disclosure');
          assert.equal(await page.locator('#synthetic-inner').evaluate(node => node.open), true,
            'A shared analysis jump opens the inner disclosure');
          const box = await page.locator('#synthetic-scene-values').boundingBox();
          assert.ok(box && box.y >= 0 && box.y + box.height <= 900,
            'The revealed descendant is measured and scrolled into the viewport');
          await finish(page, errors, writes);
        } finally { await page.close(); }
      });

      for (const motion of ['reduce', 'no-preference']) {
        await check('overview return and context ' + width + ' ' + motion, async () => {
          const {page, errors, writes} = await createPage(browser, 'en', width, motion);
          try {
            const paragraph = page.locator('#chapters .ptext').nth(25);
            await paragraph.scrollIntoViewIfNeeded(); await settle(page);
            await paragraph.locator('[data-reader-paragraph]').click();
            await page.locator('[data-reader-action=values]').click(); await settle(page);
            assert.equal(await page.locator('#reader-inspector').isVisible(), true);
            await paragraph.scrollIntoViewIfNeeded(); await settle(page);
            const origin = await page.evaluate(() => {
              const anchor = LixityReader.capture();
              return {id: anchor.panel.id, top: anchor.top, state: LixityWorkbench.state()};
            });
            const source = await page.locator('#chapters .ptext').evaluateAll(nodes => nodes.map(node => ({
              id: node.id, start: node.dataset.start, end: node.dataset.end,
              text: node.querySelector('.ptext-inner > p').textContent,
            })));
            assert.equal(await page.locator('#workbench-overview-open').evaluate(node => {
              const bounds = node.getBoundingClientRect();
              return bounds.top >= 0 && bounds.bottom <= innerHeight &&
                document.elementFromPoint(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2)?.closest('#workbench-overview-open') === node;
            }), true, 'overview navigation stays reachable without scrolling away from the current passage');
            await openOverview(page);
            await page.locator('#analysis-measurements > summary').click();
            assert.equal(await page.locator('#style-tab-bands').count(), 1);
            assert.equal(await page.locator('#bands').isVisible(), false);
            const metric = page.locator('.kpi-link[data-jump="#bands"]').first();
            await metric.focus(); await metric.press('Enter'); await settle(page);
            assert.equal(await page.locator('#bands').isVisible(), true,
              'A metric jump reveals its hidden Style tab');
            assert.equal(await page.locator('#style-tab-bands').getAttribute('aria-selected'), 'true');
            await page.locator('#workbench-overview-back').click(); await settle(page);
            assert.ok(Math.abs(await page.locator('#' + origin.id).evaluate(node => node.getBoundingClientRect().top) - origin.top) <= 2,
              'Back restores the exact passage position after navigating hidden Style content');
            assert.equal(await page.locator('#reader-inspector').isVisible(), true,
              'Back restores the suspended passage-values context');
            assert.equal(await page.locator('#workbench-overview-open').evaluate(node => node === document.activeElement), true);
            assert.equal(await page.evaluate(() => LixityWorkbench.state().analysisVisible), origin.state.analysisVisible);

            await openOverview(page);
            const toggle = page.locator('#manuscript-analysis-toggle'); await toggle.focus();
            await page.evaluate(() => scrollAndFlash(document.getElementById('p-12'))); await settle(page);
            assert.equal(await toggle.evaluate(node => node === document.activeElement), true,
              'A programmatic jump preserves another visible focus owner');
            assert.equal(await page.locator('#reader-inspector').isVisible(), true);
            await page.locator('#tab-view-research').click();
            await page.locator('#tab-view-analysis').click(); await settle(page);
            assert.equal(await page.locator('#reader-inspector').isVisible(), true);
            assert.deepEqual(await page.locator('#chapters .ptext').evaluateAll(nodes => nodes.map(node => ({
              id: node.id, start: node.dataset.start, end: node.dataset.end,
              text: node.querySelector('.ptext-inner > p').textContent,
            }))), source, 'Overview journeys preserve source text and paragraph anchors');
            await finish(page, errors, writes);
          } finally { await page.close(); }
        });
      }
    }
    for (const locale of Object.keys(fixtures)) for (const width of [1440, 320]) {
      await check('localized navigation spacing ' + locale + ' ' + width, async () => {
        const {page, errors, writes} = await createPage(browser, locale, width);
        try {
          await openOverview(page);
          const links = await page.locator('#analysis-sections a').evaluateAll(nodes => nodes.map(node => ({
            box: node.getBoundingClientRect().toJSON(), targetExists: !!document.getElementById(node.dataset.sectionLink),
          })));
          assert.ok(links.every(link => link.targetExists));
          for (let index = 1; index < links.length; index++) {
            const previous = links[index - 1].box, current = links[index].box;
            assert.ok(current.y > previous.y ? current.y - previous.bottom >= 4 : current.x - previous.right >= 4,
              'Section links retain visible spacing instead of touching');
          }
          await page.screenshot({path: path.join(artifacts, `${locale}-${width}.png`)});
          if (width === 320) {
            const navigation = page.locator('#analysis-sections'), sections = navigation.locator('[data-section-link]');
            await sections.first().focus();
            for (let index = 1; index < await sections.count(); index++) await page.keyboard.press('ArrowRight');
            await settle(page);
            const last = await sections.last().boundingBox(), bounds = await navigation.boundingBox();
            assert.equal(await sections.last().evaluate(node => node === document.activeElement), true);
            assert.ok(last.x >= bounds.x - 1 && last.x + last.width <= bounds.x + bounds.width + 1,
              'Arrow navigation makes the final overflowing section link horizontally reachable');
            const matrix = await page.locator('#matrix').boundingBox();
            assert.ok(matrix.y < 900 && matrix.y + matrix.height > 0,
              'Revealing the focused nav link does not scroll vertically back to the navigation');
            await page.screenshot({path: path.join(artifacts, `${locale}-${width}-matrix.png`)});
          }
          await finish(page, errors, writes);
        } finally { await page.close(); }
      });
    }
    if (failures.length) throw new AggregateError(failures, 'Analysis navigation regressions');
    console.log('Analysis navigation: bottom selection, hidden targets, keyboard destinations, nested disclosures, ' +
      'normal/reduced-motion passage/context return, hidden Style tabs, seven-language spacing and horizontal keyboard navigation ' +
      'at desktop/mobile passed. Screenshots: ' + artifacts);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
