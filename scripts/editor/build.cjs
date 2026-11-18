const {createHash} = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const esbuild = require('esbuild');
const {packages} = require('./package-lock.json');

const vendor = path.resolve(__dirname, '../../src/lixity/ui/assets/vendor');
const outfile = path.join(vendor, 'codemirror-editor.js');
const result = esbuild.buildSync({
  absWorkingDir: __dirname,
  entryPoints: ['editor.js'],
  bundle: true,
  minify: true,
  format: 'iife',
  globalName: 'LixityCodeMirror',
  outfile,
  legalComments: 'linked',
  metafile: true,
  write: false,
});
if (result.outputFiles.length !== 1) {
  throw new Error('Review the additional esbuild outputs and retain any new legal notices.');
}
const [bundle] = result.outputFiles;
const [output] = Object.values(result.metafile.outputs);
const packagePaths = Object.keys(packages).filter(directory => directory.startsWith('node_modules/'));
const mostSpecificPaths = [...packagePaths].sort((left, right) => right.length - left.length);
const shipped = new Set();
for (const [filename, input] of Object.entries(output.inputs)) {
  if (!input.bytesInOutput || !filename.startsWith('node_modules/')) continue;
  const directory = mostSpecificPaths.find(candidate => filename.startsWith(`${candidate}/`));
  if (!directory || packages[directory].dev) {
    throw new Error(`Bundled input is missing from the production lock: ${filename}`);
  }
  shipped.add(directory);
}
const inventory = {
  sha256: createHash('sha256').update(bundle.contents).digest('hex'),
  packages: Object.fromEntries([...shipped].sort().map(directory => [directory, packages[directory].version])),
};

// Preserve notices for the complete locked production tree, including unused exports.
const notices = [];
for (const directory of packagePaths) {
  const entry = packages[directory];
  if (entry.dev) continue;
  const license = ['LICENSE', 'LICENSE.md', 'LICENSE.txt']
    .map(filename => path.join(__dirname, directory, filename))
    .find(filename => fs.existsSync(filename));
  if (!license) throw new Error(`Missing license for ${directory}`);
  notices.push(`${directory.replace('node_modules/', '')} ${entry.version}\n${fs.readFileSync(license, 'utf8')}`);
}
const files = [
  [outfile, Buffer.from(bundle.contents)],
  [path.join(vendor, 'codemirror.LICENSE'), Buffer.from(notices.join('\n\n---\n\n'))],
  [path.join(__dirname, 'bundle-inputs.json'), Buffer.from(`${JSON.stringify(inventory, null, 2)}\n`)],
];
if (process.argv.includes('--check')) {
  const stale = files.filter(([filename, contents]) =>
    !fs.existsSync(filename) || !fs.readFileSync(filename).equals(contents));
  if (stale.length) {
    console.error(`Stale editor artifacts: ${stale.map(([filename]) => path.basename(filename)).join(', ')}`);
    console.error('Run npm ci --ignore-scripts and npm run build in scripts/editor.');
    process.exitCode = 1;
  }
} else {
  for (const [filename, contents] of files) fs.writeFileSync(filename, contents);
}
