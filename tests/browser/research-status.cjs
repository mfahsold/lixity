// Startup status sharing keeps explicit refreshes fresh on desktop and mobile.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {startNativeServer} = require('./support/native-server.cjs');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-research-status-'));
const source = `
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
project = Path(sys.argv[1]) / 'synthetic-project'
api.init(project, title='Synthetic request sharing')
api.create_dossier(project, title='Synthetic notes', body='## Evidence\\n\\nAn invented reading note.')
manuscript = project / 'manuscript.md'
manuscript.write_text('# Synthetic request sharing\\n\\n## Chapter One\\n\\nThe invented keeper opens the harbour gate. A visitor waits beside the quay.\\n\\nThe blue notebook rests on the desk. All notes in this fixture are synthetic.\\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.research_dir = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.exports_dir = str(Path(sys.argv[1]) / 'exports')
LixityServerHandler.language = 'en'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'project': str(project)}), flush=True)
server.serve_forever()
`;

function files(root) {
  const result = {};
  function visit(directory) {
    for (const entry of fs.readdirSync(directory, {withFileTypes: true})) {
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) visit(file);
      else result[path.relative(root, file)] = fs.readFileSync(file).toString('base64');
    }
  }
  visit(root);
  return result;
}

(async () => {
  const server = await startNativeServer(source, artifacts);
  const before = files(server.fixture.project);
  let browser;
  try {
    browser = await launchChromium();
    for (const viewport of [{width: 1440, height: 950}, {width: 390, height: 850}]) {
      const page = await browser.newPage({viewport, reducedMotion: 'reduce'});
      const errors = [], writes = [], statuses = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/api/**', async route => {
        const request = route.request(), url = new URL(request.url());
        if (request.method() !== 'GET') { writes.push(url.pathname); await route.abort(); return; }
        if (url.pathname === '/api/research/status') {
          let release;
          const held = new Promise(resolve => {release = resolve;});
          statuses.push({url: request.url(), release});
          await held;
        }
        await route.continue();
      });
      await page.goto(server.fixture.url);
      await expect.poll(() => statuses.length).toBe(1);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.equal(statuses.length, 1, 'Workspace and manuscript startup share the pending status observation');
      const review = page.waitForResponse(response => new URL(response.url()).pathname === '/api/research/manuscript-review');
      statuses[0].release();
      assert.equal((await review).status(), 200, 'Manuscript review receives the shared startup result');
      await expect(page.locator('#r-active-root')).toContainText('synthetic-project');
      assert.equal(statuses.length, 1, 'Both startup consumers complete from one status GET');

      // An automatic observation held in flight must not absorb an explicit refresh.
      await page.evaluate(() => { window.statusAutomatic = researchApiGet('research/status', undefined, true); });
      await expect.poll(() => statuses.length).toBe(2);
      await page.evaluate(() => { window.statusRefresh = refreshResearchProjectInfo(); });
      await expect.poll(() => statuses.length).toBe(3);
      statuses[1].release();
      await page.evaluate(() => window.statusAutomatic);
      await page.evaluate(() => { window.statusJoined = researchApiGet('research/status', undefined, true); });
      assert.equal(statuses.length, 3, 'Older settlement cannot evict the current explicit observation');
      statuses[2].release();
      await page.evaluate(() => Promise.all([window.statusRefresh, window.statusJoined]));

      await page.locator('#chapters [data-reader-paragraph]').first().click();
      await page.locator('#manuscript-context-menu [data-reader-action="values"]').click();
      await expect(page.locator('#reader-inspector')).toBeVisible();
      await page.locator('#reader-inspector [data-reader-action="research"]').click();
      await expect(page.locator('[data-passage-research]')).toHaveAttribute('data-state', 'empty');
      await page.screenshot({path: path.join(artifacts, `research-status-${viewport.width}.png`)});

      // Leaving a token context invalidates pending sharing even when returning
      // to the same root before another status request observes the departure.
      await page.evaluate(() => { window.statusDeparted = researchApiGet('research/status', undefined, true); });
      await expect.poll(() => statuses.length).toBe(4);
      await page.evaluate(() => {
        const manager = document.getElementById('research-manager');
        window.originalResearchToken = manager.dataset.researchToken;
        manager.dataset.researchToken = 'synthetic-other-root';
      });
      await page.evaluate(() => {
        document.getElementById('research-manager').dataset.researchToken = window.originalResearchToken;
      });
      await page.evaluate(() => { window.statusReturned = researchApiGet('research/status', undefined, true); });
      await expect.poll(() => statuses.length, {timeout: 2000}).toBe(5);
      statuses[3].release(); statuses[4].release();
      await page.evaluate(() => Promise.all([window.statusDeparted, window.statusReturned]));
      assert.deepEqual(errors, [], 'The rendered context flow has no runtime errors');
      assert.deepEqual(writes, [], 'The browser journey issues no writes');
      await page.close();
    }
    assert.deepEqual(files(server.fixture.project), before, 'Browser reads leave the synthetic project byte-for-byte unchanged');
    console.log('Research status browser checks passed; synthetic screenshots: ' + artifacts);
  } finally {
    if (browser) await browser.close();
    await server.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
