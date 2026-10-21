// Exact saved decision/dossier comparison stays inside the existing Review flow.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-decision-review-'));

(async () => {
  const server = await startNativeServer(`
import json, re, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
from lixity.workspace_labels import WORKSPACE_LABELS
base = Path(sys.argv[1]); project = base / 'synthetic-project'
api.init(project, title='Synthetic decision comparison')
dossier = api.create_dossier(project, title='Synthetic <img src=x onerror=alert(1)> dossier',
    body='# Earlier dossier\\n\\nThe original synthetic garden gate was blue.\\n\\n## Whole dossier context\\n\\nAn earlier author note.')['dossier_id']
decision = api.record_decision(project, title='Synthetic <script>alert(1)</script> decision',
    rationale='Original synthetic choice.', dossier_ids=[dossier])['decision_id']
current = api.get_record(project, 'decision', decision)
api.acknowledge_decision(project, decision, dossier, expected_snapshot=current['snapshot'],
    expected_decision_revision=1, expected_dossier_revision=1, status='applied')
current = api.get_record(project, 'dossier', dossier)
api.revise_record(project, 'dossier', dossier, changes={'body': '# Current dossier\\n\\nThe revised synthetic garden gate is green.\\n\\n## Separate context\\n\\nAn unchanged synthetic note outside any identified section.'},
    expected_snapshot=current['snapshot'], expected_revision=1, change_kind='supersession', reason='Synthetic dossier update')
current = api.get_record(project, 'decision', decision)
api.revise_record(project, 'decision', decision, changes={'rationale': 'The latest synthetic choice keeps the garden gate green.',
    'impact_on_plot': 'A synthetic visitor uses the garden gate.'}, expected_snapshot=current['snapshot'],
    expected_revision=1, change_kind='supersession', reason='Synthetic decision update')
other = api.create_dossier(project, title='Synthetic dossier without assessment', body='Unassessed synthetic dossier.')['dossier_id']
other_decision = api.record_decision(project, title='Synthetic unassessed decision', rationale='An explicit choice.', dossier_ids=[other])['decision_id']
api.record_decision(project, title='Synthetic unlinked decision', rationale='No dossier link.')
manuscript = project / 'manuscript.md'
manuscript.write_text('# Synthetic manuscript\\n\\nA bird crosses the quiet garden.\\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.research_dir = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.exports_dir = str(base / 'exports')
labels = {}
for locale in ('en','de','fr','es','it','pt','nl'):
    LixityServerHandler.language = locale
    LixityServerHandler.refresh()
    (base / (locale + '.html')).write_text(LixityServerHandler.dashboard_html, encoding='utf-8')
    labels[locale] = WORKSPACE_LABELS[locale]
token = re.search(r'data-manuscript-project-token="([^"]+)"', LixityServerHandler.dashboard_html).group(1)
for locale in labels:
    shell = base / (locale + '.html'); text = shell.read_text(encoding='utf-8')
    old = re.search(r'data-manuscript-project-token="([^"]+)"', text).group(1)
    shell.write_text(text.replace(old, token), encoding='utf-8')
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'decision': decision,
    'dossier': dossier, 'other_decision': other_decision, 'other': other, 'labels': labels}), flush=True)
server.serve_forever()
`, artifacts);
  let browser;
  try {
    browser = await launchChromium();
    for (const [locale, labels] of Object.entries(server.fixture.labels)) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 1000}});
      page.setDefaultTimeout(7000);
      const errors = [], writes = [], reads = [], external = [];
      let recordMode = 'native', postMode = 'native', impactMode = 'native', releases = [], postReleases = [], impactReleases = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/*', async route => {
        const request = route.request(), url = new URL(request.url());
        if (url.origin !== server.fixture.url) {external.push(request.url()); return route.abort();}
        if (url.pathname === '/') return route.fulfill({contentType: 'text/html', body: fs.readFileSync(path.join(artifacts, locale + '.html'), 'utf8')});
        if (request.method() !== 'GET') {
          writes.push(request.postDataJSON());
          if (postMode === 'failed') return route.fulfill({status:503,json:{ok:false,message:'Synthetic save unavailable'}});
          if (postMode === 'conflict') return route.fulfill({status:409,json:{ok:false,message:'Synthetic changed snapshot'}});
          if (postMode === 'held') {
            const response = await route.fetch();
            await new Promise(resolve => {postReleases.push(resolve);});
            return route.fulfill({response});
          }
          return route.continue();
        }
        if (url.pathname === '/api/research/record') {
          reads.push({kind: url.searchParams.get('kind'), id: url.searchParams.get('id'), revision: url.searchParams.get('revision')});
          const response = await route.fetch(), data = await response.json();
          if (recordMode === 'held') await new Promise(resolve => {releases.push(resolve);});
          if (recordMode === 'failed') return route.fulfill({json: {ok:false,message:'Synthetic saved version unavailable'}});
          if (recordMode === 'failed-earlier' && url.searchParams.get('revision') === '1')
            return route.fulfill({json: {ok:false,message:'Synthetic earlier version unavailable'}});
          if (recordMode === 'wrong-snapshot') data.snapshot = 'f'.repeat(64);
          if (recordMode === 'wrong-project') data.project_id = 'urn:uuid:00000000-0000-4000-8000-000000000000';
          if (recordMode === 'wrong-record-project') data.record.project_id = 'urn:uuid:00000000-0000-4000-8000-000000000000';
          if (recordMode === 'wrong-schema') data.schema_version = 'research-record-local/invalid';
          if (recordMode === 'wrong-kind') data.kind = 'claim';
          if (recordMode === 'wrong-id') data.record_id = server.fixture.other;
          if (recordMode === 'wrong-revision') data.record.revision += 1;
          if (recordMode === 'wrong-latest') data.latest_revision += 1;
          if (recordMode === 'missing-body' && data.kind === 'dossier') delete data.record.body;
          return route.fulfill({json:data});
        }
        if (url.pathname === '/api/research/decision-impact' && impactMode === 'held') {
          const response = await route.fetch();
          await new Promise(resolve => {impactReleases.push(resolve);});
          return route.fulfill({response});
        }
        return route.continue();
      });
      await page.goto(server.fixture.url);
      await page.locator('#tab-view-research').click();
      await page.locator('[data-rtab=decisions]').click();
      await page.locator('#r-decision-composer > summary').click();
      await page.locator('#r-decision-title').fill('Unsubmitted synthetic decision draft');
      await page.locator('#r-decision-rationale').fill('Preserve this synthetic rationale draft.');
      await page.locator('[data-rtab=review]').click();
      const card = page.locator('#research-editorial-review > .research-card').filter({has: page.locator('[data-decision-ack-decision="' + server.fixture.decision + '"]')});
      // Without the comparison action a reader must switch through separate viewers.
      const comparison = card.locator('[data-decision-review]');
      await expect(comparison).toHaveCount(1);
      await comparison.locator(':scope > summary').click();
      await expect(comparison.locator('[data-decision-review-latest=decision]')).toContainText('The latest synthetic choice keeps the garden gate green.');
      await expect(comparison.locator('[data-decision-review-latest=dossier]')).toContainText('The revised synthetic garden gate is green.');
      await expect(comparison.locator('[data-decision-review-earlier]')).toContainText('The original synthetic garden gate was blue.');
      assert.deepEqual(reads.slice(-3).map(item => [item.kind, item.revision]).sort(), [['decision','2'],['dossier','1'],['dossier','2']]);
      await expect(comparison.locator('[data-decision-review-latest=decision]')).toContainText(labels.research_decision_review_latest_decision.replace('{revision}', '2'));
      await expect(comparison.locator('[data-decision-review-latest=dossier]')).toContainText(labels.research_decision_review_latest_dossier.replace('{revision}', '2'));
      await expect(comparison).toContainText(labels.research_decision_review_scope);
      await expect(comparison).toContainText(labels.research_decision_review_assessment.replace('{decision}','1').replace('{dossier}','1'));
      assert.equal(await comparison.locator('script,img[src=x]').count(), 0, 'Authored titles stay inert');
      assert.equal(writes.length, 0, 'Opening and reading records never marks applied');
      const columns = await comparison.locator('.research-decision-review-grid > section').evaluateAll(elements => elements.map(element => {const r = element.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width};}));
      if (width === 1440) assert.ok(columns[1].x > columns[0].x + columns[0].width - 2, 'Desktop dossier is alongside the decision');
      else assert.ok(columns[1].y > columns[0].y, 'Narrow dossier is stacked after the decision');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
      await card.screenshot({path:path.join(artifacts, `comparison-${locale}-${width}.png`)});
      await comparison.locator('[data-decision-review-close]').click();
      await expect(comparison).not.toHaveAttribute('open', '');
      await expect(comparison.locator(':scope > summary')).toBeFocused();
      const beforeReopen = reads.length;
      await comparison.locator(':scope > summary').click();
      await expect(comparison.locator('[data-decision-review-latest=dossier]')).toBeVisible();
      assert.equal(reads.length, beforeReopen, 'A loaded exact comparison survives collapse');
      await expect(comparison.locator('[data-decision-review-latest=dossier]')).toContainText('An unchanged synthetic note outside any identified section.');
      await expect(page.locator('#r-decision-title')).toHaveValue('Unsubmitted synthetic decision draft');
      await expect(page.locator('#r-decision-rationale')).toHaveValue('Preserve this synthetic rationale draft.');
      if (locale === 'en') {
        await comparison.locator('[data-decision-review-latest=decision] [data-research-history]').focus();
        await page.keyboard.press('Escape');
        await expect(comparison).not.toHaveAttribute('open', '');
        await expect(comparison.locator(':scope > summary')).toBeFocused();
        await page.keyboard.press('Enter');
        await expect(comparison.locator('[data-decision-review-latest=dossier]')).toBeVisible();
        await page.locator('html').evaluate(element => {element.dataset.theme = 'dark';});
        await card.screenshot({path:path.join(artifacts, `comparison-dark-${width}.png`)});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
        await page.locator('html').evaluate(element => {element.dataset.theme = 'light';});
        const refresh = async () => {
          await page.locator('#r-review-refresh').click();
          await expect(comparison).not.toHaveAttribute('open', '');
        };
        const openComparison = async () => comparison.locator(':scope > summary').click();
        // Exact historical routes reuse the existing revision viewer.
        await comparison.locator('[data-decision-review-earlier] [data-research-history=dossier]').click();
        await expect(page.locator('#research-revision-history-detail')).toContainText('The original synthetic garden gate was blue.');
        await expect(page.locator('#research-revision-history-detail')).not.toContainText('The revised synthetic garden gate is green.');
        await page.keyboard.press('Escape');
        const other = page.locator('#research-editorial-review > .research-card').filter({has: page.locator('[data-decision-ack-decision="' + server.fixture.other_decision + '"]')});
        await other.locator('[data-decision-review] > summary').click();
        await expect(other.locator('[data-decision-review]')).toContainText(labels.research_decision_review_no_assessment);
        await expect(other.locator('[data-decision-review-earlier]')).toHaveCount(0);
        for (const failure of ['failed','failed-earlier','wrong-snapshot','wrong-project','wrong-record-project','wrong-schema','wrong-kind','wrong-id','wrong-revision','wrong-latest','missing-body']) {
          await refresh(); recordMode = failure;
          await openComparison();
          await expect(comparison.locator('[data-decision-review-retry]')).toBeVisible();
          await expect(comparison.locator('[data-decision-review-latest]')).toHaveCount(0);
          const failedReads = reads.slice(-3).map(item => [item.kind,item.revision]);
          recordMode = 'native';
          await comparison.locator('[data-decision-review-retry]').click();
          await expect(comparison.locator('[data-decision-review-latest=dossier]')).toContainText('The revised synthetic garden gate is green.');
          assert.deepEqual(reads.slice(-3).map(item => [item.kind,item.revision]), failedReads, 'Retry never adopts newer versions or another candidate');
        }
        await refresh(); recordMode = 'held'; releases = [];
        await openComparison();
        await expect.poll(() => releases.length).toBe(3);
        await comparison.locator('[data-decision-review-close]').click();
        recordMode = 'native'; releases.splice(0).forEach(resolve => resolve());
        await expect(comparison.locator('[data-decision-review-latest]')).toHaveCount(0);
        await openComparison();
        await expect(comparison.locator('[data-decision-review-latest=dossier]')).toContainText('The revised synthetic garden gate is green.');
        // A copied root can have the same project UUID and snapshot. Its token
        // still invalidates the in-flight read and the old write controls.
        await refresh(); recordMode = 'held'; releases = [];
        await openComparison();
        await expect.poll(() => releases.length).toBe(3);
        const oldToken = await page.locator('#research-manager').getAttribute('data-research-token');
        await page.locator('#research-manager').evaluate(element => {element.dataset.researchToken = 'synthetic-other-selected-root';});
        recordMode = 'native'; releases.splice(0).forEach(resolve => resolve());
        await expect(comparison.locator('[data-decision-review-retry]')).toBeVisible();
        await expect(comparison.locator('[data-decision-review-latest]')).toHaveCount(0);
        const beforeStaleWrite = writes.length;
        await card.locator('[data-decision-ack-status=applied]').click();
        await expect(card.locator('[data-decision-ack-feedback]')).toContainText(labels.research_decision_ack_conflict);
        assert.equal(writes.length, beforeStaleWrite, 'A stale control cannot write into another selected root');
        await page.locator('#research-manager').evaluate((element, token) => {element.dataset.researchToken = token;}, oldToken);
        await refresh(); await openComparison();
        await expect(comparison.locator('[data-decision-review-latest=dossier]')).toBeVisible();
        await comparison.locator('[data-decision-review-close]').click();
        await page.locator('#research-manager').evaluate(element => {element.dataset.researchToken = 'synthetic-other-selected-root';});
        await openComparison();
        await expect(comparison.locator('[data-decision-review-retry]')).toBeVisible();
        await page.locator('#research-manager').evaluate((element, token) => {element.dataset.researchToken = token;}, oldToken);
        await comparison.locator('[data-decision-review-retry]').click();
        await expect(comparison.locator('[data-decision-review-latest=dossier]')).toContainText('The revised synthetic garden gate is green.');
        await page.locator('[data-rtab=decisions]').click();
        const impactButton = page.locator('[data-decision-impact="' + server.fixture.decision + '"]');
        const impact = impactButton.locator('..').locator(':scope > .research-details-body');
        impactMode = 'held'; impactReleases = [];
        await impactButton.click();
        await expect.poll(() => impactReleases.length).toBe(1);
        await page.locator('#research-manager').evaluate(element => {element.dataset.researchToken = 'synthetic-other-selected-root';});
        impactMode = 'native'; impactReleases.splice(0).forEach(resolve => resolve());
        await expect(impact).toContainText(labels.research_decision_ack_conflict);
        await expect(impact.locator('[data-decision-ack-status]')).toHaveCount(0);
        await expect(impact.locator('[data-decision-review]')).toHaveCount(0);
        await page.locator('#research-manager').evaluate((element, token) => {element.dataset.researchToken = token;}, oldToken);
        await impactButton.click(); await impactButton.click();
        await expect(impact.locator('[data-decision-review]')).toHaveCount(1);
        await impact.locator('[data-decision-review] > summary').click();
        await expect(impact.locator('[data-decision-review-latest=dossier]')).toContainText('The revised synthetic garden gate is green.');
        assert.equal(writes.length, 0);
      }
      // Save/reopen only after every locale has inspected the original earlier
      // assessment; all native writes stay inside the disposable archive.
      if (locale === 'nl' && width === 320) {
        await page.evaluate(() => {window.decisionReviewDossierNode = document.querySelector('[data-decision-review-latest=dossier] .research-dossier-body-rendered');});
        const pair = card.locator('.research-decision-acknowledgement');
        const snapshot = await pair.getAttribute('data-decision-ack-snapshot');
        postMode = 'failed';
        await pair.locator('[data-decision-ack-status=applied]').click();
        await expect(pair.locator('[data-decision-ack-feedback]')).toContainText('Synthetic save unavailable');
        await expect(comparison.locator('[data-decision-review-earlier]')).toBeVisible();
        postMode = 'conflict';
        await pair.locator('[data-decision-ack-status=applied]').click();
        await expect(pair.locator('[data-decision-ack-feedback]')).toContainText(labels.research_decision_ack_conflict);
        assert.equal(await pair.getAttribute('data-decision-ack-snapshot'), snapshot);
        postMode = 'held';
        await pair.locator('[data-decision-ack-status=applied]').click();
        await expect.poll(() => postReleases.length).toBe(1);
        await expect(pair.locator('[data-decision-ack-status=applied]')).toBeDisabled();
        const count = writes.length;
        await page.evaluate(() => document.querySelector('#research-editorial-review [data-decision-ack-status=applied]').click());
        assert.equal(writes.length, count);
        assert.equal(writes.at(-1).expected_snapshot, snapshot);
        assert.equal(writes.at(-1).expected_decision_revision, 2);
        assert.equal(writes.at(-1).expected_dossier_revision, 2);
        postMode = 'native'; postReleases.splice(0).forEach(resolve => resolve());
        await expect(pair.locator('[data-decision-ack-status=review_needed]')).toBeVisible();
        await expect(comparison).toHaveAttribute('open', '');
        await expect(comparison.locator('[data-decision-review-earlier]')).toHaveCount(0);
        await expect(comparison).toContainText(labels.research_decision_review_assessment.replace('{decision}','2').replace('{dossier}','2'));
        assert.equal(await page.evaluate(() => window.decisionReviewDossierNode.isConnected), true, 'Successful acknowledgement preserves the opened exact dossier DOM');
        await page.setViewportSize({width:1440,height:1000});
        await pair.locator('[data-decision-ack-status=review_needed]').click();
        await expect(pair.locator('[data-decision-ack-status=applied]')).toBeVisible();
        assert.equal(writes.at(-1).status,'review_needed');
        await pair.locator('[data-decision-ack-status=applied]').click();
        await expect(pair.locator('[data-decision-ack-status=review_needed]')).toBeVisible();
        assert.equal(await page.evaluate(() => window.decisionReviewDossierNode.isConnected), true);
      }
      assert.deepEqual(errors, []); assert.deepEqual(external, []);
      await page.close();
    }
    console.log(`Decision review checks passed; synthetic screenshots: ${artifacts}`);
  } finally {
    if (browser) await browser.close();
    await server.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
