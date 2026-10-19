const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {pythonFixture} = require('./python-fixture.cjs');

test('large fixture JSON preserves complete HTML beyond the subprocess pipe budget', () => {
  const size = 2 * 1024 * 1024;
  const result = pythonFixture(`import json; print(json.dumps({'html': 'x' * ${size} + '\\n</script>😀', 'locales': ['en', 'de']}))`);
  assert.equal(result.html, 'x'.repeat(size) + '\n</script>😀');
  assert.deepEqual(result.locales, ['en', 'de']);
});

test('successful and failed fixture generation cleans disposable transport files', () => {
  const temporaryRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-python-fixture-test-'));
  try {
    assert.deepEqual(pythonFixture('print("{\\"ready\\":true}")', {temporaryRoot}), {ready: true});
    for (const [source, diagnostic, options] of [
      ['raise RuntimeError("Synthetic fixture failure")', /Synthetic fixture failure/, {}],
      ['print("invalid JSON")', /JSON/, {}],
      ['', /ENOENT/, {python: '/missing/lixity-browser-test-python'}],
    ]) {
      assert.throws(() => pythonFixture(source, {temporaryRoot, ...options}), diagnostic);
      assert.deepEqual(fs.readdirSync(temporaryRoot), []);
    }
  } finally { fs.rmSync(temporaryRoot, {recursive: true, force: true}); }
});
