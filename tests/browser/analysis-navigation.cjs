const {closeAnalysisSettings, openAnalysisSettings, setAnalysisOption} = require('./support/analysis-controls.cjs');
const {openAnalysisSection} = require('./support/analysis-workflow.cjs');
// Overview navigation reveals its destination and preserves the manuscript journey.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium, browserLocales} = require('../../scripts/browser_tools.cjs');
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
def measure(source):
    analysis = analyze_document(source, config, resolve_thresholds(project_config={}), include_evidence=True)
    analysis.paragraphs[0].severity = 3
    analysis.chapters[0].flagged = sum(paragraph.is_flagged for paragraph in analysis.paragraphs
                                    if paragraph.chapter_num == analysis.chapters[0].num)
    # Controlled display values provide multiple outliers without changing
    # independently computed chapter/PCA measurements.
    for index, paragraph in enumerate(analysis.paragraphs):
        paragraph.asl = (0, 1, 2, 3, 8, 30, 60)[index % 7]
    return analysis, scene_report_for_display(source, config, premeasured_chapters=analysis.metrics.chapters)
def render(locale, source, analysis, scenes):
    return render_dashboard(
        analysis.chapters, analysis.paragraphs, metrics=analysis.metrics,
        fingerprint=analysis.fingerprint, scenes=scenes, title='Synthetic navigation',
        labels={**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]},
        language_key=locale, controls=True, enabled_actions=['analyze', 'research-reader'],
        manuscript_pdf_token='a' * 64, manuscript_source_sha256='b' * 64,
        reader_document=reader_blocks(source, config, analysis.paragraphs), paragraph_evidence=analysis.evidence)
analysis, scenes = measure(text)
result = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    result[locale] = render(locale, text, analysis, scenes)
for paragraph in analysis.paragraphs:
    paragraph.severity = 0
for chapter in analysis.chapters:
    chapter.flagged = 0
result['en-without-tense-signals'] = render('en', text, analysis, scenes)
with_cues = text.replace('Synthetic passage 0. ', 'Synthetic passage 0. '
    'I am tired. She is here. I was waiting. She was alone. They were waiting. ', 1)
