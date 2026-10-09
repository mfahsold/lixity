const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
// Local research list filters against a disposable synthetic archive.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
const {spawn, execFileSync} = require('node:child_process');
const {createInterface} = require('node:readline');
const {expect} = require(path.join(playwrightModule, 'test'));
const root = path.resolve(__dirname, '../..');
const python = process.env.PYTHON_BIN || path.join(root, '.venv/bin/python');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-list-filters-'));
const pythonEnv = {...process.env, PYTHONPATH: path.join(root, 'src')};
const longTitleSegment = 'SyntheticUnbrokenResearchTitle'.repeat(3);
const sourceTitle = 'Alpha "quoted" <img src=x onerror=alert(1)> ' + longTitleSegment;
const dossierTitle = 'Alpha dossier ' + longTitleSegment;

(async () => {
  const server = spawn(python, ['-u', '-c', `
import json
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
base = Path(sys.argv[1])
project = base / 'synthetic-project'
api.init(project, title='Synthetic filter archive')
source_ids = []
for name, title, tags in [('alpha', 'Alpha "quoted" <img src=x onerror=alert(1)> ${longTitleSegment}', ['Ledger']), ('beta', 'Beta source', ['Forest'])]:
    source = base / (name + '.txt')
    source.write_text('Original ' + name + ' detail.', encoding='utf-8')
    source_ids.append(api.ingest(project, source, title=title, context={'tags': tags}, allow_retention=True)['source_id'])
dossier_ids = []
for title, body, tags in [('Alpha dossier ${longTitleSegment}', 'Shipping excerpt.\\n\\n## Timeline\\nOriginal alpha dossier detail.', ['Harbor']), ('Beta dossier', 'Woodland excerpt.\\n\\n## Travel\\nOriginal beta dossier detail.', ['Forest'])]:
    dossier_ids.append(api.create_dossier(project, title=title, body=body, tags=tags)['dossier_id'])
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.research_dir = str(project)
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.language = 'en'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'project': str(project), 'sourceIds': source_ids, 'dossierIds': dossier_ids}), flush=True)
server.serve_forever()
`, artifacts], {cwd: root, env: pythonEnv, stdio: ['ignore', 'pipe', 'pipe']});
  let stderr = '';
  server.stderr.on('data', data => { stderr += data; });
  const lines = createInterface({input: server.stdout});
  let browser;
  try {
    const fixture = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Fixture startup timed out: ' + stderr)), 15000);
      lines.once('line', line => { clearTimeout(timer); resolve(JSON.parse(line)); });
      server.once('error', error => { clearTimeout(timer); reject(error); });
      server.once('exit', code => { clearTimeout(timer); reject(new Error(`Fixture exited ${code}: ${stderr}`)); });
    });
    browser = await launchChromium();
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    page.setDefaultTimeout(10000);
    const errors = [];
    const apiRequests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (new URL(request.url()).pathname.startsWith('/api/')) apiRequests.push(request.url());
    });
    await page.goto(fixture.url);
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await expect(page.locator('#research-manager')).toBeVisible();
    await expect(page.locator('#research-sources-list .research-card')).toHaveCount(2);
    await expect(page.locator('#r-filter-sources')).toBeVisible();
    await expect(page.locator('#r-filter-sources')).toHaveAccessibleName('Filter sources…');

    // Hold actual list/detail responses to exercise both orders without timing sleeps.
    for (const [kind, id, detailText] of [['sources', fixture.sourceIds[0], 'Original alpha detail.'],
      ['dossiers', fixture.dossierIds[0], 'Original alpha dossier detail.']]) {
      const url = fixture.url + '/api/research/' + kind;
      let releaseList, listStarted, releaseDetail, detailStarted;
      const listGate = new Promise(resolve => { releaseList = resolve; });
      const listReady = new Promise(resolve => { listStarted = resolve; });
      const detailGate = new Promise(resolve => { releaseDetail = resolve; });
      const detailReady = new Promise(resolve => { detailStarted = resolve; });
      let listReads = 0;
      await page.route(url, async route => {
        listReads++;
        const response = await route.fetch();
        listStarted();
        await listGate;
        await route.fulfill({response});
      });
      await page.route(url + '?id=*', async route => {
        const response = await route.fetch();
        detailStarted();
        await detailGate;
        await route.fulfill({response});
      });
      try {
        await page.locator(`[data-rtab=${kind}]`).click();
        await listReady;
        await page.evaluate(kind => {
          window.pendingListRefresh = kind === 'sources' ? refreshResearchSources() : refreshResearchDossiers();
        }, kind);
        const card = page.locator('#research-' + kind + '-list .research-card').filter({
          has: page.locator(`[data-research-detail][data-record-id="${id}"]`),
        });
        await card.locator('.research-details-body').evaluate(node => { node.dataset.refreshPreserved = 'yes'; });
        await card.locator('[data-research-detail]').click();
        await detailReady;
        if (kind === 'dossiers') {
          releaseDetail();
          await expect(card.locator('.research-details-body')).toContainText(detailText);
        }
        releaseList();
        await page.evaluate(() => window.pendingListRefresh);
        await expect(card.locator('.research-details')).toHaveAttribute('open', '');
        await expect(card.locator('.research-details-body')).toHaveAttribute('data-refresh-preserved', 'yes');
        releaseDetail();
        await expect(card.locator('.research-details-body')).toContainText(detailText);
        assert.equal(listReads, 1, 'Concurrent ordinary refreshes share one list request');
        await card.screenshot({path: path.join(artifacts, `pending-refresh-${kind}.png`)});
        await card.locator('[data-research-detail]').click();
      } finally {
        releaseList();
        releaseDetail();
        await page.unroute(url);
        await page.unroute(url + '?id=*');
      }
    }
    await page.locator('[data-rtab=sources]').click();

    const sourceCard = page.locator('.research-card').filter({has: page.locator(`[data-research-detail=source][data-record-id="${fixture.sourceIds[0]}"]`)});
    assert.equal(await sourceCard.getAttribute('onerror'), null, 'A source title must not create card attributes');
    await sourceCard.locator('[data-research-detail]').click();
    await expect(sourceCard.locator('.research-details-body')).toContainText('Original alpha detail.');
    await sourceCard.locator('.research-details-body').evaluate(node => { node.dataset.preserved = 'yes'; });
    const sourceFilter = page.locator('#r-filter-sources');
    const stableRequests = apiRequests.length;
    await sourceFilter.fill('  bEtA  ');
    await expect(page.locator('#research-sources-list .research-card:visible')).toHaveCount(1);
    await expect(sourceCard).toBeHidden();
    assert.equal(apiRequests.length, stableRequests, 'Typing a local filter must not request the API');
    await sourceFilter.fill('LEDGER');
    await expect(sourceCard).toBeVisible();
    await expect(sourceCard.locator('.research-details')).toHaveAttribute('open', '');
    await expect(sourceCard.locator('.research-details-body')).toHaveAttribute('data-preserved', 'yes');
    await sourceFilter.fill(fixture.sourceIds[0].toUpperCase());
    await expect(page.locator('#research-sources-list .research-card:visible')).toHaveCount(1);
    await sourceFilter.fill('missing <img src=x onerror=alert(1)>');
    await expect(page.locator('#research-sources-list .research-card:visible')).toHaveCount(0);
    await expect(page.locator('#r-filter-sources-status')).toContainText('No results for');
    assert.equal(await page.locator('#research-sources-list img, #r-filter-sources-status img').count(), 0);
    await sourceFilter.fill('');
    await expect(page.locator('#research-sources-list .research-card:visible')).toHaveCount(2);
    await expect(page.locator('#r-filter-sources-status')).toBeHidden();

    await page.locator('[data-rtab=dossiers]').click();
    await expect(page.locator('#research-dossiers-list .research-card')).toHaveCount(2);
    const dossierCard = page.locator('.research-card').filter({has: page.locator(`[data-research-detail=dossier][data-record-id="${fixture.dossierIds[0]}"]`)});
    await dossierCard.locator('[data-research-detail]').click();
    await expect(dossierCard.locator('.research-details-body')).toContainText('Original alpha dossier detail.');
    await dossierCard.locator('.research-details-body').evaluate(node => { node.dataset.preserved = 'yes'; });
    const dossierFilter = page.locator('#r-filter-dossiers');
    await expect(dossierFilter).toHaveAccessibleName('Filter dossiers…');
    const stableDossierRequests = apiRequests.length;
    for (const query of ['ALPHA', 'harbor', 'shipping excerpt', 'TIMELINE', fixture.dossierIds[0].toUpperCase()]) {
      await dossierFilter.fill(query);
      await expect(page.locator('#research-dossiers-list .research-card:visible')).toHaveCount(1);
      await expect(dossierCard).toBeVisible();
    }
    await dossierFilter.fill('beta');
    await expect(dossierCard).toBeHidden();
    await dossierFilter.fill('alpha');
    await expect(dossierCard.locator('.research-details')).toHaveAttribute('open', '');
    await expect(dossierCard.locator('.research-details-body')).toHaveAttribute('data-preserved', 'yes');
    assert.equal(apiRequests.length, stableDossierRequests, 'Filtering dossiers must not request the API');

    // A committed update must win over an older list response that arrives last.
    for (const [kind, id] of [['sources', fixture.sourceIds[0]], ['dossiers', fixture.dossierIds[0]]]) {
      const url = fixture.url + '/api/research/' + kind;
      let releaseOld, oldStarted;
      const oldGate = new Promise(resolve => { releaseOld = resolve; });
      const oldReady = new Promise(resolve => { oldStarted = resolve; });
      let reads = 0;
      await page.route(url, async route => {
        const first = ++reads === 1;
        const response = await route.fetch();
        if (first) { oldStarted(); await oldGate; }
        await route.fulfill({response});
      });
      try {
        await page.locator(`[data-rtab=${kind}]`).click();
        await oldReady;
        await page.evaluate(kind => {
          window.oldListRefresh = kind === 'sources' ? refreshResearchSources() : refreshResearchDossiers();
        }, kind);
        const latestText = 'Latest synthetic ' + kind + ' detail.';
        execFileSync(python, ['-c', `
import sys
from pathlib import Path
from lixity.research import api
project, kind, record_id, addition = sys.argv[1:]
if kind == 'sources':
    source = Path(project).parent / 'alpha.txt'
    source.write_text(source.read_text() + chr(10) * 2 + addition, encoding='utf-8')
    api.ingest(project, source, source_id=record_id, allow_retention=True)
else:
    current = api.get_record(project, 'dossier', record_id)
    api.revise_record(project, 'dossier', record_id,
        changes={'body': current['record']['body'] + chr(10) * 2 + addition},
        expected_snapshot=current['snapshot'], expected_revision=current['record']['revision'],
        change_kind='correction', reason='Synthetic concurrent update.')
`, fixture.project, kind, id, latestText], {cwd: root, env: pythonEnv});
        await page.evaluate(({kind, id}) => {
          window.latestListRefresh = kind === 'sources' ? refreshResearchSources(null, id) : refreshResearchDossiers(null, id);
        }, {kind, id});
        await page.evaluate(() => window.latestListRefresh);
        const card = page.locator('#research-' + kind + '-list .research-card').filter({
          has: page.locator(`[data-research-detail][data-record-id="${id}"]`),
        });
        await expect(card.locator('.research-details')).not.toHaveAttribute('open', '');
        await card.locator('[data-research-detail]').click();
        await expect(card.locator('.research-details-body')).toContainText(latestText);
        await card.locator('.research-details-body').evaluate(node => { node.dataset.latestDetail = 'yes'; });
        releaseOld();
        await page.evaluate(() => window.oldListRefresh);
        await expect(card.locator('.research-details')).toHaveAttribute('open', '');
        await expect(card.locator('.research-details-body')).toHaveAttribute('data-latest-detail', 'yes');
        await expect(card.locator('.research-details-body')).toContainText(latestText);
        assert.equal(reads, 2, 'A post-write refresh supersedes the coalesced older request');
        await card.locator('[data-research-detail]').click();
      } finally {
        releaseOld();
        await page.unroute(url);
      }
    }

    // Delay real list responses while the query changes.
    // The refreshed list must use the latest filter, and all association options remain available.
    execFileSync(python, ['-c', `
import sys
from pathlib import Path
from lixity.research import api
p = Path(sys.argv[1])
f = p.parent / 'gamma.txt'
f.write_text('New gamma detail.', encoding='utf-8')
api.ingest(p, f, title='Gamma source', allow_retention=True)
api.create_dossier(p, title='Gamma dossier', body='A newly retained dossier.')
`, fixture.project], {cwd: root, env: pythonEnv});
    for (const [kind, selectId, selectedId] of [['sources', 'r-ground-source-select', fixture.sourceIds[0]], ['dossiers', 'r-claim-dossier-select', fixture.dossierIds[0]]]) {
      await page.locator(`[data-rtab=${kind === 'sources' ? 'grounding' : 'claims'}]`).click();
      await page.locator('#' + selectId).evaluate(element => {const details = element.closest('details'); if (details) details.open = true;});
      await page.locator('#' + selectId).selectOption(selectedId);
      let release, started;
      const gate = new Promise(resolve => { release = resolve; });
      const ready = new Promise(resolve => { started = resolve; });
      const url = fixture.url + '/api/research/' + kind;
      await page.route(url, async route => {
        const response = await route.fetch();
        started();
        await gate;
        await route.fulfill({response});
      });
      try {
        await page.locator(`[data-rtab=${kind}]`).click();
        await ready;
        await page.locator('#r-filter-' + kind).fill('gamma');
        release();
        await expect(page.locator('#research-' + kind + '-list .research-card:visible')).toHaveCount(1);
        await expect(page.locator('#research-' + kind + '-list .research-card:visible')).toContainText('Gamma');
        await expect(page.locator('#' + selectId)).toHaveValue(selectedId);
        await expect(page.locator('#' + selectId + ' option')).toHaveCount(4);
      } finally {
        release();
        await page.unroute(url);
      }
    }

    const languages = {
      en: ['Filter sources…', 'Filter dossiers…', 'No results for'],
      de: ['Quellen filtern…', 'Dossiers filtern…', 'Keine Treffer'],
      fr: ['Filtrer les sources…', 'Filtrer les dossiers…', 'Aucun résultat'],
      es: ['Filtrar fuentes…', 'Filtrar dosieres…', 'Sin resultados'],
      it: ['Filtra fonti…', 'Filtra dossier…', 'Nessun risultato'],
      pt: ['Filtrar fontes…', 'Filtrar dossiês…', 'Nenhum resultado'],
      nl: ['Bronnen filteren…', 'Dossiers filteren…', 'Geen resultaten'],
    };
    for (const [language, [sourcesName, dossiersName, noResults]] of Object.entries(languages)) {
      assert.equal((await (await page.request.post(fixture.url + '/api/settings', {data: {language}})).json()).ok, true);
      for (const width of [1440, 320]) {
        await page.setViewportSize({width, height: 900});
        await page.reload();
        await page.locator('[data-view=research]').click();
        await expect(page.locator('html')).toHaveAttribute('lang', language);
        for (const [kind, name] of [['sources', sourcesName], ['dossiers', dossiersName]]) {
          await page.locator(`[data-rtab=${kind}]`).click();
          await expect(page.locator('#research-' + kind + '-list .research-card')).toHaveCount(3);
          const title = page.locator('#research-' + kind + '-list .research-card-title').filter({hasText: longTitleSegment});
          await expect(title).toHaveText(kind === 'sources' ? sourceTitle : dossierTitle);
          assert.ok(await title.evaluate(element => {
            const box = element.getBoundingClientRect();
            const card = element.closest('.research-card').getBoundingClientRect();
            return box.left >= card.left && box.right <= card.right && box.left >= 0 && box.right <= innerWidth
              && element.scrollWidth <= element.clientWidth + 1 && element.scrollHeight <= element.clientHeight + 1;
          }), `${language} ${kind} must display the complete long title within its card at ${width}px`);
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
            `${language} ${kind} long title overflows the viewport at ${width}px`);
          if (language === 'en') {
            await page.locator('#research-manager').screenshot({path: path.join(artifacts, `${kind}-long-title-${width}.png`)});
          }
          const input = page.getByRole('searchbox', {name, exact: true});
          await input.fill('gamma');
          await expect(page.locator('#research-' + kind + '-list .research-card:visible')).toHaveCount(1);
          await expect(page.locator('#research-' + kind + '-list .research-card:visible')).toContainText('Gamma');
          await input.fill('missing');
          await expect(page.locator('#r-filter-' + kind + '-status')).toContainText(noResults);
          await input.fill('gamma');
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${language} ${kind} overflow at ${width}`);
          await page.locator('#research-manager').screenshot({path: path.join(artifacts, `${kind}-${language}-${width}.png`)});
        }
      }
    }
    assert.equal((await (await page.request.post(fixture.url + '/api/settings', {data: {language: 'en'}})).json()).ok, true);
    await page.setViewportSize({width: 1440, height: 1000});
    await page.reload();
    await expect(page.locator('#research-sources-list .research-card')).toHaveCount(3);
    for (const [action, kind, title, recordId] of [
      ['import', 'sources', 'Imported synthetic source', null],
      ['create', 'dossiers', 'Created synthetic dossier', null],
      ['revise', 'dossiers', 'Revised synthetic dossier', fixture.dossierIds[0]],
      ['batch', 'dossiers', 'Batch revised synthetic dossier', fixture.dossierIds[1]],
    ]) {
      await page.locator(`[data-rtab=${kind}]`).click();
      await page.evaluate(kind => kind === 'sources' ? refreshResearchSources() : refreshResearchDossiers(), kind);
      const url = fixture.url + '/api/research/' + kind;
      let releaseOld, oldStarted;
      const oldGate = new Promise(resolve => { releaseOld = resolve; });
      const oldReady = new Promise(resolve => { oldStarted = resolve; });
      let reads = 0;
      await page.route(url, async route => {
        const first = ++reads === 1;
        const response = await route.fetch();
        if (first) { oldStarted(); await oldGate; }
        await route.fulfill({response});
      });
      try {
        await page.evaluate(kind => {
          window.preWriteListRefresh = kind === 'sources' ? refreshResearchSources() : refreshResearchDossiers();
        }, kind);
        await oldReady;
        if (action === 'import') {
          await page.locator('#r-ingest-title').evaluate(element => { element.closest('details').open = true; });
          await page.locator('#r-ingest-title').fill(title);
          await page.locator('#r-ingest-text').fill('A permitted synthetic source for the post-write refresh regression.');
          await page.locator('#r-ingest-retention').check();
          await page.locator('#r-ingest-btn').click();
          await expect(page.locator('#r-ingest-text')).toHaveValue('');
        } else if (action === 'create') {
          await page.locator('#r-dos-title').fill(title);
          await page.locator('#r-dos-body').fill('A synthetic dossier created while an older list read is pending.');
          await page.locator('#r-dos-create-btn').click();
          await expect(page.locator('#r-dos-title')).toHaveValue('');
        } else {
          await page.locator(`#research-dossiers-list [data-research-revise=dossier][data-record-id="${recordId}"]`).click();
          await expect(page.locator('#research-revision-field-title')).toBeVisible();
          await page.locator('#research-revision-field-title').fill(title);
          await page.locator('input[name=research_revision_change_kind][value=correction]').check();
          await page.locator('#research-revision-reason').fill('Synthetic post-write refresh check.');
          if (action === 'batch') {
            await page.locator('#research-revision-batch-add').click();
            await expect(page.locator('#research-revision-batch-review')).toBeEnabled();
            await page.locator('#modal-research-revision [data-close-modal]').first().click();
            await page.locator('#research-revision-batch-review').click();
            await expect(page.locator('#research-revision-batch-apply')).toBeEnabled();
            await page.locator('#research-revision-batch-apply').click();
            await expect(page.locator('#modal-research-revision-batch')).not.toBeVisible();
          } else {
            await page.locator('#research-revision-save').click();
            await expect(page.locator('#modal-research-revision')).not.toBeVisible();
          }
        }
        const updated = page.locator('#research-' + kind + '-list .research-card-title').filter({hasText: title});
        await expect(updated).toHaveText(title);
        assert.equal(reads, 2, action + ' must read a fresh list after its accepted write');
        releaseOld();
        await page.evaluate(() => window.preWriteListRefresh);
        await expect(updated).toHaveText(title);
      } finally {
        releaseOld();
        await page.evaluate(() => window.preWriteListRefresh);
        await page.unroute(url);
      }
    }
    assert.deepEqual(errors, [], 'Research filters must not cause browser runtime errors');
    console.log(`Research list filters: controlled list/detail races, coalesced reads, fresh import/create/revision/batch reads, stale responses, matching, inert text, preserved details, no typing requests, associations, complete long titles and seven languages at 1440/320 passed. Screenshots: ${artifacts}`);
  } finally {
    if (browser) await browser.close();
    lines.close();
    server.kill('SIGTERM');
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
