const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {launchChromium, launchFirefox} = require('../../scripts/browser_tools.cjs');

(async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-navigation-'));
  const source = path.join(root, 'book.md');
  const original = '# Synthetic chapter\r\n\r\nA quiet morning beside the river.\r\n\r\nGrüße 🌊 café repeated café.\r\n\r\nGrüße 🌊 café repeated café.\r\n';
  fs.writeFileSync(source, original);
  const server = spawn('.venv/bin/python', ['tests/browser/editor-server.py', root], {env:{...process.env, PYTHONPATH:'src:.'}});
  server.stderr.on('data', data => process.stderr.write(data));
  let browser;
  try {
    const base = await new Promise((resolve, reject) => {
      server.stdout.once('data', data => resolve(String(data).trim()));
      server.once('exit', code => reject(new Error('Server exited: ' + code)));
    });
    browser = await (process.argv.includes('--firefox') ? launchFirefox() : launchChromium());
    const page = await browser.newPage();
    await page.goto(base); await page.locator('#manuscript-write').click();
    await page.locator('.cm-content').waitFor();
    const reading = page.frameLocator('#manuscript-reading-frame');
    async function read() {
      await page.locator('#manuscript-read').click();
      await reading.locator('body[data-editor-revision]').waitFor();
      await reading.locator('[data-view=analysis]').click();
      await reading.locator('#chapters .ptext-inner').last().waitFor();
    }
    async function selectLast() {
      await reading.locator('#chapters .ptext-inner').last().evaluate(node => {
        const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
        const text = walker.nextNode(), start = text.data.lastIndexOf('café');
        const range = document.createRange(); range.setStart(text, start); range.setEnd(text, start + 4);
        const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
      });
    }
    await read(); await selectLast();
    await page.locator('#manuscript-return-write').click();
    await page.waitForFunction(() => document.activeElement.closest('.cm-content') && !document.querySelector('#manuscript-read').disabled);
    await page.keyboard.type('changed');
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state === 'saved');
    assert.equal(fs.readFileSync(source, 'utf8'), original.replace(/café\.\r\n$/, 'changed.\r\n'), 'Select the exact second quote in the second repeated paragraph, with Unicode and CRLF');
    await page.keyboard.press('Control+z');
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state === 'saved');
    assert.equal(fs.readFileSync(source, 'utf8'), original, 'Range navigation preserves undo');
    await read(); await selectLast();
    await reading.locator('#chapters .ptext').last().evaluate(node => {node.dataset.start = '5';});
    await page.locator('#manuscript-return-write').click();
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').textContent.includes('cannot be mapped exactly'));
    assert.equal(fs.readFileSync(source, 'utf8'), original, 'Ambiguous paragraph context does not edit the buffer');
    await read();
    await page.locator('#manuscript-review-links').click();
    await reading.locator('.manuscript-link-review-item [data-research-history="claim"]').first().click();
    await reading.locator('#research-revision-edit-tab').click();
    await reading.locator('#research-revision-field-statement').fill('Unsaved synthetic research.');
    page.once('dialog', dialog => dialog.dismiss());
    await page.locator('#manuscript-return-write').click();
    assert.equal(await page.locator('#manuscript-reading').evaluate(node => node.open), true, 'Cancelling keeps the disposable reader mounted');
    assert.equal(await reading.locator('#research-revision-field-statement').inputValue(), 'Unsaved synthetic research.');
    page.once('dialog', dialog => dialog.dismiss());
    await page.locator('#manuscript-return-write').focus(); await page.keyboard.press('Escape');
    assert.equal(await page.locator('#manuscript-reading').evaluate(node => node.open), true, 'Escape uses the same guard');
    let unloadPrompt = false;
    page.once('dialog', async dialog => {unloadPrompt = dialog.type() === 'beforeunload'; await dialog.dismiss();});
    await page.reload({timeout:3000}).catch(() => {});
    assert.equal(unloadPrompt, true, 'Reload checks nested research drafts');
    assert.equal(await reading.locator('#research-revision-field-statement').inputValue(), 'Unsaved synthetic research.', 'Cancelled reload preserves research fields');
    await reading.locator('[name=research_revision_change_kind][value=correction]').check();
    await reading.locator('#research-revision-reason').fill('Synthetic review.');
    let finishSave;
    const held = new Promise(resolve => {finishSave = resolve;});
    await page.route('**/research-record-revise', async route => {
      await held; await route.fulfill({status:500, contentType:'application/json', body:JSON.stringify({ok:false, message:'Synthetic failure'})});
    });
    await reading.locator('#research-revision-save').click();
    await page.locator('#manuscript-return-write').click();
    assert.equal(await page.locator('#manuscript-reading').evaluate(node => node.open), true, 'An in-flight research revision cannot be discarded');
    const failed = page.waitForResponse(response => response.url().endsWith('/research-record-revise'));
    finishSave(); await failed;
    await reading.locator('#research-revision-save').waitFor({state:'visible'});
    await page.waitForFunction(() => !document.querySelector('#manuscript-reading-frame').contentWindow.LixityResearchDrafts.busy());
    assert.equal(await reading.locator('#research-revision-field-statement').inputValue(), 'Unsaved synthetic research.', 'A failed request keeps the draft');
    page.once('dialog', dialog => dialog.accept());
    await page.locator('#manuscript-return-write').click();
    await page.waitForFunction(() => document.activeElement.closest('.cm-content') && !document.querySelector('#manuscript-read').disabled);
    await read(); await selectLast();
    fs.writeFileSync(source, '# Changed externally\n');
    await page.locator('#manuscript-return-write').click();
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state === 'conflict');
    assert.equal(fs.readFileSync(source, 'utf8'), '# Changed externally\n');
    console.log('Editor navigation and nested research exit guards passed.');
  } finally {if (browser) await browser.close(); server.stdin.end();}
})().catch(error => {console.error(error); process.exitCode = 1;});
