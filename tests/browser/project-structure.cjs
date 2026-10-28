// Explicit, read-only project inspection keeps sources and outputs separate.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-project-structure-'));
const token = 'a'.repeat(64), nextToken = 'b'.repeat(64);
const fixtures = pythonFixture(String.raw`
import json
from lixity.language import get_language_profile
from lixity.pipeline import analyze_document, resolve_document_config
from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui import render_dashboard
from lixity.workspace_labels import WORKSPACE_LABELS
text = '## Synthetic chapter\n\nThe keeper waits beside the quiet river.\n'
config, _ = resolve_document_config(text, 'en')
analysis = analyze_document(text, config, FingerprintThresholds())
result = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    options = dict(controls=True, project_overview_enabled=True, project_token='a'*64,
                   labels=labels, language_key=locale, title='Synthetic project overview',
                   enabled_actions=('analyze',), research_context_token='c'*64,
                   site_publication_context_token='c'*64)
    result[locale] = {'labels': labels,
        'html': render_dashboard(analysis.chapters, analysis.paragraphs, **options)}
result['readonly'] = render_dashboard(analysis.chapters, analysis.paragraphs, **{**options, 'read_only':True})
print(json.dumps(result))
`);

function report(root = '/Synthetic project') {
  return {schema_version: 'lixity-project-structure/1', ok: true, has_errors: false, root,
    roles: [
      {role: 'manuscript', path: 'drafts/manuscript.md', state: 'available'},
      {role: 'research', path: 'research', state: 'available'},
      {role: 'outputs', path: 'exports', state: 'available'},
      {role: 'output_archive', path: 'exports/archive', state: 'missing'},
      {role: 'submissions', path: null, state: 'unassigned'},
    ],
    artifacts: [
      {name: 'Synthetic #1 %.pdf', path: 'exports/Synthetic #1 %.pdf', size_bytes: 0,
        provenance: 'unknown', downloadable: true},
      {name: '<img src=x onerror=alert(1)>.pdf', path: 'exports/<img src=x onerror=alert(1)>.pdf',
        size_bytes: null, provenance: 'unknown', downloadable: false},
      {name: 'Synthetic backup.tar.gz', path: 'exports/Synthetic backup.tar.gz', size_bytes: 123,
        provenance: 'unknown', downloadable: false},
    ], issues: [], truncated: false};
}

