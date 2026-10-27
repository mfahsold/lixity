// Exact saved passage context uses the native read-only research contracts.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {startNativeServer} = require('./support/native-server.cjs');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-passage-research-'));
const source = `
import hashlib, json, shutil, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
from lixity.server.pdf_context import research_context_token
from lixity.research.repository import Repository
project = Path(sys.argv[1]) / 'synthetic-project'
api.init(project, title='Synthetic passage research')
dossier = api.create_dossier(project, title='Synthetic pinned dossier', body='# Notes\\n\\nA saved author plan.')
claim = api.create_claim(project, title='Synthetic saved claim <img src=x>', statement='An old authored statement.', confidence='disputed', dossier_id=dossier['dossier_id'])
decision = api.record_decision(project, title='Synthetic associated decision', rationale='An authored plan, not a fact.', dossier_ids=[dossier['dossier_id']])
for index in range(6):
    api.record_decision(project, title=f'Additional decision {index + 1}', rationale='An explicit author choice.', dossier_ids=[dossier['dossier_id']])
manuscript = project / 'manuscript.md'
manuscript.write_text('# Synthetic passage manuscript\\n\\n## Chapter\\n\\n😀 A repeated quotation. A repeated quotation.\\n\\nAn unrelated paragraph contains A repeated quotation.\\n\\nAn empty passage has no association.\\n', encoding='utf-8')
anchor = api.resolve_manuscript_anchor(project, manuscript, query='😀 A repeated quotation.')
api.link_manuscript_claim(project, manuscript, claim['claim_id'], claim_revision=1,
    selection={key: anchor[key] for key in ('start_line','end_line','paragraph_sha256','start','end','quote')},
    expected_project_id=anchor['project_id'], expected_snapshot=anchor['snapshot'],
    expected_source_sha256=hashlib.sha256(manuscript.read_bytes()).hexdigest(), allow_retention=True)
# Distinct exact quotes share one historical record in the backend projection.
text = '😀 A repeated quotation. A repeated quotation.'
for start, end in [(2, 23), (24, 45), (2, 12), (4, 12), (0, 1)]:
    selection = {key: anchor[key] for key in ('start_line', 'end_line', 'paragraph_sha256')}
    selection.update(start=start, end=end, quote=text[start:end])
    current = api.get_record(project, 'claim', claim['claim_id'])
    api.link_manuscript_claim(project, manuscript, claim['claim_id'], claim_revision=1, selection=selection,
        expected_project_id=anchor['project_id'], expected_snapshot=current['snapshot'],
        expected_source_sha256=hashlib.sha256(manuscript.read_bytes()).hexdigest(), allow_retention=True)
other = api.create_claim(project, title='Synthetic saved claim <img src=x>', statement='Unrelated same-title claim.')
anchor = api.resolve_manuscript_anchor(project, manuscript, query='An unrelated paragraph')
api.link_manuscript_claim(project, manuscript, other['claim_id'], claim_revision=1,
    selection={key: anchor[key] for key in ('start_line','end_line','paragraph_sha256','start','end','quote')},
    expected_project_id=anchor['project_id'], expected_snapshot=anchor['snapshot'],
    expected_source_sha256=hashlib.sha256(manuscript.read_bytes()).hexdigest(), allow_retention=True)
for kind, identifier, changes in [('claim', claim['claim_id'], {'title': 'Current claim title', 'confidence': 'evidenced'}), ('dossier', dossier['dossier_id'], {'title': 'Current dossier title'})]:
    current = api.get_record(project, kind, identifier)
    api.revise_record(project, kind, identifier, changes=changes, expected_snapshot=current['snapshot'], expected_revision=1, change_kind='correction', reason='Synthetic current revision')
copied = Path(sys.argv[1]) / 'restored-copy'
shutil.copytree(project, copied)
assert Repository(copied).snapshot().project.id == Repository(project).snapshot().project.id
assert Repository(copied).snapshot().digest == Repository(project).snapshot().digest
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.research_dir = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.exports_dir = str(Path(sys.argv[1]) / 'exports')
LixityServerHandler.language = 'en'; LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'claim': claim['claim_id'], 'other': other['claim_id'], 'dossier': dossier['dossier_id'], 'decision': decision['decision_id'], 'copied_token': research_context_token(copied)}), flush=True)
server.serve_forever()
`;
async function savedResearchAction(page) {
  const menu = page.locator('#manuscript-context-menu');
  if (await menu.isVisible()) await menu.locator('[data-reader-action="values"]').click();
  return page.locator('#reader-inspector-body [data-reader-action="research"]');
}
async function sharedDossierJourney(browser) {
  const sharedSource = source.replace(
    'for start, end in [(2, 23), (24, 45), (2, 12), (4, 12), (0, 1)]:',
    'for start, end in []:').replace("copied = Path(sys.argv[1]) / 'restored-copy'", `
second = api.create_claim(project, title='Another claim in the same dossier', statement='A distinct authored statement.', dossier_id=dossier['dossier_id'])
anchor = api.resolve_manuscript_anchor(project, manuscript, query='😀 A repeated quotation.')
api.link_manuscript_claim(project, manuscript, second['claim_id'], claim_revision=1,
    selection={key: anchor[key] for key in ('start_line','end_line','paragraph_sha256','start','end','quote')},
    expected_project_id=anchor['project_id'], expected_snapshot=anchor['snapshot'],
    expected_source_sha256=hashlib.sha256(manuscript.read_bytes()).hexdigest(), allow_retention=True)
current = api.get_record(project, 'claim', claim['claim_id'])
selection = {key: anchor[key] for key in ('start_line','end_line','paragraph_sha256')}
selection.update(start=2, end=23, quote=text[2:23])
api.link_manuscript_claim(project, manuscript, claim['claim_id'], claim_revision=2, selection=selection,
    expected_project_id=anchor['project_id'], expected_snapshot=current['snapshot'],
    expected_source_sha256=hashlib.sha256(manuscript.read_bytes()).hexdigest(), allow_retention=True)
current = api.get_record(project, 'claim', claim['claim_id'])
api.revise_record(project, 'claim', claim['claim_id'], changes={'title': 'Newest shared claim'}, expected_snapshot=current['snapshot'], expected_revision=2, change_kind='correction', reason='Synthetic third claim revision')
current = api.get_record(project, 'dossier', dossier['dossier_id'])
api.revise_record(project, 'dossier', dossier['dossier_id'], changes={'title': 'Shared current dossier'}, expected_snapshot=current['snapshot'], expected_revision=2, change_kind='correction', reason='Synthetic third revision')
copied = Path(sys.argv[1]) / 'restored-copy'`);
  const server = await startNativeServer(sharedSource, fs.mkdtempSync(path.join(artifacts, 'shared-dossier-')));
  try {
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 950}, reducedMotion: 'reduce'});
      const errors = [], writes = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => { if (request.method() === 'POST') writes.push(request.url()); });
      await page.goto(server.fixture.url);
      const paragraph = page.locator('#chapters .ptext').first();
      const original = await paragraph.locator('.ptext-inner > p').textContent();
      await paragraph.locator('[data-reader-paragraph]').click();
      await (await savedResearchAction(page)).click();
      const context = page.locator('[data-passage-research]');
      await expect(context).toHaveAttribute('data-state', 'ready');
      await expect(context.locator('[data-research-history=claim]:not([data-record-revision])')).toHaveCount(2);
      await expect(context.locator('[data-research-history=dossier]:not([data-record-revision])')).toHaveCount(1);
      await expect(context.getByText('Shared current dossier', {exact: true})).toHaveCount(1);
      await expect(context.locator('[data-passage-research-decisions]')).toHaveCount(1);
      await expect(context.locator('[data-passage-research-associations] blockquote')).toHaveCount(3);
      const claimSections = context.locator('.passage-research-claim');
      for (const [index, title, dossierVersion] of [[0, 'Newest shared claim', 1], [1, 'Another claim in the same dossier', 2]]) {
        const section = claimSections.nth(index);
        await expect(section.locator('[data-research-history=claim]:not([data-record-revision])')).toHaveText(title);
        for (const disclosure of await section.locator('[data-passage-research-associations]').all()) {
          await expect(disclosure).toContainText('Dossier · Version ' + dossierVersion);
        }
      }
      await expect(context.getByText('Newest shared claim', {exact: true})).toHaveCount(1);
      const versions = claimSections.first().locator('[data-passage-research-associations]');
      await expect(versions).toHaveCount(2);
      for (const [index, revision, quote, confidence] of [[0, 1, '😀 A repeated quotation.', 'Disputed'], [1, 2, 'A repeated quotation.', 'With evidence']]) {
        const version = versions.nth(index);
        await expect(version.locator('summary')).toContainText('Version ' + revision);
        await expect(version).toContainText('Claim · Version ' + revision);
        await expect(version).toContainText(confidence);
        await expect(version.locator('blockquote')).toHaveText(quote);
        const pin = claimSections.first().locator(`[data-research-history=claim][data-record-revision="${revision}"]`);
        await expect(pin).toHaveCount(1);
        await pin.click();
        await expect(page.locator('#research-revision-kind')).toContainText('Version ' + revision);
        await expect(page.locator('#research-revision-history-detail')).toContainText(revision === 1 ? 'Synthetic saved claim <img src=x>' : 'Current claim title');
        await page.keyboard.press('Escape');
        await expect(pin).toBeFocused();
      }
      for (const revision of [1, 2]) {
        const pin = context.locator(`[data-research-history=dossier][data-record-revision="${revision}"]`);
        await expect(pin).toHaveCount(1);
        await pin.click();
        await expect(page.locator('#research-revision-kind')).toContainText('Version ' + revision);
        await expect(page.locator('#research-revision-history-detail')).toContainText(revision === 1 ? 'Synthetic pinned dossier' : 'Current dossier title');
        await page.keyboard.press('Escape');
        await expect(pin).toBeFocused();
      }
      const decisions = context.locator('[data-passage-research-decisions]');
      await decisions.locator('summary').first().click();
      await expect(decisions.locator('[data-research-history=decision]')).toHaveCount(5);
      await decisions.locator('details > summary').click();
      await expect(decisions.locator('[data-research-history=decision]')).toHaveCount(7);
      assert.equal(await paragraph.locator('.ptext-inner > p').textContent(), original);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      assert.deepEqual(errors, []); assert.deepEqual(writes, []);
      await decisions.locator('summary').first().click();
      await context.evaluate(node => node.scrollIntoView({block: 'start'}));
      await page.screenshot({path: path.join(artifacts, `shared-dossier-${width}.png`)});
      await page.close();
    }
  } finally { await server.close(); }
}
async function localeJourneys(browser) {
  for (const locale of ['de', 'fr', 'es', 'it', 'pt', 'nl']) {
    const server = await startNativeServer(source.replace("language = 'en'", `language = '${locale}'`), fs.mkdtempSync(path.join(artifacts, locale + '-')));
    try {
      for (const [width, height] of [[1440, 950], [390, 900], [320, 900], [320, 480]]) {
        const page = await browser.newPage({viewport: {width, height}, reducedMotion: 'reduce'});
        await page.goto(server.fixture.url);
        const labels = await page.evaluate(() => Object.fromEntries(['passage_research', 'passage_research_confidence', 'research_confidence_disputed'].map(key => [key, uiLabel(key)])));
        await page.locator('#chapters [data-reader-paragraph]').first().click();
        await expect((await savedResearchAction(page))).toHaveText(labels.passage_research);
        assert.notEqual(labels.passage_research, 'Saved research', locale + ' has translated labels');
        await (await savedResearchAction(page)).click();
        const context = page.locator('[data-passage-research]');
        await expect(context).toHaveAttribute('data-state', 'ready');
        if (height === 480) await expect(context.locator('.passage-record-title').first()).toBeInViewport();
        for (const label of Object.values(labels)) await expect(context).toContainText(label);
        assert.equal(await page.locator('[data-context-tool="research"]').evaluate(button => {
          const text = button.firstChild, range = document.createRange();
          let offset = 0;
          return button.textContent.split(' ').every(word => {
            range.setStart(text, offset); range.setEnd(text, offset + word.length);
            offset += word.length + 1;
            return range.getClientRects().length === 1;
          });
        }), true, locale + ' tool labels wrap between words');
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), locale + ' fits viewport');
        await page.screenshot({path: path.join(artifacts, `passage-${locale}-${width}x${height}.png`)});
        await page.close();
      }
    } finally { await server.close(); }
  }
}

