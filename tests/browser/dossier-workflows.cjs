// Contextual forms and selected-section edits use the existing native workflows.
const {launchChromium, modShortcut, playwrightModule} = require('../../scripts/browser_tools.cjs');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {startNativeServer} = require('./support/native-server.cjs');
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
    const box = page.locator('#r-dos-drafts-box');
    await box.locator(':scope > summary').press('Enter');
    const load = box.locator('#r-manuscript-dossier-btn');
    const guidance = box.locator('#r-manuscript-drafts-help');
    const primary = box.locator('.ctl.primary:visible');
    await expect(guidance).toBeVisible();
    await expect(primary).toHaveCount(1);
    await expect(load).toHaveClass(/\bprimary\b/);
    await load.press('Enter');
    const status = box.locator('#r-manuscript-drafts-status');
    await expect(status).toBeVisible();
    await expect(status).toHaveClass(/\bloading\b/);

    // The first project response must arrive before any proposals can render.
    releaseStatus();
    await expect(page.locator('#r-active-root')).toContainText('synthetic-project');
    releaseSuggestions();
    const drafts = page.locator('#r-manuscript-drafts');
    await expect(drafts.locator('[data-draft-select="character:mara"]')).toBeVisible();
    await expect(drafts.locator('[data-draft-select="character:ivo"]')).toBeVisible();
    await expect(status).toBeHidden();
    await expect(primary).toHaveCount(1);
    const save = drafts.locator('[data-create-manuscript-draft]');
    await expect(save).toHaveClass(/\bprimary\b/);
    await expect(save).toHaveAccessibleDescription(
      await drafts.locator('[data-draft-reason-method]').textContent()
    );
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
    if (legacy) {
      await expect(summary.locator('..').locator('..').locator('.research-excerpt')).toHaveText('„Rowan hielt Wache.“');
    }
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
    await expect(table).toBeHidden();
    const count = legacy ? legacyMiddlePassages + 4 : 3;
    await expect(overview).toContainText(new RegExp(`\\b${count}\\b`));
    const chapterCounts = await table.locator('tbody tr').evaluateAll(rows =>
      rows.map(row => Array.from(row.cells, cell => cell.textContent.trim())));
    const expected = [2, 0, legacy ? legacyMiddlePassages + 2 : 1];
    for (const [index, mentions] of expected.entries()) {
      assert.ok(chapterCounts[index].includes(String(mentions)), `Chapter ${index + 1} shows ${mentions} mentions`);
    }

    const passages = analysis.locator('[data-character-passages] [data-character-passage]');
    const passageChapters = analysis.locator('details[data-character-passage-chapter]');
    const more = analysis.locator('[data-character-more]');
    await expect(passages.first()).toBeVisible();
    await expect(passages.first().locator('mark')).toHaveCount(2);
    await expect(passageChapters.first()).toHaveAttribute('open', '');
    if (!legacy) {
      await expect(passageChapters).toHaveCount(2);
      await expect(passages.last()).toBeHidden();
    }
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
    await table.locator('..').locator(':scope > summary').press('Enter');
    await expect(table).toBeVisible();
    await table.scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(artifacts, `character-distribution-${viewport}.png`)});
    if (!(await passages.last().isVisible())) await passageChapters.last().locator(':scope > summary').press('Enter');
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
    await page.locator('#tab-view-research').click();
    if (legacy) await page.setViewportSize({width: 320, height: 900});
    const expectedPassage = legacy ? 'Rowan kept watch. Rowan counted the lamps.' : 'Mara waited for Ivo. Mara took the lantern.';
    const paragraph = page.locator('#chapters .ptext').filter({hasText: expectedPassage});
    const jump = passages.first().locator('[data-character-jump]');
    await expect(jump).toHaveText('Go to manuscript passage');
    await jump.press('Enter');
    await expect(paragraph).toBeFocused();
    assert.equal(await page.evaluate(() => LixityWorkbench.state().analysisVisible), false);
    await expect.poll(() => paragraph.evaluate(node => {
      const rect = node.getBoundingClientRect();
      return rect.top >= readingViewportTop() - 1 && rect.top < innerHeight;
    })).toBe(true);
    if (!legacy) {
      // Revalidate at activation, including when the previously offered target was replaced.
      await page.locator('#tab-view-research').click();
      const identity = await paragraph.getAttribute('data-paragraph-sha256');
      await paragraph.evaluate(node => { node.dataset.paragraphSha256 = '0'.repeat(64); });
      await jump.press('Enter');
      const status = analysis.locator('[data-character-status]');
      await expect(status).toHaveText('This passage is unavailable in the manuscript reader.');
      await expect(jump).toBeDisabled();
      await expect(page.locator('#tab-view-research')).toHaveAttribute('aria-selected', 'true');
      await paragraph.evaluate((node, hash) => { node.dataset.paragraphSha256 = hash; }, identity);

      const source = path.join(artifacts, 'synthetic-project', 'manuscript.md');
      const original = fs.readFileSync(source, 'utf8');
      try {
        fs.writeFileSync(source, original.replace(expectedPassage, expectedPassage + ' The wind shifted.'));
        await filter.selectOption('3');
        const reload = analysis.locator('[data-character-reload]');
        await expect(reload).toBeVisible();
        await reload.press('Enter');
        await expect(passages.first()).toContainText('Mara took the lantern. The wind shifted.');
        await expect(analysis.locator('[data-character-jump]')).toHaveCount(0);
        await expect(status).toContainText('The reader shows a different manuscript version.');
      } finally {
        fs.writeFileSync(source, original);
      }
    }
    assert.deepEqual(await (await page.request.get(recordUrl)).json(), before,
      'Reading character analysis preserves the authored text and exact archive revision');
    assert.ok(requestMethods.every(method => method === 'GET'), 'Opening existing character dossiers performs reads');
    assert.deepEqual(errors, []);
  } finally {
    await page.close();
  }
}

