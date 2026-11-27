const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));

const source = path.join(__dirname, '../../samples/first-look.md');
const sentence = 'It was only when she looked at it again that she began to think that there might have been a reason for the space that he had left on the form.';
const revision = 'Only then did she wonder why he had left the line blank.';
const pinnedQuote = 'Someone had tried the eastern gate of Warehouse 4.';
const digest = content => createHash('sha256').update(content).digest('hex');

const fixtureCode = `
import json
import sys
from pathlib import Path

from lixity.server.handler import LixityServerHandler
from lixity.server.runtime import _LoopbackHTTPServer
from lixity.server.workspaces import WorkspaceRegistry
from scripts.example_project import create_example_project

project = Path(sys.argv[1]) / 'warehouse-4'
fixture = create_example_project(project)
manuscript = project / 'harbour-manuscript.md'
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.exports_dir = str(project / 'exports')
workspaces = WorkspaceRegistry(LixityServerHandler)
with _LoopbackHTTPServer(('127.0.0.1', 0), LixityServerHandler) as server:
    server.workspaces = workspaces
    print(json.dumps({
        'url': f'http://127.0.0.1:{server.server_port}',
        'manuscript': str(manuscript),
        'primary_claim_id': fixture['primary_claim_id'],
    }), flush=True)
    server.serve_forever()
`;

async function checkPassageEvidence(page) {
  await page.locator('#manuscript-analysis-toggle').click();
  await page.locator('#style-layer').selectOption('sticky');
  const paragraph = page.locator('.ptext').filter({hasText: sentence});
  const actions = paragraph.locator('.reader-paragraph-actions');
  await actions.scrollIntoViewIfNeeded();
  await actions.click();
  await page.locator('#manuscript-context-menu [data-reader-action="values"]').click();
  await page.locator('#reader-inspector-body [data-reader-action="evidence"]').click();
  const evidence = page.locator('#analysis-evidence-card');
  await expect(evidence.locator('blockquote')).toHaveText(sentence);
  await expect(evidence.locator('blockquote mark')).toHaveCount(22);
  await expect(evidence.locator('.analysis-evidence-explanation .analysis-evidence-value'))
    .toContainText('22 of 31 words as function words');
  await evidence.locator('.analysis-evidence-close').click();
  await expect(evidence).toBeHidden();
  await page.locator('#reader-inspector').getByRole('button', {name: 'Close', exact: true}).click();
}

async function compareAndSave(page, api, manuscript, originalBytes, editedBytes) {
  // The editor exchanges LF text and saves using the source file's line endings.
  const original = originalBytes.toString('utf8').replaceAll('\r\n', '\n');
  const edited = editedBytes.toString('utf8').replaceAll('\r\n', '\n');
  await page.locator('#manuscript-write').click();
  await expect(page.locator('.cm-content')).toBeVisible();
  await page.locator('#manuscript-versions > summary').click();
  await page.locator('#manuscript-compare').click();
  const comparison = page.locator('#manuscript-comparison');
  const draft = page.locator('#manuscript-comparison-draft');
  await expect(draft).toHaveValue(original);
  await expect(page.locator('#manuscript-comparison-base')).toHaveValue(original);
  await expect(page.locator('#manuscript-comparison-current')).toHaveValue(original);
  const compared = page.waitForResponse(response => response.url() === `${api}/manuscript-compare` &&
    response.request().postDataJSON().draft_text === edited);
  await draft.fill(edited);
  const comparisonResponse = await compared;
  assert.ok(comparisonResponse.ok(), 'The real comparison endpoint accepts the scoped draft');
  const data = await comparisonResponse.json();
  assert.equal(data.primary_diff, 'current_to_draft');
  assert.match(data.settings_sha256, /^[a-f0-9]{64}$/);
  assert.equal(data.measurements.current.revision, digest(originalBytes));
  assert.equal(data.measurements.draft.revision, digest(edited));
  const chapter = page.locator('#manuscript-comparison-chapters li').filter({hasText: 'The Blank Line'});
  await expect(chapter).toContainText(/[-−]19 words/);
  assert.deepEqual(fs.readFileSync(manuscript), originalBytes, 'Measuring a draft preserves the file');

  await page.locator('#manuscript-comparison-use').click();
  await expect(comparison).toBeHidden();
  const status = page.locator('#manuscript-save-status');
  await expect(status).toHaveAttribute('data-state', 'unsaved');
  assert.deepEqual(fs.readFileSync(manuscript), originalBytes, 'Using the draft does not save it');
  const save = page.locator('#manuscript-save');
  await expect(save.locator('.editor-tool-label')).toBeVisible();
  assert.ok(await save.evaluate(button => {
    const label = button.querySelector('.editor-tool-label');
    const range = document.createRange();
    range.selectNodeContents(label);
    const text = range.getBoundingClientRect(), control = button.getBoundingClientRect();
    return text.width > 0 && text.left >= control.left && text.right < control.right;
  }), 'The whole Save label fits inside its button beside the draft status');
  const saved = page.waitForResponse(response => response.url() === `${api}/manuscript-edit` &&
    response.request().method() === 'POST');
  await save.click();
  assert.ok((await saved).ok(), 'The explicit save succeeds');
  await expect(status).toHaveAttribute('data-state', 'saved');
  assert.deepEqual(fs.readFileSync(manuscript), editedBytes, 'Saving changes exactly the reviewed sentence');

  await Promise.all([page.waitForNavigation(), page.locator('#manuscript-close').click()]);
  await expect(page.locator('#chapters').getByText(revision, {exact: true})).toBeVisible();
  await page.reload();
  await expect(page.locator('#chapters').getByText(revision, {exact: true})).toBeVisible();
  await expect(page.locator('#chapters').getByText(sentence, {exact: true})).toHaveCount(0);
}

