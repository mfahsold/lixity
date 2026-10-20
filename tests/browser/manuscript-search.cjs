// The author can search the manuscript itself, not only the research archive.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const path = require('node:path');
const assert = require('node:assert/strict');

const {pythonFixture} = require('./support/python-fixture.cjs');
const root = path.resolve(__dirname, '../..');
const fixtures = pythonFixture(`
import json
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
from dashboard_fixtures import full_dashboard as render
# A manuscript phrase that looks like markup, and one that only appears in a
# single chapter, so filtering is observable.
render.__globals__['SAMPLE'] = render.__globals__['SAMPLE'].replace('## Kap 2', (
    "Hier steht ein seltenes Suchwort im Manuskript.\\n\\n"
    "Und hier ein Satz mit </script><img src=x onerror=window.searchInjected=true> als Text.\\n\\n## Kap 2"
))
original = render.__globals__['render_dashboard']
fixtures = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    def localized(*args, **kwargs):
        return original(*args, **{**kwargs, 'labels': labels, 'language_key': locale})
    render.__globals__['render_dashboard'] = localized
    fixtures[locale] = {'html': render(), 'values': labels['paragraph_values'], 'skip': labels['skip_main'],
                       'markers': ['+ ' + labels['marker_' + kind] for kind in ('pruefen', 'sachcheck', 'todo', 'achtung')]}
def standalone(*args, **kwargs):
    return original(*args, **{**kwargs, 'controls': False,
        'labels': {**get_language_profile('en').labels, **WORKSPACE_LABELS['en']}, 'language_key': 'en'})
render.__globals__['render_dashboard'] = standalone
fixtures['en']['standalone_html'] = render()
print(json.dumps(fixtures))
`, {root});

