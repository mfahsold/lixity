// A native project switch must not carry a former project's startup title into an NDA.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const {createInterface} = require('node:readline');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-project-switch-native-'));

(async () => {
  const server = spawn(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-u', '-c', `
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.research.repository import Repository
from lixity.server import LixityServerHandler
base = Path(sys.argv[1])
projects = {}
for name in ('Alpha', 'Beta'):
    project = base / name.lower()
    api.init(project, title=name)
    config = project / 'lixity.toml'
    config.write_text('title = "' + name + '"\\nlanguage = "en"\\n', encoding='utf-8')
    manuscript = project / 'manuscript.md'
    manuscript.write_text('# ' + name + ' manuscript heading\\n\\n## A synthetic chapter\\n\\nA bird crosses the quiet garden. Rain begins softly.\\n', encoding='utf-8')
    projects[name] = {'root': str(project), 'manuscript': str(manuscript), 'config': str(config),
        'project_id': Repository(project).snapshot().project.id}
alpha = projects['Alpha']
LixityServerHandler.workspace_root = alpha['root']
LixityServerHandler.research_dir = alpha['root']
LixityServerHandler.source_input = alpha['manuscript']
LixityServerHandler.exports_dir = str(base / 'alpha' / 'exports')
LixityServerHandler.language = 'en'
LixityServerHandler.title = 'StartupAlphaOverride'
LixityServerHandler.title_custom = True
LixityServerHandler.project_open_overrides = {'title': 'StartupAlphaOverride', 'language': 'en'}
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'projects': projects}), flush=True)
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
    const {Alpha: alpha, Beta: beta} = fixture.projects;
    const originals = new Map(Object.values(fixture.projects).flatMap(project => [project.manuscript, project.config])
      .map(file => [file, fs.readFileSync(file)]));
    browser = await launchChromium();
    for (const [index, width] of [1440, 320].entries()) {
      const page = await browser.newPage({viewport: {width, height: 1000}});
      page.setDefaultTimeout(10000);
      const errors = [], writes = [], downloads = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => {
        if (['error', 'warning'].includes(message.type())) errors.push(message.text());
      });
      page.on('download', download => downloads.push(download.suggestedFilename()));
      await page.goto(fixture.url);
      if (index === 0) {
        await expect(page.locator('h1')).toHaveText('StartupAlphaOverride');
        await expect(page.locator('#nda-project-name')).toHaveValue('StartupAlphaOverride');
      }
      // This reset bypasses browser navigation. Finish the initial reader
      // context read before changing the server underneath its current page;
      // otherwise rejecting that former project's request is correct.
      await expect(page.locator('.manuscript-link-review .ctl-note').first()).toBeAttached();
      // On the second viewport this resets Beta back to Alpha through the real
      // endpoint; on the first it verifies that reopening the same project keeps
      // its explicit title override. Neither operation writes project files.
      const reset = await page.request.post(fixture.url + '/api/project-open', {data: {path: alpha.root}});
      assert.equal(reset.status(), 200);
      const resetState = await reset.json();
      assert.equal(resetState.ok, true);
      assert.equal(resetState.workspace_root, alpha.root);
      assert.equal(resetState.manuscript, alpha.manuscript);
      await page.reload();
      await expect(page.locator('h1')).toHaveText(index === 0 ? 'StartupAlphaOverride' : 'Alpha');
      await expect(page.locator('#nda-project-name')).toHaveValue(index === 0 ? 'StartupAlphaOverride' : 'Alpha');
      page.on('request', request => {
        const url = new URL(request.url());
        assert.equal(url.origin, fixture.url, 'The regression uses only its disposable loopback server');
        if (request.method() === 'POST') writes.push(url.pathname);
      });
      await page.locator('#btn-modal-open-project').click();
      await expect(page.locator('#modal-project-open')).toBeVisible();
      await page.locator('#open-proj-path').fill(beta.root);
      await page.locator('#modal-project-open').screenshot({path: path.join(artifacts, `open-${width}.png`)});
      const responsePromise = page.waitForResponse(response => response.url() === fixture.url + '/api/project-open'
        && response.request().method() === 'POST');
      const reload = page.waitForNavigation({waitUntil: 'domcontentloaded'});
      await page.locator('#btn-submit-open-project').click();
      const opened = await responsePromise;
      assert.equal(opened.status(), 200);
      const selected = await opened.json();
      assert.equal(selected.ok, true);
      assert.equal(selected.workspace_root, beta.root, 'The actual native endpoint selects Beta');
      assert.equal(selected.manuscript, beta.manuscript, 'The source belongs to Beta');
      await reload;
      await expect(page.locator('h1')).toHaveText('Beta');
      assert.match(await page.title(), /^Beta – /);
      await expect(page.locator('#nda-project-name')).toHaveValue('Beta');
      assert.notEqual(await page.locator('#nda-project-name').inputValue(), 'StartupAlphaOverride');
      const status = await page.request.get(fixture.url + '/api/research/status');
      assert.equal(status.status(), 200);
      const active = await status.json();
      assert.equal(active.ok, true);
      assert.equal(active.project_root, beta.root, 'Research reads also use the newly selected root');
      assert.equal(active.project_id, beta.project_id);
      await page.locator('#tab-view-project').click();
      await expect(page.locator('#nda-draft')).toBeVisible();
      await page.locator('#nda-draft').screenshot({path: path.join(artifacts, `nda-beta-${width}.png`)});
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Project and NDA controls fit the viewport');
      assert.deepEqual(writes, ['/api/project-open'], 'Project selection generates no NDA and saves no metadata');
      assert.deepEqual(downloads, [], 'No document is generated or downloaded');
      for (const [file, bytes] of originals) {
        assert.deepEqual(fs.readFileSync(file), bytes, 'Switching projects preserves synthetic manuscript/config bytes: ' + file);
      }
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log('Native project switch: actual Open Project/reload at1440/320 uses Beta heading/NDA title/source/research root, retains same-project startup override and changes no manuscript/config or generated NDA. Screenshots: ' + artifacts);
  } finally {
    if (browser) await browser.close();
    server.kill('SIGTERM');
    await Promise.race([once(server, 'exit'), new Promise(resolve => setTimeout(resolve, 3000))]);
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
