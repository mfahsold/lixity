// The author can search the manuscript itself, not only the research archive.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '../..');
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
import json, runpy
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
render = runpy.run_path('tests/test_ui_contract.py')['_full_dashboard']
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
    fixtures[locale] = {'html': render(), 'values': labels['paragraph_values'],
                       'markers': ['+ ' + labels['marker_' + kind] for kind in ('pruefen', 'sachcheck', 'todo', 'achtung')]}
print(json.dumps(fixtures))
`],
  {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8', maxBuffer: 8 * 1024 * 1024});
assert.equal(fixture.status, 0, fixture.error ? fixture.error.message : fixture.stderr);
const fixtures = JSON.parse(fixture.stdout);

(async () => {
  const browser = await launchChromium();
  try {
    for (const [locale, fixture] of Object.entries(fixtures)) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}, hasTouch: true});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => { if (['error', 'warning'].includes(message.type())) errors.push(message.text()); });
      await page.route('http://lixity.test/**', route => route.fulfill(route.request().url().includes('/api/')
        ? {json: {ok: true, locked: true, records: []}}
        : {contentType: 'text/html', body: fixture.html}));
      await page.goto('http://lixity.test/');
      assert.match(await page.title(), /^Testroman – /);
      assert.ok((await page.locator('body').innerText()).includes('Testroman'));
      await page.locator('#tab-view-analysis').click();

      const review = page.locator('#analysis-review');
      assert.equal(await review.count(), 1, 'Loaded analysis offers a compact starting point');
      const reviewTargets = await review.locator('a.ctl').evaluateAll(elements => elements.map(element => {
        const box = element.getBoundingClientRect();
        return {width: box.width, height: box.height, coarse: matchMedia('(pointer: coarse)').matches};
      }));
      assert.ok(reviewTargets.every(box => box.width >= 44 && box.height >= (box.coarse ? 44 : 40)),
        'Review routes provide appropriately sized controls: ' + JSON.stringify(reviewTargets));
      if (locale === 'de') await review.screenshot({path: `/tmp/lixity-review-entry-${width}.png`});
      const passageLink = review.locator('[data-review-passage]');
      const reviewTarget = await passageLink.getAttribute('data-target');
      await passageLink.click();
      assert.equal(await page.locator('#' + reviewTarget + ' p').isVisible(), true,
        'The first review action opens its actual source passage');
      assert.equal(await page.evaluate(() => document.activeElement.id), reviewTarget,
        'Keyboard focus follows the review action to the source passage');
      await page.locator('.chip[data-target="' + reviewTarget + '"]').click();
      await review.locator('[href="#heatmap"]').click();
      assert.equal(await page.locator('#heatmap').isVisible(), true);
      await review.locator('[href="#dist"]').click();
      assert.equal(await page.locator('#dist').evaluate(element => element.classList.contains('flash')), true);

      const field = page.locator('#text-search');
      assert.equal(await field.count(), 1, 'manuscript search field exists');
      assert.ok(await field.isVisible(), `search field visible at ${width}`);

      const paragraphs = await page.locator('#chapters .ptext').count();
      assert.ok(paragraphs > 3, 'fixture has paragraphs to filter');
      assert.equal(await page.locator('#chapters .ptext p').count(), 0,
        'Closed paragraphs do not populate the live document with manuscript text');
      const chip = page.locator('#chapters .chip').first();
      await chip.click();
      const first = page.locator('#' + await chip.getAttribute('data-target'));
      assert.equal(await first.locator('.ptext-inner > :first-child').evaluate(el => el.tagName), 'P',
        'The opened paragraph starts with manuscript text');
      assert.equal(await first.locator('.stats').isVisible(), false, 'Values start collapsed');
      assert.equal(await first.locator('.paragraph-values > summary').textContent(), fixture.values);
      assert.deepEqual(await first.locator('[data-marker-kind]').allTextContents(), fixture.markers,
        'Lazily created marker controls use the existing translated labels');
      if (locale === 'de') await first.screenshot({path: `/tmp/lixity-paragraph-first-${width}.png`});
      await first.locator('.paragraph-values > summary').click();
      assert.equal(await first.locator('.stats').isVisible(), true, 'Values are available on request');
      await chip.click();
      assert.equal(await first.locator('p').count(), 0, 'Closing releases rendered text');

      assert.equal(await page.locator('#style-tabs [role=tab]').count(), 4);
      assert.equal(await page.locator('#style-panels > .panel:visible').count(), 1);
      await page.locator('#style-tab-dimensions').click();
      assert.equal(await page.locator('#dimensions').isVisible(), true);
      await page.locator('#style-tab-dimensions').press('ArrowRight');
      assert.equal(await page.locator('#structural').isVisible(), true);
      await page.locator('#style-tab-structural').press('Home');
      assert.equal(await page.locator('#heatmap').isVisible(), true);
      await page.locator('[data-jump="#bands"]').first().click();
      assert.equal(await page.locator('#bands').isVisible(), true, 'Existing metric links select the target tab');
      if (locale === 'de') await page.locator('#style').screenshot({path: `/tmp/lixity-style-tabs-${width}.png`});

      // An empty query must leave the manuscript untouched.
      assert.equal(await page.locator('#chapters .ptext.text-miss').count(), 0);
      assert.equal(await page.locator('#text-search-next').isVisible(), false);

      await field.fill('Suchwort');
      await page.waitForFunction(() => document.querySelectorAll('#chapters .ptext:not(.text-miss)').length === 1);
      const status = await page.locator('#text-search-status').textContent();
      assert.match(status, /\d+/, `status reports a count at ${width}`);

      // Everything that does not match leaves the page; the match stays.
      const misses = await page.locator('#chapters .ptext.text-miss').count();
      const visible = await page.locator('#chapters .ptext:not(.text-miss)').count();
      assert.equal(misses + visible, paragraphs);
      assert.equal(visible, 1, 'exactly one paragraph holds the rare word');
      assert.equal(await page.locator('mark.text-hit').count(), 1);
      assert.equal(await page.locator('#chapters .ptext p').count(), 1,
        'Search opens only its current result');
      assert.equal(
        await page.locator('.chapter:not(.text-miss)').count(), 1,
        'only the chapter holding the match remains'
      );
      assert.equal(await page.locator('#text-search-next').isVisible(), true);

      // The interface must never parse manuscript text as markup.
      assert.equal(await page.evaluate(() => Boolean(window.searchInjected)), false);
      assert.equal(await page.locator('#chapters img, #chapters script').count(), 0);

      // A query without hits reports it instead of an empty page.
      await field.fill('zzzkeintrefferzzz');
      // The field debounces, so wait for the outcome rather than for any text:
      // the previous query's count is still on screen for a moment.
      await page.waitForFunction(() => document.querySelectorAll('#chapters .ptext:not(.text-miss)').length === 0);
      assert.match(await page.locator('#text-search-status').textContent(), /\D/);

      // Escape clears the search and restores the whole manuscript.
      await field.press('Escape');
      await page.waitForFunction(() => document.querySelectorAll('#chapters .ptext.text-miss').length === 0);
      assert.equal(await page.locator('#chapters .ptext:not(.text-miss)').count(), paragraphs);
      assert.equal(await page.locator('mark.text-hit').count(), 0);

      // The clear button and the arrow keys work as well.
      await field.fill('Regen');
      await page.waitForFunction(() => document.querySelectorAll('#chapters mark.text-hit').length > 0);
      const opened = await page.locator('#chapters .ptext.open').count();
      assert.ok(opened >= 1, 'the first match is opened');
      await page.locator('#text-search-clear').click();
      await page.waitForFunction(() => document.querySelectorAll('#chapters .ptext.text-miss').length === 0);
      assert.equal(await field.inputValue(), '');

      // Backward navigation also works before the input debounce has fired.
      await field.evaluate(input => {
        input.value = 'Regen';
        input.dispatchEvent(new Event('input', {bubbles: true}));
        input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', shiftKey: true, bubbles: true}));
      });
      const lastMatch = page.locator('#chapters .ptext:not(.text-miss)').last();
      assert.equal(await lastMatch.locator('mark.text-hit').count() > 0, true,
        'Immediate Shift+Enter selects the final match');
      await field.press('Escape');

      const valuesLabel = await first.locator('.paragraph-values > summary').count();
      assert.equal(valuesLabel, 0, 'Clearing search releases paragraphs opened only for results');

      await page.locator('#filter-flags').check();
      await field.fill('Morgen');
      await page.waitForFunction(() => document.querySelectorAll('#chapters .ptext:not(.text-miss)').length === 1);
      assert.equal(await page.locator('#chapters .ptext:not(.text-miss)').isVisible(), true,
        'Full manuscript search reveals matches in an unflagged chapter');
      assert.equal(await page.locator('#chapters .chapter:visible').count(), 1);
      await field.press('Escape');
      assert.equal(await page.locator('#filter-flags').isChecked(), true,
        'Clearing search preserves the existing paragraph filter');
      await page.locator('#filter-flags').uncheck();

      await chip.click();
      await first.locator('[data-marker-kind=todo]').click();
      await first.locator('.marker-note').fill('Synthetic marker draft');
      await field.fill('Suchwort');
      await page.waitForFunction(() => document.querySelectorAll('#chapters .ptext:not(.text-miss)').length === 1);
      assert.equal(await first.locator('.marker-note').inputValue(), 'Synthetic marker draft');
      await field.press('Escape');
      assert.equal(await first.locator('.marker-note').isVisible(), true,
        'Clearing search restores the original open paragraph and marker draft');
      await first.locator('[data-marker-cancel]').click();
      await chip.click();

      await field.fill('<img');
      await page.waitForFunction(() => document.querySelectorAll('#chapters .ptext:not(.text-miss)').length === 1);
      assert.ok((await page.locator('#chapters .ptext:not(.text-miss) p').textContent())
        .includes('</script><img src=x onerror=window.searchInjected=true>'));
      assert.equal(await page.evaluate(() => Boolean(window.searchInjected)), false);
      assert.equal(await page.locator('#chapters img, #chapters script').count(), 0);
      await field.press('Escape');

      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true,
        `no overflow with the search bar at ${width}`);
      assert.deepEqual(errors, []);
      await page.locator('.toolbar').screenshot({path: `/tmp/lixity-manuscript-search-${locale}-${width}.png`});
      await page.close();
    }
    console.log('Manuscript search: present, filters chapters and paragraphs, counts hits, ' +
      'steps through them, clears on Escape and keeps manuscript markup inert in seven locales at 1440/320 passed.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
