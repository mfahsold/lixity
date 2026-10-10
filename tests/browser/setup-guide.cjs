const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-setup-guide-'));
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
import json
from lixity.ui import render_dashboard
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
fixtures = {}
for language in ('en','de','fr','es','it','pt','nl'):
    labels = {**get_language_profile(language).labels, **WORKSPACE_LABELS[language]}
    fixtures[language] = {'labels': labels, 'html': render_dashboard(
        [], [], labels=labels, language_key=language, controls=True,
        enabled_actions=['analyze','rebuild','nda-draft'])}
print(json.dumps(fixtures))
`], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024});
assert.equal(fixture.status, 0, fixture.error ? fixture.error.message : fixture.stderr);
const fixtures = JSON.parse(fixture.stdout);
(async () => {
  const browser = await launchChromium();
  try {
    for (const language of Object.keys(fixtures)) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 1000}, hasTouch: true});
      const requests = [], errors = [];
      let ocr = {ok: true, status: 'native_only', backend: 'native', pdftotext_available: true, pdftoppm_available: true};
      let zotero = {ok: true, schema_version: 'research-zotero-status-local/1', status: 'unavailable', local_api_enabled: null,
        safe_refresh_available: false, library_checked: false, message: '<img src=x onerror="window.setupInjected=true">'};
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://lixity.test/**', async route => {
        const url = new URL(route.request().url());
        if (url.pathname.startsWith('/api/')) {
          requests.push({path: url.pathname, method: route.request().method()});
          const data = url.pathname.endsWith('/ocr-status') ? ocr : url.pathname.endsWith('/zotero-status') ? zotero
            : {ok: true, initialized: false, project_root: '', ocr};
          return route.fulfill({json: data});
        }
        return route.fulfill({contentType: 'text/html', body: fixtures[language].html});
      });
      await page.goto('http://lixity.test/');
      assert.equal(await page.locator('#research-setup-guide').count(), 1);
      assert.equal(await page.locator('#research-setup-guide').isVisible(), true, 'Guide works without an archive');
      assert.equal(requests.filter(request => request.path.endsWith('/ocr-status') || request.path.endsWith('/zotero-status')).length, 0);
      await page.locator('#research-setup-guide > summary').click();
      const before = requests.length;
      await page.locator('#research-setup-check').click();
      await page.waitForFunction(() => !document.querySelector('#research-setup-check').disabled);
      assert.deepEqual(requests.slice(before).map(request => request.path).sort(), ['/api/research/ocr-status','/api/research/zotero-status']);
      assert.ok(requests.slice(before).every(request => request.method === 'GET'));
      assert.ok((await page.locator('#setup-ocr-reading').textContent()).includes(fixtures[language].labels.research_ocr_native));
      assert.ok((await page.locator('#setup-zotero-reading').textContent()).includes(fixtures[language].labels.setup_zotero_unavailable));
      assert.ok(!(await page.locator('#setup-zotero-reading').textContent()).includes('<img'));
      assert.equal(await page.locator('#research-setup-guide img, #research-setup-guide script').count(), 0);
      // Nothing was found working yet, so both instruction blocks are shown.
      assert.equal(await page.locator('#setup-zotero-steps').isVisible(), true);
      assert.equal(await page.locator('#setup-ocr-steps').isVisible(), true);
      assert.equal(await page.evaluate(() => Boolean(window.setupInjected)), false);
      assert.ok((await page.locator('#research-setup-guide').textContent()).includes(fixtures[language].labels.setup_language_example));
      zotero = {...zotero, status: 'ready', local_api_enabled: true, safe_refresh_available: true};
      ocr = {...ocr, status: 'ready', backend: 'tesseract', requested_languages: ['eng'], missing_languages: []};
      await page.locator('#research-setup-check').click();
      await page.waitForFunction(() => !document.querySelector('#research-setup-check').disabled);
      assert.ok((await page.locator('#setup-zotero-reading').textContent()).includes(fixtures[language].labels.setup_zotero_ready));
      assert.ok((await page.locator('#setup-zotero-reading').textContent()).includes(fixtures[language].labels.setup_library_unchecked));
      assert.ok((await page.locator('#setup-ocr-reading').textContent()).includes(fixtures[language].labels.research_ocr_tesseract_ready));
      // Both components now report ready, so their instructions must be gone:
      // showing them beside a success message reads as a failed check.
      assert.equal(await page.locator('#setup-zotero-steps').isVisible(), false);
      assert.equal(await page.locator('#setup-ocr-steps').isVisible(), false);
      zotero = {...zotero, status: 'connected', safe_refresh_available: false};
      await page.locator('#research-setup-check').click();
      await page.waitForFunction(() => !document.querySelector('#research-setup-check').disabled);
      assert.ok((await page.locator('#setup-zotero-reading').textContent()).includes(fixtures[language].labels.setup_zotero_connected));
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.locator('#research-setup-guide').screenshot({path: path.join(artifacts, `${language}-${width}.png`)});
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log(`Setup guide: explicit metadata-only checks, unavailable/ready scope, inert messages and seven desktop/mobile locales passed. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
