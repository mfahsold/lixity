// Contextual forms and selected-section edits use the existing native workflows.
const {launchChromium, modShortcut, playwrightModule} = require('../../scripts/browser_tools.cjs');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const {createInterface} = require('node:readline');
const assert = require('node:assert/strict');
const {expect} = require(path.join(playwrightModule, 'test'));
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-dossier-workflows-'));
const legacyMiddlePassages = 120;

async function checkEarlyDossierSuggestions(browser, url) {
  const page = await browser.newPage();
  let releaseStatus, releaseSuggestions, statusRequested = false;
  const pendingStatus = new Promise(resolve => { releaseStatus = resolve; });
  const pendingSuggestions = new Promise(resolve => { releaseSuggestions = resolve; });
  try {
    await page.route(request => request.pathname === '/api/research/status', async route => {
      statusRequested = true;
      await pendingStatus;
      await route.continue();
    });
    await page.route(request => request.pathname === '/api/research/manuscript-dossier-drafts', async route => {
      await pendingSuggestions;
      await route.continue();
    });
    await page.goto(url);
    await expect.poll(() => statusRequested).toBe(true);
    await page.locator('#tab-view-research').click();
    await page.locator('#r-dos-drafts-box > summary').press('Enter');
    const load = page.locator('#r-manuscript-dossier-btn');
    await load.press('Enter');
    await expect(load).toBeDisabled();

    // The first project response must arrive before any proposals can render.
    releaseStatus();
    await expect(page.locator('#r-active-root')).toContainText('synthetic-project');
    releaseSuggestions();
    const drafts = page.locator('#r-manuscript-drafts');
    await expect(drafts.locator('[data-draft-select="character:mara"]')).toBeVisible();
    await expect(drafts.locator('[data-draft-select="character:ivo"]')).toBeVisible();
    await expect(load).toBeEnabled();
    await expect(page.locator('#research-dossiers-list')).toContainText('Current synthetic dossier');
  } finally {
    releaseStatus();
    releaseSuggestions();
    await page.close();
  }
}

async function checkDossierComposerNavigation(browser, url) {
  const page = await browser.newPage({viewport: {width: 390, height: 700}});
  try {
    await page.goto(url);
    await page.locator('#tab-view-research').click();
    await page.locator('[data-rtab=dossiers]').click();
    await expect(page.locator('#research-dossiers-list')).toContainText('Current synthetic dossier');
    const composer = page.locator('#r-dos-composer');
    const summary = composer.locator(':scope > summary');
    const ribbon = page.locator('.research-pane-navigation [aria-controls="r-dos-composer"]');
    const title = page.locator('#r-dos-title');
    const body = page.locator('#r-dos-body');
    async function expectTitleInViewport() {
      await expect.poll(() => title.evaluate(node => {
        const rect = node.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && rect.left >= 0 && rect.right <= innerWidth &&
          rect.top >= 0 && rect.bottom <= innerHeight &&
          node.contains(document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2));
      }), {message: 'The dossier title is fully on screen and clear of overlapping controls'}).toBe(true);
    }

    await expect(composer).not.toHaveAttribute('open', '');
    await summary.evaluate(node => {
      node.scrollIntoView({block: 'end', behavior: 'instant'});
      node.focus({preventScroll: true});
    });
    await page.keyboard.press('Enter');
    await expect(composer).toHaveAttribute('open', '');
    await expectTitleInViewport();
    await expect(summary).toBeFocused();

    await title.fill('Unsubmitted character dossier');
    await body.fill('A note in progress.');
    await summary.press('Enter');
    await expect(composer).not.toHaveAttribute('open', '');
    for (let activation = 0; activation < 2; activation++) {
      await ribbon.click();
      await expect(composer).toHaveAttribute('open', '');
      await expectTitleInViewport();
      await expect(title).toBeFocused();
      await expect(title).toHaveValue('Unsubmitted character dossier');
      await expect(body).toHaveValue('A note in progress.');
    }

    await summary.press('Enter');
    await expect(composer).not.toHaveAttribute('open', '');
    await page.locator('#tab-view-analysis').click();
    await page.keyboard.press(modShortcut('k'));
    await expect(page.locator('#command-palette-dialog')).toBeVisible();
    await page.locator('#command-palette-search').fill('Create New Research Dossier');
    await page.keyboard.press('Enter');
    await expect(composer).toHaveAttribute('open', '');
    await expectTitleInViewport();
    await expect(title).toBeFocused();
    await expect(title).toHaveValue('Unsubmitted character dossier');
    await expect(body).toHaveValue('A note in progress.');
  } finally {
    await page.close();
  }
}

