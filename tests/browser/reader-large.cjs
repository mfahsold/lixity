// Long documents exercise style invalidation that small UI fixtures cannot expose.
const assert = require('node:assert/strict');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const root = path.resolve(__dirname, '../..');
const html = pythonFixture(`
import json
from lixity.config import resolve_thresholds
from lixity.pipeline import analyze_document, resolve_document_config
from lixity.ui import DashboardContent, DashboardOptions, render_analysis
from lixity.ui.manuscript_document import reader_blocks
paragraphs = [('Clara walked through the quiet garden and watched the birds beside the fountain. '
               'The morning light crossed the stone path while rain gathered beyond the gate. '
               'She carried a notebook and paused beside the old window. '
               'The courtyard remained still as the distant street slowly filled with people and voices.')
              for _ in range(2000)]
paragraphs[-1] = paragraphs[-1].replace('Clara', 'Clara1999', 1)
source = '\\n\\n'.join('## Chapter %d\\n\\n' % (index // 100 + 1) + '\\n\\n'.join(paragraphs[index:index + 100])
                       for index in range(0, 2000, 100))
source += '\\n\\n> A frame with the painted compass.\\n'
config, resolved = resolve_document_config(source, 'en', project_config={})
thresholds = resolve_thresholds(project_config={})
analysis = analyze_document(source, config, thresholds)
print(json.dumps(render_analysis(analysis, resolved, title='Synthetic long manuscript',
    flag_min_severity=thresholds.flag_min_severity,
    options=DashboardOptions(controls=True, enabled_actions=['analyze']),
    content=DashboardContent(reader_document=reader_blocks(source, config, analysis.paragraphs)))))
`, {root});

