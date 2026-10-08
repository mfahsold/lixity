const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
// Exercise project selection and research controls against a disposable local server.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn, execFileSync} = require('node:child_process');
const {once} = require('node:events');
const {createInterface} = require('node:readline');
const assert = require('node:assert/strict');
const {expect} = require(path.join(playwrightModule, 'test'));
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
    browser = await launchChromium();
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
    assert.equal(await page.locator('#ms-file, [data-action=export], [data-action=sync], [data-action=gdrive]').count(), 0, 'Native UI must expose supported workflows only');
    assert.equal(await page.locator('#nda-draft-form').count(), 1, 'The empty native workspace advertises stateless NDA generation');
    assert.equal(await page.locator('#nda-draft-form input, #nda-draft-form textarea').count(), 5);
    assert.equal(await page.locator('#nda-project-name').inputValue(), '', 'An unloaded project has no inferred NDA name');
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
    await page.locator('#import-project-options').evaluate(element => {element.open = true;});
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
    await page.locator('#tab-view-analysis').click();
    const consistencyTile = page.locator('.kpi').filter({has: page.locator('[data-help]')}).filter({hasText: 'Consistency'}).first();
    await expect(consistencyTile).toContainText('–');
    assert.equal(await consistencyTile.locator('.kpi-bar').count(), 0);
    await page.locator('#tab-view-research').click();
    await expect(page.locator('#research-sources-list')).toContainText('Synthetic source');
    await expect(page.locator('#zotero-box')).toBeVisible();
    let zoteroCapture = null;
    const zoteroWarning = 'Synthetic OCR fallback: <img src=x onerror=alert(1)> review native text.';
    await page.route('**/api/research-zotero*', async route => {
      const payload = route.request().postDataJSON();
      assert.ok(payload.project_id.startsWith('urn:uuid:'));
      assert.equal(payload.library, 'users/0');
      if (route.request().url().endsWith('-ingest')) {
        zoteroCapture = payload;
        await route.fulfill({json: {ok: true, passages: 1, warnings: [zoteroWarning]}});
      } else if (payload.mode === 'collections') {
        await route.fulfill({json: {ok: true, collections: [{key: 'STUVWXYZ', data: {name: 'Synthetic collection'}}], next_start: null}});
      } else {
        const item = {key: 'ABCDEFGH', version: 1, data: {itemType: 'book', title: '<img src=x onerror=alert(1)> Synthetic Zotero'}};
        const attachments = [{key:'JKLMNPQR', version: 1, data: {itemType:'attachment', title:'Synthetic text', contentType:'text/plain', linkMode:'imported_file'}},
          {key:'23456789', version:1, data:{itemType:'attachment', title:'Synthetic audio', contentType:'audio/wav', linkMode:'imported_file'}}];
        await route.fulfill({json: {ok:true, server_id:'synthetic-instance', next_start:null, captures:[],
          ...(payload.item_key ? {item, attachments} : {items:[item]})}});
      }
    });
    await page.locator('#r-zotero-collections').click();
    await expect(page.locator('#r-zotero-collection')).toContainText('Synthetic collection');
    await page.locator('#r-zotero-collection').selectOption('STUVWXYZ');
    await page.locator('#r-zotero-browse').click();
    await expect(page.locator('#r-zotero-results')).toContainText('<img src=x onerror=alert(1)>');
    assert.equal(await page.locator('#r-zotero-results img').count(), 0);
    await page.locator('[data-zotero-item]').click();
    await expect(page.locator('#r-zotero-results')).toContainText('Synthetic audio');
    assert.equal(await page.locator('[data-zotero-capture]').count(), 1);
    await page.locator('[data-zotero-capture]').click();
    assert.equal(zoteroCapture, null, 'Capture must require explicit retention');
    for (const width of [1440,390]) {
      await page.setViewportSize({width,height:1000});
      await page.locator('#zotero-box').scrollIntoViewIfNeeded();
      await page.locator('#zotero-box').screenshot({path:path.join(artifacts, `zotero-${width}.png`)});
      assert.ok(await page.locator('#zotero-box').evaluate(e => e.getBoundingClientRect().right <= innerWidth));
    }
    await page.locator('#r-zotero-retention').check();
    await page.locator('[data-zotero-capture]').click();
    await expect(page.locator('#r-zotero-retention')).not.toBeChecked();
    await expect(page.locator('#research-status-bar.ok')).toContainText(zoteroWarning);
    assert.equal(await page.locator('#research-status-bar img').count(), 0, 'Warning markup must remain text');
    for (const width of [1440, 390]) {
      await page.setViewportSize({width, height: 1000});
      await page.locator('#research-status-bar').screenshot({path: path.join(artifacts, `zotero-warning-${width}.png`)});
      assert.ok(await page.locator('#research-status-bar').evaluate(e => e.getBoundingClientRect().right <= innerWidth));
    }
    assert.equal(zoteroCapture.attachment_key, 'JKLMNPQR');
    assert.equal(zoteroCapture.expected_server_id, 'synthetic-instance');
    assert.equal(zoteroCapture.allow_retention, true);
    await page.unroute('**/api/research-zotero*');
    await page.setViewportSize({width:1440,height:1000});

    await page.locator('[data-research-detail=source]').click();
    await expect(page.locator('#research-sources-list .research-details-body')).toContainText('Synthetic fixture, not an archival record.');
    await expect(page.locator('#research-sources-list .research-details-body')).toContainText('The synthetic archive opened in 1924.');
    assert.deepEqual(mutations, ['/api/project-create', '/api/project-open', '/api/project-open',
      '/api/research-zotero', '/api/research-zotero', '/api/research-zotero',
      '/api/research-zotero-ingest', '/api/research-zotero']);
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
    await page.locator('#tab-view-research').click();
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
    await page.locator('#r-claim-options > summary').click();
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
    await page.locator('#r-search-scope').selectOption('dossiers');
    await page.locator('#r-search-query').fill('Opening');
    await page.locator('#r-search-btn').click();
    await expect(page.locator('#research-search-results')).toContainText('Synthetic dossier');
    await expect(page.locator('#research-search-results')).toContainText('Saved version 1');
    assert.equal(await page.locator('#research-search-results [data-use-passage]').count(), 0);
    await page.locator('#research-search-results [data-research-history]').click();
    await expect(page.locator('#modal-research-revision')).toBeVisible();
    await expect(page.locator('#modal-research-revision')).toContainText('End of synthetic dossier.');
    await page.locator('#modal-research-revision [data-close-modal]').first().click();
    for (const width of [1440, 390]) {
      await page.setViewportSize({width, height: 900});
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.locator('#rtab-search').screenshot({path: path.join(artifacts, `search-records-${width}.png`)});
    }
    await page.setViewportSize({width: 1440, height: 1000});
    await page.locator('#r-search-scope').selectOption('sources');
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
      await expect(page.locator(`[id="claim-evidence-${claimId}"]`)).toContainText('The synthetic archive opened in 1924.');
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
    await page.locator('#r-decision-options > summary').click();
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

    // Editorial maintenance is a read-only view of explicit associations.
    const impactChoiceId = decisions.decisions[0].id;
    const recordBeforeReview = await (await page.request.get(fixture.url + `/api/research/record?kind=decision&id=${encodeURIComponent(impactChoiceId)}`)).json();
    assert.equal((await page.request.get(fixture.url + '/api/research/decision-impact')).status(), 400);
    const impactReport = await (await page.request.get(fixture.url + `/api/research/decision-impact?id=${encodeURIComponent(impactChoiceId)}`)).json();
    assert.equal(impactReport.schema_version, 'research-decision-impact-local/1');
    assert.equal(impactReport.dossiers[0].id, dossiers.dossiers[0].id);
    await page.locator(`[data-decision-impact="${impactChoiceId}"]`).click();
    const affectedHost = page.locator(`[data-decision-impact="${impactChoiceId}"]`).locator('..');
    await expect(affectedHost).toContainText('Synthetic dossier');
    await expect(affectedHost).toContainText('Linked versions: 1; latest saved: 1');
    await affectedHost.locator('[data-research-detail="dossier"]').click();
    await expect(affectedHost).toContainText('End of synthetic dossier.');
    await page.locator('[data-rtab=review]').click();
    const reviewHost = page.locator('#research-editorial-review');
    await expect(reviewHost).toContainText('General artistic choice');
    await expect(reviewHost).toContainText('No affected dossier is recorded');
    await expect(reviewHost).toContainText('Decision is newer than the current dossier.');
    await expect(page.locator('#rtab-review')).toContainText('They do not establish a contradiction');
    assert.equal(await reviewHost.locator('img').count(), 0);
    for (const width of [1440, 320]) {
      await page.setViewportSize({width, height: 1000});
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Editorial review overflows at ${width}px`);
      await page.locator('#rtab-review').screenshot({path: path.join(artifacts, `editorial-review-${width}.png`)});
    }
    await page.locator('#r-review-refresh').click();
    await expect(reviewHost).toContainText('Move the date');
    const recordAfterReview = await (await page.request.get(fixture.url + `/api/research/record?kind=decision&id=${encodeURIComponent(impactChoiceId)}`)).json();
    assert.equal(recordBeforeReview.snapshot, recordAfterReview.snapshot);
    await page.setViewportSize({width: 1440, height: 1000});

    await page.locator('[data-rtab=search]').click();
    await page.locator('#r-search-scope').selectOption('decisions');
    await page.locator('#r-search-query').fill('meeting');
    await page.locator('#r-search-btn').click();
    await expect(page.locator('#research-search-results')).toContainText('Move the date');
    await expect(page.locator('#research-search-results')).toContainText('Deliberate deviation');
    await page.locator('#research-search-results [data-research-history=decision]').click();
    await expect(page.locator('#research-revision-history-detail')).toContainText('Earlier meeting.');
    await page.locator('#modal-research-revision [data-close-modal]').first().click();
    await page.locator('#r-search-scope').selectOption('claims');
    await page.locator('#r-search-query').fill('Archivist');
    await page.locator('#r-search-btn').click();
    await expect(page.locator('#research-search-results')).toContainText(claimTitle);
    await expect(page.locator('#research-search-results')).toContainText('Hypothetical');
    assert.equal(await page.locator('#research-search-results img').count(), 0);
    assert.equal(await page.locator('#research-search-results [data-use-passage]').count(), 0);
    await page.locator('#r-search-scope').selectOption('sources');

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
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    assert.equal(await page.locator('#research-revision-merge img').count(), 0, 'Conflict values remain inert text');
    await page.setViewportSize({width: 320, height: 900});
    assert.ok(await revisionDialog.evaluate(el => el.scrollWidth <= el.clientWidth), 'Conflict review has no horizontal dialog overflow');
    await revisionDialog.screenshot({path: path.join(artifacts, 'revision-conflict-320.png')});
    await page.setViewportSize({width: 1440, height: 900});
    await expect(page.locator('#research-revision-merge-apply')).toBeDisabled();
    assert.equal(await page.locator('#research-revision-merge input:checked').count(), 0, 'No conflict choice is accepted automatically');
    await page.locator('#research-revision-merge input[value="mine"]').check();
    await page.locator('#research-revision-merge-apply').click();
    await expect(page.locator('#research-revision-merge')).toBeHidden();
    await expect(field('title')).toHaveValue('My unsaved draft');
    assert.equal((await (await page.request.get(fixture.url + `/api/research/record?kind=dossier&id=${encodeURIComponent(dossierId)}`)).json()).record.title,
      'Other editor title', 'Applying a reviewed preview never saves');
    await page.keyboard.press('Escape');
    await page.locator(`[data-research-revise=dossier][data-record-id="${dossierId}"]`).click();
    await expect(field('title')).toHaveValue('Other editor title');
    await field('title').fill('Another stale draft');
    await chooseChange();
    await page.request.post(fixture.url + '/api/research-claim-add', {data: {
      title: 'Unrelated synthetic claim', statement: 'A separate claim changed the snapshot.', confidence: 'hypothetical'
    }});
    await page.locator('#research-revision-save').click();
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    assert.equal(await page.locator('#research-revision-merge input[type="radio"]').count(), 0, 'Unrelated changes do not require choosing away a draft');
    await expect(page.locator('#research-revision-merge-apply')).toBeEnabled();
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
    await page.locator(`[data-load-evidence="${claimId}"]`).click();
    const evidenceData = await (await page.request.get(fixture.url + `/api/research/claims?claim_id=${encodeURIComponent(claimId)}`)).json();
    const evidenceId = evidenceData.evidence_links[0].id;
    assert.equal(evidenceData.evidence_links[0].claim_revision, 1);
    assert.equal(evidenceData.evidence_links[0].claim_latest_revision, 2);
    await page.locator(`[data-research-revise=evidence_link][data-record-id="${evidenceId}"]`).click();
    await field('relation').selectOption('qualifies');
    await page.locator('#research-revision-options').evaluate(element => {element.open = true;});
    await field('claim_revision').fill('2');
    await page.locator('#research-revision-options').evaluate(element => {element.open = true;});
    await field('rationale').fill('The revised statement needs a qualification.');
    await chooseChange();
    await page.locator('#research-revision-save').click();
    await expect(revisionDialog).not.toBeVisible();
    const revisedLink = await (await page.request.get(fixture.url + `/api/research/record?kind=evidence_link&id=${encodeURIComponent(evidenceId)}`)).json();
    const originalLink = await (await page.request.get(fixture.url + `/api/research/record?kind=evidence_link&id=${encodeURIComponent(evidenceId)}&revision=1`)).json();
    assert.equal(revisedLink.record.claim_ref.revision, 2);
    assert.equal(originalLink.record.claim_ref.revision, 1);
    await page.locator(`#research-claims-list [data-research-history=claim][data-record-id="${claimId}"]`).click();
    await expect(page.locator('#research-revision-history-detail')).toContainText(evidenceId);
    await expect(page.locator('#research-revision-history-detail')).toContainText('Claim · Saved version 2');
    await page.keyboard.press('Escape');
    await page.locator('[data-rtab=decisions]').click();
    const decisionId = decisions.decisions[0].id;
    await page.locator(`#research-decisions-list [data-research-revise=decision][data-record-id="${decisionId}"]`).click();
    await page.locator('#research-revision-options').evaluate(element => {element.open = true;});
    await field('rationale').fill('Supersede the earlier narrative choice.');
    await page.locator('#research-revision-options').evaluate(element => {element.open = true;});
    await field('deviation_from_fact').uncheck();
    await chooseChange('supersession');
    await page.locator('#research-revision-save').click();
    await expect(revisionDialog).not.toBeVisible();
    const revisedDecision = await (await page.request.get(fixture.url + `/api/research/record?kind=decision&id=${encodeURIComponent(decisionId)}`)).json();
    assert.equal(revisedDecision.record.change.change_kind, 'supersession');
    assert.equal(revisedDecision.record.deviation_from_fact, false);
    assert.equal((await (await page.request.get(fixture.url + '/api/research/decisions')).json()).decisions.length, 2);

    // Queue related drafts, review literal values, and save them atomically.
    const groupDialog = page.locator('#modal-research-revision-batch');
    const currentDossiers = await (await page.request.get(fixture.url + '/api/research/dossiers')).json();
    const secondDossierId = currentDossiers.dossiers.find(item => item.id !== dossierId).id;
    await page.locator('[data-rtab=dossiers]').click();
    await page.locator(`[data-research-revise=dossier][data-record-id="${dossierId}"]`).click();
    await field('title').fill('First queued draft <img src=x onerror=alert(1)>');
    await chooseChange();
    await page.locator('#research-revision-batch-add').click();
    await expect(page.locator('#research-revision-status')).toContainText('nothing saved');
    await expect(page.locator('#research-revision-batch-add')).toHaveText('Replace queued draft');
    await field('title').fill('Reviewed first draft <img src=x onerror=alert(1)>');
    await page.locator('#research-revision-batch-add').click();
    await expect(page.locator('#research-revision-status')).toContainText('replaced');
    await page.keyboard.press('Escape');
    await expect(page.locator('#research-revision-batch-review')).toContainText('(1)');
    await page.locator(`[data-research-revise=dossier][data-record-id="${secondDossierId}"]`).click();
    await field('title').fill('Reviewed second draft');
    await chooseChange();
    await page.locator('#research-revision-batch-add').click();
    await expect(page.locator('#research-revision-status')).toContainText('nothing saved');
    await page.keyboard.press('Escape');
    await page.locator('[data-rtab=decisions]').click();
    await page.locator(`#research-decisions-list [data-research-revise=decision][data-record-id="${decisionId}"]`).click();
    await page.locator('#research-revision-options').evaluate(element => {element.open = true;});
    await field('rationale').fill('Reflect both reviewed dossiers.');
    await page.locator('#research-revision-options').evaluate(element => {element.open = true;});
    await field('dossier_ids').fill(dossierId);
    await chooseChange('supersession');
    await page.locator('#research-revision-batch-add').click();
    await expect(page.locator('#research-revision-status')).toContainText('nothing saved');
    await page.keyboard.press('Escape');
    const readRecord = async (kind, id) => (await (await page.request.get(fixture.url + `/api/research/record?kind=${kind}&id=${encodeURIComponent(id)}`)).json());
    const groupBefore = await readRecord('dossier', dossierId);
    assert.equal(groupBefore.record.title, 'Other editor title', 'Adding drafts never saves them');
    await page.locator('#research-revision-batch-review').click();
    await expect(page.locator('#research-revision-batch-list > li')).toHaveCount(3);
    await expect(page.locator('#research-revision-batch-apply')).toBeEnabled();
    assert.equal(await groupDialog.locator('img').count(), 0, 'Queued values remain inert text');
    for (const width of [1440, 320]) {
      await page.setViewportSize({width, height: 950});
      assert.ok(await groupDialog.evaluate(el => el.scrollWidth <= el.clientWidth), `Change set overflows at ${width}px`);
      await groupDialog.screenshot({path: path.join(artifacts, `revision-change-set-${width}.png`)});
    }
    await groupDialog.locator('[data-close-modal]').last().click();
    await expect(page.locator('#research-revision-batch-review')).toContainText('(3)');
    await page.locator('#research-revision-batch-review').click();
    await expect(page.locator('#research-revision-batch-apply')).toBeEnabled();
    const racingRecord = await readRecord('dossier', dossierId);
    assert.equal((await page.request.post(fixture.url + '/api/research-record-revise', {data: {
      kind: 'dossier', id: dossierId, changes: {title: 'Racing saved title'},
      expected_snapshot: racingRecord.snapshot, expected_revision: racingRecord.record.revision,
      change_kind: 'correction', reason: 'Synthetic racing edit.'
    }})).status(), 200);
    await page.locator('#research-revision-batch-apply').click();
    await expect(page.locator('#research-revision-batch-status')).toContainText('Drafts are kept');
    await expect(page.locator('#research-revision-batch-apply')).toBeDisabled();
    await expect(page.locator('#research-revision-batch-list > li')).toHaveCount(3);
    assert.equal((await readRecord('decision', decisionId)).record.revision, revisedDecision.record.revision);
    await page.locator('#research-revision-batch-check').click();
    await expect(page.locator('#research-revision-batch-status')).toContainText('Record revision changed');
    await page.locator('#research-revision-batch-list [data-batch-edit]').first().click();
    await expect(field('title')).toHaveValue('Reviewed first draft <img src=x onerror=alert(1)>');
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    await page.locator('#research-revision-merge input[value=mine]').check();
    await page.locator('#research-revision-merge-apply').click();
    await expect(page.locator('#research-revision-merge')).toBeHidden();
    await page.locator('#research-revision-batch-add').click();
    await expect(page.locator('#research-revision-status')).toContainText('replaced');
    await page.keyboard.press('Escape');
    await page.locator('#research-revision-batch-review').click();
    await expect(page.locator('#research-revision-batch-apply')).toBeEnabled();
    await page.route('**/api/research-revision-batch-apply', route => route.fulfill({status: 500, json: {ok: false, message: 'Synthetic group save failure'}}));
    await page.locator('#research-revision-batch-apply').click();
    await expect(page.locator('#research-revision-batch-status')).toContainText('Synthetic group save failure');
    await expect(page.locator('#research-revision-batch-list > li')).toHaveCount(3);
    await expect(page.locator('#research-revision-batch-apply')).toBeDisabled();
    await page.unroute('**/api/research-revision-batch-apply');
    await page.locator('#research-revision-batch-check').click();
    await expect(page.locator('#research-revision-batch-apply')).toBeEnabled();
    await page.locator('#research-revision-batch-apply').click();
    await expect(groupDialog).not.toBeVisible();
    await expect(page.locator('#research-revision-batch-review')).toBeHidden();
    const savedGroup = await readRecord('decision', decisionId);
    assert.equal(savedGroup.record.rationale, 'Reflect both reviewed dossiers.');
    assert.deepEqual(savedGroup.record.dossier_refs, [{id: dossierId, revision: groupBefore.record.revision}], 'Grouped save retains the reviewed dossier pin instead of moving it to the simultaneous new revision');
    assert.equal((await readRecord('dossier', secondDossierId)).record.title, 'Reviewed second draft');
    assert.equal((await readRecord('dossier', dossierId)).record.title, 'Reviewed first draft <img src=x onerror=alert(1)>');
    await page.setViewportSize({width: 1440, height: 1000});

    // A displayed explicit pin is retained when changing the associated ID.
    const allClaims = await (await page.request.get(fixture.url + '/api/research/claims')).json();
    const otherClaimId = allClaims.claims.find(item => item.title === 'Unrelated synthetic claim').id;
    for (let revision = 1; revision <= 2; revision++) {
      const claimCurrent = await readRecord('claim', otherClaimId);
      assert.equal((await page.request.post(fixture.url + '/api/research-record-revise', {data: {
        kind: 'claim', id: otherClaimId, changes: {statement: `Synthetic associated claim revision ${revision + 1}.`},
        expected_snapshot: claimCurrent.snapshot, expected_revision: claimCurrent.record.revision,
        change_kind: 'correction', reason: 'Synthetic version boundary.'
      }})).status(), 200);
    }
    await page.locator('[data-rtab=claims]').click();
    await page.locator(`[data-load-evidence="${claimId}"]`).click();
    await page.locator(`[data-research-revise=evidence_link][data-record-id="${evidenceId}"]`).click();
    await expect(field('claim_revision')).toHaveValue('2');
    await field('claim_id').fill(otherClaimId);
    await expect(field('claim_revision')).toHaveValue('');
    await page.locator('#research-revision-options').evaluate(element => {element.open = true;});
    await field('claim_revision').fill('2');
    await chooseChange();
    await page.locator('#research-revision-batch-add').click();
    await expect(page.locator('#research-revision-status')).toContainText('nothing saved');
    await expect(field('claim_revision')).toHaveValue('2');
    await page.keyboard.press('Escape');
    const groupResponse = page.waitForResponse(response => response.url().endsWith('/api/research-revision-batch-prepare'));
    await page.locator('#research-revision-batch-review').click();
    assert.equal((await (await groupResponse).json()).operations[0].changes.claim_revision, 2);
    await expect(page.locator('#research-revision-batch-apply')).toBeEnabled();
    await page.locator('#research-revision-batch-clear').click();
    await expect(page.locator('#research-revision-batch-list > li')).toHaveCount(0);
    await expect(page.locator('#research-revision-batch-review')).toBeHidden();
    await groupDialog.locator('[data-close-modal]').last().click();
    assert.equal((await readRecord('evidence_link', evidenceId)).record.claim_ref.id, claimId, 'Discarding queued drafts does not revise archived associations');

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
        const ocrStates = {
          ready: 'OCR-Worker konfiguriert',
          native_only: 'PDF-Textebene verfügbar',
          partial: 'PDF-Einrichtung unvollständig',
          misconfigured_worker: 'OCR-Worker nicht ausführbar',
          missing_dependencies: 'PDF-Werkzeuge fehlen',
          future_state: 'OCR-Status unbekannt'
        };
        for (const [status, label] of Object.entries(ocrStates)) {
          await page.route('**/api/research/status', async route => {
            const response = await route.fetch();
            const body = await response.json();
            body.ocr = {status, guidance: ['English backend guidance must not leak']};
            await route.fulfill({response, json: body});
          });
          await page.reload();
          await expect(page.locator('#r-ocr-diagnostic-box')).toContainText(label);
          await expect(page.locator('#r-ocr-diagnostic-box')).not.toContainText('English backend');
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
          if (status === 'native_only') {
            await page.locator('[data-rtab="sources"]').click();
            await page.locator('#research-manager').screenshot({path: path.join(artifacts, 'ocr-origin-de-320.png')});
          }
          await page.unroute('**/api/research/status');
        }
        for (const [status, expectedLabel, missing] of [
          ['ready', 'Lokale Texterkennung konfiguriert', []],
          ['misconfigured_backend', 'Lokale OCR-Einrichtung unvollständig', ['deu']]
        ]) {
          await page.route('**/api/research/status', async route => {
            const response = await route.fetch();
            const body = await response.json();
            body.ocr = {status, backend: 'tesseract', requested_languages: ['deu', 'eng'],
              missing_languages: missing, guidance: ['English backend guidance must not leak']};
            await route.fulfill({response, json: body});
          });
          await page.reload();
          await page.locator('[data-rtab="sources"]').click();
          await expect(page.locator('#r-ocr-diagnostic-box')).toContainText(expectedLabel);
          await expect(page.locator('#r-ocr-diagnostic-box')).toContainText('Sprachen: deu + eng.');
          await expect(page.locator('#r-ocr-diagnostic-box')).not.toContainText('English backend');
          if (missing.length) await expect(page.locator('#r-ocr-diagnostic-box')).toContainText('Fehlende Sprachdaten: deu.');
          for (const width of [1440, 320]) {
            await page.setViewportSize({width, height: 844});
            assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Tesseract status overflows at ${width}px`);
            await page.locator('#r-ocr-diagnostic-box').screenshot({path: path.join(artifacts, `ocr-tesseract-${status}-${width}.png`)});
          }
          await page.unroute('**/api/research/status');
        }
        await page.reload();
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
      await page.locator(`#research-decisions-list [data-research-history=decision][data-record-id="${decisionId}"]`).click();
      await page.locator('[data-research-revision="1"]').click();
      await expect(page.locator('#research-revision-history-detail')).toContainText('Bring the opening into the first chapter.');
      assert.ok(await revisionDialog.evaluate(element => element.scrollWidth <= element.clientWidth), `${language} revision history overflow`);
      await page.locator('#research-revision-history-detail').scrollIntoViewIfNeeded();
      await revisionDialog.screenshot({path: path.join(artifacts, `history-${language}-320.png`)});
      await page.keyboard.press('Escape');
      if (language === 'en') {
        await page.locator(`#research-decisions-list [data-research-revise=decision][data-record-id="${decisionId}"]`).click();
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
      await page.locator(`[data-load-evidence="${claimId}"]`).click();
      await expect(page.locator('.claim-evidence-subpanel .badge-warning')).toBeVisible();
      if (operation === 'withdraw') {
        await expect(page.locator(`[id="claim-evidence-${claimId}"]`)).toContainText('The synthetic archive opened in 1924.');
      } else {
        await expect(page.locator(`[id="claim-evidence-${claimId}"]`)).not.toContainText('The synthetic archive opened in 1924.');
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
    await page.locator('#tab-view-research').click();
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
    await page.locator('#tab-view-research').click();
    await expect(page.locator('#research-init-box')).toBeVisible();
    await page.locator('#r-init-title').fill('Scratch research');
    await page.locator('#r-init-btn').click();
    await expect(page.locator('#research-tabs')).toBeVisible();
    await page.locator('#r-ingest-options > summary').click();
    await page.locator('#r-ingest-title').fill('Scratch source');
    await page.locator('#r-ingest-origin-url').fill('javascript:alert(1)');
    await page.locator('#r-ingest-text').fill('A synthetic source for a new local project.');
    await page.locator('#r-ingest-retention').check();
    await page.locator('#r-ingest-btn').click();
    await expect(page.locator('#research-status-bar')).toContainText('HTTP(S)');
    await expect(page.locator('#r-ingest-title')).toHaveValue('Scratch source');
    await expect(page.locator('#r-ingest-text')).toHaveValue('A synthetic source for a new local project.');
    await page.locator('#r-ingest-origin-url').fill('https://example.org/source?a=1&b=2');
    const localWarning = 'Synthetic extraction note: <img src=x onerror=alert(1)> check captured passages.';
    await page.route('**/api/research-ingest', async route => {
      const response = await route.fetch();
      const body = await response.json();
      await route.fulfill({response, json: {...body, warnings: [localWarning]}});
    });
    await page.locator('#r-ingest-btn').click();
    await expect(page.locator('#r-ingest-origin-url')).toHaveValue('');
    await expect(page.locator('#research-status-bar.ok')).toContainText(localWarning);
    assert.equal(await page.locator('#research-status-bar img').count(), 0, 'Warning markup must remain text');
    await page.unroute('**/api/research-ingest');
    for (const width of [1440, 390]) {
      await page.setViewportSize({width, height: 1000});
      await page.locator('#research-status-bar').screenshot({path: path.join(artifacts, `local-warning-${width}.png`)});
      assert.ok(await page.locator('#research-status-bar').evaluate(e => e.getBoundingClientRect().right <= innerWidth));
    }
    await page.setViewportSize({width: 1440, height: 1000});
    await expect(page.locator('#research-sources-list')).toContainText('Scratch source');
    await page.locator('[data-research-detail="source"]').first().click();
    await expect(page.locator('#research-sources-list')).toContainText('https://example.org/source?a=1&b=2');
    await expect(page.locator('#r-active-root')).toContainText(scratchProject);
    // A fully mapped archive retains evidence access while Zotero is offline.
    execFileSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
import sys
from pathlib import Path
from lixity.research import api
project = Path(sys.argv[1])
source = api.list_sources(project)['sources'][0]
text = project / 'synthetic-zotero.txt'
text.write_text('A synthetic source for a new local project.', encoding='utf-8')
context = dict(source['context'])
context['external_reference'] = {'provider': 'zotero', 'server_id': 'synthetic-instance',
    'library': 'users/0', 'item_key': 'ABCDEFGH', 'attachment_key': 'JKLMNPQR',
    'item_version': 1, 'attachment_version': 1}
api.ingest(project, text, source_id=source['id'], allow_retention=True, context=context)
`, scratchProject], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}});
    await page.reload();
    await expect(page.locator('#r-local-import')).not.toBeVisible();
    await expect(page.locator('#research-sources-list')).toContainText('Scratch source');
    await expect(page.locator('#research-sources-list a[href="zotero://select/library/items/ABCDEFGH"]')).toBeVisible();
    let zoteroOffline = true;
    await page.route('**/api/research-zotero', route => route.fulfill({json: zoteroOffline
      ? {ok: false, message: 'Synthetic Zotero unavailable; start the selected profile.'}
      : {ok: true, server_id: 'synthetic-instance', items: [], next_start: null, captures: []}}));
    await page.locator('#r-zotero-browse').click();
    await expect(page.locator('#r-zotero-results')).toContainText('Synthetic Zotero unavailable');
    await expect(page.locator('#r-zotero-browse')).toBeEnabled();
    await page.locator('[data-research-detail="source"]').first().click();
    await expect(page.locator('#research-sources-list')).toContainText('A synthetic source for a new local project.');
    zoteroOffline = false;
    await page.locator('#r-zotero-browse').click();
    await expect(page.locator('#r-zotero-results')).not.toContainText('Synthetic Zotero unavailable');
    await expect(page.locator('#r-zotero-browse')).toBeEnabled();
    await page.unroute('**/api/research-zotero');
    const importedProject = path.join(artifacts, 'imported-project');
    const importedText = '## Imported chapter\n\nA synthetic imported manuscript.';
    await page.locator('#btn-modal-new-project').click();
    await page.locator('#tab-btn-import').click();
    await page.locator('#import-file-input').setInputFiles({name: 'synthetic.md', mimeType: 'text/markdown', buffer: Buffer.from(importedText)});
    await page.locator('#import-proj-title').fill('Explicit byte import');
    await page.locator('#import-project-options').evaluate(element => {element.open = true;});
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
