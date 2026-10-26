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
def read_only(*args, **kwargs):
    return original(*args, **{**kwargs, 'language_key': 'en',
        'enabled_actions': ['research-manuscript-review'],
        'manuscript_pdf_token': 'synthetic-project-token', 'research_context_token': 'synthetic-research-token',
        'manuscript_source_sha256': 'a' * 64})
render.__globals__['render_dashboard'] = read_only
fixtures['read-only'] = render()
print(json.dumps(fixtures))
`, {root});
async function waitUntil(predicate) {
  const deadline = Date.now() + 10000;
  while (!predicate()) {
    assert.ok(Date.now() < deadline, 'Expected held request reached the native action');
    await new Promise(resolve => setTimeout(resolve, 10));
  }
}
async function openVersions(page) {
  const versions = page.locator('#research-revision-versions');
  await versions.waitFor({state: 'visible'});
  if (!await versions.evaluate(details => details.open)) await versions.locator(':scope > summary').click();
}
async function selectText(page, text) {
  await page.locator('#chapters .ptext .ptext-inner > p').first().evaluate((p, quote) => {
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
    for (const width of [1440, 390, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}});
      page.setDefaultTimeout(10000);
      const errors = [], writes = [], recordReads = []; let historyReads = 0, anchorState = 'moved', holdHistorical = false, historicalHeld, releaseHistorical;
      let holdCurrent = false, currentHeld, releaseCurrent, failCurrent = false;
      let holdHistoryList = false, historyListHeld = false, releaseHistoryList;
      let holdEditorial = false, editorialHeld = 0, releaseEditorial;
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://lixity.test/**', async route => {
        const request = route.request(), url = new URL(request.url());
        if (request.method() !== 'GET') { writes.push(url.pathname); return route.abort(); }
        if (url.pathname === '/api/research/manuscript-review') {
          assert.equal(url.searchParams.get('project_token'), 'synthetic-project-token');
          const anchor = await page.locator('#chapters .ptext').first().evaluate(panel => ({
            start_line: Number(panel.dataset.start), end_line: Number(panel.dataset.end),
            paragraph_sha256: panel.dataset.paragraphSha256, start: 4, end: 17, quote: 'safe selected',
          }));
          const resolved = {resolved_start_line: anchor.start_line, resolved_end_line: anchor.end_line,
            resolved_start:4, resolved_end:17,
            resolved_chapter_num: ['moved', 'adjusted', 'resolved'].includes(anchorState) ? 1 : null,
            resolved_chapter_title: ['moved', 'adjusted', 'resolved'].includes(anchorState) ? 'Synthetic opening' : null};
          if (anchorState === 'adjusted') {
            anchor.start = 0; anchor.end = 13; anchor.paragraph_sha256 = 'b'.repeat(64);
          }
          return route.fulfill({json: {ok: true, schema_version: 'research-manuscript-review-local/1',
            project_id: 'project', snapshot: 'snapshot', current_source_sha256: 'a'.repeat(64), source_state: 'available',
            links: [{link_id: 'link', revision: 1, claim_id: 'claim', claim_revision: 1, claim_title: 'Synthetic claim',
              anchor, anchor_state: anchorState, flags: [], ...resolved}]}});
        }
        if (url.pathname === '/api/research/history') {
          ++historyReads;
          if (holdHistoryList) {
            historyListHeld = true;
            await new Promise(resolve => { releaseHistoryList = resolve; });
          }
          return route.fulfill({json: {ok: true,
            project_id: 'project', latest_revision: 2, revisions: [{revision: 2}, {revision: 1}]}});
        }
        if (url.pathname === '/api/research/review') {
          let candidates = [];
          if (holdEditorial) {
            holdEditorial = false; ++editorialHeld;
            await new Promise(resolve => { releaseEditorial = resolve; });
            candidates = Array.from({length: 4}, (_, index) => ({decision_id: 'decision-' + index,
              decision_revision: 1, title: 'Synthetic preceding editorial decision ' + index,
              decision_created_at: '2026-01-01T00:00:00Z', flags: [], sections: []}));
          }
          return route.fulfill({json: {ok: true, schema_version: 'research-editorial-review-local/1',
            project_id: 'project', snapshot: 'snapshot', decision_count: candidates.length,
            candidate_count: candidates.length, candidates}});
        }
        if (url.pathname === '/api/research/record') {
          recordReads.push(url);
          const revision = Number(url.searchParams.get('revision') || 2);
          if (holdCurrent && !url.searchParams.has('revision')) {
            currentHeld = true;
            await new Promise(resolve => { releaseCurrent = resolve; });
          }
          if (failCurrent && !url.searchParams.has('revision')) return route.fulfill({status: 503, json: {ok: false, message: 'Synthetic latest-read failure'}});
          if (url.searchParams.get('kind') === 'dossier') return route.fulfill({json: {ok: true,
            project_id: 'project', snapshot: 'snapshot', kind: 'dossier', record_id: 'dossier-original', latest_revision: 1,
            record: {id: 'dossier-original', kind: 'dossier', revision: 1, title: 'Original pinned dossier', body: 'Historical dossier notes.', evidence_refs: [], tags: []},
            citations: []}});
          if (holdHistorical && revision === 1) {
            historicalHeld = true;
            await new Promise(resolve => { releaseHistorical = resolve; });
          }
          return route.fulfill({json: {ok: true, project_id: 'project', snapshot: 'snapshot',
            kind: 'claim', record_id: 'claim', latest_revision: 2,
            record: {id: 'claim', kind: 'claim', revision, title: revision === 1 ? 'Pinned original claim' : 'Latest changed claim',
              statement: 'Synthetic statement', scope: {}, dossier_ref: {id: revision === 1 ? 'dossier-original' : 'dossier-latest', revision: 1}, tags: []},
            citation_scope: 'current_links_to_pinned_claim_revision', citations: [{availability: 'available', passage_id: 'passage',
              source_title: 'Synthetic retained source', verbatim: revision === 1 ? 'Pinned source quotation.' : 'Latest source quotation.'}]}});
        }
        if (url.pathname.startsWith('/api/')) return route.fulfill({json: {ok: true, initialized: true,
          project_id: 'project', snapshot: 'snapshot', sources: [], dossiers: [], claims: [], decisions: [], candidates: []}});
        return route.fulfill({contentType: 'text/html', body: fixtures['read-only']});
      });
      await page.goto('http://lixity.test/');
      assert.equal(await page.locator('body').getAttribute('data-manuscript-links'), 'read');
      assert.equal(await page.locator('#manuscript-pdf-form, #workspace-reader-toggle').count(), 0,
        'Review alone does not advertise PDF generation or a dossier companion');
      await page.locator('#tab-view-analysis').click();
      await selectText(page, 'safe selected'); await page.keyboard.press('Alt+l');
      assert.equal(await page.locator('[data-manuscript-link-selection], #manuscript-link-dialog').count(), 0,
        'Read-only review exposes no selection writer or editing shortcut');
      await page.locator('#tab-view-research').click();
      await page.locator('[data-rtab=review]').click();
      await page.locator('#research-manuscript-review blockquote').waitFor();
      assert.equal(await page.locator('#research-manuscript-review blockquote').textContent(), 'safe selected');
      assert.equal(await page.locator('[data-manuscript-link-accept]').count(), 0,
        'A moved anchor stays inspectable without offering a write action');
      for (const candidateState of ['moved', 'adjusted']) {
        anchorState = candidateState;
        await page.locator('#r-review-refresh').click();
        const candidate = page.locator('#research-manuscript-review [data-manuscript-link-candidate]');
        await candidate.waitFor();
        assert.equal(await page.locator('#research-manuscript-review [data-manuscript-current-chapter]').textContent(), 'Current chapter 1: Synthetic opening');
        assert.equal(await candidate.textContent(), 'Inspect candidate passage');
        if (candidateState === 'adjusted') await page.locator('#research-manuscript-review').screenshot({
          path:`/tmp/lixity-manuscript-candidate-${width}.png`});
        await candidate.focus(); await page.keyboard.press('Enter');
        assert.equal(await page.locator('#view-pane-analysis').evaluate(node => node.classList.contains('active')), true);
        assert.equal(await page.locator('#chapters mark.manuscript-claim-hit').count(), 0,
          'Inspecting a candidate never accepts or marks its saved association');
        assert.deepEqual(writes, [], 'Candidate inspection is read-only');
        await page.locator('#tab-view-research').click();
        await page.locator('[data-rtab=review]').click();
      }
      for (const unavailableState of ['ambiguous', 'changed', 'unavailable']) {
        anchorState = unavailableState;
        const refreshed = page.waitForResponse(response => response.url().includes('/api/research/manuscript-review'));
        await page.locator('#r-review-refresh').click();
        await refreshed;
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        assert.equal(await page.locator('[data-manuscript-link-candidate]').count(), 0);
      }
      anchorState = 'adjusted';
      await page.locator('#r-review-refresh').click();
      await page.locator('#research-manuscript-review [data-manuscript-link-candidate]').waitFor();
      const guarded = await page.evaluate(() => {
        const button = document.querySelector('#research-manuscript-review [data-manuscript-link-candidate]');
        const panel = document.querySelector('#chapters .ptext'), original = paragraphContent[panel.id][0];
        paragraphContent[panel.id][0] = 'Changed candidate text'; button.click();
        paragraphContent[panel.id][0] = original;
        return document.querySelector('#view-pane-research').classList.contains('active');
      });
      assert.equal(guarded, true, 'Changed candidate quote cannot navigate from a stale rendered action');
      const contextGuarded = await page.evaluate(() => {
        const button = document.querySelector('#research-manuscript-review [data-manuscript-link-candidate]');
        const original = document.body.dataset.manuscriptSourceSha256;
        document.body.dataset.manuscriptSourceSha256 = 'c'.repeat(64); button.click();
        document.body.dataset.manuscriptSourceSha256 = original;
        return document.querySelector('#view-pane-research').classList.contains('active');
      });
      assert.equal(contextGuarded, true, 'A changed manuscript context blocks candidate navigation');
      anchorState = 'moved';
      await page.locator('#r-review-refresh').click();
      await page.locator('#research-manuscript-review [data-manuscript-link-candidate]').waitFor();
      await page.locator('#research-manuscript-review [data-research-history=claim]').click();
      const claimHistory = page.locator('#research-revision-history-detail');
      await claimHistory.getByText('Pinned original claim', {exact: true}).waitFor();
      assert.equal(await page.locator('#research-revision-versions').evaluate(details => details.open), false,
        'A pinned entry opens directly with its optional version list collapsed');
      assert.equal(historyReads, 0, 'Opening an entry does not fetch its version list');
      assert.equal(recordReads[0].searchParams.get('revision'), '1',
        'Opening the saved association requests its pinned version before loading any newer claim evidence');
      assert.match(await claimHistory.textContent(), /dossier-original/,
        'Opening an association reads its pinned claim and historical dossier association');
      assert.match(await claimHistory.textContent(), /Pinned source quotation/);
      assert.doesNotMatch(await claimHistory.textContent(), /Latest source quotation|dossier-latest/,
        'Evidence and dossier pins from a newer claim cannot replace the saved association');
      holdCurrent = true;
      await page.locator('#research-revision-edit-tab').click();
      await waitUntil(() => currentHeld);
      const editTitle = page.locator('#research-revision-field-title');
      assert.equal(await editTitle.isDisabled(), true,
        'Pinned fields cannot accept a draft while Edit is loading the current record');
      assert.equal(await page.locator('#research-revision-reason').isDisabled(), true);
      assert.equal(await page.locator('#research-revision-save').isDisabled(), true);
      failCurrent = true; holdCurrent = false; releaseCurrent();
      await page.locator('#research-revision-status').getByText(/Synthetic latest-read failure/).waitFor();
      assert.equal(await editTitle.isDisabled(), true, 'Failed current reads leave historical fields read-only');
      assert.equal(await page.locator('#research-revision-reload').isEnabled(), true, 'The existing reload action offers an explicit retry');
      failCurrent = false;
      await page.locator('#research-revision-reload').click();
      await page.waitForFunction(() => document.querySelector('#research-revision-field-title').value === 'Latest changed claim'
        && !document.querySelector('#research-revision-field-title').disabled);
      await editTitle.fill('New explicit draft after current fields are ready');
      await page.locator('#research-revision-history-tab').click();
      await page.locator('#research-revision-edit-tab').click();
      assert.equal(await editTitle.inputValue(), 'New explicit draft after current fields are ready',
        'Changing tabs after the current read preserves the author draft');
      await page.locator('#research-revision-history-tab').click();
      await openVersions(page);
      await page.locator('#research-revision-history-list [data-research-revision="2"]').click();
      await claimHistory.getByText('Latest changed claim', {exact: true}).waitFor();
      assert.match(await claimHistory.textContent(), /Latest source quotation|dossier-latest/,
        'The newest saved claim remains available through an explicit version choice');
      await page.locator('#research-revision-history-list [data-research-revision="1"]').click();
      await claimHistory.locator('[data-research-history=dossier][data-record-id=dossier-original]').click();
      await claimHistory.getByText('Original pinned dossier', {exact: true}).waitFor();
      assert.match(await claimHistory.textContent(), /Historical dossier notes/,
        'The claim opens its pinned historical dossier rather than its current association');
      await page.keyboard.press('Escape');
      anchorState = 'resolved'; await page.locator('#r-review-refresh').click();
      await page.locator('mark.manuscript-claim-hit').waitFor({state: 'attached'});
      await page.locator('#research-manuscript-review [data-manuscript-link-jump]').click();
      assert.equal(await page.locator('#tab-view-analysis').getAttribute('aria-selected'), 'true', 'Read-only associations also navigate without a write capability');
      assert.equal(await page.locator('mark.manuscript-claim-hit').first().textContent(), 'safe selected');
      await page.locator('mark.manuscript-claim-hit').first().click();
      assert.equal(await page.locator('#tab-view-analysis').getAttribute('aria-selected'), 'true', 'Inline association keeps the manuscript visible');
      await page.locator('[data-passage-research] [data-manuscript-links-paragraph]').click();
      assert.equal(await page.locator('#tab-view-research').getAttribute('aria-selected'), 'true',
        'A supported inline association opens its reviewed saved quotation');
      assert.equal(await page.locator('#research-manuscript-review .manuscript-link-review-item').count(), 1);
      await page.locator('#research-manuscript-review [data-manuscript-link-jump]').click();
      const originQuote = '😀 safe selected';
      await page.locator('#chapters .ptext').first().focus();
      await selectText(page, originQuote);
      await page.evaluate(() => {
        const selection = getSelection();
        selection.setBaseAndExtent(selection.focusNode, selection.focusOffset, selection.anchorNode, selection.anchorOffset);
      });
      const nativeSelection = () => page.evaluate(() => {
        const selection = getSelection(), direction = document.createRange();
        direction.setStart(selection.anchorNode, selection.anchorOffset);
        direction.setEnd(selection.focusNode, selection.focusOffset);
        return {quote: selection.toString(), backward: !selection.isCollapsed && direction.collapsed};
      });
      assert.deepEqual(await nativeSelection(), {quote: originQuote, backward: true},
        'The keyboard relation route starts with a backward native selection around an astral character');
      await page.locator('#chapters [data-manuscript-links-paragraph]').focus();
      assert.equal((await nativeSelection()).quote, originQuote, 'Focusing the relation control keeps the selected quote');
      holdEditorial = true;
      await page.keyboard.press('Enter');
      await page.locator('[data-passage-research] [data-manuscript-links-paragraph]').click();
      await waitUntil(() => editorialHeld === 1);
      assert.equal(await page.locator('#tab-view-research').getAttribute('aria-selected'), 'true',
        'The native paragraph association control offers the same keyboard-accessible route');
      await page.locator('#research-manuscript-review [data-manuscript-link-jump]').waitFor();
      const originReturn = page.locator('#workbench-return');
      assert.equal(await originReturn.isVisible(), true, 'Research keeps a visible return to the originating passage');
      const thread = page.locator('#workbench-thread');
      assert.match(await thread.textContent(), /Manuscript · lines/);
      releaseEditorial();
      await page.locator('#research-editorial-review .research-card').nth(3).waitFor();
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const destination = await page.locator('#research-manuscript-review blockquote').boundingBox();
      assert.ok(destination.y >= 0 && destination.y + destination.height <= 900,
        'The scoped quote destination remains visible after preceding editorial decisions finish rendering');
      await page.locator('#research-manuscript-review [data-research-history=claim]').click();
      await claimHistory.getByText('Pinned original claim', {exact: true}).waitFor();
      assert.doesNotMatch(await thread.textContent(), /Pinned original claim|Viewed record|Version 1/i,
        'The return control does not duplicate the record viewer metadata');
      assert.match(await page.locator('#research-revision-kind').textContent(), /Version 1/i);
      await page.locator('#research-revision-edit-tab').click();
      await page.waitForFunction(() => document.querySelector('#research-revision-field-title').value === 'Latest changed claim'
        && !document.querySelector('#research-revision-field-title').disabled);
      assert.doesNotMatch(await thread.textContent(), /Latest changed claim|Version 2/i);
      assert.match(await page.locator('#research-revision-kind').textContent(), /Version 2/i);
      holdHistoryList = true;
      await page.locator('#research-revision-history-tab').click();
      await openVersions(page);
      await waitUntil(() => historyListHeld);
      await page.locator('#research-revision-edit-tab').click();
      await editTitle.fill('Unsaved draft while history loads');
      const currentMeta = await page.locator('#research-revision-kind').textContent();
      const currentThread = await thread.textContent();
      assert.match(currentMeta, /Version 2/i);
      assert.doesNotMatch(currentThread, /Latest changed claim|Version 2/i);
      const readsBeforeHistoryList = recordReads.length;
      holdHistoryList = false; releaseHistoryList();
      await page.locator('#research-revision-history-list [data-research-revision="1"]').waitFor({state: 'attached'});
      assert.equal(recordReads.length, readsBeforeHistoryList,
        'Loading the optional version list never chooses or reads another version automatically');
      assert.equal(await page.locator('#research-revision-kind').textContent(), currentMeta,
        'A delayed version list cannot clear active Edit metadata');
      assert.equal(await thread.textContent(), currentThread,
        'A hidden version list cannot replace the active viewed current version');
      await page.locator('#research-revision-history-tab').click();
      holdHistorical = true; historicalHeld = false;
      await page.locator('#research-revision-history-list [data-research-revision="1"]').click();
      await waitUntil(() => historicalHeld);
      await page.locator('#research-revision-edit-tab').click();
      assert.equal(await page.locator('#research-revision-kind').textContent(), currentMeta);
      assert.equal(await thread.textContent(), currentThread,
        'An explicitly requested historical read does not replace the active Edit identity');
      holdHistorical = false; releaseHistorical();
      await page.waitForFunction(() => document.querySelector('#research-revision-history-detail').textContent.includes('Pinned original claim'));
      assert.equal(await page.locator('#research-revision-edit-tab').getAttribute('aria-selected'), 'true');
      assert.equal(await page.locator('#research-revision-kind').textContent(), currentMeta,
        'Completing the hidden History cache preserves active Edit metadata');
      assert.equal(await thread.textContent(), currentThread);
      assert.equal(await editTitle.inputValue(), 'Unsaved draft while history loads',
        'Hidden history loading preserves the unsaved current-record draft');
      historicalHeld = false;
      const readsAfterHiddenHistory = recordReads.length;
      await page.locator('#research-revision-history-tab').click();
      await claimHistory.getByText('Pinned original claim', {exact: true}).waitFor();
      assert.equal(recordReads.length, readsAfterHiddenHistory, 'Returning to History uses its completed hidden cache');
      assert.doesNotMatch(await thread.textContent(), /Pinned original claim|Version 1/i,
        'Switching record versions keeps navigation limited to its return destination');
      assert.match(await page.locator('#research-revision-kind').textContent(), /Version 1/i);
      await page.locator('#research-revision-history-list [data-research-revision="2"]').click();
      await claimHistory.getByText('Latest changed claim', {exact: true}).waitFor();
      assert.doesNotMatch(await thread.textContent(), /Latest changed claim|Version 2/i);
      assert.match(await page.locator('#research-revision-kind').textContent(), /Version 2/i);
      await page.keyboard.press('Escape');
      for (const colorScheme of ['light', 'dark']) {
        await page.emulateMedia({colorScheme});
        await thread.screenshot({path: `/tmp/lixity-work-thread-${colorScheme}-${width}.png`});
        await page.screenshot({path: `/tmp/lixity-work-thread-context-${colorScheme}-${width}.png`});
      }
      await page.emulateMedia({colorScheme: 'light'});
      if (width === 1440) {
        await page.locator('#workspace-navigation-toggle').click();
        await thread.screenshot({path: '/tmp/lixity-work-thread-collapsed-1440.png'});
        assert.ok(await thread.evaluate(node => node.scrollWidth <= node.clientWidth + 1),
          'The work thread remains usable when navigation is collapsed');
        await page.locator('#workspace-navigation-toggle').click();
      }
      await page.locator('#chapters .ptext-inner > p').first().evaluate(paragraph => {
        const oldText = paragraph.textContent, oldNode = paragraph.firstChild;
        renderParagraphText(paragraph, 'safe');
        if (paragraph.textContent !== oldText || paragraph.firstChild === oldNode) throw new Error('Expected a text-preserving mark repaint');
      });
      await originReturn.click();
      assert.equal(await thread.isVisible(), false, 'Returning clears the contextual thread');
      assert.equal(await page.locator('#tab-view-analysis').getAttribute('aria-selected'), 'true');
      assert.equal(await page.evaluate(() => document.activeElement.id), 'p-0');
      assert.deepEqual(await nativeSelection(), {quote: originQuote, backward: true},
        'Returning after Research repaints marks restores the exact native quote and selection direction');
      holdEditorial = true;
      await page.locator('#chapters [data-manuscript-links-paragraph]').click();
      await page.locator('[data-passage-research] [data-manuscript-links-paragraph]').click();
      await waitUntil(() => editorialHeld === 2);
      await page.mouse.wheel(0, -500);
      await page.evaluate(() => { document.documentElement.style.overflowAnchor = 'none'; scrollTo(0, 0); });
      releaseEditorial();
      await page.locator('#research-editorial-review .research-card').nth(3).waitFor();
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.equal(await page.evaluate(() => scrollY), 0,
        'A manual scroll while the preceding read is pending cancels deferred destination alignment');
      await originReturn.click();
      holdEditorial = true;
      await page.locator('#chapters [data-manuscript-links-paragraph]').click();
      await page.locator('[data-passage-research] [data-manuscript-links-paragraph]').click();
      await waitUntil(() => editorialHeld === 3);
      await page.locator('body').evaluate(body => { body.dataset.manuscriptSourceSha256 = 'b'.repeat(64); });
      await page.evaluate(() => scrollTo(0, 0));
      releaseEditorial();
      await page.locator('#research-editorial-review .research-card').nth(3).waitFor();
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.equal(await page.evaluate(() => scrollY), 0,
        'A source-context change cancels destination alignment before a held preceding read renders');
      assert.equal(await thread.isVisible(), false, 'A source change removes the stale thread and return control immediately');
      await originReturn.evaluate(button => button.click());
      assert.equal(await page.locator('#tab-view-research').getAttribute('aria-selected'), 'true',
        'A changed displayed source invalidates the saved origin instead of restoring an obsolete passage');
      await page.locator('body').evaluate(body => { body.dataset.manuscriptSourceSha256 = 'a'.repeat(64); });
      await page.locator('#r-review-refresh').click();
      await page.locator('#research-manuscript-review [data-research-history=claim]').waitFor();
      holdHistorical = true;
      await page.locator('#research-manuscript-review [data-research-history=claim]').click();
      await waitUntil(() => historicalHeld);
      await page.locator('#research-manager').evaluate(panel => { panel.dataset.researchToken = 'different-root'; });
      const staleReply = page.waitForResponse(response => response.url().includes('/api/research/record') && new URL(response.url()).searchParams.get('revision') === '1');
      releaseHistorical(); await staleReply;
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.doesNotMatch(await claimHistory.textContent(), /Pinned original claim|Pinned source quotation/,
        'A held historical reply cannot populate a dialog after the selected root changes');
      await page.keyboard.press('Escape');
      await page.locator('body').evaluate(body => { body.dataset.manuscriptProjectToken = 'changed-project'; });
      await page.waitForFunction(() => !document.querySelector('mark.manuscript-claim-hit'));
      assert.deepEqual(writes, []); assert.deepEqual(errors, []);
      await page.screenshot({path: `/tmp/lixity-manuscript-review-read-only-${width}.png`});
      await page.close();
    }
    for (const [locale, html] of Object.entries(fixtures).filter(([locale]) => locale !== 'read-only')) for (const width of [1440, 320]) {
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
          if (mode === 'duplicate') return route.fulfill({status: 409, json: {ok: false, code: 'duplicate-link', link_id: 'link'}});
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
      const id = await chip.getAttribute('data-target');
      const button = page.locator('#' + id + ' [data-manuscript-link-selection]');
      await selectText(page, 'safe selected');
      const selectionAction = page.locator('#manuscript-selection-tools [data-reader-action=link]');
      await selectionAction.waitFor();
      assert.equal(await button.count(), 1, 'Native compatible paragraph offers manual association');
      if (locale === 'en' && width === 320) await page.keyboard.press('Alt+l'); else await selectionAction.click();
      const dialog = page.locator('#manuscript-link-dialog'); await dialog.waitFor({state: 'visible'});
      await page.locator('#manuscript-link-claim').selectOption('claim');
      if (locale === 'en' && width === 1440) {
        await dialog.evaluate(node => {
          node.close();
          document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'l', altKey: true, bubbles: true}));
        });
        await page.locator('#manuscript-link-claim').selectOption('claim', {timeout: 5000});
        assert.equal(await dialog.isVisible(), true, 'A rapid cancel and reopen keeps the new quotation draft usable');
      }
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
      await page.locator('#tab-view-research').click(); await page.locator('#tab-view-analysis').click();
      assert.equal(await page.locator('#' + id + ' mark.manuscript-claim-hit').count() > 0, true, 'Links survive workspace navigation');
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
        assert.equal(await page.locator('#research-manuscript-review > p').first().textContent(), '1 association',
          'The review count names the manuscript association');
        assert.match(reviewText, /Exact passage/, 'Resolved anchors report their state');
        assert.match(reviewText, /Synthetic claim/, 'The pinned claim title stays visible');
        assert.equal(await page.locator('#research-manuscript-review blockquote').textContent(), 'safe selected');
        assert.equal(await page.locator('#research-manuscript-review [data-research-history="claim"]').count(), 1);
        const returnToPassage = page.locator('#research-manuscript-review [data-manuscript-link-jump]');
        assert.equal(await returnToPassage.count(), 1, 'An exact association offers a direct manuscript return');
        await returnToPassage.click();
        assert.equal(await page.locator('#tab-view-analysis').getAttribute('aria-selected'), 'true');
        assert.equal(await page.evaluate(() => document.activeElement.id), id, 'Return focuses the linked passage');
        // A selection must stay inside manuscript text, never metrics/headings.
        await page.locator('#' + id + ' .stats').evaluate(el => {
          const range = document.createRange(); range.selectNodeContents(el);
          getSelection().removeAllRanges(); getSelection().addRange(range);
          document.dispatchEvent(new Event('selectionchange'));
        });
        await page.keyboard.press('Alt+l'); assert.equal(await dialog.isVisible(), false);
        await page.evaluate(() => {
          const paragraphs = document.querySelectorAll('#chapters .ptext .ptext-inner > p');
          const range = document.createRange(); range.setStart(paragraphs[0].firstChild, 0); range.setEnd(paragraphs[1].firstChild, 3);
          getSelection().removeAllRanges(); getSelection().addRange(range); document.dispatchEvent(new Event('selectionchange'));
        });
        await page.keyboard.press('Alt+l'); assert.equal(await dialog.isVisible(), false);
        for (const scenario of ['claims', 'source', 'copiedroot', 'unavailable', 'readfail', 'malformed-review', 'malformed-row', 'malformed-claims']) {
          mode = scenario; await selectText(page, 'safe selected'); await page.keyboard.press('Alt+l');
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
        await selectText(page, 'safe selected'); await page.keyboard.press('Alt+l');
        await page.waitForFunction(() => document.querySelector('#manuscript-link-status').textContent.includes('No current claims yet'));
        assert.equal(await page.locator('#manuscript-link-claim').isEnabled(), false, 'An empty claim list keeps the picker disabled');
        assert.equal(await page.locator('#manuscript-link-status').getAttribute('class'), 'ctl-status', 'An empty claim list is informational, not an error');
        assert.equal(await page.locator('#manuscript-link-status [data-manuscript-link-reload]').count(), 0);
        await dialog.locator('.modal-footer button').first().click();
        mode = 'manyclaims';
        await selectText(page, 'safe selected'); await page.keyboard.press('Alt+l');
        await page.waitForFunction(() => !document.querySelector('#manuscript-link-filter').hidden);
        assert.equal(await page.locator('#manuscript-link-claim option').count(), 10, 'Nine claims plus the placeholder');
        await page.locator('#manuscript-link-filter').fill('claim 8');
        assert.equal(await page.locator('#manuscript-link-claim option').count(), 2, 'The filter narrows the claim list');
        await page.locator('#manuscript-link-filter').fill('');
        assert.equal(await page.locator('#manuscript-link-claim option').count(), 10, 'Clearing the filter restores the list');
        await dialog.locator('.modal-footer button').first().click();
        mode = 'archivedrift';
        await selectText(page, 'safe selected'); await page.keyboard.press('Alt+l');
        await page.locator('#manuscript-link-claim').selectOption('claim');
        await page.locator('#manuscript-link-retain').check();
        await page.locator('#manuscript-link-save').click();
        await page.waitForFunction(() => document.querySelector('#manuscript-link-status').textContent.includes('archive changed while this dialog was open'));
        assert.equal(await dialog.isVisible(), true, 'An archive conflict keeps the reviewed quote visible');
        await dialog.locator('.modal-footer button').first().click();
        mode = 'duplicate';
        await selectText(page, 'safe selected'); await page.keyboard.press('Alt+l');
        await page.locator('#manuscript-link-claim').selectOption('claim');
        await page.locator('#manuscript-link-retain').check();
        await page.locator('#manuscript-link-save').click();
        await page.waitForFunction(() => document.querySelector('#manuscript-link-status').textContent ===
          window.LixityManuscriptLinks.label('manuscript_link_duplicate'));
        await dialog.screenshot({path: `/tmp/lixity-manuscript-duplicate-${width}.png`});
        await page.setViewportSize({width:320, height:900});
        const duplicateBox = await dialog.boundingBox();
        assert.ok(duplicateBox.x >= 0 && duplicateBox.x + duplicateBox.width <= 320,
          'The duplicate explanation stays within the mobile dialog');
        await dialog.screenshot({path: '/tmp/lixity-manuscript-duplicate-320.png'});
        await page.setViewportSize({width, height:900});
        assert.equal(await page.locator('#manuscript-link-save').isEnabled(), false,
          'An existing association blocks repeated submission without claiming the archive is stale');
        await page.locator('#manuscript-link-retain').uncheck(); await page.locator('#manuscript-link-retain').check();
        assert.equal(await page.locator('#manuscript-link-save').isEnabled(), false);
        await dialog.locator('.modal-footer button').first().click();
        mode = 'normal';
        for (const anchorState of ['moved', 'adjusted', 'ambiguous', 'changed', 'unavailable']) {
          links[0].anchor_state = anchorState; links[0].flags = ['source_changed', 'claim_changed'];
          await selectText(page, 'safe selected'); await page.keyboard.press('Alt+l');
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
          assert.match(await page.locator('#research-manuscript-review').textContent(), /Manuscript changed · Claim has a newer version/);
          assert.equal(await page.locator('#research-manuscript-review [data-manuscript-link-jump]').count(), 0, 'Unresolved anchors never offer an exact return');
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
        mode = 'malformed-save'; await selectText(page, 'safe selected'); await page.keyboard.press('Alt+l');
        await page.locator('#manuscript-link-claim').selectOption('claim'); await page.locator('#manuscript-link-retain').check();
        await page.locator('#manuscript-link-save').click(); await page.locator('#manuscript-link-status.err').waitFor();
        assert.equal(await dialog.isVisible(), true, 'An incomplete success envelope cannot claim a saved association');
        assert.equal(await page.locator('#manuscript-link-quote').textContent(), 'safe selected');
        await dialog.locator('.modal-footer button').first().click();
        mode = 'heldclaims'; await selectText(page, 'safe selected'); await page.keyboard.press('Alt+l');
        await page.waitForFunction(() => document.querySelector('#manuscript-link-claim').disabled);
        await waitUntil(() => heldClaims);
        await page.locator('#research-manager').evaluate(el => { el.dataset.researchToken = 'new-context'; });
        releaseClaims(); await page.locator('#manuscript-link-status.err').waitFor();
        assert.equal(await page.locator('#manuscript-link-save').isEnabled(), false, 'Held old claims cannot unlock a different context');
        await dialog.locator('.modal-footer button').first().click();
        await page.locator('#research-manager').evaluate(el => { el.dataset.researchToken = 'synthetic-research-token'; });
        mode = 'heldsave'; await selectText(page, 'safe selected'); await page.keyboard.press('Alt+l');
        await page.locator('#manuscript-link-claim').selectOption('claim'); await page.locator('#manuscript-link-retain').check();
        await page.locator('#manuscript-link-save').click();
        await waitUntil(() => heldSave);
        assert.equal(await page.locator('#manuscript-link-save').isEnabled(), false, 'Pending save deduplicates submission');
        assert.equal(await page.locator('#manuscript-link-claim').isEnabled(), false, 'The submitted claim pin cannot change during its pending write');
        assert.equal(await page.locator('#manuscript-link-retain').isEnabled(), false, 'Retention consent stays fixed during its pending write');
        await dialog.locator('.modal-footer button').first().click(); mode = 'normal';
        await selectText(page, 'selected sentence'); await page.keyboard.press('Alt+l');
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
    console.log('Manuscript links: pinned claim/dossier history and citations, inline/paragraph relation routes, source-bound origin return, rapid dialog reopen, read-only review and seven editing locales at1440/320, retention, exact pins/codepoints, inert text, selection boundaries and stale/malformed/pending guards passed.');
  } finally {
    await Promise.all(browser.contexts().flatMap(context => context.pages()).map(page => page.unrouteAll({behavior: 'ignoreErrors'})));
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