async function settled(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function mockedFlows(browser) {
  for (const locale of ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl']) for (const width of [1440, 320]) {
    const page = await browser.newPage({viewport: {width, height: 960}, reducedMotion: 'reduce'});
    page.setDefaultTimeout(5000);
    const reads = [], writes = [], errors = [];
    let response = report(), failure = false, hold = null;
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (['error', 'warning'].includes(message.type())) errors.push(message.text()); });
    page.on('request', request => { if (request.method() !== 'GET') writes.push(request.url()); });
    await page.route('http://localhost/**', async route => {
      if (route.request().url().includes('/api/project-structure?')) {
        reads.push(new URL(route.request().url()).searchParams.get('project_token'));
        const payload = response;
        if (hold) await hold;
        await route.fulfill({status: failure ? 500 : 200, json: failure ? {ok: false} : payload}).catch(() => {});
      } else if (route.request().url().includes('/api/')) {
        await route.fulfill({json: {ok: false, initialized: false}});
      } else await route.fulfill({contentType: 'text/html', body: fixtures[locale].html});
    });
    try {
      await page.goto('http://localhost/');
      assert.match(await page.title(), /Synthetic project overview/);
      await settled(page);
      assert.deepEqual(reads, [], 'No project inventory is fetched while reading the manuscript');
      await page.locator('#tab-view-project').focus(); await page.keyboard.press('Enter');
      await page.locator('#project-overview-body:not([hidden])').waitFor();
      assert.deepEqual(reads, [token]);
      const overview = page.locator('#project-overview'), labels = fixtures[locale].labels;
      assert.equal(await overview.locator('h3').textContent(), labels.project_structure_title);
      assert.equal(await overview.locator('.project-overview-columns > section').count(), 2);
      assert.ok((await overview.textContent()).includes(labels.project_structure_provenance_unknown));
      assert.ok((await overview.textContent()).includes('<img src=x onerror=alert(1)>.pdf'));
      assert.equal(await overview.locator('img').count(), 0);
      const fileBrowser = overview.locator('.project-overview-browser');
      assert.equal(await fileBrowser.getAttribute('open'), null, 'The output inventory is collapsed initially');
      await fileBrowser.locator('summary').first().click();
      assert.equal(await fileBrowser.locator('.project-overview-output-group').count(), 2);
      assert.equal(await fileBrowser.locator('.project-overview-output-group[open]').count(), 0);
      const search = fileBrowser.locator('input[type=search]');
      await search.fill('backup');
      assert.equal(await fileBrowser.locator('.project-overview-output-group:visible').count(), 1);
      assert.equal(await fileBrowser.locator('.project-overview-row:visible').count(), 1);
      assert.ok((await fileBrowser.locator('.project-overview-row:visible').textContent()).includes('Synthetic backup.tar.gz'));
      await search.fill('nothing matches this');
      assert.ok(await fileBrowser.getByText(labels.project_structure_output_no_matches).isVisible());
      await search.fill('');
      const link = overview.locator('.project-overview-artifacts a');
      assert.equal(await link.count(), 1);
      assert.equal(await link.getAttribute('href'), '/artifact/' + encodeURIComponent('Synthetic #1 %.pdf') + '?project_token=' + token);
      assert.ok((await overview.textContent()).includes('0 B'), 'A measured zero-byte output remains zero');
      assert.equal(await page.locator('.artifacts').count(), 0, 'There is no duplicate generated-file list');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await overview.screenshot({path: path.join(artifacts, `${locale}-${width}.png`)});
      await page.locator('#tab-view-project').click();
      await page.waitForFunction(() => document.getElementById('project-overview').getAttribute('aria-busy') !== 'true');
      assert.equal(reads.length, 2, 'Each explicit activation inspects again');

      if (locale === 'en') {
        failure = true;
        await page.locator('#project-overview-refresh').click();
        await page.waitForFunction(text => document.getElementById('project-overview-status').textContent === text, labels.project_structure_failed);
        assert.equal(await page.locator('#project-overview-body').isHidden(), true, 'Failed reads never look like empty results');
        failure = false;
        response = {...report(), has_errors: true, truncated: true,
          issues: [{code: 'output-source-alias', severity: 'error', path: 'exports/source.pdf'},
                   {code: 'inventory-truncated', severity: 'warning', path: 'exports'}]};
        await page.locator('#project-overview-refresh').click();
        await page.locator('#project-overview-body:not([hidden])').waitFor();
        assert.ok((await overview.textContent()).includes(labels.project_structure_issue_source_output));
        assert.ok((await overview.textContent()).includes(labels.project_structure_issue_limited));
        let release;
        hold = new Promise(resolve => { release = resolve; });
        response = report('/Stale project');
        await page.locator('#project-overview-refresh').click();
        await page.waitForFunction(() => document.getElementById('project-overview').getAttribute('aria-busy') === 'true');
        await page.locator('#settings-form').evaluate((form, value) => { form.dataset.projectToken = value; }, nextToken);
        release(); hold = null;
        await page.waitForFunction(() => document.getElementById('project-overview').getAttribute('aria-busy') !== 'true');
        assert.equal(await page.locator('#project-overview-body').isHidden(), true);
        assert.ok(!(await overview.textContent()).includes('/Stale project'));
        response = report('/Fresh project');
        await page.locator('#project-overview-refresh').click();
        await page.waitForFunction(() => document.getElementById('project-overview-body').textContent.includes('/Fresh project'));
        assert.equal(reads.at(-1), nextToken, 'Retry uses the live settings token');
        assert.ok((await link.getAttribute('href')).endsWith('?project_token=' + nextToken));
      }
      assert.deepEqual(writes, []);
      assert.deepEqual(errors, locale === 'en'
        ? ['Failed to load resource: the server responded with a status of 500 (Internal Server Error)'] : []);
    } finally { await page.close(); }
  }
  const page = await browser.newPage();
  let reads = 0;
  await page.route('http://localhost/**', route => {
    if (route.request().url().includes('/api/project-structure')) reads++;
    return route.fulfill({contentType: 'text/html', body: fixtures.readonly});
  });
  try {
    await page.goto('http://localhost/');
    await page.evaluate(() => switchActiveView('project'));
    assert.equal(await page.locator('#project-overview').count(), 0);
    assert.equal(await page.locator('#view-pane-project.active').count(), 0);
    assert.equal(reads, 0);
  } finally { await page.close(); }
}