async function checkSceneAndLocationDrafts(page, fixture, draftWrites) {
  const labels = require(path.join(root, 'src/lixity/locales/en.json'));
  const loadButton = page.locator('#r-manuscript-dossier-btn');
  const catalogue = page.locator('#r-manuscript-drafts');
  const preview = catalogue.locator('#r-manuscript-draft-preview');
  const body = preview.locator('[data-draft-preview-body] .research-dossier-body-rendered');
  const reason = preview.locator('[data-draft-reason]');
  const choose = id => catalogue.locator(`[data-draft-select="${id}"]`);
  const create = id => preview.locator(`[data-create-manuscript-draft="${id}"]`);
  const kind = name => catalogue.locator(`[data-draft-kind="${name}"]`);
  const listRecords = async () => (await page.request.get(fixture.url + '/api/research/dossiers')).json();
  let drafts = [];

  async function reload(button = loadButton) {
    const received = page.waitForResponse(response => new URL(response.url()).pathname === '/api/research/manuscript-dossier-drafts');
    await button.press('Enter');
    drafts = (await (await received).json()).drafts;
    await expect(loadButton).toBeEnabled();
    await expect(preview).toBeVisible();
  }

  async function select(category, id) {
    await kind(category).press('Enter');
    await expect(kind(category)).toBeFocused();
    await choose(id).press('Space');
    await expect(choose(id)).toBeFocused();
    await expect(choose(id)).toHaveAttribute('aria-pressed', 'true');
    await expect(body).toBeVisible();
  }

  async function save(id, expectedStatus = 200) {
    const submitted = page.waitForResponse(response => new URL(response.url()).pathname === '/api/research-dossier-from-manuscript');
    const reviewed = drafts.find(draft => draft.id === id);
    assert.match(reviewed.preview_sha256, /^[a-f0-9]{64}$/);
    await create(id).press('Enter');
    const response = await submitted;
    assert.equal(response.status(), expectedStatus);
    assert.deepEqual([draftWrites.at(-1).draft_id, draftWrites.at(-1).preview_sha256], [id, reviewed.preview_sha256]);
    const result = await response.json();
    if (response.ok()) {
      const recordUrl = `${fixture.url}/api/research/record?kind=dossier&id=${result.dossier_id}`;
      const {record} = await (await page.request.get(recordUrl)).json();
      assert.equal(record.body, reviewed.body.trim(), 'Saving persists the reviewed dossier text');
      assert.ok(record.tags.some(tag => /^manuscript-draft:[a-f0-9]{32}$/.test(tag)),
        'The archive retains the generated origin even though it is hidden from author tag controls');
    }
    return result;
  }

  const firstScene = 'scene:1:1', otherScene = 'scene:2:1', register = 'scenes:manuscript';
  const initialRecords = await listRecords();
  await reload();
  await select('scene', register);
  await expect(reason.locator('p')).toHaveText(labels.research_dossier_draft_reason_scene_register);
  const registerGroup = catalogue.locator('[data-draft-group="scene-register"]');
  const individualGroup = catalogue.locator('[data-draft-group="scene-individual"]');
  await expect(registerGroup.locator(`[data-draft-select="${register}"]`)).toBeVisible();
  await expect(registerGroup.getByRole('heading', {name: labels.research_dossier_draft_scene_register, exact: true})).toBeVisible();
  await expect(individualGroup.getByRole('heading', {name: labels.research_dossier_draft_scene_individual, exact: true})).toBeVisible();
  await expect(individualGroup.locator(`[data-draft-select="${firstScene}"]`)).toBeVisible();
  await expect(individualGroup.locator(`[data-draft-select="${otherScene}"]`)).toBeVisible();
  await expect(choose('scene:3:2')).toContainText(`${labels.research_dossier_draft_scene_unit} 2`);
  const registerEntries = body.locator('li');
  await expect(registerEntries).toHaveCount(4);
  await expect(registerEntries).toContainText([
    'The quiet morning under the lantern and past the old tide gate', 'The ledger under the lantern',
    'The runner on the quay', 'The hill beyond the river'
  ]);
  await preview.scrollIntoViewIfNeeded();
  await page.screenshot({path: path.join(artifacts, 'scene-register-desktop.png')});
  await catalogue.evaluate(host => {
    const records = [];
    const observer = new MutationObserver(changes => records.push(...changes));
    host._choiceObservation = {records, observer, buttons:[...host.querySelectorAll('[data-draft-select]')],
      preview:host.querySelector('#r-manuscript-draft-preview')};
    observer.observe(host, {childList:true, subtree:true, attributes:true, attributeFilter:['aria-pressed']});
  });
  function choiceChanges(finished = false) {
    return catalogue.evaluate((host, finished) => {
      const {records, observer, buttons, preview} = host._choiceObservation;
      const changes = records.splice(0).concat(observer.takeRecords());
      const current = [...host.querySelectorAll('[data-draft-select]')];
      if (finished) { observer.disconnect(); delete host._choiceObservation; }
      return {sameButtons:current.length === buttons.length && current.every((button, index) => button === buttons[index]),
        samePreview:preview === host.querySelector('#r-manuscript-draft-preview'),
        replacements:changes.filter(change => change.type === 'childList').map(change => ({
          removed:[...change.removedNodes].map(node => node.id), added:[...change.addedNodes].map(node => node.id),
        })), pressed:changes.filter(change => change.type === 'attributes').map(change => change.target.dataset.draftSelect)};
    }, finished);
  }
  await select('scene', register);
  assert.deepEqual(await choiceChanges(), {sameButtons:true, samePreview:true, replacements:[], pressed:[]});
  await select('scene', firstScene);
  assert.deepEqual(await choiceChanges(true), {sameButtons:true, samePreview:false, replacements:[{
    removed:['r-manuscript-draft-preview'], added:['r-manuscript-draft-preview'],
  }], pressed:[register, firstScene]});
  await expect(choose(register)).toHaveAttribute('aria-pressed', 'false');
  await expect(reason.locator('p')).toHaveText(labels.research_dossier_draft_reason_scene_chapter);
  await expect(preview.getByRole('heading', {name: /The quiet morning under the lantern and past the old tide gate/})).toHaveCount(1);
  await expect(body).not.toContainText('The quiet morning under the lantern and past the old tide gate');
  await expect(body).toContainText('Mara waited for Ivo.');
  await expect(body).toContainText('The tide moved back.');
  await expect(body).not.toContainText('The hill beyond the river');
  await expect(preview.getByText(labels.research_dossier_draft_scene_chapter_fallback, {exact: true})).toHaveCount(1);
  assert.deepEqual(await listRecords(), initialRecords, 'Opening complete previews leaves the archive unchanged');
  const savedScene = await save(firstScene);
  await expect(choose(firstScene)).toHaveCount(0);
  await expect(catalogue.locator('[data-draft-select][aria-pressed="true"]')).toBeFocused();
  const savedAction = catalogue.locator('[data-draft-open-saved]');
  await expect(savedAction).toBeVisible();
  await savedAction.press('Enter');
  const recordDialog = page.locator('#modal-research-revision');
  await expect(recordDialog).toBeVisible();
  await expect(recordDialog).toContainText(savedScene.title);
  await page.keyboard.press('Escape');

  await reload();
  await select('scene', register);
  await expect(choose(otherScene)).toBeVisible();
  const savedRegister = await save(register);
  await expect(choose(register)).toHaveCount(0);
  assert.notEqual(savedScene.dossier_id, savedRegister.dossier_id);
  await reload();
  await select('scene', otherScene);
  await expect(choose(register)).toHaveCount(0);
  await expect(preview.getByRole('heading', {name: /The ledger under the lantern/})).toHaveCount(1);

  const greyhaven = 'location:greyhaven';
  await select('location', greyhaven);
  const location = drafts.find(draft => draft.id === greyhaven);
  assert.equal(location.evidence_hints.basis, 'inferred');
  await expect(reason.getByRole('heading')).toHaveText(labels.research_dossier_draft_reason);
  await expect(reason.locator('[data-draft-reason-method]')).toHaveText(labels.research_dossier_draft_reason_location_inferred
    .replace('{cues}', String(location.evidence_hints.qualifying_mentions)));
  const qualifyingPassage = reason.locator('[data-draft-reason-passage]');
  await expect(qualifyingPassage).toContainText(labels.research_dossier_draft_reason_location_passage);
  await expect(qualifyingPassage.locator('blockquote')).toHaveText(location.evidence_hints.reason_hit.quote);
  assert.ok(location.evidence_hints.reason_hit.quote.includes('went to Greyhaven'));
  assert.equal(location.evidence_hints.mentions, 3);
  assert.deepEqual(location.evidence_hints.chapters, [2, 3]);
  assert.equal(location.evidence_hints.first_hit.chapter, 2);
  await expect(preview.getByText(labels.research_dossier_draft_location_inferred, {exact: true})).toHaveCount(1);
  await expect(body).toContainText('A courier slept in Greyhaven until the bell rang.');
  await expect(body).not.toContainText('A forged note from Greyhaven');
  await preview.scrollIntoViewIfNeeded();
  await page.screenshot({path: path.join(artifacts, 'location-draft-desktop.png')});
  assert.ok(!drafts.some(draft => draft.id === 'location:eile'));
  const savedLocation = await save(greyhaven);
  assert.ok((await listRecords()).dossiers.some(dossier => dossier.id === savedLocation.dossier_id));

  const project = path.join(artifacts, 'synthetic-project');
  const manuscript = path.join(project, 'manuscript.md');
  const original = fs.readFileSync(manuscript, 'utf8');
  const directionalQuote = 'We set out toward Northbank before dawn.';
  const lastQuote = 'We went to Southbank before dusk.';
  try {
    fs.writeFileSync(manuscript, `${original}\n\nA lantern glowed in Northbank.\n\n${directionalQuote}\n\n` +
      `A depot stood near Northbank.\n\nThey waited in Southbank.\n\n${lastQuote}\n`);
    await reload();
    await select('location', 'location:northbank');
    await expect(reason.locator('[data-draft-reason-passage] blockquote')).toHaveText(directionalQuote);
    await expect(body).not.toContainText(directionalQuote);
    await select('location', 'location:southbank');
    await expect(reason.locator('[data-draft-reason-passage] blockquote')).toHaveCount(0);
    await expect(preview.locator('blockquote').filter({hasText: lastQuote})).toHaveCount(1);
  } finally {
    fs.writeFileSync(manuscript, original);
  }
  await reload();
  await select('scene', otherScene);
  const acceptedDigest = drafts.find(draft => draft.id === otherScene).preview_sha256;
  const beforeDrift = await listRecords();
  try {
    fs.writeFileSync(manuscript, original.replace('The storehouse stood empty.', 'The storehouse stood empty. A newly lit lantern glimmered.'));
    await save(otherScene, 409);
    const stale = catalogue.locator('[data-draft-stale]');
    const reloadStale = stale.locator('[data-draft-reload]');
    await expect(stale).toBeVisible();
    await expect(stale.getByRole('alert')).toHaveText(labels.research_dossier_draft_stale);
    await expect(create(otherScene)).toBeDisabled();
    await expect(reloadStale).toBeFocused();
    await page.setViewportSize({width: 320, height: 900});
    await stale.scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(artifacts, 'draft-stale-mobile.png')});
    assert.deepEqual(await listRecords(), beforeDrift, 'A stale preview cannot create a record');
    const rejectedAttempts = draftWrites.length;
    await reload(reloadStale);
    await expect(choose(otherScene)).toHaveAttribute('aria-pressed', 'true');
    await expect(choose(otherScene)).toBeFocused();
    await expect(stale).toBeHidden();
    await expect(create(otherScene)).toBeEnabled();
    assert.notEqual(drafts.find(draft => draft.id === otherScene).preview_sha256, acceptedDigest);
    assert.equal(draftWrites.length, rejectedAttempts, 'Reloading a stale preview does not confirm the save');
    await save(otherScene);
    assert.ok((await listRecords()).dossiers.length > beforeDrift.dossiers.length);
  } finally {
    fs.writeFileSync(manuscript, original);
  }

  const settings = path.join(project, 'lixity.toml');
  await kind('location').press('Enter');
  await catalogue.locator('[data-draft-location-settings]').press('Enter');
  const mode = page.locator('#set-location-mode');
  await expect(mode).toBeFocused();
  await expect(mode).toHaveValue('auto');
  await mode.selectOption('names');
  await page.locator('#set-location-names').fill('Greyhaven\nSilverbank');
  const applied = page.waitForResponse(response => response.url().endsWith('/api/settings'));
  const settingsReload = page.waitForEvent('domcontentloaded');
  await page.locator('#settings-form [type=submit]').click();
  assert.equal((await applied).status(), 200);
  await settingsReload;
  assert.match(fs.readFileSync(settings, 'utf8'), /locations = \["Greyhaven", "Silverbank"\]/);
  await page.locator('#tab-view-research').click();
  const draftsBox = page.locator('#r-dos-drafts-box');
  if (await draftsBox.getAttribute('open') === null) await draftsBox.locator(':scope > summary').click();
  await reload();
  const silverbank = 'location:silverbank';
  await select('location', silverbank);
  const explicit = drafts.find(draft => draft.id === silverbank);
  assert.equal(explicit.evidence_hints.basis, 'configured');
  assert.equal(explicit.evidence_hints.mentions, 2);
  await expect(body).toContainText('Lanterns glowed in Silverbank after dusk.');
  await expect(preview.getByText(labels.research_dossier_draft_location_configured, {exact: true})).toHaveCount(1);
  await expect(page.locator('#r-filter-dossiers-tags')).not.toContainText(/manuscript-draft:[a-f0-9]{32}/);
  await preview.evaluate(node => node.scrollIntoView({block: 'start', behavior: 'instant'}));
  await expect.poll(() => create(silverbank).evaluate(node => {
    const rect = node.getBoundingClientRect();
    return rect.top >= 0 && rect.bottom <= innerHeight &&
      node.contains(document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2));
  }), {message: 'Sticky research controls leave the proposal save action reachable at 320px'}).toBe(true);
  await page.screenshot({path: path.join(artifacts, 'location-draft-mobile.png')});

  const validSettings = fs.readFileSync(settings, 'utf8');
  const newCharacter = 'character:linette';
  const preferences = page.locator('#settings-dossier-drafts');
  try {
    await kind('character').press('Enter');
    await catalogue.locator('[data-draft-report-settings]').press('Enter');
    await expect(preferences.locator(':scope > summary')).toBeFocused();
    await preferences.locator('[data-dossier-drafts-field="character_context_sentences"]').fill('0');
    await preferences.locator('[data-dossier-drafts-field="inferred_location_limit"]').fill('1');
    await preferences.locator('[data-dossier-drafts-field="character_report_passages"]').uncheck();
    assert.ok(await preferences.evaluate(node => node.scrollWidth <= node.clientWidth));
    const savedPreferences = page.waitForResponse(response => response.url().endsWith('/api/settings'));
    const reloadedPreferences = page.waitForEvent('domcontentloaded');
    await page.locator('#settings-form [type=submit]').click();
    assert.equal((await savedPreferences).status(), 200);
    await reloadedPreferences;
    const editedSettings = fs.readFileSync(settings, 'utf8');
    assert.match(editedSettings, /\[dossier_drafts\]/);
    assert.match(editedSettings, /"character_context_sentences" = 0/);
    assert.match(editedSettings, /"inferred_location_limit" = 1/);
    assert.match(editedSettings, /"character_report_passages" = false/);
    fs.writeFileSync(settings, editedSettings + '\n[characters.Linette]\n');
    fs.writeFileSync(manuscript, original + '\n\nLinette waited at the depot.\n');
    await page.locator('#tab-view-research').click();
    if (await draftsBox.getAttribute('open') === null) await draftsBox.locator(':scope > summary').click();
    await reload();
    await select('character', newCharacter);
    const compact = drafts.find(draft => draft.id === newCharacter);
    assert.equal(compact.evidence_hints.includes_passages, false);
    await expect(reason.locator('blockquote')).toHaveText(compact.evidence_hints.first_hit.quote);
    await expect(body.locator('blockquote')).toHaveCount(0);
  } finally {
    fs.writeFileSync(settings, validSettings);
    fs.writeFileSync(manuscript, original);
  }

  const beforeInvalidSettings = await listRecords();
  try {
    for (const [unavailableKind, validKind, availableId, invalidSettings] of [
      ['scene', 'location', silverbank, validSettings + '"invalid" = "Not a scene number"\n'],
      ['location', 'scene', 'scene:3:2', validSettings.replace(/^locations = .*$/m, 'locations = 42')],
    ]) {
      fs.writeFileSync(settings, invalidSettings);
      await reload();
      const notice = catalogue.locator('[data-draft-unavailable]');
      await expect(notice).toHaveCount(1);
      await expect(notice).toHaveText(labels[`research_dossier_draft_${unavailableKind}_unavailable`]);
      await kind(unavailableKind).press('Enter');
      await expect(kind(unavailableKind)).toBeFocused();
      await expect(preview).toHaveCount(0);
      await select(validKind, availableId);
      await expect(notice).toHaveCount(1);
    }
    assert.deepEqual(await listRecords(), beforeInvalidSettings, 'Browsing partial catalogue results does not write');
  } finally {
    fs.writeFileSync(settings, validSettings);
  }
}

