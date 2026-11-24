// Shared startup for optional browser tests and documentation captures.
//
// Explicit environment overrides (PLAYWRIGHT_MODULE,
// PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH) take precedence. Browser checks and
// captures also discover packages installed by `make browser-tools`.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const browserToolsDir = process.env.BROWSER_TOOLS_DIR || path.join(os.homedir(), '.local/share/lixity/browser-tools');

function resolvePlaywright() {
  if (process.env.PLAYWRIGHT_MODULE) return process.env.PLAYWRIGHT_MODULE;
  try {
    // Consumers load both the package and its `test` submodule; return the
    // package directory, not the resolved main file (`index.js`).
    return path.dirname(require.resolve('playwright/package.json'));
  } catch {}
  const isolated = path.resolve(browserToolsDir, 'node_modules', 'playwright');
  return fs.existsSync(isolated) ? isolated : 'playwright';
}

function resolveChromium() {
  if (process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH) return process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
  if (process.env.PLAYWRIGHT_BROWSERS_PATH) return undefined;
  const home = os.homedir();
  const caches = [
    path.join(browserToolsDir, 'browsers'),
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

function resolveAxe() {
  const roots = [path.resolve(playwrightModule), path.resolve(browserToolsDir), __dirname];
  try { return require.resolve('axe-core/axe.min.js', {paths: roots}); }
  catch { return undefined; }
}

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

function modShortcut(key) {
  return `ControlOrMeta+${key}`;
}

module.exports = {launchChromium, launchFirefox, playwrightModule, resolveAxe, fullMatrix, browserLocales, modShortcut};
