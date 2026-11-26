const {openAnalysisSection} = require('./support/analysis-workflow.cjs');
const {setAnalysisOption} = require('./support/analysis-controls.cjs');
// Shared workbench journeys preserve document identity across optional tools.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-workbench-'));
const fixtures = pythonFixture(`
import json
from dashboard_fixtures import full_dashboard
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
original = full_dashboard.__globals__['render_dashboard']
full_dashboard.__globals__['SAMPLE'] += '\\n\\n## Reading continuity\\n\\n' + '\\n\\n'.join(
    'Synthetic paragraph %d. ' % number + 'A quiet garden gives this scene a place to continue. ' * 6
    for number in range(40))
result = {}
for locale in ('en', 'de'):
    def render(*args, **kwargs):
        return original(*args, **{**kwargs,
            'labels': {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]},
            'language_key': locale, 'enabled_actions': ['analyze', 'research-reader', 'manuscript-pdf', 'site-export'],
            'manuscript_pdf_token': 'synthetic-project', 'research_context_token': 'synthetic-research',
            'manuscript_source_sha256': 'a' * 64})
    full_dashboard.__globals__['render_dashboard'] = render
    result[locale] = full_dashboard()
print(json.dumps(result))
`, {root});
const dossier = {id: 'garden', project_id: 'synthetic-project', title: 'Garden context',
  revision: 1, body: '## Garden\n\nA saved synthetic note.', sections: ['Garden'],
  citations: [], tags: [], claims: []};

