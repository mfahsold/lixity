const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {launchChromium, launchFirefox, modShortcut} = require('../../scripts/browser_tools.cjs');

(async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-editor-'));
  const source = path.join(root, 'book.md');
  fs.writeFileSync(source, '# A synthetic chapter\n\nA quiet morning beside the river.\n');
  const server = spawn(process.env.PYTHON_BIN || '.venv/bin/python', ['tests/browser/editor-server.py', root], {env: {...process.env, PYTHONPATH: 'src:.'}});
  server.stderr.on('data', data => process.stderr.write(data));
  let browser;
  try {
    const base = await new Promise((resolve, reject) => {
      server.stdout.once('data', data => resolve(String(data).trim()));
      server.once('exit', code => reject(new Error('Server exited: ' + code)));
    });
    browser = await (process.argv.includes('--firefox') ? launchFirefox() : launchChromium());
    const page = await browser.newPage({viewport: {width: 1440, height: 900}});
    page.setDefaultTimeout(15000);
    await page.goto(base);
    assert.equal(await page.evaluate(() => Boolean(window.LixityLog && typeof window.LixityLog.event === 'function' && typeof window.setLixityDebug === 'function')), true, 'Structured browser logging API is mounted');
    assert.equal(await page.locator('#manuscript-close').isHidden(), true, 'Close writing button is hidden before entering Write mode');
    await page.locator('#manuscript-write').click({timeout: 5000});
    await page.locator('.cm-content').waitFor();
    assert.equal(await page.locator('#manuscript-close').isVisible(), true, 'Close writing button is visible while editing');
    assert.equal(await page.locator('#manuscript-write').isHidden(), true, 'Write button is replaced by Close writing while editing');
    assert.equal(await page.locator('#manuscript-reader-controls').isHidden(), true, 'Reader toolbar is hidden in Write mode so only one unified editor toolbar is shown');
    const editorToolbarBox = await page.locator('.manuscript-editor-toolbar').boundingBox();
    assert.ok(editorToolbarBox && editorToolbarBox.height <= 60, 'Unified editor toolbar fits on a single desktop row');
    assert.equal(await page.evaluate(() => Boolean(window.LixityChrome && typeof window.LixityChrome.hide === 'function' && typeof window.LixityChrome.reveal === 'function')), true, 'Central LixityChrome auto-hide controller is mounted');
    assert.equal(await page.locator('.cm-content').getAttribute('spellcheck'), 'false', 'CodeMirror editor disables browser spellcheck underlines');
    assert.equal(await page.locator('#manuscript-recover').isHidden(), true, 'Recover button stays hidden until a recovery entry is selected');
    assert.equal(await page.locator('#manuscript-discard').isHidden(), true, 'Discard button stays hidden until a recovery entry is selected');
    await page.locator('#manuscript-undo').focus();
    assert.equal(await page.locator('#lixity-tooltip kbd').textContent(), 'Ctrl+Z', 'Editor undo button exposes its keyboard shortcut badge in tooltip');
    assert.equal(await page.locator('#manuscript-read').count(), 0, 'Consolidated Read & Refresh button is removed');
    // Closing without edits returns to reading immediately and restores focus.
    await page.locator('#manuscript-close').click();
    await page.waitForFunction(() => !document.body.classList.contains('manuscript-writing'));
    assert.equal(await page.locator('#manuscript-editor').isHidden(), true, 'Close writing hides the editor section');
    assert.equal(await page.locator('#manuscript-close').isHidden(), true, 'Close writing hides itself');
    assert.equal(await page.locator('#manuscript-write').isVisible(), true, 'Close writing restores the Write button');
    assert.equal(await page.evaluate(() => document.activeElement && document.activeElement.id), 'manuscript-write', 'Close writing returns focus to #manuscript-write');
    // Closing after edits flushes pending changes and reloads the reading view.
    await page.locator('#manuscript-write').click();
    await page.locator('.cm-content').waitFor();
    await page.locator('.cm-content').click();
    await page.keyboard.press(modShortcut('End'));
    await page.keyboard.type('New sentence.');
    await Promise.all([page.waitForNavigation(), page.locator('#manuscript-close').click()]);
    await page.locator('#chapters').waitFor();
    assert.match(await page.locator('#chapters').innerText(), /New sentence\./);
    assert.match(fs.readFileSync(source, 'utf8'), /New sentence/, 'Close writing flushes dirty text before returning');
    await page.evaluate(() => { if (document.activeElement) document.activeElement.blur(); window.LixityChrome.hide(); });
    assert.equal(await page.evaluate(() => document.body.classList.contains('chrome-autohidden')), true, 'Auto-hidden chrome hides reader controls');
    await page.locator('#chapters .ptext').first().click();
    assert.equal(await page.evaluate(() => document.body.classList.contains('chrome-autohidden')), false, 'Clicking prose reveals auto-hidden reader navigation');
    await page.locator('#manuscript-write').click();
    await page.locator('.cm-content').click();
    await page.keyboard.type(' Temp.');
    await page.keyboard.press(modShortcut('z'));
    assert.doesNotMatch(await page.locator('.cm-content').innerText(), /Temp\./, 'Undo reverts typed text in Write mode');
    fs.writeFileSync(source, '# External\n\nChanged elsewhere.\n');
    await page.keyboard.type('My retained draft.');
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state === 'conflict');
    assert.equal(fs.readFileSync(source, 'utf8'), '# External\n\nChanged elsewhere.\n');
    page.on('dialog', dialog => dialog.accept());
    await page.reload();
    await page.locator('#manuscript-write').click();
    await page.locator('#manuscript-recovery option[value]:not([value=""])').first().waitFor({state: 'attached'});
    const draft = await page.locator('#manuscript-recovery option[data-kind="draft"]').first().getAttribute('value');
    await page.locator('#manuscript-recovery').selectOption(draft);
    let releaseRecovery;
    const delayedRecovery = new Promise(resolve => {releaseRecovery = resolve;});
    await page.route('**/manuscript-edit?recovery=*', async route => {await delayedRecovery; await route.continue();});
    const response = page.waitForResponse(url => url.url().includes('manuscript-edit?recovery='));
    await page.locator('#manuscript-recover').click();
    await page.locator('.cm-content').click();
    await page.keyboard.press(modShortcut('End'));
    await page.keyboard.type('Concurrent typing.');
    releaseRecovery(); await response;
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.match(await page.locator('.cm-content').innerText(), /Concurrent typing/, 'Delayed recovery must not replace newer typing');
    assert.doesNotMatch(await page.locator('.cm-content').innerText(), /My retained draft/);
    await page.unroute('**/manuscript-edit?recovery=*');
    await page.keyboard.press(modShortcut('z'));
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state === 'saved');
    await page.locator('#manuscript-recover').click();
    await page.waitForFunction(() => document.querySelector('.cm-content').innerText.includes('My retained draft'));
    assert.match(await page.locator('.cm-content').innerText(), /My retained draft/);
    assert.equal(fs.readFileSync(source, 'utf8'), '# External\n\nChanged elsewhere.\n', 'Recovery must not auto-overwrite external changes');
    await page.screenshot({path: path.join(root, 'desktop.png')});
    await page.evaluate(() => document.documentElement.style.colorScheme = 'dark');
    assert.equal(await page.locator('.cm-editor').evaluate(el => getComputedStyle(el).color), 'rgb(238, 242, 248)');
    await page.waitForFunction(() => getComputedStyle(document.body).backgroundColor === 'rgb(12, 16, 23)');
    await page.screenshot({path: path.join(root, 'desktop-dark.png')});
    await page.setViewportSize({width: 390, height: 844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path: path.join(root, 'mobile.png')});
    await page.locator('#manuscript-save').click();
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state === 'saved');
    await page.setViewportSize({width: 1440, height: 900});
    await page.locator('.cm-content').click();
    await page.keyboard.press(modShortcut('End'));
    await page.keyboard.type(' Read cycle.');
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state === 'saved');
    assert.equal(await page.locator('#manuscript-analysis-freshness').isVisible(), true, 'The original workspace must label its stale analysis after editing');
    await Promise.all([page.waitForNavigation(), page.locator('#manuscript-close').click()]);
    await page.locator('#chapters').waitFor();
    assert.match(await page.locator('#chapters').innerText(), /Read cycle/);
    assert.equal(await page.locator('#manuscript-editor').isHidden(), true, 'Closing write mode after edits returns to the refreshed reading view');
    assert.equal(await page.locator('#manuscript-write').isVisible(), true);
    assert.equal(await page.locator('#manuscript-analysis-freshness').isHidden(), true, 'Reloaded analysis is fresh after closing write mode');
    await page.locator('#manuscript-write').click();
    await page.locator('.cm-content').waitFor();
    await page.locator('.cm-content').click();
    await page.keyboard.press(modShortcut('End'));
    await page.keyboard.type(' Cursor kept.');
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state === 'saved');
    await page.screenshot({path: path.join(root, 'reading-desktop.png')});
    await page.setViewportSize({width:390, height:844});
    await page.screenshot({path: path.join(root, 'reading-mobile.png')});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    fs.writeFileSync(source, '# Externally revised while reading\n');
    await page.locator('.cm-content').click();
    await page.keyboard.type(' My retained draft.');
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state === 'conflict');
    assert.match(await page.locator('.cm-content').innerText(), /My retained draft/);
    assert.equal(fs.readFileSync(source, 'utf8'), '# Externally revised while reading\n');
    await page.setViewportSize({width:1440, height:900});
    for (const words of [50000, 150000, 300000]) {
      const manuscript = '# Synthetic scale fixture\n\n' + ('Synthetic river morning words '.repeat(25) + '\n\n').repeat(words / 100);
      const start = performance.now();
      await page.evaluate(value => {
        if (window.scaleEditor) {window.scaleEditor.destroy(); document.getElementById('scale').remove();}
        const parent = document.createElement('div'); parent.id = 'scale'; document.body.prepend(parent);
        window.scaleEditor = LixityCodeMirror.mount(parent, value, () => {}, 'en', 'Scale fixture');
        window.scaleEditor.focus();
      }, manuscript);
      await page.locator('#scale .cm-content').waitFor();
      const loadMs = Math.round(performance.now() - start);
      const typingStart = performance.now();
      await page.keyboard.type('Typed.');
      assert.equal(await page.evaluate(() => window.scaleEditor.text().length), manuscript.length + 6);
      assert.ok(await page.locator('#scale .cm-line').count() < 1000, 'Long manuscript is viewport-rendered');
      console.log(JSON.stringify({words, mountMs: loadMs, sixKeystrokesMs: Math.round(performance.now() - typingStart), bytes: Buffer.byteLength(manuscript)}));
    }
    console.log('Editor flow passed. Screenshots: ' + root);
  } finally {
    if (browser) await browser.close();
    const closed = new Promise(resolve => server.once('close', resolve));
    if (server.stdin && !server.stdin.destroyed) server.stdin.end();
    if (server.exitCode === null && server.signalCode === null) {
      let timer;
      try {
        await Promise.race([
          closed,
          new Promise((_, reject) => {
            timer = setTimeout(() => reject(new Error('Editor server shutdown timed out')), 3000);
          }),
        ]);
      } catch {
        server.kill('SIGKILL');
        await Promise.race([closed, new Promise(resolve => setTimeout(resolve, 3000))]);
      } finally {
        clearTimeout(timer);
      }
    }
    fs.rmSync(root, {recursive: true, force: true});
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
