// Local source capture: preserve drafts, consent and project context.
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(require('node:path').join(playwrightModule, 'test'));
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {createInterface} = require('node:readline');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-research-import-'));
const python = process.env.PYTHON_BIN || path.join(root, '.venv/bin/python');

(async () => {
  const server = spawn(python, ['-u', '-c', `
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
base = Path(sys.argv[1]); project = base / 'project'
api.init(project, title='Synthetic research archive')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.research_dir = str(project)
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.language = 'en'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}'}), flush=True)
server.serve_forever()
`, artifacts], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, stdio: ['ignore', 'pipe', 'pipe']});
  const lines = createInterface({input: server.stdout});
  let browser, stderr = '';
  server.stderr.on('data', data => {stderr += data;});
  try {
    const fixture = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Synthetic fixture timeout: ' + stderr)), 15000);
      lines.once('line', line => {clearTimeout(timer); resolve(JSON.parse(line));});
      server.once('error', reject);
    });
    browser = await launchChromium();
    const page = await browser.newPage({viewport: {width: 320, height: 600}});
    page.setDefaultTimeout(10000);
    await page.goto(fixture.url);
    await page.locator('[data-view=research]').click();
    await page.locator('[data-rtab=sources]').click();
    await page.locator('#r-local-import > summary').click();
    const file = page.locator('#r-ingest-file');
    const text = page.locator('#r-ingest-text');
    const retention = page.locator('#r-ingest-retention');
    const button = page.locator('#r-ingest-btn');
    const status = page.locator('#r-ingest-btn-status');
    await expect(file).toHaveAccessibleName('Source file');
    await page.locator('#r-local-import').screenshot({path: path.join(artifacts, 'capture-320.png')});
    let axePath;
    try {axePath = require.resolve('axe-core');}
    catch (_) {axePath = path.join(os.homedir(), 'rosts_services/node_modules/axe-core/axe.js');}
    if (fs.existsSync(axePath)) {
      await page.evaluate(fs.readFileSync(axePath, 'utf8'));
      const audit = await page.evaluate(async () => await axe.run(document.querySelector('#r-local-import'),
        {runOnly: {type: 'rule', values: ['label']}}));
      assert.deepEqual(audit.violations.map(violation => violation.id), [], 'Source capture controls have accessible labels');
    } else console.log('axe-core unavailable; automated capture-label audit skipped');

    // A simultaneous file and text input is an ambiguity, never discard either.
    await file.setInputFiles({name: 'synthetic.txt', mimeType: 'text/plain', buffer: Buffer.from('FILE CONTENT')});
    await text.fill('UNSAVED TEXT DRAFT');
    await retention.check();
    let posts = [];
    await page.route('**/api/research-ingest', async route => {
      posts.push(route.request().postDataJSON());
      await route.fulfill({json: {ok: true, passages: 1}});
    });
    await button.click();
    await expect(status).toContainText('Choose either');
    assert.equal(posts.length, 0);
    await expect(text).toHaveValue('UNSAVED TEXT DRAFT');
    assert.equal(await file.evaluate(node => node.files.length), 1);
    await text.fill('  \n');
    await button.click();
    await expect(status).toContainText('Choose either');
    await expect(text).toHaveValue('  \n');
    assert.equal(posts.length, 0, 'Even a whitespace-only draft is never silently discarded');
    await text.fill('UNSAVED TEXT DRAFT');
    const clearFile = page.locator('#r-ingest-file-clear');
    await expect(clearFile).toBeEnabled();
    await expect(clearFile).toBeVisible();
    await clearFile.click();
    assert.equal(await file.evaluate(node => node.files.length), 0);
    await expect(clearFile).toBeHidden();
    await expect(text).toHaveValue('UNSAVED TEXT DRAFT');

    // Error/status sits by its action even when the list of sources is long.
    await retention.uncheck();
    await page.evaluate(() => { document.querySelector('#research-sources-list').innerHTML = '<div style="height:2500px">Synthetic sources</div>'; });
    await button.click();
    await expect(status).toContainText('permission');
    const feedback = await status.boundingBox(), action = await button.boundingBox();
    assert.ok(feedback && action && feedback.y - (action.y + action.height) < 60, 'Validation is adjacent to the form action');
    await retention.check();

    // A successful earlier request cannot erase newer edits in the same form.
    let release, started;
    const gate = new Promise(resolve => {release = resolve;}), ready = new Promise(resolve => {started = resolve;});
    await page.unroute('**/api/research-ingest');
    await page.route('**/api/research-ingest', async route => {
      posts.push(route.request().postDataJSON()); started(); await gate;
      await route.fulfill({json: {ok: true, passages: 1}});
    });
    await text.fill('FIRST DRAFT');
    await button.click(); await ready;
    await text.fill('NEWER DRAFT DURING SAVE');
    release();
    await expect(button).toBeEnabled();
    await expect(text).toHaveValue('NEWER DRAFT DURING SAVE');
    assert.equal(posts.at(-1).content, 'FIRST DRAFT');
    await page.unroute('**/api/research-ingest');

    // A response from a former project must not clear the active view's draft.
    let finishOld, oldStarted;
    const oldGate = new Promise(resolve => {finishOld = resolve;}), oldReady = new Promise(resolve => {oldStarted = resolve;});
    await page.route('**/api/research-ingest', async route => {
      posts.push(route.request().postDataJSON()); oldStarted(); await oldGate;
      await route.fulfill({json: {ok: true, passages: 1}});
    });
    await text.fill('DRAFT BEFORE PROJECT SWITCH');
    await button.click(); await oldReady;
    const originalToken = await page.locator('#research-manager').getAttribute('data-research-token');
    await page.locator('#research-manager').evaluate(node => node.dataset.researchToken = 'synthetic-next-project');
    await text.fill('DRAFT IN CURRENT VIEW');
    finishOld();
    await expect(button).toBeEnabled();
    await expect(text).toHaveValue('DRAFT IN CURRENT VIEW');
    await expect(status).toBeEmpty();
    await page.locator('#research-manager').evaluate((node, original) => node.dataset.researchToken = original, originalToken || '');
    await page.unroute('**/api/research-ingest');

    await page.route('**/api/research-ingest', route => route.fulfill({status: 503, json: {ok: false, message: 'Synthetic import failure'}}));
    await button.click();
    await expect(button).toBeEnabled();
    await expect(status).toContainText('Synthetic import failure');
    await expect(text).toHaveValue('DRAFT IN CURRENT VIEW');
    assert.equal(await retention.isChecked(), true, 'Failed save keeps consent and all draft input');
    await page.unroute('**/api/research-ingest');

    // File reading is pending before network: duplicate clicks, failure and
    // project changes must never initiate a second or misdirected import.
    await text.fill('');
    await file.setInputFiles({name: 'synthetic.txt', mimeType: 'text/plain', buffer: Buffer.from('FILE CONTENT')});
    await page.evaluate(() => {
      window.NativeAuditReader = window.FileReader;
      window.auditReaders = [];
      window.FileReader = class {constructor() { window.auditReaders.push(this); } readAsText() {} readAsDataURL() {} };
    });
    await page.route('**/api/research-ingest', async route => {posts.push(route.request().postDataJSON()); await route.fulfill({json: {ok: true}});});
    await button.click();
    await expect(button).toBeDisabled();
    await button.dispatchEvent('click');
    assert.equal(await page.evaluate(() => auditReaders.length), 1, 'Double activation starts one file read');
    const before = posts.length;
    await page.evaluate(() => auditReaders[0].onerror());
    await expect(button).toBeEnabled();
    await expect(status).toContainText('could not be read');
    assert.equal(posts.length, before);
    assert.equal(await file.evaluate(node => node.files.length), 1, 'Read error retains the chosen file');

    await button.click();
    await retention.uncheck();
    await page.evaluate(() => { const reader = auditReaders.at(-1); reader.result = 'FILE CONTENT'; reader.onload(); });
    await expect(button).toBeEnabled();
    await expect(status).toContainText('permission');
    assert.equal(posts.length, before, 'Revoked consent stops the upload before posting');
    await retention.check();

    await button.click();
    await file.setInputFiles({name: 'replacement.txt', mimeType: 'text/plain', buffer: Buffer.from('REPLACEMENT')});
    await page.evaluate(() => { const reader = auditReaders.at(-1); reader.result = 'FILE CONTENT'; reader.onload(); });
    await expect(button).toBeEnabled();
    await expect(status).toContainText('selected file changed');
    assert.equal(posts.length, before, 'Changing a file during reading cancels the previous upload');

    await button.click();
    const token = await page.locator('#research-manager').getAttribute('data-research-token');
    await page.locator('#research-manager').evaluate(node => node.dataset.researchToken = 'synthetic-other-project');
    await page.evaluate(() => { const reader = auditReaders.at(-1); reader.result = 'FILE CONTENT'; reader.onload(); });
    await expect(button).toBeEnabled();
    assert.equal(posts.length, before, 'A changed project cancels the pending read before posting');
    await page.locator('#research-manager').evaluate((node, original) => node.dataset.researchToken = original, token || '');
    await page.evaluate(() => {window.FileReader = NativeAuditReader;});
    await page.unroute('**/api/research-ingest');

    // Real file reads send the submitted bytes and clear only an unchanged success.
    await page.route('**/api/research-ingest', async route => {posts.push(route.request().postDataJSON()); await route.fulfill({json: {ok: true, passages: 1}});});
    await file.setInputFiles({name: 'synthetic.txt', mimeType: 'text/plain', buffer: Buffer.from('FILE CONTENT')});
    await button.click();
    await expect(button).toBeEnabled();
    await expect(status).toContainText('saved');
    assert.equal(posts.at(-1).content, 'FILE CONTENT');
    assert.equal(await file.evaluate(node => node.files.length), 0);
    assert.equal(await retention.isChecked(), false);
    await file.setInputFiles({name: 'synthetic.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-synthetic')});
    await retention.check();
    await button.click();
    await expect(button).toBeEnabled();
    await expect(status).toContainText('saved');
    assert.equal(posts.at(-1).content_base64, Buffer.from('%PDF-synthetic').toString('base64'));
    assert.equal(await file.evaluate(node => node.files.length), 0);
    assert.equal(await retention.isChecked(), false);
    await expect(clearFile).toBeHidden();
    await page.unroute('**/api/research-ingest');

    let finishFile, fileStarted;
    const fileGate = new Promise(resolve => {finishFile = resolve;}), fileReady = new Promise(resolve => {fileStarted = resolve;});
    await page.route('**/api/research-ingest', async route => {
      posts.push(route.request().postDataJSON()); fileStarted(); await fileGate;
      await route.fulfill({json: {ok: true, passages: 1}});
    });
    await file.setInputFiles({name: 'same-name.txt', mimeType: 'text/plain', buffer: Buffer.from('ORIGINAL BYTES')});
    await retention.check();
    await button.click(); await fileReady;
    await file.setInputFiles({name: 'same-name.txt', mimeType: 'text/plain', buffer: Buffer.from('NEW BYTES')});
    finishFile();
    await expect(button).toBeEnabled();
    assert.equal(posts.at(-1).content, 'ORIGINAL BYTES');
    assert.equal(await file.evaluate(async node => node.files[0].text()), 'NEW BYTES',
      'Replacing a file with the same name during save preserves the newer selection');
    assert.equal(await retention.isChecked(), true);
    await page.unroute('**/api/research-ingest');

    // A Zotero-only archive must still permit manual local captures.
    await page.route('**/api/research/sources*', async route => {
      const response = await route.fetch(), data = await response.json();
      if (Array.isArray(data.sources)) data.sources = [{id: 'synthetic-zotero', title: 'Synthetic Zotero source',
        context: {external_reference: {library: 'users/0', item_key: 'SYNTHETIC'}}, passages: 1, byte_length: 50, tags: []}];
      await route.fulfill({response, json: data});
    });
    await page.locator('[data-rtab=sources]').click();
    await expect(page.locator('#research-sources-list')).toContainText('Synthetic Zotero source');
    await expect(page.locator('#r-local-import')).toBeVisible();
    await page.close();
    console.log(`Research import: explicit input choice, pending draft safety, consent, file errors, project isolation and Zotero coexistence passed. Screenshots: ${artifacts}`);
  } finally {if (browser) await browser.close(); server.kill('SIGTERM');}
})().catch(error => {console.error(error); process.exitCode = 1;});