result['en-with-tense-cues'] = render('en', with_cues, *measure(with_cues))
print(json.dumps(result))
`, {root});

async function settle(page) {
  const settled = await page.evaluate(() => new Promise(resolve => {
    let previous = scrollY, stable = 0;
    const timeout = setTimeout(() => resolve({position:scrollY, previous, stable}), 3000);
    function frame() {
      stable = scrollY === previous ? stable + 1 : 0; previous = scrollY;
      if (stable >= 4) {
        clearTimeout(timeout);
        resolve(null);
      } else {
        requestAnimationFrame(frame);
      }
    }
    requestAnimationFrame(frame);
  }));
  assert.equal(settled, null, `Scroll position did not settle: ${JSON.stringify(settled)}`);
  await page.waitForFunction(() => !document.querySelector('.view-pane.active')?.getAnimations()
    .some(animation => animation.playState === 'running'));
}

async function createPage(browser, locale, width, motion = 'reduce', hasTouch = false) {
  const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion: motion, hasTouch});
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
    if (url.origin !== 'http://localhost') return route.abort();
    if (url.pathname === '/api/manuscript-delta') return route.fulfill({json: {
      ok: true, schema_version: 'lixity-timeline/1', current: {revision: 'b'.repeat(64)},
      has_baseline: true, base: {created_at: 1708000000}, chapter_deltas: [
        {num: 1, match_status: 'matched', words_delta: 12345, asl_delta: 0.05, dialog_pct_delta: 25},
        {num: 2, match_status: 'ambiguous', words_delta: 12345},
      ],
    }});
    if (url.pathname.startsWith('/api/')) return route.fulfill({json: {
      ok: true, initialized: false, records: [], sources: [], dossiers: [], claims: [], decisions: [],
    }});
    return route.fulfill({contentType: 'text/html', body: fixtures[locale]});
  });
  // The loopback origin exposes the same secure context as the local app,
  // including Web Crypto for checking manuscript evidence offsets.
  await page.goto('http://localhost/');
  assert.match(await page.title(), /^Synthetic navigation – /);
  await page.locator('#tab-view-analysis').click();
  return {page, errors, writes};
}

async function openOverview(page) {
  await page.locator('#workbench-overview-open').click();
  await page.mouse.move(0, 0);
  await page.waitForFunction(() => document.getElementById('lixity-tooltip').getAttribute('aria-hidden') === 'true');
  await settle(page);
  assert.equal(await page.locator('[data-analysis-workflows]').isVisible(), true);
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
    await check('comparison restoration coordinates with later reading actions', async () => {
      for (const scenario of ['larger', 'focus', 'comparison', 'jump', 'scroll']) {
        const {page, errors, writes} = await createPage(browser, 'en', 320);
        try {
          await page.locator('#manuscript-analysis-toggle').click();
          const metric = await page.locator('#style-layer').evaluate(select => {
            return Array.from(select.options).map(option => ({key: option.value,
              ids: Array.from(document.querySelectorAll('#chapters .chip')).filter(chip => {
                const info = JSON.parse(chip.dataset.layers || '{}')[option.value];
                return info && info[4] === true;
              }).map(chip => chip.dataset.target),
            })).find(candidate => candidate.ids.length >= 5);
          });
          assert.ok(metric);
          await page.locator('#style-layer').selectOption(metric.key);
          const index = Math.floor(metric.ids.length / 2) + 1;
          await page.evaluate(id => scrollAndFlash(document.getElementById(id)), metric.ids[index]);
          await settle(page);
          await page.locator('#reader-settings').evaluate(details => { details.open = true; });
          await settle(page);
          const initial = await page.evaluate(() => LixityReader.capture().panel.id);
          const target = metric.ids[index + 1];
          const result = await page.evaluate(({kind, targetId}) => {
            const original = window.requestAnimationFrame, frames = [];
            window.requestAnimationFrame = callback => { frames.push(callback); return frames.length; };
            let intendedScroll;
            try {
              const comparison = document.getElementById('analysis-comparison-enabled');
              comparison.click(); comparison.click();
              const action = document.getElementById(kind === 'focus' ? 'reader-focus' : 'reader-text-larger');
              action.focus({preventScroll: true});
              action.dispatchEvent(new KeyboardEvent('keydown', {key: ' ', bubbles: true}));
              action.click();
              if (kind === 'comparison') { comparison.click(); comparison.click(); }
              if (kind === 'jump') {
                const target = document.getElementById(targetId);
                rememberPassageLocation(target); scrollAndFlash(target);
              }
              if (kind === 'scroll') {
                window.dispatchEvent(new WheelEvent('wheel', {deltaY: 250}));
                window.scrollBy(0, 250); intendedScroll = window.scrollY;
              }
            } finally { window.requestAnimationFrame = original; }
            for (const callback of frames) callback(performance.now());
            return {frames: frames.length, intendedScroll};
          }, {kind: scenario, targetId: target});
          assert.ok(result.frames > 0);
          await settle(page);
          if (scenario === 'scroll') {
            assert.ok(Math.abs(await page.evaluate(() => window.scrollY) - result.intendedScroll) <= 1,
              'a later user scroll supersedes queued layout restorations');
          } else {
            const expected = scenario === 'jump' ? target : initial;
            assert.equal(await page.evaluate(() => LixityReader.capture()?.panel.id), expected,
              scenario + ': later reading actions retain the intended passage');
            if (scenario === 'jump') assert.equal(new URL(page.url()).hash, '#' + target);
          }
          await finish(page, errors, writes);
        } finally { await page.close(); }
      }
    });
    await check('an empty tense filter explains how to continue', async () => {
      const {page, errors, writes} = await createPage(browser, 'en-without-tense-signals', 320);
      try {
        await page.locator('#manuscript-analysis-toggle').click();
        await page.locator('#style-layer').selectOption('asl');
        await openAnalysisSettings(page);
        const filter = page.locator('#filter-flags');
        await filter.focus(); await page.keyboard.press('Space'); await settle(page);
        assert.equal(await page.locator('#chapters .chapter:visible').count(), 0);
        const status = page.locator('#paragraph-filter-empty');
        assert.equal(await status.isVisible(), true);
        assert.match(await status.innerText(), /tense/i);
        assert.equal(await page.locator('#layer-next').isDisabled(), true);
        const reset = page.locator('#paragraph-filter-reset');
        await reset.focus(); await page.keyboard.press('Enter'); await settle(page);
        assert.equal(await filter.isChecked(), false);
        assert.equal(await filter.evaluate(node => node === document.activeElement), true);
        assert.equal(await status.isVisible(), false);
        assert.ok(await page.locator('#chapters .chapter:visible').count() > 0);
        assert.equal(await page.locator('#style-layer').inputValue(), 'asl');
        await finish(page, errors, writes);
      } finally { await page.close(); }
    });
    await check('reading marks stay secondary and search remains usable at 200% text', async () => {
      const {page, errors, writes} = await createPage(browser, 'en-with-tense-cues', 320, 'reduce', true);
      try {
        await page.setViewportSize({width:320, height:480});
        await page.locator('#manuscript-analysis-toggle').click();
        const settings = page.locator('#reader-analysis-options'), summary = settings.locator('summary').first();
        const inspect = page.locator('#reader-inspect-current'), metric = page.locator('#style-layer');
        await metric.focus();
        assert.equal(await metric.inputValue(), 'asl');
        assert.equal(await page.locator('#analysis-evidence-enabled').isVisible(), false);
        assert.equal(await page.locator('#layer-legend').isVisible(), false);
        await inspect.focus(); await page.keyboard.press('Enter'); await settle(page);
        assert.equal(await page.locator('#reader-inspector').isVisible(), true);
        assert.equal(await page.locator('#reader-inspector-close').evaluate(node => node === document.activeElement), true);
        await page.keyboard.press('Escape'); await settle(page);
        assert.equal(await inspect.evaluate(node => node === document.activeElement), true);
        await summary.focus(); await page.keyboard.press('Enter'); await settle(page);
        const filter = page.locator('#filter-flags');
        assert.equal(await filter.isVisible(), true);
        await filter.focus(); await page.keyboard.press('Space');
        await summary.focus(); await page.keyboard.press('Escape');
        assert.equal(await settings.evaluate(node => node.open), false);
        assert.equal(await summary.evaluate(node => node === document.activeElement), true);
        await page.setViewportSize({width:320, height:320});
        await page.evaluate(() => {document.documentElement.style.fontSize = '200%'; scrollTo(0,700);});
        const search = page.locator('#text-search'), clear = page.locator('#text-search-clear');
        await page.keyboard.press('Control+f');
        assert.equal(await search.evaluate(node => node === document.activeElement), true);
        await search.fill('Missing synthetic passage'); await page.keyboard.press('Enter'); await settle(page);
        assert.equal(await page.locator('#text-search-next').isVisible(), false);
        assert.equal(await inspect.isDisabled(), true);
        assert.equal(await page.evaluate(() => ['text-search-status', 'text-search-clear'].every(id => {
          const node = document.getElementById(id), bounds = node.getBoundingClientRect();
          return bounds.top >= 0 && bounds.bottom <= innerHeight &&
            node.contains(document.elementFromPoint(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2));
        })), true, 'Empty search status and Clear are visible without scrolling at 200%');
        await clear.tap(); await settle(page);
        assert.equal(await search.inputValue(), '');
        assert.equal(await filter.isChecked(), true);
        assert.equal(await metric.inputValue(), 'asl');
        await finish(page, errors, writes);
      } finally {await page.close();}
    });
    for (const width of [1440, 320]) {
      await check('measurement, tense review and return share the reading position ' + width, async () => {
        const {page, errors, writes} = await createPage(browser, 'en-with-tense-cues', width, 'reduce', width === 320);
        try {
          if (width === 320) await page.setViewportSize({width, height: 535});
          await page.locator('#manuscript-analysis-toggle').click();
          const metric = page.locator('#style-layer');
          await metric.selectOption('asl');
          const all = await page.locator('#chapters .chip.outlier').count();
          const filter = page.locator('#filter-flags');
          await setAnalysisOption(page, 'filter-flags', true);
          await closeAnalysisSettings(page); await settle(page);
          const scoped = await page.locator('#chapters .chapter.has-flags .chip.outlier').count();
          assert.ok(scoped > 0 && scoped < all);
          assert.match(await page.locator('#layer-position').textContent(), new RegExp(`(?:of | · )${scoped}$`));
          await page.locator('#layer-next').click(); await settle(page);
          const target = page.locator(new URL(page.url()).hash);
          assert.equal(await target.evaluate(node => !!node.closest('.chapter.has-flags')), true);
          assert.equal(await target.isVisible(), true);
          const search = page.locator('#text-search');
          await search.fill('No matching synthetic passage');
          await search.press('Enter'); await settle(page);
          assert.equal(await page.locator('#text-search-status').innerText(), await page.evaluate(() => uiLabel('text_search_none')));
          assert.equal(await page.locator('#paragraph-filter-suspended').isVisible(), true);
          assert.equal(await page.locator('#text-search-next').isDisabled(), true);
          assert.equal(await page.evaluate(() => {
            return ['text-search-status', 'text-search-clear', 'paragraph-filter-suspended'].every(id => {
              const node = document.getElementById(id), bounds = node.getBoundingClientRect();
              const visible = document.elementFromPoint(bounds.left + bounds.width / 2, bounds.top + bounds.height / 2);
              return bounds.top >= 0 && bounds.bottom <= innerHeight + 1 && node.contains(visible);
            });
          }), true, 'Empty search feedback and its next action remain inside the visible reading viewport');
          const clearSearch = page.locator('#text-search-clear');
          await clearSearch.focus(); await page.keyboard.press('Enter'); await settle(page);
          assert.equal(await search.evaluate(node => node === document.activeElement), true);
          assert.equal(await page.locator('#paragraph-filter-suspended').isVisible(), false);
          assert.equal(await filter.isChecked(), true);
          assert.equal(await page.locator('#chapters .chapter:not(.has-flags):visible').count(), 0,
            'Clearing search restores the author’s chosen tense scope');
          const chapter = page.locator('#chapters .chapter:not(.has-flags)').first();
          const chapterId = await chapter.getAttribute('id');
          const chapterSelector = page.locator('#reader-chapter');
          await chapterSelector.focus(); await chapterSelector.selectOption(chapterId); await settle(page);
          assert.equal(new URL(page.url()).hash, '#' + chapterId);
          assert.equal(await chapter.isVisible(), true);
          assert.equal(await chapterSelector.evaluate(node => node === document.activeElement), true);
          assert.equal(await filter.isChecked(), false, 'An explicit chapter jump clears only its blocking filter');
          assert.equal(await metric.inputValue(), 'asl');
          // Start at prose below the chapter heading so the reading position
          // is unambiguous even when sticky controls gain or lose one row.
          const start = await chapter.locator('.ptext').first().getAttribute('id');
          await page.evaluate(id => scrollAndFlash(document.getElementById(id)), start);
          await settle(page);
          assert.equal(await page.evaluate(() => LixityReader.capture()?.panel.id), start);
          await metric.selectOption('dialogue'); await settle(page);
          assert.equal(await page.evaluate(() => LixityReader.capture()?.panel.id), start);
          await metric.selectOption('asl'); await settle(page);
          assert.equal(await page.evaluate(() => LixityReader.capture()?.panel.id), start);
          await openOverview(page);
          await page.locator('#workbench-overview-back').focus();
          await page.keyboard.press('Enter'); await settle(page);
          assert.equal(await page.evaluate(() => LixityReader.capture()?.panel.id), start);
          assert.equal(await page.locator('#workbench-overview-open').evaluate(node => node === document.activeElement), true);
          await openOverview(page);
          const review = page.locator('[data-review-tense]');
          const flaggedId = await review.getAttribute('data-target');
          if (width === 320) await review.tap();
          else { await review.focus(); await page.keyboard.press('Enter'); }
          await settle(page);
          assert.equal(new URL(page.url()).hash, '#' + flaggedId);
          assert.equal(await metric.inputValue(), 'asl');
          const close = page.locator('#reader-inspector-close');
          const explanation = page.locator('#reader-inspector .reader-passage-flag');
          assert.equal(await explanation.isVisible(), true);
          assert.equal(await explanation.locator('.reader-passage-flag-title').textContent(),
            await page.evaluate(() => uiLabel('reading_tense_mixed')));
          await explanation.locator('.reader-tense-cue').first().waitFor({state: 'visible'});
          assert.equal(await close.evaluate(button => button === document.activeElement), true);
          await page.keyboard.press('Enter'); await settle(page);
          assert.equal(await page.locator('#reader-inspector').isVisible(), false);
          const cue = page.locator('#' + flaggedId + ' [data-reader-flag]');
          assert.equal(await cue.evaluate(button => button === document.activeElement), true);
          assert.equal(await cue.evaluate(button => {
            const rect = button.getBoundingClientRect();
            return rect.bottom > readingViewportTop() && rect.top < innerHeight;
          }), true);
          await finish(page, errors, writes);
        } finally { await page.close(); }
      });
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
            return Array.from(select.options).map(option => ({key: option.value,
              ids: Array.from(document.querySelectorAll('#chapters .chip')).filter(chip => {
                const info = JSON.parse(chip.dataset.layers || '{}')[option.value];
                return info && info[4] === true;
              }).map(chip => chip.dataset.target),
            })).find(candidate => candidate.ids.length >= 3);
          });
          assert.ok(metric, 'The synthetic manuscript has multiple abnormal paragraphs for one metric');
          await page.locator('#style-layer').selectOption(metric.key);
          const middle = Math.floor(metric.ids.length / 2);
          await page.evaluate(id => scrollAndFlash(document.getElementById(id)), metric.ids[middle]);
          await settle(page);
          assert.equal((await page.locator('#layer-position').textContent()).trim(), `Difference ${middle + 1} of ${metric.ids.length}`);
          await page.locator('#layer-next').focus(); await page.keyboard.press('Enter'); await settle(page);
          assert.equal(new URL(page.url()).hash, '#' + metric.ids[(middle + 1) % metric.ids.length],
            'Next continues from the current passage in manuscript order');
          await setAnalysisOption(page, 'analysis-comparison-enabled', false);
          await setAnalysisOption(page, 'analysis-comparison-enabled', true);
          await closeAnalysisSettings(page);
          await page.locator('#layer-prev').focus(); await page.keyboard.press('Space'); await settle(page);
          assert.equal(new URL(page.url()).hash, '#' + metric.ids[middle],
            'Reapplying the same metric does not reset abnormal navigation to the first paragraph');
          assert.equal(await page.locator('#style-layer').inputValue(), metric.key);
          assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'true');
          if (width === 320) {
            for (const [direction, index] of [['next', middle + 1], ['prev', middle]]) {
              const scheduled = await page.evaluate(which => {
                const original = window.requestAnimationFrame, frames = [];
                window.requestAnimationFrame = callback => { frames.push(callback); return frames.length; };
                try {
                  const comparison = document.getElementById('analysis-comparison-enabled');
                  comparison.click(); comparison.click();
                  const control = document.getElementById('layer-' + which);
                  control.focus({preventScroll: true}); control.click();
                } finally { window.requestAnimationFrame = original; }
                for (const callback of frames) callback(performance.now());
                return frames.length;
              }, direction);
              assert.ok(scheduled > 0, 'the comparison changes queued a layout restoration');
              await settle(page);
              assert.equal(new URL(page.url()).hash, '#' + metric.ids[index],
                'a pending comparison layout must not change the navigation origin');
              assert.equal(await page.evaluate(() => LixityReader.capture()?.panel.id), metric.ids[index],
                'the selected passage remains visible after queued restoration frames');
              assert.equal(await page.locator('#layer-' + direction).evaluate(node => node === document.activeElement), true,
                'navigation keeps focus on its control');
            }
          }
          await page.evaluate(({focused, current}) => {
            const panel = document.getElementById(focused); panel.tabIndex = -1;
            panel.focus({preventScroll: true}); scrollAndFlash(document.getElementById(current));
          }, {focused: metric.ids[0], current: metric.ids[middle]});
          await settle(page);
          assert.equal((await page.locator('#layer-position').textContent()).trim(), `Difference ${middle + 1} of ${metric.ids.length}`,
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
          const query = (await page.locator('#' + metric.ids[0] + ' .ptext-inner > p').textContent()).match(/^Synthetic passage \d+\./)[0];
          await page.locator('#text-search').fill(query);
          await page.locator('#text-search').press('Enter'); await settle(page);
          const scoped = await page.evaluate(ids => ids.filter(id => !document.getElementById(id).closest('.text-miss')), metric.ids);
          assert.ok(scoped.length > 0 && scoped.length < metric.ids.length, 'Search limits the set of reachable differences');
          assert.match(await page.locator('#layer-position').textContent(), new RegExp(`(?:of | · )${scoped.length}$`));
          await page.locator('#layer-next').click(); await settle(page);
          assert.ok(scoped.includes(new URL(page.url()).hash.slice(1)), 'Difference navigation remains within the searchable result set');
          assert.equal(await page.locator('#text-search').inputValue(), query);
          assert.equal(await page.locator('#style-layer').inputValue(), metric.key,
            'Revealing a filtered passage retains the selected metric');
          await page.locator('#text-search').fill('No matching synthetic passage');
          await page.locator('#text-search').press('Enter'); await settle(page);
          assert.equal(await page.locator('#layer-next').isDisabled(), true);
          assert.equal((await page.locator('#layer-position').textContent()).trim(), 'Differing paragraphs · 0');
          await page.locator('#style-layer').selectOption('');
          assert.equal(await page.locator('#layer-prev').isDisabled(), true);
          assert.equal(await page.locator('#layer-next').isDisabled(), true);
          assert.equal(await page.locator('#layer-position').isVisible(), false);
          await finish(page, errors, writes);
        } finally { await page.close(); }
      });

      await check('metric and dimension chapter drills ' + width, async () => {
        const {page, errors, writes} = await createPage(browser, 'en', width);
        try {
          await page.locator('#text-search').fill('quiet garden');
          await page.locator('#text-search').press('Enter'); await settle(page);
          await openOverview(page);
          await openAnalysisSection(page, 'style');
          await page.locator('#style-tab-heatmap').click();
          const supported = page.locator('#heatmap td.z[data-layer=asl]').last();
          const chapter = await supported.getAttribute('data-chapter');
          await supported.focus(); await page.keyboard.press('Enter'); await settle(page);
          assert.equal(await page.locator('#analysis-metric-context').isVisible(), true,
            'A chapter comparison explains its measurement before leaving the overview');
          assert.equal(await page.locator('#metric-context-values tr').count(), 16);
          assert.equal(await page.locator('#metric-context-values [data-metric-row=asl] button').getAttribute('aria-pressed'), 'true');
          assert.equal(await page.locator('#metric-context-value').textContent(), 'Unavailable',
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
          await openAnalysisSection(page, 'style');
          await page.locator('#style-tab-heatmap').click();
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
          await openAnalysisSection(page, 'style');
          await page.locator('#style-tab-dimensions').click();
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
          await openAnalysisSection(page, 'style');
          await page.locator('#style-tab-dimensions').click();
          const chapterOnlyLoading = page.locator('#dimensions .load[data-layer=""]').first();
          assert.ok(await chapterOnlyLoading.count(), 'The dimension also exposes measurements without paragraph layers');
          const priorLayer = await page.locator('#style-layer').inputValue();
          await chapterOnlyLoading.click();
          assert.equal(await page.locator('#metric-context-no-layer').isVisible(), true);
          await page.locator('#metric-context-details > summary').click();
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
          await openAnalysisSection(page, 'style');
          await page.locator('#style-tab-bands').click();
          const cutoff = page.locator('#bands .band-outlier[data-metric-feature]').first();
          await cutoff.click();
          assert.equal(await page.locator('#metric-context-chapter').textContent(),
            await page.locator('#heatmap-ch-' + await cutoff.getAttribute('data-chapter') + ' .ch').textContent());
          await page.locator('#metric-context-details > summary').click();
          await page.locator('#metric-context-values [data-metric-row=dialog_pct] button').click();
          const dialogValue = await page.locator('#metric-context-value').textContent();
          assert.match(dialogValue, /^0[.,]00 /, 'A measured zero is shown with its unit');
          await page.locator('[data-metric-close]').first().click();
          await finish(page, errors, writes);
        } finally { await page.close(); }
      });

      await check('bottom selection ' + width, async () => {
        const {page, errors, writes} = await createPage(browser, 'en', width);
        try {
          await openOverview(page);
          await openAnalysisSection(page, 'matrix');
          await settle(page);
          assert.equal(await page.locator('#matrix').isVisible(), true);
          assert.equal(await page.locator('[data-analysis-section-target=matrix]').getAttribute('aria-pressed'),
            'true', 'The selected chapter matrix remains identified by its workflow control');
          assert.equal(await page.locator('[data-analysis-workflows] [data-section-indicator]').count(), 0,
            'Workflow choices do not imply measured progress');
          await openAnalysisSection(page, 'flags');
          assert.equal(await page.locator('#matrix').isVisible(), false,
            'Choosing a different view conceals the previous comparison panel');
          assert.equal(await page.locator('[data-analysis-section-target=matrix]').getAttribute('aria-pressed'), 'false');
          await finish(page, errors, writes);
        } finally { await page.close(); }
      });

      await check('keyboard manuscript destinations ' + width, async () => {
        const {page, errors, writes} = await createPage(browser, 'en', width);
        try {
          if (width === 320) await page.setViewportSize({width, height: 480});
          await openOverview(page);
          await openAnalysisSection(page, 'flags');
          const flag = page.locator('#flags .flag-row').first(), paragraph = await flag.getAttribute('data-target');
          const read = flag.locator('.triage-read-cell button');
          await read.focus(); await read.press('Enter'); await settle(page);
          const passage = page.locator('#' + paragraph);
          assert.equal(await passage.isVisible(), true);
          assert.equal(await page.evaluate(() => document.activeElement.id), paragraph,
            'The explicit keyboard reading action focuses the revealed paragraph');
          const inspector = page.locator('#reader-inspector');
          assert.equal(await inspector.isVisible(), width !== 320,
            'The triage jump opens an adjacent inspector only when it can be seen beside the paragraph');
          if (width === 320) {
            assert.equal(await passage.locator('.ptext-inner > p').evaluate(prose => {
              const top = prose.getBoundingClientRect().top;
              return top >= readingViewportTop() - 1 && top < innerHeight;
            }), true, 'The target text starts below the sticky reader controls and inside the viewport');
            await page.keyboard.press('Tab');
            assert.equal(await passage.locator('[data-reader-paragraph]').evaluate(node => node === document.activeElement), true);
            await page.keyboard.press('Tab');
            const reason = passage.locator('[data-reader-flag]');
            assert.equal(await reason.evaluate(node => node === document.activeElement), true,
              'The next passage control opens the reason for this tense finding');
            await reason.press('Enter'); await settle(page);
            assert.equal(await inspector.locator('.reader-passage-flag').isVisible(), true);
            const close = inspector.locator('#reader-inspector-close');
            assert.equal(await close.evaluate(node => {
              const bounds = node.getBoundingClientRect();
              return node === document.activeElement && node.contains(document.elementFromPoint(
                bounds.left + bounds.width / 2, bounds.top + bounds.height / 2));
            }), true, 'Opening the local reason scrolls to the inspector and focuses its visible close control');
            await close.press('Enter'); await settle(page);
            assert.equal(await inspector.isVisible(), false);
            assert.equal(await reason.evaluate(node => node === document.activeElement), true,
              'Closing the inspector returns focus to the local reason');
          }
          await openOverview(page);
          await openAnalysisSection(page, 'matrix');
          const chapter = page.locator('#matrix tbody [data-jump]').last(), target = await chapter.getAttribute('data-jump');
          await chapter.focus(); await chapter.press('Enter'); await settle(page);
          assert.equal(await page.locator(target).isVisible(), true);
          assert.equal(await page.evaluate(() => document.activeElement.id), target.slice(1),
            'A keyboard matrix drill focuses its revealed chapter');
          for (const activation of ['click', 'keyboard']) {
            await openOverview(page);
            await page.evaluate(() => {
              const filter = document.getElementById('filter-flags');
              filter.checked = false;
              filter.dispatchEvent(new Event('change', {bubbles: true}));
            });
            await openAnalysisSection(page, 'matrix');
            const flagged = page.locator('#matrix tbody tr[data-flags="1"] a[data-flags="1"]').first();
            assert.equal(await flagged.count(), 1, 'The fixture provides a flagged chapter link');
            if (activation === 'click') await flagged.click();
            else { await flagged.focus(); await flagged.press('Enter'); }
            await settle(page);
            assert.equal(await page.locator('#filter-flags').isChecked(), true,
              `Flag context survives native chapter link ${activation}`);
            assert.equal(await page.locator('#ch-1').isVisible(), true,
              `Flagged chapter is revealed through ${activation}`);
          }
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
              window.__testOverviewAnchor = anchor.panel;
              return {top: anchor.top, state: LixityWorkbench.state()};
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
            await openAnalysisSection(page, 'analysis-measurements');
            const measurements = page.locator('#analysis-measurements');
            await measurements.locator('#kpi-lexis-drawer summary').click();
            assert.equal(await page.locator('#style-tab-bands').count(), 1);
            assert.equal(await page.locator('#bands').isVisible(), false);
            const metric = page.locator('.kpi-link[data-jump="#bands"]').first();
            await metric.focus(); await metric.press('Enter'); await settle(page);
            assert.equal(await page.locator('#bands').isVisible(), true,
              'A metric jump reveals its hidden Style tab');
            assert.equal(await page.locator('#style-tab-bands').getAttribute('aria-selected'), 'true');
            await page.locator('#workbench-overview-back').click(); await settle(page);
            assert.ok(Math.abs(await page.evaluate(() => window.__testOverviewAnchor.getBoundingClientRect().top) - origin.top) <= 2,
              'Back restores the exact passage position after navigating hidden Style content');
            assert.equal(await page.locator('#reader-inspector').isVisible(), true,
              'Back restores the suspended passage-values context');
            assert.equal(await page.locator('#workbench-overview-open').evaluate(node => node === document.activeElement), true);
            assert.equal(await page.evaluate(() => LixityWorkbench.state().analysisVisible), origin.state.analysisVisible);

            await openOverview(page);
            assert.equal(await page.locator('#manuscript-analysis-toggle').isVisible(), false);
            const focusOwner = page.locator('#tab-view-analysis');
            assert.equal(await focusOwner.isVisible(), true);
            await focusOwner.focus();
            assert.equal(await focusOwner.evaluate(node => node === document.activeElement), true,
              'The programmatic-jump check starts with an actually focused visible control');
            await page.evaluate(() => scrollAndFlash(document.getElementById('p-12'))); await settle(page);
            assert.equal(await focusOwner.evaluate(node => node === document.activeElement), true,
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
    for (const locale of Object.keys(fixtures).filter(l => browserLocales.includes(l))) for (const width of [1440, 320]) {
      await check('localized navigation spacing ' + locale + ' ' + width, async () => {
        const {page, errors, writes} = await createPage(browser, locale, width);
        try {
          await page.emulateMedia({colorScheme: width === 320 ? 'dark' : 'light'});
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
          const nextAction = guideBody.locator('.ctl.primary:visible');
          assert.equal(await guideBody.locator('[data-analysis-guide-action]:visible').count(), 1,
            'Turning on analysis is the sole next action before selecting any measurement');
          assert.equal(await nextAction.textContent(), await page.evaluate(() => uiLabel('analysis_guide_enable')));
          assert.equal(await page.locator('#reader-guide-counted').isVisible(), false,
            'The first step omits explanations for marks that are still off');
          assert.ok(await guideBody.evaluate(node => node.scrollWidth <= node.clientWidth),
            'Help retains readable, bounded horizontal layout');
          await guideBody.screenshot({path: path.join(artifacts, `guide-${locale}-${width}.png`)});
          if (width === 320) {
            await page.evaluate(() => {
              document.documentElement.style.fontSize = '200%';
              window.dispatchEvent(new Event('resize'));
            });
            assert.ok(await guideBody.evaluate(node => {
              const box = node.getBoundingClientRect();
              return node.scrollWidth <= node.clientWidth && box.left >= 0 && box.right <= innerWidth;
            }), 'The next action remains within the guide at 200% text size');
            await page.evaluate(() => {
              document.documentElement.style.removeProperty('font-size');
              window.dispatchEvent(new Event('resize'));
            });
          }
          await page.keyboard.press('Escape');
          assert.equal(await guide.evaluate(node => node.open), false);
          assert.equal(await guide.locator('summary').evaluate(node => node === document.activeElement), true);
          await guide.locator('summary').press('Enter');
          await page.keyboard.press('Tab');
          assert.equal(await nextAction.evaluate(node => node === document.activeElement), true);
          await nextAction.press('Enter');
          assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'true');
          assert.equal(await page.locator('#style-layer').evaluate(node => node === document.activeElement), true);
          const overview = page.locator('#workbench-overview-open');
          assert.equal(await overview.locator('.reader-control-label').isVisible(), true,
            'The analysis overview keeps a visible label on compact screens');
          await overview.press('Enter');
          await page.locator('[data-analysis-workflow="compare"]').click();
          await page.locator('[data-analysis-section-target="matrix"]').press('Enter');
          await settle(page);
          assert.equal(await page.locator('#matrix').isVisible(), true);
          assert.equal(await page.locator('#matrix > h2').evaluate(node => node === document.activeElement), true,
            'The keyboard action focuses the destination heading');
          await page.locator('#workbench-overview-back').click();
          await settle(page);
          assert.equal(await page.locator('#chapters').isVisible(), true);
          await page.locator('#style-layer').selectOption('');
          const none = await page.locator('#reader-analysis-guide-state').textContent();
          assert.notEqual(none, off, 'Analysis on without a metric is distinct from Analysis off');
          const reference = page.locator('#reader-metric-reference');
          assert.equal(await reference.evaluate(link => link.hash), '#measurements');
          const measures = await page.locator('#style-layer option').evaluateAll(options =>
            options.filter(option => option.value).map(option => ({
              value:option.value, title:option.textContent, unit:option.dataset.unit, hint:option.dataset.hint
            })));
          assert.equal(measures.length, 12);
          for (const measure of measures) {
            await page.locator('#style-layer').selectOption(measure.value);
            assert.equal(await reference.evaluate(link => link.hash), '#measure-' + measure.value);
            const description = await page.locator('#reader-analysis-guide-state').textContent();
            assert.ok(description.includes(measure.title), `${locale}: ${measure.value} uses its localized title`);
            if (!measure.unit) assert.equal(description, measure.title, `${locale}: evidence-only metrics need no empty unit`);
            assert.equal(await page.locator('#reader-metric-definition').textContent(), measure.hint);
          }
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
          assert.equal(await guide.locator('[data-analysis-guide-action="explore"]').evaluate(button => {
            const box = button.getBoundingClientRect();
            return button.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2));
          }), true, 'The open guide escapes the toolbar scrollport and exposes its actions without scrolling the toolbar');
          await guide.locator('[data-analysis-guide-action="explore"]').click();
          await settle(page);
          assert.equal(await page.locator('#reader-inspector').isVisible(), true);
          assert.equal(await page.locator('#reader-inspector-close').evaluate(node => node === document.activeElement), true);
          assert.equal(await page.locator('#reader-inspector .paragraph-values > summary').evaluate(node => {
            const text = document.createRange();
            text.selectNodeContents(node);
            return text.getClientRects().length;
          }), 1, 'The passage values label fits on a line');
          await page.keyboard.press('Escape');
          await settle(page);
          assert.equal(await page.locator('#reader-inspector').isVisible(), false);
          assert.equal(await guide.locator('summary').evaluate(node => node === document.activeElement), true,
            'Closing paragraph details returns to the visible help trigger');
          await guide.locator('summary').click();
          assert.equal(await nextAction.getAttribute('data-analysis-guide-action'), 'example');
          await nextAction.press('Enter');
          await settle(page);
          await page.waitForFunction(() => !document.getElementById('analysis-evidence-card').hidden);
          assert.equal(await page.locator('#style-layer').inputValue(), 'asl');
          await page.keyboard.press('Escape');
          await settle(page);
          assert.equal(await guide.locator('summary').evaluate(node => node === document.activeElement), true,
            'Closing measurement evidence returns to the visible help trigger');
          await setAnalysisOption(page, 'analysis-evidence-enabled', false);
          await page.locator('#reader-focus').click();
          assert.equal(await guide.isVisible(), false, 'Focus reading hides optional guidance');
          await page.locator('#reader-focus').click();
          assert.equal(await guide.isVisible(), true);
          assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), false);
          await setAnalysisOption(page, 'analysis-evidence-enabled', true);
          await closeAnalysisSettings(page);
          if (width === 320) await page.setViewportSize({width, height: 480});
          await page.locator('#manuscript-reader-controls').evaluate(node => { node.scrollTop = 0; });
          await settle(page);
          const controls = await page.locator('#manuscript-reader-controls').boundingBox();
          if (width === 320) assert.ok(controls.height <= 480 * .45 + 1,
            'Compact analysis leaves most of the short viewport available for manuscript prose');
          const documentScroll = await page.evaluate(() => scrollY);
          for (const selector of ['#style-layer', '#reader-analysis-options > summary',
            '#reader-inspect-current', '#reader-settings > summary', '#reader-focus', '#workbench-overview-open',
            '#workspace-reader-toggle']) {
            await page.locator(selector).evaluate(node => node.scrollIntoView({block:'nearest', inline:'nearest'}));
            await settle(page);
            const box = await page.locator(selector).boundingBox();
            assert.ok(box && box.y >= controls.y - 1 && box.y + box.height <= controls.y + controls.height + 1,
              `${selector} remains reachable within the compact controls: ${JSON.stringify({box, controls})}`);
            assert.ok(Math.abs(await page.evaluate(() => scrollY) - documentScroll) <= 1,
              'Reaching wrapped toolbar actions scrolls only the controls, preserving the manuscript position');
          }
          await page.screenshot({path: path.join(artifacts, `analysis-controls-${locale}-${width}.png`)});
          if (width === 320) await page.setViewportSize({width, height: 900});
          await page.locator('#manuscript-analysis-toggle').click();
          await openOverview(page);
          assert.equal(await guide.isVisible(), false, 'Reader guidance does not compete with the overview');
          const reason = page.locator('#review-passage-reason');
          assert.equal(await reason.isVisible(), true);
          assert.equal(await page.locator('[data-review-passage]').getAttribute('aria-describedby'), 'review-passage-reason');
          const navigation = page.locator('[data-analysis-workflows]');
          const entries = navigation.locator('[data-analysis-workflow]');
          assert.equal(await entries.count(), 3);
          assert.equal(await entries.first().evaluate(button => getComputedStyle(button).textAlign), 'start');
          const boxes = await entries.evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().toJSON()));
          for (let index = 1; index < boxes.length; index++) {
            const previous = boxes[index - 1], current = boxes[index];
            assert.ok(current.y > previous.y ? current.y - previous.bottom >= 4 : current.x - previous.right >= 4,
              'Workflow entries retain visible spacing instead of touching');
          }
          await page.screenshot({path: path.join(artifacts, `${locale}-${width}.png`)});
          if (width === 320) {
            await entries.first().focus();
            await page.keyboard.press('Tab'); await page.keyboard.press('Tab');
            assert.equal(await entries.last().evaluate(node => node === document.activeElement), true,
              'Workflow choices remain reachable in ordinary keyboard order');
            const last = await entries.last().boundingBox(), bounds = await navigation.boundingBox();
            assert.ok(last.x >= bounds.x - 1 && last.x + last.width <= bounds.x + bounds.width + 1,
              'The final workflow entry remains wholly readable');
            await openAnalysisSection(page, 'matrix');
            const matrix = await page.locator('#matrix').boundingBox();
            assert.ok(matrix.y < 900 && matrix.y + matrix.height > 0,
              'The chosen chapter matrix arrives in the viewport');
            await page.screenshot({path: path.join(artifacts, `${locale}-${width}-matrix.png`)});
          }
          await openAnalysisSection(page, 'style');
          await page.locator('#style-tab-heatmap').click();
          const metric = page.locator('#heatmap [data-metric-feature=hd_d]').first();
          const priorMetric = await page.locator('#style-layer').inputValue();
          await metric.focus(); await metric.press('Enter');
          if (width === 320) await page.setViewportSize({width, height: 480});
          const dialog = page.locator('#analysis-metric-context');
          assert.equal(await dialog.isVisible(), true);
          assert.equal(await page.locator('#metric-context-no-layer').isVisible(), true);
          assert.equal(await page.locator('#metric-context-values tr').count(), 16);
          assert.ok((await page.locator('#metric-context-definition').textContent()).length > 20);
          const comparison = await dialog.evaluate(node => {
            const data = JSON.parse(node.dataset.metricContext);
            const feature = data.features.hd_d;
            return {
              typical: node.querySelector('#metric-context-typical').textContent,
              expected: feature.median + ' ' + feature.unit,
            };
          });
          assert.equal(comparison.typical, comparison.expected, 'The typical value has the same unit as the chapter');
          const tiles = dialog.locator('.metric-context-comparison > div');
          const value = await tiles.first().boundingBox();
          const typical = await tiles.last().boundingBox();
          assert.equal(value.y, typical.y, 'The chapter and reference values stay side by side');
          const breakdown = dialog.locator('#metric-context-details');
          assert.equal(await breakdown.locator('.table-wrap').isVisible(), false,
            'The opening state shows the selected measurement before the full table');
          await breakdown.locator('summary').press('Enter');
          assert.equal(await breakdown.locator('.table-wrap').isVisible(), true);
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
          await openAnalysisSection(page, 'style');
          await page.locator('#style-tab-dimensions').click();
          await page.locator('#dimensions [data-dimension-loading]').first().click();
          const origin = page.locator('#metric-context-origin');
          assert.equal(await origin.isVisible(), true);
          assert.ok(!(await origin.textContent()).match(/dim_loading|dim_poles/),
            'Axis captions use the owning localized label pack, not missing global UI keys');
          await page.screenshot({path: path.join(artifacts, `metric-origin-${locale}-${width}.png`)});
          await page.keyboard.press('Escape');
          await openAnalysisSection(page, 'matrix');
          const baseline = page.locator('#matrix-revision-baseline');
          await baseline.waitFor({state: 'visible'});
          assert.equal(await baseline.locator('a').getAttribute('href'), `/guides/metrics/${locale}.html#revisions`);
          const differences = page.locator('#matrix tr[data-chapter-num="1"] .chapter-revision-delta');
          assert.deepEqual(await differences.allTextContents(), await page.evaluate(() => {
            const lang = document.documentElement.lang;
            const signed = (value, digits) => new Intl.NumberFormat(lang, {minimumFractionDigits: digits,
              maximumFractionDigits: digits, signDisplay: 'always'}).format(value);
            return [signed(12345, 0), signed(0.05, 1), uiLabel('measurement_percentage_point_change').replace('{value}', signed(25, 1))];
          }));
          assert.ok(await differences.evaluateAll(nodes => nodes.every(delta => delta.scrollWidth <= delta.clientWidth)));
          assert.equal(await page.locator('#matrix tr[data-chapter-num="2"] .chapter-revision-delta').count(), 0);
          if (locale === 'de') await page.screenshot({path: path.join(artifacts, `matrix-differences-${width}.png`)});
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
