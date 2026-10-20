const {startNativeServer} = require('./support/native-server.cjs');
// Clicking a paragraph strip chip must show the paragraph: an off-screen block
// scrolls into view and flashes instead of silently toggling (the reported
// "clicks do not get through" behaviour).
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-paragraph-feedback-'));

(async () => {
  const server = await startNativeServer(`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
project = Path(sys.argv[1]) / 'synthetic-project'
project.mkdir(parents=True)
chapters = []
for c in range(1, 10):
    paras = '\\n\\n'.join('Chapter %d paragraph %d carries several words for a visible block.' % (c, p) for p in range(1, 16))
    chapters.append('## Chapter %d\\n\\n%s' % (c, paras))
manuscript = project / 'manuscript.md'
manuscript.write_text('# Synthetic book\\n\\n' + '\\n\\n'.join(chapters) + '\\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.exports_dir = str(Path(sys.argv[1]) / 'exports')
LixityServerHandler.language = 'en'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}'}), flush=True)
server.serve_forever()
`, artifacts);
  try {
    const fixture = server.fixture;
    const browser = await launchChromium();
    try {
      for (const width of [1280, 360]) {
        const page = await browser.newPage({viewport: {width, height: 800}});
        await page.addInitScript(() => localStorage.setItem('lixity.manuscript.mode', 'inspect'));
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('request', request => assert.equal(new URL(request.url()).origin, new URL(fixture.url).origin,
          'Native workflow makes only disposable loopback requests'));
        await page.goto(fixture.url);
        await page.locator('#chapters .chip').first().waitFor();
        const chapter = page.locator('#chapters .chapter').nth(4);
        await chapter.scrollIntoViewIfNeeded();
        const chips = chapter.locator('.strip .chip');
        await chips.nth(0).click();
        for (let index = 1; index <= 6; index++) {
          const target = await chips.nth(index).getAttribute('data-target');
          const panel = page.locator('#' + target);
          const intersects = () => panel.evaluate(element => {
            const rect = element.getBoundingClientRect();
            return rect.top < innerHeight && rect.bottom > 0;
          });
          if (index === 6) assert.equal(await intersects(), false, 'The sixth paragraph starts outside the viewport');
          await chips.nth(index).click();
          if (index === 6) {
            await page.waitForFunction(selector => {
              const element = document.querySelector(selector);
              const rect = element.getBoundingClientRect();
              return element.classList.contains('open') && rect.top < innerHeight && rect.bottom > 0;
            }, '#' + target, {timeout: 5000});
            await page.waitForFunction(selector => document.querySelector(selector).classList.contains('flash'),
              '#' + target, {timeout: 2500});
            await panel.screenshot({path: path.join(artifacts, `paragraph-feedback-${width}.png`)});
            await chips.nth(index).click();
            assert.equal(await panel.evaluate(element => element.classList.contains('open')), false,
              'A second click closes the paragraph');
          }
        }
        // Chapter folding: the chevron folds the body; jumps expand it again.
        const foldToggle = chapter.locator("[data-chapter-toggle]");
        await foldToggle.click();
        assert.equal(await chapter.evaluate(el => el.classList.contains("collapsed")), true, "The toggle folds the chapter");
        assert.equal(await chapter.locator(".strip").isVisible(), false, "A folded chapter hides its strip");
        await foldToggle.click();
        assert.equal(await chapter.locator(".strip").isVisible(), true, "Unfolding restores the strip");
        await foldToggle.click();
        await page.locator('#text-search').fill('Chapter 5 paragraph 9 carries');
        await page.locator('#text-search').press('Enter');
        await page.waitForFunction(() => !document.querySelector('#ch-5').classList.contains('collapsed'),
          null, {timeout: 5000});
        await page.locator('#text-search').press('Escape');
        assert.deepEqual(errors, []);
        await page.close();
      }
    } finally {await browser.close();}
    console.log(`Paragraph feedback: click-open scrolls and flashes the off-screen paragraph at 1280/360. Screenshots: ${artifacts}`);
  } finally {await server.close();}
})().catch(error => {console.error(error);process.exitCode = 1;});