async function checkCharacterDossier(browser, fixture, dossierId, legacy) {
  const page = await browser.newPage({viewport: {width: legacy ? 320 : 1440, height: 900}});
  const recordUrl = `${fixture.url}/api/research/record?kind=dossier&id=${dossierId}`;
  const requestMethods = [], analysisReads = [], errors = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/api/')) requestMethods.push(request.method());
    if (url.pathname === '/api/research/dossier-character') analysisReads.push(url.searchParams);
  });
  page.on('pageerror', error => errors.push(error.message));
  try {
    const before = await (await page.request.get(recordUrl)).json();
    assert.equal(before.record.revision, 1);
    await page.goto(fixture.url);
    await page.locator('#tab-view-research').click();
    const summary = page.locator(`#research-dossiers-list [data-research-detail=dossier][data-record-id="${dossierId}"]`);
    await summary.click();
    const dossier = summary.locator('..');
    const analysis = dossier.locator('details[data-dossier-character]');
    await expect(analysis).toBeVisible();
    await expect(analysis).not.toHaveAttribute('open', '');
    assert.deepEqual(analysisReads, [], 'Collapsed analysis leaves the manuscript read on demand');
    await analysis.locator(':scope > summary').press('Enter');
    const overview = analysis.locator('[data-character-overview]');
    const table = analysis.locator('[data-character-distribution]');
    await expect(overview).toBeVisible();
    await expect(table.locator('tbody tr')).toHaveCount(3);
    const count = legacy ? legacyMiddlePassages + 4 : 3;
    await expect(overview).toContainText(new RegExp(`\\b${count}\\b`));
    const chapterCounts = await table.locator('tbody tr').evaluateAll(rows =>
      rows.map(row => Array.from(row.cells, cell => cell.textContent.trim())));
    const expected = [2, 0, legacy ? legacyMiddlePassages + 2 : 1];
    for (const [index, mentions] of expected.entries()) {
      assert.ok(chapterCounts[index].includes(String(mentions)), `Chapter ${index + 1} shows ${mentions} mentions`);
    }

    const passages = analysis.locator('[data-character-passages] [data-character-passage]');
    const more = analysis.locator('[data-character-more]');
    await expect(passages.first()).toBeVisible();
    await expect(passages.first().locator('mark')).toHaveCount(2);
    let pages = 1;
    while (await more.isVisible()) {
      const previousCount = await passages.count();
      await more.press('Enter');
      await expect.poll(() => passages.count()).toBeGreaterThan(previousCount);
      const firstNew = passages.nth(previousCount);
      await expect(firstNew).toBeFocused();
      await expect.poll(() => firstNew.evaluate(node => {
        const rect = node.getBoundingClientRect();
        return rect.top >= 0 && node.contains(document.elementFromPoint(rect.left + rect.width / 2, rect.top + 4));
      })).toBe(true);
      assert.ok(++pages <= legacyMiddlePassages + 2, 'Each page advances the passage list');
    }
    const excerpts = await passages.locator('blockquote').allTextContents();
    assert.equal(excerpts.length, legacy ? legacyMiddlePassages + 2 : 2);
    assert.equal(new Set(excerpts).size, excerpts.length, 'A paragraph with two mentions appears once');
    if (legacy) {
      assert.ok(pages > 1, 'The legacy dossier exposes further reading pages');
      assert.match(excerpts[0], /Rowan kept watch\. Rowan counted the lamps\./);
      const contextBefore = passages.first().locator('[data-character-context="before"]');
      const contextAfter = passages.first().locator('[data-character-context="after"]');
      await expect(contextBefore.locator('p').last()).toHaveText('The mast creaked. A cart stopped nearby.');
      await expect(contextAfter.locator('p').last()).toHaveText('The bell fell quiet. The tide moved back.');
      assert.equal(await contextBefore.evaluate(node => node.nextElementSibling.tagName), 'BLOCKQUOTE');
      assert.equal(await contextAfter.evaluate(node => node.previousElementSibling.tagName), 'BLOCKQUOTE');
      assert.equal(excerpts[0], 'Rowan kept watch. Rowan counted the lamps.');
      for (let number = 1; number <= legacyMiddlePassages; number++) {
        assert.match(excerpts[number], new RegExp(`Rowan recorded the tally ${number} in the notebook\\.`));
      }
      await expect(passages.nth(2)).not.toContainText('Rowan recorded the tally 1 in the notebook.');
      await expect(passages.nth(2)).not.toContainText('Rowan recorded the tally 3 in the notebook.');
      await expect(analysis.locator('[data-character-passages]')).not.toContainText('The storehouse stood empty.');
      await expect(analysis.locator('[data-character-passages]')).not.toContainText('The far scene opened beneath a hill.');
      assert.match(excerpts.at(-1), /called to Rook.*The red paper lantern finally disappeared\./s);
      assert.deepEqual(await passages.last().locator('mark').allTextContents(), ['Rook', 'Rowan']);
      await expect(dossier.locator('.research-dossier-body-rendered')).toContainText('Erste Textstelle');
    } else {
      assert.match(excerpts[0], /Mara waited for Ivo\. Mara took the lantern\./);
      assert.match(excerpts.at(-1), /called to Mare from the quay/);
    }
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Reading fits the viewport');
    const viewport = legacy ? 'mobile' : 'desktop';
    await overview.scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(artifacts, `character-analysis-${viewport}.png`)});
    await table.scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(artifacts, `character-distribution-${viewport}.png`)});
    await passages.last().scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(artifacts, `character-reading-${viewport}.png`)});
    const filter = analysis.locator('[data-character-chapter]');
    await filter.focus();
    await filter.selectOption('2');
    await expect(passages).toHaveCount(0);
    await expect(more).toBeHidden();
    await filter.selectOption('1');
    await expect(passages).toHaveCount(1);
    await expect(passages.first()).toContainText(legacy ? 'Rowan counted the lamps.' : 'Mara took the lantern.');
    await expect(filter).toBeFocused();
    if (legacy) {
      await expect(passages.first().locator('[data-character-context="before"]')).toContainText('The mast creaked.');
      await expect(passages.first().locator('[data-character-context="after"]')).toContainText('The tide moved back.');
      await passages.first().scrollIntoViewIfNeeded();
      await page.screenshot({path: path.join(artifacts, 'character-context-mobile.png')});
      await page.setViewportSize({width: 1440, height: 900});
      await passages.first().scrollIntoViewIfNeeded();
      await page.screenshot({path: path.join(artifacts, 'character-context-desktop.png')});
    }
    assert.match(analysisReads[1].get('analysis_sha256'), /^[a-f0-9]{64}$/);
    assert.ok(analysisReads.slice(1).every(query => query.get('analysis_sha256') === analysisReads[1].get('analysis_sha256')),
      'Reading pages and chapter filters stay bound to the accepted analysis');
    if (!legacy) {
      await page.locator(`[data-workspace-dossier="${dossierId}"]`).click();
      await expect(page.locator('#workspace-reader-dossier')).toHaveValue(dossierId);
      const alongside = page.locator('#workspace-reader-body details[data-dossier-character]');
      await alongside.locator(':scope > summary').press('Enter');
      await expect(alongside.locator('[data-character-passage]').first()).toContainText('Mara took the lantern.');
      await expect(alongside.locator('[data-character-distribution] tbody tr')).toHaveCount(3);
    }
    assert.deepEqual(await (await page.request.get(recordUrl)).json(), before,
      'Reading character analysis preserves the authored text and exact archive revision');
    assert.ok(requestMethods.every(method => method === 'GET'), 'Opening existing character dossiers performs reads');
    assert.deepEqual(errors, []);
  } finally {
    await page.close();
  }
}

