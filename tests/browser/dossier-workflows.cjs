// Contextual forms and selected-section edits use the existing native workflows.
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const {createInterface} = require('node:readline');
const assert = require('node:assert/strict');
const {expect} = require(path.join(playwrightModule, 'test'));
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-dossier-workflows-'));

(async () => {
  const server = spawn(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-u', '-c', `
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
base = Path(sys.argv[1]); project = base / 'synthetic-project'
api.init(project, title='Synthetic contextual research')
dossier = api.create_dossier(project, title='Current synthetic dossier', body='# Notes\\n\\nOriginal note.\\n\\n# Detail\\n\\nOriginal detail.')
api.create_dossier(project, title='Another synthetic dossier', body='Unrelated body.')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.language = 'en'; LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'dossier': dossier['dossier_id']}), flush=True)
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
      server.once('error', reject);
      server.once('exit', code => reject(new Error(`Fixture exited ${code}: ${stderr}`)));
    });
    browser = await launchChromium();
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [], preparations = [], saves = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (request.method() !== 'POST') return;
      if (request.url().endsWith('/research-record-prepare')) preparations.push(request.postDataJSON());
      if (request.url().endsWith('/research-record-revise')) saves.push(request.postDataJSON());
    });
    const details = page.locator(`[data-research-detail=dossier][data-record-id="${fixture.dossier}"]`);
    async function openDetails() {
      await Promise.all([page.waitForResponse(response => response.url() === fixture.url + '/api/research/dossiers'), page.locator('[data-rtab=dossiers]').click()]);
      // A refresh preserves an unchanged open detail, so close it first;
      // clicking blindly would toggle the preserved detail shut.
      if (await details.evaluate(node => node.parentElement.open)) await details.click();
      await details.click();
      await expect(page.locator(`[data-dossier-claim="${fixture.dossier}"]`)).toBeVisible();
    }
    async function reviseRecord(transform) {
      const current = await (await page.request.get(fixture.url + '/api/research/record?kind=dossier&id=' + fixture.dossier)).json();
      const response = await page.request.post(fixture.url + '/api/research-record-revise', {data: {
        kind: 'dossier', id: fixture.dossier, expected_snapshot: current.snapshot,
        expected_revision: current.record.revision, changes: transform(current.record),
        change_kind: 'correction', reason: 'Synthetic concurrent section change'
      }});
      assert.equal(response.ok(), true);
      return response.json();
    }
    async function reviseBody(transform) {
      return reviseRecord(record => ({body: transform(record.body)}));
    }
    await page.goto(fixture.url);
    await page.locator('#tab-view-research').click();
    await openDetails();
    await page.evaluate(() => {
      document.getElementById('r-claim-title').value = 'Preserved contextual claim';
      document.getElementById('r-claim-statement').value = 'A synthetic contextual statement.';
    });
    await page.locator(`[data-dossier-claim="${fixture.dossier}"]`).click();
    await expect(page.locator('#r-claim-title')).toHaveValue('Preserved contextual claim');
    await expect(page.locator('#r-claim-title')).toBeFocused();
    await expect(page.locator('#r-claim-dossier-select')).toHaveValue(fixture.dossier);
    assert.equal(await page.locator('#r-claim-dossier-select option:checked').textContent(), 'Current synthetic dossier');
    await page.locator('#r-claim-create-btn').click();
    await expect(page.locator('#r-claim-title')).toHaveValue('');
    const claims = await (await page.request.get(fixture.url + '/api/research/claims')).json();
    assert.equal(claims.claims[0].dossier_id, fixture.dossier);
    await openDetails();
    await page.evaluate(() => {
      document.getElementById('r-decision-title').value = 'Preserved contextual decision';
      document.getElementById('r-decision-rationale').value = 'A synthetic contextual rationale.';
    });
    await page.locator(`[data-dossier-decision="${fixture.dossier}"]`).click();
    await expect(page.locator('#r-decision-title')).toHaveValue('Preserved contextual decision');
    await expect(page.locator('#r-decision-title')).toBeFocused();
    await expect(page.locator('#r-decision-dossier-select')).toHaveValue(fixture.dossier);
    await page.locator('#r-decision-create-btn').click();
    await expect(page.locator('#r-decision-title')).toHaveValue('');
    const decisions = await (await page.request.get(fixture.url + '/api/research/decisions')).json();
    const decision = await (await page.request.get(fixture.url + '/api/research/record?kind=decision&id=' + decisions.decisions[0].id)).json();
    assert.equal(decision.record.dossier_refs[0].id, fixture.dossier);
    assert.equal(decision.record.dossier_refs[0].revision, 1);
    await openDetails();
    const sectionButton = page.locator('[data-dossier-section=Notes]');
    await sectionButton.click();
    const dialog = page.locator('#modal-research-revision');
    await expect(page.locator('#research-revision-field-body')).toHaveValue('Original note.');
    assert.equal(await page.locator('#research-revision-field-title').count(), 0, 'Selected-section edits show only the body field');
    await expect(page.locator('#research-revision-batch-add')).not.toBeVisible();
    await reviseBody(body => body.replace('Original detail.', 'Concurrent detail.'));
    await page.locator('#research-revision-field-body').fill('Revised note.');
    await page.locator('input[name=research_revision_change_kind][value=correction]').check();
    await page.locator('#research-revision-reason').fill('Synthetic section correction.');
    await page.locator('#research-revision-save').click();
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    await expect(page.locator('#research-revision-merge')).not.toContainText('Concurrent detail.');
    await page.locator('#research-revision-merge-apply').click();
    await expect(page.locator('#research-revision-merge')).not.toBeVisible();
    await page.locator('#research-revision-save').click();
    await expect(dialog).not.toBeVisible();
    const accepted = await (await page.request.get(fixture.url + '/api/research/record?kind=dossier&id=' + fixture.dossier)).json();
    assert.equal(accepted.record.body, '# Notes\n\nRevised note.\n\n# Detail\n\nConcurrent detail.');
    assert.equal(accepted.record.title, 'Current synthetic dossier');
    assert.equal(preparations.at(-1).section, 'Notes');
    assert.equal(preparations.at(-1).changes.body, 'Revised note.');
    assert.equal(saves.at(-1).changes.body, accepted.record.body, 'Save publishes the canonical complete prepared body');
    await openDetails();
    await sectionButton.click();
    await expect(page.locator('#research-revision-field-body')).toHaveValue('Revised note.');
    await page.locator('#research-revision-field-body').fill('My conflicting note.');
    await page.locator('input[name=research_revision_change_kind][value=correction]').check();
    await page.locator('#research-revision-reason').fill('Synthetic conflict review.');
    await reviseBody(body => body.replace('Revised note.', 'Their conflicting note.'));
    await page.locator('#research-revision-save').click();
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    await expect(page.locator('#research-revision-field-body')).toHaveValue('My conflicting note.');
    await expect(page.locator('#research-revision-reason')).toHaveValue('Synthetic conflict review.');
    await expect(page.locator('#research-revision-merge')).not.toContainText('Concurrent detail.');
    await page.locator('#research-revision-merge input[value=mine]').check();
    const sectionSnapshot = await page.locator('#research-revision-snapshot').textContent();
    const sectionSaves = saves.length;
    await reviseBody(body => body.replace('Their conflicting note.', 'A later unreviewed conflicting note.'));
    await page.locator('#research-revision-merge-apply').click();
    await expect(page.locator('#research-revision-form')).toHaveAttribute('aria-busy', 'false');
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    await expect(page.locator('#research-revision-merge')).toContainText('A later unreviewed conflicting note.');
    assert.equal(await page.locator('#research-revision-merge input:checked').count(), 0, 'Stale choices cannot apply to another saved section version');
    await expect(page.locator('#research-revision-field-body')).toHaveValue('My conflicting note.');
    await expect(page.locator('#research-revision-reason')).toHaveValue('Synthetic conflict review.');
    assert.equal(await page.locator('#research-revision-snapshot').textContent(), sectionSnapshot, 'A stale Apply cannot adopt the new snapshot');
    assert.equal(saves.length, sectionSaves, 'Refreshing an unresolved preview never saves');
    await page.locator('#research-revision-merge input[value=mine]').check();
    await page.locator('#research-revision-merge-apply').click();
    await expect(page.locator('#research-revision-field-body')).toHaveValue('My conflicting note.');
    await expect(page.locator('#research-revision-merge')).not.toBeVisible();
    await page.locator('#research-revision-save').click();
    await expect(dialog).not.toBeVisible();
    const reconciled = await (await page.request.get(fixture.url + '/api/research/dossiers?id=' + fixture.dossier)).json();
    assert.ok(reconciled.body.includes('My conflicting note.'));
    assert.ok(reconciled.body.includes('Concurrent detail.'));

    // The same shared Apply guard also protects ordinary record edits and a
    // snapshot-only change where this record's own revision has not advanced.
    await openDetails();
    await page.locator(`[data-research-revise=dossier][data-record-id="${fixture.dossier}"]:not([data-dossier-section])`).click();
    await expect(page.locator('#research-revision-field-title')).toHaveValue('Current synthetic dossier');
    await page.locator('#research-revision-field-title').fill('My reviewed general title');
    await page.locator('input[name=research_revision_change_kind][value=correction]').check();
    await page.locator('#research-revision-reason').fill('Synthetic general conflict review.');
    const theirTitle = await reviseRecord(() => ({title: 'Their first general title'}));
    await page.locator('#research-revision-save').click();
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    await page.locator('#research-revision-merge input[value=mine]').check();
    const generalSnapshot = await page.locator('#research-revision-snapshot').textContent();
    const unrelated = await page.request.post(fixture.url + '/api/research-dossier', {data: {
      title: 'Concurrent unrelated dossier', body: 'Synthetic unrelated publication.'
    }});
    assert.equal(unrelated.ok(), true);
    const unchangedRecord = await (await page.request.get(fixture.url + '/api/research/record?kind=dossier&id=' + fixture.dossier)).json();
    assert.equal(unchangedRecord.record.revision, theirTitle.record.revision);
    await page.locator('#research-revision-merge-apply').click();
    await expect(page.locator('#research-revision-form')).toHaveAttribute('aria-busy', 'false');
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    assert.equal(await page.locator('#research-revision-merge input:checked').count(), 0, 'A new HEAD also requires review when the record revision is unchanged');
    assert.equal(await page.locator('#research-revision-snapshot').textContent(), generalSnapshot);
    await expect(page.locator('#research-revision-field-title')).toHaveValue('My reviewed general title');
    await page.locator('#research-revision-merge input[value=current]').check();
    await reviseRecord(() => ({title: 'A later unreviewed general title'}));
    const generalSaves = saves.length;
    await page.locator('#research-revision-merge-apply').click();
    await expect(page.locator('#research-revision-form')).toHaveAttribute('aria-busy', 'false');
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    await expect(page.locator('#research-revision-merge')).toContainText('A later unreviewed general title');
    assert.equal(await page.locator('#research-revision-merge input:checked').count(), 0);
    await expect(page.locator('#research-revision-field-title')).toHaveValue('My reviewed general title');
    await expect(page.locator('#research-revision-reason')).toHaveValue('Synthetic general conflict review.');
    assert.equal(await page.locator('#research-revision-snapshot').textContent(), generalSnapshot);
    assert.equal(saves.length, generalSaves);
    await page.locator('#research-revision-merge input[value=mine]').check();
    await page.locator('#research-revision-merge-apply').click();
    await expect(page.locator('#research-revision-merge')).not.toBeVisible();
    await page.locator('#research-revision-save').click();
    await expect(dialog).not.toBeVisible();
    const reviewedTitle = await (await page.request.get(fixture.url + '/api/research/record?kind=dossier&id=' + fixture.dossier)).json();
    assert.equal(reviewedTitle.record.title, 'My reviewed general title');
    assert.ok(reviewedTitle.record.body.includes('My conflicting note.'));
    for (const language of ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl']) {
      await page.request.post(fixture.url + '/api/settings', {data: {language}});
      await page.reload();
      await page.locator('#tab-view-research').click();
      await openDetails();
      await sectionButton.click();
      await expect(page.locator('#research-revision-field-body')).toHaveValue('My conflicting note.');
      for (const width of language === 'en' ? [1440, 390, 320] : [320]) {
        await page.setViewportSize({width, height: 900});
        assert.ok(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth), `${language} ${width}px section dialog overflow`);
        await dialog.screenshot({path: path.join(artifacts, `section-${language}-${width}.png`)});
      }
      await page.keyboard.press('Escape');
    }
    assert.deepEqual(errors, []);
    console.log(`Dossier workflows: titled contextual claim/decision pins and preserved drafts; selected-section prepare/save, unrelated concurrent preservation, bounded conflict review and seven locales at 1440/390/320 passed. Screenshots: ${artifacts}`);
  } finally {
    if (stderr.includes('Traceback')) console.error(stderr);
    if (browser) await browser.close();
    lines.close();
    if (server.exitCode === null) { const exited = once(server, 'exit'); server.kill(); await exited; }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
