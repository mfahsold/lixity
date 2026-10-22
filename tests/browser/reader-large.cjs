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
from lixity.ui.dashboard import render_analysis
from lixity.ui.manuscript_document import reader_blocks
paragraphs = [('Clara walked through the quiet garden and watched the birds beside the fountain. '
               'The morning light crossed the stone path while rain gathered beyond the gate. '
               'She carried a notebook and paused beside the old window. '
               'The courtyard remained still as the distant street slowly filled with people and voices.')
              for _ in range(2000)]
paragraphs[-1] = paragraphs[-1].replace('Clara', 'Clara1999', 1)
source = '\\n\\n'.join('## Chapter %d\\n\\n' % (index // 100 + 1) + '\\n\\n'.join(paragraphs[index:index + 100])
                       for index in range(0, 2000, 100))
config, resolved = resolve_document_config(source, 'en', project_config={})
thresholds = resolve_thresholds(project_config={})
analysis = analyze_document(source, config, thresholds)
print(json.dumps(render_analysis(analysis, resolved, title='Synthetic long manuscript',
    flag_min_severity=thresholds.flag_min_severity, controls=True, enabled_actions=['analyze'],
    reader_document=reader_blocks(source, config, analysis.paragraphs))))
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
      await search.fill('Clara1999 walked'); await search.press('Enter');
      assert.equal(await page.locator('#chapters .ptext:visible').count(), 1);
      assert.equal(await last.isVisible(), true);
      await search.press('Escape');
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
    console.log('Long manuscript: 100k synthetic words/2000 paragraphs ready, searchable, selectable and reversible at 1440/320; ordinary/reduced motion bounds geometry reads and feedback targets.');
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
