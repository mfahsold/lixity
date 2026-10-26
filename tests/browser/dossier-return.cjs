// Dossier departures retain their exact accepted reading context, without writes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {startNativeServer} = require('./support/native-server.cjs');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-dossier-return-'));

function fixtureSource(reading = true) {
  return `
import hashlib, json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
base = Path(sys.argv[1]); project = base / 'synthetic-project'
api.init(project, title='Synthetic dossier return')
source = base / 'source.txt'
source.write_text('The synthetic archive opened in 1924.\\n\\nRain fell over the synthetic reading room.', encoding='utf-8')
api.ingest(project, source, allow_retention=True, title='Synthetic retained source')
api.reindex(project)
passage = api.search(project, 'archive')['hits'][0]['passage_id']
body = '# Notes\\n\\n' + '\\n\\n'.join('Synthetic reading note %d. Keep this dossier reading position.' % n for n in range(24)) + '\\n\\n# Detail\\n\\nAn original synthetic note.'
dossier = api.create_dossier(project, title='Origin synthetic dossier', body=body, evidence_ids=[passage])
claim = api.create_claim(project, title='Synthetic linked claim', statement='Synthetic archive interpretation.', dossier_id=dossier['dossier_id'])
api.link_evidence(project, claim_id=claim['claim_id'], passage_id=passage)
manuscript = project / 'manuscript.md'
manuscript.write_text('# Synthetic native manuscript\\n\\n## First chapter\\n\\nA bird crosses the quiet garden. Rain begins.\\n\\n## Second chapter\\n\\nA quiet house stands beyond the garden.\\n', encoding='utf-8')
anchor = api.resolve_manuscript_anchor(project, manuscript, query='A bird crosses the quiet garden.')
api.link_manuscript_claim(project, manuscript, claim['claim_id'], claim_revision=1,
    selection={key: anchor[key] for key in ('start_line','end_line','paragraph_sha256','start','end','quote')},
    expected_project_id=anchor['project_id'], expected_snapshot=anchor['snapshot'],
    expected_source_sha256=hashlib.sha256(manuscript.read_bytes()).hexdigest(), allow_retention=True)
current = api.get_record(project, 'dossier', dossier['dossier_id'])
api.revise_record(project, 'dossier', dossier['dossier_id'], changes={'body': body.replace('An original synthetic note.', 'A current synthetic note.')},
    expected_snapshot=current['snapshot'], expected_revision=1, change_kind='correction', reason='Synthetic dossier revision')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.research_dir = str(project)
LixityServerHandler.source_input = ${reading ? 'str(manuscript)' : 'None'}
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.language = 'en'; LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'dossier': dossier['dossier_id'], 'claim': claim['claim_id']}), flush=True)
server.serve_forever()
`;
}

