// Context help explains existing reading actions without becoming a prerequisite.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const {pythonFixture} = require('./support/python-fixture.cjs');

const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-contextual-help-'));
const settingsOnly = process.argv.includes('--settings-only');
const touchOnly = process.argv.includes('--touch-only');
const fixtures = pythonFixture(`
import json
from lixity import CorpusConfig
from lixity.config import resolve_thresholds
from lixity.language import get_language_profile
from lixity.pipeline import analyze_document
from lixity.ui import render_dashboard
from lixity.workspace_labels import WORKSPACE_LABELS
text = '\\n\\n'.join('## Synthetic chapter %d\\n\\n' % chapter + '\\n\\n'.join(
    'Synthetic passage %d. The searchable garden phrase belongs to this passage. ' % paragraph +
    'A quiet courtyard gives this synthetic paragraph enough text to read. ' * 4
    for paragraph in range(1, 7)) for chapter in range(1, 4))
analysis = analyze_document(text, CorpusConfig(language='en', chapter_regex=r'(?m)^##\\s+'),
                            resolve_thresholds(project_config={}))
fixtures = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    fixtures[locale] = {'labels': labels, 'html': render_dashboard(
        analysis.chapters, analysis.paragraphs, metrics=analysis.metrics, fingerprint=analysis.fingerprint,
        title='Synthetic contextual help', labels=labels, language_key=locale, controls=True,
        enabled_actions=['analyze', 'research-reader'], manuscript_pdf_token='synthetic-project',
        research_context_token='synthetic-research', manuscript_source_sha256='a' * 64)}
print(json.dumps(fixtures))
`, {root});

async function settle(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function createPage(browser, fixture, width) {
  const page = await browser.newPage({viewport: {width, height: 900}, hasTouch: width === 320, reducedMotion: 'reduce'});
  page.setDefaultTimeout(5000);
  const errors = [], writes = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => {
    if (['warning', 'error'].includes(message.type())) errors.push(message.text());
  });
  await page.route('**/*', route => {
    const request = route.request(), url = new URL(request.url());
    if (request.method() !== 'GET') {
      writes.push(url.pathname);
      return route.fulfill({status: 400, json: {ok: false, message: 'Reading help cannot save'}});
    }
    if (url.origin !== 'http://lixity.test') return route.abort();
    if (url.pathname.startsWith('/api/')) return route.fulfill({json: {
      ok: true, initialized: true, project_id: 'synthetic-project', records: [], sources: [],
      dossiers: [], claims: [], decisions: [], candidates: [], links: [],
    }});
    return route.fulfill({contentType: 'text/html', body: fixture.html});
  });
  await page.goto('http://lixity.test/');
  assert.match(await page.title(), /^Synthetic contextual help – /);
  await page.locator('#tab-view-analysis').click();
  await settle(page);
  return {page, errors, writes, source: await manuscript(page)};
}

function manuscript(page) {
  return page.locator('#chapters .ptext').evaluateAll(nodes => nodes.map(node => ({
    id: node.id, start: node.dataset.start, end: node.dataset.end,
    text: node.querySelector('.ptext-inner > p').textContent,
  })));
}

