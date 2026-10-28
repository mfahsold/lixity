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
