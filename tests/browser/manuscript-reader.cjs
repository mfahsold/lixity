// Reading keeps one exact manuscript tree; tools appear only on demand.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-manuscript-reader-'));
const selectedQuote = '😀 A synthetic reader sentence [literal.*+?]';
const fixtures = pythonFixture(`
import json
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
from dashboard_fixtures import full_dashboard as render
render.__globals__['SAMPLE'] = render.__globals__['SAMPLE'].replace('Ich trinke Kaffee.',
    '😀 A synthetic reader sentence [literal.*+?] <img src=x onerror=window.readerInjected=true>.', 1)
render.__globals__['SAMPLE'] += '\\n\\n## Reading position\\n\\n' + '\\n\\n'.join(
    'Synthetic reading paragraph %d. ' % number + 'A calm courtyard gives this paragraph enough text to wrap naturally. ' * 6
    for number in range(1, 31))
original = render.__globals__['render_dashboard']
fixtures = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    def localized(*args, **kwargs):
        fixtures[locale] = {'text': [paragraph.text for paragraph in args[1]]}
        return original(*args, **{**kwargs, 'labels': labels, 'language_key': locale,
            'enabled_actions': ['analyze', 'research-reader', 'research-manuscript-link'],
            'manuscript_pdf_token': 'synthetic-project-token', 'research_context_token': 'synthetic-research-token',
            'manuscript_source_sha256': 'a' * 64})
    render.__globals__['render_dashboard'] = localized
    html = render()
    fixtures[locale]['html'] = html
print(json.dumps(fixtures))
`, {root});
const dossier = {id: 'synthetic-dossier', project_id: 'synthetic-project', title: 'Synthetic reading notes',
  revision: 1, body: '## Context\n\nA saved synthetic dossier beside the manuscript.\n\n' + 'Context for reading. '.repeat(100),
  editable_sections: ['Context'], citations: [], sections: ['Context'], tags: [], evidence_count: 0};

async function createPage(browser, fixture, width) {
  const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion: 'reduce', hasTouch: width <= 390});
  const errors = [], writes = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('http://lixity.test/**', route => {
    const request = route.request(), url = new URL(request.url());
    if (request.method() !== 'GET') {
      writes.push(url.pathname);
      return route.fulfill({status: 400, json: {ok: false, message: 'Reading never requires a write'}});
    }
    if (url.pathname === '/api/research/dossiers') return route.fulfill({json: url.searchParams.has('id')
      ? {ok: true, ...dossier} : {ok: true, project_id: dossier.project_id, dossiers: [dossier]}});
    if (url.pathname === '/api/research/manuscript-review') return route.fulfill({json: {
      ok: true, schema_version: 'research-manuscript-review-local/1', project_id: dossier.project_id,
      snapshot: 'synthetic-snapshot', source_state: 'available', current_source_sha256: 'a'.repeat(64), links: [],
    }});
    if (url.pathname.startsWith('/api/')) return route.fulfill({json: {
      ok: true, initialized: true, project_id: dossier.project_id, snapshot: 'synthetic-snapshot',
      records: [], sources: [], dossiers: [dossier], claims: [], decisions: [], candidates: [],
    }});
    return route.fulfill({contentType: 'text/html', body: fixture.html});
  });
  await page.goto('http://lixity.test/');
  await page.locator('#tab-view-analysis').click();
  return {page, errors, writes};
}

async function selectQuote(paragraph, quote) {
  await paragraph.evaluate((p, value) => {
    const text = p.textContent, start = text.indexOf(value);
    if (start < 0) throw new Error('The requested synthetic quote is absent');
    const walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT), nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    let offset = 0, from, to;
    for (const node of nodes) {
      if (!from && start >= offset && start < offset + node.length) from = [node, start - offset];
      if (start + value.length > offset && start + value.length <= offset + node.length) to = [node, start + value.length - offset];
      offset += node.length;
    }
    const range = document.createRange(); range.setStart(...from); range.setEnd(...to);
    const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
    document.dispatchEvent(new Event('selectionchange'));
  }, quote);
}

