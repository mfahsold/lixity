const {test} = require('node:test');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const {startNativeServer} = require('./native-server.cjs');

const artifactDir = '/tmp';

test('a ready fixture can close after its process already exited', {timeout: 2000}, async () => {
  const server = await startNativeServer('import json, os; print(json.dumps({"pid": os.getpid()}), flush=True)', artifactDir);
  while (true) {
    try { process.kill(server.fixture.pid, 0); }
    catch (error) { assert.equal(error.code, 'ESRCH'); break; }
    await new Promise(resolve => setTimeout(resolve, 5));
  }
  await new Promise(resolve => setImmediate(resolve));
  await server.close();
  await server.close();
});

for (const [name, source, diagnostic] of [
  ['startup traceback', 'raise RuntimeError("Synthetic startup failure")', /exited.*1[\s\S]*Synthetic startup failure/],
  ['malformed JSON', 'import time; print("invalid JSON", flush=True); time.sleep(60)', /Invalid synthetic server fixture JSON/],
  ['startup timeout', 'import time; time.sleep(60)', /startup timed out/],
]) test(`${name} makes a standalone suite exit nonzero`, () => {
  const result = spawnSync(process.execPath, ['-e', `
    const {startNativeServer} = require(${JSON.stringify(require.resolve('./native-server.cjs'))});
    startNativeServer(${JSON.stringify(source)}, '/tmp', {startupTimeoutMs: ${name === 'startup timeout' ? 100 : 1000}})
      .then(server => server.close())
      .catch(error => { console.error(error); process.exitCode = 1; });
  `], {encoding: 'utf8', timeout: 5000});
  assert.equal(result.error, undefined);
  assert.equal(result.status, 1, 'An unresolved fixture must not silently exit with success');
  assert.match(result.stderr, diagnostic);
});

test('a missing Python executable fails instead of leaving readiness unresolved', {timeout: 2000}, async () => {
  await assert.rejects(startNativeServer('', artifactDir,
    {python: '/missing/lixity-browser-test-python'}), /ENOENT/);
});

test('cleanup stops a server that ignores SIGTERM', {timeout: 2000}, async () => {
  const server = await startNativeServer(`
import json, os, signal, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
print(json.dumps({"pid": os.getpid()}), flush=True)
while True: time.sleep(60)
`, artifactDir, {shutdownTimeoutMs: 100});
  await Promise.all([server.close(), server.close()]);
  assert.throws(() => process.kill(server.fixture.pid, 0), {code: 'ESRCH'});
});
