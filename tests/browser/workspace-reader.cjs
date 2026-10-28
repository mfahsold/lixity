// The author can read a dossier beside the existing manuscript without editing either.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-workspace-reader-'));
const fixtures = pythonFixture(`
import json
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
from dashboard_fixtures import full_dashboard as render
original = render.__globals__['render_dashboard']
fixtures = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    def localized(*args, **kwargs):
        return original(*args, **{**kwargs, 'labels': labels, 'language_key': locale,
            'enabled_actions': ['analyze', 'manuscript-pdf', 'research-reader'], 'manuscript_pdf_token': 'synthetic-token'})
    render.__globals__['render_dashboard'] = localized
    fixtures[locale] = render()
print(json.dumps(fixtures))
`, {root});
const dossier = {id: 'synthetic-dossier', project_id: 'synthetic-project', title: 'Synthetic dossier', revision: 2,
  body: '## Context\n\nA synthetic dossier with <img src=x onerror=window.readerInjected=true> as text.\n\n' + 'Historical source notes. '.repeat(100),
  editable_sections: ['Context'], citations: [], sections: ['Context'], tags: [], evidence_count: 0};
(async () => {
  const browser = await launchChromium();
  try {
    for (const [locale, html] of Object.entries(fixtures)) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}});
      const errors = [], readerRequests = [], writes = [];
      let conflict = false;
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://lixity.test/**', route => {
        const request = route.request(), url = new URL(request.url());
        if (request.method() === 'POST') writes.push(url.pathname);
        if (url.pathname === '/api/research/dossiers' && url.searchParams.has('project_token')) {
          readerRequests.push(url);
          assert.equal(url.searchParams.get('project_token'), 'synthetic-token');
          if (conflict) return route.fulfill({status: 409, json: {ok: false, message: '<img onerror=window.readerInjected=true> Reload the selected project'}});
          return route.fulfill({json: url.searchParams.has('id') ? {ok: true, ...dossier} : {ok: true, dossiers: [dossier]}});
        }
        if (url.pathname === '/api/research/status') return route.fulfill({json: {ok: true, initialized: true,
          project_id: 'synthetic-project', project_root: '/tmp/synthetic-project', dossiers: [dossier], sources: [], claims: [], decisions: []}});
        if (url.pathname === '/api/research/dossiers') return route.fulfill({json: {ok: true, dossiers: [dossier]}});
        if (url.pathname.startsWith('/api/')) return route.fulfill({json: {ok: true, records: [], sources: [], claims: [], decisions: []}});
        return route.fulfill({contentType: 'text/html', body: html});
      });
      await page.goto('http://lixity.test/');
      await page.locator('#tab-view-analysis').click();
      const toggle = page.locator('#workspace-reader-toggle');
      const panel = page.locator('#workspace-reader-panel');
      const select = page.locator('#workspace-reader-dossier');
      const body = page.locator('#workspace-reader-body');
      assert.equal(await toggle.isVisible(), true);
      assert.equal(await panel.isVisible(), false);
      assert.equal(readerRequests.length, 0, 'The optional reader makes no requests before opening');
      const paragraph = page.locator('#chapters .ptext').first();
      const originalText = await paragraph.locator('p').textContent();
      const navigationToggle = page.locator('#workspace-navigation-toggle');
      const navigation = page.locator('#workspace-navigation-content');
      const originalWidth = await page.locator('.workspace-shell').evaluate(node => node.getBoundingClientRect().width);
      await page.locator('#chapters .ptext').last().scrollIntoViewIfNeeded();
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const departure = await page.evaluate(() => {
        const anchor = LixityReader.capture();
        window.__testCompanionAnchor = anchor.panel;
        return {top:anchor.top, proseOffset:anchor.proseOffset, scrollY, maxScroll:document.documentElement.scrollHeight - innerHeight,
          height:document.documentElement.scrollHeight, tag:anchor.panel.tagName, id:anchor.panel.id};
      });
      assert.equal(await toggle.evaluate(node => {
        const bounds = node.getBoundingClientRect();
        return bounds.top >= 0 && bounds.bottom <= innerHeight &&
          document.elementFromPoint(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2)?.closest('#workspace-reader-toggle') === node;
      }), true, 'companion navigation remains reachable at the current deep reading position');
      await toggle.click();
      await page.waitForFunction(() => !document.querySelector('#workspace-reader-dossier').disabled);
      const opened = await page.evaluate(() => {
        const current = LixityReader.capture();
        return {top:window.__testCompanionAnchor.getBoundingClientRect().top, scrollY,
          anchorId:current && current.panel.id, anchorTop:current && current.top, proseOffset:current && current.proseOffset};
      });
      await toggle.click();
      try {
        await page.waitForFunction(top => window.__testCompanionAnchor.isConnected &&
          Math.abs(window.__testCompanionAnchor.getBoundingClientRect().top - top) <= 2, departure.top,
          {timeout: 5000});
      } catch (error) {
        const actual = await page.evaluate(() => ({top:window.__testCompanionAnchor.getBoundingClientRect().top,
          connected:window.__testCompanionAnchor.isConnected, scrollY, innerHeight,
          maxScroll:document.documentElement.scrollHeight - innerHeight, height:document.documentElement.scrollHeight,
          focus:document.activeElement?.id, state:LixityWorkbench.state()}));
        throw new Error(`Companion position ${locale}/${width}: departure=${JSON.stringify(departure)} opened=${JSON.stringify(opened)} actual=${JSON.stringify(actual)}`, {cause:error});
      }
      await toggle.click();
      if (width >= 1100) {
        assert.equal(await navigation.isVisible(), false, 'Companion automatically frees desktop navigation space');
        assert.equal(await navigationToggle.getAttribute('aria-expanded'), 'false');
        assert.ok(await page.locator('.workspace-shell').evaluate(node => node.getBoundingClientRect().width) < originalWidth / 2);
        await navigationToggle.click();
        assert.equal(await navigation.isVisible(), true, 'Navigation remains manually accessible beside the dossier');
        await navigationToggle.click();
      } else {
        assert.equal(await navigation.isVisible(), true, 'Mobile navigation stays available');
        assert.equal(await navigationToggle.isVisible(), false);
      }
      await page.waitForFunction(() => !document.querySelector('#workspace-reader-dossier').disabled);
      assert.equal(await panel.isVisible(), true);
      assert.equal(await toggle.getAttribute('aria-expanded'), 'true');
      const controlTops = await page.evaluate(() => ['workspace-reader-dossier', 'workspace-reader-refresh']
        .map(id => Math.round(document.getElementById(id).getBoundingClientRect().top)));
      assert.ok(Math.abs(controlTops[0] - controlTops[1]) <= 1,
        `The dossier select and refresh button line up: ${JSON.stringify(controlTops)}`);
      assert.equal(await select.inputValue(), '', 'Opening does not silently pick a dossier');
      await select.selectOption(dossier.id);
      await body.locator('.research-dossier-body-rendered p').filter({hasText: 'Historical source notes.'}).waitFor();
      assert.equal(await paragraph.locator('p').textContent(), originalText, 'Manuscript state stays intact');
      assert.equal(await page.locator('#analysis-review').isVisible(), false, 'The companion view focuses on manuscript reading');
      assert.equal(await page.locator('#text-search').isVisible(), true, 'Manuscript search remains usable while reading');
      assert.equal(await body.locator('[data-research-revise], [data-dossier-add-image], [data-use-passage]').count(), 0,
        'The companion view is read-only');
      assert.equal(await page.evaluate(() => Boolean(window.readerInjected)), false);
      assert.equal(await body.locator('img').count(), 0, 'Source-like markup remains data');
      const boxes = await page.evaluate(() => {
        const a = document.querySelector('#workspace-analysis-body').getBoundingClientRect();
        const b = document.querySelector('#workspace-reader-panel').getBoundingClientRect();
        return {analysis: {x: a.x, width: a.width, y: a.y}, reader: {x: b.x, width: b.width, y: b.y},
          width: innerWidth, document: document.documentElement.scrollWidth};
      });
      assert.ok(boxes.document <= width + 1, 'No horizontal overflow');
      if (width > 900) assert.ok(boxes.reader.x > boxes.analysis.x && boxes.analysis.width >= 400, 'Desktop shows adjacent reading panes');
      else assert.ok(boxes.reader.y <= boxes.analysis.y, 'Narrow screens stack the dossier before manuscript');
      if (locale === 'de') {
        await page.locator('#workspace-reader').scrollIntoViewIfNeeded();
        await page.screenshot({path: path.join(artifacts, `reader-${width}.png`)});
      }
      if (['de', 'pt'].includes(locale) && width === 320) {
        await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
        for (const enlargedWidth of [390, 320]) {
          await page.setViewportSize({width:enlargedWidth, height:900});
          const readable = await select.evaluate(element => {
            const control = element.getBoundingClientRect();
            const row = element.closest('.workspace-reader-controls').getBoundingClientRect();
            return control.width >= Math.min(8 * parseFloat(getComputedStyle(element).fontSize), row.width) - 1;
          });
          assert.ok(readable, `${locale}/${enlargedWidth}: enlarged dossier selection retains a readable width`);
          await select.scrollIntoViewIfNeeded();
          await page.screenshot({path:path.join(artifacts, `reader-${locale}-${enlargedWidth}-enlarged.png`)});
        }
        await page.evaluate(() => { document.documentElement.style.fontSize = ''; });
        await page.setViewportSize({width, height:900});
      }
      await toggle.click();
      assert.equal(await panel.isVisible(), false);
      assert.equal(await navigation.isVisible(), true, 'Closing restores the previous navigation state');
      assert.equal(await page.locator('#analysis-review').isVisible(), false, 'Closing a dossier retains the document reading surface');
      await page.locator('#workbench-overview-open').click();
      assert.equal(await page.locator('#analysis-review').isVisible(), true, 'The explicit overview reveals broad analysis');
      await page.locator('#workbench-overview-back').click();
      assert.equal(await paragraph.locator('p').textContent(), originalText);
      await page.locator('#tab-view-research').click();
      await page.locator('[data-rtab=dossiers]').click();
      const catalogueDeparture = readerRequests.length;
      await page.locator('[data-workspace-dossier="synthetic-dossier"]').click();
      await body.locator('.research-dossier-body-rendered p').filter({hasText: 'Historical source notes.'}).waitFor();
      const openedRequests = readerRequests.slice(catalogueDeparture);
      assert.equal(openedRequests.filter(url => !url.searchParams.has('id')).length, 1,
        'Opening a catalogue dossier starts one catalogue read, including when the companion was closed');
      assert.equal(openedRequests.filter(url => url.searchParams.get('id') === dossier.id).length, 1,
        'The requested dossier is loaded once after its catalogue is accepted');
      assert.equal(await page.locator('#tab-view-analysis').getAttribute('aria-selected'), 'true');
      assert.equal(await select.inputValue(), dossier.id);
      assert.equal(await paragraph.locator('p').textContent(), originalText);
      if (locale === 'en') {
        // Retarget an existing companion through the same catalogue action.
        await page.locator('#tab-view-research').click();
        await page.locator('[data-rtab=dossiers]').click();
        const retargetDeparture = readerRequests.length;
        await page.locator('[data-workspace-dossier="synthetic-dossier"]').click();
        await body.locator('.research-dossier-body-rendered p').filter({hasText: 'Historical source notes.'}).waitFor();
        assert.equal(readerRequests.slice(retargetDeparture).filter(url => !url.searchParams.has('id')).length, 1,
          'An already-open companion accepts one explicit catalogue retarget request');
        assert.equal(await select.inputValue(), dossier.id);
      }
      conflict = true;
      await page.locator('#workspace-reader-refresh').click();
      await page.waitForFunction(() => document.querySelector('#workspace-reader-status').classList.contains('err'));
      assert.match(await page.locator('#workspace-reader-status').textContent(), /Reload the selected project/);
      assert.equal(await body.textContent(), '', 'A failed refresh removes potentially stale research content');
      assert.equal(await page.locator('#workspace-reader-status img').count(), 0);
      conflict = false;
      await page.locator('#workspace-reader-refresh').click();
      await body.locator('.research-dossier-body-rendered p').filter({hasText: 'Historical source notes.'}).waitFor();
      await select.press('Escape');
      assert.equal(await panel.isVisible(), false);
      assert.equal(await page.evaluate(() => document.activeElement.id), 'workspace-reader-toggle');
      if (width >= 1100) {
        await navigationToggle.click();
        assert.equal(await navigation.isVisible(), false);
        await toggle.click(); await page.locator('#workspace-reader-close').click();
        assert.equal(await navigation.isVisible(), false, 'A prior manual collapse survives companion use');
        await navigationToggle.click();
        await toggle.click();
        await page.setViewportSize({width:320,height:900});
        await page.waitForFunction(() => !document.getElementById('workspace-navigation-content').hidden);
        assert.equal(await navigation.isVisible(), true, 'Resizing restores the mobile switcher');
        await page.setViewportSize({width,height:900});
        await page.locator('#workspace-reader-close').click();
        assert.equal(await navigation.isVisible(), true);
      }
      if (locale === 'en') {
        await page.reload();
        await page.locator('#tab-view-research').click();
        await page.locator('[data-rtab=dossiers]').click();
        assert.equal(await select.locator('option[value="synthetic-dossier"]').count(), 0,
          'The first catalogue opening starts without a preloaded companion option');
        const firstDeparture = readerRequests.length;
        await page.locator('[data-workspace-dossier="synthetic-dossier"]').click();
        await body.locator('.research-dossier-body-rendered p').filter({hasText: 'Historical source notes.'}).waitFor();
        assert.equal(readerRequests.slice(firstDeparture).filter(url => !url.searchParams.has('id')).length, 1,
          'The first catalogue opening also needs only one catalogue read');
        assert.equal(await select.inputValue(), dossier.id, 'The explicit first dossier survives population of its options');
      }
      assert.deepEqual(writes, [], 'Reading beside the manuscript never writes or edits anything');
      assert.deepEqual(errors, []);
      await page.close();
    }
    const gated = await browser.newPage();
    let guardedReads = 0;
    await gated.route('http://lixity.test/**', route => {
      if (route.request().url().includes('project_token')) guardedReads++;
      return route.fulfill(route.request().url().includes('/api/') ? {json: {ok: true, locked: true, records: []}} :
        {contentType: 'text/html', body: fixtures.en.replace('id="workspace-reader" data-project-token="synthetic-token"',
          'id="workspace-reader" data-project-token=""')});
    });
    await gated.goto('http://lixity.test/');
    await gated.locator('#tab-view-analysis').click();
    assert.equal(await gated.locator('#workspace-reader-toggle').isDisabled(), true, 'A capability alone cannot bypass context binding');
    assert.equal(guardedReads, 0);
    await gated.close();

    const delayed = await browser.newPage();
    let reads = 0;
    await delayed.route('http://lixity.test/**', route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/api/research/dossiers' && url.searchParams.has('id')) {
        reads++;
        return route.fulfill({json: {ok: true, ...dossier,
          body: reads === 1 ? 'Older delayed dossier text.' : 'Latest saved dossier text.'}});
      }
      if (url.pathname === '/api/research/dossiers') return route.fulfill({json: {ok: true, dossiers: [dossier]}});
      if (url.pathname.startsWith('/api/')) return route.fulfill({json: {ok: true, locked: true, records: []}});
      return route.fulfill({contentType: 'text/html', body: fixtures.en});
    });
    await delayed.goto('http://lixity.test/');
    await delayed.locator('#tab-view-analysis').click();
    await delayed.evaluate(() => {
      const read = window.LixityWorkspaceReader.read;
      let held = false;
      window.LixityWorkspaceReader.read = async query => {
        const response = await read(query);
        if (held || !query.includes('id=')) return response;
        held = true;
        return new Promise(resolve => {window.releaseReaderResponse = () => {
          resolve(response);
          setTimeout(() => {window.readerResponseProcessed = true;}, 0);
        };});
      };
    });
    await delayed.locator('#workspace-reader-toggle').click();
    await delayed.waitForFunction(() => !document.querySelector('#workspace-reader-dossier').disabled);
    await delayed.locator('#workspace-reader-dossier').selectOption(dossier.id);
    await delayed.waitForFunction(() => Boolean(window.releaseReaderResponse));
    await delayed.locator('#workspace-reader-toggle').click();
    await delayed.locator('#workspace-reader-toggle').click();
    await delayed.locator('#workspace-reader-body .research-dossier-body-rendered').getByText('Latest saved dossier text.', {exact: true}).waitFor();
    await delayed.evaluate(() => window.releaseReaderResponse());
    await delayed.waitForFunction(() => window.readerResponseProcessed);
    assert.match(await delayed.locator('#workspace-reader-body').textContent(), /Latest saved dossier text/);
    assert.doesNotMatch(await delayed.locator('#workspace-reader-body').textContent(), /Older delayed dossier text/,
      'A closed reader request cannot overwrite the reopened view');
    assert.equal(await delayed.locator('#workspace-reader-dossier').isDisabled(), false);
    await delayed.close();
    console.log('Workspace reader: seven desktop/mobile locales, optional context-bound dossier reads, retained manuscript state, safe errors, retry and read-only controls passed. Screenshots: ' + artifacts);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
