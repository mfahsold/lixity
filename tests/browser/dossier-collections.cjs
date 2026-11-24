// Synthetic collection editing: title selection, ordered membership and context safety.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const {createInterface} = require('node:readline');
const {launchChromium, playwrightModule, resolveAxe} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-dossier-collections-'));

(async () => {
  const server = spawn(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-u', '-c', `
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
from lixity.site_export import prepare_site
base = Path(sys.argv[1]); project = base / 'synthetic-project'
api.init(project, title='Synthetic collection review', language='en')
source = project / 'manuscript.md'
source.write_text('# Synthetic manuscript\\n\\nThe river crosses the quiet valley.\\n', encoding='utf-8')
(project / 'lixity.toml').write_text('manuscript = "manuscript.md"\\nlanguage = "en"\\n', encoding='utf-8')
ids = []
for number in range(20):
    title = ('Synthetic dossier %02d — ' % number) + ('Long readable title and context ' * 4)
    if number == 19: title = '<img src=x onerror=window.collectionInjected=true> & "Synthetic title"'
    ids.append(api.create_dossier(project, title=title, body='Synthetic retained notes.')['dossier_id'])
missing = 'urn:uuid:00000000-0000-4000-8000-000000000099'
api.save_dossier_collection(project, 'retained', name='Synthetic retained collection', dossier_ids=[ids[0], ids[1], missing])
record = api.get_dossier(project, ids[1])
api.withdraw(project, dossier_id=ids[1], expected_snapshot=record['snapshot'], expected_revision=record['revision'], reason='Synthetic withdrawal')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(source)
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.language = 'en'; LixityServerHandler.refresh()
from dashboard_fixtures import full_dashboard as render
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
from lixity.server.pdf_context import research_context_token
original = render.__globals__['render_dashboard']; fixtures = {}; captions = {}
for locale in ('de', 'en', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    captions[locale] = {key: labels[key] for key in ('research_dossier_collection_new', 'research_dossier_collection_add', 'research_dossier_collection_missing')}
    def localized(*args, **kwargs):
        return original(*args, **{**kwargs, 'labels': labels, 'language_key': locale,
            'enabled_actions': ['analyze', 'research-reader'], 'research_context_token': research_context_token(project)})
    render.__globals__['render_dashboard'] = localized
    fixtures[locale] = render()
(base / 'fixtures.json').write_text(json.dumps(fixtures), encoding='utf-8')
(base / 'captions.json').write_text(json.dumps(captions), encoding='utf-8')
(base / 'readonly.html').write_bytes(prepare_site(project, include_research=True).files['index.html'])
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'ids': ids, 'missing': missing}), flush=True)
server.serve_forever()
`, artifacts], {cwd: root, env: {...process.env, PYTHONPATH: [path.join(root, 'src'), path.join(root, 'tests')].join(path.delimiter)}, stdio: ['ignore', 'pipe', 'pipe']});
  let browser, stderr = '';
  server.stderr.on('data', data => { stderr = (stderr + data).slice(-5000); });
  const lines = createInterface({input: server.stdout});
  try {
    const fixture = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Fixture timeout: ' + stderr)), 20000);
      lines.once('line', line => {clearTimeout(timer); resolve(JSON.parse(line));});
      server.once('error', error => {clearTimeout(timer); reject(error);});
      server.once('exit', code => {clearTimeout(timer); reject(new Error(`Fixture exited ${code}: ${stderr}`));});
    });
    browser = await launchChromium();
    const fixtures = JSON.parse(fs.readFileSync(path.join(artifacts, 'fixtures.json'), 'utf8'));
    const captions = JSON.parse(fs.readFileSync(path.join(artifacts, 'captions.json'), 'utf8'));
    // Neither the shared overview nor an initial catalogue read may erase early typing.
    const loading = await browser.newPage({viewport: {width: 1440, height: 1000}});
    let releaseInitialStatus, releaseInitialDossiers;
    let initialDossiersEntered;
    const initialStatusGate = new Promise(resolve => {releaseInitialStatus = resolve;});
    const initialDossiersGate = new Promise(resolve => {releaseInitialDossiers = resolve;});
    const initialDossiers = new Promise(resolve => {initialDossiersEntered = resolve;});
    await loading.route(fixture.url + '/', route => route.fulfill({contentType: 'text/html', body: fixtures.en}));
    await loading.route(url => /^\/api\/research\/(status|dossiers)$/.test(url.pathname), async route => {
      const isDossiers = new URL(route.request().url()).pathname.endsWith('/dossiers');
      if (isDossiers) initialDossiersEntered();
      await (isDossiers ? initialDossiersGate : initialStatusGate);
      await route.continue();
    });
    await loading.goto(fixture.url);
    await loading.locator('#tab-view-research').click();
    await loading.locator('[data-rtab=dossiers]').click();
    await initialDossiers;
    await loading.locator('#r-dos-collection-manage > summary').click();
    const initialName = loading.locator('#r-dos-col-name');
    await expect(initialName).toHaveJSProperty('readOnly', true);
    await initialName.pressSequentially('Synthetic early draft');
    await expect(initialName).toHaveValue('');
    // Establish the accepted project before delivering the catalogue requested in the unknown context.
    releaseInitialStatus();
    await expect(loading.locator('#r-active-root')).toContainText('synthetic-project');
    await expect(initialName).toBeEditable();
    await initialName.fill('Synthetic accepted-context draft');
    const oldDossiersReply = loading.waitForResponse(response => new URL(response.url()).pathname === '/api/research/dossiers');
    releaseInitialDossiers();
    await (await oldDossiersReply).finished();
    await loading.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await expect(initialName).toBeEditable();
    await expect(initialName).toHaveValue('Synthetic accepted-context draft');
    await loading.evaluate(() => refreshResearchDossiers(null, null, true));
    await expect(initialName).toHaveValue('Synthetic accepted-context draft');
    await loading.close();

    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [];
    const writes = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (request.method() === 'POST') writes.push(request.postDataJSON());
    });
    await page.route(fixture.url + '/', route => route.fulfill({contentType: 'text/html', body: fixtures.en}));
    await page.goto(fixture.url);
    await page.locator('#tab-view-research').click();
    await page.locator('[data-rtab=dossiers]').click();
    await page.locator('#r-dos-collection-manage > summary').click();
    await expect(page.locator('#r-dos-col-picker'), 'Collections select dossiers by readable titles rather than technical IDs').toBeVisible({timeout: 3000});
    assert.equal(await page.locator('#r-dos-col-picker').evaluate(node => node.tagName), 'SELECT');
    const form = page.locator('#r-dos-collection-manage');
    const picker = page.locator('#r-dos-col-picker');
    const members = page.locator('#r-dos-col-members [data-col-member-id]');
    const id = page.locator('#r-dos-col-id');
    const name = page.locator('#r-dos-col-name');
    const save = page.locator('#r-dos-col-save-btn');
    const list = async () => (await (await page.request.get(fixture.url + '/api/research/dossiers')).json()).collections;
    const memberIds = () => members.evaluateAll(nodes => nodes.map(node => node.dataset.colMemberId));
    async function add(value) {
      await picker.selectOption(value);
      await page.locator('#r-dos-col-add-btn').click();
    }
    async function persist() {
      const response = page.waitForResponse(response => response.request().method() === 'POST' &&
        response.url().endsWith('/research-dossier') && response.request().postDataJSON().action === 'save_collection');
      await save.click();
      const result = await response;
      assert.equal(result.ok(), true);
      await expect(save).toBeEnabled();
      return result.json();
    }
    async function action(value, operation) {
      await page.locator(`#r-dos-col-members [data-col-member-id="${value}"] [data-col-action="${operation}"]`).click();
    }
    assert.equal(await page.locator('#r-dos-col-advanced').evaluate(node => node.open), false);
    await expect(id).not.toBeVisible();
    await expect(page.locator('#r-dos-col-dossiers')).not.toBeVisible();
    await expect(picker.locator('option')).toHaveCount(20); // Placeholder plus all 19 available dossiers.
    await expect(picker).toContainText('Synthetic dossier 00');
    await expect(picker).toContainText('<img src=x onerror=window.collectionInjected=true>');
    assert.equal(await form.locator('img').count(), 0);
    assert.equal(await page.evaluate(() => window.collectionInjected), undefined);

    // Existing membership is ordered and includes retained withdrawn/missing entries.
    await page.locator('#r-dos-collection-select').selectOption('retained');
    await expect(members).toHaveCount(3);
    assert.deepEqual(await memberIds(), [fixture.ids[0], fixture.ids[1], fixture.missing]);
    assert.equal(await page.evaluate(() => window.LixityResearchDrafts.hasPendingWork()), false);
    await name.fill('Synthetic revised collection');
    await add(fixture.ids[19]);
    await action(fixture.ids[19], 'up');
    await action(fixture.ids[0], 'remove');
    assert.deepEqual(await memberIds(), [fixture.ids[1], fixture.ids[19], fixture.missing]);
    assert.equal(await page.evaluate(() => window.LixityResearchDrafts.hasPendingWork()), true);
    // An ordinary catalogue refresh must not replace an unsaved collection draft.
    await page.evaluate(() => refreshResearchDossiers(null, null, true));
    await expect(name).toHaveValue('Synthetic revised collection');
    assert.deepEqual(await memberIds(), [fixture.ids[1], fixture.ids[19], fixture.missing]);
    await page.locator('#r-dos-collection-select').selectOption('unassigned');
    await expect(name).toHaveValue('Synthetic revised collection');
    assert.deepEqual(await memberIds(), [fixture.ids[1], fixture.ids[19], fixture.missing],
      'Changing the catalogue filter must not discard an unsaved ordered-membership draft');

    let release;
    let entered;
    const pending = new Promise(resolve => {entered = resolve;});
    const gate = new Promise(resolve => {release = resolve;});
    const hold = async route => {entered(); await gate; await route.continue();};
    await page.route('**/api/research-dossier', hold);
    const saving = persist();
    await pending;
    await expect(save).toBeDisabled();
    await expect(name).toBeDisabled();
    await expect(picker).toBeDisabled();
    await expect(page.locator('#r-dos-col-new-btn')).toBeDisabled();
    release();
    await saving;
    await page.unroute('**/api/research-dossier', hold);
    await expect.poll(async () => (await list()).find(item => item.id === 'retained').name).toBe('Synthetic revised collection');
    assert.deepEqual((await list()).find(item => item.id === 'retained').dossier_ids,
      [fixture.ids[1], fixture.ids[19], fixture.missing]);
    assert.deepEqual(writes.at(-1).dossier_ids, [fixture.ids[1], fixture.ids[19], fixture.missing]);
    assert.equal(await page.evaluate(() => window.LixityResearchDrafts.hasPendingWork()), false);

    // A failed save retains the draft, then a deliberate retry persists it.
    await name.fill('Synthetic failed then retried');
    const fail = route => route.fulfill({status: 500, json: {ok: false, message: 'Synthetic storage unavailable'}});
    await page.route('**/api/research-dossier', fail);
    await save.click();
    await expect(form).toContainText('Synthetic storage unavailable');
    await expect(name).toHaveValue('Synthetic failed then retried');
    await expect(save).toBeEnabled();
    assert.deepEqual(await memberIds(), [fixture.ids[1], fixture.ids[19], fixture.missing]);
    await page.unroute('**/api/research-dossier', fail);
    await persist();

    // A successful write must not hide a failure to reload the full catalogue.
    await name.fill('Synthetic catalogue saved');
    const failCatalogue = route => route.fulfill({status: 500,
      json: {ok: false, message: 'Synthetic catalogue unavailable'}});
    await page.route('**/api/research/dossiers?*', failCatalogue);
    await persist();
    await expect(page.locator('#research-manager')).toContainText('Synthetic catalogue unavailable');
    assert.equal((await list()).find(item => item.id === 'retained').name,
      'Synthetic catalogue saved', 'The write succeeded even though the catalogue reload failed');
    await page.unroute('**/api/research/dossiers?*', failCatalogue);
    await page.evaluate(() => refreshResearchDossiers(null, null, true));

    // New mode clears the old selection and assigns a readonly technical identifier.
    await page.locator('#r-dos-col-new-btn').click();
    await expect(name).toHaveValue('');
    await expect(members).toHaveCount(0);
    await name.fill('Synthetic created collection');
    await add(fixture.ids[2]);
    await add(fixture.ids[3]);
    const down = page.locator(`[data-col-member-id="${fixture.ids[2]}"] [data-col-action="down"]`);
    await down.focus();
    await down.press('Enter');
    assert.deepEqual(await memberIds(), [fixture.ids[3], fixture.ids[2]]);
    assert.equal(await page.evaluate(() => Boolean(document.activeElement.closest('#r-dos-collection-manage'))), true,
      'Keyboard reorder keeps focus in the collection editor');
    await page.locator('#r-dos-col-advanced > summary').click();
    await expect(id).toHaveAttribute('readonly', '');
    await persist();
    const createdId = await id.inputValue();
    assert.ok(createdId && createdId !== 'retained');
    assert.deepEqual((await list()).find(item => item.id === createdId).dossier_ids, [fixture.ids[3], fixture.ids[2]]);
    await page.locator('#r-dos-col-advanced > summary').click();

    // A stale selection cannot produce a write into a newly selected research context.
    const oldToken = await page.locator('#research-manager').getAttribute('data-research-token');
    const writeCount = writes.length;
    await name.fill('Stale synthetic context draft');
    assert.equal(await page.evaluate(() => window.LixityResearchDrafts.hasPendingWork()), true);
    await page.locator('#research-manager').evaluate(node => {node.dataset.researchToken = 'changed-synthetic-context';});
    await save.click();
    await page.waitForTimeout(100);
    assert.equal(writes.length, writeCount, 'Stale collection form must not submit with a new context token');
    await expect(name).toHaveValue('Stale synthetic context draft');
    assert.equal(await page.evaluate(() => window.LixityResearchDrafts.hasPendingWork()), true,
      'Name-only collection changes must still guard navigation when stale-context controls are disabled');
    await page.locator('#research-manager').evaluate((node, token) => {node.dataset.researchToken = token;}, oldToken);
    await page.evaluate(() => refreshResearchDossiers(null, null, true));
    await page.locator('#r-dos-collection-select').selectOption('retained');
    await name.fill('Old context request');
    // A response from the old context must not erase state already owned by the new context.
    let releaseLate;
    let enterLate;
    const lateEntered = new Promise(resolve => {enterLate = resolve;});
    const lateGate = new Promise(resolve => {releaseLate = resolve;});
    const lateHold = async route => {enterLate(); await lateGate; await route.continue();};
    await page.route('**/api/research-dossier', lateHold);
    const lateResponse = page.waitForResponse(response => response.url().endsWith('/research-dossier'));
    await save.click();
    await lateEntered;
    await page.evaluate(() => {
      document.querySelector('#research-manager').dataset.researchToken = 'another-synthetic-context';
      document.querySelector('#r-dos-col-name').value = 'New context draft must survive';
    });
    releaseLate();
    await lateResponse;
    await expect(save).not.toHaveAttribute('data-pending', 'true');
    await expect(name).toHaveValue('New context draft must survive');
    await page.unroute('**/api/research-dossier', lateHold);
    assert.deepEqual(errors, []);
    await page.close();

    const cases = [];
    for (const locale of ['de', 'en', 'fr', 'es', 'it', 'pt', 'nl']) {
      cases.push([locale, 1440, 'light'], [locale, 390, 'dark']);
    }
    for (const width of [1024, 2560, 320]) cases.push(['de', width, 'light'], ['en', width, 'dark']);
    const axePath = resolveAxe();
    let axeChecks = 0;
    for (const [locale, width, theme] of cases) {
      const localized = await browser.newPage({viewport: {width, height: 1000}, colorScheme: theme});
      const localErrors = [];
      localized.on('pageerror', error => localErrors.push(error.message));
      await localized.route(fixture.url + '/', route => route.fulfill({contentType: 'text/html', body: fixtures[locale]}));
      await localized.addInitScript(value => localStorage.setItem('lixity-theme', value), theme);
      await localized.goto(fixture.url);
      await localized.locator('#tab-view-research').click();
      await localized.locator('[data-rtab=dossiers]').click();
      await localized.locator('#r-dos-collection-manage > summary').click();
      await localized.locator('#r-dos-collection-select').selectOption('retained');
      await expect(localized.locator('#r-dos-col-members [data-col-member-id]')).toHaveCount(3);
      await expect(localized.locator('#r-dos-col-new-btn')).toHaveText(captions[locale].research_dossier_collection_new);
      await expect(localized.locator('#r-dos-col-add-btn')).toHaveText(captions[locale].research_dossier_collection_add);
      await expect(localized.locator('#r-dos-col-members')).toContainText(captions[locale].research_dossier_collection_missing);
      const geometry = await localized.locator('#r-dos-collection-manage').evaluate(node => {
        const box = node.getBoundingClientRect();
        const clipped = [...node.querySelectorAll('button,input,select,label,[data-col-member-id]')].filter(item => {
          if (!item.getClientRects().length) return false;
          const r = item.getBoundingClientRect();
          return r.right > innerWidth + 1 || r.left < -1 || (item.scrollWidth > item.clientWidth + 1);
        }).map(item => item.id || item.tagName);
        return {overflow: box.right > innerWidth + 1 || box.left < -1, clipped};
      });
      assert.deepEqual(geometry, {overflow: false, clipped: []}, `${locale}/${width}/${theme}: editor controls and wrapped members fit`);
      const content = await localized.locator('#r-dos-collection-manage').innerText();
      assert.ok(!content.includes('urn:uuid:'), 'Technical IDs are absent from the primary reading surface');
      assert.ok(!content.includes('research_dossier_collection_'), 'Raw localization keys never reach users');
      assert.equal(await localized.locator('#r-dos-col-members img').count(), 0);
      assert.equal(await localized.evaluate(() => window.collectionInjected), undefined);
      if (locale === 'de' && [1440, 390].includes(width)) {
        await localized.locator('#r-dos-collection-manage').screenshot({path: path.join(artifacts, `collection-de-${width}-${theme}.png`)});
      }
      if (axePath && locale === 'de' && [1440, 390].includes(width)) {
        await localized.addScriptTag({path: axePath});
        const result = await localized.evaluate(() => axe.run('#r-dos-collection-manage', {
          runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}
        }));
        assert.deepEqual(result.violations.map(v => ({id: v.id, nodes: v.nodes.length})), [], 'Collection editor axe violations');
        axeChecks++;
      }
      assert.deepEqual(localErrors, []);
      await localized.close();
    }
    const readonly = await browser.newPage();
    const readWrites = [];
    readonly.on('request', request => {if (request.method() === 'POST') readWrites.push(request.url());});
    await readonly.route(fixture.url + '/', route => route.fulfill({contentType: 'text/html', body: fs.readFileSync(path.join(artifacts, 'readonly.html'), 'utf8')}));
    await readonly.goto(fixture.url);
    await readonly.locator('#tab-view-research').click();
    await readonly.locator('[data-rtab=dossiers]').click();
    await expect(readonly.locator('#r-dos-collection-manage')).not.toBeVisible();
    assert.deepEqual(readWrites, [], 'Read-only exports never submit collection writes');
    await readonly.close();
    console.log(`Collection workflow and ${cases.length} localized geometry states passed; axe checks=${axeChecks}${axePath ? '' : ' (axe-core unavailable)'}; screenshots: ${artifacts}`);
  } finally {
    lines.close();
    if (browser) await browser.close();
    if (server.exitCode === null && server.signalCode === null) {
      const stopped = once(server, 'exit').catch(() => {});
      server.kill('SIGTERM');
      await stopped;
    }
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