async function assertDockGeometry(page) {
  await expect.poll(() => page.evaluate(() => {
    const dock = document.getElementById('workspace-context-panel'), box = dock.getBoundingClientRect();
    const tabs = dock.querySelector('.context-tool-tabs').getBoundingClientRect();
    const layout = document.getElementById('workspace-reader-layout').getBoundingClientRect();
    const thread = document.getElementById('workbench-thread');
    const boundary = innerWidth < 1100 && !thread.hidden ? thread.getBoundingClientRect().bottom : 0;
    return tabs.top >= boundary && box.bottom <= Math.min(innerHeight, layout.bottom) + 1;
  }), {message: 'Shared context tabs stay below the sticky thread and the dock stays inside viewport/container'}).toBe(true).catch(async error => {
    console.error(await page.evaluate(() => {
      const dock = document.getElementById('workspace-context-panel');
      return {width: innerWidth, scroll: scrollY, dock: dock.getBoundingClientRect().toJSON(),
        tabs: dock.querySelector('.context-tool-tabs').getBoundingClientRect().toJSON(),
        parent: dock.parentElement.getBoundingClientRect().toJSON(),
        top: getComputedStyle(dock).top, maxHeight: getComputedStyle(dock).maxHeight,
        available: dock.style.getPropertyValue('--context-available-height'),
        thread: document.getElementById('workbench-thread').getBoundingClientRect().toJSON()};
    }));
    throw error;
  });
}
async function geometryJourneys(browser, shortServer) {
  const longSource = source.replace("anchor = api.resolve_manuscript_anchor(project, manuscript, query='😀 A repeated quotation.')",
    "manuscript.write_text(manuscript.read_text() + '\\n\\n' + '\\n\\n'.join('Synthetic long reading paragraph %d. ' % n + 'The quiet garden continues. ' * 12 for n in range(50)), encoding='utf-8')\nanchor = api.resolve_manuscript_anchor(project, manuscript, query='😀 A repeated quotation.')");
  const longServer = await startNativeServer(longSource, fs.mkdtempSync(path.join(artifacts, 'long-')));
  try {
    for (const [name, server] of [['short', shortServer], ['long', longServer]]) for (const width of [1440, 1024]) {
      const page = await browser.newPage({viewport: {width, height: 950}, reducedMotion: 'reduce'});
      const errors = []; page.on('pageerror', error => errors.push(error.message));
      await page.goto(server.fixture.url);
      const paragraph = page.locator('#chapters .ptext').first();
      await paragraph.locator('[data-reader-paragraph]').click();
      const top = (await paragraph.boundingBox()).y;
      await (await savedResearchAction(page)).click();
      await expect(page.locator('[data-passage-research]')).toHaveAttribute('data-state', 'ready');
      await assertDockGeometry(page);
      await expect.poll(async () => Math.abs((await paragraph.boundingBox()).y - top)).toBeLessThan(2);
      for (const position of ['reading', 'bottom']) {
        if (position === 'bottom') await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
        for (const tool of ['research', 'analysis', 'dossier']) {
          if (tool !== 'research') await page.locator(`[data-context-tool="${tool}"]`).click();
          if (tool === 'dossier') await expect(page.locator('#workspace-reader-dossier')).toBeEnabled();
          await assertDockGeometry(page);
          const dock = page.locator('#workspace-context-panel');
          const wheel = await dock.evaluate(async node => {
            // Let the scroll-triggered dock fit and ResizeObserver reach paint;
            // a previously overflowing dock can now fit its entire content.
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            const box = node.getBoundingClientRect();
            return {overflows: node.scrollHeight > node.clientHeight + 2, documentScroll: scrollY,
              x: box.x + box.width / 2, y: box.y + Math.min(120, box.height / 2)};
          });
          const beforeScroll = wheel.documentScroll;
          if (wheel.overflows) {
            await page.mouse.move(wheel.x, wheel.y);
            await page.mouse.wheel(0, 200);
            await expect.poll(() => dock.evaluate(node => node.scrollTop)).toBeGreaterThan(0);
            assert.equal(await page.evaluate(() => scrollY), beforeScroll, 'Wheel input scrolls the existing dock, not the manuscript');
          }
          await dock.evaluate(node => { node.scrollTop = node.scrollHeight; });
          assert.equal(await page.evaluate(() => scrollY), beforeScroll, 'Internal dock scrolling leaves document scroll alone');
          await dock.evaluate(node => { node.scrollTop = 0; });
          await assertDockGeometry(page);
          assert.equal(await dock.evaluate(node => getComputedStyle(node).position), 'sticky');
          await page.screenshot({path: path.join(artifacts, `dock-${name}-${width}-${position}-${tool}.png`)});
        }
        // Establish the same requested research tool before changing document scroll.
        if (position === 'reading') {
          await paragraph.locator('[data-reader-paragraph]').click();
          await (await savedResearchAction(page)).click();
          await expect(page.locator('[data-passage-research]')).toHaveAttribute('data-state', 'ready');
        }
      }
      assert.deepEqual(errors, []); await page.close();
    }
  } finally { await longServer.close(); }
}

