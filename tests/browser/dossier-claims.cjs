// Dossier reading projects current linked claims through the existing native API.
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
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-dossier-claims-'));

(async () => {
  const server = spawn(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-u', '-c', `
import hashlib, json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.research.repository import Repository
from lixity.pipeline import paragraph_identity, profile_document, resolve_document_config
from lixity.style_fingerprint import FingerprintThresholds
from lixity.server import LixityServerHandler
from lixity.server.pdf_context import manuscript_pdf_token, research_context_token
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
base = Path(sys.argv[1]); project = base / 'synthetic-project'
api.init(project, title='Synthetic linked claims')
dossier = api.create_dossier(project, title='Synthetic dossier', body='## Context\\n\\nCurrent synthetic dossier notes.')
other = api.create_dossier(project, title='Unrelated dossier', body='Separate notes.')
empty = api.create_dossier(project, title='Empty dossier', body='No linked claim yet.')
claim = api.create_claim(project, title='Original linked title', statement='Synthetic archive interpretation.', dossier_id=dossier['dossier_id'])
current = api.get_record(project, 'claim', claim['claim_id'])
api.revise_record(project, 'claim', claim['claim_id'], changes={'title': 'Current linked <img src=x onerror=window.claimInjected=true> title', 'confidence': 'disputed'}, expected_snapshot=current['snapshot'], expected_revision=1, change_kind='correction', reason='Synthetic title correction')
api.create_claim(project, title='Unrelated claim', statement='Separate synthetic interpretation.', dossier_id=other['dossier_id'])
api.create_claim(project, title='Unlinked claim', statement='Unlinked synthetic interpretation.')
manuscript = project / 'manuscript.md'
manuscript.write_text('# Synthetic manuscript\\n\\nA bird crosses the quiet garden. Rain begins.\\n', encoding='utf-8')
config, _ = resolve_document_config(manuscript.read_text(encoding='utf-8'), 'en')
paragraph = profile_document(manuscript.read_text(encoding='utf-8'), config, FingerprintThresholds())[0][0]
snapshot = Repository(project).snapshot()
api.link_manuscript_claim(project, manuscript, claim['claim_id'], claim_revision=2,
    selection={**paragraph_identity(paragraph), 'start': 0, 'end': 6, 'quote': paragraph.text[:6]},
    expected_project_id=snapshot.project.id, expected_snapshot=snapshot.digest,
    expected_source_sha256=hashlib.sha256(manuscript.read_bytes()).hexdigest(), allow_retention=True)
current_dossier = api.get_record(project, 'dossier', dossier['dossier_id'])
api.revise_record(project, 'dossier', dossier['dossier_id'], changes={'body': '## Context\\n\\nRevised synthetic dossier notes.'},
    expected_snapshot=current_dossier['snapshot'], expected_revision=1, change_kind='correction', reason='Synthetic note revision')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.research_dir = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.language = 'en'
LixityServerHandler.refresh()
token = manuscript_pdf_token(str(manuscript), project_root=project, language='en', title=None, thresholds=LixityServerHandler.thresholds)
from dashboard_fixtures import full_dashboard as render
original = render.__globals__['render_dashboard']
fixtures = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    def localized(*args, **kwargs):
        return original(*args, **{**kwargs, 'labels': labels, 'language_key': locale,
            'enabled_actions': ['analyze', 'manuscript-pdf', 'research-reader'], 'manuscript_pdf_token': token,
            'research_context_token': research_context_token(project)})
    render.__globals__['render_dashboard'] = localized
    fixtures[locale] = render()
(base / 'fixtures.json').write_text(json.dumps(fixtures), encoding='utf-8')
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'dossier': dossier['dossier_id'], 'empty': empty['dossier_id'], 'claim': claim['claim_id']}), flush=True)
server.serve_forever()
`, artifacts], {cwd: root, env: {...process.env, PYTHONPATH: [path.join(root, 'src'), path.join(root, 'tests')].join(path.delimiter)}, stdio: ['ignore', 'pipe', 'pipe']});
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
    const fixtures = JSON.parse(fs.readFileSync(path.join(artifacts, 'fixtures.json'), 'utf8'));
    browser = await launchChromium();
    for (const [locale, html] of Object.entries(fixtures)) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 950}});
      page.setDefaultTimeout(10000);
      const errors = [], writes = [], reads = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => {
        if (request.method() === 'POST') writes.push(request.url());
        const url = new URL(request.url());
        if (url.pathname === '/api/research/claims' && url.searchParams.has('dossier_id')) reads.push(url);
      });
      await page.route(fixture.url + '/', route => route.fulfill({contentType: 'text/html', body: html}));
      await page.goto(fixture.url);
      await page.locator('#tab-view-research').click();
      await expect(page.locator('#tab-view-research'), `${locale}/${width}: Research navigation switches the active view; errors: ${errors.join('; ')}`).toHaveAttribute('aria-selected', 'true');
      await page.locator('[data-rtab=claims]').click();
      await page.locator('#r-claim-composer > summary').click();
      await page.locator('#r-claim-title').fill('Retained unsubmitted draft');
      await page.locator('[data-rtab=decisions]').click();
      await page.locator('#r-decision-composer > summary').click();
      await page.locator('#r-decision-title').fill('Retained unsubmitted decision');
      await page.locator('#r-decision-rationale').fill('Synthetic authored decision rationale.');
      await page.locator('#r-decision-options > summary').click();
      await page.locator('#r-decision-claim-select').selectOption(fixture.claim);
      await page.locator('#r-decision-dossier-select').selectOption(fixture.empty);
      await page.locator('[data-rtab=dossiers]').click();
      const summary = page.locator(`[data-research-detail=dossier][data-record-id="${fixture.dossier}"]`);
      await summary.click();
      const detail = page.locator('.research-details-body').filter({has: page.locator(`[data-dossier-claim="${fixture.dossier}"]`)});
      const linked = detail.locator('.research-dossier-claims');
      await expect(detail.locator('.research-folder-notes')).toContainText('Revised synthetic dossier notes.');
      await expect(detail.locator('.research-folder-citations')).toBeVisible();
      await expect(detail.locator('[data-research-global=claims]')).toBeVisible();
      await expect(detail.locator('[data-research-global=decisions]')).toBeVisible();
      await expect(linked).toContainText('Current linked <img src=x onerror=window.claimInjected=true> title');
      await expect(linked.locator('li')).toHaveCount(1);
      await expect(linked).not.toContainText('Original linked title');
      await expect(linked).not.toContainText('Unrelated claim');
      await expect(linked).not.toContainText('Unlinked claim');
      await expect(linked.locator('.research-badge')).toBeVisible();
      await expect(linked.locator('[data-claim-revision]')).toHaveAttribute('data-claim-revision', '2');
      await expect(linked.locator('[data-manuscript-link-count]')).toHaveAttribute('data-manuscript-link-count', '1');
      await expect(linked.locator('[data-dossier-version-review]')).toBeVisible();
      assert.equal(await linked.locator('img').count(), 0, 'Claim titles remain inert text');
      assert.equal(await linked.locator('li > strong').evaluate(title => {
        const boundary = title.closest('.research-dossier-claims').getBoundingClientRect();
        return Array.from(title.getClientRects()).every(rect => rect.left >= boundary.left - 1 && rect.right <= boundary.right + 1);
      }), true, 'Long claim titles wrap inside the dossier reading width');
      assert.equal(await page.evaluate(() => Boolean(window.claimInjected)), false);
      assert.ok(reads.length > 0, 'Opening a dossier requests its current claim associations');
      assert.ok(reads.every(url => url.searchParams.get('research_token') && url.searchParams.get('dossier_id') === fixture.dossier));
      assert.equal(await linked.locator('[data-research-revise]').count(), 0, 'Reading links offer the existing viewer');
      await linked.locator('[data-research-history=claim]').click();
      await expect(page.locator('#modal-research-revision')).toBeVisible();
      await expect(page.locator('#research-revision-history-detail')).toContainText('Current linked');
      await expect(page.locator('#research-revision-history-list [data-research-revision]')).toHaveCount(2);
      await page.locator('#research-revision-history-list [data-research-revision="1"]').click();
      await expect(page.locator('#research-revision-history-detail')).toContainText('Original linked title');
      await page.keyboard.press('Escape');
      await detail.scrollIntoViewIfNeeded();
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Dossier list fits the viewport');
      if (locale === 'de') await detail.screenshot({path: path.join(artifacts, `dossier-${width}.png`)});
      await detail.locator('[data-research-global=claims]').click();
      await expect(page.locator('#rtab-claims')).toBeVisible();
      await expect(page.locator('#research-claims-list')).toContainText('Unlinked claim');
      await expect(page.locator('#r-claim-title')).toHaveValue('Retained unsubmitted draft');
      await page.locator('[data-rtab=dossiers]').click();
      if (!await summary.evaluate(button => button.parentElement.open)) await summary.click();
      await detail.locator('[data-research-global=decisions]').click();
      await expect(page.locator('#rtab-decisions[role=tabpanel]')).toBeVisible();
      await expect(page.locator('[data-rtab=decisions]')).toHaveAttribute('aria-selected', 'true');
      await expect(page.locator('[data-rtab=decisions]')).toBeFocused();
      await expect(page.locator('#rtab-dossiers')).not.toBeVisible();
      await expect(page.locator('#r-decision-title')).toHaveValue('Retained unsubmitted decision');
      await expect(page.locator('#r-decision-rationale')).toHaveValue('Synthetic authored decision rationale.');
      await expect(page.locator('#r-decision-claim-select')).toHaveValue(fixture.claim);
      await expect(page.locator('#r-decision-dossier-select')).toHaveValue(fixture.empty);
      assert.deepEqual(writes, [], 'Global record routes preserve drafts without publishing them');
      if (locale === 'en') await page.locator('#rtab-decisions').screenshot({path: path.join(artifacts, `global-decisions-${width}.png`)});
      await page.locator('#tab-view-analysis').click();
      await page.locator('#workspace-reader-toggle').click();
      await page.waitForFunction(() => !document.querySelector('#workspace-reader-dossier').disabled);
      await page.locator('#workspace-reader-dossier').selectOption(fixture.dossier);
      const companion = page.locator('#workspace-reader-body .research-dossier-claims');
      await expect(companion.locator('li')).toHaveCount(1);
      await expect(companion).toContainText('Current linked');
      await expect(companion.locator('[data-research-revise]')).toHaveCount(0);
      await companion.locator('[data-research-history=claim]').click();
      await expect(page.locator('#research-revision-history-detail')).toContainText('Current linked');
      await page.keyboard.press('Escape');
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Companion list fits the viewport');
      if (locale === 'de') await page.locator('#workspace-reader-panel').screenshot({path: path.join(artifacts, `companion-${width}.png`)});
      await page.locator('#workspace-reader-dossier').selectOption(fixture.empty);
      await expect(page.locator('#workspace-reader-body .research-dossier-claims')).toHaveAttribute('aria-busy', 'false');
      await expect(page.locator('#workspace-reader-body .research-dossier-claims li')).toHaveCount(0);
      assert.ok(await page.locator('#workspace-reader-body .research-dossier-claims > p').last().textContent(), 'Empty associations have a localized explanation');
      if (locale === 'en') await expect(page.locator('#workspace-reader-body .research-dossier-claims')).toContainText('No claims linked');
      assert.deepEqual(writes, [], 'Reading and history never publish a change');
      assert.deepEqual(errors, []);
      await page.close();
    }
    const guarded = await browser.newPage({viewport: {width: 1440, height: 950}});
    const errors = [];
    guarded.on('pageerror', error => errors.push(error.message));
    await guarded.route(fixture.url + '/', route => route.fulfill({contentType: 'text/html', body: fixtures.en}));
    await guarded.goto(fixture.url);
    await guarded.locator('#tab-view-research').click();
    await guarded.locator('[data-rtab=dossiers]').click();
    const summary = guarded.locator(`[data-research-detail=dossier][data-record-id="${fixture.dossier}"]`);
    const detail = summary.locator('..').locator('.research-details-body');
    const linked = detail.locator('.research-dossier-claims');
    async function holdRead(kind, marker) {
      await guarded.evaluate(({kind, marker}) => {
        window.originalDossierRead = window.originalDossierRead || researchApiGet;
        window.releaseDelayedDossierRead = null;
        window.delayedDossierReadProcessed = false;
        let held = false;
        researchApiGet = async endpoint => {
          const result = await window.originalDossierRead(endpoint);
          const matches = kind === 'claims' ? endpoint.startsWith('research/claims?dossier_id=') : endpoint.startsWith('research/dossiers?id=');
          if (!matches || held) return result;
          held = true;
          const delayed = kind === 'claims' ? {...result, claims: result.claims.map(claim => ({...claim, title: marker}))} : {...result, body: marker};
          return new Promise(resolve => {window.releaseDelayedDossierRead = () => {
            resolve(delayed);
            setTimeout(() => {window.delayedDossierReadProcessed = true;}, 0);
          };});
        };
      }, {kind, marker});
    }
    async function releaseRead() {
      await guarded.evaluate(() => window.releaseDelayedDossierRead());
      await guarded.waitForFunction(() => window.delayedDossierReadProcessed);
      await guarded.evaluate(() => {researchApiGet = window.originalDossierRead;});
    }
    await holdRead('dossier', 'Older delayed dossier notes.');
    await summary.click();
    await guarded.waitForFunction(() => Boolean(window.releaseDelayedDossierRead));
    await summary.click();
    await summary.click();
    await expect(linked).toContainText('Current linked');
    await releaseRead();
    await expect(detail).not.toContainText('Older delayed dossier notes.');
    await summary.click();
    await holdRead('claims', 'Older delayed linked title');
    await summary.click();
    await guarded.waitForFunction(() => Boolean(window.releaseDelayedDossierRead));
    await summary.click();
    await summary.click();
    await expect(linked).toContainText('Current linked');
    await releaseRead();
    await expect(linked).not.toContainText('Older delayed linked title');

    // A wrong-project envelope is an unavailable read, never an empty list.
    await summary.click();
    await guarded.evaluate(() => {
      researchApiGet = async endpoint => {
        const result = await window.originalDossierRead(endpoint);
        return endpoint.startsWith('research/claims?dossier_id=') ? {...result, project_id: 'different-synthetic-project'} : result;
      };
    });
    await summary.click();
    await expect(linked).toContainText('Failed to load claims');
    await expect(linked).not.toContainText('No claims linked');
    await guarded.evaluate(() => {researchApiGet = window.originalDossierRead;});
    await linked.getByRole('button', {name: 'Reload linked claims'}).click();
    await expect(linked).toContainText('Current linked');

    // A copied archive can share project IDs: the displayed root token still
    // must match before a delayed response may alter the live reading view.
    await summary.click();
    await holdRead('claims', 'Delayed response for a former root');
    await summary.click();
    await guarded.waitForFunction(() => Boolean(window.releaseDelayedDossierRead));
    await guarded.evaluate(() => {
      const panel = document.getElementById('research-manager');
      window.originalResearchRootToken = panel.dataset.researchToken;
      panel.dataset.researchToken = 'b'.repeat(64);
    });
    await releaseRead();
    await expect(linked).not.toContainText('Delayed response for a former root');
    await expect(linked.locator('li')).toHaveCount(0);
    await guarded.evaluate(() => {document.getElementById('research-manager').dataset.researchToken = window.originalResearchRootToken;});

    await guarded.locator('#tab-view-analysis').click();
    await guarded.locator('#workspace-reader-toggle').click();
    await guarded.waitForFunction(() => !document.querySelector('#workspace-reader-dossier').disabled);
    await holdRead('claims', 'Delayed claims for a previous reader selection');
    await guarded.locator('#workspace-reader-dossier').selectOption(fixture.dossier);
    await guarded.waitForFunction(() => Boolean(window.releaseDelayedDossierRead));
    await guarded.locator('#workspace-reader-dossier').selectOption(fixture.empty);
    const companion = guarded.locator('#workspace-reader-body .research-dossier-claims');
    await expect(companion).toContainText('No claims linked');
    await releaseRead();
    await expect(companion).not.toContainText('Delayed claims for a previous reader selection');
    await expect(companion.locator('li')).toHaveCount(0);
    await holdRead('claims', 'Delayed claims for a former manuscript');
    await guarded.locator('#workspace-reader-dossier').selectOption(fixture.dossier);
    await guarded.waitForFunction(() => Boolean(window.releaseDelayedDossierRead));
    await guarded.evaluate(() => {document.getElementById('workspace-reader').dataset.projectToken = 'c'.repeat(64);});
    await releaseRead();
    await expect(companion).not.toContainText('Delayed claims for a former manuscript');
    await expect(companion.locator('li')).toHaveCount(0);
    assert.deepEqual(errors, []);
    await guarded.close();
    const native = await browser.newPage({viewport: {width: 1440, height: 950}});
    const relationWrites = [];
    native.on('request', request => { if (request.method() === 'POST') relationWrites.push(request.url()); });
    await native.goto(fixture.url);
    await native.locator('#tab-view-research').click();
    await native.locator(`[data-research-detail=dossier][data-record-id="${fixture.dossier}"]`).click();
    const nativeClaims = native.locator('.research-dossier-claims');
    await nativeClaims.locator(`[data-manuscript-links-dossier="${fixture.dossier}"]`).first().click();
    await expect(native.locator('#research-manuscript-review blockquote')).toHaveText('A bird');
    await native.locator('#research-manuscript-review [data-manuscript-link-jump]').click();
    await expect(native.locator('#tab-view-analysis')).toHaveAttribute('aria-selected', 'true');
    await expect(native.locator('#chapters .ptext').first()).toBeFocused();
    await native.locator('#chapters [data-manuscript-links-paragraph]').click();
    await expect(native.locator('[data-passage-research]')).toHaveAttribute('data-state', 'ready');
    await native.locator('[data-passage-research] [data-manuscript-links-paragraph]').click();
    await expect(native.locator('#research-manuscript-review blockquote')).toHaveText('A bird');
    await native.locator('#research-manuscript-review [data-research-history=claim]').click();
    await expect(native.locator('#research-revision-history-detail')).toContainText('Current linked');
    await native.locator('#research-revision-history-detail [data-research-history=dossier]').click();
    await expect(native.locator('#research-revision-history-detail')).toContainText('Current synthetic dossier notes.');
    await expect(native.locator('#research-revision-history-detail')).not.toContainText('Revised synthetic dossier notes.');
    await native.keyboard.press('Escape');
    await native.locator('#research-manuscript-review [data-research-history=claim]').click();
    await expect(native.locator('#research-revision-history-detail')).toContainText('Current linked');
    await native.locator('#research-revision-history-detail [data-manuscript-links-claim]').click();
    await expect(native.locator('#modal-research-revision')).not.toBeVisible();
    await expect(native.locator('#research-manuscript-review blockquote')).toHaveText('A bird');
    assert.deepEqual(relationWrites, [], 'Following real saved associations and history never publishes a change');
    await native.close();
    console.log('Dossier linked claims: seven locales, desktop/mobile, current associations, shared history, retry and delayed/wrong-root guards passed. Screenshots: ' + artifacts);
  } finally {
    if (browser) await browser.close();
    server.kill('SIGTERM');
    await Promise.race([once(server, 'exit'), new Promise(resolve => setTimeout(resolve, 3000))]);
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