(async () => {
  const browser = await launchChromium();
  try {
    for (const width of [1440, 320]) for (const reducedMotion of ['reduce', 'no-preference']) {
      const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion});
      const errors = [], writes = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://lixity.test/**', route => {
        const request = route.request();
        if (request.method() !== 'GET') writes.push(request.method());
        return route.fulfill(new URL(request.url()).pathname.startsWith('/api/')
          ? {json: {ok: false, message: 'Synthetic offline project'}}
          : {contentType: 'text/html', body: html});
      });
      // Ordinary navigation timeout catches an unusable long-document startup;
      // this is a functional readiness check, not a millisecond benchmark gate.
      await page.goto('http://lixity.test/');
      const paragraphs = page.locator('#chapters .ptext');
      assert.equal(await paragraphs.count(), 2000);
      assert.equal(await page.locator('[data-reader-paragraph]').count(), 2000);
      const last = paragraphs.last();
      const identity = await last.evaluate(node => ({id: node.id, hash: node.dataset.paragraphSha256,
        start: node.dataset.start, end: node.dataset.end, text: node.querySelector('.ptext-inner > p').textContent}));
      assert.match(identity.text, /^Clara1999 walked/);
      const search = page.locator('#text-search');
      const measureSearch = width === 1440 && reducedMotion === 'reduce';
      const readSearchWork = () => page.evaluate(() => window.readSearchWork());
      if (measureSearch) await paragraphs.first().evaluate(panel => {
        toggleParagraph(paragraphChips[panel.id], true, true);
        const initialOpen = Array.from(document.querySelectorAll('#chapters .ptext.open'), node => node.id);
        const paragraph = panel.querySelector('p');
        manuscriptParagraphMarks[panel.id] = [{start: 0, end: 5}];
        manuscriptMotifMarks[panel.id] = [{start: 0, end: 5, motif: true, current: true}];
        renderParagraphText(paragraph, '');
        const markSelector = 'mark.manuscript-claim-hit.motif-hit';
        const existingMark = paragraph.querySelector(markSelector);
        if (!existingMark) throw new Error('Synthetic claim and motif marks were not rendered');
        const renders = [], folds = [];
        const originalRender = window.renderParagraphText;
        window.renderParagraphText = function (node, query) {
          renders.push([node.closest('.ptext').id, query]);
          return originalRender(node, query);
        };
        const originalToggle = window.toggleParagraph;
        window.toggleParagraph = function (chip, open, instant) {
          const panel = document.getElementById(chip.dataset.target);
          folds.push({id: panel.id, changed: panel.classList.contains('open') !== open});
          return originalToggle(chip, open, instant);
        };
        window.readSearchWork = () => ({renders: renders.splice(0), folds: folds.splice(0), initialOpen,
          open: Array.from(document.querySelectorAll('#chapters .ptext.open'), node => node.id),
          marksStable: paragraph.querySelector(markSelector) === existingMark});
      });
      await search.fill('Clara1999 walked'); await search.press('Enter');
      assert.equal(await page.locator('#chapters .ptext:visible').count(), 1);
      assert.equal(await last.isVisible(), true);
      if (measureSearch) {
        assert.equal(await last.locator('mark.text-hit').textContent(), 'Clara1999 walked');
        const initial = await readSearchWork();
        assert.deepEqual(initial.renders, [[identity.id, 'Clara1999 walked']]);
        assert.ok(initial.folds.every(fold => fold.changed));
        assert.equal(initial.marksStable, true);
        await search.fill('Clara1999'); await search.press('Enter');
        assert.equal(await last.locator('mark.text-hit').textContent(), 'Clara1999');
        const revised = await readSearchWork();
        assert.deepEqual(revised.renders, [[identity.id, 'Clara1999']]);
        assert.ok(revised.folds.every(fold => fold.id === identity.id && fold.changed));
        assert.equal(revised.marksStable, true);
        await search.press('Enter');
        const repeated = await readSearchWork();
        assert.deepEqual(repeated.renders, []);
        assert.deepEqual(repeated.folds, []);
      }
      await search.press('Escape');
      if (measureSearch) {
        const cleared = await readSearchWork();
        assert.deepEqual(cleared.renders, [[identity.id, '']]);
        assert.ok(cleared.folds.every(fold => fold.changed));
        assert.deepEqual(cleared.open, cleared.initialOpen);
        assert.equal(cleared.marksStable, true);
        assert.equal(await page.locator('mark.text-hit').count(), 0);
        const quote = page.locator('#chapters .reader-quote');
        const quoteText = await quote.textContent();
        await search.fill('painted compass'); await search.press('Enter');
        assert.equal(await quote.locator('mark.text-hit').textContent(), 'painted compass');
        const quoteHit = await quote.locator('mark.text-hit').elementHandle();
        await search.press('Enter');
        assert.equal(await quote.evaluate((node, mark) => node.querySelector('mark') === mark, quoteHit), true);
        await search.fill('compass'); await search.press('Enter');
        assert.equal(await quote.locator('mark.text-hit').textContent(), 'compass');
        await search.press('Escape');
        assert.equal(await quote.textContent(), quoteText);
      }
      await last.locator('.ptext-inner > p').evaluate(node => {
        const range = document.createRange(); range.selectNodeContents(node);
        const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
      });
      assert.equal(await page.evaluate(() => getSelection().toString()), identity.text);
      const toggle = page.locator('#manuscript-analysis-toggle');
      await toggle.click(); await toggle.click();
      assert.deepEqual(await last.evaluate(node => ({id: node.id, hash: node.dataset.paragraphSha256,
        start: node.dataset.start, end: node.dataset.end, text: node.querySelector('.ptext-inner > p').textContent})), identity);
      if (reducedMotion === 'no-preference') {
        await last.scrollIntoViewIfNeeded();
        await toggle.click();
        const work = await page.evaluate(() => {
          const chapters = document.getElementById('chapters');
          const visibleParagraphs = Array.from(chapters.querySelectorAll('.chapter')).filter(node => {
            const box = node.getBoundingClientRect(); return box.bottom > 0 && box.top < innerHeight;
          }).reduce((count, node) => count + node.querySelectorAll('.ptext').length, 0);
          const original = Element.prototype.getBoundingClientRect;
          let reads = 0;
          Element.prototype.getBoundingClientRect = function() {
            if (this.matches('.ptext')) reads++;
            return original.call(this);
          };
          try { LixityMotion.analysis(chapters); }
          finally { Element.prototype.getBoundingClientRect = original; }
          return {reads, visibleParagraphs, marked: chapters.querySelectorAll('.reader-layer-enter').length};
        });
        assert.ok(work.reads > 0 && work.reads <= work.visibleParagraphs,
          'Motion measures paragraphs in visible chapters, not the entire manuscript: ' + JSON.stringify(work));
        assert.ok(work.marked > 0 && work.marked <= 8, 'Normal motion remains bounded to eight visible feedback targets');
        await page.emulateMedia({reducedMotion: 'reduce'});
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        assert.equal(await page.locator('.reader-layer-enter').count(), 0, 'A live preference change clears layer feedback');
      }
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      assert.deepEqual(errors, []); assert.deepEqual(writes, []);
      await page.close();
    }
    console.log('Long manuscript: 100k synthetic words/2000 paragraphs ready, searchable, selectable and reversible at 1440/320; search changes only affected highlights and panels; motion bounds geometry reads and feedback targets.');
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