async function sourceState(page) {
  return page.locator('#chapters .ptext').evaluateAll(panels => panels.map(panel => ({
    id: panel.id, start: panel.dataset.start, end: panel.dataset.end, hash: panel.dataset.paragraphSha256,
    text: panel.querySelector('.ptext-inner > p')?.textContent,
  })));
}

async function settleGeometry(page) {
  // Display changes restore the paragraph anchor on the next animation frame.
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

(async () => {
  const browser = await launchChromium();
  try {
    for (const [locale, fixture] of Object.entries(fixtures)) for (const width of locale === 'en' ? [1440, 390, 320] : [1440, 320]) {
      const {page, errors, writes} = await createPage(browser, fixture, width);
      const analysis = page.locator('#manuscript-analysis-toggle');
      assert.equal(await analysis.isVisible(), true, 'Analysis has one explicit visible display control');
      assert.equal(await analysis.getAttribute('aria-pressed'), 'false', 'The workspace opens with analysis hidden');
      const analysisName = await analysis.getAttribute('aria-label');
      assert.ok(analysisName, 'The Analysis toggle has a localized, constant accessible name');
      assert.equal(await page.locator('select#manuscript-mode:visible').count(), 0,
        'Reading and analysis do not require switching manuscript presentations');
      assert.equal(await page.locator('body').evaluate(body => body.classList.contains('manuscript-reading')), true);
      assert.deepEqual(await page.locator('#chapters .ptext .ptext-inner > p').allTextContents(), fixture.text,
        'Every source paragraph appears exactly once, in manuscript order');
      assert.equal(await page.locator('#chapters .ptext').count(), fixture.text.length);
      assert.equal(await page.locator('#chapters .strip').first().isVisible(), false,
        'Reading starts with text rather than paragraph metric strips');
      assert.equal(await page.locator('#chapters .stats').first().isVisible(), false);
      if (locale === 'en') {
        for (const colorScheme of ['light', 'dark']) {
          await page.emulateMedia({colorScheme});
          assert.equal(await page.locator('#chapters .ptext').evaluateAll(panels =>
            panels.every(panel => getComputedStyle(panel).backgroundColor === 'rgba(0, 0, 0, 0)')), true,
          `Continuous prose has no paragraph-card backgrounds in ${colorScheme} mode`);
        }
        await page.emulateMedia({colorScheme: 'light'});
      }
      assert.equal(await page.locator('#manuscript-context-menu').isVisible(), false);
      assert.equal(await page.locator('#reader-inspector').isVisible(), false);
      assert.equal(await page.evaluate(() => Boolean(window.readerInjected)), false);
      assert.equal(await page.locator('#chapters img, #chapters script').count(), 0,
        'Manuscript-like markup remains inert source text');
      const readingWidth = await page.evaluate(() => ({viewport: innerWidth, document: document.documentElement.scrollWidth}));
      assert.ok(readingWidth.document <= readingWidth.viewport,
        `The reader does not force horizontal scrolling (${locale} ${width}): ${JSON.stringify(readingWidth)}`);
      const anchors = await sourceState(page);
      assert.ok(anchors.every(item => item.id && Number(item.start) <= Number(item.end) && /^[a-f0-9]{64}$/.test(item.hash)));

      const first = page.locator('#chapters .ptext').first();
      await first.evaluate(node => {window.readerCanonicalFirst = node;});
      const id = await first.getAttribute('id');
      const actions = first.locator(`.reader-paragraph-actions[data-reader-paragraph="${id}"]`);
      assert.equal(await actions.count(), 1, 'Paragraph tools have a discoverable native button');
      assert.ok(await actions.getAttribute('aria-label'), 'Paragraph tools have a localized accessible name');
      await actions.click();
      const menu = page.locator('#manuscript-context-menu');
      assert.equal(await menu.isVisible(), true);
      assert.equal(await menu.getAttribute('role'), 'menu');
      await menu.locator('[data-reader-action=values]').click();
      const inspector = page.locator('#reader-inspector');
      assert.equal(await inspector.isVisible(), true, 'Values open on request in the paragraph inspector');
      assert.ok((await page.locator('#reader-inspector-body').textContent()).trim());
      assert.equal(await inspector.locator('.reader-passage-context [data-manuscript-links-paragraph]').getAttribute('data-manuscript-links-paragraph'), id,
        'The passage lens routes research to the inspected paragraph, independently of scroll position');
      assert.ok((await inspector.locator('.reader-passage-context p').textContent()).includes(await first.getAttribute('data-start')),
        'The passage lens names its manuscript line context');
      assert.equal(await analysis.getAttribute('aria-pressed'), 'false', 'Local values do not enable global Analysis');
      await analysis.click(); await analysis.click();
      assert.equal(await inspector.isVisible(), true, 'Changing global Analysis does not dismiss local values');
      if (locale === 'en') for (const colorScheme of ['light', 'dark']) {
        await page.emulateMedia({colorScheme});
        await inspector.screenshot({path: path.join(artifacts, `passage-values-${colorScheme}-${width}.png`)});
        await page.screenshot({path: path.join(artifacts, `passage-values-context-${colorScheme}-${width}.png`)});
      }
      await page.emulateMedia({colorScheme: 'light'});
      if (locale === 'en' && width === 390) {
        await inspector.locator('[data-manuscript-links-paragraph]').tap();
        assert.equal(await page.locator('#tab-view-research').getAttribute('aria-selected'), 'true');
        await page.locator('#workbench-return').tap();
        assert.equal(await page.locator('#tab-view-analysis').getAttribute('aria-selected'), 'true');
        assert.equal(await inspector.isVisible(), true, 'Touch research return preserves the local passage tool');
      }
      await page.locator('#workbench-overview-open').click();
      await page.locator('#workbench-overview-back').click();
      assert.equal(await inspector.isVisible(), true, 'Returning from overview restores the explicit local tool');
      assert.equal(await analysis.getAttribute('aria-pressed'), 'false', 'Overview return restores global Analysis independently');
      if (width === 1440) {
        const insetWidth = await page.locator('#workspace-analysis-body').evaluate(node => node.getBoundingClientRect().width);
        await page.locator('#reader-focus').click(); await settleGeometry(page);
        assert.equal(await inspector.isVisible(), false);
        assert.ok(await page.locator('#workspace-analysis-body').evaluate(node => node.getBoundingClientRect().width) > insetWidth,
          'Focus reading releases the document column space reserved for the hidden inspector');
        await page.keyboard.press('Escape'); await settleGeometry(page);
        assert.equal(await page.locator('#reader-focus').getAttribute('aria-pressed'), 'false',
          'Escape exits focus before touching the temporarily hidden inspector');
        assert.equal(await inspector.isVisible(), true, 'Leaving focus restores the open inspector');
      }
      if (locale === 'en') {
        const firstValues = await page.locator('#reader-inspector-body').textContent();
        const nextActions = page.locator('#chapters .ptext').nth(1).locator('.reader-paragraph-actions');
        await nextActions.click();
        await page.keyboard.press('Escape');
        assert.equal(await inspector.isVisible(), true, 'Closing a later paragraph menu leaves the existing inspector open');
        assert.equal(await page.locator('#reader-inspector-body').textContent(), firstValues,
          'A later context menu does not silently change the inspected passage');
      }
      await page.locator('#reader-inspector-close').click();
      assert.equal(await inspector.isVisible(), false, 'The inspector has an equally direct close action');
      assert.equal(await actions.evaluate(button => document.activeElement === button), true,
        'Closing the first passage inspector returns to its own trigger after a later menu');
      assert.deepEqual(await sourceState(page), anchors, 'Context tools preserve exact manuscript text and anchors');

      assert.equal(await analysis.getAttribute('aria-pressed'), 'false', 'Closing local values preserves global Analysis Off');
      await analysis.click();
      assert.equal(await analysis.getAttribute('aria-label'), analysisName, 'Analysis keeps its accessible name when active');
      assert.equal(await page.locator('#chapters .strip').first().isVisible(), true,
        'Analysis exposes restrained paragraph diagnostics alongside the same prose');
      await page.locator('#filter-flags').check();
      await analysis.click();
      await settleGeometry(page);
      assert.equal(await page.locator('#chapters .chapter').evaluateAll(chapters => chapters.every(chapter => {
        const style = getComputedStyle(chapter); return style.display !== 'none' && style.visibility !== 'hidden';
      })), true, 'Hiding analysis shows every chapter after filtering flagged passages');
      assert.deepEqual(await sourceState(page), anchors, 'Hiding analysis preserves the full source tree');
      await analysis.click();
      assert.equal(await page.locator('#filter-flags').isChecked(), true,
        'Showing analysis retains the explicitly chosen diagnostic filter');
      await page.locator('#filter-flags').uncheck();
      await analysis.click();
      await page.locator('#workbench-overview-open').click();
      assert.equal(await page.locator('#manuscript-analysis-panels').isVisible(), true,
        'Dense comparisons have an explicit overview surface');
      assert.equal(await page.locator('#workbench-overview-back').isVisible(), true);
      assert.deepEqual(await sourceState(page), anchors, 'The overview keeps the canonical manuscript mounted');
      await page.locator('#workbench-overview-back').click();
      assert.equal(await first.evaluate(node => node === window.readerCanonicalFirst), true,
        'Returning from the overview restores the same manuscript nodes');
      assert.equal(await page.locator('#chapters').isVisible(), true);
      assert.equal(await analysis.getAttribute('aria-pressed'), 'false',
        'Returning from a temporary overview restores Analysis Off');
      await settleGeometry(page);
      await page.locator('#text-search').fill('Fenster');
      await page.locator('#chapters .ptext.text-miss').first().waitFor({state: 'attached'});
      assert.ok(await page.locator('#chapters .ptext.text-miss').count() > 0);
      assert.equal(await page.locator('#chapters .ptext.text-miss').evaluateAll(panels =>
        panels.every(panel => getComputedStyle(panel).display === 'none')), true,
        'Search excludes nonmatches in the continuous manuscript');
      await page.locator('#text-search-clear').click();
      if (locale === 'de') {
        await page.locator('#chapters').scrollIntoViewIfNeeded();
        await page.screenshot({path: path.join(artifacts, `reading-${width}.png`)});
      }

      if (locale === 'en') {
        await first.locator('.ptext-inner > p').click({button: 'right'});
        assert.equal(await menu.isVisible(), true, 'Right click opens the same paragraph tools');
        await page.keyboard.press('Escape');
        assert.equal(await menu.isVisible(), false);
        await actions.focus();
        await page.keyboard.press('Shift+F10');
        assert.equal(await menu.isVisible(), true, 'The keyboard context-menu shortcut reaches paragraph tools');
        const beforeArrow = await page.evaluate(() => document.activeElement?.dataset.readerAction);
        await page.keyboard.press('ArrowDown');
        assert.notEqual(await page.evaluate(() => document.activeElement?.dataset.readerAction), beforeArrow,
          'Arrow keys move between context actions');
        await page.keyboard.press('Escape');
        assert.equal(await menu.isVisible(), false);
        assert.equal(await actions.evaluate(button => document.activeElement === button), true,
          'Closing context tools returns keyboard focus to their trigger');
        await page.keyboard.press('Shift+F10');
        await page.keyboard.press('Tab');
        assert.equal(await menu.isVisible(), false, 'Tab dismisses the temporary context menu');
        assert.equal(await page.locator('#chapters .ptext').nth(1).locator('.reader-paragraph-actions')
          .evaluate(button => document.activeElement === button), true,
        'Tab proceeds to the next paragraph action instead of returning to the cancelled menu trigger');

        await actions.click();
        await menu.locator('[data-reader-action=todo]').click();
        const markerNote = page.locator('[data-marker-editor] .marker-note');
        await markerNote.waitFor({state: 'visible'});
        await markerNote.fill('A synthetic unsaved reading note');
        await markerNote.press('Escape');
        assert.equal(await page.locator('[data-marker-editor]').count(), 0,
          'Contextual markers reuse the explicit, reversible note editor');

        const paragraph = first.locator('.ptext-inner > p');
        const originalSize = await paragraph.evaluate(p => parseFloat(getComputedStyle(p).fontSize));
        await page.locator('#reader-settings > summary').click();
        await page.locator('#reader-text-larger').click();
        await settleGeometry(page);
        assert.ok(await paragraph.evaluate(p => parseFloat(getComputedStyle(p).fontSize)) > originalSize,
          'Reader zoom changes the text size rather than scaling a canvas');
        await page.locator('#reader-text-smaller').click();
        await settleGeometry(page);
        assert.equal(await paragraph.evaluate(p => parseFloat(getComputedStyle(p).fontSize)), originalSize);
        await page.locator('#reader-width').selectOption('narrow');
        await page.locator('#reader-spacing').selectOption('relaxed');
        const relaxed = await paragraph.evaluate(p => parseFloat(getComputedStyle(p).lineHeight));
        await page.locator('#reader-spacing').selectOption('compact');
        assert.ok(await paragraph.evaluate(p => parseFloat(getComputedStyle(p).lineHeight)) < relaxed,
          'Line spacing changes the manuscript reading geometry');
        await page.locator('#reader-spacing').selectOption('relaxed');
        await page.locator('#reader-settings > summary').click();

        if (width === 1440) {
          const readingAnchor = page.locator('#chapters .ptext').nth(20);
          await readingAnchor.evaluate(panel => panel.scrollIntoView({block: 'start'}));
          const before = await readingAnchor.evaluate(panel => panel.getBoundingClientRect().top);
          await page.locator('#reader-settings > summary').click();
          await page.locator('#reader-text-larger').click();
          await settleGeometry(page);
          const after = await readingAnchor.evaluate(panel => panel.getBoundingClientRect().top);
          assert.ok(Math.abs(after - before) < 80,
            'Changing text size keeps the current manuscript passage in view');
          await page.locator('#reader-text-smaller').click();
          await settleGeometry(page);
          await page.locator('#reader-settings > summary').click();
        }

        const focus = page.locator('#reader-focus');
        await focus.click();
        await settleGeometry(page);
        assert.equal(await focus.getAttribute('aria-pressed'), 'true');
        assert.equal(await paragraph.isVisible(), true);
        await focus.click();
        await settleGeometry(page);
        assert.equal(await focus.getAttribute('aria-pressed'), 'false', 'The focus control reverses its own action');

        await focus.click();
        await settleGeometry(page);
        await actions.click();
        await menu.locator('[data-reader-action=values]').click();
        assert.equal(await focus.getAttribute('aria-pressed'), 'false',
          'Opening paragraph values exits focus mode so the inspector is reachable');
        assert.equal(await inspector.isVisible(), true, 'Values requested in focus mode remain visible');
        await page.locator('#reader-inspector-close').click();
        await settleGeometry(page);

        const directPassage = page.locator('#chapters .ptext').nth(20);
        await directPassage.evaluate(panel => window.LixityManuscriptLinks.navigate(panel));
        await settleGeometry(page);
        const directGeometry = await directPassage.evaluate(panel => ({
          top: panel.getBoundingClientRect().top,
          controlsBottom: document.getElementById('manuscript-reader-controls').getBoundingClientRect().bottom,
          viewport: innerHeight,
        }));
        assert.ok(directGeometry.top >= directGeometry.controlsBottom - 1 && directGeometry.top < directGeometry.viewport,
          `An exact manuscript return lands below the reader controls (${width}): ${JSON.stringify(directGeometry)}`);

        await page.locator('#reader-chapter').selectOption('ch-2');
        assert.equal(await page.locator('#ch-2').evaluate(chapter => {
          const box = chapter.getBoundingClientRect(); return box.top < innerHeight && box.bottom > 0;
        }), true, 'Chapter navigation reveals the selected chapter');
        await page.locator('#reader-chapter').selectOption('ch-1');
        await page.locator('#ch-2').evaluate(chapter => chapter.scrollIntoView({block: 'start'}));
        await page.locator('#reader-chapter').selectOption('ch-1');
        assert.equal(await page.locator('#reader-chapter').inputValue(), '',
          'The chapter command resets so the same destination remains selectable');
        await paragraph.scrollIntoViewIfNeeded();
        await selectQuote(paragraph, selectedQuote);
        const selectionTools = page.locator('#manuscript-selection-tools');
        await selectionTools.waitFor({state: 'visible'});
        assert.equal(await selectionTools.getAttribute('role'), 'toolbar');
        await selectionTools.locator('[data-reader-action=link]').click();
        await page.locator('#manuscript-link-dialog[open]').waitFor();
        assert.equal(await page.locator('#manuscript-link-quote').textContent(), selectedQuote,
          'The contextual link uses the unchanged exact selected quote');
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('#manuscript-link-dialog').evaluate(dialog => dialog.open), false);
        assert.deepEqual(await sourceState(page), anchors);

        await focus.click();
        await settleGeometry(page);
        await actions.click();
        await menu.locator('[data-reader-action=companion]').click();
        assert.equal(await focus.getAttribute('aria-pressed'), 'false',
          'Opening a companion exits focus mode so the requested dossier is reachable');
        assert.equal(await page.locator('#workspace-reader-panel').isVisible(), true,
          'A dossier requested from focused reading is visible');
        await page.locator('#workspace-reader-dossier').selectOption(dossier.id);
        await page.locator('#workspace-reader-body .research-dossier-body-rendered').waitFor();
        const divider = page.locator('#workspace-reader-divider');
        if (width >= 1100) {
          assert.equal(await divider.isVisible(), true);
          assert.equal(await divider.getAttribute('role'), 'separator');
          assert.equal(await divider.getAttribute('aria-orientation'), 'vertical');
          const initial = Number(await divider.getAttribute('aria-valuenow'));
          await divider.focus(); await divider.press('ArrowLeft');
          assert.ok(Number(await divider.getAttribute('aria-valuenow')) < initial,
            'The keyboard divider changes the relative manuscript width');
          await divider.press('ArrowRight');
          assert.equal(Number(await divider.getAttribute('aria-valuenow')), initial);
          const box = await divider.boundingBox();
          await page.mouse.move(box.x + box.width / 2, box.y + Math.min(box.height / 2, 50));
          await page.mouse.down(); await page.mouse.move(box.x - 70, box.y + 50, {steps: 6}); await page.mouse.up();
          assert.ok(Number(await divider.getAttribute('aria-valuenow')) < initial,
            'Dragging the divider gives either document more horizontal space');
        } else assert.equal(await divider.isVisible(), false, 'Stacked mobile reading does not expose an unusable divider');
        await page.locator('#workspace-reader-close').click();
        assert.deepEqual(await sourceState(page), anchors);

        await page.reload(); await page.locator('#tab-view-analysis').click();
        await page.locator('#reader-settings > summary').click();
        assert.equal(await page.locator('#reader-width').inputValue(), 'narrow', 'Reader preferences survive reload');
        assert.equal(await page.locator('#reader-spacing').inputValue(), 'relaxed');
        assert.deepEqual(await page.locator('#chapters .ptext .ptext-inner > p').allTextContents(), fixture.text);
      }
      assert.deepEqual(writes, [], 'Reading and opening contextual tools never save data implicitly');
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log(`Manuscript reader: continuous exact text, reversible tools, seven desktop/mobile locales, keyboard context menus, typography, selection, focus and accessible dossier divider passed. Screenshots: ${artifacts}`);
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