async function suspensionJourneys(browser, server) {
  for (const width of [1440, 390]) {
    const page = await browser.newPage({viewport: {width, height: 950}, reducedMotion: 'reduce'});
    await page.goto(server.fixture.url);
    const context = page.locator('[data-passage-research]');
    const trigger = page.locator('#chapters [data-reader-paragraph]').first();
    async function open() {
      await trigger.click(); await (await savedResearchAction(page)).click();
    }
    async function suspend(kind) {
      await page.locator(kind === 'overview' ? '#workbench-overview-open' : '#reader-focus').click();
      await expect(context).toBeHidden();
    }
    async function resume(kind) {
      await page.locator(kind === 'overview' ? '#workbench-overview-back' : '#reader-focus').click();
      await expect(context).toBeVisible();
      await expect(page.locator('[data-context-tool="research"]')).toBeVisible();
    }
    for (const kind of ['overview', 'focus']) {
      await open(); await expect(context).toHaveAttribute('data-state', 'ready');
      await suspend(kind); await resume(kind);
      await expect(context).toHaveAttribute('data-state', 'ready');
      await expect(context.locator('[data-research-history=claim]:not([data-record-revision])')).toHaveCount(1);
      await expect(context.locator('[data-manuscript-links-paragraph]')).toBeVisible();
      let release, held, completed;
      const waiting = new Promise(resolve => { held = resolve; });
      const finished = new Promise(resolve => { completed = resolve; });
      const routePattern = '**/api/research/manuscript-review?*';
      await page.route(routePattern, async route => {
        const response = await route.fetch(); held();
        await new Promise(resolve => { release = resolve; });
        await route.fulfill({response}); completed();
      });
      await page.evaluate(() => { LixityManuscriptLinks.passage(document.querySelector('#chapters .ptext'), true); });
      await waiting;
      await suspend(kind); await resume(kind);
      await expect(context).toHaveAttribute('data-state', 'stale');
      await expect(context.locator('[data-passage-research-retry]')).toBeVisible();
      await suspend(kind); await resume(kind);
      await expect(context).toHaveAttribute('data-state', 'stale');
      await expect(context.locator('[data-passage-research-retry]')).toBeVisible();
      release(); await finished; await page.unroute(routePattern);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await expect(context.locator('[data-research-history]')).toHaveCount(0);
      await context.locator('[data-passage-research-retry]').click();
      await expect(context).toHaveAttribute('data-state', 'ready');
      await suspend(kind);
      const original = await page.locator('#research-manager').getAttribute('data-research-token');
      await page.locator('#research-manager').evaluate((node, token) => { node.dataset.researchToken = token; }, server.fixture.copied_token);
      await page.locator('#research-manager').evaluate((node, token) => { node.dataset.researchToken = token; }, original);
      await resume(kind);
      await expect(context).toHaveAttribute('data-state', 'stale');
      await suspend(kind); await resume(kind);
      await expect(context).toHaveAttribute('data-state', 'stale');
      await expect(context.locator('[data-passage-research-retry]')).toBeVisible();
      await context.locator('[data-passage-research-retry]').click();
      await expect(context).toHaveAttribute('data-state', 'ready');
    }
    await page.close();
  }
}

