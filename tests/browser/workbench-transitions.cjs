// Context requests reveal their tool and return to the requesting passage.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-workbench-transitions-'));
const html = pythonFixture(`
import json
from dashboard_fixtures import full_dashboard
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
original = full_dashboard.__globals__['render_dashboard']
full_dashboard.__globals__['SAMPLE'] += '\\n\\n## Context return\\n\\n' + '\\n\\n'.join(
    'Synthetic passage %d. ' % number + 'The quiet garden gives this scene room to continue. ' * 6
    for number in range(40))
def render(*args, **kwargs):
    return original(*args, **{**kwargs,
        'labels': {**get_language_profile('en').labels, **WORKSPACE_LABELS['en']},
        'language_key': 'en', 'enabled_actions': ['analyze', 'research-reader'],
        'manuscript_pdf_token': 'synthetic-project', 'research_context_token': 'synthetic-research',
        'manuscript_source_sha256': 'a' * 64})
full_dashboard.__globals__['render_dashboard'] = render
print(json.dumps(full_dashboard()))
`, {root});
const dossier = {id: 'garden', project_id: 'synthetic-project', title: 'Synthetic garden dossier',
  revision: 1, body: '## Context\n\nA saved synthetic note beside the manuscript.',
  sections: ['Context'], citations: [], tags: [], claims: []};

async function settle(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function documentState(page) {
  return page.locator('#chapters .ptext').evaluateAll(nodes => nodes.map(node => ({
    id: node.id, hash: node.dataset.paragraphSha256, start: node.dataset.start, end: node.dataset.end,
    text: node.querySelector('.ptext-inner > p')?.textContent,
  })));
}

async function createPage(browser, width, reducedMotion = 'reduce') {
  const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion});
  page.setDefaultTimeout(10000);
  const errors = [], writes = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => {if (message.type() === 'error') errors.push(message.text());});
  await page.route('**/*', route => {
    const request = route.request(), url = new URL(request.url());
    if (request.method() !== 'GET') {
      writes.push(url.pathname);
      return route.fulfill({status: 400, json: {ok: false, message: 'Context reading cannot save'}});
    }
    if (url.origin !== 'http://lixity.test') return route.abort();
    if (url.pathname === '/api/research/dossiers') return route.fulfill({json:
      url.searchParams.has('id') ? {ok: true, ...dossier}
        : {ok: true, project_id: dossier.project_id, dossiers: [dossier]}});
    if (url.pathname.startsWith('/api/')) return route.fulfill({json: {
      ok: true, initialized: true, project_id: dossier.project_id, snapshot: 'synthetic-snapshot',
      records: [], sources: [], dossiers: [dossier], claims: [], decisions: [], candidates: [], links: [],
    }});
    return route.fulfill({contentType: 'text/html', body: html});
  });
  await page.goto('http://lixity.test/');
  await page.locator('#tab-view-analysis').click();
  return {page, errors, writes};
}

async function openFromPassage(page, action, waitForLayout = true, passageIndex = 27) {
  const paragraph = page.locator('#chapters .ptext').nth(passageIndex);
  await paragraph.scrollIntoViewIfNeeded();
  await settle(page);
  const origin = {paragraph, id: await paragraph.getAttribute('id'),
    top: await paragraph.evaluate(node => node.getBoundingClientRect().top)};
  assert.ok(await page.evaluate(() => scrollY) > 1500, 'The request starts well down the manuscript');
  await paragraph.locator('.reader-paragraph-actions').click();
  await page.locator(`#manuscript-context-menu [data-reader-action="${action}"]`).click();
  if (waitForLayout) await settle(page);
  return origin;
}

async function assertToolDestination(page, heading, close, width, label) {
  const box = await heading.boundingBox();
  assert.ok(box && box.y >= 0 && box.y + box.height <= 900,
    `${width}: ${label} heading must enter the viewport after a passage request; got ${JSON.stringify(box)}`);
  assert.equal(await close.evaluate(node => document.activeElement === node), true,
    `${width}: ${label} request gives the visible close control keyboard focus`);
}

