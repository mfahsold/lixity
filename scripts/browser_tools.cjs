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
    path.join(home, '.local/share/lixity/browser-tools/node_modules/playwright'),
    path.join(home, 'node_modules/playwright'),
    path.join(home, 'rosts_services/node_modules/playwright'),
  ];
  return candidates.find(candidate => fs.existsSync(candidate)) || 'playwright';
}

function resolveChromium() {
  if (process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH) return process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
  const home = os.homedir();
  const caches = [
    path.join(home, '.local/share/lixity/browser-tools/browsers'),
    path.join(home, '.cache', 'ms-playwright'),
  ];
  for (const cache of caches) {
    if (!fs.existsSync(cache)) continue;
    const builds = fs.readdirSync(cache).filter(entry => entry.startsWith('chromium-')).sort().reverse();
    for (const build of builds) {
      for (const sub of [
        'chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
        'chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
        'chrome-linux-arm64/chrome', 'chrome-linux64/chrome', 'chrome-linux/chrome',
      ]) {
        const candidate = path.join(cache, build, sub);
        if (fs.existsSync(candidate)) return candidate;
      }
    }
  }
  return ['/usr/bin/chromium-browser', '/usr/bin/chromium'].find(file => fs.existsSync(file));
}

const playwrightModule = resolvePlaywright();
const {chromium, firefox} = require(playwrightModule);

function launchChromium(options = {}) {
  const executablePath = resolveChromium();
  // The full Chromium channel supports microphone permissions in headless mode.
  const browserOptions = executablePath ? {executablePath} : {channel: 'chromium'};
  return chromium.launch({headless: true, ...browserOptions, ...options,
    args: [...(options.args || []), '--mute-audio']});
}

function launchFirefox(options = {}) {
  // Mute only the browser's output; media clocks, volume controls and analyser
  // nodes still run, so synthetic playback tests cannot disturb the desktop.
  return firefox.launch({headless: true, ...options,
    firefoxUserPrefs: {...options.firefoxUserPrefs, 'media.volume_scale': '0.0'}});
}

const fullMatrix = process.env.LIXITY_BROWSER_FULL === '1';
const browserLocales = fullMatrix ? ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl'] : ['en', 'de'];

module.exports = {launchChromium, launchFirefox, playwrightModule, fullMatrix, browserLocales};