async function guardJourneys(browser, server) {
  const page = await browser.newPage({viewport: {width: 1440, height: 950}});
  const writes = [], errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (request.method() === 'POST') writes.push(request.url()); });
  await page.goto(server.fixture.url);
  const paragraphs = page.locator('#chapters .ptext');
  const context = page.locator('[data-passage-research]');
  async function open(index = 0, refresh = false) {
    if (refresh) {
      await page.evaluate(index => { LixityManuscriptLinks.passage(document.querySelectorAll('#chapters .ptext')[index], true); }, index);
      return;
    }
    await paragraphs.nth(index).locator('[data-reader-paragraph]').click();
    await (await savedResearchAction(page)).click();
  }
  await open(2);
  await expect(context).toHaveAttribute('data-state', 'empty');
  await expect(context).toContainText('No associations for this passage.');
  await context.locator('[data-passage-research-close]').focus();
  await page.keyboard.press('Escape');
  await expect(context).toBeHidden();
  await expect(paragraphs.nth(2).locator('[data-reader-paragraph]')).toBeFocused();
  const reviewRoute = '**/api/research/manuscript-review?*';
  await page.route(reviewRoute, route => route.fulfill({status: 500, json: {ok: false, message: 'Synthetic context read failure'}}));
  await open(0, true);
  await expect(context).toHaveAttribute('data-state', 'read-error');
  await expect(context).toContainText('Synthetic context read failure');
  await page.unroute(reviewRoute);
  await context.locator('[data-passage-research-retry]').click();
  await expect(context).toHaveAttribute('data-state', 'ready');
  await page.route(reviewRoute, async route => {
    const response = await route.fetch(), data = await response.json();
    await route.fulfill({response, json: {...data, current_source_sha256: 'changed-on-disk'}});
  });
  await page.evaluate(() => document.getElementById('r-review-refresh').click());
  await expect(context).toHaveAttribute('data-state', 'stale');
  assert.equal(await context.locator('[data-research-history]').count(), 0, 'A refreshed stale source invalidates an already displayed summary');
  await page.unroute(reviewRoute);
  await context.locator('[data-passage-research-retry]').click();
  await expect(context).toHaveAttribute('data-state', 'ready');
  await page.route(reviewRoute, async route => {
    const response = await route.fetch(), data = await response.json();
    data.passage_context.paragraphs[0].groups[0].claims[0].versions[0].pinned.id = server.fixture.other;
    await route.fulfill({response, json: data});
  });
  await open(0, true);
  await expect(context).toHaveAttribute('data-state', 'unavailable');
  assert.equal(await context.locator('[data-research-history]').count(), 0, 'A projection with a foreign claim identity never renders a mixed summary');
  await page.unroute(reviewRoute);
  await context.locator('[data-passage-research-retry]').click();
  await expect(context).toHaveAttribute('data-state', 'ready');
  await page.route(reviewRoute, async route => {
    const response = await route.fetch(), data = await response.json();
    data.passage_context.paragraphs[0].groups[0].claims[0].current.title = {invalid: 'not a title'};
    await route.fulfill({response, json: data});
  });
  await open(0, true);
  await expect(context).toHaveAttribute('data-state', 'unavailable');
  await page.unroute(reviewRoute);
  // Incomplete or internally mixed projections cannot become accepted context.
  for (const fault of ['missing', 'duplicate', 'foreign-dossier', 'wrong-current-revision', 'unavailable']) {
    await page.route(reviewRoute, async route => {
      const response = await route.fetch(), data = await response.json();
      if (fault === 'missing') delete data.passage_context;
      else if (fault === 'duplicate') data.passage_context.paragraphs.push(data.passage_context.paragraphs[0]);
      else if (fault === 'foreign-dossier') data.passage_context.paragraphs[0].groups[0].dossier.pins[0].id = server.fixture.other;
      else if (fault === 'unavailable') Object.assign(data.passage_context.paragraphs[0], {state: 'unavailable', shown: 0, groups: []});
      else data.passage_context.paragraphs[0].groups[0].claims[0].current.revision = 99;
      await route.fulfill({response, json: data});
    });
    await open(0, true);
    await expect(context).toHaveAttribute('data-state', 'unavailable');
    await expect(context.locator('[data-research-history]')).toHaveCount(0);
    await page.unroute(reviewRoute);
  }
  // An exact quote with an unresolved review state never becomes resolved UI.
  await page.route(reviewRoute, async route => {
    const response = await route.fetch(), data = await response.json();
    data.links.forEach((row, i) => { row.anchor_state = ['moved', 'adjusted', 'ambiguous'][i % 3]; });
    data.passage_context.paragraphs = [];
    await route.fulfill({response, json: data});
  });
  await page.evaluate(() => LixityManuscriptLinks.passage(document.querySelector('#chapters .ptext'), true));
  await expect(context).toHaveAttribute('data-state', 'empty');
  assert.equal(await context.locator('[data-research-history]').count(), 0);
  await expect(context.locator('[data-manuscript-links-paragraph]')).toBeVisible();
  await page.unroute(reviewRoute);
  await page.reload();
  // Hold a real accepted response, then change one identity dimension at a time.
  for (const dimension of ['passage', 'source', 'project', 'root', 'closed', 'detached', 'view']) {
    let release, held, completed;
    const finished = new Promise(resolve => { completed = resolve; });
    const waiting = new Promise(resolve => { held = resolve; });
    await page.route(reviewRoute, async route => {
      const response = await route.fetch();
      held(); await new Promise(resolve => { release = resolve; });
      await route.fulfill({response}); completed();
    });
    await open(0, true); await waiting;
    await expect(context).toHaveAttribute('data-state', 'pending');
    const originalToken = await page.locator('#research-manager').getAttribute('data-research-token');
    if (dimension === 'passage') await open(2);
    else if (dimension === 'closed') await context.locator('[data-passage-research-close]').click();
    else if (dimension === 'view') {
      await page.locator('#tab-view-research').click();
      await page.locator('#tab-view-analysis').click();
    }
    else if (dimension === 'detached') await paragraphs.first().evaluate(node => node.remove());
    else await page.evaluate(({dimension, copiedToken}) => {
      const host = dimension === 'source' ? document.body : dimension === 'project' ? document.getElementById('manuscript-pdf-form') : document.getElementById('research-manager');
      const key = dimension === 'source' ? 'manuscriptSourceSha256' : dimension === 'project' ? 'projectToken' : 'researchToken';
      host.dataset[key] = dimension === 'root' ? copiedToken : 'changed-' + dimension;
    }, {dimension, copiedToken: server.fixture.copied_token});
    if (dimension === 'root') {
      await expect(context).toHaveAttribute('data-state', 'stale');
      await page.locator('#research-manager').evaluate((node, token) => { node.dataset.researchToken = token; }, originalToken);
    }
    release(); await finished;
    await page.unroute(reviewRoute);
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await context.locator('[data-research-history]').count(), 0, dimension + ' invalidates a held context result');
    await expect(context).not.toHaveAttribute('data-state', 'pending');
    if (dimension === 'detached') await expect(page.locator('#workbench-return')).toBeHidden();
    await page.reload();
  }
  // Initialization is an explicit separate route, never a side effect of opening.
  await page.route('**/api/research/status?*', route => route.fulfill({json: {ok: true, initialized: false}}));
  await page.reload(); await open();
  await expect(context).toHaveAttribute('data-state', 'uninitialized');
  await expect(context).toContainText('Open Research setup');
  assert.deepEqual(writes, []); assert.deepEqual(errors, []);
  await page.close();
}

