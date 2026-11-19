const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {launchChromium, launchFirefox, modShortcut} = require('../../scripts/browser_tools.cjs');

(async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-navigation-'));
  const source = path.join(root, 'book.md');
  const original = '# Synthetic chapter\r\n\r\nA quiet morning beside the river.\r\n\r\nGrüße 🌊 café repeated café.\r\n\r\nGrüße 🌊 café repeated café.\r\n';
  fs.writeFileSync(source, original);
  const server = spawn(process.env.PYTHON_BIN || '.venv/bin/python', ['tests/browser/editor-server.py', root], {env:{...process.env, PYTHONPATH:'src:.'}});
  server.stderr.on('data', data => process.stderr.write(data));
  let browser;
  try {
    const base = await new Promise((resolve, reject) => {
      server.stdout.once('data', data => resolve(String(data).trim()));
      server.once('exit', code => reject(new Error('Server exited: ' + code)));
    });
    browser = await (process.argv.includes('--firefox') ? launchFirefox() : launchChromium());
    const page = await browser.newPage();
    await page.goto(base);
    const initialRevision = await page.evaluate(() => document.body.dataset.manuscriptSourceSha256);
    await page.locator('#manuscript-write').click();
    await page.locator('.cm-content').waitFor();
    assert.equal(await page.locator('#manuscript-read').count(), 0, 'Consolidated close button replaces separate Read & Refresh button');
    // Closing without edits returns to the reading view immediately without reloading.
    await page.locator('#manuscript-close').click();
    assert.equal(await page.locator('#manuscript-editor').isHidden(), true);
    assert.equal(await page.evaluate(() => document.body.dataset.manuscriptSourceSha256), initialRevision);
    // Editing and closing flushes pending edits and reloads the refreshed reading view.
    await page.locator('#manuscript-write').click();
    await page.locator('.cm-content').waitFor();
    await page.locator('.cm-content').click();
    await page.keyboard.press(modShortcut('End'));
    await page.keyboard.type(' Consolidated close edit.');
    await Promise.all([page.waitForNavigation(), page.locator('#manuscript-close').click()]);
    await page.locator('#chapters').waitFor();
    assert.match(await page.locator('#chapters').innerText(), /Consolidated close edit\./);
    assert.notEqual(await page.evaluate(() => document.body.dataset.manuscriptSourceSha256), initialRevision);
    // External changes detected on save surface an explicit conflict without overwriting disk.
    await page.locator('#manuscript-write').click();
    await page.locator('.cm-content').waitFor();
    fs.writeFileSync(source, '# Changed externally\n');
    await page.locator('.cm-content').click();
    await page.keyboard.type(' Local draft.');
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state === 'conflict');
    assert.equal(fs.readFileSync(source, 'utf8'), '# Changed externally\n');
    console.log('Editor navigation and consolidated close flow passed.');
  } finally {if (browser) await browser.close(); server.stdin.end();}
})().catch(error => {console.error(error); process.exitCode = 1;});
