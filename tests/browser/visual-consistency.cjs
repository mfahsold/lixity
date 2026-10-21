const {openProjectActions} = require('./support/project-actions.cjs');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
// Shared visual roles and interaction states; synthetic data only.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const {pythonFixture} = require('./support/python-fixture.cjs');
const root = path.resolve(__dirname, '../..');
const fixtures = pythonFixture(`import json
from lixity.ui import render_dashboard
from dashboard_fixtures import full_dashboard
print(json.dumps({"analysis": full_dashboard(),
    "report": render_dashboard([], [], title="Synthetic exported report"),
    "identity": render_dashboard([], [], controls=True, title="Synthetic project",
        project_author="Synthetic Writer", author_setting_enabled=True,
        identity_check={"title":{"status":"matched","value":"Synthetic project","source":"metadata:title"},
            "author_name":{"status":"mismatch","value":"Another Writer","source":"metadata:author"}})}))`, {root});
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-visual-consistency-'));
const siteRoot = path.join(artifacts, 'site');
const staged = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'),
  ['scripts/stage_pages.py', '--output', siteRoot], {cwd: root, encoding: 'utf8'});
assert.equal(staged.status, 0, staged.stderr);
const contrast = (first, second) => {
  const luminance = value => value.match(/[\d.]+/g).slice(0, 3).map(Number).map(v => v / 255)
    .map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4)
    .reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
  const a = luminance(first), b = luminance(second);
  return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
};
const textRole = locator => locator.evaluate(element => {
  const css = getComputedStyle(element);
  return {family: css.fontFamily, size: css.fontSize, weight: css.fontWeight,
    lineHeight: css.lineHeight, color: css.color};
});
async function checkSelectedHover(page, selector, label) {
  const control = page.locator(selector);
  await page.mouse.move(0, 0);
  const colors = () => control.evaluate(element => {
    const color = getComputedStyle(element).color;
    let background = 'rgba(0, 0, 0, 0)';
    for (let node = element; node && background === 'rgba(0, 0, 0, 0)'; node = node.parentElement) {
      background = getComputedStyle(node).backgroundColor;
    }
    return {color, background};
  });
  const normal = await colors();
  await control.hover();
  const hovered = await colors();
  assert.ok(contrast(normal.color, normal.background) >= 4.5,
    `${label} selected contrast: ${JSON.stringify(normal)}`);
  assert.ok(contrast(hovered.color, hovered.background) >= 4.5,
    `${label} selected hover contrast: ${JSON.stringify({normal, hovered})}`);
  assert.equal(hovered.color, normal.color,
    `${label} hovering keeps the selected foreground`);
}
async function checkTypography(page, label) {
  const body = await textRole(page.locator('body'));
  const controlFamilies = await page.locator('button, select, textarea, input.ctl:not(.ctl-code)').evaluateAll(elements =>
    elements.map(element => ({id: element.id || element.className, family: getComputedStyle(element).fontFamily})));
  assert.ok(controlFamilies.length > 0 && controlFamilies.every(control => control.family === body.family),
    `${label} UI control fonts: ${JSON.stringify(controlFamilies.filter(control => control.family !== body.family))}`);
  const settingLabel = await textRole(page.locator('.setting-field label').first());
  const formLabel = await textRole(page.locator('.form-label').first());
  assert.deepEqual(settingLabel, formLabel, `${label} Settings and modal field labels`);
  const settingsTitle = await textRole(page.locator('.settings-form h3'));
  const sectionTitle = await textRole(page.locator('#research-manager .section-heading').first());
  assert.deepEqual(settingsTitle, sectionTitle, `${label} section headings`);
  const fieldHelp = await textRole(page.locator('#set-author-name-help'));
  const sharedHelp = await textRole(page.locator('#research-hint'));
  assert.deepEqual(fieldHelp, sharedHelp, `${label} field and panel helper text`);
  const code = await textRole(page.locator('code').first());
  const passageId = await textRole(page.locator('#r-link-passage-id'));
  assert.equal(passageId.family, code.family, `${label} technical input and code font`);
  assert.notEqual(code.family, body.family, `${label} code keeps its reading role`);
  assert.equal((await textRole(page.locator('.project-header h1'))).family, body.family,
    `${label} project identity uses the interface font`);
}
// The design tokens are the single source for radius and type sizes: every
// control shares one radius, badges and tags are pills, and the sampled text
// roles stay on the published ladder.
async function checkScale(page, label) {
  const ladder = await page.evaluate(() => {
    return Object.fromEntries(['--text-micro', '--text-note', '--text-small', '--text-control',
      '--text-section-title', '--text-body'].map(name => {
      const probe = document.createElement('span');
      probe.style.fontSize = `var(${name})`;
      document.body.appendChild(probe);
      const value = getComputedStyle(probe).fontSize;
      probe.remove();
      return [name, value];
    }));
  });
  assert.equal(ladder['--text-micro'], '13px', `${label} micro step`);
  assert.deepEqual(Object.keys(ladder).length, 6, `${label} ladder`);
  const radii = await page.locator('button.ctl:not(.ctl-link):visible, a.ctl:visible, select.ctl:visible, input.ctl:visible, textarea.ctl:visible, .view-nav-tab:visible, .theme-btn:visible')
    .evaluateAll(elements => Array.from(new Set(elements.map(element => getComputedStyle(element).borderRadius))));
  assert.deepEqual(radii, [await page.evaluate(() => {
    const probe = document.createElement('span');
    probe.style.borderRadius = 'var(--radius-sm)';
    document.body.appendChild(probe);
    const value = getComputedStyle(probe).borderRadius;
    probe.remove();
    return value;
  })], `${label} control radius`);
  const pillNodes = page.locator('.badge:visible, .badge-sm:visible, .research-tag:visible, .version-badge:visible, .research-badge:visible');
  if (await pillNodes.count()) {
    const pills = await pillNodes.evaluateAll(elements => Array.from(new Set(elements.map(element => getComputedStyle(element).borderRadius))));
    assert.deepEqual(pills, ['999px'], `${label} badge and tag radius`);
  }
  const textNodes = page.locator('.ctl-note:visible, .text-note:visible, table:visible, .badge:visible');
  if (await textNodes.count()) {
    const sizes = await textNodes.evaluateAll(elements => Array.from(new Set(elements.map(element => getComputedStyle(element).fontSize))));
    const allowed = Object.values(ladder);
    const strays = sizes.filter(size => !allowed.includes(size));
    assert.deepEqual(strays, [], `${label} text sizes off the token ladder (${JSON.stringify(sizes)})`);
  }
  // One control size per class: the computed minimum height is shared by every
  // default control (and every compact one). Rendered height may grow when a
  // long label wraps on narrow viewports - that is layout, not drift.
  const controlSizes = await page.locator(
    'button.ctl:not(.ctl-sm):not(.ctl-compact):not(.ctl-link):visible, select.ctl:not(.ctl-sm):visible, input.ctl:not(.ctl-sm):visible')
    .evaluateAll(elements => elements.map(element => ({
      id: element.id || element.className, minHeight: getComputedStyle(element).minHeight})));
  if (controlSizes.length) {
    const sizes = Array.from(new Set(controlSizes.map(box => box.minHeight)));
    assert.equal(sizes.length, 1, `${label} default control minimum heights: ${JSON.stringify(controlSizes)}`);
  }
  const compactSizes = await page.locator('.ctl-sm:visible')
    .evaluateAll(elements => elements.map(element => ({
      id: element.id || element.className, minHeight: getComputedStyle(element).minHeight})));
  if (compactSizes.length) {
    const sizes = Array.from(new Set(compactSizes.map(box => box.minHeight)));
    assert.equal(sizes.length, 1, `${label} compact control minimum heights: ${JSON.stringify(compactSizes)}`);
  }
}
(async () => {
  let browser;
  try {
    browser = await launchChromium();
    for (const theme of ['light', 'dark']) for (const hasTouch of [false, true]) {
      const context = await browser.newContext({colorScheme: theme, reducedMotion: 'reduce', hasTouch});
      const errors = [];
      await context.route('http://lixity.test/**', route => {
        const url = new URL(route.request().url());
        if (['/app', '/identity', '/report'].includes(url.pathname)) return route.fulfill({contentType: 'text/html', body: fixtures[url.pathname === '/app' ? 'analysis' : url.pathname.slice(1)]});
        if (url.pathname.startsWith('/api/')) return route.fulfill({json: {ok: true, locked: true, records: []}});
        const relative = url.pathname.replace(/^\/site\//, '') || 'index.html';
        const file = path.resolve(siteRoot, relative);
        assert.ok(file.startsWith(siteRoot + path.sep));
        return route.fulfill({contentType: file.endsWith('.css') ? 'text/css' : file.endsWith('.js') ? 'text/javascript' : file.endsWith('.svg') ? 'image/svg+xml' : file.endsWith('.png') ? 'image/png' : 'text/html', body: fs.readFileSync(file)});
      });
      const app = await context.newPage(), site = await context.newPage(), identity = await context.newPage(), report = await context.newPage();
      for (const page of [app, site, identity, report]) page.on('pageerror', e => errors.push(e.message));
      await report.goto('http://lixity.test/report');
      assert.notEqual((await textRole(report.locator('.project-header h1'))).family,
        (await textRole(report.locator('body'))).family, 'Exported report titles retain their literary font');
      for (const width of [1440, 320]) {
        for (const [page, route] of [[app, 'app'], [site, 'site/']]) {
          await page.setViewportSize({width, height: 1000});
          await page.goto('http://lixity.test/' + route);
          assert.ok((await page.locator('body').innerText()).length > 1000);
        }
        const roles = page => page.evaluate(() => {
          const probe = document.createElement('span');
          document.body.appendChild(probe);
          const colors = ['--bg', '--surface', '--fg', '--accent', '--action-bg', '--action-hover', '--on-action']
            .map(name => { probe.style.color = `var(${name})`; return getComputedStyle(probe).color; });
          probe.remove();
          return colors;
        });
        assert.deepEqual(await roles(app), await roles(site), `palette mismatch: ${theme}`);
        if (!hasTouch) for (const view of ['research', 'analysis', 'project']) {
          await app.locator(`#tab-view-${view}`).click();
          assert.equal(await app.locator(`#tab-view-${view}`).getAttribute('aria-selected'), 'true');
          await checkSelectedHover(app, `#tab-view-${view}`,
            `${view}-${theme}-${width}`);
          if (view === 'research') await app.locator('.view-navigation').screenshot({
            path: path.join(artifacts, `selected-hover-research-${theme}-${width}.png`)});
        }
        await checkTypography(app, `${theme} ${width}px`);
        await checkScale(app, `${theme} ${width}px app`);
        await checkScale(site, `${theme} ${width}px site`);
        await app.locator('#tab-view-analysis').click();
        await checkScale(app, `${theme} ${width}px analysis`);
        await identity.setViewportSize({width, height: 1000});
        await identity.goto('http://lixity.test/identity');
        await identity.locator('#tab-view-project').click();
        assert.deepEqual(await textRole(identity.locator('#project-identity-check dt').first()),
          await textRole(identity.locator('.setting-field label').first()), `${theme} ${width}px identity labels`);
        assert.ok(await identity.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
          `${theme} ${width}px identity overflow`);
        await identity.locator('#settings-identity summary').click();
        await identity.locator('#project-identity-check').screenshot({path: path.join(artifacts, `identity-${theme}-${width}-${hasTouch ? 'touch' : 'mouse'}.png`)});
        await openProjectActions(app);
        await app.locator('#btn-modal-new-project').click();
        const createDialog = app.locator('#modal-project-create');
        assert.ok(await createDialog.isVisible());
        assert.equal(await app.locator('#research-revision-edit-tab').getAttribute('aria-selected'), 'true',
          'Opening project tabs must not reset the separate research revision tabs');
        // Short windows and mobile keyboards must not clip the end of a form.
        await app.setViewportSize({width, height: 480});
        await app.locator('#import-project-options > summary').click();
        const author = app.locator('#import-proj-author');
        await author.focus();
        await author.scrollIntoViewIfNeeded();
        assert.ok(await author.evaluate(element => {
          const box = element.getBoundingClientRect();
          const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
          return hit === element;
        }), `${theme} ${width}px focused dialog field is not clipped`);
        const disabledImport = app.locator('#btn-submit-import-project');
        await disabledImport.scrollIntoViewIfNeeded();
        const disabledStyle = () => disabledImport.evaluate(element => {
          const css = getComputedStyle(element);
          return [css.color, css.backgroundColor, css.borderColor];
        });
        await app.mouse.move(0, 0);
        const disabledBefore = await disabledStyle();
        await disabledImport.hover();
        assert.deepEqual(await disabledStyle(), disabledBefore, 'Disabled actions do not advertise hover activation');
        await app.locator('#import-proj-path').focus();
        await app.keyboard.press('Tab');
        assert.ok(await app.evaluate(() => {
          const focus = document.activeElement, box = focus.getBoundingClientRect();
          return focus.closest('dialog') && box.top >= 0 && box.bottom <= innerHeight;
        }), 'Keyboard focus remains in the visible dialog');
        assert.ok(await createDialog.locator('.modal-close').evaluate(element => {
          const box = element.getBoundingClientRect();
          return document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2) === element;
        }), 'The dialog close action remains reachable after scrolling the form');
        await app.screenshot({path: path.join(artifacts, `modal-short-${theme}-${width}-${hasTouch ? 'touch' : 'mouse'}.png`)});
        await app.setViewportSize({width, height: 1000});
        await app.locator('#tab-btn-scratch').click();
        assert.ok(await app.locator('#tab-pane-scratch').isVisible());
        await app.mouse.move(0, 0);
        const createAction = app.locator('#btn-submit-create-project');
        await createAction.focus();
        await app.keyboard.down('Space');
        try {
          const colors = await createAction.evaluate(element => {
            const css = getComputedStyle(element);
            return [css.color, css.backgroundColor];
          });
          assert.ok(contrast(...colors) >= 4.5, `${theme} primary keyboard-pressed contrast`);
        } finally {
          // Do not submit the form: this checks the held activation state.
          await app.locator('#tab-btn-scratch').focus();
          await app.keyboard.up('Space');
        }
        assert.equal((await textRole(app.locator('#tab-btn-scratch'))).family,
          (await textRole(app.locator('body'))).family, `${theme} ${width}px modal tab font`);
        assert.ok(await createDialog.evaluate(element => element.scrollWidth <= element.clientWidth),
          `${theme} ${width}px modal content overflow`);
        await app.screenshot({path: path.join(artifacts, `modal-${theme}-${width}-${hasTouch ? 'touch' : 'mouse'}.png`)});
        await createDialog.locator('.modal-close').click();
        assert.ok(!(await createDialog.isVisible()));
        assert.equal(await app.evaluate(() => document.activeElement.id), 'btn-modal-new-project',
          'Closing a dialog restores focus to its opener');
        assert.equal(await app.locator('.chip').first().evaluate(el => getComputedStyle(el).transitionDuration), '0s');
        await app.locator('#tab-view-analysis').click();
        await app.locator('#manuscript-analysis-toggle').click();
        const minimum = hasTouch ? 44 : 24;
        const paragraph = app.locator('.chip').first();
        const paragraphTargets = await app.locator('#chapters .chip').evaluateAll(elements => elements.map(element => {
          const box = element.getBoundingClientRect();
          return {width: box.width, height: box.height};
        }));
        assert.ok(paragraphTargets.length > 0 && paragraphTargets.every(box => box.width >= minimum && box.height >= minimum),
          `${theme} paragraph targets: ${JSON.stringify(paragraphTargets)}`);
        await paragraph.focus();
        await app.keyboard.down('Space');
        try {
          const pressed = await paragraph.boundingBox();
          assert.ok(pressed.width >= minimum && pressed.height >= minimum,
            `${theme} pressed paragraph target: ${JSON.stringify(pressed)}`);
        } finally { await app.keyboard.up('Space'); }
        await app.locator('#workbench-overview-open').click();
        await app.locator('#style-tab-dimensions').click();
        const denseTargets = await app.locator('.dim-ctl:visible').evaluateAll(elements => elements.map(element => {
          const box = element.getBoundingClientRect();
          return {width: box.width, height: box.height};
        }));
        assert.ok(denseTargets.length > 0 && denseTargets.every(box => box.width >= minimum && box.height >= minimum),
          `${theme} paragraph and dimension targets: ${JSON.stringify(denseTargets)}`);
        assert.equal(await site.locator('html').evaluate(el => getComputedStyle(el).scrollBehavior), 'auto');
        assert.equal(await site.locator('.ctl').first().evaluate(el => getComputedStyle(el).transitionDuration), '0s');
        const heatmapColors = await app.locator('td.z[style]').evaluateAll(nodes => nodes.map(node => {
          const css = getComputedStyle(node);
          return [css.color, css.backgroundColor];
        }));
        assert.ok(heatmapColors.length > 0);
        heatmapColors.forEach(([text, fill]) => assert.ok(contrast(text, fill) >= 4.5, `${theme} heatmap label contrast`));
        await app.locator('#tab-view-analysis').focus();
        await app.keyboard.press('Enter');
        for (const [page, selector, label] of [[app, 'a.ctl.primary', 'app'], [site, 'a.ctl.primary', 'site']]) {
          const control = page.locator(selector).filter({visible: true}).first();
          await control.focus();
          const style = await control.evaluate(el => {
            const css = getComputedStyle(el);
            return {id: el.id, disabled: el.disabled, focused: document.activeElement === el,
              color: css.color, background: css.backgroundColor, outline: css.outlineStyle,
              height: el.getBoundingClientRect().height, animation: css.animationName,
              coarse: matchMedia('(pointer: coarse)').matches};
          });
          assert.ok(contrast(style.color, style.background) >= 4.5, `${label} primary contrast`);
          assert.ok(style.height >= (style.coarse ? 44 : 40), `${label} target ${JSON.stringify(style)}`);
          assert.notEqual(style.outline, 'none', `${label} keyboard focus: ${JSON.stringify(style)}`);
          assert.equal(style.animation, 'none');
          await page.screenshot({path: path.join(artifacts, `${label}-${theme}-${width}-${hasTouch ? 'touch' : 'mouse'}.png`)});
          await page.addStyleTag({content: '* { line-height: 1.5 !important; letter-spacing: .12em !important; word-spacing: .16em !important; } p { margin-bottom: 2em !important; }'});
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${label} text-spacing overflow at ${width}`);
          assert.ok(await control.isVisible());
        }
        await site.locator('#themeToggle').click();
        assert.equal(await site.locator('html').getAttribute('data-theme'), 'light');
        await site.evaluate(() => localStorage.removeItem('lixity-theme'));
      }
      assert.deepEqual(errors, []);
      await context.close();
    }
    console.log(`Shared typography, identity labels, palette, action contrast, touch targets, focus, text-spacing, reduced motion and theme interaction passed. Screenshots: ${artifacts}`);
  } finally {
    try { if (browser) await browser.close(); }
    finally { fs.rmSync(siteRoot, {recursive: true, force: true}); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
