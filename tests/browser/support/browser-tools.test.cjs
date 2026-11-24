const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');

test('a locally installed Playwright resolves both its main and test entry points', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-playwright-resolver-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const scripts = path.join(root, 'scripts');
  const moduleDir = path.join(root, 'node_modules', 'playwright');
  fs.mkdirSync(scripts, {recursive: true});
  fs.mkdirSync(moduleDir, {recursive: true});
  fs.copyFileSync(path.join(__dirname, '../../../scripts/browser_tools.cjs'), path.join(scripts, 'browser_tools.cjs'));
  fs.writeFileSync(path.join(moduleDir, 'package.json'), JSON.stringify({name: 'playwright', main: 'index.js'}));
  fs.writeFileSync(path.join(moduleDir, 'index.js'), 'exports.chromium = {};');
  fs.writeFileSync(path.join(moduleDir, 'test.js'), 'exports.expect = true;');
  const result = spawnSync(process.execPath, ['-e', `
    const path = require('node:path');
    const {playwrightModule} = require('./scripts/browser_tools.cjs');
    if (!require(path.join(playwrightModule, 'test')).expect) process.exit(1);
  `], {cwd: root, encoding: 'utf8', env: {...process.env, PLAYWRIGHT_MODULE: ''}});
  assert.equal(result.status, 0, result.stderr);
});

test('the configured browser tools directory supplies Playwright and axe together', t => {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-isolated-browser-tools-')));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const tools = path.join(root, 'isolated');
  const packages = path.join(tools, 'node_modules');
  const playwright = path.join(packages, 'playwright');
  const axe = path.join(packages, 'axe-core', 'axe.min.js');
  fs.mkdirSync(playwright, {recursive: true});
  fs.mkdirSync(path.dirname(axe), {recursive: true});
  fs.copyFileSync(path.join(__dirname, '../../../scripts/browser_tools.cjs'), path.join(root, 'browser_tools.cjs'));
  fs.writeFileSync(path.join(playwright, 'index.js'), 'exports.chromium = {launch: options => options};');
  fs.writeFileSync(axe, 'globalThis.syntheticAxe = true;');
  const result = spawnSync(process.execPath, ['-e', `
    const assert = require('node:assert/strict');
    const {playwrightModule, resolveAxe, launchChromium} = require('./browser_tools.cjs');
    assert.equal(playwrightModule, ${JSON.stringify(playwright)});
    assert.equal(resolveAxe(), ${JSON.stringify(axe)});
    assert.equal(launchChromium().channel, 'chromium');
  `], {cwd: root, encoding: 'utf8', env: {...process.env, NODE_PATH: '', PLAYWRIGHT_MODULE: '',
    BROWSER_TOOLS_DIR: tools, PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH: '', PLAYWRIGHT_BROWSERS_PATH: '0'}});
  assert.equal(result.status, 0, result.stderr);
});

test('modShortcut returns portable ControlOrMeta key chords', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-mod-shortcut-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const scripts = path.join(root, 'scripts');
  const moduleDir = path.join(root, 'node_modules', 'playwright');
  fs.mkdirSync(scripts, {recursive: true});
  fs.mkdirSync(moduleDir, {recursive: true});
  fs.copyFileSync(path.join(__dirname, '../../../scripts/browser_tools.cjs'), path.join(scripts, 'browser_tools.cjs'));
  fs.writeFileSync(path.join(moduleDir, 'package.json'), JSON.stringify({name: 'playwright', main: 'index.js'}));
  fs.writeFileSync(path.join(moduleDir, 'index.js'), 'exports.chromium = {};');
  const result = spawnSync(process.execPath, ['-e', `
    const assert = require('node:assert/strict');
    const {modShortcut} = require('./scripts/browser_tools.cjs');
    assert.equal(modShortcut('z'), 'ControlOrMeta+z');
    assert.equal(modShortcut('End'), 'ControlOrMeta+End');
    assert.equal(modShortcut('k'), 'ControlOrMeta+k');
  `], {cwd: root, encoding: 'utf8', env: {...process.env, PLAYWRIGHT_MODULE: ''}});
  assert.equal(result.status, 0, result.stderr);
});
