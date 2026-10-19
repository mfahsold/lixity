// Synthetic manuscript selections are explicit local claim associations.
const assert = require('node:assert/strict');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const root = path.resolve(__dirname, '../..');
const fixtures = pythonFixture(`
import json
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
from dashboard_fixtures import full_dashboard as render
render.__globals__['SAMPLE'] = render.__globals__['SAMPLE'].replace('Ich trinke Kaffee.', 'İA😀 safe selected sentence [literal.*+?] <img src=x onerror=window.linkInjected=true>.', 1)
original = render.__globals__['render_dashboard']
fixtures = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    def localized(*args, **kwargs):
        return original(*args, **{**kwargs, 'labels': labels, 'language_key': locale,
            'enabled_actions': ['analyze', 'manuscript-pdf', 'research-reader', 'research-manuscript-link'],
            'manuscript_pdf_token': 'synthetic-project-token', 'research_context_token': 'synthetic-research-token',
            'manuscript_source_sha256': 'a' * 64})
    render.__globals__['render_dashboard'] = localized
    fixtures[locale] = render()
print(json.dumps(fixtures))
`, {root});
async function waitUntil(predicate) {
  const deadline = Date.now() + 10000;
  while (!predicate()) {
    assert.ok(Date.now() < deadline, 'Expected held request reached the native action');
    await new Promise(resolve => setTimeout(resolve, 10));
  }
}
async function selectText(page, text) {
  await page.locator('#chapters .ptext.open .ptext-inner > p').first().evaluate((p, quote) => {
    const walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT), nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    const at = p.textContent.indexOf(quote); let offset = 0, start, end;
    for (const node of nodes) {
      if (!start && at >= offset && at < offset + node.length) start = [node, at - offset];
      if (at + quote.length > offset && at + quote.length <= offset + node.length) end = [node, at + quote.length - offset];
      offset += node.length;
    }
    const range = document.createRange(); range.setStart(...start); range.setEnd(...end);
    const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
    document.dispatchEvent(new Event('selectionchange'));
  }, text);
}
(async () => {
  const browser = await launchChromium();
  try {
    for (const [locale, html] of Object.entries(fixtures)) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}, hasTouch: true});
      const errors = [], writes = []; let links = [], anchor, mode = "normal", heldSave, releaseSave, heldClaims, releaseClaims;
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://lixity.test/**', async route => {
        const request = route.request(), url = new URL(request.url());
        if (url.pathname === '/api/research/manuscript-review') {
          assert.equal(url.searchParams.get('project_token'), 'synthetic-project-token');
          assert.equal(url.searchParams.get('research_token'), 'synthetic-research-token');
          if (mode === 'readfail') return route.fulfill({status: 409, json: {ok: false, message: '<img src=x> read failed'}});
          return route.fulfill({json: {ok: true,
          schema_version: 'research-manuscript-review-local/1', project_id: 'project', snapshot: 'snapshot',
          current_source_sha256: (mode === 'source' ? 'b' : 'a').repeat(64), source_state: mode === 'unavailable' ? 'unreadable' : 'available', links: mode === 'malformed-review' ? {} : mode === 'malformed-row' ? [null] : links}}); }
        if (url.pathname === '/api/research/status') {
          return route.fulfill({json: {ok: true, initialized: true, project_id: 'project',
            project_root: '/tmp/synthetic-research', sources_count: 0, dossiers_count: 0,
            claims_count: 1, decisions_count: 0}});
        }
        if (url.pathname === '/api/research/review') {
          return route.fulfill({json: {ok: true, schema_version: 'research-editorial-review-local/1',
            project_id: 'project', snapshot: 'snapshot', decision_count: 0, candidate_count: 0, candidates: []}});
        }
        if (url.pathname === '/api/research/claims') {
          if (mode === 'heldclaims') { heldClaims = true; await new Promise(resolve => { releaseClaims = resolve; }); }
          return route.fulfill({json: {ok: true,
          schema_version: 'research-claims-local/2', project_id: mode === 'copiedroot' ? 'other-project' : 'project', snapshot: mode === 'claims' ? 'new-snapshot' : 'snapshot',
          claims: mode === 'manyclaims' ? Array.from({length: 9}, (_, index) => ({id: 'claim-' + index, revision: 1, title: 'Synthetic claim ' + index, statement: 'Statement ' + index})) : mode === 'emptyclaims' ? [] : mode === 'malformed-claims' ? [null] : [{id: 'claim', revision: 2, title: '<img src=x onerror=window.linkInjected=true> synthetic claim', statement: 'Current statement'}]}}); }
        if (url.pathname === '/api/research-manuscript-link') {
          const data = request.postDataJSON(); writes.push(data);
          if (mode === 'heldsave') { heldSave = true; await new Promise(resolve => { releaseSave = resolve; }); }
          if (mode === 'malformed-save') return route.fulfill({json: {ok: true, project_id: 'project'}});
          if (mode === 'archivedrift') return route.fulfill({status: 409, json: {ok: false, code: 'stale-archive', message: 'Synthetic drift'}});
          if (mode === 'savefail') return route.fulfill({status: 409, json: {ok: false, message: 'Claim changed'}});
          anchor = data.selection;
          links = [{link_id: 'link', revision: 1, state: 'active', claim_id: 'claim', claim_revision: 2,
            claim_title: 'Synthetic claim', anchor, anchor_state: 'resolved', flags: [],
            resolved_start_line: anchor.start_line, resolved_end_line: anchor.end_line}];
          return route.fulfill({json: {ok: true, schema_version: 'research-manuscript-link-local/1', project_id: 'project', snapshot: 'accepted-snapshot', link_id: 'link', claim_id: data.claim_id, claim_revision: data.claim_revision, record: {id: 'link', kind: 'manuscript_claim_link', claim_ref: {id: data.claim_id, revision: data.claim_revision}, anchor: data.selection}}});
        }
        if (url.pathname === '/api/research-manuscript-reanchor') {
          const data = request.postDataJSON(); writes.push(data);
          return route.fulfill({json: {ok: true, schema_version: 'research-manuscript-link-local/1', project_id: 'project', snapshot: 'reanchor-snapshot', link_id: data.link_id, claim_id: 'claim', claim_revision: 2, record: {id: data.link_id, kind: 'manuscript_claim_link', claim_ref: {id: 'claim', revision: 2}}}});
        }
        if (url.pathname.startsWith('/api/')) return route.fulfill({json: {ok: true, locked: true, records: [], sources: [], claims: [], decisions: []}});
        return route.fulfill({contentType: 'text/html', body: html});
      });
      await page.goto('http://lixity.test/');
      await page.locator('#tab-view-analysis').click();
      const chip = page.locator('#chapters .chip').first();
      const id = await chip.getAttribute('data-target'); await chip.click();
      const button = page.locator('#' + id + ' [data-manuscript-link-selection]');
      assert.equal(await button.count(), 1, 'Native compatible paragraph offers manual association');
      await selectText(page, 'safe selected');
      if (locale === 'en' && width === 320) await page.keyboard.press('Alt+l'); else await button.click();
      const dialog = page.locator('#manuscript-link-dialog'); await dialog.waitFor({state: 'visible'});
      await page.locator('#manuscript-link-claim').selectOption('claim');
      assert.equal(await page.locator('#manuscript-link-save').isEnabled(), false, 'Retention must be explicit');
      assert.equal(writes.length, 0, 'Selection and picker perform no write');
      if (locale === 'en') await dialog.screenshot({path: `/tmp/lixity-manuscript-links-picker-${width}.png`});
      await page.locator('#manuscript-link-retain').check(); await page.locator('#manuscript-link-save').click();
      await page.waitForFunction(() => document.querySelectorAll('mark.manuscript-claim-hit').length > 0);
      assert.equal(writes.length, 1); assert.equal(writes[0].selection.start, 4, 'Astral emoji counts as one codepoint');
      assert.equal(writes[0].selection.quote, 'safe selected'); assert.equal(writes[0].claim_revision, 2);
      assert.equal(writes[0].allow_retention, true); assert.equal(writes[0].project_token, 'synthetic-project-token');
      await page.locator('#text-search').fill('selected sentence');
      await page.waitForFunction(() => document.querySelectorAll('mark.text-hit').length > 0);
      assert.equal((await page.locator('mark.text-hit').allTextContents()).join(''), 'selected sentence',
        'Case folding the preceding İ must not shift original-text search intervals');
      assert.equal(await page.locator('mark.manuscript-claim-hit.text-hit').count() > 0, true, 'Overlapping highlights compose');
      await page.locator('#text-search').fill('[literal.*+?]');
      await page.waitForFunction(() => Array.from(document.querySelectorAll('mark.text-hit')).map(n => n.textContent).join('') === '[literal.*+?]');
      assert.equal(await page.locator('mark.manuscript-claim-hit').count() > 0, true, 'Literal regexp characters preserve saved link highlights');
      await page.locator('#text-search').press('Escape');
      await chip.click(); await chip.click();
      assert.equal(await page.locator('#' + id + ' mark.manuscript-claim-hit').count() > 0, true, 'Links survive lazy reopening');
      assert.equal(await page.evaluate(() => Boolean(window.linkInjected)), false);
      assert.equal(await page.locator('#chapters img').count(), 0);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      if (locale === 'en') await page.locator('#' + id).screenshot({path: `/tmp/lixity-manuscript-links-${width}.png`});
      if (locale === 'en' && width === 1440) {
        // The Review tab lists persisted associations with state, flags and quote.
        await page.locator('#tab-view-research').click();
        await page.locator('[data-rtab="review"]').click();
        const reviewRows = page.locator('#research-manuscript-review .manuscript-link-review-item');
        await reviewRows.first().waitFor();
        assert.equal(await page.locator('#research-manuscript-review-section').isVisible(), true, 'A bound manuscript reveals the review section');
        assert.equal(await reviewRows.count(), 1);
        const reviewText = await page.locator('#research-manuscript-review').textContent();
        assert.match(reviewText, /1 saved associations/, 'The review count names the saved associations');
        assert.match(reviewText, /Exact passage/, 'Resolved anchors report their state');
        assert.match(reviewText, /Synthetic claim/, 'The pinned claim title stays visible');
        assert.equal(await page.locator('#research-manuscript-review blockquote').textContent(), 'safe selected');
        assert.equal(await page.locator('#research-manuscript-review [data-research-history="claim"]').count(), 1);
        await page.locator('#tab-view-analysis').click();
        // A selection must stay inside manuscript text, never metrics/headings.
        await page.locator('#' + id + ' .paragraph-values > summary').click();
        await page.locator('#' + id + ' .stats').evaluate(el => {
          const range = document.createRange(); range.selectNodeContents(el);
          getSelection().removeAllRanges(); getSelection().addRange(range);
          document.dispatchEvent(new Event('selectionchange'));
        });
        await button.click(); assert.equal(await dialog.isVisible(), false);
        const second = page.locator('#chapters .chip').nth(1); await second.click();
        await page.evaluate(() => {
          const paragraphs = document.querySelectorAll('#chapters .ptext.open .ptext-inner > p');
          const range = document.createRange(); range.setStart(paragraphs[0].firstChild, 0); range.setEnd(paragraphs[1].firstChild, 3);
          getSelection().removeAllRanges(); getSelection().addRange(range); document.dispatchEvent(new Event('selectionchange'));
        });
        await button.click(); assert.equal(await dialog.isVisible(), false);
        await second.click();
        for (const scenario of ['claims', 'source', 'copiedroot', 'unavailable', 'readfail', 'malformed-review', 'malformed-row', 'malformed-claims']) {
          mode = scenario; await selectText(page, 'safe selected'); await button.click();
          await page.locator('#manuscript-link-status.err').waitFor();
          assert.equal(await page.locator('#manuscript-link-save').isEnabled(), false, scenario + ' prevents save');
          if (scenario === 'readfail') {
            await page.locator('#research-manuscript-review .ctl-status.err').waitFor({state: 'attached'});
            assert.equal(await page.locator('#research-manuscript-review img').count(), 0, 'Review errors stay inert text');
          }
          if (scenario === 'source') {
            assert.equal(await page.locator('#' + id + ' mark.manuscript-claim-hit').count(), 0,
              'A source mismatch removes marks on the stale rendered manuscript');
            assert.equal(await page.locator('#manuscript-link-status [data-manuscript-link-reload]').count(), 1,
              'A stale manuscript offers an explicit reload');
            assert.match(await page.locator('#manuscript-link-status').textContent(), /changed after this page was loaded/);
          }
          if (scenario === 'readfail') assert.equal(await page.locator('#manuscript-link-status [data-manuscript-link-reload]').count(), 0,
            'Unrelated failures stay without a reload action');
          await dialog.locator('.modal-footer button').first().click();
        }
        mode = 'source';
        await page.locator('#tab-view-research').click();
        await page.locator('[data-rtab="review"]').click();
        await page.waitForFunction(() => document.querySelector('#research-manuscript-review [data-manuscript-link-reload]') !== null,
          null, {timeout: 5000});
        assert.equal(await page.locator('#research-manuscript-review [data-manuscript-link-reload]').count(), 1,
          'The review tab offers the same reload');
        assert.match(await page.locator('#research-manuscript-review').textContent(), /changed after this page was loaded/);
        await page.locator('#tab-view-analysis').click();
        mode = 'emptyclaims';
        await selectText(page, 'safe selected'); await button.click();
        await page.waitForFunction(() => document.querySelector('#manuscript-link-status').textContent.includes('No current claims yet'));
        assert.equal(await page.locator('#manuscript-link-claim').isEnabled(), false, 'An empty claim list keeps the picker disabled');
        assert.equal(await page.locator('#manuscript-link-status').getAttribute('class'), 'ctl-status', 'An empty claim list is informational, not an error');
        assert.equal(await page.locator('#manuscript-link-status [data-manuscript-link-reload]').count(), 0);
        await dialog.locator('.modal-footer button').first().click();
        mode = 'manyclaims';
        await selectText(page, 'safe selected'); await button.click();
        await page.waitForFunction(() => !document.querySelector('#manuscript-link-filter').hidden);
        assert.equal(await page.locator('#manuscript-link-claim option').count(), 10, 'Nine claims plus the placeholder');
        await page.locator('#manuscript-link-filter').fill('claim 8');
        assert.equal(await page.locator('#manuscript-link-claim option').count(), 2, 'The filter narrows the claim list');
        await page.locator('#manuscript-link-filter').fill('');
        assert.equal(await page.locator('#manuscript-link-claim option').count(), 10, 'Clearing the filter restores the list');
        await dialog.locator('.modal-footer button').first().click();
        mode = 'archivedrift';
        await selectText(page, 'safe selected'); await button.click();
        await page.locator('#manuscript-link-claim').selectOption('claim');
        await page.locator('#manuscript-link-retain').check();
        await page.locator('#manuscript-link-save').click();
        await page.waitForFunction(() => document.querySelector('#manuscript-link-status').textContent.includes('archive changed while this dialog was open'));
        assert.equal(await dialog.isVisible(), true, 'An archive conflict keeps the reviewed quote visible');
        await dialog.locator('.modal-footer button').first().click();
        mode = 'normal';
        for (const anchorState of ['moved', 'adjusted', 'ambiguous', 'changed', 'unavailable']) {
          links[0].anchor_state = anchorState; links[0].flags = ['source_changed', 'claim_changed'];
          await selectText(page, 'safe selected'); await button.click();
          await page.locator('#manuscript-link-claim').waitFor({state: 'visible'});
          await page.waitForFunction(() => !document.querySelector('#manuscript-link-claim').disabled);
          assert.equal(await page.locator('#' + id + ' mark.manuscript-claim-hit').count(), 0, anchorState + ' does not silently reanchor');
          await dialog.locator('.modal-footer button').first().click();
          await page.locator('#tab-view-research').click();
          await page.locator('[data-rtab="review"]').click();
          await page.locator('#r-review-refresh').click();
          await page.waitForFunction(expected => document.querySelector('#research-manuscript-review').textContent.includes(expected),
            {moved: 'Moved passage: review required', adjusted: 'Adjusted paragraph, quote found: can be accepted',
              ambiguous: 'Multiple possible passages: review required',
              changed: 'Passage changed: review required', unavailable: 'Source unavailable: review required'}[anchorState]);
          assert.match(await page.locator('#research-manuscript-review').textContent(), /Source bytes changed · Claim has a newer version/);
          if (anchorState === 'moved' || anchorState === 'adjusted') {
            const accept = page.locator('#research-manuscript-review [data-manuscript-link-accept]').first();
            await accept.waitFor();
            const before = writes.length;
            const routed = page.waitForResponse(response => response.url().includes('/api/research-manuscript-reanchor'));
            await accept.click();
            assert.equal((await (await routed).json()).ok, true);
            assert.equal(writes.length, before + 1);
            const payload = writes[before];
            assert.equal(payload.link_id, 'link');
            assert.equal(payload.expected_revision, 1);
            assert.equal(payload.expected_snapshot, 'snapshot');
            assert.equal(payload.expected_source_sha256, 'a'.repeat(64));
            assert.equal(payload.project_token, 'synthetic-project-token');
          }
          await page.locator('#tab-view-analysis').click();
        }
        links[0].anchor_state = 'resolved';
        mode = 'malformed-save'; await selectText(page, 'safe selected'); await button.click();
        await page.locator('#manuscript-link-claim').selectOption('claim'); await page.locator('#manuscript-link-retain').check();
        await page.locator('#manuscript-link-save').click(); await page.locator('#manuscript-link-status.err').waitFor();
        assert.equal(await dialog.isVisible(), true, 'An incomplete success envelope cannot claim a saved association');
        assert.equal(await page.locator('#manuscript-link-quote').textContent(), 'safe selected');
        await dialog.locator('.modal-footer button').first().click();
        mode = 'heldclaims'; await selectText(page, 'safe selected'); await button.click();
        await page.waitForFunction(() => document.querySelector('#manuscript-link-claim').disabled);
        await waitUntil(() => heldClaims);
        await page.locator('#research-manager').evaluate(el => { el.dataset.researchToken = 'new-context'; });
        releaseClaims(); await page.locator('#manuscript-link-status.err').waitFor();
        assert.equal(await page.locator('#manuscript-link-save').isEnabled(), false, 'Held old claims cannot unlock a different context');
        await dialog.locator('.modal-footer button').first().click();
        await page.locator('#research-manager').evaluate(el => { el.dataset.researchToken = 'synthetic-research-token'; });
        mode = 'heldsave'; await selectText(page, 'safe selected'); await button.click();
        await page.locator('#manuscript-link-claim').selectOption('claim'); await page.locator('#manuscript-link-retain').check();
        await page.locator('#manuscript-link-save').click();
        await waitUntil(() => heldSave);
        assert.equal(await page.locator('#manuscript-link-save').isEnabled(), false, 'Pending save deduplicates submission');
        assert.equal(await page.locator('#manuscript-link-claim').isEnabled(), false, 'The submitted claim pin cannot change during its pending write');
        assert.equal(await page.locator('#manuscript-link-retain').isEnabled(), false, 'Retention consent stays fixed during its pending write');
        await dialog.locator('.modal-footer button').first().click(); mode = 'normal';
        await selectText(page, 'selected sentence'); await button.click();
        await page.locator('#manuscript-link-claim').selectOption('claim'); releaseSave();
        await page.waitForTimeout(100);
        assert.equal(await dialog.isVisible(), true, 'Older accepted response preserves newer draft');
        assert.equal(await page.locator('#manuscript-link-quote').textContent(), 'selected sentence');
        assert.equal(await page.locator('#manuscript-link-retain').isChecked(), false);
        await dialog.screenshot({path: '/tmp/lixity-manuscript-links-picker-1440.png'});
        await dialog.locator('.modal-footer button').first().click();
      }
      assert.deepEqual(errors, []); await page.close();
    }
    console.log('Manual manuscript links: seven locales at 1440/320, retention, exact pins/codepoints, inert text, overlapping search/lazy marks; selection boundaries, stale/malformed envelopes, context/held responses and pending controls passed.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
