// Real native HTTP/browser saves retain synthetic quotes without changing prose.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn, spawnSync} = require('node:child_process');
const {once} = require('node:events');
const {createInterface} = require('node:readline');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const root = path.resolve(__dirname, '../..');
const python = process.env.PYTHON_BIN || path.join(root, '.venv/bin/python');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-manuscript-links-native-'));

async function selectQuote(paragraph, quote) {
  await paragraph.evaluate((element, selectedQuote) => {
    const startOffset = element.textContent.indexOf(selectedQuote);
    if (startOffset < 0) throw new Error('Synthetic quote is absent from the rendered paragraph');
    const endOffset = startOffset + selectedQuote.length;
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    let offset = 0, first = null, last = null;
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!first && startOffset >= offset && startOffset < offset + node.length) {
        first = [node, startOffset - offset];
      }
      if (endOffset > offset && endOffset <= offset + node.length) {
        last = [node, endOffset - offset];
      }
      offset += node.length;
    }
    if (!first || !last || first[0] === last[0]) {
      throw new Error('The native selection must span safe text nodes around the search mark');
    }
    const range = document.createRange();
    range.setStart(...first); range.setEnd(...last);
    const selection = window.getSelection();
    selection.removeAllRanges(); selection.addRange(range);
    document.dispatchEvent(new Event('selectionchange'));
    if (selection.toString() !== selectedQuote) throw new Error('Range did not preserve the exact quote');
  }, quote);
}

