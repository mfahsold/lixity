const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {launchChromium} = require('../../scripts/browser_tools.cjs');

const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-debug-ui-'));
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
import json
from lixity.server import build_server_dashboard
from lixity.research import api
html, _ = build_server_dashboard(None, language="en", title="Synthetic debug regression", debug=True)
print(json.dumps({"html": html, "status": {"ok": True, "initialized": False,
                 "project_root": "/tmp/synthetic-debug-project", "ocr": api.ocr_status()}}))
`], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8', maxBuffer: 8 * 1024 * 1024});
assert.equal(fixture.status, 0, fixture.error ? fixture.error.message : fixture.stderr);
const rendered = JSON.parse(fixture.stdout);

(async () => {
  const browser = await launchChromium();
  const errors = [];
  async function open({saved = null, serverDebug = false, windowDebug = false, blockedStorage = false, width = 1440} = {}) {
    const context = await browser.newContext({viewport: {width, height: 900}});
    await context.addInitScript(({saved, windowDebug, blockedStorage}) => {
      if (saved !== null) localStorage.setItem('lixity_debug', saved);
      window.LIXITY_DEBUG = windowDebug;
      if (blockedStorage) Object.defineProperty(window, 'localStorage', {
        get() { throw new DOMException('Synthetic blocked storage', 'SecurityError'); }
      });
    }, {saved, windowDebug, blockedStorage});
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => {
      if (['error', 'warning'].includes(message.type())) errors.push(message.text());
    });
    const html = serverDebug ? rendered.html : rendered.html.replace('<meta name="lixity-debug" content="true"/>', '');
    await page.route('http://lixity.test/**', route => {
      if (route.request().url().endsWith('/api/research/status')) return route.fulfill({json: rendered.status});
      assert.equal(route.request().url(), 'http://lixity.test/');
      return route.fulfill({contentType: 'text/html', body: html});
    });
    await page.goto('http://lixity.test/');
    assert.equal(page.url(), 'http://lixity.test/');
    assert.ok((await page.title()).includes('Synthetic debug regression'));
    assert.ok(await page.locator('.project-header').isVisible());
    return {context, page};
  }
  try {
    for (const width of [1440, 320]) {
      const {context, page} = await open({serverDebug: true, windowDebug: true, width});
      const diagnostics = [];
      page.on('console', message => diagnostics.push(message.text()));
      assert.equal(await page.evaluate(() => window.LixityLog.isDebug()), true);
      await page.evaluate(() => window.setLixityDebug(false));
      assert.equal(await page.evaluate(() => window.LixityLog.isDebug()), false);
      await page.reload();
      assert.equal(await page.evaluate(() => window.LixityLog.isDebug()), false, `saved false survives reload at ${width}`);
      assert.equal(await page.evaluate(() => localStorage.getItem('lixity_debug')), '0');
      await page.evaluate(() => {
        window.LixityLog.debug('synthetic-disabled-diagnostic');
        window.LixityLog.info('synthetic-disabled-diagnostic');
        window.LixityLog.api('GET', '/synthetic-disabled-diagnostic', 1, 200);
      });
      assert.ok(!diagnostics.some(message => message.includes('synthetic-disabled-diagnostic')));
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({path: path.join(artifacts, `debug-disabled-${width}.png`)});
      await context.close();
    }
    for (const scenario of [
      {saved: '1', expected: true},
      {saved: '0', serverDebug: true, windowDebug: true, expected: false},
      {serverDebug: true, expected: true},
      {windowDebug: true, expected: true},
      {expected: false},
      {saved: 'invalid', serverDebug: true, expected: true},
      {saved: 'true', windowDebug: true, expected: true},
      {saved: '', expected: false},
      {blockedStorage: true, serverDebug: true, expected: true},
      {blockedStorage: true, expected: false},
    ]) {
      const {context, page} = await open(scenario);
      assert.equal(await page.evaluate(() => window.LixityLog.isDebug()), scenario.expected, JSON.stringify(scenario));
      await context.close();
    }
    const {context, page} = await open();
    await page.evaluate(() => window.setLixityDebug(true));
    await page.reload();
    assert.equal(await page.evaluate(() => window.LixityLog.isDebug()), true, 'saved true survives reload without server debug');
    const responseLogs = [];
    page.on('console', message => responseLogs.push(message));
    await page.evaluate(() => window.LixityLog.api('GET', '/api/synthetic-source', 12.5, 200,
      {ok: true, text: 'SYNTHETIC_PRIVATE_RESPONSE', nested: {body: 'SYNTHETIC_PRIVATE_RESPONSE'}}));
    const loggedArguments = await Promise.all(responseLogs.flatMap(message => message.args().map(argument => argument.jsonValue())));
    assert.ok(responseLogs.some(message => message.text().includes('/api/synthetic-source -> 200 (12.5ms)')));
    assert.ok(!JSON.stringify(loggedArguments).includes('SYNTHETIC_PRIVATE_RESPONSE'), 'API diagnostics must not retain response content');
    await context.close();
    const blocked = await open({serverDebug: true, blockedStorage: true});
    await blocked.page.evaluate(() => window.setLixityDebug(false));
    assert.equal(await blocked.page.evaluate(() => window.LixityLog.isDebug()), false, 'unavailable storage still allows an active-page override');
    await blocked.page.reload();
    assert.equal(await blocked.page.evaluate(() => window.LixityLog.isDebug()), true, 'unavailable storage falls back on reload');
    await blocked.context.close();
    assert.deepEqual(errors, []);
    console.log(`Browser debug overrides: reload, fallback and blocked storage passed at 1440/320. Screenshots: ${artifacts}`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