async function positions(control, capture = false) {
  return control.evaluate((element, capture) => {
    function snapshot() {
      const result = [];
      for (let node = element.parentElement; node; node = node.parentElement) {
        if (node.scrollHeight > node.clientHeight || node.scrollWidth > node.clientWidth) {
          result.push({id: node.id, top: node.scrollTop, left: node.scrollLeft});
        }
      }
      return {scrolls: result, top: element.getBoundingClientRect().top, left: element.getBoundingClientRect().left};
    }
    if (!capture) return snapshot();
    element._dossierDeparture = {count: 0, positions: null};
    element.addEventListener('pointerdown', () => {
      element._dossierDeparture.count++;
      element._dossierDeparture.positions = snapshot();
    }, {once: true, capture: true});
  }, capture);
}
async function assertReturned(page, control, before, message) {
  await expect(control, message).toBeFocused();
  await expect.poll(async () => Math.abs((await control.boundingBox()).y - before.top), {message}).toBeLessThan(2);
  const after = await positions(control);
  assert.deepEqual(after.scrolls, before.scrolls, message + ': every source scrollport is restored');
  assert.ok(Math.abs(after.left - before.left) < 2, message + ': horizontal position is retained');
  await expect.poll(() => control.evaluate(element => element.classList.contains('flash') &&
    getComputedStyle(element).boxShadow !== 'none'), {
    message: 'The returned dossier control receives a visible arrival cue without shifting content',
  }).toBe(true);
}
async function assertReturnAvailable(page) {
  // Check geometry before screenshots or clicks can implicitly scroll the
  // return into view. The action must already be available at the destination.
  await expect.poll(() => page.locator('#workbench-return').evaluate(button => {
    const box = button.getBoundingClientRect();
    return box.top >= 0 && box.bottom <= innerHeight && box.left >= 0 && box.right <= innerWidth;
  }), {message: 'The dossier return is immediately inside the destination viewport'}).toBe(true);
}
async function depart(page, control, tab) {
  // Supplemental dossier actions require an explicit native disclosure click.
  const actions = control.locator('xpath=ancestor::details[contains(@class,"research-dossier-actions")]');
  if (await actions.count() && await actions.getAttribute('open') === null) {
    await actions.locator(':scope > summary').click();
  }
  await control.scrollIntoViewIfNeeded();
  await control.focus();
  // Hover can change click actionability even after a trial. Capture the real
  // native departure event, before navigation, rather than its earlier layout.
  await control.click({trial: true});
  // A second locator.click can run another implicit ancestor scroll between
  // actionability and pointerdown, leaving a sticky dock in a transient layout.
  // Click the checked native target directly so departure reflects the visible UI.
  const clickBox = await control.boundingBox();
  assert.ok(clickBox);
  await positions(control, true);
  await page.mouse.click(clickBox.x + clickBox.width / 2, clickBox.y + clickBox.height / 2);
  const captured = await control.evaluate(element => {
    const value = element._dossierDeparture;
    delete element._dossierDeparture;
    return value;
  });
  assert.ok(captured && captured.count === 1 && captured.positions,
    'One native pointerdown captures a non-null departure origin');
  const before = captured.positions;
  await expect(page.locator(`[data-rtab=${tab}]`)).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#workbench-return')).toBeVisible();
  await expect(page.locator('#workbench-return')).toHaveText('Back to dossier');
  await expect(page.locator('#workbench-thread')).toContainText('Origin synthetic dossier');
  await expect(page.locator('#workbench-thread')).toContainText('Version 2');
  await assertReturnAvailable(page);
  if (page.dossierEvidence && !page.dossierEvidence.captured) {
    page.dossierEvidence.captured = true;
    await page.screenshot({path: page.dossierEvidence.prefix + '-departure.png'});
    await page.locator('#workbench-thread').screenshot({path: page.dossierEvidence.prefix + '-thread.png'});
  }
  if (page.viewportSize().width === 320 && !page.dossierResized) {
    page.dossierResized = true;
    const viewport = page.viewportSize();
    const returnButton = page.locator('#workbench-return');
    const original = await returnButton.elementHandle();
    await returnButton.focus();
    await page.setViewportSize({width: 1440, height: viewport.height});
    await expect(returnButton).toBeFocused();
    assert.equal(await returnButton.evaluate((node, previous) => node === previous, original), true,
      'Resizing retains the same focused return control');
    await expect.poll(() => page.locator('#workbench-thread').evaluate(node => node.parentElement.classList.contains('workspace-shell'))).toBe(true);
    await expect(returnButton).toBeFocused();
    await page.setViewportSize(viewport);
    await expect(returnButton).toBeFocused();
    await expect.poll(() => page.locator('#workbench-thread').evaluate(node => node.parentElement.classList.contains('page'))).toBe(true);
    await expect(returnButton).toBeFocused();
    await expect.poll(() => returnButton.evaluate(node => {
      const box = node.getBoundingClientRect(); return box.top >= 0 && box.bottom <= innerHeight;
    })).toBe(true);
    await original.dispose();
  }
  const dossierReads = page.dossierReads;
  await page.locator('#workbench-return').click();
  await assertReturned(page, control, before, 'Dossier return restores the requesting control and exact scroll position');
  if (page.dossierEvidence && !page.dossierEvidence.returnCaptured) {
    page.dossierEvidence.returnCaptured = true;
    await page.screenshot({path: page.dossierEvidence.prefix + '-return-cue.png'});
  }
  assert.equal(page.dossierReads, dossierReads, 'Returning reuses the accepted dossier without a list/detail refresh');
}

