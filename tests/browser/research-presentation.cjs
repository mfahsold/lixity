// Saved research history keeps one selected context and readable localized fields.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-research-presentation-'));

(async () => {
  const server = await startNativeServer(`
import json, re, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
from lixity.workspace_labels import WORKSPACE_LABELS
base = Path(sys.argv[1]); project = base / 'synthetic-project'
api.init(project, title='Synthetic presentation project')
source = base / 'source.txt'; source.write_text('The synthetic archive opened in 1924. A retained synthetic sentence.', encoding='utf-8')
capture = api.ingest(project, source, allow_retention=True, title='Synthetic retained source')
passage = api.get_source(project, capture['source_id'])['passages'][0]['id']
dossier = api.create_dossier(project, title='Synthetic dossier', body='# Notes\\n\\n**Synthetic** dossier body.', evidence_ids=[passage])['dossier_id']
claim = api.create_claim(project, title='Synthetic claim <img src=x onerror=window.presentationInjected=true>', statement='Original synthetic statement.', confidence='evidenced', dossier_id=dossier, time_period='1924', place='Synthetic garden', actors=['Mara'], tags=['synthetic'])['claim_id']
empty = api.create_claim(project, title='Synthetic unlinked claim', statement='No optional scope or dossier.')['claim_id']
link = api.link_evidence(project, claim_id=claim, passage_id=passage, relation='supports', reviewer='Synthetic reviewer')['evidence_link_id']
relation = api.create_claim_relation(project, claim, empty, rationale='Original synthetic relation.')['relation_id']
decision = api.record_decision(project, title='Synthetic decision', rationale='Original synthetic rationale.', claim_id=claim, dossier_ids=[dossier], deviation_from_fact=False, impact_on_plot='Synthetic plot effect.')['decision_id']
records = {'claim': claim, 'dossier': dossier, 'evidence_link': link, 'claim_relation': relation, 'decision': decision}
changes = {'claim': {'statement': 'Current synthetic statement.'}, 'dossier': {'body': '# Notes\\n\\nCurrent synthetic dossier body.'}, 'evidence_link': {'rationale': 'Current synthetic evidence rationale.'}, 'claim_relation': {'rationale': 'Current synthetic relation rationale.'}, 'decision': {'rationale': 'Current synthetic decision rationale.'}}
for kind, identifier in records.items():
    current = api.get_record(project, kind, identifier)
    api.revise_record(project, kind, identifier, changes=changes[kind], expected_snapshot=current['snapshot'], expected_revision=1, change_kind='correction', reason='One synthetic ' + kind + ' change reason.')
manuscript = project / 'manuscript.md'; manuscript.write_text('## Synthetic chapter\\n\\nA synthetic bird crosses the garden.\\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project); LixityServerHandler.research_dir = str(project)
LixityServerHandler.source_input = str(manuscript); LixityServerHandler.exports_dir = str(base / 'exports')
for locale in ('en','de','fr','es','it','pt','nl'):
    LixityServerHandler.language = locale; LixityServerHandler.refresh()
    (base / (locale + '.html')).write_text(LixityServerHandler.dashboard_html, encoding='utf-8')
token = re.search(r'data-manuscript-project-token="([^"]+)"', LixityServerHandler.dashboard_html).group(1)
for locale in ('en','de','fr','es','it','pt','nl'):
    shell = base / (locale + '.html'); markup = shell.read_text(encoding='utf-8')
    old = re.search(r'data-manuscript-project-token="([^"]+)"', markup).group(1)
    shell.write_text(markup.replace(old, token), encoding='utf-8')
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'records': records, 'empty': empty, 'labels': WORKSPACE_LABELS}), flush=True)
server.serve_forever()
`, artifacts);
  let browser;
  try {
    browser = await launchChromium();
    const inventory = [];
    const locales = process.env.RESEARCH_PRESENTATION_INVENTORY || process.env.RESEARCH_PRESENTATION_RED ? ['en'] : ['en','de','fr','es','it','pt','nl'];
    for (const locale of locales) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 950}});
      page.setDefaultTimeout(10000);
      const errors = [], writes = [], reads = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => {
        if (request.method() === 'POST') writes.push(request.url());
        else if (request.method() === 'GET') reads.push(new URL(request.url()));
      });
      await page.route(server.fixture.url + '/', route => route.fulfill({contentType: 'text/html', body: fs.readFileSync(path.join(artifacts, locale + '.html'), 'utf8')}));
      await page.route(url => url.pathname === '/api/research/history', async route => {
        const response = await route.fetch(), data = await response.json();
        data.revisions.sort((left, right) => left.revision - right.revision);
        await route.fulfill({json: data});
      });
      await page.goto(server.fixture.url);
      await page.locator('#tab-view-research').click();
      await page.waitForFunction(() => Boolean(researchSelectionProjectId));
      const labels = server.fixture.labels[locale];
      const dialog = page.locator('#modal-research-revision');
      const detail = page.locator('#research-revision-history-detail');
      async function open(kind, id, revision) {
        const firstRead = reads.length;
        await page.evaluate(({kind, id, revision}) => {
          document.getElementById('synthetic-history-entry')?.remove();
          const button = document.createElement('button'); button.id = 'synthetic-history-entry';
          button.dataset.researchHistory = kind; button.dataset.recordId = id;
          if (revision) button.dataset.recordRevision = String(revision);
          button.textContent = 'Synthetic history entry'; document.body.appendChild(button);
        }, {kind, id, revision});
        await page.locator('#synthetic-history-entry').click();
        await expect(detail.locator('dd').first()).toBeVisible();
        return reads.slice(firstRead);
      }
      async function showVersions() {
        const disclosure = page.locator('#research-revision-versions');
        if (!await disclosure.evaluate(node => node.open)) await disclosure.locator(':scope > summary').click();
        await expect(page.locator('#research-revision-history-list [data-research-revision]')).toHaveCount(2);
      }
      const currentText = {claim: 'Current synthetic statement.', dossier: 'Current synthetic dossier body.',
        evidence_link: 'Current synthetic evidence rationale.', claim_relation: 'Current synthetic relation rationale.',
        decision: 'Current synthetic decision rationale.'};
      for (const [kind, id] of Object.entries(server.fixture.records)) {
        const opened = await open(kind, id);
        await expect(detail).toContainText(currentText[kind]);
        assert.equal(opened.filter(url => url.pathname === '/api/research/record' && url.searchParams.get('id') === id)[0].searchParams.get('revision'), null,
          'An ordinary entry asks the record owner for current, without a historical pin');
        assert.equal(opened.filter(url => url.pathname === '/api/research/history').length, 0,
          'Opening an entry does not fetch its secondary version list');
        assert.equal(await page.locator('#research-revision-versions').evaluate(node => node.open), false);
        await expect(page.locator('#research-revision-history-list')).toBeHidden();
        assert.equal(await dialog.locator('[role=tab]').first().getAttribute('id'), 'research-revision-history-tab',
          'Reading is the primary entry mode');
        const order = await dialog.evaluate(node => ({
          fields: node.querySelector('#research-revision-history-detail dl').getBoundingClientRect().top,
          provenance: node.querySelector('.research-revision-provenance').getBoundingClientRect().top,
          versions: node.querySelector('#research-revision-versions > summary').getBoundingClientRect().top,
          technical: node.querySelector('#research-revision-technical > summary').getBoundingClientRect().top,
        }));
        assert.ok(order.fields < order.provenance && order.fields < order.versions && order.fields < order.technical,
          `The entry content precedes provenance, version navigation and technical details: ${JSON.stringify(order)}`);
        const reason = 'One synthetic ' + kind + ' change reason.';
        inventory.push({locale, width, kind, reasonOccurrences: (await dialog.innerText()).split(reason).length - 1,
          versionHeadings: await detail.locator('h4').allTextContents(), fields: await detail.locator('dt').allTextContents(),
          visibleCitations: await dialog.locator('.research-passage-card:visible').count(),
          editCitationsVisible: await page.locator('#research-revision-citations').isVisible()});
        if (locale === 'en' && ['claim', 'decision'].includes(kind)) await dialog.screenshot({path: path.join(artifacts, `${process.env.RESEARCH_PRESENTATION_INVENTORY ? 'before' : 'after'}-${kind}-${width}.png`)});
        if (!process.env.RESEARCH_PRESENTATION_INVENTORY) {
          assert.equal((await dialog.innerText()).split(reason).length - 1, 1, 'Selected change reason is presented once');
          assert.equal(await detail.locator('h4').filter({hasText: labels.research_revision_number.replace('{revision}', '2')}).count(), 0, 'Selected version belongs to one shared context, not a repeated detail heading');
          assert.equal(await page.locator('#research-revision-history-list small').count(), 0, 'Version navigation does not repeat change reasons');
          await showVersions();
          await expect(detail).toContainText(currentText[kind]);
          assert.equal(await page.locator('#research-revision-history-list [data-research-revision]').first().getAttribute('data-research-revision'), '1',
            'The real server history is deliberately presented with an earlier revision first');
          await expect(page.locator('#research-revision-history-list [data-research-revision="2"]')).toHaveAttribute('aria-description', labels.research_revision_correction);
          await expect(page.locator('#research-revision-history-list [data-research-revision="1"]')).toHaveAttribute('aria-description', labels.research_revision_original);
          await expect(page.locator('#research-revision-kind')).toContainText(labels.research_revision_current);
          assert.equal(await detail.locator('time[datetime]').count(), 1, 'Localized provenance keeps its original timestamp');
          assert.equal(await detail.locator('time').getAttribute('datetime'), await detail.locator('time').evaluate(node => node.parentElement.title));
          assert.equal(await page.locator('#research-revision-citations').isVisible(), false, 'The edit-only citation owner stays hidden in History');
          assert.equal(await dialog.locator('.research-passage-card:visible').count(), ['dossier', 'evidence_link', 'decision'].includes(kind) ? 1 : 0, 'Each active quotation is displayed once');
          const shortFields = {dossier: ['notes'], evidence_link: ['passage', 'rationale'],
            claim_relation: ['rationale'], decision: ['title', 'rationale', 'plot_impact', 'dossiers']};
          const visibleFields = await detail.locator('dt').allTextContents();
          assert.ok((shortFields[kind] || []).every(key => visibleFields.includes(labels['research_read_' + key])), 'Prompt-shaped labels use localized reading nouns');
          if (kind === 'claim') {
            await expect(detail).toContainText(labels.research_confidence_evidenced);
            const fields = await detail.locator('dt').allTextContents();
            assert.ok(fields.includes(labels.research_read_title) && fields.includes(labels.research_read_statement), 'Reading uses short title/statement labels');
            assert.ok(['period', 'place', 'actors', 'tags'].every(key => fields.includes(labels['research_read_' + key])), 'Populated optional reading labels are short in every locale');
            assert.ok(!fields.includes(labels.research_claim_title) && !fields.includes(labels.research_claim_statement), 'Edit prompts do not appear as reading labels');
            assert.equal(await detail.locator('dt').filter({hasText: labels.research_revision_dossier_revision}).count(), 0, 'Reference and pin share one row');
            assert.equal(await detail.locator('img').count(), 0, 'Authored titles remain inert');
          }
          if (kind === 'decision') await expect(detail).toContainText(labels.research_value_no);
          if (kind === 'evidence_link') await expect(detail).toContainText(labels.research_relation_supports);
          if (kind === 'claim_relation') {
            await expect(detail).toContainText(labels.research_relation_causes);
            await expect(detail).toContainText(labels.research_relation_active);
          }
          await page.locator('#research-revision-history-list [data-research-revision="1"]').click();
          await expect(page.locator('#research-revision-kind')).toContainText(labels.research_revision_earlier);
          await expect(page.locator('#research-revision-history-list [data-research-revision="1"]')).toHaveAttribute('aria-current', 'true');
          assert.equal((await dialog.innerText()).includes(reason), false, 'Earlier selection does not retain current reason');
        }
        await dialog.locator('.modal-close').click();
      }
      if (!process.env.RESEARCH_PRESENTATION_INVENTORY) {
        await open('claim', server.fixture.empty);
        assert.equal(await detail.locator('dt').filter({hasText: labels.research_dossier}).count(), 0, 'Absent optional dossier is omitted');
        assert.equal(await detail.locator('dt').filter({hasText: labels.research_read_period}).count(), 0, 'Absent optional scope is omitted');
        await dialog.locator('.modal-close').click();
        await open('claim', server.fixture.records.claim);
        await page.locator('#research-revision-edit-tab').click();
        await expect(page.locator('#research-revision-fields')).toContainText(labels.research_claim_statement);
        await page.locator('#research-revision-field-statement').fill('Unsaved synthetic draft.');
        await page.locator('#research-revision-edit-tab').focus();
        await page.keyboard.press('ArrowRight');
        await expect(page.locator('#research-revision-history-tab')).toBeFocused();
        await expect(page.locator('#research-revision-history-tab')).toHaveAttribute('aria-selected', 'true');
        await showVersions();
        await page.locator('#research-revision-history-list [data-research-revision="1"]').click();
        await expect(page.locator('#research-revision-kind')).toContainText(labels.research_revision_earlier);
        await page.locator('#research-revision-history-tab').focus();
        await page.keyboard.press('ArrowLeft');
        await expect(page.locator('#research-revision-edit-tab')).toBeFocused();
        await expect(page.locator('#research-revision-field-statement')).toHaveValue('Unsaved synthetic draft.');
        await expect(page.locator('#research-revision-kind')).toContainText(labels.research_revision_current);
        await page.keyboard.press('End');
        await expect(page.locator('#research-revision-edit-tab')).toBeFocused();
        await expect(page.locator('#research-revision-field-statement')).toHaveValue('Unsaved synthetic draft.');
        await page.keyboard.press('Home');
        await expect(page.locator('#research-revision-history-tab')).toBeFocused();
        await expect(page.locator('#research-revision-kind')).toContainText(labels.research_revision_earlier);
        await dialog.locator('.modal-close').click();
        const pinnedReads = await open('claim', server.fixture.records.claim, 1);
        assert.equal(pinnedReads.find(url => url.pathname === '/api/research/record').searchParams.get('revision'), '1');
        await expect(detail).toContainText('Original synthetic statement.');
        await expect(page.locator('#research-revision-kind')).toContainText(labels.research_revision_earlier);
        assert.equal(await page.locator('#research-revision-versions').evaluate(node => node.open), false,
          'An explicitly pinned entry is readable without expanding version navigation');
        await dialog.locator('.modal-close').click();
        await open('claim', server.fixture.records.claim);
        await expect(detail).toContainText('Current synthetic statement.');
        await dialog.locator('.modal-close').click();
        if (locale === 'en' && width === 1440) {
          // Malformed optional values are data: preserve explicit numeric
          // zero and display an unparseable timestamp literally, without HTML.
          const recordRoute = url => url.pathname === '/api/research/record';
          await page.route(recordRoute, async route => {
            const response = await route.fetch(); const data = await response.json();
            data.record.created_at = 'Unknown <b>timestamp</b>';
            data.record.scope = {...data.record.scope, place: 0};
            await route.fulfill({json: data});
          });
          await open('claim', server.fixture.empty);
          await expect(detail).toContainText('Unknown <b>timestamp</b>');
          const place = detail.locator('dt').filter({hasText: labels.research_read_place});
          await expect(place.locator('xpath=following-sibling::dd[1]')).toHaveText('0');
          assert.equal(await detail.locator('b, time').count(), 0, 'Invalid timestamp is inert raw data');
          await dialog.locator('.modal-close').click(); await page.unroute(recordRoute);
          await open('claim', server.fixture.records.claim);
          await page.locator('#research-revision-edit-tab').click();
          await page.evaluate(() => {document.getElementById('research-manager').dataset.researchToken += '-changed';});
          await page.locator('#research-revision-history-tab').click();
          await expect(detail).toHaveText(labels.research_revision_conflict);
          await dialog.locator('.modal-close').click();
        }
      }
      assert.deepEqual(errors, [], 'No page errors');
      assert.deepEqual(writes, [], 'Presentation and tabs never write authored records');
      await page.close();
    }
    fs.writeFileSync(path.join(artifacts, 'inventory.json'), JSON.stringify(inventory, null, 2));
    console.log(`${process.env.RESEARCH_PRESENTATION_INVENTORY ? 'Inventory' : 'Research presentation GREEN'}: ${inventory.length} rendered type/viewport cases; artifacts ${artifacts}`);
  } finally {
    if (browser) await browser.close();
    await server.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
