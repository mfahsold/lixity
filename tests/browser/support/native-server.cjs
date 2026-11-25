// Disposable Python fixtures share readiness and cleanup, not project setup.
const {spawn} = require('node:child_process');
const {createInterface} = require('node:readline');
const path = require('node:path');

const root = path.resolve(__dirname, '../../..');

function deadline(promise, milliseconds, message) {
  let timer;
  return Promise.race([promise, new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(message())), milliseconds);
  })]).finally(() => clearTimeout(timer));
}

async function startNativeServer(source, artifactDir, {
  python = process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'),
  startupTimeoutMs = 15000,
  shutdownTimeoutMs = 3000,
} = {}) {
  const keepDiagnostics = process.env.LIXITY_TEST_AUDIO_DIAGNOSTICS === '1';
  const child = spawn(python, ['-u', '-c', source, artifactDir], {
    cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src'),
      ...(keepDiagnostics ? {LIXITY_LOG_FORMAT: 'json'} : {})},
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const lines = createInterface({input: child.stdout});
  let stderr = '', closing;
  child.stderr.on('data', data => { stderr = (stderr + data).slice(-8000); });
  const stderrLines = keepDiagnostics ? createInterface({input: child.stderr}) : null;
  stderrLines?.on('line', line => {
    let record;
    try { record = JSON.parse(line); } catch { return; }
    // Forward only the structured audio HTTP envelope to the bounded suite log.
    if (record?.event !== 'audio_operation' || record.logger !== 'lixity.server' ||
        typeof record.id !== 'string' || !/^[0-9a-f]{16}$/.test(record.id) ||
        typeof record.route !== 'string' || !/^(audio|speech)-[a-z-]{1,40}$/.test(record.route) ||
        !Number.isInteger(record.status) || record.status < 100 || record.status > 599 ||
        !Number.isSafeInteger(record.duration_ms) || record.duration_ms < 0) return;
    const {event, id, route, status, duration_ms} = record;
    const operation = typeof record.operation === 'string' && /^[a-z_]{1,24}$/.test(record.operation)
      ? record.operation : undefined;
    console.error(JSON.stringify({event, id, route, operation, status, duration_ms}));
  });
  // Subscribe before readiness: a fixture may already have exited by cleanup.
  const closed = new Promise(resolve => { child.once('close', resolve); });
  const ready = new Promise((resolve, reject) => {
    lines.once('line', line => {
      try { resolve(JSON.parse(line)); }
      catch (error) { reject(new Error('Invalid synthetic server fixture JSON', {cause: error})); }
    });
    child.on('error', reject);
    child.once('close', (code, signal) => {
      reject(new Error(`Synthetic server exited ${code ?? signal} before readiness: ${stderr}`));
    });
  });

  function close() {
    if (closing) return closing;
    closing = (async () => {
      try {
        if (child.pid && child.exitCode === null && child.signalCode === null) child.kill('SIGTERM');
        try {
          await deadline(closed, shutdownTimeoutMs, () => 'Synthetic server shutdown timed out');
        } catch {
          child.kill('SIGKILL');
          await deadline(closed, shutdownTimeoutMs, () => 'Synthetic server failed to stop after SIGKILL');
        }
      } finally {
        lines.close();
        stderrLines?.close();
      }
    })();
    return closing;
  }

  try {
    const fixture = await deadline(ready, startupTimeoutMs, () => `Synthetic server startup timed out: ${stderr}`);
    return {fixture, close, stderr: () => stderr};
  } catch (error) {
    await close();
    throw error;
  }
}

module.exports = {startNativeServer};
