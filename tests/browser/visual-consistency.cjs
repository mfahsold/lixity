// Shared visual roles and interaction states; synthetic data only.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
let playwrightMod = process.env.PLAYWRIGHT_MODULE || 'playwright';
try { require.resolve(playwrightMod); } catch {
  const fallback = '/home/codeai/.npm/_npx/b234c773f454f454/node_modules/playwright';
  if (fs.existsSync(fallback)) playwrightMod = fallback;
}
const {chromium} = require(playwrightMod);
const root = path.resolve(__dirname, '../..');
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c',
  "import runpy; print(runpy.run_path('tests/test_ui_contract.py')['_full_dashboard']())"],
  {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8'});
assert.equal(fixture.status, 0, fixture.stderr);
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-visual-consistency-'));
const contrast = (first, second) => {
  const luminance = value => value.match(/[\d.]+/g).slice(0, 3).map(Number).map(v => v / 255)
    .map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4)
    .reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
  const a = luminance(first), b = luminance(second);
  return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
};
(async () => {
  const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ||
    (fs.existsSync('/usr/bin/chromium-browser') ? '/usr/bin/chromium-browser' : undefined);
  const browser = await chromium.launch({headless: true, ...(executablePath ? {executablePath} : {})});
  try {
    for (const theme of ['light', 'dark']) for (const hasTouch of [false, true]) {
      const context = await browser.newContext({colorScheme: theme, reducedMotion: 'reduce', hasTouch});
      const errors = [];
      await context.route('http://lixity.test/**', route => {
        const url = new URL(route.request().url());
        if (url.pathname === '/app') return route.fulfill({contentType: 'text/html', body: fixture.stdout});
        if (url.pathname.startsWith('/api/')) return route.fulfill({json: {ok: true, locked: true, records: []}});
        const relative = url.pathname.replace(/^\/site\//, '') || 'index.html';
        const file = path.resolve(root, 'docs', relative);
        assert.ok(file.startsWith(path.join(root, 'docs') + path.sep));
        return route.fulfill({contentType: file.endsWith('.css') ? 'text/css' : file.endsWith('.png') ? 'image/png' : 'text/html', body: fs.readFileSync(file)});
      });
      const app = await context.newPage(), site = await context.newPage();
      for (const page of [app, site]) page.on('pageerror', e => errors.push(e.message));
      for (const width of [1440, 320]) {
        for (const [page, route] of [[app, 'app'], [site, 'site/']]) {
          await page.setViewportSize({width, height: 1000});
          await page.goto('http://lixity.test/' + route);
          assert.ok((await page.locator('body').innerText()).length > 1000);
        }
        const roles = page => page.evaluate(() => {
          const css = getComputedStyle(document.documentElement);
          return ['--bg', '--surface', '--fg', '--accent', '--action-bg', '--action-hover', '--on-action']
            .map(name => css.getPropertyValue(name).trim());
        });
        assert.deepEqual(await roles(app), await roles(site), `palette mismatch: ${theme}`);
        assert.equal(await app.locator('.chip').first().evaluate(el => getComputedStyle(el).transitionDuration), '0s');
        assert.equal(await site.locator('html').evaluate(el => getComputedStyle(el).scrollBehavior), 'auto');
        assert.equal(await site.locator('.btn').first().evaluate(el => getComputedStyle(el).transitionDuration), '0s');
        const heatmapColors = await app.locator('td.z[style]').evaluateAll(nodes => nodes.map(node => {
          const css = getComputedStyle(node);
          return [css.color, css.backgroundColor];
        }));
        assert.ok(heatmapColors.length > 0);
        heatmapColors.forEach(([text, fill]) => assert.ok(contrast(text, fill) >= 4.5, `${theme} heatmap label contrast`));
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
    console.log(`Shared palette, action contrast, touch targets, focus, text-spacing, reduced motion and theme interaction passed. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
