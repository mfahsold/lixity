// Clicking a paragraph strip chip must show the paragraph: an off-screen block
// scrolls into view and flashes instead of silently toggling (the reported
// "clicks do not get through" behaviour).
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const {spawn} = require('node:child_process');
const {createInterface} = require('node:readline');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const root = path.resolve(__dirname, '../..');
const python = process.env.PYTHON_BIN || path.join(root, '.venv/bin/python');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-paragraph-feedback-'));

(async () => {
  const server = spawn(python, ['-u', '-c', `
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
`, artifacts], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, stdio: ['ignore', 'pipe', 'pipe']});
  const lines = createInterface({input: server.stdout});
  let stderr = '';
  server.stderr.on('data', data => {stderr = (stderr + data).slice(-4000);});
  try {
    const fixture = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Synthetic server startup timed out: ' + stderr)), 15000);
      lines.once('line', line => {clearTimeout(timer); resolve(JSON.parse(line));});
      server.once('error', error => {clearTimeout(timer); reject(error);});
      server.once('exit', code => {clearTimeout(timer); reject(new Error(`Synthetic server exited ${code}: ${stderr}`));});
    });
    const browser = await launchChromium();
    try {
      for (const width of [1280, 360]) {
        const page = await browser.newPage({viewport: {width, height: 800}});
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
        assert.deepEqual(errors, []);
        await page.close();
      }
    } finally {await browser.close();}
    console.log(`Paragraph feedback: click-open scrolls and flashes the off-screen paragraph at 1280/360. Screenshots: ${artifacts}`);
  } finally {server.kill();}
})().catch(error => {console.error(error);process.exitCode = 1;});