async function helpControls(page, labels, locale, width) {
  const controls = [
    ['#manuscript-analysis-toggle', 'reading_help_analysis', 'reading_analysis'],
    ['#workbench-overview-open', 'reading_help_overview', 'reading_overview'],
    ['#reader-focus', 'reading_help_focus', 'reading_focus'],
    ['#text-search', 'reading_help_search', 'text_search'],
    ['#workspace-reader-toggle', 'reader_hint', 'reader_toggle'],
    ['#chapters [data-reader-paragraph]', 'reading_help_actions', 'reading_actions'],
  ];
  const missing = [];
  for (const [selector, help] of controls) {
    if (await page.locator(selector).first().getAttribute('data-help') !== labels[help]) missing.push(selector);
  }
  assert.deepEqual(missing, [], 'Reading controls must expose the localized explanations: ' + missing.join(', '));
  const tip = page.locator('#lixity-tooltip');
  for (const [selector, help, name] of controls) {
    const control = page.locator(selector).first();
    await control.scrollIntoViewIfNeeded();
    await control.focus();
    await expect(tip).toHaveAttribute('aria-hidden', 'false');
    await expect(tip).toHaveText(labels[help]);
    await expect(control).toHaveAccessibleName(labels[name]);
    await expect(control).toHaveAccessibleDescription(labels[help]);
    assert.equal(await tip.locator('a, button, input, select, textarea, [tabindex]').count(), 0,
      'A descriptive tooltip introduces no extra action or focus stop');
    const box = await tip.boundingBox();
    assert.ok(box.x >= 0 && box.x + box.width <= width && box.y >= 0 && box.y + box.height <= 900,
      'Localized help remains inside the viewport');
    if (selector === '#manuscript-analysis-toggle') {
      await page.screenshot({path: path.join(artifacts, `${locale}-${width}-help.png`)});
    }
    await page.keyboard.press('Escape');
    await expect(tip).toHaveAttribute('aria-hidden', 'true');
    await expect(control).toHaveAccessibleName(labels[name]);
    assert.equal(await control.evaluate(node => node === document.activeElement), true);
    assert.equal((await control.getAttribute('aria-describedby') || '').includes('lixity-tooltip'), false);
    if (width === 1440) {
      await control.hover();
      await expect(tip).toHaveAttribute('aria-hidden', 'false');
      await expect(tip).toHaveText(labels[help]);
      await page.mouse.move(0, 0);
      await page.keyboard.press('Escape');
      await expect(tip).toHaveAttribute('aria-hidden', 'true');
    }
  }
}

async function keyboardActions(page) {
  const action = page.locator('#chapters [data-reader-paragraph]').first();
  assert.equal(await action.getAttribute('aria-keyshortcuts'), 'Shift+F10');
  await action.scrollIntoViewIfNeeded(); await action.focus();
  await action.press('Shift+F10');
  const menu = page.locator('#manuscript-context-menu');
  await expect(menu).toBeVisible();
  assert.equal(await menu.locator('[data-reader-action]').first().evaluate(node => node === document.activeElement), true);
  await action.hover();
  await expect(page.locator('#lixity-tooltip')).toHaveAttribute('aria-hidden', 'false');
  await page.keyboard.press('Escape');
  await expect(page.locator('#lixity-tooltip')).toHaveAttribute('aria-hidden', 'true');
  await expect(menu).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();
  await expect(page.locator('#lixity-tooltip')).toHaveAttribute('aria-hidden', 'true');
  assert.equal(await action.evaluate(node => node === document.activeElement), true,
    'Escape returns keyboard focus to the paragraph action that opened the menu');

  const search = page.locator('#text-search');
  assert.equal(await search.getAttribute('aria-keyshortcuts'), 'Enter Shift+Enter Escape');
  await search.fill('pending synthetic query');
  await search.press('Escape');
  assert.equal(await search.inputValue(), '', 'Search Escape clears its query even while contextual help is visible');
  await search.fill('searchable garden phrase');
  await page.waitForFunction(() => document.querySelector('#chapters .ptext .text-hit'));
  const first = await page.evaluate(() => decodeURIComponent(location.hash.slice(1)));
  assert.ok(await page.locator('#' + first + ' .text-hit').count() > 0);
  await search.press('Enter');
  const next = await page.evaluate(() => decodeURIComponent(location.hash.slice(1)));
  assert.notEqual(next, first, 'Enter visits a different real matching paragraph');
  assert.ok(await page.locator('#' + next + ' .text-hit').count() > 0);
  await search.press('Shift+Enter');
  assert.equal(await page.evaluate(() => decodeURIComponent(location.hash.slice(1))), first,
    'Shift+Enter visits the previous matching paragraph');
  await page.waitForFunction(() => document.querySelector('#chapters .ptext.flash'));
  await expect(page.locator('#chapters .ptext.flash')).toHaveCount(0, {timeout: 2400});
  await search.press('Escape');
  assert.equal(await search.inputValue(), '');
  assert.equal(await page.locator('#chapters .text-hit').count(), 0);
  assert.equal(await page.locator('body').evaluate(node => node.classList.contains('text-search-active')), false);
}

