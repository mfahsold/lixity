const {launchChromium} = require('../../scripts/browser_tools.cjs');
// Shared visual roles and interaction states; synthetic data only.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c',
  `import json, runpy
from lixity.ui import render_dashboard
print(json.dumps({"analysis": runpy.run_path('tests/test_ui_contract.py')['_full_dashboard'](),
    "identity": render_dashboard([], [], controls=True, title="Synthetic project",
        project_author="Synthetic Writer", author_setting_enabled=True,
        identity_check={"title":{"status":"matched","value":"Synthetic project","source":"metadata:title"},
            "author_name":{"status":"mismatch","value":"Another Writer","source":"metadata:author"}})}))`],
  {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8'});
assert.equal(fixture.status, 0, fixture.stderr);
const fixtures = JSON.parse(fixture.stdout);
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-visual-consistency-'));
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
  assert.notEqual((await textRole(page.locator('.project-header h1'))).family, body.family,
    `${label} project title keeps its literary font`);
}
(async () => {
  const browser = await launchChromium();
  try {
    for (const theme of ['light', 'dark']) for (const hasTouch of [false, true]) {
      const context = await browser.newContext({colorScheme: theme, reducedMotion: 'reduce', hasTouch});
      const errors = [];
      await context.route('http://lixity.test/**', route => {
        const url = new URL(route.request().url());
        if (url.pathname === '/app' || url.pathname === '/identity') return route.fulfill({contentType: 'text/html', body: fixtures[url.pathname === '/app' ? 'analysis' : 'identity']});
        if (url.pathname.startsWith('/api/')) return route.fulfill({json: {ok: true, locked: true, records: []}});
        const relative = url.pathname.replace(/^\/site\//, '') || 'index.html';
        const file = path.resolve(root, 'docs', relative);
        assert.ok(file.startsWith(path.join(root, 'docs') + path.sep));
        return route.fulfill({contentType: file.endsWith('.css') ? 'text/css' : file.endsWith('.js') ? 'text/javascript' : file.endsWith('.svg') ? 'image/svg+xml' : file.endsWith('.png') ? 'image/png' : 'text/html', body: fs.readFileSync(file)});
      });
      const app = await context.newPage(), site = await context.newPage(), identity = await context.newPage();
      for (const page of [app, site, identity]) page.on('pageerror', e => errors.push(e.message));
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
        await checkTypography(app, `${theme} ${width}px`);
        await identity.setViewportSize({width, height: 1000});
        await identity.goto('http://lixity.test/identity');
        await identity.locator('#tab-view-project').click();
        assert.deepEqual(await textRole(identity.locator('#project-identity-check dt').first()),
          await textRole(identity.locator('.setting-field label').first()), `${theme} ${width}px identity labels`);
        assert.ok(await identity.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
          `${theme} ${width}px identity overflow`);
        await identity.locator('#project-identity-check').screenshot({path: path.join(artifacts, `identity-${theme}-${width}-${hasTouch ? 'touch' : 'mouse'}.png`)});
        await app.locator('#btn-modal-new-project').click();
        const createDialog = app.locator('#modal-project-create');
        assert.ok(await createDialog.isVisible());
        await app.locator('#tab-btn-scratch').click();
        assert.ok(await app.locator('#tab-pane-scratch').isVisible());
        assert.equal((await textRole(app.locator('#tab-btn-scratch'))).family,
          (await textRole(app.locator('body'))).family, `${theme} ${width}px modal tab font`);
        assert.ok(await createDialog.evaluate(element => element.scrollWidth <= element.clientWidth),
          `${theme} ${width}px modal content overflow`);
        await app.screenshot({path: path.join(artifacts, `modal-${theme}-${width}-${hasTouch ? 'touch' : 'mouse'}.png`)});
        await createDialog.locator('.modal-close').click();
        assert.ok(!(await createDialog.isVisible()));
        assert.equal(await app.locator('.chip').first().evaluate(el => getComputedStyle(el).transitionDuration), '0s');
        await app.locator('#tab-view-analysis').click();
        await app.locator('#style-tab-dimensions').click();
        const minimum = hasTouch ? 44 : 24;
        const denseTargets = await app.locator('.chip, .dim-ctl').evaluateAll(elements => elements.map(element => {
          const box = element.getBoundingClientRect();
          return {width: box.width, height: box.height};
        }));
        assert.ok(denseTargets.length > 0 && denseTargets.every(box => box.width >= minimum && box.height >= minimum),
          `${theme} paragraph and dimension targets: ${JSON.stringify(denseTargets)}`);
        const paragraph = app.locator('.chip').first();
        await paragraph.focus();
        await app.keyboard.down('Space');
        try {
          const pressed = await paragraph.boundingBox();
          assert.ok(pressed.width >= minimum && pressed.height >= minimum,
            `${theme} pressed paragraph target: ${JSON.stringify(pressed)}`);
        } finally { await app.keyboard.up('Space'); }
        assert.equal(await site.locator('html').evaluate(el => getComputedStyle(el).scrollBehavior), 'auto');
        assert.equal(await site.locator('.btn').first().evaluate(el => getComputedStyle(el).transitionDuration), '0s');
        const heatmapColors = await app.locator('td.z[style]').evaluateAll(nodes => nodes.map(node => {
          const css = getComputedStyle(node);
          return [css.color, css.backgroundColor];
        }));
        assert.ok(heatmapColors.length > 0);
        heatmapColors.forEach(([text, fill]) => assert.ok(contrast(text, fill) >= 4.5, `${theme} heatmap label contrast`));
        await app.locator('#tab-view-project').focus();
        await app.keyboard.press('Enter');
        for (const [page, selector, label] of [[app, 'button.ctl.primary', 'app'], [site, '.btn.primary', 'site']]) {
          const control = page.locator(selector).filter({visible: true}).first();
          await control.focus();
          const style = await control.evaluate(el => {
            const css = getComputedStyle(el);
            return {color: css.color, background: css.backgroundColor, outline: css.outlineStyle,
              height: el.getBoundingClientRect().height, animation: css.animationName,
              coarse: matchMedia('(pointer: coarse)').matches};
          });
          assert.ok(contrast(style.color, style.background) >= 4.5, `${label} primary contrast`);
          assert.ok(style.height >= (style.coarse ? 44 : 40), `${label} target ${JSON.stringify(style)}`);
          assert.notEqual(style.outline, 'none', `${label} keyboard focus`);
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
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
