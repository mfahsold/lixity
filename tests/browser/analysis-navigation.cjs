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
from lixity.ui.manuscript_document import reader_blocks
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
text += '\\n\\n## Brief chapter\\n\\nRain.'
config = CorpusConfig(language='en', chapter_regex=r'(?m)^##\\s+')
analysis = analyze_document(text, config, resolve_thresholds(project_config={}))
analysis.paragraphs[0].severity = 3
analysis.chapters[0].flagged = sum(paragraph.is_flagged for paragraph in analysis.paragraphs
                                if paragraph.chapter_num == analysis.chapters[0].num)
# Controlled paragraph display values provide several outliers; chapter/PCA
# measurements retain their independently computed synthetic-text baselines.
for index, paragraph in enumerate(analysis.paragraphs):
    paragraph.asl = (0, 1, 2, 3, 8, 30, 60)[index % 7]
scenes = scene_report_for_display(text, config, premeasured_chapters=analysis.metrics.chapters)
result = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    result[locale] = render_dashboard(
        analysis.chapters, analysis.paragraphs, metrics=analysis.metrics,
        fingerprint=analysis.fingerprint, scenes=scenes, title='Synthetic navigation',
        labels={**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]},
        language_key=locale, controls=True, enabled_actions=['analyze', 'research-reader'],
        manuscript_pdf_token='synthetic-navigation-project',
        reader_document=reader_blocks(text, config, analysis.paragraphs))
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
      await check('compact abnormal paragraph navigation ' + width, async () => {
        const {page, errors, writes} = await createPage(browser, 'en', width);
        try {
          await page.locator('#manuscript-analysis-toggle').click();
          assert.equal(await page.locator('#manuscript-reader-controls #style-layer').count(), 1,
            'The only metric selector stays in the sticky reading controls');
          assert.equal(await page.locator('#manuscript-reader-controls #analysis-evidence-enabled').count(), 1);
          assert.equal(await page.locator('#manuscript-reader-controls #analysis-comparison-enabled').count(), 1);
          assert.equal(await page.locator('#layer-prev').count(), 1);
          const metric = await page.locator('#style-layer').evaluate(select => {
            const cutoff = Number(document.getElementById('layer-legend').dataset.cutoff);
            return Array.from(select.options).map(option => ({key: option.value,
              ids: Array.from(document.querySelectorAll('#chapters .chip')).filter(chip => {
                const info = JSON.parse(chip.dataset.layers || '{}')[option.value];
                return info && Math.abs(info[2]) >= cutoff;
              }).map(chip => chip.dataset.target),
            })).find(candidate => candidate.ids.length >= 3);
          });
          assert.ok(metric, 'The synthetic manuscript has multiple abnormal paragraphs for one metric');
          await page.locator('#style-layer').selectOption(metric.key);
          const middle = Math.floor(metric.ids.length / 2);
          await page.evaluate(id => scrollAndFlash(document.getElementById(id)), metric.ids[middle]);
          await settle(page);
          assert.equal((await page.locator('#layer-position').textContent()).trim(), `${middle + 1} / ${metric.ids.length}`);
          await page.locator('#layer-next').focus(); await page.keyboard.press('Enter'); await settle(page);
          assert.equal(new URL(page.url()).hash, '#' + metric.ids[(middle + 1) % metric.ids.length],
            'Next continues from the current passage in manuscript order');
          await page.locator('#analysis-comparison-enabled').uncheck();
          await page.locator('#analysis-comparison-enabled').check();
          await page.locator('#layer-prev').focus(); await page.keyboard.press('Space'); await settle(page);
          assert.equal(new URL(page.url()).hash, '#' + metric.ids[middle],
            'Reapplying the same metric does not reset abnormal navigation to the first paragraph');
          assert.equal(await page.locator('#style-layer').inputValue(), metric.key);
          assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'true');
          await page.evaluate(({focused, current}) => {
            const panel = document.getElementById(focused); panel.tabIndex = -1;
            panel.focus({preventScroll: true}); scrollAndFlash(document.getElementById(current));
          }, {focused: metric.ids[0], current: metric.ids[middle]});
          await settle(page);
          assert.equal((await page.locator('#layer-position').textContent()).trim(), `${middle + 1} / ${metric.ids.length}`,
            'A paragraph focused above the viewport does not override the current reading position');
          await page.locator('#' + metric.ids[middle] + ' .ptext-inner > p').evaluate(prose => {
            const range = document.createRange(); range.selectNodeContents(prose);
            const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
          });
          await page.locator('#layer-next').click(); await settle(page);
          assert.equal(new URL(page.url()).hash, '#' + metric.ids[(middle + 1) % metric.ids.length],
            'A selected passage supplies the starting point for paragraph navigation');
          await page.locator('#layer-next').click(); await settle(page);
          assert.equal(new URL(page.url()).hash, '#' + metric.ids[(middle + 2) % metric.ids.length],
            'A previous text selection does not restart each subsequent navigation step');
          await page.locator('#text-search').fill('Synthetic passage 0.');
          await page.locator('#text-search').press('Enter'); await settle(page);
          await page.locator('#layer-next').click(); await settle(page);
          assert.equal(await page.locator('#' + metric.ids[0]).isVisible(), true,
            'Global paragraph navigation reveals an abnormal passage outside the current search');
          assert.equal(await page.locator('#text-search').inputValue(), '');
          assert.equal(await page.locator('#style-layer').inputValue(), metric.key,
            'Revealing a filtered passage retains the selected metric');
          await page.locator('#style-layer').selectOption('');
          assert.equal(await page.locator('#layer-prev').isDisabled(), true);
          assert.equal(await page.locator('#layer-next').isDisabled(), true);
          assert.equal((await page.locator('#layer-position').textContent()).trim(), '0 / 0');
          await finish(page, errors, writes);
        } finally { await page.close(); }
      });

      await check('metric and dimension chapter drills ' + width, async () => {
        const {page, errors, writes} = await createPage(browser, 'en', width);
        try {
          await page.locator('#text-search').fill('quiet garden');
          await page.locator('#text-search').press('Enter'); await settle(page);
          await openOverview(page);
          await page.locator('#analysis-measurements > summary').click();
          await page.evaluate(() => revealStyleTarget(document.getElementById('heatmap')));
          const supported = page.locator('#heatmap td.z[data-layer=asl]').last();
          const chapter = await supported.getAttribute('data-chapter');
          await supported.focus(); await page.keyboard.press('Enter'); await settle(page);
          assert.equal(await page.locator('#analysis-metric-context').isVisible(), true,
            'A chapter comparison explains its measurement before leaving the overview');
          assert.equal(await page.locator('#metric-context-values tr').count(), 16);
          assert.equal(await page.locator('#metric-context-values [data-metric-row=asl] button').getAttribute('aria-pressed'), 'true');
          assert.match(await page.locator('#metric-context-value').textContent(), /^– /,
            'An unavailable chapter measurement remains unavailable, not zero');
          await page.locator('#metric-context-read').click(); await settle(page);
          assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'true',
            'A metric-specific chapter drill carries its metric into visible Analysis');
          assert.equal(await page.locator('#style-layer').inputValue(), 'asl');
          assert.equal(await page.locator('#ch-' + chapter).isVisible(), true,
            'The chosen metric chapter is revealed beyond the previous search filter');
          assert.equal(await page.locator('#text-search').inputValue(), '');
          assert.equal(await page.evaluate(() => document.activeElement.id), 'ch-' + chapter,
            'A keyboard metric drill keeps focus on its revealed chapter after clearing search');
          assert.equal(new URL(page.url()).hash, '#ch-' + chapter);
          await openOverview(page);
          await page.evaluate(() => revealStyleTarget(document.getElementById('heatmap')));
          const unsupported = page.locator('#heatmap td.z[data-layer=""]').last();
          assert.ok(await unsupported.count(), 'There is a chapter-only measurement in the synthetic matrix');
          await unsupported.focus(); await page.keyboard.press('Enter'); await settle(page);
          assert.equal(await page.locator('#metric-context-no-layer').isVisible(), true,
            'Chapter-only measurements explain why there are no exact paragraph marks');
          await page.locator('#metric-context-read').click(); await settle(page);
          assert.equal(await page.locator('#style-layer').inputValue(), '',
            'A chapter-only measurement never displays the previous paragraph metric');
          assert.equal(await page.locator('#chapters .metric-notable').count(), 0);
          await openOverview(page);
          await page.evaluate(() => revealStyleTarget(document.getElementById('dimensions')));
          const chosen = await page.locator('#dim-chapter-select option').last().getAttribute('value');
          await page.locator('#dim-chapter-select').selectOption(chosen);
          const loading = page.locator('#dimensions .load[data-layer]:not([data-layer=""])').first();
          const key = await loading.getAttribute('data-layer');
          await loading.focus(); await page.keyboard.press('Enter'); await settle(page);
          assert.equal(await page.locator('#metric-context-chapter').textContent(),
            await page.locator('#dim-chapter-select option:checked').textContent());
          assert.equal(await page.locator('#metric-context-origin').isVisible(), true);
          await page.locator('#metric-context-read').click(); await settle(page);
          assert.equal(new URL(page.url()).hash, '#ch-' + chosen,
            'Dimension loadings retain the selected chapter when returning to the manuscript');
          assert.equal(await page.locator('#style-layer').inputValue(), key);
          assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'true');
          await openOverview(page);
          await page.evaluate(() => revealStyleTarget(document.getElementById('dimensions')));
          const chapterOnlyLoading = page.locator('#dimensions .load[data-layer=""]').first();
          assert.ok(await chapterOnlyLoading.count(), 'The dimension also exposes measurements without paragraph layers');
          const priorLayer = await page.locator('#style-layer').inputValue();
          await chapterOnlyLoading.click();
          assert.equal(await page.locator('#metric-context-no-layer').isVisible(), true);
          await page.locator('#metric-context-values [data-metric-row=asl] button').click();
          assert.equal(await page.locator('#metric-context-no-layer').isVisible(), false);
          assert.equal(await page.locator('#metric-context-origin').isVisible(), false,
            'Another metric is not presented as the original axis loading');
          assert.equal(await page.locator('#style-layer').inputValue(), priorLayer,
            'Inspecting another chapter metric does not change the manuscript layer');
          await page.keyboard.press('Escape');
          assert.equal(await page.locator('#analysis-metric-context').isVisible(), false);
          assert.equal(await chapterOnlyLoading.evaluate(node => node === document.activeElement), true,
            'Closing restores focus to the exact loading without losing the selected chapter');
          await page.evaluate(() => revealStyleTarget(document.getElementById('bands')));
          const cutoff = page.locator('#bands .band-outlier[data-metric-feature]').first();
          await cutoff.click();
          assert.equal(await page.locator('#metric-context-chapter').textContent(),
            await page.locator('#heatmap-ch-' + await cutoff.getAttribute('data-chapter') + ' .ch').textContent());
          await page.locator('#metric-context-values [data-metric-row=dialog_pct] button').click();
          const dialogValue = await page.locator('#metric-context-value').textContent();
          assert.ok(!dialogValue.startsWith('–'), 'A measured zero is not missing');
          await page.locator('[data-metric-close]').first().click();
          await finish(page, errors, writes);
        } finally { await page.close(); }
      });

      await check('bottom selection ' + width, async () => {
        const {page, errors, writes} = await createPage(browser, 'en', width);
        try {
          await openOverview(page);
          await page.locator('#analysis-sections [data-section-link=matrix]').click();
          await settle(page);
          assert.equal(await page.locator('#matrix').isVisible(), true);
          assert.equal(await page.locator('#analysis-sections [aria-current=true]').getAttribute('data-section-link'),
            'matrix', 'The final chapter matrix remains current at the bottom of the page');
          assert.equal(await page.locator('#analysis-sections [data-section-indicator]').count(), 0,
            'Overview section links do not imply measured progress');
          assert.equal(await page.locator('#analysis-sections [aria-current=true]').evaluate(node => getComputedStyle(node).textDecorationLine),
            'underline', 'The current section is underlined');
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
          const read = flag.locator('.triage-read-cell button');
          await read.focus(); await read.press('Enter'); await settle(page);
          assert.equal(await page.locator('#' + paragraph).isVisible(), true);
          assert.equal(await page.evaluate(() => document.activeElement.id), paragraph,
            'The explicit keyboard reading action focuses the revealed paragraph');
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
          const guide = page.locator('#reader-analysis-guide');
          assert.equal(await guide.isVisible(), true);
          assert.equal(await guide.evaluate(node => node.open), false, 'Guidance is voluntary, not an opening overlay');
          const before = await page.evaluate(() => JSON.stringify(LixityWorkbench.state()));
          await guide.locator('summary').click();
          assert.equal(await page.evaluate(() => JSON.stringify(LixityWorkbench.state())), before,
            'Opening guidance changes no analysis state');
          const off = await page.locator('#reader-analysis-guide-state').textContent();
          assert.ok(off && !off.includes('analysis_guide_'), 'The inactive explanation is localized');
          const guideBody = guide.locator('.reader-settings-body');
          assert.equal(await guideBody.isVisible(), true);
          assert.equal(await guideBody.locator('[data-analysis-guide-action]').count(), 3,
            'First-analysis guidance offers three direct actions through existing reader controls');
          assert.ok(await guideBody.evaluate(node => node.scrollWidth <= node.clientWidth),
            'Help retains readable, bounded horizontal layout');
          await guideBody.screenshot({path: path.join(artifacts, `guide-${locale}-${width}.png`)});
          await page.keyboard.press('Escape');
          assert.equal(await guide.evaluate(node => node.open), false);
          assert.equal(await guide.locator('summary').evaluate(node => node === document.activeElement), true);
          await page.locator('#manuscript-analysis-toggle').click();
          await page.locator('#style-layer').selectOption('');
          const none = await page.locator('#reader-analysis-guide-state').textContent();
          assert.notEqual(none, off, 'Analysis on without a metric is distinct from Analysis off');
          await page.locator('#style-layer').selectOption('asl');
          const selected = await page.locator('#reader-analysis-guide-state').textContent();
          assert.notEqual(selected, none);
          assert.ok(selected.includes(await page.locator('#style-layer option:checked').textContent()));
          await guide.locator('summary').click();
          await guide.locator('[data-analysis-guide-action="choose"]').click();
          assert.equal(await guide.evaluate(node => node.open), false);
          assert.equal(await page.locator('#style-layer').evaluate(node => node === document.activeElement), true);
          assert.equal(await page.locator('#style-layer').inputValue(), 'asl', 'Choosing a measure starts at the existing selection');
          await guide.locator('summary').click();
          await guide.locator('[data-analysis-guide-action="explore"]').click();
          await settle(page);
          assert.equal(await page.locator('#reader-inspector').isVisible(), true);
          assert.equal(await page.locator('#reader-inspector-close').evaluate(node => node === document.activeElement), true);
          await page.keyboard.press('Escape');
          await settle(page);
          assert.equal(await page.locator('#reader-inspector').isVisible(), false);
          await guide.locator('summary').click();
          assert.equal(await guide.locator('[data-analysis-guide-action="example"]').isEnabled(), true);
          await guide.locator('[data-analysis-guide-action="example"]').click();
          await settle(page);
          await page.waitForFunction(() => !document.getElementById('analysis-evidence-card').hidden);
          assert.equal(await page.locator('#style-layer').inputValue(), 'asl');
          await page.keyboard.press('Escape');
          await settle(page);
          await page.locator('#analysis-evidence-enabled').uncheck();
          await page.locator('#reader-focus').click();
          assert.equal(await guide.isVisible(), false, 'Focus reading hides optional guidance');
          await page.locator('#reader-focus').click();
          assert.equal(await guide.isVisible(), true);
          assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), false);
          await page.locator('#analysis-evidence-enabled').check();
          if (width === 320) await page.setViewportSize({width, height: 480});
          await page.locator('#manuscript-reader-controls').evaluate(node => { node.scrollTop = 0; });
          await settle(page);
          const controls = await page.locator('#manuscript-reader-controls').boundingBox();
          if (width === 320) assert.ok(controls.height <= 480 * .45 + 1,
            'Compact analysis leaves most of the short viewport available for manuscript prose');
          for (const selector of ['#style-layer', '.reader-outlier-navigation', '.reader-evidence-toggle',
            '.reader-comparison-toggle', '#reader-settings > summary', '#reader-focus', '#workbench-overview-open',
            '#workspace-reader-toggle']) {
            const box = await page.locator(selector).boundingBox();
            assert.ok(box && box.y >= controls.y - 1 && box.y + box.height <= controls.y + controls.height + 1,
              `${selector} stays visible in compact localized reading controls: ${JSON.stringify({box, controls})}`);
          }
          await page.screenshot({path: path.join(artifacts, `analysis-controls-${locale}-${width}.png`)});
          if (width === 320) await page.setViewportSize({width, height: 900});
          await page.locator('#manuscript-analysis-toggle').click();
          await openOverview(page);
          assert.equal(await guide.isVisible(), false, 'Reader guidance does not compete with the overview');
          const reason = page.locator('#review-passage-reason');
          assert.equal(await reason.isVisible(), true);
          assert.equal(await page.locator('[data-review-passage]').getAttribute('aria-describedby'), 'review-passage-reason');
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
              'The final wrapping section link remains wholly readable');
            const matrix = await page.locator('#matrix').boundingBox();
            assert.ok(matrix.y < 900 && matrix.y + matrix.height > 0,
              'Revealing the focused nav link does not scroll vertically back to the navigation');
            await page.screenshot({path: path.join(artifacts, `${locale}-${width}-matrix.png`)});
          }
          await page.locator('#analysis-measurements').evaluate(node => { node.open = true; });
          await page.evaluate(() => revealStyleTarget(document.getElementById('heatmap')));
          const metric = page.locator('#heatmap [data-metric-feature=hd_d]').first();
          const priorMetric = await page.locator('#style-layer').inputValue();
          await metric.focus(); await metric.press('Enter');
          if (width === 320) await page.setViewportSize({width, height: 480});
          const dialog = page.locator('#analysis-metric-context');
          assert.equal(await dialog.isVisible(), true);
          assert.equal(await page.locator('#metric-context-no-layer').isVisible(), true);
          assert.equal(await page.locator('#metric-context-values tr').count(), 16);
          assert.ok((await page.locator('#metric-context-definition').textContent()).length > 20);
          const bounds = await dialog.boundingBox();
          assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= width + 1,
            'The localized measurement dialog fits the viewport');
          const readBounds = await page.locator('#metric-context-read').boundingBox();
          assert.ok(readBounds.y >= 0 && readBounds.y + readBounds.height <= (width === 320 ? 480 : 900),
            'The explicit manuscript action stays visible even on a short mobile viewport');
          if (width === 320) {
            const table = dialog.locator('.table-wrap');
            assert.ok(await table.evaluate(node => node.scrollWidth > node.clientWidth),
              'Wide measurement columns scroll instead of crushing localized labels');
            assert.ok(await dialog.locator('thead th').nth(1).evaluate(node => node.clientWidth >= 100),
              'Measured values retain a readable column width');
          }
          await page.screenshot({path: path.join(artifacts, `metric-context-${locale}-${width}.png`)});
          const lastMetric = page.locator('#metric-context-values tr').last().locator('button');
          await lastMetric.scrollIntoViewIfNeeded();
          await lastMetric.click();
          assert.equal(await page.locator('#metric-context-title').evaluate(node => node === document.activeElement), true,
            'Switching a metric brings its explanation back into the visible reading area');
          await page.keyboard.press('Escape');
          assert.equal(await metric.evaluate(node => node === document.activeElement), true);
          assert.equal(await page.locator('#style-layer').inputValue(), priorMetric);
          await page.evaluate(() => revealStyleTarget(document.getElementById('dimensions')));
          await page.locator('#dimensions [data-dimension-loading]').first().click();
          const origin = page.locator('#metric-context-origin');
          assert.equal(await origin.isVisible(), true);
          assert.ok(!(await origin.textContent()).match(/dim_loading|dim_poles/),
            'Axis captions use the owning localized label pack, not missing global UI keys');
          await page.screenshot({path: path.join(artifacts, `metric-origin-${locale}-${width}.png`)});
          await page.keyboard.press('Escape');
          await finish(page, errors, writes);
        } finally { await page.close(); }
      });
    }
    if (failures.length) throw new AggregateError(failures, 'Analysis navigation regressions');
    console.log('Analysis navigation: compact localized controls, passage-relative abnormal navigation, metric/chapter context, ' +
      'bottom selection, hidden targets, keyboard destinations, nested disclosures, ' +
      'normal/reduced-motion passage/context return, hidden Style tabs, seven-language spacing and horizontal keyboard navigation ' +
      'at desktop/mobile passed. Screenshots: ' + artifacts);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
