const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {pythonFixture} = require('./support/python-fixture.cjs');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-project-history-'));
const data = pythonFixture(`
import json
import tempfile
from pathlib import Path
from lixity.server import build_server_dashboard
from lixity.research import api
from lixity.workspace_labels import WORKSPACE_LABELS
with tempfile.TemporaryDirectory() as directory:
    p = Path(directory) / 'synthetic-project'
    api.init(p, title='Synthetic project history')
    dossier = api.create_dossier(p, title='Synthetic dossier', body='Original synthetic notes.')
    decision = api.record_decision(p, title='Synthetic decision', rationale='Original synthetic decision.', dossier_ids=[dossier['dossier_id']])
    record = api.get_record(p, 'decision', decision['decision_id'])
    fixtures = {}
    for language in ('en','de','fr','es','it','pt','nl'):
        html, _ = build_server_dashboard(None, language=language, title='Synthetic project history',
                                         project_create_base='/synthetic/profile/Lixity')
        fixtures[language] = {'html': html, 'labels': WORKSPACE_LABELS[language]}
    print(json.dumps({'fixtures': fixtures, 'record': record,
                     'decisions': api.list_decisions(p), 'dossiers': api.list_dossiers(p)}))
`);
const recentKey = 'lixity:recent-projects';
const sample = {
  filename: 'first-look.md',
  language: 'en',
  content: fs.readFileSync(path.join(__dirname, '../../samples/first-look.md'), 'utf8'),
};
const hostile = '/synthetic/<img src=x onerror=alert(1)>/manuscript.md';
const history = [' /synthetic/first ', '/synthetic/first', 42, null, {path: '/wrong'}, hostile,
  ...Array.from({length: 12}, (_, index) => '/synthetic/project-' + index)];