(async () => {
  const browser = await launchChromium();
  try {
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}, javaScriptEnabled: false});
      await page.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: fixtures.en.standalone_html}));
      await page.goto('http://lixity.test/');
      const paragraph = page.locator('#chapters .ptext').first();
      assert.ok((await paragraph.locator('p').textContent()).includes('Ich trinke Kaffee.'),
        'The standalone report retains the complete manuscript without JavaScript');
      assert.equal(await paragraph.locator('p').isVisible(), true);
      await paragraph.locator('.paragraph-values > summary').press('Enter');
      assert.equal(await paragraph.locator('.stats').isVisible(), true,
        'Paragraph values remain available without JavaScript');
      await page.close();
    }
    for (const [locale, fixture] of Object.entries(fixtures)) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}, hasTouch: true});
      await page.addInitScript(() => localStorage.setItem('lixity.manuscript.mode', 'inspect'));
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => { if (['error', 'warning'].includes(message.type())) errors.push(message.text()); });
      await page.route('http://lixity.test/**', route => route.fulfill(route.request().url().includes('/api/')
        ? {json: {ok: true, locked: true, records: []}}
        : {contentType: 'text/html', body: fixture.html}));
      await page.goto('http://lixity.test/');
      assert.match(await page.title(), /^Testroman – /);
      assert.ok((await page.locator('body').innerText()).includes('Testroman'));
      const skip = page.locator('.skip-link');
      assert.equal(await skip.textContent(), fixture.skip, 'The skip link uses the selected workspace language');
      await page.keyboard.press('Tab');
      assert.equal(await skip.evaluate(link => link === document.activeElement), true,
        'The first keyboard stop exposes the skip link');
      await skip.press('Enter');
      assert.equal(await page.locator('#chapters').isVisible(), true,
        'Skipping from the initial workspace view reveals the manuscript');
      assert.equal(await page.evaluate(() => document.activeElement.id), 'chapters',
        'The skip link moves keyboard focus to the main content');
      await page.locator('#tab-view-analysis').click();

      const first = page.locator('#chapters .ptext').first();
      const paragraphs = await page.locator('#chapters .ptext').count();
      const originalText = await page.locator('#chapters .ptext .ptext-inner > p').allTextContents();
      assert.equal(originalText.length, paragraphs, 'Continuous prose is mounted exactly once');
      const field = page.locator('#text-search');
      assert.equal(await field.isVisible(), true);
      await page.locator('#workbench-overview-open').click();
      assert.equal(await page.locator('#analysis-review').isVisible(), true);
      const sections = page.locator('#analysis-sections [data-section-link]');
      await sections.first().focus(); await sections.first().press('ArrowRight');
      assert.equal(await sections.nth(1).evaluate(link => link === document.activeElement), true);
      await field.fill('Suchwort'); await field.press('Enter');
      assert.equal(await page.locator('#chapters .ptext:not(.text-miss)').isVisible(), true,
        'Searching from an overview reveals its manuscript result');
      await field.press('Escape');
      await page.locator('#workbench-overview-open').click();
      await page.locator('#workbench-overview-back').click();
      await first.locator('[data-reader-paragraph]').click();
      await page.locator('[data-reader-action=values]').click();
      assert.equal(await page.locator('#reader-inspector .stats').isVisible(), true);
      assert.equal(await page.locator('#reader-inspector summary').textContent(), fixture.values);
      await page.locator('#reader-inspector-close').click();

      await field.fill('Suchwort');
      await page.waitForFunction(() => document.querySelectorAll('#chapters .ptext:not(.text-miss)').length === 1);
      assert.match(await page.locator('#text-search-status').textContent(), /\d+/);
      assert.equal(await page.locator('#chapters .ptext:visible').count(), 1);
      assert.equal(await page.locator('mark.text-hit').count(), 1);
      assert.equal(await page.locator('#chapters .ptext p').count(), paragraphs,
        'Search preserves the manuscript DOM while hiding nonmatches');
      await field.fill('zzzkeintrefferzzz');
      await page.waitForFunction(() => document.querySelectorAll('#chapters .ptext:not(.text-miss)').length === 0);
      assert.ok((await page.locator('#text-search-status').textContent()).trim());
      await field.press('Escape');
      assert.equal(await page.locator('#chapters .ptext.text-miss').count(), 0);
      assert.equal(await page.locator('mark.text-hit').count(), 0);

      if (locale === 'en') {
        await field.evaluate(input => {
          input.value = 'Regen'; input.dispatchEvent(new Event('input', {bubbles: true}));
          input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', shiftKey: true, bubbles: true}));
        });
        assert.ok(await page.locator('#chapters .ptext:not(.text-miss)').last().locator('mark.text-hit').count());
        await field.press('Escape');
        await first.locator('[data-reader-paragraph]').click();
        await page.locator('[data-reader-action=todo]').click();
        await first.locator('.marker-note').fill('Synthetic marker draft');
        await field.fill('Suchwort');
        await page.waitForFunction(() => document.querySelectorAll('#chapters .ptext:not(.text-miss)').length === 1);
        assert.equal(await first.locator('.marker-note').inputValue(), 'Synthetic marker draft');
        await field.press('Escape');
        assert.equal(await first.locator('.marker-note').isVisible(), true);
        await first.locator('[data-marker-cancel]').click();
      }
      await field.fill('<img');
      await page.waitForFunction(() => document.querySelectorAll('#chapters .ptext:not(.text-miss)').length === 1);
      assert.ok((await page.locator('#chapters .ptext:not(.text-miss) p').textContent()).includes('</script><img'));
      assert.equal(await page.evaluate(() => Boolean(window.searchInjected)), false);
      assert.equal(await page.locator('#chapters img, #chapters script').count(), 0);
      await field.press('Escape');
      assert.deepEqual(await page.locator('#chapters .ptext .ptext-inner > p').allTextContents(), originalText);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      assert.deepEqual(errors, []);
      await page.locator('.toolbar').screenshot({path: `/tmp/lixity-manuscript-search-${locale}-${width}.png`});
      await page.close();
    }
    console.log('Manuscript search: present, filters chapters and paragraphs, counts hits, ' +
      'localized actions/inert text in seven locales at 1440/320; full search/marker/tab regressions at both widths passed.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