(async () => {
  const browser = await launchChromium();
  try {
    for (const reading of [true, false]) {
      const server = await startNativeServer(fixtureSource(reading), fs.mkdtempSync(path.join(artifacts, reading ? 'reading-' : 'empty-')));
      try {
        const fixture = server.fixture;
        for (const [width, height] of [[1440, 950], [320, 900], [320, 480]]) for (const reducedMotion of reading ? ['reduce', 'no-preference'] : ['reduce']) {
          const page = await browser.newPage({viewport: {width, height}, reducedMotion});
          const errors = [], writes = [];
          page.dossierReads = 0;
          page.dossierEvidence = {prefix: path.join(artifacts, `${reading ? 'reading' : 'empty'}-${width}x${height}-${reducedMotion}`)};
          page.on('pageerror', error => errors.push(error.message));
          page.on('request', request => {
            const url = new URL(request.url());
            if (request.method() === 'POST') writes.push(url.pathname);
            if (url.pathname === '/api/research/dossiers') page.dossierReads++;
          });
          await page.goto(fixture.url);
          await expect(page).toHaveTitle(reading ? /Synthetic native manuscript/ : /No Project Loaded/);
          await page.locator('#tab-view-research').click();
          const summary = page.locator(`[data-research-detail=dossier][data-record-id="${fixture.dossier}"]`);
          await summary.click();
          const detail = summary.locator('..').locator('.research-details-body');
          await expect(detail.locator('.research-dossier-claims-list li')).toHaveCount(1);
          await page.evaluate(() => {
            document.getElementById('r-claim-title').value = 'Unsubmitted claim draft';
            document.getElementById('r-link-rationale').value = 'Unsubmitted evidence rationale';
            document.getElementById('r-decision-title').value = 'Unsubmitted decision draft';
          });
          if (reading) {
            await depart(page, detail.locator('[data-manuscript-links-claim]'), 'review');
            // The retained source quotation and historical dossier pin remain exact.
            await detail.locator('[data-research-history=claim]').click();
            await expect(page.locator('#research-revision-history-detail')).toContainText('The synthetic archive opened in 1924.');
            await expect(page.locator('#workbench-return')).toBeHidden();
            await page.locator('#research-revision-history-detail [data-research-history=dossier]').click();
            await expect(page.locator('#research-revision-history-detail')).toContainText('An original synthetic note.');
            await expect(page.locator('#research-revision-kind')).toHaveText('Dossier · Version 1 · Earlier version');
            await page.keyboard.press('Escape');
            await expect(detail.locator('[data-research-history=claim]')).toBeFocused();
            // A cancelled pending viewer never becomes a dossier departure,
            // and its eventual read cannot publish navigation context.
            let release, held;
            const heldRead = new Promise(resolve => { held = resolve; });
            const recordRoute = '**/api/research/record?*';
            await page.route(recordRoute, async route => {
              const response = await route.fetch(); held();
              await new Promise(resolve => { release = resolve; });
              await route.fulfill({response});
            });
            await detail.locator('[data-research-history=claim]').click();
            await heldRead;
            await page.keyboard.press('Escape');
            release();
            await expect(page.locator('#modal-research-revision')).not.toBeVisible();
            await expect(page.locator('#workbench-return')).toBeHidden();
            await page.unroute(recordRoute);
            // Failed record reads retain the native Close route, with no
            // invented dossier return or source action.
            await page.route(recordRoute, route => route.fulfill({status: 500, json: {ok: false, message: 'Synthetic record read failure'}}));
            await detail.locator('[data-research-history=claim]').click();
            await expect(page.locator('#research-revision-status')).toContainText('Synthetic record read failure');
            await page.keyboard.press('Escape');
            await expect(page.locator('#workbench-return')).toBeHidden();
            await page.unroute(recordRoute);
            // A claim-viewer departure must still return to the initial dossier.
            const openClaim = detail.locator('[data-research-history=claim]');
            await openClaim.focus(); const beforeClaim = await positions(openClaim);
            await openClaim.click();
            await page.locator('#research-revision-history-detail [data-manuscript-links-claim]').click();
            await expect(page.locator('#modal-research-revision')).not.toBeVisible();
            await expect(page.locator('#workbench-return')).toHaveText('Back to dossier');
            await assertReturnAvailable(page);
            await page.locator('#workbench-return').click();
            await assertReturned(page, openClaim, beforeClaim, 'Claim viewer handoff retains its initial dossier origin');
          }
          const actions = detail.locator('.research-dossier-actions');
          if (await actions.getAttribute('open') === null) await actions.locator(':scope > summary').click();
          await depart(page, detail.locator('[data-research-global=claims]'), 'claims');
          await depart(page, detail.locator('[data-research-global=decisions]'), 'decisions');
          await expect(page.locator('#r-claim-title')).toHaveValue('Unsubmitted claim draft');
          await expect(page.locator('#r-link-rationale')).toHaveValue('Unsubmitted evidence rationale');
          await expect(page.locator('#r-decision-title')).toHaveValue('Unsubmitted decision draft');
          // Project/research identity changes invalidate the old dossier
          // immediately, even when its old DOM is still present.
          await detail.locator('[data-research-global=claims]').click();
          await expect(page.locator('#workbench-return')).toHaveText('Back to dossier');
          await assertReturnAvailable(page);
          const researchToken = await page.locator('#research-manager').getAttribute('data-research-token');
          await page.locator('#research-manager').evaluate(node => { node.dataset.researchToken = 'foreign-context'; });
          await expect(page.locator('#workbench-return')).toBeHidden();
          await page.locator('#research-manager').evaluate((node, token) => { node.dataset.researchToken = token; }, researchToken);
          await expect(page.locator('#workbench-return')).toBeHidden();
          if (reading) {
            await page.locator('#tab-view-analysis').click();
            const paragraph = page.locator('#chapters .ptext').filter({hasText: 'A bird crosses'});
            await paragraph.locator('[data-manuscript-links-paragraph]').click();
            await expect(page.locator('[data-passage-research]')).toHaveAttribute('data-state', 'ready');
            await expect(page.locator('#tab-view-analysis')).toHaveAttribute('aria-selected', 'true');
            await expect(page.locator('#workbench-return')).toHaveText('Back to passage');
            await page.locator('#workbench-return').click();
            // Create another passage journey, then detour through a companion dossier.
            await paragraph.locator('[data-manuscript-links-paragraph]').click();
            await page.locator('#tab-view-analysis').click();
            await page.locator('#workspace-reader-toggle').click();
            await expect(page.locator('#workspace-reader-dossier')).toBeEnabled();
            await page.locator('#workspace-reader-dossier').selectOption(fixture.dossier);
            const companion = page.locator('#workspace-reader-body');
            await expect(companion.locator('.research-dossier-claims-list li')).toHaveCount(1);
            await depart(page, companion.locator('[data-manuscript-links-claim]'), 'review');
            await expect(page.locator('#workbench-return')).toHaveText('Back to passage');
            await expect(page.locator('#workspace-reader-panel')).toBeVisible();
            await page.locator('#workbench-return').click();
            await expect(paragraph).toBeFocused();
            await depart(page, companion.locator('[data-research-global=claims]'), 'claims');
            await expect(page.locator('#workspace-reader-dossier')).toHaveValue(fixture.dossier);
            await companion.locator('[data-research-global=decisions]').click();
            await expect(page.locator('#workbench-return')).toHaveText('Back to dossier');
            await assertReturnAvailable(page);
            await page.locator('#tab-view-analysis').click();
            await page.locator('#workspace-reader-close').click();
            await expect(page.locator('#workbench-return')).toBeHidden();
            await page.locator('#workspace-reader-toggle').click();
            await expect(companion.locator('.research-dossier-claims-list li')).toHaveCount(1);
            // A replaced accepted root must never restore a disconnected control.
            await companion.locator('.research-dossier-actions > summary').click();
            await companion.locator('[data-research-global=decisions]').click();
            await expect(page.locator('#workbench-return')).toHaveText('Back to dossier');
            await assertReturnAvailable(page);
            await page.evaluate(() => document.getElementById('workspace-reader-body').replaceChildren());
            await expect(page.locator('#workbench-return')).toBeHidden();
          }
          await expect(page.locator('#workbench-thread')).toBeHidden();
          assert.deepEqual(errors, []);
          assert.deepEqual(writes, [], 'Reading, cancel and returning never publish a research change');
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
          await page.screenshot({path: path.join(artifacts, `${reading ? 'reading' : 'empty'}-${width}x${height}-${reducedMotion}.png`)});
          await page.close();
        }
      } finally { await server.close(); }
    }
    console.log(`Dossier return: exact native dossier/companion origins, prior passage return, pins, drafts, empty manuscripts, ordinary/reduced motion and desktop/mobile passed. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
