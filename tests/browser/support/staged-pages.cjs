// Use the production Pages allowlist and keep staged files outside screenshot folders.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');

const repository = path.resolve(__dirname, '../../..');

function stagePages({baseUrl} = {}) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-staged-pages-'));
  const output = path.join(directory, 'site');
  process.once('exit', () => fs.rmSync(directory, {recursive: true, force: true}));
  const python = process.env.PYTHON_BIN || path.join(repository, '.venv/bin/python');
  const args = ['scripts/stage_pages.py', '--output', output];
  if (baseUrl) args.push('--base-url', baseUrl);
  const result = spawnSync(python, args, {cwd: repository, encoding: 'utf8'});
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`Pages staging exited ${result.status ?? result.signal}: ${result.stderr}`);
  return output;
}

module.exports = {stagePages};
