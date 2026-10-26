// Real native review decisions are project-local and never manuscript tasks.
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const {expect} = require(require('node:path').join(playwrightModule, 'test'));
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const {execFileSync} = require('node:child_process');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-analysis-triage-'));
const python = process.env.PYTHON_BIN || path.join(root, '.venv/bin/python');

(async () => {
  const server = await startNativeServer(`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
base = Path(sys.argv[1]); project = base / 'project'; project.mkdir()
text = '## First\\n\\nShe walks. She waits. She watches.\\n\\nShe walks. She waits. She watches. She walked. She waited. She watched.\\n\\n## Second\\n\\nHe walks. He waits. He watches. He walked. He waited. He watched.\\n'
source = project / 'manuscript.md'; source.write_text(text)
(project / 'lixity.toml').write_text('manuscript = "manuscript.md"\\nlanguage = "en"\\n')
LixityServerHandler.workspace_root = str(project); LixityServerHandler.source_input = str(source)
LixityServerHandler.exports_dir = str(project / 'exports'); LixityServerHandler.language = 'en'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'source': str(source), 'project': str(project)}), flush=True)
server.serve_forever()
`, artifacts);
  let browser;
  try {
    browser = await launchChromium();
    const page = await browser.newPage({viewport:{width:1440,height:950}, reducedMotion:'reduce'});
    const errors = [], markerWrites = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (request.method() === 'POST' && request.url().includes('/api/marker-')) markerWrites.push(request.url());
    });
    const original = fs.readFileSync(server.fixture.source);
    const rows = page.locator('#flags .flag-row');
    async function overview() {
      await page.locator('#tab-view-analysis').click();
      await page.locator('#workbench-overview-open').click();
      await page.locator('#flags').scrollIntoViewIfNeeded();
      await rows.first().locator('.triage-read-cell button').scrollIntoViewIfNeeded();
      await expect(rows.first().locator('.triage-read-cell button')).toBeVisible();
      await expect(page.locator('#flags .triage-choice').first()).toBeEnabled();
    }
    await page.goto(server.fixture.url);
    await overview();
    assert.ok(await rows.count() >= 2);
    await expect(page.locator('#flags .flag-row[role="button"]')).toHaveCount(0);
    await expect(page.locator('#flags [data-marker-kind]')).toHaveCount(0);
    await expect(page.locator('#flags')).toContainText('Review passages in context');
    await rows.first().locator('.triage-reason summary').click();
    await expect(rows.first().locator('.triage-reason')).toContainText('Present markers: 3; past markers: 3');
    await expect(page.locator('#manuscript-analysis-panels')).toBeVisible();
    await rows.first().locator('.triage-choice').selectOption('kept');
    await rows.first().locator('[data-triage-save]').click();
    await expect(rows.first().locator('.triage-saved-state')).toHaveText('Deliberately kept');
    await expect(page.locator('#triage-progress')).toContainText('1 /');
    await page.reload(); await overview();
    await expect(rows.first().locator('.triage-saved-state')).toHaveText('Deliberately kept');
    await page.locator('#triage-status-filter').selectOption('unreviewed');
    assert.equal(await page.locator('#flags .flag-row:not([hidden])').count(), await rows.count() - 1);
    await page.locator('#triage-next').click();
    await expect(page.locator('#chapters')).toBeVisible();
    await page.locator('#workbench-overview-open').click();
    await page.locator('#triage-status-filter').selectOption('');
    await rows.nth(1).locator('.triage-choice').selectOption('later');
    await rows.nth(1).locator('[data-triage-save]').click();
    await expect(rows.nth(1).locator('.triage-saved-state')).toHaveText('Review later');
    await expect(page.locator('#triage-progress')).toContainText('1 /');
    for (const width of [1440, 320]) {
      await page.setViewportSize({width,height:950});
      await page.locator('#flags').scrollIntoViewIfNeeded();
      if (width === 320) {
        const positions = await rows.first().evaluate(row => ({
          read:row.querySelector('.triage-read-cell').getBoundingClientRect().bottom,
          decision:row.querySelector('.triage-decision-cell').getBoundingClientRect().top,
        }));
        assert.ok(positions.read <= positions.decision, 'Reading precedes decisions without overlapping mobile cards');
      }
      await page.screenshot({path:path.join(artifacts,`review-${width}.png`)});
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    }
    assert.deepEqual(fs.readFileSync(server.fixture.source), original);
    execFileSync(python, ['-c', "from pathlib import Path; import sys; p=Path(sys.argv[1]); p.write_text(p.read_text()+'\\nNew unrelated text.\\n')", server.fixture.source]);
    await page.reload(); await overview();
    await expect(rows.first().locator('.triage-saved-state')).toHaveText('Earlier decision is stale');
    await expect(page.locator('#triage-progress')).toContainText('0 /');
    await page.locator('#triage-status-filter').selectOption('stale');
    assert.ok(await page.locator('#flags .flag-row:not([hidden])').count() >= 2);
    await rows.first().locator('.triage-choice').selectOption('kept');
    let release;
    const held = new Promise(resolve => {release=resolve;});
    await page.route('**/api/analysis-review', async route => {
      await held;
      await route.fulfill({status:409,json:{ok:false,message:'Synthetic stale state'}});
    });
    await rows.first().locator('[data-triage-save]').click();
    await expect(rows.first().locator('.triage-choice')).toBeDisabled();
    release();
    await expect(page.locator('#triage-save-status')).toContainText('could not be confirmed');
    await expect(page.locator('#triage-reload')).toBeVisible();
    assert.deepEqual(markerWrites, []);
    assert.deepEqual(errors, []);
    console.log(`Native analysis triage: explicit decisions, reload, no manuscript/task writes, deferred count, stale source, filters, next-passage, conflict recovery and desktop/mobile passed. Screenshots: ${artifacts}`);
  } finally {
    if (browser) await browser.close();
    await server.close();
  }
})().catch(error => {console.error(error);process.exitCode=1;});