async function hoverIntent(page) {
  const y = page.viewportSize().height - 80;
  await page.evaluate(top => {
    const host = document.createElement('div'); host.id = 'synthetic-hover-intent';
    Object.assign(host.style, {position: 'fixed', left: '12px', top: top + 'px', width: '220px', height: '60px', zIndex: '10000'});
    host.textContent = 'Synthetic loading metadata'; document.body.appendChild(host);
  }, y);
  try {
    await page.mouse.move(30, y + 20); await page.keyboard.press('Escape');
    await page.evaluate(() => {
      const metadata = document.createElement('span');
      metadata.title = 'Synthetic exact timestamp'; metadata.textContent = 'Synthetic readable date';
      Object.assign(metadata.style, {display: 'block', width: '100%', height: '100%'});
      document.getElementById('synthetic-hover-intent').replaceChildren(metadata);
    });
    await settle(page);
    const tip = page.locator('#lixity-tooltip');
    await expect(tip).toHaveAttribute('aria-hidden', 'true');
    await page.mouse.move(31, y + 20);
    await expect(tip).toHaveAttribute('aria-hidden', 'false');
    await expect(tip).toHaveText('Synthetic exact timestamp');
    await page.keyboard.press('Escape');
    await expect(tip).toHaveAttribute('aria-hidden', 'true');
  } finally {
    await page.mouse.move(0, 0);
    await page.evaluate(() => document.getElementById('synthetic-hover-intent').remove());
  }
}

async function touchAfterHoverDeparture(browser) {
  const state = await createPage(browser, fixtures.en, 320), {page} = state;
  try {
    const now = new Date('2026-10-22T12:00:00Z');
    await page.clock.install({time: now});
    await page.clock.pauseAt(now);
    await page.evaluate(() => {
      const host = document.createElement('div'); host.id = 'synthetic-hover-departures';
      Object.assign(host.style, {position: 'fixed', inset: '100px 0 auto', height: '150px', zIndex: '10000', background: 'white'});
      document.body.appendChild(host);
      window.syntheticHoverDepartures = 0;
      host.addEventListener('mouseout', event => {
        if (event.target.matches('.help')) window.syntheticHoverDepartures++;
      });
    });
    const tip = page.locator('#lixity-tooltip');
    for (const left of [20, 140]) {
      await page.mouse.move(left + 20, 120);
      await page.evaluate(left => {
        const help = document.createElement('span'); help.className = 'help'; help.tabIndex = 0;
        help.dataset.help = 'Synthetic hover context'; help.textContent = 'Hover context';
        Object.assign(help.style, {position: 'absolute', left: left + 'px', top: '0', width: '80px', height: '45px'});
        document.getElementById('synthetic-hover-departures').appendChild(help);
      }, left);
      await page.clock.runFor(20);
      await page.mouse.move(left + 20, 120);
      await expect(tip).toHaveAttribute('aria-hidden', 'true');
      await page.mouse.move(left + 110, 120);
    }
    assert.equal(await page.evaluate(() => window.syntheticHoverDepartures), 2,
      'Two real departures from reflowed inactive help precede the touch gesture');
    await page.evaluate(() => {
      const help = document.createElement('span'); help.className = 'help'; help.tabIndex = 0;
      help.id = 'synthetic-touch-help'; help.dataset.help = 'Synthetic touch explanation'; help.textContent = 'Touch explanation';
      Object.assign(help.style, {position: 'absolute', left: '20px', top: '70px', width: '220px', height: '45px'});
      document.getElementById('synthetic-hover-departures').appendChild(help);
    });
    const help = page.locator('#synthetic-touch-help');
    await help.focus(); await page.keyboard.press('Escape');
    await expect(tip).toHaveAttribute('aria-hidden', 'true');
    await help.tap();
    await expect(tip).toHaveAttribute('aria-hidden', 'false');
    await page.clock.runFor(200);
    await expect(tip, 'Old hover departures cannot dismiss an explicitly opened touch explanation').toHaveAttribute('aria-hidden', 'false');
    await help.tap();
    await expect(tip).toHaveAttribute('aria-hidden', 'true');
    await page.clock.runFor(1100);
    await page.mouse.move(40, 190);
    await expect(tip).toHaveAttribute('aria-hidden', 'false');
    await page.mouse.move(280, 190);
    await page.clock.runFor(200);
    await expect(tip, 'A real mouse departure still dismisses its own hover explanation').toHaveAttribute('aria-hidden', 'true');
    await page.locator('#synthetic-hover-departures').click({position: {x: 290, y: 130}});
    await help.focus();
    await page.keyboard.press('Shift+Tab'); await page.keyboard.press('Tab');
    await expect(help).toBeFocused();
    await expect(tip).toHaveAttribute('aria-hidden', 'false');
    await page.keyboard.press('Escape');
    await expect(tip).toHaveAttribute('aria-hidden', 'true');
    assert.deepEqual(state.errors, []); assert.deepEqual(state.writes, []);
    assert.deepEqual(await manuscript(page), state.source);
  } finally { await page.close(); }
}

