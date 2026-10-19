// Complete synthetic dashboards cross the Python/Node boundary as JSON.
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const {spawnSync} = require('node:child_process');

function pythonFixture(source, options = {}) {
  const root = options.root || path.resolve(__dirname, '../../..');
  const python = options.python || process.env.PYTHON_BIN || path.join(root, '.venv/bin/python');
  const directory = fs.mkdtempSync(path.join(options.temporaryRoot || os.tmpdir(), 'lixity-python-fixture-'));
  const output = path.join(directory, 'fixture.json');
  let descriptor;
  try {
    descriptor = fs.openSync(output, 'w');
    // Complete multilingual dashboards grow with bundled assets. A file-backed
    // stdout preserves their exact bytes without a fixed subprocess pipe limit.
    const result = spawnSync(python, ['-c', source], {
      cwd: root,
      env: {...process.env, PYTHONPATH: [path.join(root, 'src'), path.join(root, 'tests')].join(path.delimiter)},
      stdio: ['ignore', descriptor, 'pipe'], encoding: 'utf8',
    });
    if (result.error) throw result.error;
    if (result.status !== 0) throw new Error(`Synthetic Python fixture exited ${result.status}: ${result.stderr}`);
    return JSON.parse(fs.readFileSync(output, 'utf8'));
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
    fs.rmSync(directory, {recursive: true, force: true});
  }
}

module.exports = {pythonFixture};
