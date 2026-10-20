// Asynchronous annotations preserve exact native selections in the shared reader.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const root = path.resolve(__dirname, '../..');
const quote = '😀 A synthetic selected sentence [literal.*+?]';
const fixture = pythonFixture(`
import json
from dashboard_fixtures import full_dashboard as render
render.__globals__['SAMPLE'] = render.__globals__['SAMPLE'].replace(
    'Ich trinke Kaffee.', '😀 A synthetic selected sentence [literal.*+?].', 1)
original = render.__globals__['render_dashboard']
def configured(*args, **kwargs):
    return original(*args, **{**kwargs, 'language_key': 'en',
        'enabled_actions': ['analyze', 'research-reader', 'research-manuscript-link'],
        'manuscript_pdf_token': 'synthetic-project-token',
        'research_context_token': 'synthetic-research-token',
        'manuscript_source_sha256': 'a' * 64})
render.__globals__['render_dashboard'] = configured
print(json.dumps(render()))
`, {root});

async function select(page, backwards = false) {
  await page.locator('#chapters .ptext-inner > p').first().evaluate((paragraph, value) => {
    const text = paragraph.textContent, start = text.indexOf(value.quote);
    if (start < 0) throw new Error('Synthetic quote is absent');
    const walker = document.createTreeWalker(paragraph, NodeFilter.SHOW_TEXT), nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    function point(at) {
      for (const node of nodes) {
        if (at <= node.length) return [node, at];
        at -= node.length;
      }
      throw new Error('Selection offset lies outside the paragraph');
    }
    const from = point(start), to = point(start + value.quote.length), selection = getSelection();
    selection.setBaseAndExtent(...(value.backwards ? to : from), ...(value.backwards ? from : to));
    document.dispatchEvent(new Event('selectionchange'));
  }, {quote, backwards});
}

async function verifyArchiveLifecycle(browser) {
  const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-reader-archive-'));
  const server = await startNativeServer(`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
base = Path(sys.argv[1])
projects = []
for name in ('first', 'second'):
    project = base / name
    project.mkdir()
    source = project / 'manuscript.md'
    source.write_text('# Synthetic archive lifecycle\\n\\n## One\\n\\nA bird crosses a quiet garden.\\n', encoding='utf-8')
    projects.append({'root': str(project), 'source': str(source)})
LixityServerHandler.workspace_root = projects[0]['root']
LixityServerHandler.source_input = projects[0]['source']
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'projects': projects}), flush=True)
server.serve_forever()
`, artifacts);
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
    const errors = [], reviewRequests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => {if (message.type() === 'error') errors.push(message.text());});
    page.on('request', request => {
      if (new URL(request.url()).pathname === '/api/research/manuscript-review') reviewRequests.push(request.url());
    });
    await page.goto(server.fixture.url);
    await page.locator('#tab-view-analysis').click();
    await page.locator('.manuscript-link-review .ctl-status').waitFor({state: 'attached'});
    assert.equal(reviewRequests.length, 0,
      'An uninitialized native project opens continuous reading without requesting an unavailable archive');
    await page.locator('#tab-view-research').click();
    await page.locator('#r-init-title').fill('Synthetic research archive');
    await page.locator('#r-init-btn').click();
    await page.locator('#research-tabs').waitFor({state: 'visible'});
    await page.locator('#tab-view-analysis').click();
    await page.locator('.manuscript-link-review .ctl-note').first().waitFor({state: 'attached'});
    assert.ok(reviewRequests.length > 0, 'Research initialized in the same page becomes readable on return');
    const count = reviewRequests.length;
    const switched = await page.request.post(server.fixture.url + '/api/project-open', {
      data: {path: server.fixture.projects[1].root},
    });
    assert.equal(switched.status(), 200);
    await page.reload();
    await page.locator('#tab-view-analysis').click();
    await page.locator('.manuscript-link-review .ctl-status').waitFor({state: 'attached'});
    assert.equal(reviewRequests.length, count,
      'Switching to a project without an archive does not reuse previous initialization');
    assert.deepEqual(errors, [], 'Expected archive absence creates no browser errors');
    await page.close();
  } finally {await server.close();}
}

