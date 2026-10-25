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
from lixity.workspace_labels import WORKSPACE_LABELS
project = Path(sys.argv[1])
manuscript = project / 'manuscript.md'
manuscript.write_text('## Opening\\n\\nRain falls across a synthetic garden.\\n')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
pages = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    LixityServerHandler.language = locale
    LixityServerHandler.refresh()
    name = locale + '.html'
    (project / name).write_text(LixityServerHandler.dashboard_html, encoding='utf-8')
    pages[locale] = name
LixityServerHandler.language = 'en'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
labels = {locale: {key: value for key, value in pack.items() if key.startswith('site_export_limit_')}
          for locale, pack in WORKSPACE_LABELS.items()}
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'pages': pages, 'labels': labels}), flush=True)
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
    for (const [locale, filename] of Object.entries(server.fixture.pages)) for (const width of [1440, 320]) {
      const localized = await browser.newPage({viewport:{width, height:900}});
      localized.on('pageerror', e => errors.push(e.message));
      await localized.route(server.fixture.url + '/', route => route.fulfill({
        contentType:'text/html', body:fs.readFileSync(path.join(artifacts, filename), 'utf8')}));
      let category = 'research_response_bytes';
      await localized.route('**/api/site-preflight', route => route.fulfill({status:413, contentType:'application/json',
        body:JSON.stringify({ok:false, message:'English backend detail <img src=x onerror=alert(1)>',
          preflight:{schema_version:'lixity-site-preflight-error/1', ok:false, complete:false, files_written:false,
            limit:category, observed_bytes:200, limit_bytes:100, overflow_bytes:100}})}));
      await localized.goto(server.fixture.url);
      await localized.locator('#tab-view-project').click();
      await localized.locator('#project-actions > summary').click();
      await localized.locator('#btn-site-export').click();
      for (const [limit, key] of [['research_record_bytes','research'], ['research_response_bytes','research'], ['publication_bytes','publication'], ['bundle_bytes','bundle']]) {
        category = limit;
        await localized.locator('#site-export-check').click();
        await expect(localized.locator('#site-export-status')).toContainText(server.fixture.labels[locale]['site_export_limit_' + key]);
        await expect(localized.locator('#site-export-status')).toContainText(server.fixture.labels[locale].site_export_limit_incomplete);
        await expect(localized.locator('#site-export-status')).not.toContainText('English backend detail');
        if (limit === 'research_record_bytes') {
          await expect(localized.locator('#site-export-status')).not.toContainText(server.fixture.labels[locale].site_export_limit_scope);
        }
        const details = localized.locator('#site-export-preflight details');
        assert.equal(await details.evaluate(node => node.open), false);
        await details.locator('summary').click();
        await expect(details.locator('pre')).toContainText('English backend detail <img');
        await expect(details.locator('img')).toHaveCount(0);
        assert(await localized.locator('#modal-site-export').evaluate(n => n.scrollWidth <= n.clientWidth + 1));
      }
      await localized.locator('#modal-site-export').screenshot({path:path.join(artifacts, `limit-${locale}-${width}.png`)});
      if (locale === 'en') {
        category = 'unknown_future_limit';
        await localized.locator('#site-export-check').click();
        await expect(localized.locator('#site-export-status')).toContainText('English backend detail');
        await expect(localized.locator('#site-export-preflight')).toBeHidden();
      }
      await localized.close();
    }
    assert.deepEqual(errors, []);
    console.log('Site preflight: native size checks and seven-locale bounded failures, safe technical details, unknown-category fallback and desktop/mobile layout passed. ' + artifacts);
  } finally { if (browser) await browser.close(); await server.close(); }
})().catch(e => { console.error(e); process.exitCode=1; });
