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

async function assertDesktopGeometry(page, context) {
  const geometry = await page.evaluate(() => {
    const selectors = ['#research-tabs [role=tab]', '#research-tools-entry > button', '.research-claim-toolbar button'];
    const rows = selectors.map(selector => {
      const controls = Array.from(document.querySelectorAll(selector));
      const boxes = controls.map(control => {
        const box = control.getBoundingClientRect(), parent = control.closest('#research-tabs, #research-tools-entry, .research-claim-toolbar').getBoundingClientRect();
        return {left:box.left, right:box.right, top:box.top, bottom:box.bottom,
          fits:control.scrollWidth <= control.clientWidth + 1 && control.scrollHeight <= control.clientHeight + 1,
          contained:box.left >= parent.left - 1 && box.right <= parent.right + 1};
      });
      return {selector, boxes};
    });
    const panel = document.querySelector('.research-tab-pane:not([style*="display: none"]):not([style*="display:none"])');
    return {rows, pageFits:document.documentElement.scrollWidth <= innerWidth,
      panelFits:panel && panel.scrollWidth <= panel.clientWidth + 1};
  });
  assert.ok(geometry.pageFits && geometry.panelFits, `${context}: selected content fits the viewport`);
  for (const {selector, boxes} of geometry.rows) {
    assert.ok(boxes.length >= 2, `${context}: ${selector} contains its real controls`);
    assert.ok(boxes.every(box => box.fits && box.contained), `${context}: ${selector} labels and controls are unclipped`);
    assert.ok(Math.max(...boxes.map(box => box.top)) < Math.min(...boxes.map(box => box.bottom)),
      `${context}: ${selector} stays on one row`);
  }
}

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
      // Static shells allow inline handlers: inertness must come from escaping attributes.
      const injected = await page.evaluate(() => {
        const host = document.createElement('div');
        host.innerHTML = renderSafeMarkdown('> [!NOTE] audit" onpointerenter="window.__auditXss=1\n> Synthetic body.\n\n[[x"/onpointerenter="window.__wikiXss=1]]');
        document.body.append(host);
        host.querySelectorAll('*').forEach(node => node.dispatchEvent(new Event('pointerenter')));
        const result = {alert: Boolean(window.__auditXss), wiki: Boolean(window.__wikiXss),
          handlers: host.querySelectorAll('[onpointerenter]').length};
        host.remove();
        return result;
      });
      assert.deepEqual(injected, {alert:false, wiki:false, handlers:0}, 'Markdown titles and wiki targets remain inert data');

      const dossierReviewAvailability = await page.evaluate(() => {
        const detail = {id:'synthetic-dossier', body:'Synthetic dossier body.', review_needed:true,
          decision_reviews:[{status:'review_needed', title:'Synthetic decision', reason:'Synthetic changed pin.'}]};
        const manager = document.getElementById('research-manager');
        const withManager = researchDossierDetailHtml(detail, true);
        manager.id = 'synthetic-manager-not-available';
        let withoutManager;
        try { withoutManager = researchDossierDetailHtml(detail, true); }
        finally { manager.id = 'research-manager'; }
        return {withAction:withManager.includes('data-research-review-dossier'),
          withoutAction:withoutManager.includes('data-research-review-dossier'),
          retainedWarning:withoutManager.includes('Synthetic changed pin.')};
      });
      assert.deepEqual(dossierReviewAvailability, {withAction:true,withoutAction:false,retainedWarning:true},
        'Dossier warnings retain context while utility actions require a research manager');
      await page.locator('[data-view=research]').click();
      const tabs = page.locator('#research-tabs [role=tab]');
      await expect(tabs).toHaveCount(5);
      for (const key of ['dossiers', 'claims', 'timeline', 'decisions', 'sources']) {
        const tab = page.locator(`[data-rtab=${key}]`), panel = page.locator('#rtab-'+key);
        await expect(tab).toHaveAttribute('id', 'research-tab-'+key);
        await expect(tab).toHaveAttribute('aria-controls', 'rtab-'+key);
        await expect(panel).toHaveAttribute('role', 'tabpanel');
        await expect(panel).toHaveAttribute('aria-labelledby', 'research-tab-'+key);
      }
      for (const key of ['search', 'review']) {
        const trigger = page.locator(`[data-rtab=${key}]`);
        await expect(trigger).toHaveAttribute('aria-controls', 'rtab-'+key);
        assert.equal(await trigger.getAttribute('role'), null, 'Shared utilities are buttons outside the content tablist');
        assert.equal(await page.locator(`#research-tabs [data-rtab=${key}]`).count(), 0);
        await trigger.click();
        await expect(trigger).toHaveAttribute('aria-expanded', 'true');
        await expect(page.locator('#research-tool-host')).toBeVisible();
        await expect(page.locator('#rtab-'+key)).toBeVisible();
        if (key === 'review') {
          await page.evaluate(() => {
            document.getElementById('research-manuscript-review-section').hidden = false;
            document.getElementById('research-manuscript-terms-section').hidden = false;
          });
          await expect(page.locator('#rtab-review > .research-pane-navigation')).toBeVisible();
          await expect(page.locator('#rtab-review > .research-pane-navigation button')).toHaveCount(4);
        }
        await expect(page.locator('#rtab-dossiers')).toBeVisible();
        await expect(page.locator('[data-rtab=dossiers]')).toHaveAttribute('aria-selected', 'true');
        await page.locator('#research-tool-close').click();
        await expect(page.locator('#research-tool-host')).toBeHidden();
        await expect(trigger).toBeFocused();
      }
      assert.equal(await page.locator('[data-rtab=grounding]').count(), 0, 'Comparison is a source action');
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
      await expect(page.locator('[data-rtab=sources]')).toBeFocused();
      const activeBox = await page.locator('[data-rtab=sources]').boundingBox();
      assert.ok(activeBox.x >= 0 && activeBox.x+activeBox.width <= width,
        `${locale}/${width}: the focused destination stays visible`);
      await page.keyboard.press('Enter');
      await expect(page.locator('#rtab-sources')).toBeVisible();
      await expect(page.locator('.research-tab-pane:visible')).toHaveCount(1);
      if (width === 320) {
        const previous = page.locator('#research-navigation-previous');
        const next = page.locator('#research-navigation-next');
        await expect(previous).toBeVisible();
        await expect(next).toBeVisible();
        await expect(previous).toBeEnabled();
        await previous.click();
        await expect(page.locator('[data-rtab=sources]')).toHaveAttribute('aria-selected', 'true');
        await expect(next).toBeEnabled();
        assert.ok(await next.getAttribute('aria-label'), 'Overflow controls are named');
      }
      await page.locator('[data-rtab=dossiers]').click();
      await expect(page.locator('#rtab-dossiers')).toBeVisible();
      await page.evaluate(() => {
        const renderSynthetic = renderResearchDossiersView;
        renderResearchDossiersView = function(data) {
          if (data && Array.isArray(data.dossiers) && data.dossiers.length) renderSynthetic(data);
        };
        renderResearchDossiersView({dossiers: Array.from({length: 13}, function(_, index) {
          return {id: 'synthetic-dossier-' + index, title: 'Synthetic dossier ' + index,
            excerpt: 'Synthetic excerpt ' + index, sections: [], tags: ['synthetic'],
            collections: [], evidence_count: 0, revision: 1, review_needed: false};
        }), collections: [], unassigned_dossier_ids: []});
      });
      await expect(page.locator('#research-dossiers-list .research-card:visible')).toHaveCount(12);
      const showMore = page.locator('#research-dossiers-more [data-research-show-more=dossiers]');
      await expect(showMore).toBeVisible();
      await expect(showMore).not.toHaveText(/research_show_more/);
      await showMore.evaluate(button => button.click());
      await expect(page.locator('#research-dossiers-list .research-card:visible')).toHaveCount(13);
      await expect(page.locator('#research-dossiers-more')).toBeHidden();
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
      if (['en', 'de'].includes(locale) && width === 1440 && colorScheme === 'light') {
        await page.locator('[data-rtab=claims]').click();
        for (const desktopWidth of [1024, 1280, 1920, 2560]) {
          await page.setViewportSize({width:desktopWidth, height:900});
          await assertDesktopGeometry(page, `${locale}/${desktopWidth}`);
          await page.locator('#research-manager').screenshot({path:path.join(artifacts, `${locale}-${desktopWidth}-desktop.png`)});
        }
        assert.deepEqual(writes, [], 'Desktop geometry navigation never saves research');
        assert.deepEqual(errors, []);
      }
      await page.close();
    }
    console.log('Research navigation: named tab/panel relationships, manual keyboard selection, visible mobile overflow and no writes passed in seven locales at1440/320 light/dark; DE/EN desktop navigation, utilities and claim toolbar stay on one row without clipping at1024/1280/1920/2560. '+artifacts);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