(async () => {
  const browser = await launchChromium();
  try {
    await verifyArchiveLifecycle(browser);
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion: 'reduce'});
      const errors = [], writes = [];
      page.on('pageerror', error => errors.push(error.message));
      let releaseReview, observeReview;
      const reviewRequested = new Promise(resolve => {observeReview = resolve;});
      await page.route('http://lixity.test/**', async route => {
        const request = route.request(), url = new URL(request.url());
        if (request.method() !== 'GET') {
          writes.push(url.pathname);
          return route.fulfill({status: 400, json: {ok: false}});
        }
        if (url.pathname === '/api/research/manuscript-review') {
          await new Promise(resolve => {releaseReview = resolve; observeReview();});
          return route.fulfill({json: {ok: true, schema_version: 'research-manuscript-review-local/1',
            project_id: 'synthetic-project', snapshot: 'synthetic-snapshot',
            source_state: 'available', current_source_sha256: 'a'.repeat(64), links: []}});
        }
        if (url.pathname.startsWith('/api/')) return route.fulfill({json: {
          ok: true, initialized: true, project_id: 'synthetic-project', snapshot: 'synthetic-snapshot',
          records: [], sources: [], dossiers: [], claims: [], decisions: [], candidates: [],
        }});
        return route.fulfill({contentType: 'text/html', body: fixture});
      });
      await page.goto('http://lixity.test/');
      await page.locator('#tab-view-analysis').click();
      await select(page);
      await reviewRequested;
      await page.locator('#manuscript-selection-tools').waitFor({state: 'visible'});
      releaseReview();
      await page.locator('#research-manuscript-review .ctl-note').first().waitFor({state: 'attached'});
      assert.equal(await page.evaluate(() => getSelection().toString()), quote,
        'The first selection survives the initial delayed association response');

      const unchanged = await page.locator('#chapters .ptext').first().evaluate(panel => {
        const paragraph = panel.querySelector('.ptext-inner > p'), first = paragraph.firstChild;
        window.LixityManuscriptLinks.marks(panel, []);
        return paragraph.firstChild === first;
      });
      assert.equal(unchanged, true, 'Unchanged annotation spans retain their native text nodes');

      await select(page, true);
      const changed = await page.locator('#chapters .ptext').first().evaluate(panel => {
        const paragraph = panel.querySelector('.ptext-inner > p'), selection = getSelection();
        function offset(node, at) {
          const prefix = document.createRange(); prefix.selectNodeContents(paragraph); prefix.setEnd(node, at);
          return prefix.toString().length;
        }
        const before = {anchor: offset(selection.anchorNode, selection.anchorOffset),
          focus: offset(selection.focusNode, selection.focusOffset), text: selection.toString()};
        window.LixityManuscriptLinks.marks(panel, [{start: 0, end: 8}, {start: 20, end: 30}]);
        return {before, after: {anchor: offset(selection.anchorNode, selection.anchorOffset),
          focus: offset(selection.focusNode, selection.focusOffset), text: selection.toString()},
          marks: paragraph.querySelectorAll('.manuscript-claim-hit').length};
      });
      assert.deepEqual(changed.after, changed.before,
        'Changed mark wrappers preserve backward selection and exact UTF-16 offsets around astral text');
      assert.ok(changed.marks > 0, 'The new annotation is rendered while selection remains intact');
      await page.locator('#manuscript-selection-tools [data-reader-action=link]').click();
      await page.locator('#manuscript-link-dialog[open]').waitFor();
      assert.equal(await page.locator('#manuscript-link-quote').textContent(), quote,
        'The exact preserved selection reaches the existing claim dialog');
      await page.keyboard.press('Escape');
      const crossing = await page.locator('#chapters .ptext').evaluateAll(panels => {
        const paragraphs = panels.slice(0, 2).map(panel => panel.querySelector('.ptext-inner > p'));
        const textNodes = paragraphs.map(paragraph => document.createTreeWalker(paragraph, NodeFilter.SHOW_TEXT).nextNode());
        const selection = getSelection();
        selection.setBaseAndExtent(textNodes[0], 0, textNodes[1], Math.min(12, textNodes[1].length));
        const before = selection.toString();
        panels.slice(0, 2).forEach(panel => window.LixityManuscriptLinks.marks(panel, [{start: 0, end: 5}]));
        return {before, after: selection.toString()};
      });
      assert.ok(crossing.before.length > quote.length);
      assert.equal(crossing.after, crossing.before, 'Annotations preserve selections crossing paragraph boundaries');
      assert.deepEqual(writes, [], 'Opening contextual research does not write manuscript or research data');
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log('Manuscript selections: delayed first review, unchanged nodes, changed annotations, backward astral offsets and claim dialog passed on desktop/mobile.');
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
