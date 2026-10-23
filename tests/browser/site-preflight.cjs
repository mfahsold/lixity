// Explicit export checks share native preparation and leave selected files untouched.
const {startNativeServer} = require('./support/native-server.cjs');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const assert = require('node:assert/strict');
const {expect} = require(path.join(playwrightModule, 'test'));
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-site-preflight-'));
(async () => {
  const server = await startNativeServer(`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
project = Path(sys.argv[1])
manuscript = project / 'manuscript.md'
manuscript.write_text('## Opening\\n\\nRain falls across a synthetic garden.\\n')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}'}), flush=True)
server.serve_forever()
`, artifacts);
  let browser;
  try {
    browser = await launchChromium();
    const page = await browser.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    let checks = 0, downloads = 0;
    page.on('request', r => { if (r.url().endsWith('/api/site-preflight')) checks++; if (r.url().endsWith('/api/site-export')) downloads++; });
    for (const width of [1440, 320]) {
      await page.setViewportSize({width, height:900});
      await page.goto(server.fixture.url);
      await page.locator('#tab-view-project').click();
      await page.locator('#project-actions > summary').click();
      await page.locator('#btn-site-export').click();
      const check = page.locator('#site-export-check');
      await expect(check).toBeVisible();
      assert.equal(checks, width === 1440 ? 0 : 1, 'Opening the dialog must not prepare a package');
      await check.click();
      await expect(page.locator('#site-export-preflight')).toBeVisible();
      await expect(page.locator('#site-export-preflight')).toContainText('MiB');
      await expect(page.locator('#site-export-preflight')).toContainText('not verified');
      await expect(check).toBeEnabled();
      await expect(check).toBeFocused();
      assert.equal(downloads, 0);
      assert(await page.locator('#modal-site-export').evaluate(n => n.scrollWidth <= n.clientWidth + 1));
      await page.locator('#modal-site-export').screenshot({path:path.join(artifacts, `check-${width}.png`)});
      await page.locator('#site-export-research').check();
      await expect(page.locator('#site-export-preflight')).toBeHidden();
    }
    assert.deepEqual(errors, []);
    console.log('Site preflight: explicit request, actual package sizes, no download, invalidation and desktop/mobile layout passed. ' + artifacts);
  } finally { if (browser) await browser.close(); await server.close(); }
})().catch(e => { console.error(e); process.exitCode=1; });