async function nativeFlows(browser) {
  const server = await startNativeServer(String.raw`
import json, sys, threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
base = Path(sys.argv[1]); projects = {}
for name in ('Alpha', 'Beta'):
    project = base / name.lower()
    api.init(project, title=name)
    manuscript = project / 'drafts' / 'manuscript.md'; manuscript.parent.mkdir()
    manuscript.write_text('## Synthetic chapter\n\nThe keeper watches the quiet river.\n', encoding='utf-8')
    (project / 'lixity.toml').write_text('title = "' + name + '"\nlanguage = "en"\nmanuscript = "drafts/manuscript.md"\n', encoding='utf-8')
    exports = project / 'exports'; (exports / 'archive').mkdir(parents=True)
    (exports / 'Synthetic #1 %.pdf').write_bytes(b'%PDF synthetic ' + name.encode())
    (exports / 'source-copy.md').hardlink_to(manuscript)
    api.create_dossier(project, title=name + ' synthetic dossier', body='Synthetic retained notes only.')
    projects[name] = {'root': str(project), 'manuscript': str(manuscript)}
alpha = projects['Alpha']
LixityServerHandler.workspace_root = alpha['root']; LixityServerHandler.research_dir = alpha['root']
LixityServerHandler.source_input = alpha['manuscript']; LixityServerHandler.exports_dir = str(base / 'alpha' / 'exports')
LixityServerHandler.language = 'en'; LixityServerHandler.refresh()
class DifferentArchive(LixityServerHandler):
    workspace_root = alpha['root']
    source_input = alpha['manuscript']
    exports_dir = str(base / 'alpha' / 'exports')
    research_dir = projects['Beta']['root']
DifferentArchive.refresh()
different = ThreadingHTTPServer(('127.0.0.1', 0), DifferentArchive)
threading.Thread(target=different.serve_forever, daemon=True).start()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}',
    'different_url': f'http://127.0.0.1:{different.server_port}', 'projects': projects}), flush=True)
server.serve_forever()
`, artifacts);
  function filesIn(directory) {
    return fs.readdirSync(directory, {withFileTypes: true}).flatMap(entry => {
      const file = path.join(directory, entry.name);
      return entry.isDirectory() ? filesIn(file) : [file];
    });
  }
  const originals = new Map(Object.values(server.fixture.projects).flatMap(project => filesIn(project.root))
    .map(file => [file, fs.readFileSync(file)]));
  try {
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 1000}, reducedMotion: 'reduce'});
      page.setDefaultTimeout(10000);
      const errors = [], writes = [], reads = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => { if (['error', 'warning'].includes(message.type())) errors.push(message.text()); });
      try {
        const reset = await page.request.post(server.fixture.url + '/api/project-open', {data: {path: server.fixture.projects.Alpha.root}});
        assert.equal(reset.status(), 200);
        page.on('request', request => {
          const url = new URL(request.url());
          assert.equal(url.origin, server.fixture.url, 'All native requests use the disposable loopback fixture');
          if (request.method() !== 'GET') writes.push(url.pathname);
          if (url.pathname === '/api/project-structure') reads.push(url);
        });
        await page.goto(server.fixture.url);
        await page.locator('.manuscript-link-review .ctl-note').first().waitFor({state: 'attached'});
        assert.deepEqual(reads, [], 'Native reading does not inspect project folders in the background');
        await page.locator('#tab-view-project').click();
        await page.locator('#project-overview-body:not([hidden])').waitFor();
        const overview = page.locator('#project-overview');
        assert.ok((await overview.textContent()).includes(server.fixture.projects.Alpha.root));
        assert.ok((await overview.textContent()).includes('drafts/manuscript.md'));
        const outputs = overview.locator('.project-overview-artifacts a');
        assert.equal(await outputs.count(), 1, 'The source hardlink is listed without an output link');
        const href = await outputs.getAttribute('href');
        const downloaded = await page.request.get(server.fixture.url + href);
        assert.equal(downloaded.status(), 200);
        assert.equal((await downloaded.body()).toString(), '%PDF synthetic Alpha', 'The filename is URL-decoded exactly once');
        const oldToken = new URL(server.fixture.url + href).searchParams.get('project_token');
        assert.equal(oldToken, await page.locator('#settings-form').getAttribute('data-project-token'));
        await overview.locator('[data-project-role="manuscript"] button').click();
        assert.equal(await page.locator('#view-pane-analysis.active').count(), 1);
        await page.locator('#tab-view-project').click();
        await page.locator('#project-overview-body:not([hidden])').waitFor();
        await overview.locator('[data-project-role="research"] button').click();
        assert.equal(await page.locator('#view-pane-research.active').count(), 1);
        await page.waitForFunction(() => document.querySelector('#research-tabs [data-rtab="dossiers"]').getAttribute('aria-selected') === 'true');
        await page.waitForFunction(() => document.getElementById('rtab-dossiers').textContent.includes('Alpha synthetic dossier'));
        await page.locator('#tab-view-project').click();
        await page.locator('#project-overview-body:not([hidden])').waitFor();
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        await overview.screenshot({path: path.join(artifacts, `native-${width}.png`)});
        assert.deepEqual(writes, [], 'Overview inspection, navigation and existing downloads write no project state');
        const opened = await page.request.post(server.fixture.url + '/api/project-open', {data: {path: server.fixture.projects.Beta.root}});
        assert.equal(opened.status(), 200);
        const stale = await page.request.get(server.fixture.url + href);
        assert.equal(stale.status(), 409, 'A formerly visible output link cannot read a newly selected project');
        const staleOverview = await page.request.get(server.fixture.url + '/api/project-structure?project_token=' + oldToken);
        assert.equal(staleOverview.status(), 409);
        await page.reload();
        await page.locator('#tab-view-project').click();
        await page.locator('#project-overview-body:not([hidden])').waitFor();
        assert.ok((await overview.textContent()).includes(server.fixture.projects.Beta.root));
        assert.ok(!(await overview.textContent()).includes(server.fixture.projects.Alpha.root));
        assert.deepEqual(errors, []);
      } finally { await page.close(); }
    }
    const different = await browser.newPage();
    different.setDefaultTimeout(10000);
    try {
      await different.goto(server.fixture.different_url);
      await different.locator('#tab-view-project').click();
      await different.locator('#project-overview-body:not([hidden])').waitFor();
      const button = different.locator('[data-project-role="research"] button');
      assert.equal(await button.isDisabled(), true, 'A different selected Research archive cannot be opened as this project’s archive');
      assert.equal(await button.getAttribute('data-switch-view'), null);
      assert.ok((await different.locator('[data-project-role="research"]').textContent()).includes(fixtures.en.labels.project_structure_research_context));
    } finally { await different.close(); }
    for (const [file, bytes] of originals) assert.deepEqual(fs.readFileSync(file), bytes, 'Read-only inspection preserves synthetic project bytes: ' + file);
    assert.deepEqual(Object.values(server.fixture.projects).flatMap(project => filesIn(project.root)).sort(), [...originals.keys()].sort());
  } finally { await server.close(); }
}

(async () => {
  const browser = await launchChromium();
  try { await mockedFlows(browser); await nativeFlows(browser); }
  finally { await browser.close(); }
  console.log('Project structure: seven-locale desktop/mobile explicit reads, separate sources/outputs, retry, stale-token rejection, keyboard and read-only isolation; native source navigation, encoded output downloads, project switch and read-only project bytes passed. ' + artifacts);
})().catch(error => { console.error(error); process.exitCode = 1; });
