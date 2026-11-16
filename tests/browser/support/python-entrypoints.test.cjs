const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');

test('native browser entry points honor external Python without a repository venv', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-python-entrypoints-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const repository = path.resolve(__dirname, '../../..');
  const suites = ['editor-features.cjs', 'editor-navigation.cjs', 'manuscript-editor.cjs', 'home-tour.cjs'];
  for (const relative of ['scripts/browser_tools.cjs', ...suites.map(name => `tests/browser/${name}`)]) {
    const target = path.join(root, relative);
    fs.mkdirSync(path.dirname(target), {recursive: true});
    fs.copyFileSync(path.join(repository, relative), target);
  }
  const playwright = path.join(root, 'node_modules/playwright');
  fs.mkdirSync(playwright, {recursive: true});
  fs.writeFileSync(path.join(playwright, 'package.json'), JSON.stringify({name: 'playwright', main: 'index.js'}));
  fs.writeFileSync(path.join(playwright, 'index.js'), 'exports.chromium = {}; exports.firefox = {};');
  fs.writeFileSync(path.join(playwright, 'test.js'), 'exports.expect = {};');
  const probe = path.join(root, 'interpreter-probe.cjs');
  // Node is a portable external executable: record only the Python fixture
  // invocation, then fail before the suite can launch a browser.
  fs.writeFileSync(probe, `
    if (process.argv[1] && process.argv[1].endsWith('.py')) {
      require('node:fs').writeFileSync(process.env.LIXITY_PYTHON_PROBE,
        JSON.stringify({executable: process.execPath, arguments: process.argv.slice(1)}));
      process.exit(17);
    }
  `);
  assert.equal(fs.existsSync(path.join(root, '.venv')), false);
  for (const suite of suites) {
    await t.test(suite, () => {
      const marker = path.join(root, `${suite}.json`);
      const env = {...process.env, PYTHON_BIN: process.execPath, PLAYWRIGHT_MODULE: '',
        TMPDIR: root, TMP: root, TEMP: root,
        NODE_OPTIONS: `--require=${JSON.stringify(probe)}`, LIXITY_PYTHON_PROBE: marker};
      const result = spawnSync(process.execPath, [path.join(root, 'tests/browser', suite)], {
        cwd: root, encoding: 'utf8', timeout: 10000, env,
      });
      assert.equal(fs.existsSync(marker), true,
        `${suite} must invoke the explicit interpreter outside .venv: ${result.stderr}`);
      const invocation = JSON.parse(fs.readFileSync(marker, 'utf8'));
      assert.equal(invocation.executable, process.execPath);
      assert.match(invocation.arguments[0], /(?:editor-server|stage_pages)\.py$/);
      assert.equal(result.status, 1, `${suite} must report the synthetic fixture failure`);
      const missingPython = path.join(root, 'missing-python');
      const failed = spawnSync(process.execPath, [path.join(root, 'tests/browser', suite)], {
        cwd: root, encoding: 'utf8', timeout: 10000, env: {...env, PYTHON_BIN: missingPython},
      });
      assert.equal(failed.status, 1);
      assert.match(failed.stderr, /ENOENT/);
      assert.ok(failed.stderr.includes(missingPython), 'Invalid overrides must fail explicitly');
    });
  }
});
