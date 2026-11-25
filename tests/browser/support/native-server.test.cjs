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

test('opt-in fixture diagnostics retain the redacted production audio response record', () => {
  const fixture = `
import json, sys
from http.server import ThreadingHTTPServer
from lixity.log import get_logger, log_event
from lixity.server import LixityServerHandler
log_event(get_logger("server"), "different_event", message="PRIVATE_UNRELATED")
print("PRIVATE_ARBITRARY_STDERR", file=sys.stderr, flush=True)
server = ThreadingHTTPServer(("127.0.0.1", 0), LixityServerHandler)
print(json.dumps({"url": f"http://127.0.0.1:{server.server_port}"}), flush=True)
server.serve_forever()
`;
  const result = spawnSync(process.execPath, ['-e', `
    const {startNativeServer} = require(${JSON.stringify(require.resolve('./native-server.cjs'))});
    (async () => {
      const server = await startNativeServer(${JSON.stringify(fixture)}, '/tmp');
      try {
        const response = await fetch(server.fixture.url + '/api/audio-microphone?token=PRIVATE_QUERY', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({action: 'save_reference', project_token: 'PRIVATE_PAYLOAD'}),
        });
        console.log(JSON.stringify({id: response.headers.get('X-Lixity-Diagnostic-Id'), status: response.status}));
      } finally { await server.close(); }
    })().catch(error => { console.error(error); process.exitCode = 1; });
  `], {
    env: {...process.env, LIXITY_TEST_AUDIO_DIAGNOSTICS: '1', LIXITY_LOG_LEVEL: 'INFO'},
    encoding: 'utf8', timeout: 5000,
  });
  assert.equal(result.error, undefined);
  assert.equal(result.status, 0, result.stderr);
  const response = JSON.parse(result.stdout);
  const logged = JSON.parse(result.stderr);
  assert.match(response.id, /^[0-9a-f]{16}$/);
  assert.equal(response.status, 400);
  assert.ok(Number.isInteger(logged.duration_ms) && logged.duration_ms >= 0);
  assert.deepEqual(logged, {
    event: 'audio_operation', id: response.id, route: 'audio-microphone', operation: 'save_reference',
    status: response.status, duration_ms: logged.duration_ms,
  });
});
