// Exercise project selection and research controls against a disposable local server.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn, execFileSync} = require('node:child_process');
const {once} = require('node:events');
const {createInterface} = require('node:readline');
const assert = require('node:assert/strict');
let playwrightMod = process.env.PLAYWRIGHT_MODULE || 'playwright';
try { require.resolve(playwrightMod); } catch {
  const fallback = '/home/codeai/.npm/_npx/b234c773f454f454/node_modules/playwright';
  if (fs.existsSync(fallback)) playwrightMod = fallback;
}
const {chromium} = require(playwrightMod);
const {expect} = require(path.join(playwrightMod, 'test'));
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-research-ui-'));

(async () => {
  const server = spawn(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-u', '-c', `
import json
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
base = Path(sys.argv[1])
project = base / 'existing-novel'
project.mkdir()
(project / 'manuscript.md').write_text('', encoding='utf-8')
(project / 'chapter "quoted" & <draft>.md').write_text('Synthetic filename fixture.', encoding='utf-8')
api.init(project, title='Synthetic research')
research_only = base / 'research-only'
api.init(research_only, title='Synthetic research-only project')
source = base / 'source.txt'
source.write_text('The synthetic archive opened in 1924.', encoding='utf-8')
api.ingest(project, source, allow_retention=True, title='Synthetic source', context={'provenance_note': 'Synthetic fixture, not an archival record.'})
api.reindex(project)
passage = api.search(project, 'archive')['hits'][0]['passage_id']
api.create_dossier(project, title='Synthetic dossier', body='Opening date. ' * 30 + 'End of synthetic dossier.', evidence_ids=[passage])
LixityServerHandler.workspace_root = str(base)
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.language = 'en'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'project': str(project), 'researchOnly': str(research_only), 'passage': passage}), flush=True)
server.serve_forever()
`, artifacts], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, stdio: ['ignore', 'pipe', 'pipe']});
  let stderr = '';
  server.stderr.on('data', data => { stderr += data; });
  const lines = createInterface({input: server.stdout});
  let browser;
  try {
    const fixture = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Fixture startup timed out: ' + stderr)), 15000);
      lines.once('line', line => { clearTimeout(timeout); resolve(JSON.parse(line)); });
      server.once('error', error => { clearTimeout(timeout); reject(error); });
      server.once('exit', code => { clearTimeout(timeout); reject(new Error(`Fixture exited ${code}: ${stderr}`)); });
    });
    const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ||
      (fs.existsSync('/usr/bin/chromium-browser') ? '/usr/bin/chromium-browser' :
       fs.existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);
    browser = await chromium.launch({headless: true, ...(executablePath ? {executablePath} : {})});
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}, hasTouch: true});
    page.setDefaultTimeout(10000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(fixture.url);
    await expect(page.locator('#welcome-hero')).toBeVisible();
    await expect(page.locator('#research-init-box')).toBeVisible();
    assert.equal(await page.locator('.research-tab-pane:visible').count(), 0);
    // Onboarding is optional and never hides the persistent project actions.
    await page.locator('#welcome-dismiss').click();
    await expect(page.locator('#welcome-hero')).not.toBeVisible();
    await expect(page.locator('#btn-modal-open-project')).toBeVisible();
    await expect(page.locator('#btn-modal-new-project')).toBeVisible();
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({width, height: 844});
      await page.reload();
      await page.evaluate(() => scrollTo(0, 0));
      await expect(page.locator('#welcome-hero')).not.toBeVisible();
      assert.ok(await page.locator('.workspace-bar').evaluate(element => {
        const box = element.getBoundingClientRect();
        return box.top >= 0 && box.bottom <= innerHeight && box.right <= innerWidth;
      }), `Collapsed guidance must keep project controls in the first viewport at ${width}px`);
      await expect(page.locator('#welcome-show')).toBeVisible();
      await page.locator('.workspace-bar').screenshot({path: path.join(artifacts, `workspace-actions-${width}.png`)});
    }
    await page.setViewportSize({width: 1440, height: 1000});
    await page.locator('#welcome-show').click();
    await expect(page.locator('#welcome-hero')).toBeVisible();
    assert.equal(await page.locator('#ms-file, #nda-manager, [data-action=export], [data-action=sync], [data-action=gdrive]').count(), 0, 'Standalone UI must expose supported workflows only');
    const noStoragePage = await browser.newPage();
    noStoragePage.on('pageerror', error => errors.push('Blocked storage: ' + error.message));
    await noStoragePage.addInitScript(() => {
      Object.defineProperty(window, 'localStorage', {get() { throw new DOMException('Storage disabled', 'SecurityError'); }});
    });
    await noStoragePage.goto(fixture.url);
    await noStoragePage.locator('#welcome-dismiss').click();
    await expect(noStoragePage.locator('#welcome-hero')).not.toBeVisible();
    await noStoragePage.locator('#welcome-show').click();
    await expect(noStoragePage.locator('#welcome-hero')).toBeVisible();
    await noStoragePage.close();

    // Import is an explicit separate workflow and merely selecting it sends no mutation.
    const mutations = [];
    page.on('request', request => {
      const endpoint = new URL(request.url()).pathname;
      if (request.method() === 'POST' && /\/api\/(project-|research-)/.test(endpoint)) mutations.push(endpoint);
    });
    await page.locator('#btn-modal-open-project').click();
    await expect(page.locator('#modal-project-open')).toBeVisible();
    const openHelp = page.locator('#modal-project-open .help').first();
    await openHelp.focus();
    await expect(page.locator('#modal-project-open #lixity-tooltip')).toBeVisible();
    await expect(page.locator('#lixity-tooltip')).toContainText(/research|archive/i);
    await page.keyboard.press('Escape');
    await expect(page.locator('#lixity-tooltip')).not.toBeVisible();
    await expect(page.locator('#modal-project-open')).toBeVisible();
    await expect(page.locator('#open-proj-choose')).toBeVisible();
    await page.locator('#open-proj-path').fill(fixture.project);
    await page.locator('#open-proj-choose').click();
    await expect(page.locator('#open-project-chooser-path')).toHaveText(fixture.project);
    await expect(page.locator('#open-project-chooser-list button').filter({hasText: 'chapter "quoted" & <draft>.md'})).toBeVisible();
    assert.equal(await page.locator('#open-project-chooser-list draft').count(), 0, 'Filename markup must remain text');
    await page.locator('#open-project-chooser-close').click();
    await expect(page.locator('#open-project-chooser')).not.toBeVisible();
    await expect(page.locator('#open-proj-path')).toHaveValue(fixture.project);
    assert.deepEqual(mutations, [], 'Browsing and cancelling must not change the workspace');
    let finishListing;
    let listingStarted;
    const listingGate = new Promise(resolve => { finishListing = resolve; });
    const listingReady = new Promise(resolve => { listingStarted = resolve; });
    await page.route('**/api/project-paths?*', async route => {
      listingStarted();
      await listingGate;
      await route.fulfill({json: {ok: true, path: '/late-response', parent: '/', entries: [], truncated: false}});
    });
    await page.locator('#open-proj-choose').click();
    await listingReady;
    await page.locator('#open-project-chooser-close').click();
    const listingFinished = page.waitForResponse(response => response.url().includes('/api/project-paths?'));
    finishListing();
    await listingFinished;
    await expect(page.locator('#open-project-chooser')).not.toBeVisible();
    await expect(page.locator('#open-project-chooser-path')).not.toContainText('/late-response');
    await expect(page.locator('#open-proj-path')).toHaveValue(fixture.project);
    await page.unroute('**/api/project-paths?*');
    await page.locator('#link-switch-to-import').click();
    await expect(page.locator('#modal-project-open')).not.toBeVisible();
    await expect(page.locator('#modal-project-create #tab-pane-import')).toBeVisible();
    await page.locator('#import-file-input').setInputFiles({name: 'synthetic.md', mimeType: 'text/markdown', buffer: Buffer.from('## Imported chapter\n\nSynthetic text.')});
    await expect(page.locator('#import-preview-box')).toBeVisible();
    await page.locator('#import-proj-lang').selectOption('fr');
    const dropped = await page.evaluateHandle(() => {
      const transfer = new DataTransfer();
      transfer.items.add(new File(['## Dropped chapter\n\nSynthetic drop content.'], 'dropped.md', {type: 'text/markdown'}));
      return transfer;
    });
    await page.locator('#import-dropzone').dispatchEvent('drop', {dataTransfer: dropped});
    await expect(page.locator('#import-preview-box')).toContainText('dropped.md');
    await expect(page.locator('#import-proj-lang')).toHaveValue('fr');
    assert.deepEqual(mutations, []);
    await page.locator('#import-proj-title').fill('Synthetic import');
    await page.locator('#import-proj-path').fill(fixture.project);
    await page.locator('#btn-submit-import-project').click();
    await expect(page.locator('#import-project-status')).toBeVisible();
    await expect(page.locator('#modal-project-create')).toBeVisible();
    await expect(page.locator('#import-proj-path')).toHaveValue(fixture.project);
    assert.equal(fs.readFileSync(path.join(fixture.project, 'manuscript.md'), 'utf8'), '');
    await page.keyboard.press('Escape');

    // Opening an empty manuscript must attach its existing sibling research archive.
    await page.locator('#btn-modal-open-project').click();
    const missing = path.join(artifacts, 'missing-project');
    await page.locator('#open-proj-path').fill(missing);
    await page.locator('#btn-submit-open-project').click();
    await expect(page.locator('#open-project-status')).toBeVisible();
    await expect(page.locator('#modal-project-open')).toBeVisible();
    await expect(page.locator('#open-proj-path')).toHaveValue(missing);
    // Listing errors preserve the draft and cannot submit an older selection.
    await page.locator('#open-proj-choose').click();
    await expect(page.locator('#open-project-chooser-status')).not.toBeEmpty();
    await expect(page.locator('#open-project-chooser-select-folder')).toBeDisabled();
    await expect(page.locator('#open-proj-path')).toHaveValue(missing);
    await page.locator('#open-project-chooser-close').click();
    await page.locator('#open-proj-path').fill(fixture.project);
    await expect(page.locator('#open-project-status')).not.toBeVisible();
    await page.locator('#open-proj-choose').click();
    await expect(page.locator('#open-project-chooser-path')).toHaveText(fixture.project);
    await page.locator('#modal-project-open').screenshot({path: path.join(artifacts, 'choose-file-desktop.png')});
    await page.locator('#open-project-chooser-list button').filter({hasText: /^.*manuscript\.md$/}).click();
    await expect(page.locator('#open-project-chooser')).not.toBeVisible();
    await expect(page.locator('#open-proj-path')).toHaveValue(path.join(fixture.project, 'manuscript.md'));
    await Promise.all([page.waitForNavigation(), page.locator('#btn-submit-open-project').click()]);
    await expect(page.locator('#r-active-root')).toContainText(fixture.project);
    await expect(page.locator('#research-sources-list')).toContainText('Synthetic source');
    await page.locator('[data-research-detail=source]').click();
    await expect(page.locator('#research-sources-list .research-details-body')).toContainText('Synthetic fixture, not an archival record.');
    await expect(page.locator('#research-sources-list .research-details-body')).toContainText('The synthetic archive opened in 1924.');
    assert.deepEqual(mutations, ['/api/project-create', '/api/project-open', '/api/project-open']);
    assert.equal(fs.readFileSync(path.join(fixture.project, 'manuscript.md'), 'utf8'), '');
    await expect(page.locator('#r-active-root')).toContainText('1 sources, 1 dossiers, 0 claims, 0 decisions');
    await expect(page.locator('#research-init-box')).not.toBeVisible();
    assert.equal(await page.locator('.research-tab-pane:visible').count(), 1);
    const sourceBeforeReopen = await (await page.request.get(fixture.url + '/api/research/sources')).json();
    await page.locator('[data-rtab=grounding]').click();
    await page.locator('#r-ground-source-select').selectOption(sourceBeforeReopen.sources[0].id);
    await page.locator('[data-rtab=sources]').click();
    await expect(page.locator('#r-ground-source-select')).toHaveValue(sourceBeforeReopen.sources[0].id);
    // The folder route selects the same archive as the empty manuscript route.
    await page.locator('#btn-modal-open-project').click();
    await page.locator('#open-proj-path').fill(fixture.project);
    await page.locator('#open-proj-choose').click();
    await expect(page.locator('#open-project-chooser-path')).toHaveText(fixture.project);
    await page.locator('#open-project-chooser-parent').click();
    await expect(page.locator('#open-project-chooser-path')).toHaveText(artifacts);
    await page.locator('#open-project-chooser-list button[data-open-path-kind=directory]').filter({hasText: /^.*existing-novel$/}).click();
    await expect(page.locator('#open-project-chooser-path')).toHaveText(fixture.project);
    await page.locator('#open-project-chooser-select-folder').click();
    await expect(page.locator('#open-proj-path')).toHaveValue(fixture.project);
    await Promise.all([page.waitForNavigation(), page.locator('#btn-submit-open-project').click()]);
    await expect(page.locator('#modal-project-open')).not.toBeVisible();
    await expect(page.locator('#r-active-root')).toContainText(fixture.project);
    const sourceAfterReopen = await (await page.request.get(fixture.url + '/api/research/sources')).json();
    assert.deepEqual(sourceAfterReopen.sources, sourceBeforeReopen.sources);
    await page.locator('[data-rtab=dossiers]').click();
    await expect(page.locator('#research-dossiers-list')).toContainText('Synthetic dossier');
    await page.locator('[data-research-detail=dossier]').click();
    await expect(page.locator('#research-dossiers-list .research-details-body')).toContainText('End of synthetic dossier.');
    await expect(page.locator('#research-dossiers-list .research-details-body')).toContainText('The synthetic archive opened in 1924.');
    const dossiers = await (await page.request.get(fixture.url + '/api/research/dossiers')).json();
    await page.locator('[data-rtab=claims]').click();
    await expect(page.locator('#research-claims-list')).toContainText('No claims yet');
    const claimTitle = 'Archive <img src=x onerror=alert(1)> "opening"';
    await page.locator('#r-claim-title').fill(claimTitle);
    await page.locator('#r-claim-statement').fill('The synthetic archive opened in 1924.');
    await page.locator('#r-claim-time').fill('1924');
    await page.locator('#r-claim-place').fill('Synthetic town');
    await page.locator('#r-claim-actors').fill('Archivist, Reader');
    await page.locator('#r-claim-dossier-select').selectOption(dossiers.dossiers[0].id);
    await page.locator('#r-claim-create-btn').click();
    await expect(page.locator('#research-claims-list')).toContainText(claimTitle);
    assert.equal(await page.locator('#research-claims-list img').count(), 0);
    const claims = await (await page.request.get(fixture.url + '/api/research/claims')).json();
    assert.equal(claims.claims.length, 1);
    const claimId = claims.claims[0].id;
    assert.deepEqual(claims.claims[0].scope.actors, ['Archivist', 'Reader']);
    assert.equal(claims.claims[0].dossier_id, dossiers.dossiers[0].id);
    await expect(page.locator('#r-active-root')).toContainText('1 claims');
    await page.locator('#r-link-claim-select').selectOption(claimId);
    await page.locator('[data-rtab=search]').click();
    await page.locator('#r-search-query').fill('archive');
    await page.locator('#r-search-btn').click();
    await page.locator('#research-search-results [data-use-passage=claim]').click();
    await expect(page.locator('#rtab-claims')).toBeVisible();
    await expect(page.locator('#r-link-passage-id')).toHaveValue(fixture.passage);
    await expect(page.locator('#r-link-claim-select')).toHaveValue(claimId);
    await page.locator('#r-link-rationale').fill('Synthetic source supports this date.');
    await page.locator('#r-link-evidence-btn').click();
    await expect(page.locator('#research-status-bar')).toContainText('Evidence linked');
    await page.locator('[data-load-evidence]').click();
    await expect(page.locator('.claim-evidence-subpanel')).toContainText('The synthetic archive opened in 1924.');
    await page.locator('#research-manager').screenshot({path: path.join(artifacts, 'claims-desktop.png')});

    await page.locator('[data-rtab=search]').click();
    await page.locator('#research-search-results [data-use-passage=dossier]').click();
    await expect(page.locator('#rtab-dossiers')).toBeVisible();
    await expect(page.locator('#r-dos-eids')).toHaveValue(fixture.passage);
    await page.locator('[data-rtab=search]').click();
    await page.locator('#research-search-results [data-use-passage=dossier]').click();
    await expect(page.locator('#r-dos-eids')).toHaveValue(fixture.passage);
    await page.locator('#r-dos-title').fill('Linked search note');
    await page.locator('#r-dos-body').fill('A dossier assembled from a selected passage.');
    await page.locator('#r-dos-create-btn').click();
    await expect(page.locator('#research-dossiers-list')).toContainText('Linked search note');
    await expect(page.locator('#r-active-root')).toContainText('2 dossiers');

    await page.locator('[data-rtab=decisions]').click();
    await expect(page.locator('#research-decisions-list')).toContainText('No decisions yet');
    await page.locator('#r-decision-title').fill('Move the date');
    await page.locator('#r-decision-rationale').fill('Bring the opening into the first chapter.');
    await page.locator('#r-decision-plot').fill('Earlier meeting.');
    await page.locator('#r-decision-claim-select').selectOption(claimId);
    // Inspect evidence while drafting; the selected claim must survive a tab refresh.
    await page.locator('[data-rtab=claims]').click();
    await expect(page.locator('#research-claims-list')).toContainText(claimTitle);
    await page.locator('[data-rtab=decisions]').click();
    await expect(page.locator('#r-decision-claim-select')).toHaveValue(claimId);
    const deviationHelp = page.locator('label:has(#r-decision-deviation) .help');
    await deviationHelp.tap();
    await expect(page.locator('#lixity-tooltip')).toBeVisible();
    await expect(page.locator('#lixity-tooltip')).toContainText('does not certify factual accuracy');
    await expect(page.locator('#r-decision-deviation')).not.toBeChecked();
    await deviationHelp.tap();
    await expect(page.locator('#lixity-tooltip')).not.toBeVisible();
    await expect(page.locator('#r-decision-deviation')).not.toBeChecked();
    await page.locator('#r-decision-deviation').check();
    await page.locator('#r-decision-create-btn').click();
    await expect(page.locator('#research-decisions-list')).toContainText('Move the date');
    await expect(page.locator('#research-decisions-list')).toContainText('Earlier meeting.');
    await expect(page.locator('#research-decisions-list')).toContainText(claimId);
    const decisions = await (await page.request.get(fixture.url + '/api/research/decisions')).json();
    assert.equal(decisions.decisions[0].claim_id, claimId);
    assert.equal(decisions.decisions[0].deviation_from_fact, true);
    await expect(page.locator('#r-active-root')).toContainText('1 decisions');
    await page.locator('#research-manager').screenshot({path: path.join(artifacts, 'decisions-desktop.png')});
    await page.locator('#r-decision-title').fill('General artistic choice');
    await page.locator('#r-decision-rationale').fill('Use a quieter opening.');
    await page.locator('#r-decision-claim-select').selectOption('');
    await page.locator('#r-decision-create-btn').click();
    const generalDecision = page.locator('#research-decisions-list .research-card').filter({hasText: 'General artistic choice'});
    await expect(generalDecision).toBeVisible();
    assert.equal(await generalDecision.locator('.badge-success').count(), 0, 'No marked deviation is not factual certification');
    await expect(generalDecision.locator('.badge-neutral')).toBeVisible();

    // Revise existing authored records through the same UI without duplicating them.
    const dossierId = dossiers.dossiers[0].id;
    const revisionDialog = page.locator('#modal-research-revision');
    const field = name => page.locator(`#research-revision-field-${name}`);
    const chooseChange = async (kind = 'correction') => {
      await page.locator(`[name=research_revision_change_kind][value=${kind}]`).check();
      await page.locator('#research-revision-reason').fill('Synthetic author review.');
    };
    await page.locator('[data-rtab=dossiers]').click();
    await page.locator(`[data-research-revise=dossier][data-record-id="${dossierId}"]`).click();
    await expect(field('body')).toHaveValue(/End of synthetic dossier\./);
    await field('title').fill('Revised synthetic dossier');
    const revisedBody = 'A revised note with **important bold** and <img src=x onerror=alert(1)> as inert text.\n\n| Year | Event |\n| :--- | :--- |\n| 1924 | Opening |\n\n```mermaid\ngraph TD\n  A[Start] --> B[Finish]\n```\n\n[internal](lixity:dossier/test-ref) and [bad](javascript:alert(1))';
    await field('body').fill(revisedBody);
    await chooseChange();
    assert.ok((await field('body').boundingBox()).height >= 150, 'Dossier body editor must have usable height');
    assert.ok((await page.locator('#research-revision-reason').boundingBox()).height >= 65, 'Revision reason must have usable height');
    await field('title').scrollIntoViewIfNeeded();
    await revisionDialog.screenshot({path: path.join(artifacts, 'revision-dossier-desktop.png')});
    await page.locator('#research-revision-reason').scrollIntoViewIfNeeded();
    await revisionDialog.screenshot({path: path.join(artifacts, 'revision-dossier-reason-desktop.png')});
    await page.locator('#research-revision-save').click();
    await expect(revisionDialog).not.toBeVisible();
    await expect(page.locator('#research-dossiers-list')).toContainText('Revised synthetic dossier');
    assert.equal((await (await page.request.get(fixture.url + '/api/research/dossiers')).json()).dossiers.length, 2);
    await page.locator(`[data-research-history=dossier][data-record-id="${dossierId}"]`).click();
    await page.locator('[data-research-revision="1"]').click();
    await expect(page.locator('#research-revision-history-detail')).toContainText('End of synthetic dossier.');
    await page.locator('#research-revision-history-detail').scrollIntoViewIfNeeded();
    await revisionDialog.screenshot({path: path.join(artifacts, 'revision-dossier-history-desktop.png')});
    await page.locator('[data-research-revision="2"]').click();
    await expect(page.locator('#research-revision-history-detail')).toContainText('<img src=x onerror=alert(1)>');
    assert.equal(await page.locator('#research-revision-history-detail img').count(), 0);
    await expect(page.locator('#research-revision-history-detail strong')).toContainText('important bold');
    await expect(page.locator('#research-revision-history-detail table.research-table')).toBeVisible();
    await expect(page.locator('#research-revision-history-detail svg.research-diagram')).toBeVisible();
    await expect(page.locator('#research-revision-history-detail .rd-node text')).toContainText(['Start', 'Finish']);
    await expect(page.locator('#research-revision-history-detail code.lixity-ref')).toContainText('internal (dossier/test-ref)');
    assert.equal(await page.locator('#research-revision-history-detail a[href*="javascript"]').count(), 0);
    await page.locator('#research-revision-history-detail [data-source-toggle]').click();
    await expect(page.locator('#research-revision-history-detail .research-dossier-body-source')).toBeVisible();
    await expect(page.locator('#research-revision-history-detail .research-dossier-body-rendered')).toBeHidden();
    await page.locator('#research-revision-history-detail [data-source-toggle]').click();
    await expect(page.locator('#research-revision-history-detail .research-dossier-body-source')).toBeHidden();
    await expect(page.locator('#research-revision-history-detail .research-dossier-body-rendered')).toBeVisible();
    await page.keyboard.press('Escape');

    // Stale drafts and failed requests remain editable, with an explicit reload.
    await page.locator(`[data-research-revise=dossier][data-record-id="${dossierId}"]`).click();
    await field('title').fill('My unsaved draft');
    await chooseChange();
    await page.locator('#research-revision-history-tab').click();
    await expect(page.locator('[data-research-revision="2"]')).toContainText('Current');
    await page.locator('#research-revision-edit-tab').click();
    const concurrent = await (await page.request.get(fixture.url + `/api/research/record?kind=dossier&id=${encodeURIComponent(dossierId)}`)).json();
    const concurrentResult = await page.request.post(fixture.url + '/api/research-record-revise', {data: {
      kind: 'dossier', id: dossierId, changes: {title: 'Other editor title'},
      expected_snapshot: concurrent.snapshot, expected_revision: concurrent.record.revision,
      change_kind: 'correction', reason: 'Synthetic concurrent edit.'
    }});
    assert.equal(concurrentResult.status(), 200);
    await page.locator('#research-revision-save').click();
    await expect(page.locator('#research-revision-status')).toContainText('changed');
    await expect(field('title')).toHaveValue('My unsaved draft');
    await expect(page.locator('#research-revision-reload')).toBeVisible();
    await page.locator('#research-revision-reload').click();
    await expect(field('title')).toHaveValue('Other editor title');
    await page.locator('#research-revision-history-tab').click();
    await expect(page.locator('[data-research-revision="3"]')).toContainText('Current');
    await expect(page.locator('[data-research-revision="2"]')).not.toContainText('Current');
    await page.locator('#research-revision-edit-tab').click();
    await field('title').fill('Failed request draft');
    await chooseChange();
    let requestStarted;
    const started = new Promise(resolve => { requestStarted = resolve; });
    let releaseResponse;
    const heldResponse = new Promise(resolve => { releaseResponse = resolve; });
    await page.route('**/api/research-record-revise', async route => {
      requestStarted();
      await heldResponse;
      await route.fulfill({status: 500, json: {ok: false, message: 'Synthetic revision save failure'}});
    });
    await page.locator('#research-revision-save').click();
    await started;
    await expect(field('title')).toBeDisabled();
    await expect(page.locator('#research-revision-reason')).toBeDisabled();
    await expect(page.locator('[name=research_revision_change_kind]').first()).toBeDisabled();
    releaseResponse();
    await expect(page.locator('#research-revision-status')).toContainText('Synthetic revision save failure');
    await expect(field('title')).toHaveValue('Failed request draft');
    await expect(field('title')).toBeEnabled();
    await page.unroute('**/api/research-record-revise');
    await page.keyboard.press('Escape');
    await page.locator(`[data-research-revise=dossier][data-record-id="${dossierId}"]`).click();
    await expect(field('title')).toHaveValue('Other editor title');
    await page.keyboard.press('Escape');

    await page.route('**/api/research/record?*', route => route.fulfill({status: 500, json: {ok: false, message: 'Synthetic initial history failure'}}));
    await page.locator(`[data-research-history=dossier][data-record-id="${dossierId}"]`).click();
    await expect(page.locator('#research-revision-status')).toBeVisible();
    await expect(page.locator('#research-revision-status')).toContainText('Synthetic initial history failure');
    await page.keyboard.press('Escape');
    await page.unroute('**/api/research/record?*');

    await page.locator('[data-rtab=claims]').click();
    await page.locator(`[data-research-revise=claim][data-record-id="${claimId}"]`).click();
    await field('statement').fill('The archive possibly opened in 1924.');
    await chooseChange();
    await page.locator('#research-revision-save').click();
    await expect(revisionDialog).not.toBeVisible();
    await page.locator('[data-load-evidence]').click();
    const evidenceData = await (await page.request.get(fixture.url + `/api/research/claims?claim_id=${encodeURIComponent(claimId)}`)).json();
    const evidenceId = evidenceData.evidence_links[0].id;
    assert.equal(evidenceData.evidence_links[0].claim_revision, 1);
    assert.equal(evidenceData.evidence_links[0].claim_latest_revision, 2);
    await page.locator(`[data-research-revise=evidence_link][data-record-id="${evidenceId}"]`).click();
    await field('relation').selectOption('qualifies');
    await field('claim_revision').fill('2');
    await field('rationale').fill('The revised statement needs a qualification.');
    await chooseChange();
    await page.locator('#research-revision-save').click();
    await expect(revisionDialog).not.toBeVisible();
    const revisedLink = await (await page.request.get(fixture.url + `/api/research/record?kind=evidence_link&id=${encodeURIComponent(evidenceId)}`)).json();
    const originalLink = await (await page.request.get(fixture.url + `/api/research/record?kind=evidence_link&id=${encodeURIComponent(evidenceId)}&revision=1`)).json();
    assert.equal(revisedLink.record.claim_ref.revision, 2);
    assert.equal(originalLink.record.claim_ref.revision, 1);
    await page.locator(`[data-research-history=claim][data-record-id="${claimId}"]`).click();
    await expect(page.locator('#research-revision-history-detail')).toContainText(evidenceId);
    await expect(page.locator('#research-revision-history-detail')).toContainText('Claim · Revision 2');
    await page.keyboard.press('Escape');
    await page.locator('[data-rtab=decisions]').click();
    const decisionId = decisions.decisions[0].id;
    await page.locator(`[data-research-revise=decision][data-record-id="${decisionId}"]`).click();
    await field('rationale').fill('Supersede the earlier narrative choice.');
    await field('deviation_from_fact').uncheck();
    await chooseChange('supersession');
    await page.locator('#research-revision-save').click();
    await expect(revisionDialog).not.toBeVisible();
    const revisedDecision = await (await page.request.get(fixture.url + `/api/research/record?kind=decision&id=${encodeURIComponent(decisionId)}`)).json();
    assert.equal(revisedDecision.record.change.change_kind, 'supersession');
    assert.equal(revisedDecision.record.deviation_from_fact, false);
    assert.equal((await (await page.request.get(fixture.url + '/api/research/decisions')).json()).decisions.length, 2);

    // New source bytes do not rewrite the dossier or replace its old quotation.
    execFileSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c',
      'import sys; from pathlib import Path; from lixity.research import api; p=Path(sys.argv[1]); source=api.list_sources(p)["sources"][0]; f=p.parent/"source-refresh.txt"; f.write_text("The synthetic archive date is disputed.",encoding="utf-8"); api.ingest(p,f,source_id=source["id"],allow_retention=True)',
      fixture.project], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}});
    await page.locator('[data-rtab=dossiers]').click();
    await page.locator(`[data-research-revise=dossier][data-record-id="${dossierId}"]`).click();
    await expect(page.locator('#research-revision-source-updates')).toBeVisible();
    await expect(page.locator('#research-revision-source-updates')).toContainText('Synthetic source');
    await expect(field('body')).toHaveValue(revisedBody);
    await page.setViewportSize({width: 390, height: 844});
    assert.ok(await revisionDialog.evaluate(element => element.scrollWidth <= element.clientWidth));
    await revisionDialog.screenshot({path: path.join(artifacts, 'revision-dossier-mobile.png')});
    await page.keyboard.press('Escape');
    await page.setViewportSize({width: 1440, height: 1000});

    await page.route('**/api/research/decisions', route => route.fulfill({status: 500, json: {ok: false, message: 'Synthetic decision load failure'}}));
    await page.locator('[data-rtab=decisions]').click();
    await expect(page.locator('#research-decisions-list')).toContainText('Synthetic decision load failure');
    assert.equal(await page.locator('#research-decisions-list .research-card').count(), 0);
    await page.unroute('**/api/research/decisions');

    await page.route('**/api/research-search', route => route.fulfill({status: 500, json: {ok: false, message: 'Synthetic search failure'}}));
    await page.locator('[data-rtab=search]').click();
    await page.locator('#r-search-btn').click();
    await expect(page.locator('#research-search-results')).toContainText('Synthetic search failure');
    await expect(page.locator('#research-status-bar.err')).toContainText('Synthetic search failure');
    await page.unroute('**/api/research-search');
    await page.route('**/api/research-compare', route => route.fulfill({status: 500, json: {ok: false, message: 'Synthetic comparison failure'}}));
    await page.locator('[data-rtab=grounding]').click();
    await page.locator('#r-ground-source-select').selectOption(sourceAfterReopen.sources[0].id);
    await page.locator('#r-ground-btn').click();
    await expect(page.locator('#research-grounding-results')).toContainText('Synthetic comparison failure');
    await expect(page.locator('#research-status-bar.err')).toContainText('Synthetic comparison failure');
    await page.unroute('**/api/research-compare');

    // An unavailable status must not expose ingest controls or imply an empty archive.
    await page.route('**/api/research/status', route => route.fulfill({status: 500, json: {ok: false, message: 'Synthetic archive unavailable'}}));
    await page.reload();
    await expect(page.locator('#research-status-bar')).toContainText('Synthetic archive unavailable');
    await expect(page.locator('#research-init-box')).not.toBeVisible();
    await expect(page.locator('#research-tabs')).not.toBeVisible();
    assert.equal(await page.locator('.research-tab-pane:visible').count(), 0, 'Unavailable research must hide all tab panes');
    await page.unroute('**/api/research/status');
    await page.reload();
    await expect(page.locator('#research-tabs')).toBeVisible();

    for (const width of [390, 320]) {
      await page.setViewportSize({width, height: 844});
      for (const tab of ['sources', 'claims', 'decisions']) {
        await page.locator(`[data-rtab=${tab}]`).click();
        await expect(page.locator(`#rtab-${tab}`)).toBeVisible();
        assert.equal(await page.locator('.research-tab-pane:visible').count(), 1);
        await page.locator('#research-manager').screenshot({path: path.join(artifacts, `${tab}-${width}.png`)});
        const overflow = await page.locator('#research-manager *').evaluateAll(elements => elements.filter(element => element.getBoundingClientRect().right > innerWidth).map(element => ({tag: element.tagName, id: element.id, width: element.getBoundingClientRect().width})).slice(0, 12));
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Research ${tab} overflows at ${width}px: ${JSON.stringify(overflow)}; ${artifacts}`);
      }
    }
    // Presentation language changes labels, not archive identity or stored text.
    const sourceTabs = {en: 'Sources', de: 'Quellen', fr: 'Sources', es: 'Fuentes', it: 'Fonti', pt: 'Fontes', nl: 'Bronnen'};
    for (const [language, sourcesLabel] of Object.entries(sourceTabs)) {
      const response = await page.request.post(fixture.url + '/api/settings', {data: {language}});
      assert.equal((await response.json()).ok, true);
      await page.reload();
      await expect(page.locator('html')).toHaveAttribute('lang', language);
      await expect(page.locator('[data-rtab=sources]')).toHaveText(sourcesLabel);
      if (language === 'de') {
        await page.locator('[data-rtab=grounding]').click();
        await page.locator('#r-ground-source-select').selectOption(sourceAfterReopen.sources[0].id);
        await page.locator('#r-ground-btn').click();
        await expect(page.locator('.research-comparison-warning')).toContainText('Unterschiedliche Sprachprofile');
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      }
      for (const tab of ['sources', 'claims', 'decisions']) {
        await page.locator(`[data-rtab=${tab}]`).click();
        await expect(page.locator(`#rtab-${tab}`)).toBeVisible();
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${language} ${tab} mobile overflow`);
      }
      await page.locator('#research-manager').screenshot({path: path.join(artifacts, `locale-${language}-320.png`)});
      await page.locator(`[data-research-history=decision][data-record-id="${decisionId}"]`).click();
      await page.locator('[data-research-revision="1"]').click();
      await expect(page.locator('#research-revision-history-detail')).toContainText('Bring the opening into the first chapter.');
      assert.ok(await revisionDialog.evaluate(element => element.scrollWidth <= element.clientWidth), `${language} revision history overflow`);
      await page.locator('#research-revision-history-detail').scrollIntoViewIfNeeded();
      await revisionDialog.screenshot({path: path.join(artifacts, `history-${language}-320.png`)});
      await page.keyboard.press('Escape');
      if (language === 'en') {
        await page.locator(`[data-research-revise=decision][data-record-id="${decisionId}"]`).click();
        await expect(page.locator('#research-revision-field-rationale')).toBeVisible();
        assert.ok((await page.locator('#research-revision-reason').boundingBox()).height >= 65, 'Mobile revision reason must have usable height');
        await page.locator('#research-revision-field-title').scrollIntoViewIfNeeded();
        await revisionDialog.screenshot({path: path.join(artifacts, 'revision-decision-top-320.png')});
        await page.locator('#research-revision-reason').scrollIntoViewIfNeeded();
        await revisionDialog.screenshot({path: path.join(artifacts, 'revision-decision-reason-320.png')});
        await page.keyboard.press('Escape');
      }
      await page.locator('#btn-modal-open-project').click();
      await expect(page.locator('#open-proj-path')).toBeVisible();
      await page.locator('#open-proj-path').fill(fixture.project);
      await page.locator('#open-proj-choose').click();
      await expect(page.locator('#open-project-chooser-path')).toHaveText(fixture.project);
      assert.ok(await page.locator('#modal-project-open').evaluate(element => element.scrollWidth <= element.clientWidth), `${language} chooser mobile overflow`);
      await page.locator('#modal-project-open').screenshot({path: path.join(artifacts, `open-${language}-320.png`)});
      await page.locator('#link-switch-to-import').click();
      await expect(page.locator('#import-dropzone')).toBeVisible();
      await page.locator('#modal-project-create').screenshot({path: path.join(artifacts, `import-${language}-320.png`)});
      await page.keyboard.press('Escape');
    }
    // Lifecycle states come from the real archive API, not invented response shapes.
    const sourceData = await (await page.request.get(fixture.url + '/api/research/sources')).json();
    const sourceId = sourceData.sources[0].id;
    for (const operation of ['withdraw', 'purge']) {
      execFileSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c',
        'import sys; from lixity.research import api; getattr(api, sys.argv[3])(sys.argv[1], source_id=sys.argv[2], reason="Synthetic browser lifecycle test")',
        fixture.project, sourceId, operation], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}});
      await page.locator('[data-rtab=claims]').click();
      await page.locator('[data-load-evidence]').click();
      await expect(page.locator('.claim-evidence-subpanel .badge-warning')).toBeVisible();
      if (operation === 'withdraw') {
        await expect(page.locator('.claim-evidence-subpanel')).toContainText('The synthetic archive opened in 1924.');
      } else {
        await expect(page.locator('.claim-evidence-subpanel')).not.toContainText('The synthetic archive opened in 1924.');
      }
    }
    // Folder selection also supports an archive with no manuscript at all.
    await page.locator('#btn-modal-open-project').click();
    await page.locator('#open-proj-path').fill(fixture.researchOnly);
    await page.locator('#open-proj-choose').click();
    await expect(page.locator('#open-project-chooser-path')).toHaveText(fixture.researchOnly);
    await page.locator('#open-project-chooser-select-folder').click();
    await Promise.all([page.waitForNavigation(), page.locator('#btn-submit-open-project').click()]);
    await expect(page.locator('#r-active-root')).toContainText(fixture.researchOnly);
    await expect(page.locator('#research-init-box')).not.toBeVisible();
    assert.equal((await (await page.request.get(fixture.url + '/api/research/status')).json()).initialized, true);
    assert.equal(fs.existsSync(path.join(fixture.researchOnly, 'manuscript.md')), false);
    // Scratch creation, optional research initialization and explicit byte import
    // have distinct results and leave previously opened archives unchanged.
    await page.setViewportSize({width: 1440, height: 1000});
    await page.locator('#btn-modal-new-project').click();
    await page.locator('#tab-btn-scratch').click();
    const scratchProject = path.join(artifacts, 'scratch-project');
    await page.locator('#new-proj-title').fill('Synthetic new project');
    await page.locator('#new-proj-path').fill(scratchProject);
    await page.locator('#new-proj-lang').selectOption('en');
    await Promise.all([page.waitForNavigation(), page.locator('#btn-submit-create-project').click()]);
    await expect(page.locator('#welcome-hero')).not.toBeVisible();
    await expect(page.locator('#welcome-show')).toBeVisible();
    await page.locator('#welcome-show').click();
    await expect(page.locator('#welcome-hero')).toBeVisible();
    await page.locator('#welcome-dismiss').click();
    await expect(page.locator('#research-init-box')).toBeVisible();
    await page.locator('#r-init-title').fill('Scratch research');
    await page.locator('#r-init-btn').click();
    await expect(page.locator('#research-tabs')).toBeVisible();
    await page.locator('#r-ingest-title').fill('Scratch source');
    await page.locator('#r-ingest-text').fill('A synthetic source for a new local project.');
    await page.locator('#r-ingest-retention').check();
    await page.locator('#r-ingest-btn').click();
    await expect(page.locator('#research-sources-list')).toContainText('Scratch source');
    await expect(page.locator('#r-active-root')).toContainText(scratchProject);
    const importedProject = path.join(artifacts, 'imported-project');
    const importedText = '## Imported chapter\n\nA synthetic imported manuscript.';
    await page.locator('#btn-modal-new-project').click();
    await page.locator('#tab-btn-import').click();
    await page.locator('#import-file-input').setInputFiles({name: 'synthetic.md', mimeType: 'text/markdown', buffer: Buffer.from(importedText)});
    await page.locator('#import-proj-title').fill('Explicit byte import');
    await page.locator('#import-proj-path').fill(importedProject);
    await Promise.all([page.waitForNavigation(), page.locator('#btn-submit-import-project').click()]);
    assert.equal(fs.readFileSync(path.join(importedProject, 'manuscript.md'), 'utf8'), importedText);
    assert.equal((await (await page.request.get(fixture.url + '/api/research/status')).json()).initialized, false);
    assert.equal(fs.existsSync(path.join(scratchProject, 'research', 'HEAD.json')), true);
    assert.equal(fs.readFileSync(path.join(fixture.project, 'manuscript.md'), 'utf8'), '');
    assert.deepEqual(errors, []);
    console.log(`Research: file/folder open, import and error recovery, source/dossier details, claims/evidence/decisions, purge history, seven locales and desktop/mobile layout passed. Screenshots: ${artifacts}`);
  } finally {
    if (browser) await browser.close();
    lines.close();
    if (server.exitCode === null) {
      const exited = once(server, 'exit');
      server.kill();
      await exited;
    }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
