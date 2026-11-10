// Keep shipped third-party notices aligned with the pinned production dependency tree.
const fs = require('node:fs');
const path = require('node:path');
const lock = require('./package-lock.json');
const notices = [];
for (const [directory, entry] of Object.entries(lock.packages)) {
  if (!directory || entry.dev) continue;
  const filename = ['LICENSE', 'LICENSE.md', 'LICENSE.txt'].find(name => fs.existsSync(path.join(directory, name)));
  if (!filename) throw new Error('Missing license for ' + directory);
  notices.push(directory.replace('node_modules/', '') + ' ' + entry.version + '\n' + fs.readFileSync(path.join(directory, filename), 'utf8'));
}
fs.writeFileSync('../../src/lixity/ui/assets/vendor/codemirror.LICENSE', notices.join('\n\n---\n\n'));
