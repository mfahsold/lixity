// Shared startup for optional browser tests and documentation captures.
//
// Explicit environment overrides (PLAYWRIGHT_MODULE,
// PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH) take precedence; otherwise common
// local locations are probed so `make browser` and `make screenshots` work
// without manually exporting paths.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

function resolvePlaywright() {
  if (process.env.PLAYWRIGHT_MODULE) return process.env.PLAYWRIGHT_MODULE;
  try {
    // Consumers load both the package and its `test` submodule; return the
    // package directory, not the resolved main file (`index.js`).
    return path.dirname(require.resolve('playwright/package.json'));
  } catch {}
  const home = os.homedir();
  const candidates = [
    path.resolve(__dirname, '../node_modules/playwright'),
    path.join(home, 'node_modules/playwright'),
    path.join(home, 'rosts_services/node_modules/playwright'),
  ];
  return candidates.find(candidate => fs.existsSync(candidate)) || 'playwright';
}

function resolveChromium() {
  if (process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH) return process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
  const cache = path.join(os.homedir(), '.cache', 'ms-playwright');
  if (fs.existsSync(cache)) {
    const builds = fs.readdirSync(cache).filter(entry => entry.startsWith('chromium-')).sort().reverse();
    for (const build of builds) {
      for (const sub of ['chrome-linux-arm64/chrome', 'chrome-linux64/chrome', 'chrome-linux/chrome']) {
        const candidate = path.join(cache, build, sub);
        if (fs.existsSync(candidate)) return candidate;
      }
    }
  }
  return ['/usr/bin/chromium-browser', '/usr/bin/chromium'].find(file => fs.existsSync(file));
}

const playwrightModule = resolvePlaywright();
const {chromium} = require(playwrightModule);

function launchChromium() {
  const executablePath = resolveChromium();
  return chromium.launch({headless: true, ...(executablePath ? {executablePath} : {})});
}

module.exports = {launchChromium, playwrightModule};