async function checkExistingCharacterDraft(browser, fixture) {
  const page = await browser.newPage({viewport: {width: 1440, height: 900}});
  const labels = require(path.join(root, 'src/lixity/locales/en.json'));
  const draftsBox = page.locator('#r-dos-drafts-box');
  const catalogue = draftsBox.locator('#r-manuscript-drafts');
  const preview = catalogue.locator('#r-manuscript-draft-preview');
  const existing = draftsBox.locator('[data-draft-load-existing]');
  const stage = preview.locator('[data-draft-stage-existing]');
  const dialog = page.locator('#modal-research-revision');
  const body = dialog.locator('#research-revision-field-body');
  const stagePreview = dialog.locator('#research-revision-stage-proposal');
  const stageEdit = dialog.locator('#research-revision-stage-edit');
  const save = dialog.locator('#research-revision-save');
  const discard = dialog.locator('#research-revision-discard');
  const directSelector = `[data-update-character-dossier][data-record-id="${fixture.legacy}"]`;
  const recordUrl = `${fixture.url}/api/research/record?kind=dossier&id=${fixture.legacy}`;
  const record = async () => (await page.request.get(recordUrl)).json();
  const listUrl = fixture.url + '/api/research/dossiers';
  const countDossiers = async () => (await (await page.request.get(listUrl)).json()).dossiers.length;
  const writeAttempts = [], errors = [];
  let catalogueReads = 0;
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (path === '/api/research/manuscript-dossier-drafts') catalogueReads++;
    if (request.method() === 'POST' && /^\/api\/(research-dossier(?:-from-manuscript)?|research-record-revise)$/.test(path)) {
      writeAttempts.push({path, body: request.postDataJSON()});
    }
  });

  async function readSuggestions(trigger, includeExisting) {
    const request = page.waitForResponse(response => {
      const url = new URL(response.url());
      return url.pathname === '/api/research/manuscript-dossier-drafts' &&
        (url.searchParams.get('include_existing') === '1') === includeExisting;
    });
    await trigger.press('Enter');
    const {drafts} = await (await request).json();
    return drafts;
  }

  async function selectCharacter(id) {
    const option = catalogue.locator(`[data-draft-select="${id}"]`);
    await option.press('Space');
    await expect(option).toBeFocused();
    await expect(option).toHaveAttribute('aria-pressed', 'true');
  }

  const rowan = 'character:rowan';
  const loadButton = draftsBox.locator('#r-manuscript-dossier-btn');
  const stale = catalogue.locator('[data-draft-stale]');
  const reloadExisting = stale.locator('[data-draft-reload]');
  try {
    const original = await record();
    const countBefore = await countDossiers();
    assert.equal(original.record.revision, 1);
    await page.goto(fixture.url);
    await page.locator('#tab-view-research').click();
    const composer = page.locator('#r-dos-composer');
    await composer.locator(':scope > summary').press('Enter');
    const manualTitle = page.locator('#r-dos-title');
    const manualBody = page.locator('#r-dos-body');
    await manualTitle.fill('A separate unsaved dossier');
    await manualBody.fill('Keep this independent draft without a write.');

    const legacySummary = page.locator(`#research-dossiers-list [data-research-detail=dossier][data-record-id="${fixture.legacy}"]`);
    await legacySummary.click();
    const details = legacySummary.locator('..');
    const direct = details.locator(directSelector);
    await expect(direct).toHaveText(labels.research_dossier_draft_stage_existing);
    const proposals = url => url.pathname === '/api/research/dossier-character' && url.searchParams.get('format') === 'markdown';
    await page.route(proposals, route => route.fulfill({status: 404, json: {ok: false, code: 'character-dossier-empty'}}));
    await direct.press('Enter');
    await expect(details.locator('[data-character-update-status]')).toHaveText(labels.research_dossier_draft_unavailable);
    await expect(direct).toBeEnabled();
    await expect(dialog).toBeHidden();
    await page.unroute(proposals);
    await direct.press('Enter');
    await expect(dialog.locator('#research-revision-title')).toHaveText(labels.research_dossier_draft_revision_title);
    await expect(stagePreview).toContainText('Rowan kept watch. Rowan counted the lamps.');
    await expect(stagePreview).toContainText(labels.research_dossier_character_distribution);
    await expect(stagePreview).toContainText(labels.research_dossier_character_passages);
    await expect(stagePreview.locator('table tbody tr')).toHaveCount(2);
    await expect(stagePreview.locator('table tbody tr td:first-child')).toHaveText(['1', '3']);
    await expect(stagePreview.locator('blockquote').first().locator('strong')).not.toContainText('Rowan');
    await expect(stagePreview.locator('blockquote').filter({hasText: 'Rowan kept watch.'}).locator('strong'))
      .toHaveText(['Rowan', 'Rowan']);
    await expect(stagePreview).toContainText('The mast creaked. A cart stopped nearby.');
    await expect(stagePreview).toContainText('The bell fell quiet. The tide moved back.');
    await expect(stagePreview).toContainText(`Rowan recorded the tally ${legacyMiddlePassages} in the notebook.`);
    await expect(stagePreview).toContainText('The red paper lantern finally disappeared.');
    await expect(stagePreview).not.toContainText('The far scene opened beneath a hill.');
    await expect(stageEdit).toBeFocused();
    await expect(body).toBeHidden();
    await expect(discard).toHaveText(labels.research_dossier_draft_revision_discard);
    await discard.press('Enter');
    await expect(dialog).toBeHidden();
    await expect(direct).toBeFocused();

    await page.locator(`[data-research-history=dossier][data-record-id="${fixture.legacy}"]`).click();
    await expect(dialog.locator(directSelector)).toBeVisible();
    await dialog.locator(directSelector).press('Enter');
    await expect(dialog.locator('#research-revision-title')).toHaveText(labels.research_dossier_draft_revision_title);
    await expect(stagePreview).toContainText('Rowan kept watch. Rowan counted the lamps.');
    await expect(stageEdit).toHaveText(labels.research_dossier_draft_revision_edit);
    await stageEdit.press('Enter');
    await expect(stagePreview).toBeHidden();
    await expect(body).toBeFocused();
    const editableText = await body.inputValue();
    assert.ok(editableText.startsWith(original.record.body));
    assert.ok(editableText.includes('**Rowan** kept watch. **Rowan** counted the lamps.'));
    assert.ok(editableText.includes('The red paper lantern finally disappeared.'));
    assert.equal(await body.evaluate(field => field.selectionStart), original.record.body.length);
    await discard.press('Enter');
    await expect(dialog).toBeHidden();
    assert.deepEqual(await record(), original, 'Direct entry points let the author discard a draft before saving');
    assert.deepEqual(writeAttempts, []);

    await draftsBox.locator(':scope > summary').press('Enter');
    await expect(loadButton).toHaveText(labels.research_dossier_draft_load);
    await expect(existing).toHaveText(labels.research_dossier_draft_load_existing);
    await expect(loadButton).toHaveAttribute('aria-pressed', 'false');
    await expect(existing).toHaveAttribute('aria-pressed', 'false');
    await expect(catalogue).toBeEmpty();
    const defaults = await readSuggestions(loadButton, false);
    assert.ok(!defaults.some(draft => draft.id === rowan), 'New suggestions exclude the known character dossier');
    await expect(catalogue.locator(`[data-draft-select="${rowan}"]`)).toHaveCount(0);
    await expect(loadButton).toHaveAttribute('aria-pressed', 'true');
    await catalogue.locator('[data-draft-kind="scene"]').press('Enter');
    await catalogue.locator('[data-draft-select="scene:1:1"]').press('Enter');
    await expect(preview.locator('[data-create-manuscript-draft="scene:1:1"]')).toBeEnabled();
    await expect(existing).toBeVisible();
    const inclusive = await readSuggestions(existing, true);
    await expect(existing).toHaveAttribute('aria-pressed', 'true');
    const first = inclusive.find(draft => draft.id === rowan);
    assert.equal(first.already_covered, true);
    assert.deepEqual([first.existing_dossier.id, first.existing_dossier.revision], [fixture.legacy, 1]);
    for (const id of ['character:nightjar', 'character:linden']) {
      const other = inclusive.find(draft => draft.id === id);
      assert.equal(other.already_covered, true);
      assert.equal(other.existing_dossier, undefined);
      await expect(catalogue.locator(`[data-draft-select="${id}"]`)).toHaveCount(0);
    }
    await selectCharacter(rowan);
    await expect(preview.locator('[data-create-manuscript-draft]')).toHaveCount(0);
    await expect(preview.locator('[data-draft-preview-body]')).toHaveCount(0);
    await expect(catalogue.locator('[data-draft-select^="scene:"]')).toHaveCount(0);
    await page.setViewportSize({width: 320, height: 640});
    await preview.locator('h5').evaluate(node => node.scrollIntoView({block: 'center', behavior: 'instant'}));
    await expect.poll(() => stage.evaluate(node => {
      const rect = node.getBoundingClientRect();
      return rect.top >= 0 && rect.bottom <= innerHeight &&
        node.contains(document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2));
    }), {message: 'The primary action is reachable in the short catalogue entry at 320px'}).toBe(true);
    await page.screenshot({path: path.join(artifacts, 'existing-figure-preview-mobile.png')});
    await page.setViewportSize({width: 1440, height: 900});
    await preview.locator('h5').scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(artifacts, 'existing-figure-preview-desktop.png')});

    const authoredTitle = 'Rowan with an authored note';
    const authoredBody = original.record.body + '\n\n## Writer’s private working note\n\nKeep the hand-drawn compass.';
    const authoredTags = [...original.record.tags, 'compass-note'];
    const corrected = await page.request.post(fixture.url + '/api/research-record-revise', {data: {
      kind: 'dossier', id: fixture.legacy, expected_snapshot: original.snapshot,
      expected_revision: original.record.revision, changes: {title: authoredTitle, body: authoredBody, tags: authoredTags},
      change_kind: 'correction', reason: 'Synthetic author correction before regeneration'
    }});
    assert.ok(corrected.ok());
    const second = await record();
    assert.equal(second.record.revision, 2);

    await stage.press('Enter');
    await expect(stale).toBeVisible();
    await expect(reloadExisting).toBeFocused();
    await expect(reloadExisting).toHaveText(labels.research_dossier_draft_reload);
    await expect(stage).toBeDisabled();
    await expect(dialog).toBeHidden();
    assert.deepEqual(await record(), second, 'A stale archived revision cannot stage a generated replacement');
    assert.deepEqual(writeAttempts, []);

    const refreshed = await readSuggestions(reloadExisting, true);
    const reviewed = refreshed.find(draft => draft.id === rowan);
    assert.deepEqual([reviewed.existing_dossier.id, reviewed.existing_dossier.revision], [fixture.legacy, 2]);
    await expect(preview).toContainText(authoredTitle);
    await selectCharacter(rowan);
    const manuscript = path.join(artifacts, 'synthetic-project', 'manuscript.md');
    const source = fs.readFileSync(manuscript, 'utf8');
    const catalogueReadsBeforeStage = catalogueReads;
    const latestParagraph = 'Rowan returned quietly to the landing.';
    try {
      fs.writeFileSync(manuscript, source + '\n\n' + latestParagraph + '\n');
      await stage.press('Enter');
      await expect(stagePreview).toContainText(latestParagraph);
      await expect(stale).toHaveCount(0);
      await discard.press('Enter');
      await expect(dialog).toBeHidden();
      assert.deepEqual(await record(), second, 'Reviewing fresh manuscript evidence does not save it');
      assert.equal(catalogueReads, catalogueReadsBeforeStage, 'Preparing an exact dossier reads no duplicate catalogue');
      assert.deepEqual(writeAttempts, []);
    } finally {
      fs.writeFileSync(manuscript, source);
    }
    await stage.press('Enter');
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('#research-revision-title')).toHaveText(labels.research_dossier_draft_revision_title);
    await expect(dialog.locator('#research-revision-kind')).toContainText(authoredTitle);
    await expect(dialog.locator('#research-revision-stage-help')).toHaveText(labels.research_dossier_draft_revision_help);
    await expect(dialog.locator('#research-revision-field-title')).toBeHidden();
    await expect(dialog.locator('#research-revision-batch-add')).toBeHidden();
    await expect(dialog.locator('#research-revision-reason')).toBeHidden();
    await expect(save).toHaveText(labels.research_dossier_draft_revision_save);
    await expect(save).toBeEnabled();
    await expect(stageEdit).toBeFocused();
    await expect(stagePreview).toContainText('Rowan kept watch. Rowan counted the lamps.');
    await expect(stagePreview).not.toContainText(latestParagraph);
    await expect(stagePreview).not.toContainText('Keep the hand-drawn compass.');
    await expect(body).toBeHidden();
    await expect(manualTitle).toHaveValue('A separate unsaved dossier');
    await expect(manualBody).toHaveValue('Keep this independent draft without a write.');
    await page.setViewportSize({width: 320, height: 640});
    assert.ok(await dialog.evaluate(node => node.scrollWidth <= node.clientWidth), 'The staged revision fits at 320px');
    await expect(dialog.locator('#research-revision-stage-help')).toBeInViewport();
    await expect(stagePreview).toBeInViewport();
    await expect(save).toBeInViewport();
    await page.screenshot({path: path.join(artifacts, 'existing-figure-staged-mobile.png')});
    assert.deepEqual(await record(), second, 'Staging a proposal leaves the current accepted revision untouched');
    assert.equal(await countDossiers(), countBefore);
    assert.deepEqual(writeAttempts, []);

    const refusedMessage = 'Synthetic retryable save failure';
    await page.route('**/api/research-record-revise', route =>
      route.fulfill({status: 400, json: {ok: false, message: refusedMessage}}), {times: 1});
    await save.press('Enter');
    const saveStatus = dialog.locator('#research-revision-status');
    await expect(saveStatus).toContainText(refusedMessage);
    await expect(saveStatus).toBeInViewport();
    await expect(save).toBeInViewport();
    await expect(stagePreview).toContainText('Rowan kept watch. Rowan counted the lamps.');
    await expect(body).toBeHidden();
    assert.deepEqual(await record(), second);
    await save.press('Enter');
    await expect(dialog).toBeHidden();
    const saved = await record();
    assert.equal(saved.record.revision, 3);
    assert.equal(saved.record.id, fixture.legacy);
    assert.equal(saved.record.title, authoredTitle);
    assert.ok(saved.record.body.startsWith(authoredBody));
    assert.ok(saved.record.body.includes('**Rowan** kept watch. **Rowan** counted the lamps.'));
    assert.ok(saved.record.body.includes(labels.research_dossier_character_distribution));
    assert.ok(saved.record.body.includes('The mast creaked. A cart stopped nearby.'));
    assert.ok(saved.record.body.includes('The red paper lantern finally disappeared.'));
    assert.equal(saved.record.body, writeAttempts.at(-1).body.changes.body);
    assert.deepEqual(saved.record.tags, second.record.tags);
    assert.deepEqual(saved.record.citations, second.record.citations);
    assert.equal(saved.record.change.change_kind, 'supersession');
    assert.equal(saved.record.change.reason, labels.research_dossier_draft_revision_reason);
    assert.equal(await countDossiers(), countBefore);
    assert.equal(writeAttempts.length, 2);
    assert.deepEqual(writeAttempts[1], writeAttempts[0], 'Retrying sends the same reviewed proposal');
    assert.equal(writeAttempts[1].path, '/api/research-record-revise');
    assert.equal(writeAttempts[1].body.expected_revision, 2);
    assert.equal(writeAttempts[1].body.expected_snapshot, second.snapshot);
    assert.equal(writeAttempts[1].body.change_kind, 'supersession');
    assert.equal(writeAttempts[1].body.reason, labels.research_dossier_draft_revision_reason);
    const historical = await (await page.request.get(recordUrl + '&revision=1')).json();
    assert.deepEqual(historical.record, original.record);
    await readSuggestions(loadButton, false);
    await readSuggestions(existing, true);
    await selectCharacter(rowan);
    await stage.press('Enter');
    await expect(draftsBox.locator('#r-manuscript-drafts-status')).toHaveText(labels.research_dossier_draft_staged_same);
    await expect(dialog).toBeHidden();
    assert.deepEqual(await record(), saved, 'Staging identical manuscript material cannot duplicate the appendix');
    assert.equal(writeAttempts.length, 2);
    await readSuggestions(loadButton, false);
    await expect(catalogue.locator(`[data-draft-select="${rowan}"]`)).toHaveCount(0);
    await catalogue.locator('[data-draft-kind="scene"]').press('Enter');
    await catalogue.locator('[data-draft-select="scene:1:1"]').press('Enter');
    await expect(preview.locator('[data-create-manuscript-draft="scene:1:1"]')).toBeEnabled();
    try {
      fs.writeFileSync(manuscript, source + '\n\n' + latestParagraph + '\n');
      await readSuggestions(existing, true);
      await selectCharacter(rowan);
      await stage.press('Enter');
      await expect(stagePreview).toContainText(latestParagraph);
      await save.press('Enter');
      await expect(dialog).toBeHidden();
      const refreshed = await record();
      assert.equal(refreshed.record.revision, 4);
      assert.ok(refreshed.record.body.startsWith(authoredBody));
      assert.equal(refreshed.record.body.match(/\*\*Rowan\*\* kept watch\./g)?.length, 1);
      assert.ok(refreshed.record.body.includes('**Rowan** returned quietly to the landing.'));
      const previous = await (await page.request.get(recordUrl + '&revision=3')).json();
      assert.deepEqual(previous.record, saved.record, 'Refreshing the saved analysis preserves the earlier pin');
    } finally {
      fs.writeFileSync(manuscript, source);
    }
    assert.deepEqual(errors, []);
  } finally {
    await page.close();
  }
}

