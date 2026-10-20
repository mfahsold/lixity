// Shared chrome and overlays stay attached, reachable and outside manuscript text.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-overlay-layout-'));
const fixtures = pythonFixture(`
import json
from dashboard_fixtures import full_dashboard as render
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
original = render.__globals__['render_dashboard']
fixtures = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    def localized(*args, **kwargs):
        return original(*args, **{**kwargs, 'labels': labels, 'language_key': locale})
    render.__globals__['render_dashboard'] = localized
    fixtures[locale] = render()
print(json.dumps(fixtures))
`, {root});

async function settle(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}
async function viewportContains(locator) {
  return locator.evaluate(el => {
    const box = el.getBoundingClientRect();
    return box.width > 0 && box.height > 0 && box.left >= 0 && box.right <= innerWidth + 1
      && box.top >= 0 && box.bottom <= innerHeight + 1;
  });
}

(async () => {
  const browser = await launchChromium(), failures = [];
  async function check(name, run) {
    try { await run(); }
    catch (error) { failures.push(name + ': ' + error.message); console.error('FAIL ' + name + ': ' + error.message); }
  }
  try {
    for (const [locale, html] of Object.entries(fixtures)) {
      const page = await browser.newPage({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
      page.setDefaultTimeout(5000);
      const errors = [], writes = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://lixity.test/**', route => {
        const request = route.request();
        if (request.method() !== 'GET') writes.push(request.url());
        return route.fulfill(request.url().includes('/api/') ? {json: {ok: true, initialized: true,
          project_id: 'synthetic-overlay-project', records: [], sources: [], dossiers: [], claims: []}}
        : {contentType: 'text/html', body: html});
      });
      await page.goto('http://lixity.test/');
      await check(locale + ' sidebar identity and disclosure', async () => {
        const toggle = page.locator('#workspace-navigation-toggle');
        const before = await toggle.innerHTML(), box = await toggle.boundingBox();
        const identity = await page.locator('.workspace-shell .product-name').boundingBox();
        assert.ok(box.width >= 40 && box.width <= 44 && box.height >= 40 && box.height <= 44,
          'The sidebar control has a compact reachable target');
        assert.ok(box.y < identity.y + identity.height && box.y + box.height > identity.y,
          'The sidebar control sits beside product identity');
        assert.equal(await toggle.getAttribute('aria-pressed'), null);
        await toggle.focus(); await page.keyboard.press('Enter');
        assert.equal(await toggle.getAttribute('aria-expanded'), 'false');
        assert.equal(await toggle.innerHTML(), before, 'The sidebar glyph stays stable');
        assert.equal(await page.locator('.workspace-shell .product-name').isVisible(), true);
        const collapsed = await toggle.boundingBox(), collapsedIdentity = await page.locator('.workspace-shell .product-name').boundingBox();
        assert.equal(collapsed.y, box.y, 'The sidebar control stays in its learned row');
        assert.ok(collapsed.y < collapsedIdentity.y + collapsedIdentity.height && collapsed.y + collapsed.height > collapsedIdentity.y,
          'Collapsed navigation retains product identity beside its control');
        assert.equal(await toggle.evaluate(el => document.activeElement === el), true);
        if (locale === 'en') {
          await page.keyboard.press('Escape');
          await page.screenshot({path: path.join(artifacts, 'sidebar-collapsed.png')});
        }
        await page.keyboard.press('Enter');
        assert.equal(await toggle.getAttribute('aria-expanded'), 'true');
        await page.keyboard.press('Escape');
        await page.screenshot({path: path.join(artifacts, `sidebar-${locale}.png`)});
        if (locale === 'en') {
          await page.emulateMedia({colorScheme: 'dark'});
          await page.screenshot({path: path.join(artifacts, 'sidebar-dark.png')});
          await page.emulateMedia({colorScheme: 'light'});
        }
        await page.setViewportSize({width: 1024, height: 900}); await settle(page);
        assert.equal(await page.evaluate(() => document.activeElement.dataset.view), 'analysis',
          'The selected destination receives focus when resizing hides the sidebar control');
      });
      await page.setViewportSize({width: 1440, height: 900}); await page.goto('http://lixity.test/');
      await check(locale + ' settings resize and short viewport', async () => {
        await page.locator('#reader-settings > summary').click();
        await page.setViewportSize({width: 390, height: 480}); await settle(page);
        const settings = page.locator('.reader-settings-body');
        assert.ok(await viewportContains(settings), 'An open settings popup follows the resized viewport');
        await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
        await page.setViewportSize({width: 320, height: 480}); await settle(page);
        assert.ok(await viewportContains(settings), 'Enlarged settings fit a short narrow viewport');
        await page.locator('#reader-spacing').scrollIntoViewIfNeeded();
        assert.ok(await viewportContains(page.locator('#reader-spacing')), 'The final setting remains reachable');
        await page.screenshot({path: path.join(artifacts, `settings-${locale}-320.png`)});
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('#reader-settings').evaluate(el => el.open), false);
      });
      for (const width of [1024, 901]) {
        await page.setViewportSize({width, height: 900}); await page.goto('http://lixity.test/');
        await check(locale + ' paragraph gutter ' + width, async () => {
          const action = page.locator('.reader-paragraph-actions').first();
          await action.click(); await page.locator('[data-reader-action="values"]').click();
          for (const split of [null, 35, 75]) {
            if (split !== null) await page.locator('#workspace-reader-divider').evaluate((el, value) => {
              el.focus(); el.dispatchEvent(new KeyboardEvent('keydown', {key: value === 35 ? 'Home' : 'End', bubbles: true}));
            }, split);
            await action.scrollIntoViewIfNeeded(); await settle(page);
            const box = await action.boundingBox(), divider = await page.locator('#workspace-reader-divider').boundingBox();
            assert.ok(box.x + box.width <= divider.x, `Paragraph actions stay before the divider at split ${split}`);
            const prose = await page.locator('#chapters .ptext-inner > p').first().boundingBox();
            assert.ok(prose.x + prose.width <= box.x, 'The action target stays outside manuscript text');
          }
          if (locale === 'en') await page.screenshot({path: path.join(artifacts, `gutter-${width}.png`)});
        });
      }
      await page.setViewportSize({width: 320, height: 480}); await page.goto('http://lixity.test/');
      await page.evaluate(() => {
        document.documentElement.style.fontSize = '200%';
        const dialog = document.querySelector('#modal-research-revision');
        document.querySelector('#research-revision-form').hidden = true;
        document.querySelector('#research-revision-history').hidden = false;
        document.querySelector('#research-revision-kind').textContent = 'Dossier · Synthetic title';
        document.querySelector('#research-revision-history-detail').textContent = 'Synthetic saved history. '.repeat(400);
        dialog.showModal();
      });
      await check(locale + ' enlarged revision close', async () => {
        await page.locator('#research-revision-history-detail').evaluate(el => el.scrollIntoView());
        assert.ok(await viewportContains(page.locator('#modal-research-revision .modal-close')),
          'Reading enlarged saved history keeps Close in the viewport');
        await page.screenshot({path: path.join(artifacts, `revision-${locale}-320.png`)});
        await page.locator('#modal-research-revision .modal-close').click();
        assert.equal(await page.locator('#modal-research-revision').evaluate(el => el.open), false);
      });
      // Exercise the same source-context definition-list markup at the shared
      // stylesheet boundary; source API/context guards are covered separately.
      await page.evaluate(() => {
        document.body.className = '';
        document.body.innerHTML = '<div class="research-details-body"><dl><dt>Origin URL</dt><dd id="origin-url">https://example.invalid/'
          + 'A'.repeat(350) + '</dd></dl></div>';
        const style = document.createElement('style');
        style.textContent = '* {line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}';
        document.head.appendChild(style);
      });
      await check(locale + ' provenance line wrapping', async () => {
        const contained = await page.locator('#origin-url').evaluate(el => {
          const range = document.createRange(); range.selectNodeContents(el);
          const box = el.getBoundingClientRect();
          return Array.from(range.getClientRects()).every(line => line.left >= box.left - 1 && line.right <= box.right + 1);
        });
        assert.ok(contained, 'Long provenance text lines stay inside their definition box');
        await page.screenshot({path: path.join(artifacts, `provenance-${locale}-320.png`)});
      });
      assert.deepEqual(errors, [], locale + ' runtime errors');
      assert.deepEqual(writes, [], locale + ' chrome and reading never write data');
      await page.close();
    }
    assert.deepEqual(failures, [], failures.join('\n'));
    console.log('Overlay layout: seven locales, sidebar identity, resized settings, split gutters, enlarged revision Close and provenance text passed; ' + artifacts);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
