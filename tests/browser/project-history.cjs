const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-project-history-'));
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
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
        html, _ = build_server_dashboard(None, language=language, title='Synthetic project history')
        fixtures[language] = {'html': html, 'labels': WORKSPACE_LABELS[language]}
    print(json.dumps({'fixtures': fixtures, 'record': record,
                     'decisions': api.list_decisions(p), 'dossiers': api.list_dossiers(p)}))
`], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024});
assert.equal(fixture.status, 0, fixture.stderr);
const data = JSON.parse(fixture.stdout);
const recentKey = 'lixity:recent-projects';
const hostile = '/synthetic/<img src=x onerror=alert(1)>/manuscript.md';
const history = [' /synthetic/first ', '/synthetic/first', 42, null, {path: '/wrong'}, hostile,
  ...Array.from({length: 12}, (_, index) => '/synthetic/project-' + index)];

(async () => {
  const browser = await launchChromium();
  const errors = [];
  const opens = [];
  const saves = [];
  let result = {ok: true, reload: false, message: 'Synthetic project opened'};
  let resultStatus = null;
  async function open({language = 'en', saved = history, blocked = false, initialized = false} = {}) {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
    await context.addInitScript(({saved, blocked, recentKey}) => {
      if (!sessionStorage.getItem('synthetic-history-seeded')) {
        if (typeof saved === 'string') localStorage.setItem(recentKey, saved);
        else if (saved !== null) localStorage.setItem(recentKey, JSON.stringify(saved));
        sessionStorage.setItem('synthetic-history-seeded', '1');
      }
      if (blocked) Object.defineProperty(window, 'localStorage', {get() { throw new DOMException('Synthetic blocked storage', 'SecurityError'); }});
    }, {saved, blocked, recentKey});
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
      assert.equal(await page.locator('#welcome-project-recent-list [data-recent-project-path]').count(), 8, 'Welcome shows a bounded, deduplicated recent list');
      assert.equal(await page.locator('#welcome-project-recent-list img').count(), 0);
      const before = opens.length;
      await page.locator('#welcome-project-recent-list [data-recent-project-path]').nth(1).click();
      assert.equal(await page.locator('#open-proj-path').inputValue(), hostile);
      assert.equal(opens.length, before, 'Selecting history does not open a project');
      await page.locator('#modal-project-open [data-close-modal]').first().click();
      await page.locator('#hero-btn-browse-project').click();
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
        await check.page.locator('#hero-btn-browse-project').click();
        assert.ok(await check.page.locator('#open-project-chooser').isVisible(), 'Chooser remains usable without history');
        if (scenario.blocked) {
          await check.page.locator('[data-open-path-kind=manuscript]').click();
          await check.page.locator('#btn-submit-open-project').click();
          await check.page.waitForFunction(() => !document.getElementById('modal-project-open').open);
          assert.ok(await check.page.locator('#welcome-project-recent').isHidden(), 'A successful open remains usable when history cannot be stored');
        }
        await check.context.close();
      }
    }
    for (const language of ['en','de','fr','es','it','pt','nl']) {
      const {context, page} = await open({language, saved: ['/synthetic/first', hostile], initialized: true});
      for (const width of [1440, 320]) {
        await page.setViewportSize({width, height: 1000});
        if (!process.argv.includes('--labels-only')) {
          assert.ok(await page.locator('#hero-btn-browse-project').isVisible());
          assert.equal(await page.locator('#welcome-project-recent-list [data-recent-project-path]').count(), 2);
          await page.screenshot({path: path.join(artifacts, `recent-${language}-${width}.png`)});
        }
        await page.locator('[data-rtab=decisions]').click();
        await page.locator('[data-research-revise=decision]').click();
        await page.locator('#research-revision-field-rationale').waitFor();
        const correction = page.locator('[name=research_revision_change_kind][value=correction]');
        const supersession = page.locator('[name=research_revision_change_kind][value=supersession]');
        if (language === 'en') {
          assert.ok((await correction.locator('..').textContent()).includes('Fix an error'));
          assert.ok((await supersession.locator('..').textContent()).includes('Update the content or decision'));
          assert.ok((await page.locator('#research-revision-kind').textContent()).includes('Saved version 1'));
        }
        assert.ok(!(await page.locator('#research-revision-kind').textContent()).includes(data.record.record.id));
        assert.ok(await page.locator('#research-revision-technical').isVisible());
        assert.equal(await page.locator('#research-revision-technical').getAttribute('open'), null, 'Technical details start collapsed');
        await page.locator('#research-revision-technical > summary').click();
        assert.ok((await page.locator('#research-revision-technical').textContent()).includes(data.record.snapshot));
        await page.locator('#research-revision-technical > summary').click();
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
    console.log(`Recent projects and clear revision wording passed in seven locales at 1440/320. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