(async () => {
  const server = spawn(python, ['-u', '-c', `
import hashlib, json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.pipeline import paragraph_identity, profile_document, resolve_document_config
from lixity.research import api
from lixity.research.repository import Repository
from lixity.server import LixityServerHandler
from lixity.style_fingerprint import FingerprintThresholds
project = Path(sys.argv[1]) / 'synthetic-project'
api.init(project, title='Synthetic native manuscript links')
claim = api.create_claim(project, title='Synthetic current claim', statement='An author association for synthetic review.')
current = api.get_record(project, 'claim', claim['claim_id'])
api.revise_record(project, 'claim', claim['claim_id'], changes={'statement': 'Reviewed synthetic claim version.'},
    expected_snapshot=current['snapshot'], expected_revision=1, change_kind='correction', reason='Synthetic reviewed version')
quotes = [
    'The selected sentence <img src=x onerror=window.nativeLinkInjected=true> stays inert.',
    'Another selected sentence <img src=x onerror=window.nativeLinkInjected=true> stays inert.',
]
manuscript = project / 'manuscript.md'
text = '# Synthetic native manuscript\\n\\n## First chapter\\n\\nA😀 ' + quotes[0] + ' A bird crosses the garden.\\n\\n## Second chapter\\n\\nB😀 ' + quotes[1] + ' The rain begins softly.\\n'
manuscript.write_text(text, encoding='utf-8')
config, _ = resolve_document_config(text, 'en')
paragraphs = profile_document(text, config, FingerprintThresholds())[0]
selections = []
for quote in quotes:
    paragraph = next(p for p in paragraphs if quote in p.text)
    start = paragraph.text.index(quote)
    selections.append({**paragraph_identity(paragraph), 'start': start, 'end': start + len(quote), 'quote': quote})
initial = Repository(project).snapshot()
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.research_dir = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.exports_dir = str(Path(sys.argv[1]) / 'exports')
LixityServerHandler.language = 'en'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'project': str(project),
    'manuscript': str(manuscript), 'source_sha256': hashlib.sha256(manuscript.read_bytes()).hexdigest(),
    'project_id': initial.project.id, 'initial_archive_schema': initial.manifest.schema_version,
    'claim_id': claim['claim_id'], 'selections': selections}), flush=True)
server.serve_forever()
`, artifacts], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, stdio: ['ignore', 'pipe', 'pipe']});
  const lines = createInterface({input: server.stdout});
  let stderr = '', browser;
  server.stderr.on('data', data => {stderr = (stderr + data).slice(-5000);});
  try {
    const fixture = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Synthetic server startup timed out: ' + stderr)), 15000);
      lines.once('line', line => {clearTimeout(timer); resolve(JSON.parse(line));});
      server.once('error', error => {clearTimeout(timer); reject(error);});
      server.once('exit', code => {clearTimeout(timer); reject(new Error(`Synthetic server exited ${code}: ${stderr}`));});
    });
    assert.equal(fixture.initial_archive_schema, 'research-manifest-local/2', 'Fixture starts without manuscript-link storage');
    const originalBytes = fs.readFileSync(fixture.manuscript);
    browser = await launchChromium();
    for (const [index, width] of [1440, 320].entries()) {
      const page = await browser.newPage({viewport: {width, height: 1000}});
      page.setDefaultTimeout(10000);
      const errors = [], writes = [], reads = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => {
        if (['error', 'warning'].includes(message.type())) errors.push(message.text());
      });
      page.on('request', request => {
        const url = new URL(request.url());
        assert.equal(url.origin, fixture.url, 'Native workflow makes only disposable loopback requests');
        if (request.method() === 'POST') writes.push(url.pathname);
        if (url.pathname === '/api/research/manuscript-review') reads.push(url);
      });
      await page.goto(fixture.url);
      assert.match(await page.title(), /^Synthetic native manuscript/);
      assert.ok((await page.locator('body').innerText()).includes('Synthetic native manuscript'));
      await page.locator('#tab-view-analysis').click();
      const selection = fixture.selections[index];
      const panel = page.locator(`#chapters .ptext[data-start="${selection.start_line}"]`);
      const panelId = await panel.getAttribute('id');
      const chip = page.locator(`#chapters .chip[data-target="${panelId}"]`);
      await chip.click();
      const paragraph = panel.locator('.ptext-inner > p');
      await expect(paragraph).toContainText(selection.quote);
      // Search produces a real safe mark: Range then crosses its text nodes.
      await page.locator('#text-search').fill('selected sentence');
      await expect(page.locator('#text-search-status')).toContainText('2 matches');
      if (index === 1) await page.locator('#text-search').press('Enter');
      await expect(paragraph.locator('mark.text-hit')).toHaveText('selected sentence');
      await expect(page.locator('#text-search')).toHaveValue('selected sentence');
      assert.ok(await page.locator('#text-search').evaluate(element => element.getBoundingClientRect().width >= 100),
        'The native search field keeps a readable input width');
      await page.locator('#text-search').scrollIntoViewIfNeeded();
      await page.screenshot({path: path.join(artifacts, `search-${width}.png`)});
      await selectQuote(paragraph, selection.quote);
      await panel.locator('[data-manuscript-link-selection]').click();
      const dialog = page.locator('#manuscript-link-dialog');
      await expect(dialog).toBeVisible();
      await expect(page.locator('#manuscript-link-claim')).toBeEnabled();
      await page.locator('#manuscript-link-claim').selectOption(fixture.claim_id);
      await expect(page.locator('#manuscript-link-statement')).toHaveText('Reviewed synthetic claim version.');
      await expect(page.locator('#manuscript-link-quote')).toHaveText(selection.quote);
      await expect(page.locator('#manuscript-link-save')).toBeDisabled();
      assert.deepEqual(writes, [], 'Opening a quote/claim draft writes nothing');
      assert.equal(await dialog.locator('img').count(), 0, 'Quote preview contains inert text');
      await page.locator('#manuscript-link-retain').check();
      await expect(page.locator('#manuscript-link-save')).toBeEnabled();
      await dialog.screenshot({path: path.join(artifacts, `dialog-${width}.png`)});
      const layout = await page.evaluate(() => ({
        viewport: innerWidth, width: document.documentElement.scrollWidth,
        overflow: Array.from(document.querySelectorAll('body *')).filter(element => {
          const rect = element.getBoundingClientRect();
          return rect.width && (rect.right > innerWidth + 1 || rect.left < -1);
        }).slice(0, 12).map(element => ({tag: element.tagName, id: element.id, className: element.className,
          left: element.getBoundingClientRect().left, right: element.getBoundingClientRect().right})),
      }));
      assert.ok(layout.width <= layout.viewport, 'Native dialog fits the viewport: ' + JSON.stringify(layout));
      const savedResponse = page.waitForResponse(response => response.url() === fixture.url + '/api/research-manuscript-link' && response.request().method() === 'POST');
      await page.locator('#manuscript-link-save').click();
      const response = await savedResponse;
      assert.equal(response.status(), 200);
      const saved = await response.json();
      assert.equal(saved.ok, true);
      assert.equal(saved.schema_version, 'research-manuscript-link-local/1');
      assert.equal(saved.archive_schema_version, 'research-manifest-local/7');
      assert.equal(saved.claim_id, fixture.claim_id);
      assert.equal(saved.claim_revision, 2, 'Native save pins the selected current version');
      assert.deepEqual(Object.fromEntries(Object.keys(selection).map(key => [key, saved.record.anchor[key]])), selection);
      assert.equal(saved.record.anchor.start, 3, 'Astral emoji prefix uses codepoints, not UTF-16 offsets');
      assert.equal(saved.record.anchor.retention_confirmed, true);
      assert.equal(saved.record.anchor.source_sha256, fixture.source_sha256);
      await expect(dialog).not.toBeVisible();
      await expect(paragraph.locator('mark.manuscript-claim-hit.text-hit')).toHaveText('selected sentence');
      assert.equal((await paragraph.locator('mark.manuscript-claim-hit').allTextContents()).join(''), selection.quote,
        'Source and search marks compose without changing the selected text');
      const tokens = await page.evaluate(() => ({
        research: document.querySelector('#research-manager').dataset.researchToken,
        project: document.querySelector('#manuscript-pdf-form').dataset.projectToken,
      }));
      const reportResponse = await page.request.get(fixture.url + '/api/research/manuscript-review?' + new URLSearchParams({research_token: tokens.research, project_token: tokens.project}));
      assert.equal(reportResponse.status(), 200);
      const report = await reportResponse.json();
      assert.equal(report.schema_version, 'research-manuscript-review-local/1');
      assert.equal(report.links.length, index + 1, 'Native review reads persisted associations');
      const row = report.links.find(link => link.link_id === saved.link_id);
      assert.equal(row.claim_revision, 2);
      assert.equal(row.anchor_state, 'resolved');
      assert.deepEqual(row.flags, []);
      assert.equal(row.anchor.quote, selection.quote);
      assert.equal(row.resolved_start_line, selection.start_line);
      assert.equal(report.current_source_sha256, fixture.source_sha256);
      assert.ok(reads.every(url => url.searchParams.get('research_token') && url.searchParams.get('project_token')),
        'Native review calls send both real selected-context tokens');
      await page.locator('#text-search').press('Escape');
      await chip.click();
      await expect(panel).not.toHaveClass(/\bopen\b/);
      await chip.click();
      await expect(panel).toHaveClass(/\bopen\b/);
      await expect(paragraph.locator('mark.manuscript-claim-hit')).toHaveText(selection.quote);
      assert.equal(await page.locator('#chapters img').count(), 0);
      assert.equal(await page.evaluate(() => Boolean(window.nativeLinkInjected)), false);
      assert.deepEqual(writes, ['/api/research-manuscript-link'], 'Only explicit Save publishes a write');
      assert.deepEqual(fs.readFileSync(fixture.manuscript), originalBytes, 'Native association never changes manuscript bytes');
      assert.equal(crypto.createHash('sha256').update(fs.readFileSync(fixture.manuscript)).digest('hex'), fixture.source_sha256);
      await panel.screenshot({path: path.join(artifacts, `resolved-${width}.png`)});
      assert.deepEqual(errors, []);
      await page.close();
    }
    const persisted = spawnSync(python, ['-c', `
import json, sys
from lixity.research import api
from lixity.research.repository import Repository
snapshot = Repository(sys.argv[1]).snapshot()
links = api.list_manuscript_links(sys.argv[1])
print(json.dumps({'schema': snapshot.manifest.schema_version, 'links': links['links']}))
`, fixture.project], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8'});
    assert.equal(persisted.status, 0, persisted.stderr);
    const accepted = JSON.parse(persisted.stdout);
    assert.equal(accepted.schema, 'research-manifest-local/7');
    assert.equal(accepted.links.length, 2, 'Fresh repository reads validate both persisted quote records');
    assert.deepEqual(accepted.links.map(link => link.anchor.quote).sort(), fixture.selections.map(selection => selection.quote).sort());
    console.log('Native manuscript links: real rendered dashboard and HTTP writes/review, desktop/mobile, retention, exact quote/codepoint/version pins, storage7, inert text, search/lazy marks and unchanged manuscript passed. Screenshots: ' + artifacts);
  } finally {
    if (browser) await browser.close();
    server.kill('SIGTERM');
    await Promise.race([once(server, 'exit'), new Promise(resolve => setTimeout(resolve, 3000))]);
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
