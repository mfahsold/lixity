// Research destinations retain one named panel and visible overflow navigation.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const {pythonFixture} = require('./support/python-fixture.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-research-navigation-'));
const fixtures = pythonFixture(`
import json
from lixity.language import get_language_profile
from lixity.ui import render_dashboard
from lixity.workspace_labels import WORKSPACE_LABELS
print(json.dumps({locale:render_dashboard([], [], controls=True, title='Synthetic research navigation',
    labels={**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}, language_key=locale)
    for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl')}))
`, {root});

(async () => {
  const browser = await launchChromium();
  try {
    for (const [locale, html] of Object.entries(fixtures)) for (const width of [1440, 320]) for (const colorScheme of ['light', 'dark']) {
      const page = await browser.newPage({viewport:{width, height:900}, colorScheme, reducedMotion:'reduce'});
      const errors = [], writes = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://lixity.test/**', route => {
        const request = route.request(), url = new URL(request.url());
        if (request.method() !== 'GET') writes.push(url.pathname);
        if (url.pathname.startsWith('/api/')) return route.fulfill({json:{ok:true, initialized:true,
          project_id:'synthetic-project', project_root:'/synthetic-project', records:[], sources:[],
          dossiers:[], claims:[], decisions:[], links:[], rows:[], hits:[], snapshot:'synthetic-snapshot'}});
        return route.fulfill({contentType:'text/html', body:html});
      });
      await page.goto('http://lixity.test/');
      await expect(page).toHaveTitle(/Synthetic research navigation/);
      await page.locator('[data-view=research]').click();
      const tabs = page.locator('#research-tabs [role=tab]');
      await expect(tabs).toHaveCount(7);
      for (const key of ['dossiers', 'claims', 'decisions', 'review', 'sources', 'search', 'grounding']) {
        const tab = page.locator(`[data-rtab=${key}]`), panel = page.locator('#rtab-'+key);
        await expect(tab).toHaveAttribute('id', 'research-tab-'+key);
        await expect(tab).toHaveAttribute('aria-controls', 'rtab-'+key);
        await expect(panel).toHaveAttribute('role', 'tabpanel');
        await expect(panel).toHaveAttribute('aria-labelledby', 'research-tab-'+key);
      }
      const selected = page.locator('[data-rtab=dossiers]');
      await expect(selected).toHaveAttribute('aria-selected', 'true');
      await selected.focus(); await page.keyboard.press('ArrowRight');
      await expect(page.locator('[data-rtab=claims]')).toBeFocused();
      await expect(selected).toHaveAttribute('aria-selected', 'true');
      await page.keyboard.press('Enter');
      await expect(page.locator('#rtab-claims')).toBeVisible();
      await expect(page.locator('#rtab-dossiers')).toBeHidden();
      await expect(page.locator('[data-rtab=claims]')).toHaveAttribute('tabindex', '0');
      await expect(selected).toHaveAttribute('tabindex', '-1');
      await page.keyboard.press('End');
      await expect(page.locator('[data-rtab=grounding]')).toBeFocused();
      const activeBox = await page.locator('[data-rtab=grounding]').boundingBox();
      assert.ok(activeBox.x >= 0 && activeBox.x+activeBox.width <= width,
        `${locale}/${width}: the focused destination stays visible`);
      await page.keyboard.press('Enter');
      await expect(page.locator('#rtab-grounding')).toBeVisible();
      await expect(page.locator('.research-tab-pane:visible')).toHaveCount(1);
      if (width === 320) {
        const previous = page.locator('#research-navigation-previous');
        const next = page.locator('#research-navigation-next');
        await expect(previous).toBeVisible();
        await expect(next).toBeVisible();
        await expect(previous).toBeEnabled();
        await previous.click();
        await expect(page.locator('[data-rtab=grounding]')).toHaveAttribute('aria-selected', 'true');
        await expect(next).toBeEnabled();
        assert.ok(await next.getAttribute('aria-label'), 'Overflow controls are named');
      }
      await page.locator('[data-rtab=dossiers]').click();
      await expect(page.locator('#rtab-dossiers')).toBeVisible();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      assert.deepEqual(writes, [], 'Research view navigation does not save or retain data');
      assert.deepEqual(errors, []);
      if (locale === 'en' || locale === 'de') await page.locator('#research-manager').screenshot({
        path:path.join(artifacts, `${locale}-${width}-${colorScheme}.png`)});
      if (['de', 'pt'].includes(locale) && width === 320 && colorScheme === 'light') {
        await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
        for (const enlargedWidth of [390, 320]) {
          await page.setViewportSize({width:enlargedWidth, height:900});
          for (const tab of await tabs.all()) {
            await tab.focus();
            const fits = await tab.evaluate(button => {
              const box = button.getBoundingClientRect();
              const viewport = button.parentElement.getBoundingClientRect();
              return button.scrollWidth <= button.clientWidth + 1
                && button.scrollHeight <= button.clientHeight + 1
                && box.left >= viewport.left - 1 && box.right <= viewport.right + 1;
            });
            assert.ok(fits, `${locale}/${enlargedWidth}: enlarged destination text fits its button and scrollport`);
          }
          const heights = await tabs.evaluateAll(buttons => buttons.map(button => button.getBoundingClientRect().height));
          assert.ok(Math.max(...heights) - Math.min(...heights) <= 1,
            `${locale}/${enlargedWidth}: wrapped destination labels keep the strip aligned`);
          await page.screenshot({path:path.join(artifacts, `${locale}-${enlargedWidth}-enlarged.png`)});
        }
      }
      await page.close();
    }
    console.log('Research navigation: named tab/panel relationships, manual keyboard selection, visible mobile overflow and no writes passed in seven locales at1440/320 light/dark. '+artifacts);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