async function assertPassageReturn(page, origin, width, label, focusTarget) {
  await settle(page);
  const top = await origin.paragraph.evaluate(node => node.getBoundingClientRect().top);
  assert.ok(Math.abs(top - origin.top) <= 2,
    `${width}: ${label} returns to the requesting passage position (${origin.top} -> ${top})`);
  const target = focusTarget || origin.paragraph.locator('.reader-paragraph-actions');
  assert.equal(await target.evaluate(node => document.activeElement === node), true,
    `${width}: ${label} returns keyboard focus to its origin control`);
}

(async () => {
  const browser = await launchChromium();
  try {
    for (const width of [390, 320, 1440]) {
      const {page, errors, writes} = await createPage(browser, width);
      const original = await documentState(page);
      const valuesOrigin = await openFromPassage(page, 'values');
      if (width <= 900) {
        await page.screenshot({path: path.join(artifacts, `${width}-values-open.png`)});
        await assertToolDestination(page, page.locator('#reader-inspector-title'),
          page.locator('#reader-inspector-close'), width, 'Values');
      } else {
        const boxes = await page.evaluate(id => ({
          passage: document.getElementById(id).getBoundingClientRect().toJSON(),
          dock: document.getElementById('workspace-context-panel').getBoundingClientRect().toJSON(),
          scrollY,
        }), valuesOrigin.id);
        assert.ok(boxes.dock.x > boxes.passage.x + boxes.passage.width,
          'Desktop context stays beside the manuscript');
        assert.ok(boxes.scrollY > 1500, 'Desktop context does not jump to the document top');
        assert.ok(Math.abs(boxes.passage.y - valuesOrigin.top) <= 2,
          'Opening desktop context preserves the passage position');
      }
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#workspace-context-panel').isVisible(), false,
        `${width}: Escape closes the requested Values tool`);
      await assertPassageReturn(page, valuesOrigin, width, 'Values Escape');

      const dossierOrigin = await openFromPassage(page, 'companion');
      if (width <= 900) await assertToolDestination(page, page.locator('#workspace-reader-title'),
        page.locator('#workspace-reader-close'), width, 'Dossier');
      await page.waitForFunction(() => !document.getElementById('workspace-reader-dossier').disabled);
      await page.locator('#workspace-reader-dossier').selectOption(dossier.id);
      await page.locator('#workspace-reader-body h3').waitFor();
      assert.match(await page.locator('#workspace-reader-body').textContent(), /A saved synthetic note/);
      await page.locator('#workspace-reader-close').click();
      assert.equal(await page.locator('#workspace-context-panel').isVisible(), false,
        `${width}: The dossier close control closes its context tool`);
      await assertPassageReturn(page, dossierOrigin, width, 'Dossier close',
        width > 900 ? page.locator('#workspace-reader-toggle') : null);

      if (width <= 900) {
        await openFromPassage(page, 'companion');
        // A later passage owns its explicit request even while another tool is open.
        const laterOrigin = await openFromPassage(page, 'values', true, 33);
        await assertToolDestination(page, page.locator('#reader-inspector-title'),
          page.locator('#reader-inspector-close'), width, 'Later passage Values');
        await page.keyboard.press('Escape');
        await assertPassageReturn(page, laterOrigin, width, 'Later passage cross-tool request');
      }

      if (width > 900) {
        // The desktop sidebar remains reachable without scrolling the manuscript.
        const viewTop = await dossierOrigin.paragraph.evaluate(node => node.getBoundingClientRect().top);
        await page.locator('#tab-view-research').click();
        assert.equal(await page.locator('#tab-view-research').getAttribute('aria-selected'), 'true');
        await page.locator('#tab-view-analysis').click();
        await settle(page);
        assert.equal(await page.locator('#tab-view-analysis').getAttribute('aria-selected'), 'true');
        assert.ok(Math.abs(await dossierOrigin.paragraph.evaluate(node => node.getBoundingClientRect().top) - viewTop) <= 2,
          `${width}: Manuscript / Research navigation preserves the passage origin`);
      }
      assert.deepEqual(await documentState(page), original, `${width}: Tools preserve source text and IDs`);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false,
        `${width}: Context transitions do not create horizontal overflow`);
      assert.deepEqual(errors, [], `${width}: Context transitions have no runtime or console errors`);
      assert.deepEqual(writes, [], `${width}: Context transitions never save or retain source data`);
      await page.screenshot({path: path.join(artifacts, `${width}-returned.png`)});
      await page.close();
    }
    for (const width of [1440, 390]) {
      const {page, errors, writes} = await createPage(browser, width, 'no-preference');
      const original = await documentState(page);
      // Keyboard reversal can arrive before the tool's entrance animation finishes.
      const valuesOrigin = await openFromPassage(page, 'values', false);
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#workspace-context-panel').isVisible(), false,
        `${width}: Immediate Escape reverses an opening Values tool`);
      await assertPassageReturn(page, valuesOrigin, width, 'Immediate Values reversal');
      const dossierOrigin = await openFromPassage(page, 'companion', false);
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#workspace-context-panel').isVisible(), false,
        `${width}: Immediate Escape reverses an opening Dossier tool`);
      await assertPassageReturn(page, dossierOrigin, width, 'Immediate Dossier reversal',
        width > 900 ? page.locator('#workspace-reader-toggle') : null);

      const motionOrigin = await openFromPassage(page, 'values', false);
      // Enter activates the focused tab without waiting for an earlier entrance to finish.
      await page.locator('[data-context-tool="dossier"]').press('Enter');
      await page.locator('[data-context-tool="analysis"]').press('Enter');
      await page.locator('[data-context-tool="dossier"]').press('Enter');
      const activeEffects = await page.locator('#workspace-context-panel').evaluate(node => {
        const effects = node.getAnimations({subtree: true}).filter(effect => effect.playState === 'running');
        // Slow active effects only to keep the preference-change check deterministic.
        effects.forEach(effect => effect.updatePlaybackRate(.01));
        return effects.length;
      });
      assert.ok(activeEffects > 0, `${width}: Normal motion gives the newly requested context a visible reveal`);
      await page.emulateMedia({reducedMotion: 'reduce'});
      await page.waitForFunction(() => !document.getElementById('workspace-reader-dossier').disabled);
      await page.locator('#workspace-reader-dossier').selectOption(dossier.id);
      await page.locator('#workspace-reader-body h3').waitFor();
      await settle(page);
      assert.equal(await page.locator('#workspace-context-panel').evaluate(node =>
        node.getAnimations({subtree: true}).filter(effect => ['running', 'paused'].includes(effect.playState)).length),
      0, `${width}: A live reduced-motion preference cancels the active context reveal`);
      assert.equal(await page.locator('[data-context-tool="dossier"]').getAttribute('aria-pressed'), 'true',
        `${width}: Rapid tool reversals retain the final requested Dossier`);
      assert.match(await page.locator('#workspace-reader-body').textContent(), /A saved synthetic note/);
      if (width <= 900) {
        const heading = await page.locator('#workspace-reader-title').boundingBox();
        assert.ok(heading && heading.y >= 0 && heading.y + heading.height <= 900,
          'Rapid mobile tool reversals keep the final context heading in the viewport');
      }
      await page.locator('#workspace-reader-close').click();
      await assertPassageReturn(page, motionOrigin, width, 'Rapid context reversal',
        width > 900 ? page.locator('#workspace-reader-toggle') : null);
      assert.deepEqual(await documentState(page), original, `${width}: Motion never replaces source text or IDs`);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      assert.deepEqual(errors, [], `${width}: Motion and live preferences have no runtime errors`);
      assert.deepEqual(writes, [], `${width}: Rapid transitions never save or retain source data`);
      await page.screenshot({path: path.join(artifacts, `${width}-motion-returned.png`)});
      await page.close();
    }
    console.log(`Workbench context transitions passed at 390/320/1440 pixels with reduced and normal motion; screenshots: ${artifacts}`);
  } finally {await browser.close();}
})().catch(error => {console.error(error); console.error(`Screenshots: ${artifacts}`); process.exitCode = 1;});