(async () => {
  const browser = await launchChromium();
  const errors = [];
  const opens = [];
  const creates = [];
  const saves = [];
  const environmentRequests = [];
  let result = {ok: true, reload: false, message: 'Synthetic project opened'};
  let resultStatus = null;
  async function open({language = 'en', saved = history, blocked = false, initialized = false, desktop = false} = {}) {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
    await context.addInitScript(({saved, blocked, recentKey, desktop, sample}) => {
      if (!sessionStorage.getItem('synthetic-history-seeded')) {
        if (typeof saved === 'string') localStorage.setItem(recentKey, saved);
        else if (saved !== null) localStorage.setItem(recentKey, JSON.stringify(saved));
        sessionStorage.setItem('synthetic-history-seeded', '1');
      }
      if (blocked) Object.defineProperty(window, 'localStorage', {get() { throw new DOMException('Synthetic blocked storage', 'SecurityError'); }});
      if (desktop) {
        window.desktopRecentWrites = [];
        window.desktopPendingPaths = [];
        window.desktopPreferenceWrites = [];
        window.desktopEnvironmentReads = 0;
        window.desktopUpdateChecks = 0;
        window.desktopOpenedUrls = [];
        window.lixityDesktop = {
          version: 1,
          platform: 'macos',
          appRevision: '0123456789abcdef0123456789abcdef01234567',
          setWorkspaceTitle: async title => { window.desktopTitle = title; },
          setPreference: async (...entry) => window.desktopPreferenceWrites.push(entry),
          getRuntimeEnvironment: async () => {
            ++window.desktopEnvironmentReads;
            if (window.desktopEnvironmentUnavailable) throw new Error('Synthetic native diagnostic');
            return {ok: true, app: {version: '0.9.1', desktop_mode: true}};
          },
          checkForUpdates: () => new Promise((resolve, reject) => {
            ++window.desktopUpdateChecks;
            window.resolveDesktopUpdate = resolve;
            window.rejectDesktopUpdate = reject;
          }),
          openExternalUrl: async url => window.desktopOpenedUrls.push(url),
          pickProjectDirectory: async () => { throw new Error('Synthetic picker failure'); },
          takeOpenPath: async () => window.desktopPendingPaths.shift() || null,
          recordRecentProject: async (...entry) => window.desktopRecentWrites.push(entry),
          readSampleManuscript: () => new Promise((resolve, reject) => {
            window.resolveSample = () => resolve(sample);
            window.rejectSample = () => reject(new Error('Synthetic sample failure'));
          }),
        };
      }
    }, {saved, blocked, recentKey, desktop, sample});
    const page = await context.newPage();
    page.setDefaultTimeout(5000);
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://lixity.test/**', async route => {
      const request = route.request();
      const url = new URL(request.url());
      if (url.pathname === '/api/project-open') {
        opens.push(request.postDataJSON());
        return route.fulfill({json: result, status: resultStatus || (result.ok ? 200 : 400)});
      }
      if (url.pathname === '/api/desktop/environment') {
        environmentRequests.push(url.search);
        return route.fulfill({json: {ok: true, app: {version: '0.9.1', desktop_mode: false}}});
      }
      if (url.pathname === '/api/project-create') {
        creates.push(request.postDataJSON());
        return route.fulfill({json: {ok: true, path: '/synthetic/profile/Lixity/first-draft',
          manuscript: '/synthetic/profile/Lixity/first-draft/manuscript.md'}});
      }
      if (url.pathname === '/api/project-paths') return route.fulfill({json: {
        ok: true, path: '/synthetic', parent: '/', truncated: false,
        entries: [{name: '<img src=x onerror=alert(1)>.md', path: hostile, kind: 'manuscript'}]
      }});
      if (url.pathname === '/api/research/status') return route.fulfill({json: {
        ok: true, initialized, project_root: '/synthetic', project_id: data.record.project_id,
        sources_count: 0, dossiers_count: 1, claims_count: 0, decisions_count: 1
      }});
      if (url.pathname === '/api/research/decisions') return route.fulfill({json: {ok: true, ...data.decisions}});
      if (url.pathname === '/api/research/dossiers') return route.fulfill({json: {ok: true, ...data.dossiers}});
      if (url.pathname === '/api/research/record') return route.fulfill({json: {ok: true, ...data.record}});
      if (url.pathname === '/api/research-record-revise') {
        saves.push(request.postDataJSON());
        return route.fulfill({json: {ok: false, message: 'Synthetic conflict'}, status: 409});
      }
      if (url.pathname.startsWith('/api/')) return route.fulfill({json: {ok: true, sources: [], claims: [], dossiers: [], decisions: []}});
      return route.fulfill({contentType: 'text/html', body: data.fixtures[language].html});
    });
    await page.goto('http://lixity.test/');
    return {context, page};
  }
  try {
    if (!process.argv.includes('--labels-only')) {
      const {context, page} = await open();
      await page.evaluate(() => window.LixityDesktopBridge.openSystemStatus());
      const browserStatus = page.locator('#modal-desktop-environment [data-desktop-env-body]');
      await browserStatus.getByText('Local Browser', {exact: false}).waitFor();
      assert.deepEqual(environmentRequests, ['?probe_zotero=1']);
      await page.keyboard.press('Escape');
      assert.ok(await page.locator('#hero-btn-example').isHidden(), 'The browser welcome uses the online example');
      assert.equal(await page.locator('#welcome-project-recent-list [data-recent-project-path]').count(), 8, 'Welcome shows a bounded, deduplicated recent list');
      assert.equal(await page.locator('#welcome-project-recent-list img').count(), 0);
      const before = opens.length;
      await page.locator('#welcome-project-recent-list [data-recent-project-path]').nth(1).click();
      assert.equal(await page.locator('#open-proj-path').inputValue(), hostile);
      assert.equal(opens.length, before, 'Selecting history does not open a project');
      await page.locator('#modal-project-open [data-close-modal]').first().click();
      await page.locator('#hero-btn-open-project').click();
      assert.ok(await page.locator('#open-project-chooser').isVisible());
      await page.locator('[data-open-path-kind=manuscript]').click();
      assert.equal(await page.locator('#open-proj-path').inputValue(), hostile);
      assert.equal(opens.length, before, 'Browsing only selects a path');
      await page.locator('#modal-project-open [data-close-modal]').first().click();
      const unchanged = await page.evaluate(key => localStorage.getItem(key), recentKey);
      await page.locator('#hero-btn-open-project').click();
      await page.locator('#open-proj-path').fill('/synthetic/missing');
      result = {ok: false, message: 'Synthetic open failure'};
      await page.locator('#btn-submit-open-project').click();
      await page.waitForFunction(() => !document.getElementById('open-project-status').hidden);
      assert.equal(await page.evaluate(key => localStorage.getItem(key), recentKey), unchanged, 'Failed opens do not alter history');
      assert.ok(await page.locator('#modal-project-open').isVisible());
      resultStatus = 500;
      result = {ok: true, message: 'Synthetic inconsistent success envelope'};
      await page.locator('#open-proj-path').fill('/synthetic/http-failed');
      await page.locator('#btn-submit-open-project').click();
      await page.waitForFunction(() => !document.getElementById('btn-submit-open-project').disabled);
      assert.ok(await page.locator('#modal-project-open').isVisible(), 'An HTTP error cannot count as a successful open');
      assert.equal(await page.evaluate(key => localStorage.getItem(key), recentKey), unchanged);
      resultStatus = null;
      result = {ok: true, reload: false, message: 'Synthetic project opened'};
      await page.locator('#open-proj-path').fill('/synthetic/accepted');
      await page.locator('#btn-submit-open-project').click();
      await page.waitForFunction(() => !document.getElementById('modal-project-open').open);
      const saved = await page.evaluate(key => JSON.parse(localStorage.getItem(key)), recentKey);
      assert.equal(saved[0], '/synthetic/accepted');
      assert.equal(saved.length, 8);
      assert.ok(saved.every(entry => typeof entry === 'string'), 'Only paths are stored');
      await page.reload();
      assert.equal(await page.locator('#welcome-project-recent-list [data-recent-project-path]').first().getAttribute('data-recent-project-path'), '/synthetic/accepted');
      await page.locator('#welcome-project-recent [data-clear-recent-projects]').click();
      await page.reload();
      assert.ok(await page.locator('#welcome-project-recent').isHidden(), 'Clearing history survives reload');
      await context.close();
      for (const scenario of [{saved: '{broken'}, {saved: {path: '/not-an-array'}}, {blocked: true}]) {
        const check = await open(scenario);
        assert.ok(await check.page.locator('#welcome-project-recent').isHidden());
        await check.page.locator('#hero-btn-open-project').click();
        assert.ok(await check.page.locator('#open-project-chooser').isVisible(), 'Chooser remains usable without history');
        if (scenario.blocked) {
          await check.page.locator('[data-open-path-kind=manuscript]').click();
          await check.page.locator('#btn-submit-open-project').click();
          await check.page.waitForFunction(() => !document.getElementById('modal-project-open').open);
          assert.ok(await check.page.locator('#welcome-project-recent').isHidden(), 'A successful open remains usable when history cannot be stored');
        }
        await check.context.close();
      }
      const desktop = await open({desktop: true, saved: []});
      try {
        const page = desktop.page;
        const workspaceRoot = '/synthetic/Manuskript über Regen';
        const configuration = `${workspaceRoot}/lixity.toml`;
        result = {ok: true, workspace_root: workspaceRoot, title: 'Synthetic selected project', language: 'de'};
        const nativeOpen = page.waitForResponse('http://lixity.test/api/project-open');
        await page.evaluate(selected => {
          window.desktopPendingPaths.push(selected);
          window.dispatchEvent(new Event('lixity:desktop-open-path'));
        }, configuration);
        await nativeOpen;
        assert.deepEqual(opens.at(-1), {path: configuration}, 'The desktop bridge forwards the exact file selector');
        await page.waitForFunction(() => window.desktopRecentWrites.length === 1);
        result = {ok: true, reload: false, message: 'Synthetic project opened'};
        await page.locator('#hero-btn-open-project').click();
        await page.locator('#open-project-chooser:not([hidden])').waitFor();
        await page.keyboard.press('Escape');
        await page.locator('#modal-project-open[open]').waitFor({state: 'hidden'});
        await page.locator('#hero-btn-write').click();
        await page.locator('#new-proj-title:focus').waitFor();
        assert.equal(creates.length, 0, 'Opening the editor setup does not create a project');
        assert.match(await page.locator('#new-proj-path-help').textContent(), /\/synthetic\/profile\/Lixity/);
        await page.locator('#new-proj-title').fill('First draft');
        await page.locator('#btn-submit-create-project').click();
        await page.locator('#modal-project-create[open]').waitFor({state: 'hidden'});
        assert.equal(creates[0].path, '', 'The backend resolves the displayed default');
        assert.deepEqual(await page.evaluate(() => desktopRecentWrites), [
          [workspaceRoot, 'Synthetic selected project', 'de'],
          ['/synthetic/profile/Lixity/first-draft', 'First draft', 'en']
        ]);
      } finally { await desktop.context.close(); }

      const {context: sampleContext, page: samplePage} = await open({desktop: true, saved: [], language: 'de'});
      try {
        await samplePage.waitForFunction(() => window.desktopTitle ===
          document.querySelector('.workspace-shell .project-header h1').textContent.trim());
        assert.equal(await samplePage.locator('html').getAttribute('data-desktop-platform'), 'macos');
        await samplePage.evaluate(() => window.dispatchEvent(new CustomEvent('lixity:desktop-theme', {detail: 'dark'})));
        await samplePage.waitForFunction(() => document.documentElement.dataset.theme === 'dark');
        assert.deepEqual(await samplePage.evaluate(() => window.desktopPreferenceWrites), []);
        await samplePage.evaluate(() => window.dispatchEvent(new CustomEvent('lixity:desktop-theme', {detail: null})));
        await samplePage.waitForFunction(() => !document.documentElement.dataset.theme);
        assert.equal(await samplePage.evaluate(() => desktopUpdateChecks), 0, 'Desktop startup makes no update check');
        const updates = samplePage.locator('#modal-desktop-environment');
        const updateAction = updates.getByRole('button', {name: data.fixtures.de.labels.desktop_env_check_updates});
        const updateStatus = updates.getByRole('status');
        const menuAction = () => samplePage.evaluate(() => window.dispatchEvent(new CustomEvent('lixity:desktop-menu', {detail: 'help-check-updates'})));
        await menuAction();
        await updateAction.waitFor();
        await updates.getByText('Build-Stand', {exact: false}).waitFor();
        assert.equal(await updates.locator('code[title="0123456789abcdef0123456789abcdef01234567"]').textContent(), '01234567');
        assert.equal(await samplePage.evaluate(() => desktopEnvironmentReads), 1, 'Desktop status uses native IPC');
        assert.ok(await updateAction.isDisabled());
        await menuAction();
        assert.equal(await samplePage.evaluate(() => desktopUpdateChecks), 1, 'An in-flight check prevents duplicates');
        const reply = (status, tag) => samplePage.evaluate(({status, tag}) => window.resolveDesktopUpdate({
          status, latest_tag: tag, current_version: '0.9.1', guide_url: 'https://mfahsold.github.io/lixity/guides/installation.html#desktop',
        }), {status, tag});
        const downloadLink = updates.getByRole('button', {name: data.fixtures.de.labels.desktop_env_open_downloads});
        await reply('no_public_installer', null);
        await updateStatus.getByText(data.fixtures.de.labels.desktop_env_no_public_installer).waitFor();
        assert.equal(await downloadLink.count(), 0);
        await updateAction.press('Enter');
        await reply('no_matching_installer', 'v0.10.0');
        await updateStatus.getByText(data.fixtures.de.labels.desktop_env_no_matching_installer).waitFor();
        assert.equal(await downloadLink.count(), 0);
        await updateAction.press('Enter');
        await reply('available', 'v0.10.0');
        await updateStatus.getByText(data.fixtures.de.labels.desktop_env_update_available).waitFor();
        await downloadLink.click();
        assert.deepEqual(await samplePage.evaluate(() => desktopOpenedUrls), ['https://mfahsold.github.io/lixity/guides/installation.html#desktop']);
        await updateAction.press('Enter');
        await samplePage.evaluate(() => window.rejectDesktopUpdate(new Error('Synthetic unreachable catalog')));
        await updateStatus.getByText(data.fixtures.de.labels.desktop_env_update_failed).waitFor();
        assert.ok(await updateAction.isEnabled());
        await samplePage.keyboard.press('Escape');
        await samplePage.evaluate(() => {
          window.desktopEnvironmentUnavailable = true;
          return window.LixityDesktopBridge.openSystemStatus();
        });
        await updates.getByText(data.fixtures.de.labels.desktop_env_error).waitFor();
        assert.equal(await samplePage.evaluate(() => desktopEnvironmentReads), 2);
        assert.deepEqual(environmentRequests, ['?probe_zotero=1'], 'Desktop failures stay in the native contract');
        await samplePage.keyboard.press('Escape');
        const preview = samplePage.locator('#import-preview-box');
        const submit = samplePage.locator('#btn-submit-import-project');
        const dialog = samplePage.locator('#modal-project-create');
        const sampleButton = samplePage.getByRole('button', {name: data.fixtures.de.labels.welcome_sample_action});
        const before = creates.length;
        await sampleButton.press('Enter');
        assert.ok(await submit.isDisabled());
        await samplePage.keyboard.press('Escape');
        await samplePage.evaluate(() => resolveSample());
        await samplePage.locator('#hero-btn-new-project').click();
        assert.ok(await preview.isHidden(), 'A sample response after cancelling cannot populate normal import');
        await samplePage.keyboard.press('Escape');
        assert.equal(creates.length, before, 'Opening and cancelling the sample makes no project');

        await sampleButton.press('Enter');
        await samplePage.evaluate(() => rejectSample());
        await dialog.getByText(data.fixtures.de.labels.welcome_sample_error).waitFor();
        assert.ok(await submit.isDisabled());
        await samplePage.keyboard.press('Escape');

        await sampleButton.press('Enter');
        await samplePage.evaluate(() => resolveSample());
        await preview.waitFor();
        assert.equal(await samplePage.locator('#import-proj-title').inputValue(), 'The Crate at Warehouse 4');
        assert.equal(await samplePage.locator('#import-proj-lang').inputValue(), sample.language);
        assert.equal(await samplePage.locator('#import-fpc-filename').textContent(), sample.filename);
        assert.equal(creates.length, before, 'The sample preview requires confirmation to create a copy');
        await submit.click();
        await samplePage.locator('#modal-project-create[open]').waitFor({state: 'hidden'});
        assert.equal(creates.length, before + 1);
        assert.equal(creates.at(-1).path, '', 'The sample uses the normal project location');
        assert.equal(creates.at(-1).content, sample.content);
        assert.equal(creates.at(-1).language, sample.language);
      } finally { await sampleContext.close(); }
    }
    for (const language of ['en','de','fr','es','it','pt','nl']) {
      const {context, page} = await open({language, saved: ['/synthetic/first', hostile], initialized: true, desktop: true});
      for (const width of [1440, 320]) {
        await page.setViewportSize({width, height: 1000});
        if (!process.argv.includes('--labels-only')) {
          const hero = page.locator('#welcome-hero');
          const labels = data.fixtures[language].labels;
          assert.equal(await page.locator('#project-actions').getAttribute('open'), null);
          assert.ok(await hero.getByRole('button', {name: labels.welcome_open_action}).isVisible());
          assert.ok(await hero.getByRole('link', {name: labels.welcome_example}).isVisible());
          const showSample = hero.getByRole('button', {name: labels.welcome_sample_action});
          assert.ok(await showSample.isVisible());
          assert.equal(await showSample.getAttribute('aria-describedby'), 'welcome-sample-help');
          assert.equal(await hero.locator('#welcome-sample-help').textContent(), labels.welcome_sample_help);
          const write = hero.getByRole('button', {name: labels.welcome_write_action});
          await write.press('Enter');
          await page.locator('#new-proj-title:focus').waitFor();
          await page.keyboard.press('Escape');
          const importButton = hero.getByRole('button', {name: labels.welcome_import_action});
          await importButton.click();
          await page.locator('#import-dropzone:focus').waitFor();
          await page.keyboard.press('Escape');
          assert.ok(await hero.evaluate(element => element.scrollWidth <= element.clientWidth));
          assert.equal(await page.locator('#welcome-project-recent-list [data-recent-project-path]').count(), 2);
          await page.screenshot({path: path.join(artifacts, `recent-${language}-${width}.png`)});
        }
        await page.locator('#tab-view-research').click();
        await page.locator('[data-rtab=decisions]').click();
        await page.locator('[data-research-revise=decision]').click();
        await page.locator('#research-revision-field-rationale').waitFor();
        const correction = page.locator('[name=research_revision_change_kind][value=correction]');
        const supersession = page.locator('[name=research_revision_change_kind][value=supersession]');
        if (language === 'en') {
          assert.ok((await correction.locator('..').textContent()).includes('Fix an error'));
          assert.ok((await supersession.locator('..').textContent()).includes('Update the content or decision'));
          assert.ok((await page.locator('#research-revision-kind').textContent()).includes('Version 1'));
        }
        assert.ok(!(await page.locator('#research-revision-kind').textContent()).includes(data.record.record.id));
        assert.equal(await page.locator('#research-revision-technical').count(), 0);
        assert.ok(!(await page.locator('#modal-research-revision').innerText()).includes(data.record.snapshot));
        await page.screenshot({path: path.join(artifacts, `revision-${language}-${width}.png`)});
        if (language === 'en' && width === 1440) {
          await page.locator('#research-revision-field-rationale').fill('Synthetic updated rationale.');
          await supersession.check();
          await page.locator('#research-revision-reason').fill('Synthetic author update.');
          await page.locator('#research-revision-save').click();
          await page.waitForFunction(() => !document.getElementById('research-revision-status').hidden);
          assert.equal(saves.at(-1).change_kind, 'supersession', 'Friendly wording preserves the wire enum');
          assert.equal(saves.at(-1).expected_snapshot, data.record.snapshot);
          assert.equal(await page.locator('#research-revision-field-rationale').inputValue(), 'Synthetic updated rationale.');
        }
        await page.locator('#modal-research-revision [data-close-modal]').first().click();
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      }
      await context.close();
    }
    assert.deepEqual(errors, []);
    console.log(`Desktop sample, recent projects and clear revision wording passed in seven locales at 1440/320. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
