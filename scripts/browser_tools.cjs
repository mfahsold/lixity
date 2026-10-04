// Shared startup for optional browser tests and documentation captures.
const fs = require('node:fs');
const playwrightModule = process.env.PLAYWRIGHT_MODULE || 'playwright';
const {chromium} = require(playwrightModule);

function launchChromium() {
  const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ||
    ['/usr/bin/chromium-browser', '/usr/bin/chromium'].find(file => fs.existsSync(file));
  return chromium.launch({headless: true, ...(executablePath ? {executablePath} : {})});
}

module.exports = {launchChromium, playwrightModule};