async function adjacentToolbarActions(page, locale, width) {
  await page.locator('#chapters .ptext').nth(8).scrollIntoViewIfNeeded();
  const trigger = page.locator('#reader-focus'), tip = page.locator('#lixity-tooltip');
  await trigger.focus();
  await expect(tip).toHaveAttribute('aria-hidden', 'false');
  assert.deepEqual(await tip.evaluate(node => {
    const hint = node.getBoundingClientRect();
    return Array.from(document.querySelectorAll('.manuscript-reader-controls button, .manuscript-reader-controls select, .manuscript-reader-controls summary, .toolbar input, .toolbar button, .toolbar a'))
      .filter(control => {
        const box = control.getBoundingClientRect();
        return control.getClientRects().length && box.width > 0 && box.height > 0 &&
          box.right > hint.left && box.left < hint.right && box.bottom > hint.top && box.top < hint.bottom;
      }).map(control => control.id || control.tagName);
  }), [], 'A reading hint cannot cover another action in the compact toolbar or its adjacent search row');
  await tip.hover();
  await expect(tip).toHaveAttribute('aria-hidden', 'false');
  await page.screenshot({path: path.join(artifacts, `${locale}-${width}-toolbar-help.png`)});
  await page.locator('#workbench-overview-open').click({timeout: 2000});
  await expect(page.locator('#manuscript-analysis-panels')).toBeVisible();
  await page.locator('#workbench-overview-back').click(); await settle(page);
  await trigger.focus();
  await expect(tip).toHaveAttribute('aria-hidden', 'false');
  await page.locator('#text-search').click({timeout: 2000});
  assert.equal(await page.locator('#text-search').evaluate(node => node === document.activeElement), true,
    'Search remains directly clickable while a neighboring reading hint is open');
  await page.keyboard.press('Escape');
}

async function shortcutReference(page, labels, locale, width, height = 900) {
  const reference = page.locator('#reader-settings .reader-shortcuts');
  assert.equal(await reference.count(), 1, 'Reading settings expose a visible keyboard reference');
  if (height === 480) {
    // A queued native toggle can place the panel after its first painted frame.
    await page.evaluate(() => {
      const settings = document.getElementById('reader-settings');
      window.__settingsOpeningFrame = new Promise(resolve => {
        function sample() {
          if (settings.open) resolve(settings.querySelector('.reader-settings-body').getBoundingClientRect().toJSON());
          else requestAnimationFrame(sample);
        }
        requestAnimationFrame(sample);
      });
    });
  }
  await page.locator('#reader-settings > summary').click();
  await expect(reference).toBeVisible();
  await expect(reference).toContainText(labels.reading_shortcuts);
  for (const key of ['reading_shortcut_actions', 'reading_shortcut_search', 'reading_shortcut_close']) {
    await expect(reference).toContainText(labels[key]);
  }
  assert.deepEqual(await reference.locator('kbd').allTextContents(), ['Shift+F10', 'Enter', 'Esc']);
  const body = page.locator('#reader-settings .reader-settings-body');
  if (height === 480) {
    const openingBounds = await page.evaluate(async () => {
      const bounds = await window.__settingsOpeningFrame;
      delete window.__settingsOpeningFrame;
      return bounds;
    });
    assert.ok(openingBounds.x >= 0 && openingBounds.right <= width && openingBounds.y >= 0 && openingBounds.bottom <= height,
      `The settings popover fits its first visible frame after a closed resize: ${JSON.stringify({locale, width, height, openingBounds})}`);
  }
  const bounds = await body.boundingBox();
  assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= width && bounds.y >= 0 && bounds.y + bounds.height <= height,
    `The settings popover remains bounded at desktop, narrow and short heights: ${JSON.stringify({locale, width, height, bounds})}`);
  for (const row of await reference.locator('strong, kbd, dd').all()) {
    await row.scrollIntoViewIfNeeded();
    const box = await row.boundingBox();
    assert.ok(box.x >= bounds.x && box.x + box.width <= bounds.x + bounds.width + 1 &&
      box.y >= bounds.y - 1 && box.y + box.height <= bounds.y + bounds.height + 1,
    'Every localized shortcut row remains reachable through the settings scrollport');
  }
  await page.screenshot({path: path.join(artifacts, `${locale}-${width}-${height}-shortcuts.png`)});
  await page.locator('#reader-settings > summary').focus();
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('#reader-settings').evaluate(node => node.open), false);
}