(async () => {
  const server = await startNativeServer(source, artifacts);
  const browser = await launchChromium();
  try {
    await sharedDossierJourney(browser);
    await geometryJourneys(browser, server);
    for (const [width, height] of [[1440, 950], [390, 900], [320, 900], [320, 480]]) for (const reducedMotion of ['reduce', 'no-preference']) {
      const page = await browser.newPage({viewport: {width, height}, reducedMotion});
      const writes = [], errors = [], reads = [], dossierReads = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => {
        if (!['GET', 'HEAD'].includes(request.method())) writes.push(request.url());
        if (request.url().includes('/api/research/record?')) reads.push(new URL(request.url()));
        if (request.url().includes('/api/research/dossiers?')) dossierReads.push(new URL(request.url()));
      });
      await page.goto(server.fixture.url);
      const paragraph = page.locator('#chapters .ptext').first();
      const prose = paragraph.locator('.ptext-inner > p');
      const node = await prose.elementHandle();
      const before = await prose.evaluate(el => ({text: el.textContent, hash: el.closest('.ptext').dataset.paragraphSha256}));
      assert.deepEqual(reads, [], 'Record viewers make no reads before an explicit request');
      await page.evaluate(() => {
        document.getElementById('r-claim-title').value = 'Unsubmitted claim draft';
        document.getElementById('r-decision-title').value = 'Unsubmitted decision draft';
      });
      await page.locator('#manuscript-analysis-toggle').click();
      await paragraph.locator('[data-reader-paragraph]').click();
      await page.locator('[data-reader-action="values"]').click();
      await prose.evaluate(node => {
        const range = document.createRange(); range.selectNodeContents(node);
        const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
        selection.setBaseAndExtent(selection.focusNode, selection.focusOffset, selection.anchorNode, selection.anchorOffset);
      });
      await paragraph.locator('[data-reader-paragraph]').click();
      await expect((await savedResearchAction(page))).toBeVisible({timeout: 1500});
      await (await savedResearchAction(page)).focus();
      const originTop = (await paragraph.boundingBox()).y;
      await page.keyboard.press('Enter');
      const context = page.locator('#workspace-context-panel [data-passage-research]');
      await expect(context).toBeVisible();
      if (width > 900) await expect.poll(() => page.locator("#workspace-context-panel .context-tool-tabs").evaluate(node => node.getBoundingClientRect().top)).toBeGreaterThanOrEqual(0);
      if (width <= 900) await expect.poll(() => page.evaluate(() => document.getElementById("workspace-context-panel").getBoundingClientRect().top >= document.getElementById("workbench-thread").getBoundingClientRect().bottom)).toBe(true);
      await expect(context).toContainText('Current claim title');
      await expect(context).toContainText('Current dossier title');
      await expect(context).toContainText('Synthetic associated decision');
      await expect(context).toContainText('Disputed');
      await expect(context.locator('.passage-research-item')).toHaveCount(1);
      const associations = context.locator('[data-passage-research-associations]');
      const decisions = context.locator('[data-passage-research-decisions]');
      assert.equal(await associations.evaluate(node => node.open), false, 'Exact quotes stay behind one disclosure');
      assert.equal(await decisions.evaluate(node => node.open), false, 'Current dossier decisions are optional context');
      await expect(associations.locator('blockquote')).toHaveCount(5);
      await expect(decisions.locator('summary').first()).toHaveText('7 decisions in current dossier');
      await expect(decisions).not.toContainText('Showing 5 of 7');
      assert.equal(await context.locator(`[data-record-id="${server.fixture.other}"]`).count(), 0);
      assert.equal(await context.locator('img').count(), 0);
      await expect(context).toContainText('Showing 5 of 6');
      await expect(page.locator('[data-context-tool="research"]')).toHaveAttribute('aria-pressed', 'true');
      assert.deepEqual(reads, [], 'Passage summaries use the backend projection without per-record composition');
      assert.deepEqual(dossierReads, [], 'Passage summaries do not fetch a dossier body to assemble decisions');
      await decisions.locator('summary').first().click();
      await expect(decisions.locator('[data-research-history=decision]')).toHaveCount(5);
      const more = decisions.locator('details');
      assert.equal(await more.evaluate(node => node.open), false);
      await more.locator('summary').click();
      await expect(more.locator('[data-research-history=decision]').last()).toBeVisible();
      await expect(decisions.locator('[data-research-history=decision]')).toHaveCount(7);
      for (const kind of ['claim', 'dossier', 'decision']) {
        const trigger = context.locator(`[data-research-history="${kind}"]:not([data-record-revision])`).first();
        await trigger.click();
        await expect(page.locator('#research-revision-kind')).toContainText('Version ' + (kind === 'decision' ? 1 : 2));
        await expect(page.locator('#research-revision-history-detail')).toContainText({claim: 'An old authored statement.', dossier: 'A saved author plan.', decision: 'An authored plan, not a fact.'}[kind]);
        await page.keyboard.press('Escape');
        await expect(trigger).toBeFocused();
      }
      for (const kind of ['claim', 'dossier']) {
        const pin = context.locator(`[data-research-history="${kind}"][data-record-revision="1"]`);
        await pin.click();
        await expect(page.locator('#research-revision-kind')).toContainText('Version 1');
        await expect(page.locator('#research-revision-history-detail')).toContainText(kind === 'claim' ? 'Synthetic saved claim <img src=x>' : 'Synthetic pinned dossier');
        await page.keyboard.press('Escape');
        await expect(pin).toBeFocused();
      }
      assert.deepEqual(await prose.evaluate(el => ({text: el.textContent, hash: el.closest('.ptext').dataset.paragraphSha256})), before);
      assert.equal(await prose.evaluate((el, previous) => el === previous, node), true);
      assert.deepEqual(writes, []);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Context fits viewport');
      await page.screenshot({path: path.join(artifacts, `passage-en-${width}x${height}-${reducedMotion}.png`)});
      await context.locator('[data-manuscript-links-paragraph]').click();
      await expect(page.locator('[data-rtab="review"]')).toHaveAttribute('aria-selected', 'true');
      await expect(page.locator('#research-manuscript-review .manuscript-link-review-item')).toHaveCount(6);
      await page.locator('#workbench-return').click();
      await expect(paragraph).toBeFocused();
      await expect.poll(async () => Math.abs((await paragraph.boundingBox()).y - originTop)).toBeLessThan(2);
      assert.equal(await page.evaluate(() => getSelection().toString()), before.text, 'Exact selected text survives research and return');
      assert.deepEqual(await prose.evaluate(node => {
        const selection = getSelection(), range = document.createRange(); range.selectNodeContents(node);
        range.setEnd(selection.anchorNode, selection.anchorOffset); const anchor = range.toString().length;
        range.setEnd(selection.focusNode, selection.focusOffset);
        return {anchor, focus: range.toString().length};
      }), {anchor: before.text.length, focus: 0}, 'Backward selection direction and UTF-16 offsets survive return');
      await expect(page.locator('#reader-inspector')).toBeVisible();
      await expect(page.locator('#manuscript-analysis-toggle')).toHaveAttribute('aria-pressed', 'true');
      assert.equal(await prose.evaluate((el, previous) => el === previous, node), true);
      await expect(page.locator('#r-claim-title')).toHaveValue('Unsubmitted claim draft');
      await expect(page.locator('#r-decision-title')).toHaveValue('Unsubmitted decision draft');
      assert.deepEqual(writes, []);
      assert.deepEqual(errors, []);
      await page.close();
    }
    await suspensionJourneys(browser, server);
    await guardJourneys(browser, server);
    await localeJourneys(browser);
    console.log('PASS native passage research; artifacts ' + artifacts);
  } finally { await browser.close(); await server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