async function createPage(browser, html, width, desktop = false) {
  const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion: 'reduce'});
  const errors = [], writes = [];
  page.on('pageerror', error => errors.push(error.message));
  if (desktop) await page.addInitScript(() => {
    window.desktopPreferenceWrites = [];
    window.desktopExportRequests = [];
    window.desktopLinkCalls = [];
    window.desktopRevealCalls = [];
    window.desktopUpdateResult = {current_version: '0.10.0', latest_tag: 'v0.10.0', status: 'current',
      guide_url: 'https://mfahsold.github.io/lixity/guides/installation.html#desktop'};
    window.lixityDesktop = {
      version: 1,
      openExternalUrl: async url => {
        window.desktopLinkCalls.push(url);
        throw new Error('Synthetic opener rejection');
      },
      getPreferences: async () => ({theme: 'light'}),
      checkForUpdates: async () => window.desktopUpdateResult,
      setPreference: async (key, value) => window.desktopPreferenceWrites.push([key, value]),
      saveExport: (spec, filename) => new Promise((resolve, reject) => {
        window.desktopExportRequests.push({spec, filename, resolve, reject});
      }),
      revealInFileManager: async path => window.desktopRevealCalls.push(path),
    };
  });
  await page.route('http://lixity.test/**', route => {
    const url = new URL(route.request().url());
    if (route.request().method() !== 'GET') {
      writes.push(url.pathname);
      return route.fulfill({status: 400, json: {ok: false, message: 'No reading writes'}});
    }
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

async function settle(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}
async function documentState(page) {
  return page.locator('#chapters .ptext').evaluateAll(nodes => nodes.map(node => ({
    id: node.id, hash: node.dataset.paragraphSha256, start: node.dataset.start, end: node.dataset.end,
    text: node.querySelector('.ptext-inner > p')?.textContent,
  })));
}

async function nativeReaderPreferences(browser) {
  const context = await browser.newContext({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
  const reader = {size: 22, width: 'wide', spacing: 'relaxed', metric: 'dialogue', comparison: false,
    evidenceByMetric: {dialogue: false}};
  let releaseFirst, markReading;
  const holdFirst = new Promise(resolve => { releaseFirst = resolve; });
  const reading = new Promise(resolve => { markReading = resolve; });
  const patches = [];
  const errors = [];
  try {
    let firstRead = true;
    await context.exposeFunction('readWorkspacePreferences', async () => {
      const snapshot = structuredClone(reader);
      if (firstRead) {
        firstRead = false;
        markReading();
        await holdFirst;
      }
      return {reader: snapshot};
    });
    await context.exposeFunction('writeWorkspacePreference', (key, patch) => {
      assert.equal(key, 'reader');
      patches.push(patch);
      const {evidenceByMetric, ...fields} = patch;
      Object.assign(reader, fields);
      if (evidenceByMetric) Object.assign(reader.evidenceByMetric, evidenceByMetric);
    });
    await context.addInitScript(() => {
      window.lixityDesktop = {version: 1, getPreferences: window.readWorkspacePreferences,
        setPreference: window.writeWorkspacePreference};
    });
    await context.route('http://127.0.0.1:*/*', route => route.fulfill(
      new URL(route.request().url()).pathname.startsWith('/api/') ?
        {json: {ok: true, records: [], links: []}} : {contentType: 'text/html', body: fixtures.en}
    ));
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    async function openReader(port) {
      await page.goto(`http://127.0.0.1:${port}/`);
      await page.locator('#tab-view-analysis').click();
      await page.locator('#manuscript-analysis-toggle').click();
    }
    const metric = page.locator('#style-layer');
    const counted = page.locator('#analysis-evidence-enabled');
    const comparison = page.locator('#analysis-comparison-enabled');

    await openReader(18731);
    await reading;
    assert.deepEqual(patches, [], 'The temporary default selection does not overwrite native preferences');
    await metric.selectOption('function');
    await setAnalysisOption(page, 'analysis-evidence-enabled', true);
    await expect.poll(() => patches.length).toBe(2);
    releaseFirst();
    await expect(page.locator('#reader-size-value')).toHaveText('22');
    await expect(page.locator('#reader-width')).toHaveValue('wide');
    await expect(page.locator('#reader-spacing')).toHaveValue('relaxed');
    await expect(metric).toHaveValue('function');
    await expect(counted).toBeChecked();
    await expect(comparison).not.toBeChecked();
    assert.deepEqual(patches, [{metric: 'function'}, {evidenceByMetric: {function: true}}],
      'Hydration respects the subsequent edits without publishing a stale snapshot');

    await page.locator('#reader-settings summary').click();
    await page.locator('#reader-text-larger').click();
    await page.locator('#reader-settings [data-reader-choice="narrow"]').click();
    await page.locator('#reader-settings [data-reader-choice="compact"]').click();
    await expect.poll(() => patches.length).toBe(5);

    // A fresh loopback port has a different localStorage origin.
    await openReader(18732);
    await expect(page.locator('#reader-size-value')).toHaveText('24');
    await expect(page.locator('#reader-width')).toHaveValue('narrow');
    await expect(page.locator('#reader-spacing')).toHaveValue('compact');
    await expect(metric).toHaveValue('function');
    await expect(counted).toBeChecked();
    await expect(comparison).not.toBeChecked();
    assert.equal(patches.length, 5, 'Loading the portable preferences sends no redundant writes');

    await metric.selectOption('');
    await expect.poll(() => reader.metric).toBe('');
    await openReader(18733);
    await expect(page.locator('#reader-size-value')).toHaveText('24');
    await expect(metric).toHaveValue('');
    assert.deepEqual(errors, []);
  } finally {
    releaseFirst();
    await context.close();
  }
}

(async () => {
  const browser = await launchChromium();
  try {
    await nativeReaderPreferences(browser);
    const desktop = await createPage(browser, fixtures.en, 1440, true);
    try {
      const {page} = desktop;
      const sendMenu = action => page.evaluate(id =>
        window.dispatchEvent(new CustomEvent('lixity:desktop-menu', {detail: id})), action);
      const overview = page.locator('#workbench-overview-back');
      const manuscriptTab = page.locator('#tab-view-analysis');
      await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
      assert.deepEqual(await page.evaluate(() => desktopPreferenceWrites), []);
      const footer = page.locator('#license-terms .license-links');
      for (const [name, url, activate] of [
        ['Full AGPL license', 'https://github.com/mfahsold/lixity/blob/main/LICENSE', link => link.press('Enter')],
        ['Project funding', 'https://github.com/mfahsold/lixity/blob/main/docs/FUNDING.md', link => link.click()],
        ['Request a commercial license', 'https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md#when-to-talk-to-the-maintainer', link => link.click()],
      ]) {
        await page.context().route(url.split('#')[0], route => route.fulfill({body: name}));
        const opened = page.waitForEvent('popup');
        await activate(footer.getByRole('link', {name}));
        const popup = await opened;
        await popup.waitForURL(url);
        await popup.close();
      }
      assert.deepEqual(await page.evaluate(() => desktopLinkCalls), [], 'Anchor navigation is handled by the host');
      await sendMenu('help-check-updates');
      const updateDialog = page.locator('#modal-desktop-environment');
      const updateStatus = updateDialog.getByRole('status');
      const downloadGuide = updateDialog.getByRole('button', {name: 'Open desktop downloads'});
      await expect(updateStatus).toContainText('The installed desktop version is current.');
      await expect(updateStatus).toContainText('Installed 0.10.0 · Published v0.10.0');
      await expect(downloadGuide).toHaveCount(0);
      await page.evaluate(() => {
        window.desktopUpdateResult = {...window.desktopUpdateResult, latest_tag: 'v0.11.0', status: 'available'};
      });
      await updateDialog.getByRole('button', {name: 'Check for Updates…'}).click();
      await expect(updateStatus).toContainText('A newer desktop installer is available.');
      await expect(updateStatus).toContainText('Installed 0.10.0 · Published v0.11.0');
      await expect(downloadGuide).toBeVisible();
      await updateDialog.locator('[data-close-desktop-env]').click();
      await sendMenu('view-research');
      await expect(page.locator('#tab-view-research')).toHaveAttribute('aria-selected', 'true');
      await sendMenu('view-analysis-overview');
      await expect(manuscriptTab).toHaveAttribute('aria-selected', 'true');
      await expect(overview).toBeFocused();
      await expect(page.locator('#analysis-measurements')).toBeVisible();
      await overview.click();
      await page.locator('#tab-view-project').click();
      await page.evaluate(() => window.LixityCommandPalette.open());
      const search = page.locator('#command-palette-search');
      await search.fill('Analysis overview');
      await search.press('Enter');
      await expect(manuscriptTab).toHaveAttribute('aria-selected', 'true');
      await expect(overview).toBeFocused();
      await sendMenu('view-toggle-theme');
      await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
      assert.deepEqual(await page.evaluate(() => desktopPreferenceWrites), [['theme', 'dark']]);
      await sendMenu('file-export-pdf');
      const layout = page.locator('#manuscript-pdf-layout');
      const download = page.locator('#manuscript-pdf-download');
      const status = page.locator('#manuscript-pdf-status');
      await expect(layout).toBeVisible();
      await expect(layout).toBeFocused();
      await layout.selectOption('sheet');
      const filename = String.raw`Kapitel \ Rohfassung.pdf`;
      const savedPath = `/synthetic/${filename}`;
      for (const [index, outcome, message] of [
        [0, {saved: false}, ''],
        [1, null, 'The PDF could not be created. Try again; after changing projects, reload this page.'],
        [2, {saved: true, path: savedPath, filename}, 'PDF download started.'],
      ]) {
        await download.click();
        await expect(download).toBeDisabled();
        await expect(status).not.toHaveText('PDF download started.');
        assert.deepEqual(await page.evaluate(i => {
          const {spec, filename} = desktopExportRequests[i];
          return {spec, filename};
        }, index), {spec: {path: '/api/manuscript-pdf', method: 'POST',
          payload: {layout: 'sheet', project_token: 'synthetic-project'}}, filename: 'manuscript-sheet.pdf'});
        await page.evaluate(([i, saved]) => {
          if (saved) desktopExportRequests[i].resolve(saved);
          else desktopExportRequests[i].reject('Synthetic save failure');
        }, [index, outcome]);
        await expect(status).toHaveText(message);
        await expect(download).toBeEnabled();
        await expect(page.locator('.desktop-save-toast')).toHaveCount(index === 2 ? 1 : 0);
      }
      const toast = page.locator('.desktop-save-toast');
      await expect(toast.getByRole('status')).toHaveText(`Saved ${filename}`);
      await expect(page.locator('body > .desktop-save-toast')).toHaveCount(1);
      await toast.getByRole('button', {name: 'Show in folder'}).click();
      assert.deepEqual(await page.evaluate(() => desktopRevealCalls), [savedPath]);
      await page.evaluate(({filename, savedPath}) => {
        const modal = document.createElement('dialog');
        modal.className = 'lixity-modal';
        modal.textContent = 'Synthetic export dialog';
        document.body.appendChild(modal);
        modal.showModal();
        window.LixityDesktopBridge.notifySavedExport({saved: true, path: savedPath, filename});
      }, {filename, savedPath});
      await expect(page.locator('dialog:modal .desktop-save-toast')).toHaveCount(1);
      await toast.getByRole('button', {name: 'Show in folder'}).click();
      assert.deepEqual(await page.evaluate(() => desktopRevealCalls), [savedPath, savedPath]);
      await toast.getByRole('button', {name: 'Close', exact: true}).click();
      await expect(toast).toBeHidden();
      await page.evaluate(() => document.querySelector('dialog:modal').remove());
      await page.locator('#btn-site-export').click();
      const siteDownload = page.locator('#site-export-download');
      const siteStatus = page.locator('#site-export-status');
      await page.locator('#site-export-research').check();
      await page.locator('#site-export-sources').check();
      for (const saved of [false, true]) {
        await siteDownload.click();
        await expect(siteDownload).toBeDisabled();
        await expect(siteStatus).toHaveText('Preparing website…');
        assert.deepEqual(await page.evaluate(() => {
          const {spec, filename} = desktopExportRequests.at(-1);
          return {spec, filename};
        }), {spec: {path: '/api/site-export', method: 'POST', payload: {
          project_token: 'synthetic-project', include_research: true, include_source_files: true,
        }}, filename: 'lixity-reading-website.zip'});
        await page.evaluate(saved => desktopExportRequests.at(-1).resolve({saved}), saved);
        await expect(siteDownload).toBeEnabled();
        if (saved) await expect(siteStatus).toContainText('Unzip the ZIP and open index.html');
        else await expect(siteStatus).toHaveText('');
      }
      assert.deepEqual(desktop.writes, []);
      assert.deepEqual(desktop.errors, []);
    } finally {
      await desktop.page.close();
    }

    const {page: shortcutPage} = await createPage(browser, fixtures.en, 1440);
    try {
      await shortcutPage.mouse.move(320, 450);
      await shortcutPage.mouse.wheel(0, 360);
      await shortcutPage.waitForFunction(() => window.scrollY > 64 && window.LixityChrome.isHidden());
      await shortcutPage.evaluate(() => {
        const query = document.querySelectorAll;
        let toolbarChecks = 0;
        window.readToolbarChecks = () => {
          document.querySelectorAll = query;
          return toolbarChecks;
        };
        document.querySelectorAll = function(selector) {
          if (selector === '.passage-jump-bar:not([hidden])') toolbarChecks++;
          return query.call(this, selector);
        };
      });
      for (let step = 0; step < 8; step++) {
        const previous = await shortcutPage.evaluate(() => window.scrollY);
        await shortcutPage.mouse.wheel(0, 70);
        await shortcutPage.waitForFunction(top => window.scrollY > top, previous);
      }
      assert.equal(await shortcutPage.evaluate(() => window.readToolbarChecks()), 0,
        'Steady downward scrolling keeps hidden toolbars without checking their geometry again');
      await shortcutPage.mouse.wheel(0, -100);
      await shortcutPage.waitForFunction(() => !window.LixityChrome.isHidden());
      const readerControls = shortcutPage.locator('#manuscript-reader-controls');
      const analysisToggle = shortcutPage.locator('#manuscript-analysis-toggle');
      const toolbarOpacities = () => shortcutPage
        .locator('#manuscript-reader-controls, #analysis-outline-document > .toolbar')
        .evaluateAll(bars => bars.map(bar => getComputedStyle(bar).opacity));
      await shortcutPage.clock.install();
      await analysisToggle.click();
      await analysisToggle.blur();
      await settle(shortcutPage);
      await shortcutPage.mouse.move(1000, 650);
      const beforeReviewScroll = await shortcutPage.evaluate(() => window.scrollY);
      await shortcutPage.mouse.wheel(0, 360);
      await shortcutPage.waitForFunction(top => window.scrollY > top, beforeReviewScroll);
      assert.deepEqual(await toolbarOpacities(), ['1', '1'],
        'Downward scrolling leaves the active manuscript analysis toolbar visible');
      for (const selector of ['#manuscript-analysis-toggle', '#style-layer', '#text-search']) {
        const control = shortcutPage.locator(selector);
        await expect(control).toBeInViewport({ratio: 1});
        assert.ok(await control.evaluate(node => {
          const rect = node.getBoundingClientRect();
          const target = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
          return node.contains(target);
        }), 'Active manuscript analysis controls are reachable without moving the pointer back to the toolbar');
      }
      await shortcutPage.clock.fastForward(4000);
      assert.deepEqual(await toolbarOpacities(), ['1', '1'],
        'Inactivity leaves the active manuscript analysis toolbar visible');
      await analysisToggle.click();
      const prompter = shortcutPage.locator('#teleprompter-modal');
      for (const view of ['research', 'project']) {
        await shortcutPage.locator('#tab-view-' + view).click();
        await shortcutPage.keyboard.press('p');
        assert.equal(await prompter.isVisible(), false, 'P leaves the ' + view + ' view alone');
      }
      await shortcutPage.locator('#tab-view-analysis').click();
      await shortcutPage.locator('#workbench-overview-open').click();
      await openAnalysisSection(shortcutPage, 'style');
      await shortcutPage.locator('[data-analysis-section-target="style"]').blur();
      await settle(shortcutPage);
      await shortcutPage.evaluate(() => window.scrollTo({top: 0, behavior: 'instant'}));
      await shortcutPage.mouse.move(1000, 650);
      const beforeOverviewScroll = await shortcutPage.evaluate(() => window.scrollY);
      await shortcutPage.mouse.wheel(0, 240);
      await shortcutPage.waitForFunction(top => window.scrollY > top, beforeOverviewScroll);
      assert.equal(await readerControls.evaluate(node => getComputedStyle(node).opacity), '1',
        'Downward scrolling leaves the analysis overview return controls visible');
      await expect(shortcutPage.locator('#workbench-overview-back')).toBeInViewport({ratio: 1});
      await shortcutPage.clock.fastForward(4000);
      assert.equal(await readerControls.evaluate(node => getComputedStyle(node).opacity), '1',
        'Inactivity leaves the analysis overview return controls visible');
      await shortcutPage.keyboard.press('p');
      assert.equal(await prompter.isVisible(), false, 'P leaves the analysis overview open');
      await shortcutPage.locator('#workbench-overview-back').click();
      await shortcutPage.locator('#reader-settings > summary').click();
      await shortcutPage.keyboard.press('p');
      assert.equal(await prompter.isVisible(), false, 'P leaves the appearance settings open');
      await shortcutPage.keyboard.press('Escape');
      await shortcutPage.locator('#reader-chapter').press('p');
      assert.equal(await prompter.isVisible(), false, 'P is available for native select keyboard navigation');
      await shortcutPage.evaluate(() => window.LixityCommandPalette.open());
      await shortcutPage.keyboard.press('p');
      assert.equal(await prompter.isVisible(), false, 'P is available for an open dialog’s input');
      await shortcutPage.keyboard.press('Escape');
      await shortcutPage.locator('#reader-teleprompter').press('p');
      assert.equal(await prompter.isVisible(), true, 'P activates the eligible manuscript control');
    } finally {
      await shortcutPage.close();
    }
    for (const [locale, html] of Object.entries(fixtures)) for (const width of [1440, 320]) {
      const {page, errors, writes} = await createPage(browser, html, width);
      const toggle = page.locator('#manuscript-analysis-toggle');
      assert.equal(await toggle.count(), 1, 'Analysis has one explicit visible display control');
      assert.equal(await toggle.getAttribute('aria-pressed'), 'false');
      const name = await toggle.getAttribute('aria-label');
      assert.ok(name && (await toggle.textContent()).trim(), 'State is named in the interface');
      const original = await documentState(page);
      await page.locator('#workbench-overview-open').click();
      await page.locator('#workbench-overview-back').click();
      await settle(page);
      assert.equal(await toggle.getAttribute('aria-pressed'), 'false',
        'A temporary overview returns to the previous analysis-layer preference');
      await page.locator('#chapters .ptext').nth(25).scrollIntoViewIfNeeded();
      const currentPassage = await page.evaluate(() => LixityReader.capture().panel.id);
      const prose = page.locator('#' + currentPassage + ' .ptext-inner > p');
      const beforeAnalysis = await prose.boundingBox();
      const beforeToggle = await toggle.boundingBox();
      const beforeNavigation = await page.locator('#workspace-navigation-toggle').getAttribute('aria-expanded');
      await toggle.click();
      await settle(page);
      assert.equal(await page.locator('#workspace-context-panel').isVisible(), false,
        'The analysis layer does not implicitly open a context tool');
      const afterAnalysis = await prose.boundingBox();
      assert.ok(Math.abs((await toggle.boundingBox()).width - beforeToggle.width) <= 1,
        'The On/Off switch keeps its width across state labels and selected type weight');
      for (const key of ['x', 'y', 'width', 'height']) assert.ok(
        Math.abs(beforeAnalysis[key] - afterAnalysis[key]) <= 2,
        `Revealing analysis preserves prose ${key}, without rewrapping or moving its passage`);
      assert.equal(await page.locator('#workspace-navigation-toggle').getAttribute('aria-expanded'), beforeNavigation,
        'Revealing analysis preserves the navigation arrangement');
      assert.equal(await toggle.getAttribute('aria-pressed'), 'true');
      assert.equal(await toggle.getAttribute('aria-label'), name, 'A toggle keeps its accessible name');
      if (width === 320) {
        await page.locator('#' + currentPassage + ' [data-reader-paragraph]').click();
        await page.locator('[data-reader-action=values]').click();
        await settle(page);
        await toggle.focus();
        await toggle.press('Space'); await settle(page);
        assert.equal(await toggle.evaluate(node => document.activeElement === node), true,
          'Hiding analysis with its keyboard toggle retains that toggle focus');
        await toggle.press('Space');
        assert.equal(await toggle.getAttribute('aria-pressed'), 'true');
        assert.equal(await page.locator('#manuscript-context-menu').isVisible(), false,
          'A second Space reverses Analysis rather than opening paragraph actions');
      }
      await page.locator('#workspace-reader-toggle').click();
      await page.locator('#workspace-reader-dossier').selectOption('garden');
      await page.locator('#workspace-reader-body h3').waitFor();
      await toggle.click();
      assert.equal(await toggle.getAttribute('aria-pressed'), 'false');
      assert.equal(await page.locator('#workspace-reader-panel').isVisible(), true,
        'Hiding analysis preserves a separately selected dossier');
      await toggle.click();
      assert.equal(await page.locator('#workspace-reader-panel').isVisible(), true);
      // Return from a relation route requests the document even if it is already active.
      await page.locator('#tab-view-research').click();
      await page.locator('#tab-view-analysis').click();
      await page.evaluate(() => LixityWorkbench.dispatch({type: 'surface', value: 'document'}));
      assert.equal(await page.locator('#workspace-reader-panel').isVisible(), true,
        'Resuming an already active document preserves its dossier');
      await page.locator('#chapters .ptext').nth(25).scrollIntoViewIfNeeded();
      const passageOrigin = await page.evaluate(() => { const anchor = LixityReader.capture(); return {id: anchor.panel.id, top: anchor.top}; });
      await page.locator('#workbench-overview-open').click();
      assert.equal(await page.locator('.analysis-workflow-entries').isVisible(), true);
      const overviewHeading = await page.locator('#analysis-review h2').boundingBox();
      assert.ok(overviewHeading.y >= 0 && overviewHeading.y + overviewHeading.height <= 900,
        'Opening the overview from a deep passage starts at its first review heading');
      assert.equal(await page.locator('#workbench-overview-back').isVisible(), true);
      await openAnalysisSection(page, 'matrix');
      await page.locator('#workbench-overview-back').click();
      await settle(page);
      assert.ok(Math.abs(await page.locator('#' + passageOrigin.id).evaluate(node => node.getBoundingClientRect().top) - passageOrigin.top) <= 2,
        'Overview section navigation preserves the original passage return');
      assert.equal(await page.locator('#workspace-reader-panel').isVisible(), true,
        'Overview return restores the document context tool');
      await page.locator('#chapters .ptext').nth(25).scrollIntoViewIfNeeded();
      const offOrigin = await page.evaluate(() => { const anchor = LixityReader.capture(); return {id: anchor.panel.id, top: anchor.top}; });
      await page.locator('#workbench-overview-open').click();
      await openAnalysisSection(page, 'matrix');
      assert.equal(await toggle.isVisible(), false, 'Analysis marks are controlled from the document surface');
      await page.locator('#workbench-overview-back').click();
      await toggle.click(); await settle(page);
      assert.ok(Math.abs(await page.locator('#' + offOrigin.id).evaluate(node => node.getBoundingClientRect().top) - offOrigin.top) <= 2,
        'Returning from overview and hiding analysis preserves the original passage');
      assert.equal(await page.locator('#workspace-reader-panel').isVisible(), true);
      await page.locator('#workspace-reader-close').click();

      const first = page.locator('#chapters .ptext').first();
      await first.locator('[data-reader-paragraph]').click();
      await page.locator('[data-reader-action=values]').click();
      await page.locator('#reader-settings > summary').click();
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#reader-settings').evaluate(node => node.open), false,
        'Escape closes appearance before the underlying context dock');
      assert.equal(await page.locator('#reader-inspector').isVisible(), true);
      await page.locator('#tab-view-research').click();
      await page.locator('[data-rtab=claims]').click();
      const composer = page.locator('#r-claim-composer');
      await composer.locator('summary').first().click();
      await composer.locator('[data-close-disclosure]').focus();
      await page.keyboard.press('Escape');
      assert.equal(await composer.evaluate(node => node.open), false,
        'One Escape closes the active disclosure, not a hidden manuscript tool');
      await page.locator('#tab-view-analysis').click();
      await page.locator('#reader-inspector-close').click();

      await page.locator('#chapters .ptext').nth(25).scrollIntoViewIfNeeded();
      await settle(page);
      assert.equal(await toggle.isVisible(), true);
      const rect = await toggle.boundingBox();
      assert.ok(rect.y >= 0 && rect.y + rect.height <= 900, 'Analysis reversal remains in the viewport');
      await toggle.click();
      assert.deepEqual(await documentState(page), original, 'Analysis and tools preserve exact source text/anchors');
      assert.deepEqual(writes, []); assert.deepEqual(errors, []);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      await page.screenshot({path: path.join(artifacts, `${locale}-${width}.png`)});
      await page.close();
    }
    console.log(`Workbench journeys passed; screenshots: ${artifacts}`);
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