async function settingsGeometry(page, locale, width) {
  const analysis = page.locator('#manuscript-analysis-toggle');
  const wasEnabled = await analysis.getAttribute('aria-pressed') === 'true';
  if (await analysis.getAttribute('aria-pressed') !== 'true') await analysis.click();
  try {
    for (const height of [480, 900]) {
      await page.setViewportSize({width, height}); await settle(page);
      for (const id of ['reader-settings']) {
        await page.setViewportSize({width, height}); await settle(page);
        const settings = page.locator('#' + id), summary = settings.locator(':scope > summary');
        const closedArrow = await summary.evaluate(node => getComputedStyle(node, '::after').transform);
        await summary.click(); await settle(page);
        const body = settings.locator('.reader-settings-body');
        const geometry = await settings.evaluate(node => {
          const trigger = node.querySelector('summary').getBoundingClientRect();
          const panel = node.querySelector('.reader-settings-body').getBoundingClientRect();
          return {trigger: trigger.toJSON(), panel: panel.toJSON(),
            arrow: getComputedStyle(node.querySelector('summary'), '::after').content,
            transform: getComputedStyle(node.querySelector('summary'), '::after').transform,
            overflow: node.querySelector('.reader-settings-body').scrollWidth > node.querySelector('.reader-settings-body').clientWidth};
        });
        const {trigger, panel} = geometry;
        assert.ok(panel.bottom <= trigger.top || panel.top >= trigger.bottom,
          `A reading dropdown leaves its own close trigger exposed: ${JSON.stringify({locale, width, height, id, geometry})}`);
        assert.ok(panel.left >= 8 && panel.right <= width - 8 && panel.top >= 8 && panel.bottom <= height - 8,
          'An anchored reading dropdown remains inside the viewport gutter');
        assert.notEqual(geometry.arrow, 'none', 'Every reading dropdown has a visible disclosure affordance');
        assert.notEqual(geometry.transform, closedArrow, 'The disclosure affordance shows its open state');
        assert.equal(geometry.overflow, false, 'Localized controls wrap inside the anchored panel');
        assert.equal(await page.locator('.reader-settings[open]').count(), 1);
        await page.screenshot({path: path.join(artifacts, `${locale}-${width}-${height}-${id}.png`)});
        if (height === 900) {
          await page.setViewportSize({width, height: 480}); await settle(page);
          const resized = await settings.evaluate(node => ({
            trigger: node.querySelector('summary').getBoundingClientRect().toJSON(),
            panel: node.querySelector('.reader-settings-body').getBoundingClientRect().toJSON(),
          }));
          assert.ok(resized.panel.bottom <= resized.trigger.top || resized.panel.top >= resized.trigger.bottom,
            'An open reading dropdown keeps its trigger exposed after the viewport becomes short');
          assert.ok(resized.panel.top >= 8 && resized.panel.bottom <= 472,
            'An open reading dropdown recalculates its available scroll height after resize');
        }
        await summary.click();
        assert.equal(await settings.evaluate(node => node.open), false, 'The same visible trigger closes its dropdown');
        await expect(body).toBeHidden();
      }
      const group = page.locator('#reader-analysis-settings');
      assert.equal(await group.getAttribute('role'), 'group', 'Analysis settings are direct controls, not another popup');
      assert.equal(await group.locator('summary').count(), 0);
      for (const selector of ['#style-layer', '#analysis-evidence-enabled', '#analysis-comparison-enabled']) {
        const control = page.locator(selector);
        await expect(control).toBeVisible();
        const geometry = await control.evaluate(node => {
          const bounds = (node.closest('label') || node).getBoundingClientRect();
          return {left:bounds.left, right:bounds.right, scroll:node.scrollWidth, client:node.clientWidth};
        });
        assert.ok(geometry.left >= 0 && geometry.right <= width,
          `Direct localized analysis controls stay inside the viewport: ${JSON.stringify({locale, width, height, selector, geometry})}`);
        if (selector !== '#style-layer') {
          const checked = await control.isChecked();
          await control.focus(); await page.keyboard.press('Space');
          assert.equal(await control.isChecked(), !checked, 'Keyboard toggles the independently selected analysis decoration');
          await expect(control).toBeFocused();
          await page.keyboard.press('Space');
          assert.equal(await control.isChecked(), checked);
        }
      }
    }
  } finally {
    const open = page.locator('.reader-settings[open] > summary');
    if (await open.count()) {await open.focus(); await page.keyboard.press('Escape');}
    if (!wasEnabled && await analysis.getAttribute('aria-pressed') === 'true') await analysis.click();
  }
}