(async () => {
  const server = await startNativeServer(`
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
api.create_dossier(project, title='Character: Nightjar', body='A manually authored record about Nightjar.')
for title in ('Figur: Linden', 'Character: Linden'):
    api.create_dossier(project, title=title, tags=['manuscript-draft', 'character'],
        body='One of two existing generated dossiers for Linden.')
manuscript = project / 'manuscript.md'
middle = '\\n\\n'.join(f'Rowan recorded the tally {index} in the notebook.' for index in range(1, ${legacyMiddlePassages} + 1))
manuscript.write_text(
    '# Sample\\n\\n## First chapter\\n\\nMara waited for Ivo. Mara took the lantern.\\n\\n'
    'The mast creaked. A cart stopped nearby.\\n\\nRowan kept watch. Rowan counted the lamps.\\n\\n'
    'The bell fell quiet. The tide moved back.\\n\\n'
    '## Second chapter\\n\\nThe storehouse stood empty.\\n\\n'
    'Nightjar passed the door while Linden waited by the wall.\\n\\n'
    'A courier slept in Greyhaven until the bell rang. Lanterns glowed in Silverbank after dusk.\\n\\n'
    'Er war in Eile und blieb am Kai. Sie blieb in Eile.\\n\\n'
    'A tide chart labelled the next shoal Greyhavenish.\\n\\n'
    '~~~text\\nA forged note from Greyhaven named the ghost route.\\n~~~\\n\\n'
    '## Third chapter\\n\\nThe ferryman called to Mare from the quay.\\n\\n' + middle + '\\n\\n'
    '🧭 The runner called to Rook from the quay. Rowan held the soaked map flat as the crew drew nearer, '
    'and the wind whipped along the edge of the pier, scattering scraps of rope and cloth into the water. '
    'The red paper lantern finally disappeared.\\n\\n***\\n\\nThe far scene opened beneath a hill. '
    'A boat went to Greyhaven before the wharf shift. The boats moored near greyhaven after dawn. '
    'The night ferry returned to Silverbank before the thaw.\\n', encoding='utf-8')
(project / 'lixity.toml').write_text(
    '[characters.Mara]\\naliases = ["Mare"]\\n[characters.Ivo]\\n[characters.Rowan]\\naliases = ["Rook"]\\n'
    '[characters.Nightjar]\\n[characters.Linden]\\n'
    '[scene_analysis.titles]\\n"1:1" = "The quiet morning under the lantern and past the old tide gate"\\n'
    '"2:1" = "The ledger under the lantern"\\n"3:1" = "The runner on the quay"\\n'
    '"3:2" = "The hill beyond the river"\\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.language = 'en'; LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'dossier': dossier['dossier_id'],
    'legacy': legacy['dossier_id']}), flush=True)
server.serve_forever()
`, artifacts);
  const {fixture} = server;
  let browser;
  try {
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
    const manualDossier = draftList.locator('[data-draft-manual-character]');
    await draftsBox.locator(':scope > summary').press('Enter');
    await loadDrafts.press('Enter');
    await expect(ivoDraft).toBeVisible();
    await expect(maraDraft).toHaveAttribute('aria-pressed', 'true');
    await expect(loadDrafts).toBeFocused();
    await ivoDraft.press('Space');
    await expect(preview).toContainText('Ivo');
    await expect(preview.locator('[data-draft-reason] p')).toHaveText('The manuscript contains the configured character name or one of its variants.');
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
    await expect(draftList).toContainText('No suggestions for new character dossiers found.');
    await sceneKind.press('Enter');
    await expect(preview).toContainText(/scenes?/i);
    const savedDossiers = await (await page.request.get(fixture.url + '/api/research/dossiers')).json();
    assert.ok(savedDossiers.dossiers.some(item => item.title === 'Character: Ivo'));
    const maraDossier = savedDossiers.dossiers.find(item => item.title === 'Character: Mara');
    assert.ok(maraDossier);
    await checkCharacterDossier(browser, fixture, maraDossier.id, false);
    await checkCharacterDossier(browser, fixture, fixture.legacy, true);
    await checkExistingCharacterDraft(browser, fixture);

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
    await expect(manualDossier).toHaveClass(/\bprimary\b/);
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
    await checkSceneAndLocationDrafts(page, fixture, draftWrites);

    const manuscript = path.join(artifacts, 'synthetic-project', 'manuscript.md');
    const originalText = fs.readFileSync(manuscript, 'utf8');
    for (const language of ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl']) {
      const labels = require(path.join(root, 'src/lixity/locales', `${language}.json`));
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
      const localizedExisting = draftsBox.locator('[data-draft-load-existing]');
      await expect(localizedExisting).toHaveText(labels.research_dossier_draft_load_existing);
      await expect(loadDrafts).toHaveText(labels.research_dossier_draft_load);
      for (const button of [localizedExisting, loadDrafts]) {
        assert.ok(await button.evaluate(node => node.scrollWidth <= node.clientWidth), `${language} dossier option fits at 320px`);
      }
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

      const placeKind = draftList.locator('[data-draft-kind=location]');
      await placeKind.press('Enter');
      await expect(placeKind).toBeFocused();
      await draftList.locator('[data-draft-select="location:silverbank"]').press('Enter');
      await expect(preview.locator('[data-draft-reason] h6')).toHaveText(labels.research_dossier_draft_reason);
      await expect(preview.locator('[data-draft-reason] p')).toHaveText(labels.research_dossier_draft_reason_location_configured);
      await expect(preview.getByText(labels.research_dossier_draft_location_configured, {exact: true})).toHaveCount(1);
      await expect(preview.locator('[data-draft-preview-body] .research-dossier-body-rendered')).toContainText('Lanterns glowed in Silverbank after dusk.');
      await sceneKind.press('Enter');
      await expect(sceneKind).toBeFocused();
      await expect(draftList.getByRole('heading', {name: labels.research_dossier_draft_scene_individual, exact: true})).toBeVisible();
      await expect(draftList.locator('[data-draft-select="scene:3:2"]')).toContainText(`${labels.research_dossier_draft_scene_unit} 2`);
      await draftList.locator('[data-draft-select="scene:3:2"]').press('Enter');
      await expect(preview.locator('[data-draft-reason] p')).toHaveText(labels.research_dossier_draft_reason_scene_scene);
      assert.ok(await draftList.evaluate(node => node.scrollWidth <= node.clientWidth),
        `${language} draft list and preview fit at 320px`);
      if (language === 'de') await draftList.screenshot({path: path.join(artifacts, 'scene-draft-de-320.png')});

      const legacySummary = page.locator(`#research-dossiers-list [data-research-detail=dossier][data-record-id="${fixture.legacy}"]`);
      await legacySummary.click();
      const dossierDetails = legacySummary.locator('..');
      const localizedDirect = dossierDetails.locator('[data-update-character-dossier]');
      await expect(localizedDirect).toHaveText(labels.research_dossier_draft_stage_existing);
      assert.ok(await localizedDirect.evaluate(button => button.scrollWidth <= button.clientWidth),
        `${language} direct update action fits at 320px`);
      try {
        fs.writeFileSync(manuscript, originalText + '\n\nRowan checked the spare lantern.\n');
        await localizedDirect.press('Enter');
        await expect(dialog.locator('#research-revision-title')).toHaveText(labels.research_dossier_draft_revision_title);
        await expect(dialog.locator('#research-revision-stage-help')).toHaveText(labels.research_dossier_draft_revision_help);
        const saveSupplement = dialog.locator('#research-revision-save');
        const discardSupplement = dialog.locator('#research-revision-discard');
        const editSupplement = dialog.locator('#research-revision-stage-edit');
        await expect(saveSupplement).toHaveText(labels.research_dossier_draft_revision_save);
        await expect(discardSupplement).toHaveText(labels.research_dossier_draft_revision_discard);
        await expect(editSupplement).toHaveText(labels.research_dossier_draft_revision_edit);
        const localizedProposal = dialog.locator('#research-revision-stage-proposal');
        await expect(localizedProposal).toBeVisible();
        await expect(localizedProposal).toContainText(labels.research_dossier_character_distribution);
        await expect(localizedProposal).toContainText(labels.research_dossier_character_passages);
        await expect(localizedProposal).toContainText('Rowan checked the spare lantern.');
        for (const element of [dialog, saveSupplement, discardSupplement, editSupplement]) {
          assert.ok(await element.evaluate(node => node.scrollWidth <= node.clientWidth),
            `${language} staged dossier controls fit at 320px`);
        }
        await discardSupplement.press('Enter');
        await expect(dialog).toBeHidden();
      } finally {
        fs.writeFileSync(manuscript, originalText);
      }
      const character = dossierDetails.locator('details[data-dossier-character]');
      const characterSummary = character.locator(':scope > summary');
      await expect(characterSummary).toHaveText(labels.research_dossier_character_live_heading);
      await expect(dossierDetails.locator('.research-folder-notes > h4')).toHaveText(labels.research_dossier_saved_body);
      await characterSummary.press('Enter');
      await expect(character.getByText(labels.research_dossier_character_live_distribution, {exact: true})).toBeVisible();
      await expect(character.getByText(labels.research_dossier_character_passages, {exact: true}).first()).toBeVisible();
      await expect(character.getByText(labels.research_dossier_character_context_hint, {exact: true})).toBeVisible();
      const firstMatch = character.locator('[data-character-passage]').first();
      const jump = firstMatch.locator('[data-character-jump]');
      await expect(jump).toHaveText(labels.manuscript_link_open_passage);
      assert.ok(await jump.evaluate(button => button.scrollWidth <= button.clientWidth),
        `${language} manuscript jump fits at 320px`);
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

      await page.locator('#research-tab-review').press('Enter');
      const termReports = page.locator('#research-manuscript-terms-section');
      if (!(await termReports.evaluate(node => node.open))) await termReports.locator(':scope > summary').press('Enter');
      const termEditor = termReports.locator('#r-term-manage');
      await termEditor.locator(':scope > summary').press('Enter');
      const addVariant = termEditor.getByRole('button', {name:labels.manuscript_terms_variant_add});
      await addVariant.press('Enter');
      const variant = termEditor.getByRole('group', {name:labels.manuscript_terms_variant_title.replace('{number}', '1')});
      await expect(variant.getByRole('textbox', {name:labels.manuscript_terms_variant_form})).toBeFocused();
      await expect(variant.getByRole('textbox', {name:labels.manuscript_terms_variant_chapters})).toBeVisible();
      await expect(variant.getByRole('textbox', {name:labels.manuscript_terms_variant_note})).toBeVisible();
      assert.ok(await termEditor.evaluate(node => node.scrollWidth <= node.clientWidth), `${language} variant editor fits at 320px`);
      await variant.getByRole('button', {name:labels.manuscript_terms_variant_remove}).press('Enter');
      await expect(addVariant).toBeFocused();
    }
    assert.deepEqual(errors, []);
    console.log(`Dossier workflows: full draft previews, independent scene saves, auditable locations, exact character regeneration and paged character readings passed. Seven locales at 1440/390/320. Screenshots: ${artifacts}`);
  } finally {
    try {
      if (browser) await browser.close();
    } finally {
      await server.close();
      const stderr = server.stderr();
      if (stderr.includes('Traceback')) console.error(stderr);
    }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
