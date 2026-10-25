// Browser plugin unavailable: use the repository's Chromium helpers.
// A native synthetic project exercises the full decision-column layout.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const {startNativeServer} = require('./support/native-server.cjs');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-triage-layout-'));

(async () => {
  const server = await startNativeServer(`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
project = Path(sys.argv[1]) / 'project'; project.mkdir()
source = project / 'manuscript.md'
source.write_text('## Ein synthetisches Kapitel mit einem längeren Titel\\n\\n'
    'Ich gehe. Ich sehe. Ich komme.\\n\\n'
    'Ich gehe durch den Garten. Ich sehe die alten Bäume. Ich komme nach Hause. '
    'Ich ging durch den Garten. Ich sah die alten Bäume. Ich kam nach Hause.\\n\\n'
    'Ich ging. Ich sah. Ich kam.\\n\\n'
    'Ich gehe. Ich sehe. Ich komme.\\n')
(project / 'lixity.toml').write_text('manuscript = "manuscript.md"\\nlanguage = "de"\\n')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(source)
LixityServerHandler.exports_dir = str(project / 'exports')
LixityServerHandler.language = 'de'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'source': str(source)}), flush=True)
server.serve_forever()
`, artifacts);
  let browser;
  const measurements = [];
  try {
    browser = await launchChromium();
    const source = fs.readFileSync(server.fixture.source);
    for (const width of [1440, 1280, 1024, 768, 320]) {
      const page = await browser.newPage({viewport:{width,height:950}, reducedMotion:'reduce'});
      const errors = [], writes = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => {
        if (['error', 'warning'].includes(message.type())) errors.push(message.text());
      });
      page.on('request', request => {if (request.method() !== 'GET') writes.push(request.method());});
      try {
        await page.goto(server.fixture.url);
        await expect(page).toHaveTitle(/Lixity/);
        await page.locator('#tab-view-analysis').click();
        await page.locator('#workbench-overview-open').click();
        const row = page.locator('#flags .flag-row').first();
        const button = row.locator('.triage-read-cell button');
        await expect(button).toHaveText('Textstelle lesen');
        await expect(row.locator('.triage-choice')).toBeEnabled();
        await page.locator('#flags').scrollIntoViewIfNeeded();
        const dimensions = await row.evaluate(row => {
          const button = row.querySelector('.triage-read-cell button').getBoundingClientRect();
          const wrap = row.closest('.flags-wrap'), table = wrap.querySelector('table');
          return {buttonWidth:button.width, buttonHeight:button.height,
            tableWidth:table.getBoundingClientRect().width, wrapWidth:wrap.clientWidth,
            decisionRight:row.querySelector('.triage-choice').getBoundingClientRect().right,
            wrapRight:wrap.getBoundingClientRect().right,
            rowDisplay:getComputedStyle(row).display};
        });
        measurements.push({width,...dimensions});
        await page.screenshot({path:path.join(artifacts,`triage-${width}.png`)});
        assert.ok(dimensions.buttonWidth >= 100, `${width}: read action has a readable width (${JSON.stringify(dimensions)})`);
        assert.ok(dimensions.buttonHeight <= 60, `${width}: read label is not a vertical letter column`);
        if (width <= 1280) {
          assert.equal(dimensions.rowDisplay, 'grid', `${width}: compact records avoid overflowing columns`);
        }
        assert.ok(dimensions.tableWidth <= dimensions.wrapWidth + 1, `${width}: all columns fit the available pane`);
        assert.ok(dimensions.decisionRight <= dimensions.wrapRight, `${width}: decisions are not clipped`);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        await button.focus();
        await expect(button).toBeFocused();
        await expect(button).toBeInViewport();
        await page.keyboard.press('Tab');
        await expect(row.locator('.triage-choice')).toBeFocused();
        await page.keyboard.press('Shift+Tab');
        await expect(button).toBeFocused();
        if (width === 320) {
          await page.screenshot({path:path.join(artifacts,`triage-${width}-read-focus.png`)});
        }
        await page.keyboard.press('Enter');
        await expect(page.locator('#chapters')).toBeVisible();
        assert.deepEqual(errors, []);
        assert.deepEqual(writes, []);
      } finally {await page.close();}
    }
    assert.deepEqual(fs.readFileSync(server.fixture.source), source);
    console.log(JSON.stringify(measurements));
    console.log(`Native triage layout passed at five widths; screenshots: ${artifacts}`);
  } finally {
    if (browser) await browser.close();
    await server.close();
  }
})().catch(error => {console.error(error);process.exitCode=1;});