async function enlargedSettings(page, locale) {
  await page.setViewportSize({width: 1440, height: 900});
  await page.evaluate(() => scrollTo(0, 0)); await settle(page);
  const summary = page.locator('#reader-settings > summary');
  try {
    await summary.click();
    await page.setViewportSize({width: 390, height: 480}); await settle(page);
    await page.evaluate(() => {document.documentElement.style.fontSize = '200%';});
    await page.setViewportSize({width: 320, height: 480}); await settle(page);
    const body = page.locator('#reader-settings .reader-settings-body');
    const box = await body.boundingBox();
    assert.ok(box && box.x >= 0 && box.x + box.width <= 320 && box.y >= 0 && box.y + box.height <= 480,
      `An enlarged reading popup stays bounded when resizing puts its anchor outside the viewport: ${JSON.stringify({locale, box})}`);
    await page.locator('#reader-spacing').scrollIntoViewIfNeeded();
    const field = await page.locator('#reader-spacing').boundingBox();
    assert.ok(field.y >= box.y && field.y + field.height <= box.y + box.height,
      'The final enlarged reading setting remains reachable inside the popup');
    await page.screenshot({path: path.join(artifacts, `${locale}-320-480-settings-enlarged.png`)});
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#reader-settings').evaluate(node => node.open), false);
  } finally {
    await page.evaluate(() => {document.documentElement.style.fontSize = '';});
    if (await page.locator('#reader-settings').evaluate(node => node.open)) {
      await summary.focus(); await page.keyboard.press('Escape');
    }
  }
}