(async () => {
  const server = spawn(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-u', '-c', `
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
base = Path(sys.argv[1]); project = base / 'synthetic-project'
api.init(project, title='Synthetic contextual research')
dossier = api.create_dossier(project, title='Current synthetic dossier', body='# Notes\\n\\nOriginal note.\\n\\n# Detail\\n\\nOriginal detail.')
api.create_dossier(project, title='Another synthetic dossier', body='Unrelated body.')
legacy = api.create_dossier(project, title='Figur: Rowan', language='de',
    tags=['manuscript-draft', 'character'],
    body='## Überblick\\n\\n- **Figur:** Rowan\\n\\n## Erste Textstelle\\n\\n„Rowan hielt Wache.“')
manuscript = project / 'manuscript.md'
middle = '\\n\\n'.join(f'Rowan recorded the tally {index} in the notebook.' for index in range(1, ${legacyMiddlePassages} + 1))
manuscript.write_text(
    '# Sample\\n\\n## First chapter\\n\\nMara waited for Ivo. Mara took the lantern.\\n\\n'
    'The mast creaked. A cart stopped nearby.\\n\\nRowan kept watch. Rowan counted the lamps.\\n\\n'
    'The bell fell quiet. The tide moved back.\\n\\n'
    '## Second chapter\\n\\nThe storehouse stood empty.\\n\\n'
    '## Third chapter\\n\\nThe ferryman called to Mare from the quay.\\n\\n' + middle + '\\n\\n'
    '🧭 The runner called to Rook from the quay. Rowan held the soaked map flat as the crew drew nearer, '
    'and the wind whipped along the edge of the pier, scattering scraps of rope and cloth into the water. '
    'The red paper lantern finally disappeared.\\n\\n***\\n\\nThe far scene opened beneath a hill.\\n', encoding='utf-8')
(project / 'lixity.toml').write_text(
    '[characters.Mara]\\naliases = ["Mare"]\\n[characters.Ivo]\\n[characters.Rowan]\\naliases = ["Rook"]\\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.language = 'en'; LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'dossier': dossier['dossier_id'],
    'legacy': legacy['dossier_id']}), flush=True)
server.serve_forever()
`, artifacts], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, stdio: ['ignore', 'pipe', 'pipe']});
  let stderr = '';
  server.stderr.on('data', data => { stderr += data; });
  const lines = createInterface({input: server.stdout});
  let browser;
  try {
    const fixture = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Fixture startup timed out: ' + stderr)), 15000);
      lines.once('line', line => { clearTimeout(timeout); resolve(JSON.parse(line)); });
      server.once('error', reject);
      server.once('exit', code => reject(new Error(`Fixture exited ${code}: ${stderr}`)));
    });
    const dossierListURL = url => url.origin === fixture.url &&
      url.pathname === '/api/research/dossiers' && !url.searchParams.has('id');
    browser = await launchChromium();
    await checkEarlyDossierSuggestions(browser, fixture.url);
    await checkDossierComposerNavigation(browser, fixture.url);
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [], preparations = [], saves = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (request.method() !== 'POST') return;
      if (request.url().endsWith('/research-record-prepare')) preparations.push(request.postDataJSON());
      if (request.url().endsWith('/research-record-revise')) saves.push(request.postDataJSON());
    });
    const details = page.locator(`[data-research-detail=dossier][data-record-id="${fixture.dossier}"]`);
    async function openDetails() {
      await Promise.all([page.waitForResponse(response => dossierListURL(new URL(response.url())), {timeout: 10000}), page.locator('[data-rtab=dossiers]').click()]);
      // A refresh preserves an unchanged open detail, so close it first;
      // clicking blindly would toggle the preserved detail shut.
      if (await details.evaluate(node => node.parentElement.open)) await details.click();
      await details.click();
      await expect(details.locator('..').locator('.research-dossier-actions > summary')).toBeVisible();
    }
    async function openActions() {
      const actions = details.locator('..').locator('.research-dossier-actions');
      if (!await actions.evaluate(node => node.open)) await actions.locator(':scope > summary').click();
      await expect(actions.locator(`[data-dossier-claim="${fixture.dossier}"]`)).toBeVisible();
    }
    async function reviseRecord(transform) {
      const current = await (await page.request.get(fixture.url + '/api/research/record?kind=dossier&id=' + fixture.dossier)).json();
      const response = await page.request.post(fixture.url + '/api/research-record-revise', {data: {
        kind: 'dossier', id: fixture.dossier, expected_snapshot: current.snapshot,
        expected_revision: current.record.revision, changes: transform(current.record),
        change_kind: 'correction', reason: 'Synthetic concurrent section change'
      }});
      assert.equal(response.ok(), true);
      return response.json();
    }
    async function reviseBody(transform) {
      return reviseRecord(record => ({body: transform(record.body)}));
    }
    await page.goto(fixture.url);
    await page.locator('#tab-view-research').click();
    await openDetails();
    await expect(details.locator('..').locator('details[data-dossier-character]')).toHaveCount(0);
    const initialActions = details.locator('..').locator('.research-dossier-actions');
    assert.equal(await initialActions.evaluate(node => node.open), false, 'Dossier reading starts with secondary actions closed');
    await expect(page.locator(`[data-dossier-claim="${fixture.dossier}"]`)).not.toBeVisible();
    const recordBeforeActions = await (await page.request.get(fixture.url + '/api/research/record?kind=dossier&id=' + fixture.dossier)).json();
    await openActions();
    assert.deepEqual(await (await page.request.get(fixture.url + '/api/research/record?kind=dossier&id=' + fixture.dossier)).json(), recordBeforeActions,
      'Opening dossier actions preserves the accepted source record and snapshot');
    await page.evaluate(() => {
      document.getElementById('r-claim-title').value = 'Preserved contextual claim';
      document.getElementById('r-claim-statement').value = 'A synthetic contextual statement.';
    });
    await page.locator(`[data-dossier-claim="${fixture.dossier}"]`).click();
    await expect(page.locator('#r-claim-title')).toHaveValue('Preserved contextual claim');
    await expect(page.locator('#r-claim-title')).toBeFocused();
    await expect(page.locator('#r-claim-dossier-select')).toHaveValue(fixture.dossier);
    assert.equal(await page.locator('#r-claim-dossier-select option:checked').textContent(), 'Current synthetic dossier');
    await page.locator('#r-claim-create-btn').click();
    await expect(page.locator('#r-claim-title')).toHaveValue('');
    const claims = await (await page.request.get(fixture.url + '/api/research/claims')).json();
    assert.equal(claims.claims[0].dossier_id, fixture.dossier);
    await openDetails();
    await openActions();
    await page.evaluate(() => {
      document.getElementById('r-decision-title').value = 'Preserved contextual decision';
      document.getElementById('r-decision-rationale').value = 'A synthetic contextual rationale.';
    });
    await page.locator(`[data-dossier-decision="${fixture.dossier}"]`).click();
    await expect(page.locator('#r-decision-title')).toHaveValue('Preserved contextual decision');
    await expect(page.locator('#r-decision-title')).toBeFocused();
    await expect(page.locator('#r-decision-dossier-select')).toHaveValue(fixture.dossier);
    await page.locator('#r-decision-create-btn').click();
    await expect(page.locator('#r-decision-title')).toHaveValue('');
    const decisions = await (await page.request.get(fixture.url + '/api/research/decisions')).json();
    const decision = await (await page.request.get(fixture.url + '/api/research/record?kind=decision&id=' + decisions.decisions[0].id)).json();
    assert.equal(decision.record.dossier_refs[0].id, fixture.dossier);
    assert.equal(decision.record.dossier_refs[0].revision, 1);
    await openDetails();
    const sectionButton = page.locator('[data-dossier-section=Notes]');
    await sectionButton.click();
    const dialog = page.locator('#modal-research-revision');
    await expect(page.locator('#research-revision-field-body')).toHaveValue('Original note.');
    assert.equal(await page.locator('#research-revision-field-title').count(), 0, 'Selected-section edits show only the body field');
    await expect(page.locator('#research-revision-batch-add')).not.toBeVisible();
    await reviseBody(body => body.replace('Original detail.', 'Concurrent detail.'));
    await page.locator('#research-revision-field-body').fill('Revised note.');
    await page.locator('input[name=research_revision_change_kind][value=correction]').check();
    await page.locator('#research-revision-reason').fill('Synthetic section correction.');
    await page.locator('#research-revision-save').click();
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    await expect(page.locator('#research-revision-merge')).not.toContainText('Concurrent detail.');
    await page.locator('#research-revision-merge-apply').click();
    await expect(page.locator('#research-revision-merge')).not.toBeVisible();
    await page.locator('#research-revision-save').click();
    await expect(dialog).not.toBeVisible();
    const accepted = await (await page.request.get(fixture.url + '/api/research/record?kind=dossier&id=' + fixture.dossier)).json();
    assert.equal(accepted.record.body, '# Notes\n\nRevised note.\n\n# Detail\n\nConcurrent detail.');
    assert.equal(accepted.record.title, 'Current synthetic dossier');
    assert.equal(preparations.at(-1).section, 'Notes');
    assert.equal(preparations.at(-1).changes.body, 'Revised note.');
    assert.equal(saves.at(-1).changes.body, accepted.record.body, 'Save publishes the canonical complete prepared body');
    await openDetails();
    await sectionButton.click();
    await expect(page.locator('#research-revision-field-body')).toHaveValue('Revised note.');
    await page.locator('#research-revision-field-body').fill('My conflicting note.');
    await page.locator('input[name=research_revision_change_kind][value=correction]').check();
    await page.locator('#research-revision-reason').fill('Synthetic conflict review.');
    await reviseBody(body => body.replace('Revised note.', 'Their conflicting note.'));
    await page.locator('#research-revision-save').click();
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    await expect(page.locator('#research-revision-field-body')).toHaveValue('My conflicting note.');
    await expect(page.locator('#research-revision-reason')).toHaveValue('Synthetic conflict review.');
    await expect(page.locator('#research-revision-merge')).not.toContainText('Concurrent detail.');
    await page.locator('#research-revision-merge input[value=mine]').check();
    const sectionVersion = await page.locator('#research-revision-kind').textContent();
    const sectionSaves = saves.length;
    await reviseBody(body => body.replace('Their conflicting note.', 'A later unreviewed conflicting note.'));
    await page.locator('#research-revision-merge-apply').click();
    await expect(page.locator('#research-revision-form')).toHaveAttribute('aria-busy', 'false');
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    await expect(page.locator('#research-revision-merge')).toContainText('A later unreviewed conflicting note.');
    assert.equal(await page.locator('#research-revision-merge input:checked').count(), 0, 'Stale choices cannot apply to another saved section version');
    await expect(page.locator('#research-revision-field-body')).toHaveValue('My conflicting note.');
    await expect(page.locator('#research-revision-reason')).toHaveValue('Synthetic conflict review.');
    assert.equal(await page.locator('#research-revision-kind').textContent(), sectionVersion, 'A stale Apply cannot advance the displayed record version');
    assert.equal(saves.length, sectionSaves, 'Refreshing an unresolved preview never saves');
    const reviewedSection = await (await page.request.get(fixture.url + '/api/research/record?kind=dossier&id=' + fixture.dossier)).json();
    await page.locator('#research-revision-merge input[value=mine]').check();
    await page.locator('#research-revision-merge-apply').click();
    await expect(page.locator('#research-revision-field-body')).toHaveValue('My conflicting note.');
    await expect(page.locator('#research-revision-merge')).not.toBeVisible();
    await page.locator('#research-revision-save').click();
    await expect(dialog).not.toBeVisible();
    assert.equal(saves.at(-1).expected_snapshot, reviewedSection.snapshot, 'Only the explicitly reviewed snapshot can be saved');
    const reconciled = await (await page.request.get(fixture.url + '/api/research/dossiers?id=' + fixture.dossier)).json();
    assert.ok(reconciled.body.includes('My conflicting note.'));
    assert.ok(reconciled.body.includes('Concurrent detail.'));

    // The same shared Apply guard also protects ordinary record edits and a
    // snapshot-only change where this record's own revision has not advanced.
    await openDetails();
    await openActions();
    await page.locator(`[data-research-revise=dossier][data-record-id="${fixture.dossier}"]:not([data-dossier-section])`).click();
    await expect(page.locator('#research-revision-field-title')).toHaveValue('Current synthetic dossier');
    await page.locator('#research-revision-field-title').fill('My reviewed general title');
    await page.locator('input[name=research_revision_change_kind][value=correction]').check();
    await page.locator('#research-revision-reason').fill('Synthetic general conflict review.');
    const theirTitle = await reviseRecord(() => ({title: 'Their first general title'}));
    await page.locator('#research-revision-save').click();
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    await page.locator('#research-revision-merge input[value=mine]').check();
    const generalVersion = await page.locator('#research-revision-kind').textContent();
    const unrelated = await page.request.post(fixture.url + '/api/research-dossier', {data: {
      title: 'Concurrent unrelated dossier', body: 'Synthetic unrelated publication.'
    }});
    assert.equal(unrelated.ok(), true);
    const unchangedRecord = await (await page.request.get(fixture.url + '/api/research/record?kind=dossier&id=' + fixture.dossier)).json();
    assert.equal(unchangedRecord.record.revision, theirTitle.record.revision);
    await page.locator('#research-revision-merge-apply').click();
    await expect(page.locator('#research-revision-form')).toHaveAttribute('aria-busy', 'false');
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    assert.equal(await page.locator('#research-revision-merge input:checked').count(), 0, 'A new HEAD also requires review when the record revision is unchanged');
    assert.equal(await page.locator('#research-revision-kind').textContent(), generalVersion);
    await expect(page.locator('#research-revision-field-title')).toHaveValue('My reviewed general title');
    await page.locator('#research-revision-merge input[value=current]').check();
    await reviseRecord(() => ({title: 'A later unreviewed general title'}));
    const generalSaves = saves.length;
    await page.locator('#research-revision-merge-apply').click();
    await expect(page.locator('#research-revision-form')).toHaveAttribute('aria-busy', 'false');
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    await expect(page.locator('#research-revision-merge')).toContainText('A later unreviewed general title');
    assert.equal(await page.locator('#research-revision-merge input:checked').count(), 0);
    await expect(page.locator('#research-revision-field-title')).toHaveValue('My reviewed general title');
    await expect(page.locator('#research-revision-reason')).toHaveValue('Synthetic general conflict review.');
    assert.equal(await page.locator('#research-revision-kind').textContent(), generalVersion);
    assert.equal(saves.length, generalSaves);
    const reviewedGeneral = await (await page.request.get(fixture.url + '/api/research/record?kind=dossier&id=' + fixture.dossier)).json();
    await page.locator('#research-revision-merge input[value=mine]').check();
    await page.locator('#research-revision-merge-apply').click();
    await expect(page.locator('#research-revision-merge')).not.toBeVisible();
    await page.locator('#research-revision-save').click();
    await expect(dialog).not.toBeVisible();
    assert.equal(saves.at(-1).expected_snapshot, reviewedGeneral.snapshot, 'The published mutation stays bound to the final reviewed snapshot');
    const reviewedTitle = await (await page.request.get(fixture.url + '/api/research/record?kind=dossier&id=' + fixture.dossier)).json();
    assert.equal(reviewedTitle.record.title, 'My reviewed general title');
    assert.ok(reviewedTitle.record.body.includes('My conflicting note.'));

    const draftWrites = [];
    page.on('request', request => {
      if (request.method() === 'POST' && /\/api\/research-dossier(?:-from-manuscript)?$/.test(request.url())) {
        draftWrites.push(request.postDataJSON());
      }
    });
    const draftsBox = page.locator('#r-dos-drafts-box');
    const loadDrafts = page.locator('#r-manuscript-dossier-btn');
    const draftList = page.locator('#r-manuscript-drafts');
    const preview = draftList.locator('#r-manuscript-draft-preview');
    const ivoDraft = draftList.locator('[data-draft-select="character:ivo"]');
    const maraDraft = draftList.locator('[data-draft-select="character:mara"]');
    const characterKind = draftList.locator('[data-draft-kind=character]');
    const sceneKind = draftList.locator('[data-draft-kind=scene]');
    const manualDossier = draftList.getByRole('button', {name:'Create a character dossier manually'});
    await draftsBox.locator(':scope > summary').press('Enter');
    await loadDrafts.press('Enter');
    await expect(ivoDraft).toBeVisible();
    await expect(maraDraft).toHaveAttribute('aria-pressed', 'true');
    await expect(loadDrafts).toBeFocused();
    await ivoDraft.press('Space');
    await expect(preview).toContainText('Ivo');
    await expect(ivoDraft).toBeFocused();
    await sceneKind.press('Enter');
    await expect(sceneKind).toBeFocused();
    await expect(preview).toContainText(/scenes?/i);
    await characterKind.press('Enter');
    await expect(characterKind).toBeFocused();
    await expect(ivoDraft).toHaveAttribute('aria-pressed', 'true');
    assert.deepEqual(draftWrites, [], 'Opening and browsing previews sends no save');
    await preview.locator('[data-create-manuscript-draft="character:ivo"]').press('Enter');
    await expect(ivoDraft).toHaveCount(0);
    await expect(maraDraft).toBeFocused();
    await expect(preview).toContainText('Mara');
    assert.equal(draftWrites[0].draft_id, 'character:ivo');
    await preview.locator('[data-create-manuscript-draft="character:mara"]').press('Enter');
    await expect(manualDossier).toBeVisible();
    await expect(draftList).toContainText('There are currently no new character suggestions.');
    await expect(preview).toContainText(/scenes?/i);
    const savedDossiers = await (await page.request.get(fixture.url + '/api/research/dossiers')).json();
    assert.ok(savedDossiers.dossiers.some(item => item.title === 'Character: Ivo'));
    const maraDossier = savedDossiers.dossiers.find(item => item.title === 'Character: Mara');
    assert.ok(maraDossier);
    await checkCharacterDossier(browser, fixture, maraDossier.id, false);
    await checkCharacterDossier(browser, fixture, fixture.legacy, true);

    const dossierTitle = page.locator('#r-dos-title');
    const dossierBody = page.locator('#r-dos-body');
    const dossierTags = page.locator('#r-dos-tags');
    await page.evaluate(() => {
      document.getElementById('r-dos-title').value = 'Unsubmitted dossier';
      document.getElementById('r-dos-body').value = 'Preserved notes.';
      document.getElementById('r-dos-tags').value = 'working';
    });
    await manualDossier.press('Enter');
    await expect(dossierTitle).toBeFocused();
    await expect(dossierTitle).toHaveValue('Unsubmitted dossier');
    await expect(dossierBody).toHaveValue('Preserved notes.');
    await expect(dossierTags).toHaveValue('working');
    await page.route('**/api/research/manuscript-dossier-drafts?*', route =>
      route.fulfill({json:{ok:true, drafts:[], skipped_existing:2}}));
    await loadDrafts.press('Enter');
    await expect(preview).toHaveCount(0);
    await expect(manualDossier).toBeVisible();
    await dossierTitle.fill('');
    await dossierBody.fill('');
    await dossierTags.evaluate(node => { node.value = ''; });
    await manualDossier.press('Enter');
    await expect(dossierTitle).toBeFocused();
    await expect(dossierBody).toHaveValue(/Motivation/i);
    await expect(dossierTags).toHaveValue('character');
    assert.deepEqual(draftWrites.map(write => write.draft_id), ['character:ivo', 'character:mara'],
      'Only explicit manuscript draft saves create records');
    await page.unroute('**/api/research/manuscript-dossier-drafts?*');

    for (const language of ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl']) {
      await page.request.post(fixture.url + '/api/settings', {data: {language}});
      await page.reload();
      await page.locator('#tab-view-research').click();
      await openDetails();
      await sectionButton.click();
      await expect(page.locator('#research-revision-field-body')).toHaveValue('My conflicting note.');
      for (const width of language === 'en' ? [1440, 390, 320] : [320]) {
        await page.setViewportSize({width, height: 900});
        assert.ok(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth), `${language} ${width}px section dialog overflow`);
        await dialog.screenshot({path: path.join(artifacts, `section-${language}-${width}.png`)});
      }
      await page.keyboard.press('Escape');
      if (!await draftsBox.evaluate(node => node.open)) await draftsBox.locator(':scope > summary').press('Enter');
      await loadDrafts.press('Enter');
      const localizedManual = draftList.locator('[data-draft-manual-character]');
      await expect(localizedManual).toBeVisible();
      const localizedLabel = await localizedManual.textContent();
      assert.ok(localizedLabel && !localizedLabel.startsWith('research_'), `${language} manual action must be localized`);
      assert.ok(await localizedManual.evaluate(button => button.scrollWidth <= button.clientWidth),
        `${language} manual action fits at 320px`);
      if (language === 'de') await draftList.screenshot({path:path.join(artifacts, 'dossier-suggestions-de-320.png')});
      await localizedManual.press('Enter');
      await expect(dossierTitle).toBeFocused();
      await expect(dossierBody).not.toHaveValue('');

      const labels = require(path.join(root, 'src/lixity/locales', `${language}.json`));
      const legacySummary = page.locator(`#research-dossiers-list [data-research-detail=dossier][data-record-id="${fixture.legacy}"]`);
      await legacySummary.click();
      const character = legacySummary.locator('..').locator('details[data-dossier-character]');
      const characterSummary = character.locator(':scope > summary');
      await expect(characterSummary).toHaveText(labels.research_dossier_character_heading);
      await characterSummary.press('Enter');
      await expect(character.getByText(labels.research_dossier_character_distribution, {exact: true}).first()).toBeVisible();
      await expect(character.getByText(labels.research_dossier_character_passages, {exact: true}).first()).toBeVisible();
      await expect(character.getByText(labels.research_dossier_character_context_hint, {exact: true})).toBeVisible();
      const firstMatch = character.locator('[data-character-passage]').first();
      await expect(firstMatch.locator('[data-character-context="before"] p').first()).toHaveText(labels.research_dossier_character_context_before);
      await expect(firstMatch.locator('[data-character-context="after"] p').first()).toHaveText(labels.research_dossier_character_context_after);
      if (language === 'de') {
        await characterSummary.scrollIntoViewIfNeeded();
        await page.screenshot({path: path.join(artifacts, 'character-analysis-de-320.png')});
      }
      const dimensions = await character.evaluate(node => {
        const bounds = node.getBoundingClientRect();
        const overflow = Array.from(node.querySelectorAll('*'))
          .filter(child => child.getBoundingClientRect().right > bounds.right + 1)
          .slice(0, 12).map(child => `${child.tagName}.${child.className}`);
        return {scroll: node.scrollWidth, client: node.clientWidth, overflow};
      });
      assert.ok(dimensions.scroll <= dimensions.client,
        `${language} character analysis fits at 320px: ${JSON.stringify(dimensions)}`);
    }
    assert.deepEqual(errors, []);
    console.log(`Dossier workflows: contextual claim/decision pins, concurrent section edits, manuscript suggestions, manual dossiers and exact paged character readings with nearby context passed. Seven locales at 1440/390/320. Screenshots: ${artifacts}`);
  } finally {
    if (stderr.includes('Traceback')) console.error(stderr);
    if (browser) await browser.close();
    lines.close();
    if (server.exitCode === null) { const exited = once(server, 'exit'); server.kill(); await exited; }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
