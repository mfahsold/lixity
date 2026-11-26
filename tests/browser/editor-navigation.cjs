const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {launchChromium, launchFirefox, modShortcut} = require('../../scripts/browser_tools.cjs');

async function holdEditResponse(page, method) {
  let receive, release, settled;
  const received = new Promise(resolve => { receive = resolve; });
  const released = new Promise(resolve => { release = resolve; });
  const delivered = new Promise(resolve => { settled = resolve; });
  let holding = false;
  await page.route('**/manuscript-edit', async route => {
    if (holding || route.request().method() !== method) return route.continue();
    holding = true;
    const response = await route.fetch();
    receive(route.request());
    await released;
    try { await route.fulfill({response}); }
    catch (_) { /* A superseded fetch may already have been aborted. */ }
    finally { settled(); }
  });
  return {received, async deliver() { release(); await delivered; }};
}

(async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-navigation-'));
  const source = path.join(root, 'book.md');
  const original = '# Synthetic chapter\r\n\r\nA quiet morning beside the river.\r\n\r\nGrüße 🌊 café repeated café.\r\n\r\nGrüße 🌊 café repeated café.\r\n' +
    Array.from({length: 40}, (_, index) => '\r\nSynthetic paragraph ' + (index + 1) + ' from the walking notes.\r\n').join('');
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
    const page = await browser.newPage({viewport: {width: 1440, height: 900}});
    await page.addInitScript(() => {
      window.reportedDirty = [];
      window.lixityDesktop = {setDirtyState: async state => { window.reportedDirty.push(state.unsavedEditor); }};
    });
    await page.goto(base);
    const initialRevision = await page.evaluate(() => document.body.dataset.manuscriptSourceSha256);
    const write = page.locator('#manuscript-write');
    const close = page.locator('#manuscript-close');
    const editor = page.locator('.cm-content');

    // The first response belongs to the view that requested it.
    const initialRead = await holdEditResponse(page, 'GET');
    await write.click();
    await initialRead.received;
    await page.locator('#tab-view-research').click();
    await initialRead.deliver();
    await page.locator('#tab-view-analysis').click();
    assert.equal(await page.locator('#manuscript-editor').isHidden(), true);

    // A failed open stays in the reader and displays actionable feedback.
    await page.route('**/manuscript-edit', route => route.fulfill({
      status: 503, json: {ok: false, message: 'Temporary fixture failure'},
    }), {times: 1});
    await write.click();
    const openError = page.locator('#manuscript-opening-error');
    await openError.waitFor();
    assert.equal(await openError.getAttribute('role'), 'alert');
    assert.equal(await page.locator('#manuscript-editor').isHidden(), true);

    const readerPassage = page.locator('#chapters .ptext').nth(16);
    await readerPassage.evaluate(node => node.scrollIntoView({behavior: 'instant', block: 'center'}));
    const readerOffset = () => readerPassage.evaluate(node => node.getBoundingClientRect().top);
    const beforeWriting = await readerOffset();
    assert.ok(await page.evaluate(() => scrollY > 0), 'The return begins below the first reader viewport');

    // Opening focuses the content and uses the recovery records in the opening response.
    let editorReads = 0;
    page.on('request', request => {
      if (request.method() === 'GET' && request.url().endsWith('/manuscript-edit')) editorReads++;
    });
    await write.click();
    await editor.waitFor();
    await page.waitForFunction(() => document.activeElement.matches('.cm-content'));
    assert.equal(await openError.isHidden(), true);
    await page.locator('#manuscript-versions > summary').press('Enter');
    await page.locator('#manuscript-recovery option').first().waitFor({state: 'attached'});
    assert.equal(editorReads, 1);
    assert.equal(await page.locator('#manuscript-versions > summary').evaluate(node => document.activeElement === node), true);
    await page.locator('#manuscript-compare').click();
    const candidate = page.locator('#manuscript-comparison-draft');
    await candidate.waitFor();
    await candidate.fill('Candidate text that is only in the comparison.');
    assert.deepEqual(await page.evaluate(() => window.reportedDirty), [false, true]);
    page.once('dialog', dialog => dialog.accept());
    await page.locator('#manuscript-comparison-cancel').click();
    await page.waitForFunction(() => window.reportedDirty.at(-1) === false);
    assert.deepEqual(await page.evaluate(() => window.reportedDirty), [false, true, false]);

    // Closing without edits restores reading and preserves the editor caret.
    await editor.focus();
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowRight');
    const selection = () => page.evaluate(() => {
      const selected = getSelection();
      return {
        anchor: selected.anchorNode.parentElement.closest('.cm-line').textContent,
        offset: selected.anchorOffset,
      };
    });
    const beforeClose = await selection();
    assert.equal(await page.locator('#manuscript-read').count(), 0, 'Consolidated close button replaces separate Read & Refresh button');
    await close.click();
    assert.equal(await page.locator('#manuscript-editor').isHidden(), true);
    assert.equal(await write.evaluate(node => document.activeElement === node), true);
    assert.equal(await page.evaluate(() => document.body.dataset.manuscriptSourceSha256), initialRevision);
    assert.ok(Math.abs(await readerOffset() - beforeWriting) <= 1);
    await write.click();
    await editor.waitFor();
    assert.deepEqual(await selection(), beforeClose);
    await close.click();
    await page.evaluate(() => window.LixityManuscriptEditor.openAtLine(3));
    assert.deepEqual(await selection(), {anchor: 'A quiet morning beside the river.', offset: 0});

    // A newer edit during the close save must be persisted before reload.
    const saveResponse = await holdEditResponse(page, 'POST');
    const prompts = [];
    const handleDialog = async dialog => { prompts.push(dialog.type()); await dialog.dismiss(); };
    page.on('dialog', handleDialog);
    await page.keyboard.press(modShortcut('End'));
    await page.keyboard.type(' Consolidated close edit.');
    await close.click();
    const firstWrite = await saveResponse.received;
    assert.match(firstWrite.postDataJSON().text, /Consolidated close edit\./);
    await editor.focus();
    await page.keyboard.type(' Kept the next edit.');
    await Promise.all([page.waitForNavigation(), saveResponse.deliver()]);
    await page.locator('#chapters').waitFor();
    assert.match(await page.locator('#chapters').innerText(), /Consolidated close edit\. Kept the next edit\./);
    assert.deepEqual(prompts, []);
    page.off('dialog', handleDialog);
    assert.notEqual(await page.evaluate(() => document.body.dataset.manuscriptSourceSha256), initialRevision);
    await page.waitForFunction(() => document.activeElement.id === 'manuscript-write');
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.ok(Math.abs(await readerOffset() - beforeWriting) <= 1);

    // The platform save shortcut uses manuscript persistence rather than Save Page.
    await write.click();
    await editor.waitFor();
    await page.keyboard.press(modShortcut('End'));
    await page.keyboard.type(' Shortcut edit.');
    assert.match(await page.locator('#manuscript-save').getAttribute('aria-keyshortcuts'), /^(Control|Meta)\+S$/);
    await page.evaluate(() => {
      document.addEventListener('keydown', event => {
        if (event.key.toLowerCase() === 's') window.saveShortcutHandled = event.defaultPrevented;
      }, true);
    });
    await page.keyboard.press(modShortcut('s'));
    assert.equal(await page.evaluate(() => window.saveShortcutHandled), true);
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state === 'saved');
    assert.match(fs.readFileSync(source, 'utf8'), /Shortcut edit\./);

    // External changes detected on save surface an explicit conflict without overwriting disk.
    fs.writeFileSync(source, '# Changed externally\n');
    await editor.click();
    await page.keyboard.type(' Local draft.');
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state === 'conflict');
    assert.equal(fs.readFileSync(source, 'utf8'), '# Changed externally\n');
    console.log('Editor navigation, comparison dirty state, caret, save shortcut, and close flow passed.');
  } finally {if (browser) await browser.close(); server.stdin.end();}
})().catch(error => {console.error(error); process.exitCode = 1;});