async function nativeControls(page, width, labels) {
  const activate = locator => width === 320 ? locator.tap() : locator.click();
  const analysis = page.locator('#manuscript-analysis-toggle');
  await activate(analysis); await settle(page);
  assert.equal(await analysis.getAttribute('aria-pressed'), 'true', 'A direct activation still switches analysis');
  await activate(analysis); await settle(page);
  assert.equal(await analysis.getAttribute('aria-pressed'), 'false');
  await activate(page.locator('#workbench-overview-open')); await settle(page);
  await expect(page.locator('#manuscript-analysis-panels')).toBeVisible();
  await activate(page.locator('#workbench-overview-back')); await settle(page);
  await expect(page.locator('#chapters')).toBeVisible();
  const focus = page.locator('#reader-focus');
  await activate(focus); await settle(page);
  assert.equal(await focus.getAttribute('aria-pressed'), 'true');
  await expect(page.locator('#lixity-tooltip')).toHaveAttribute('aria-hidden', 'true');
  await page.keyboard.press('Escape'); await settle(page);
  assert.equal(await focus.getAttribute('aria-pressed'), 'false',
    'One Escape exits focus after activating its button, without an obsolete action hint taking priority');
  if (width === 320) await page.evaluate(() => {
    // Keep the existing touch window open even on a busy host. Native input,
    // frames and timers remain real; restore the original clock in finally.
    window.contextualHelpDateNow = Date.now;
    const now = Date.now(); Date.now = () => now;
  });
  try {
    await activate(page.locator('#workspace-reader-toggle')); await settle(page);
    await expect(page.locator('#workspace-reader-panel')).toBeVisible();
    await activate(page.locator('#workspace-reader-close')); await settle(page);
    await expect(page.locator('#workspace-reader-panel')).toBeHidden();
    await expect(page.locator('#workspace-reader-toggle')).toBeFocused();
    if (width === 320) {
      const tip = page.locator('#lixity-tooltip');
      assert.equal(await page.locator('#workspace-reader-toggle').evaluate(node => node.matches(':focus-visible')), false);
      await expect(tip, 'Touch Close retains focus without reopening incidental action help').toHaveAttribute('aria-hidden', 'true');
      await page.keyboard.press('Shift+Tab');
      const overview = page.locator('#workbench-overview-open');
      await expect(overview).toBeFocused();
      assert.equal(await overview.evaluate(node => node.matches(':focus-visible')), true);
      await expect(tip).toHaveAttribute('aria-hidden', 'false');
      await expect(tip).toHaveText(labels.reading_help_overview);
      await expect(overview).toHaveAccessibleDescription(labels.reading_help_overview);
      await page.keyboard.press('Escape');
      await expect(tip).toHaveAttribute('aria-hidden', 'true');
    }
  } finally {
    if (width === 320) await page.evaluate(() => {
      Date.now = window.contextualHelpDateNow;
      delete window.contextualHelpDateNow;
    });
  }
  const paragraph = page.locator('#chapters [data-reader-paragraph]').first();
  await activate(paragraph);
  await expect(page.locator('#manuscript-context-menu')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#manuscript-context-menu')).toBeHidden();
}

(async () => {
  const browser = await launchChromium(), failures = [];
  async function check(name, operation) {
    try { await operation(); }
    catch (error) { failures.push(new Error(name + ': ' + error.message, {cause: error})); }
  }
  try {
    if (!settingsOnly) await touchAfterHoverDeparture(browser);
    for (const [locale, fixture] of touchOnly ? [] : Object.entries(fixtures)) for (const width of [1440, 320]) {
      const state = await createPage(browser, fixture, width), {page} = state;
      try {
        if (settingsOnly) {
          await settingsGeometry(page, locale, width);
          if (width === 320) await enlargedSettings(page, locale);
          assert.deepEqual(state.errors, []); assert.deepEqual(state.writes, []);
          assert.deepEqual(await manuscript(page), state.source);
          continue;
        }
        await check(`${locale} ${width} contextual help`, () => helpControls(page, fixture.labels, locale, width));
        await hoverIntent(page);
        await check(`${locale} ${width} adjacent toolbar actions`, () => adjacentToolbarActions(page, locale, width));
        await check(`${locale} ${width} keyboard actions`, () => keyboardActions(page));
        await check(`${locale} ${width} keyboard reference`, () => shortcutReference(page, fixture.labels, locale, width));
        await check(`${locale} ${width} native controls`, () => nativeControls(page, width, fixture.labels));
        if (width === 320) {
          await page.setViewportSize({width, height: 480}); await settle(page);
          await check(`${locale} ${width} short keyboard reference`, () => shortcutReference(page, fixture.labels, locale, width, 480));
        }
        await settingsGeometry(page, locale, width);
        if (width === 320) await enlargedSettings(page, locale);
        assert.deepEqual(state.errors, []); assert.deepEqual(state.writes, []);
        assert.deepEqual(await manuscript(page), state.source);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      } finally { await page.close(); }
    }
    if (failures.length) throw new AggregateError(failures, 'Contextual help regressions');
    console.log((touchOnly
      ? 'Contextual touch help: native rapid hover departures, explicit touch continuity, second-tap dismissal and mouse/keyboard transitions passed. Screenshots: '
      : settingsOnly
      ? 'Reading dropdowns: seven desktop/mobile locales, short viewport, anchored internal scrolling, open resize, disclosure state, native close and unchanged source passed. Screenshots: '
      : 'Contextual help: seven localized desktop/mobile control descriptions, focus/hover/Escape, anchored dropdowns and bounded shortcuts, actual passage/search keys, native click/tap and unchanged source passed. Screenshots: ') + artifacts);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