async function checkRetainedAssociation(page, api, claimId) {
  await page.locator('#tab-view-research').click();
  await page.locator('[data-rtab="review"]').click();
  const rows = page.locator('#research-manuscript-review .manuscript-link-review-item');
  await expect(rows).toHaveCount(7);
  const row = rows.filter({has: page.locator('blockquote').filter({hasText: pinnedQuote})});
  const pin = row.locator('[data-research-history="claim"]');
  await expect(pin).toHaveAttribute('data-record-id', claimId);
  await expect(pin).toHaveAttribute('data-record-revision', '1');
  const read = page.waitForResponse(response => {
    const url = new URL(response.url());
    return response.url().startsWith(`${api}/research/record?`) &&
      url.searchParams.get('kind') === 'claim' && url.searchParams.get('revision') === '1';
  });
  await pin.click();
  const response = await read;
  assert.ok(response.ok(), 'The saved association opens its retained record');
  const record = await response.json();
  assert.equal(record.record.revision, 1);
  assert.equal(record.is_latest, false);
  await expect(page.locator('#research-revision-history-detail')).toContainText(
    'The customs log describes an attempted entry at Warehouse 4 in October 1923.');
}

(async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-warehouse-author-'));
  let server, browser;
  try {
    server = await startNativeServer(fixtureCode, directory);
    const {url, manuscript, primary_claim_id: claimId} = server.fixture;
    const original = fs.readFileSync(source);
    assert.deepEqual(fs.readFileSync(manuscript), original, 'The native fixture uses the canonical manuscript');
    const text = original.toString('utf8');
    assert.equal(text.split(sentence).length, 2, 'The evidence sentence occurs exactly once');
    const edited = Buffer.from(text.replace(sentence, revision), 'utf8');

    browser = await launchChromium();
    const page = await browser.newPage({viewport: {width: 1440, height: 960}, reducedMotion: 'reduce'});
    const errors = [], outsideWorkspace = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      const requested = new URL(request.url());
      if (/^https?:$/.test(requested.protocol) && requested.origin !== url) outsideWorkspace.push(requested.origin);
    });
    await page.goto(url);
    const workspace = new URL(page.url());
    assert.match(workspace.pathname, /^\/w\/[a-f0-9]{32}\/$/);
    const api = new URL('api', workspace).href;

    await checkPassageEvidence(page);
    await compareAndSave(page, api, manuscript, original, edited);
    await checkRetainedAssociation(page, api, claimId);
    assert.deepEqual(fs.readFileSync(manuscript), edited);
    assert.deepEqual(errors, []);
    assert.deepEqual(outsideWorkspace, []);
    console.log('Warehouse 4 author workflow: passage evidence 22/31, same-settings draft comparison, exact save and reopen, retained claim version.');
  } finally {
    try {
      if (browser) await browser.close();
    } finally {
      if (server) await server.close();
      fs.rmSync(directory, {recursive: true, force: true});
    }
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
