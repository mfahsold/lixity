const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {launchChromium, launchFirefox, modShortcut, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
(async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-editor-features-'));
  const source = path.join(root, 'book.md');
  const original = '# Synthetic chapter\n\nA quiet morning beside the river.\n\nCafé river. Café river.\n';
  const reviewed = '# Reviewed\n\nDr. Vale waits. She turns.\n';
  const external = '# External\n\n“Rain falls.” Storm clouds bring rain again soon.\n';
  fs.writeFileSync(source, original);
  const server = spawn(process.env.PYTHON_BIN || '.venv/bin/python', ['tests/browser/editor-server.py', root], {env:{...process.env,PYTHONPATH:'src:.'}});
  server.stderr.on('data', data => process.stderr.write(data));
  let browser;
  try {
    const base = await new Promise((resolve,reject) => {server.stdout.once('data', d=>resolve(String(d).trim()));server.once('exit',c=>reject(new Error('Server '+c)));});
    browser = await (process.argv.includes('--firefox') ? launchFirefox() : launchChromium());
    const page = await browser.newPage({viewport:{width:1440,height:900}}); page.setDefaultTimeout(10000);
    async function checkHelp(selector, name, description) {
      const control = page.locator(selector);
      await control.focus();
      await expect(control).toHaveAccessibleName(name);
      await expect(control).toHaveAccessibleDescription(description);
      const tip = page.locator('#lixity-tooltip');
      await expect(tip).toBeVisible();
      const box = await tip.boundingBox();
      const viewport = page.viewportSize();
      assert.ok(box && box.x >= 0 && box.y >= 0 &&
        box.x + box.width <= viewport.width && box.y + box.height <= viewport.height);
      await page.keyboard.press('Escape');
      await expect(tip).toHaveAttribute('aria-hidden', 'true');
    }
    const outsideWorkspace = [];
    page.on('request', request => {
      const url = new URL(request.url());
      if (/^https?:$/.test(url.protocol) && url.origin !== new URL(base).origin) outsideWorkspace.push(url.origin);
    });
    let holdInitial = true, initialMeasured, releaseInitial, initialDelivered;
    const initialPulseMeasured = new Promise(resolve => {initialMeasured = resolve;});
    const initialPulseHeld = new Promise(resolve => {releaseInitial = resolve;});
    const initialPulseDelivered = new Promise(resolve => {initialDelivered = resolve;});
    const deltaRoute = '**/manuscript-delta';
    let deltaReads = 0;
    await page.route(deltaRoute, async route => {
      deltaReads++;
      if (!holdInitial) return route.continue();
      holdInitial = false;
      const response = await route.fetch();
      initialMeasured();
      await initialPulseHeld;
      try {await route.fulfill({response});}
      catch (error) {if (!String(error).includes('aborted')) throw error;}
      finally {initialDelivered();}
    });
    await page.goto(base);
    await checkHelp('#manuscript-write', 'Write', 'Open the manuscript for editing at your current reading position.');
    await page.locator('#manuscript-write').click();
    await page.locator('.cm-content').waitFor();
    assert.equal(deltaReads, 0, 'Entering Write does not request a report');
    const versionsMenu = page.locator('#manuscript-versions > summary');
    const pulse = page.locator('#manuscript-session-pulse');
    const pulseValues = page.locator('#manuscript-pulse-popover p');
    await versionsMenu.click();
    await pulse.click();
    await initialPulseMeasured;
    await versionsMenu.click();
    await page.locator('#manuscript-search').click();
    await page.locator('.cm-search input[name=search]').fill('Café');
    await page.locator('.cm-search input[name=replace]').fill('Next morning');
    await page.locator('.cm-search button[name=replaceAll]').click();
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state==='saved');
    assert.equal(fs.readFileSync(source,'utf8'),original.replaceAll('Café','Next morning'));
    assert.equal(deltaReads, 1, 'Autosave while writing does not request a revision report');
    await versionsMenu.click();
    const refreshedPulse = page.waitForResponse(response => response.url().endsWith('/manuscript-delta'));
    await pulse.click();
    const measured = await (await refreshedPulse).json();
    const baselineDate = await page.evaluate(createdAt => (
      new Intl.DateTimeFormat(document.documentElement.lang, {dateStyle:'medium'}).format(new Date(createdAt * 1000))
    ), measured.base.created_at);
    await pulseValues.filter({hasText: new RegExp('^' + measured.current.words + ' words')}).waitFor();
    await pulseValues.filter({hasText:'since ' + baselineDate}).waitFor();
    const expectedPulse = await pulseValues.textContent();
    releaseInitial();
    await initialPulseDelivered;
    await page.waitForLoadState('networkidle');
    assert.equal(await pulseValues.textContent(), expectedPulse, 'A late response cannot replace the acknowledged revision’s pulse');
    await page.unroute(deltaRoute);
    await page.setViewportSize({width:320,height:844});
    assert.ok(await pulseValues.evaluate(node => node.scrollWidth <= node.clientWidth));
    await page.setViewportSize({width:1440,height:900});
    await versionsMenu.click();
    await page.locator('#manuscript-undo').click();
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state==='saved');
    assert.equal(fs.readFileSync(source,'utf8'),original,'One undo restores replace-all');
    await page.locator('.cm-search button[name=close]').click();
    fs.writeFileSync(source, external);
    await page.locator('.cm-content').click(); await page.keyboard.press(modShortcut('End')); await page.keyboard.type(' My draft.');
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state==='conflict');
    const recovery = page.locator('#manuscript-recovery');
    const retained = recovery.locator('option[data-kind="draft"]').first();
    await retained.waitFor({state:'attached'});
    await page.keyboard.insertText(' Newer unsaved text.');
    await page.locator('#manuscript-versions > summary').click();
    await recovery.selectOption(await retained.getAttribute('value'));
    assert.ok(await page.locator('#manuscript-recover').isDisabled());
    assert.match(await recovery.getAttribute('aria-describedby'), /manuscript-recovery-note/);
    assert.match(await page.locator('#manuscript-recovery-note').innerText(), /Compare the recovery copy/);
    await checkHelp('#manuscript-download', 'Download draft', 'Download the text currently in the editor as a separate Markdown file.');
    const [backup] = await Promise.all([
      page.waitForEvent('download'), page.locator('#manuscript-download').click(),
    ]);
    assert.match(fs.readFileSync(await backup.path(), 'utf8'), /Newer unsaved text/);
    await checkHelp('#manuscript-compare', 'Compare versions', 'Compare the file on disk with your current text or the selected recovery copy.');
    await page.locator('#manuscript-compare').click();
    await page.locator('#manuscript-comparison[open]').waitFor();
    await page.setViewportSize({width:320,height:844});
    await checkHelp('#manuscript-comparison-use', 'Use as draft',
      'Review the draft in the editor. Choose “Save this draft” to write it to the manuscript.');
    assert.equal(fs.readFileSync(source, 'utf8'), external, 'Reading draft help does not write the manuscript');
    await page.setViewportSize({width:1440,height:900});
    const reference = page.locator('#manuscript-comparison a[href*="/guides/metrics/"]');
    assert.ok(await reference.isVisible(), 'The version comparison exposes its reference in the open dialog');
    assert.equal(await reference.getAttribute('href'), '/guides/metrics/en.html#revisions');
    assert.equal(await reference.textContent(), 'How it’s measured');
    assert.equal(await reference.getAttribute('target'), '_blank');
    assert.ok(await reference.evaluate(node => node.relList.contains('noopener')));
    assert.equal(await page.locator('#manuscript-comparison-base').inputValue(),original);
    assert.equal(await page.locator('#manuscript-comparison-current').inputValue(), external);
    assert.match(await page.locator('#manuscript-comparison-draft').inputValue(),/My draft/);
    assert.doesNotMatch(await page.locator('#manuscript-comparison-draft').inputValue(), /Newer unsaved text/);
    const editorBuffer = page.locator('#manuscript-comparison-buffer');
    await page.locator('#manuscript-comparison-buffer-label').click();
    assert.equal(await editorBuffer.getAttribute('readonly'), '');
    assert.match(await editorBuffer.inputValue(), /Newer unsaved text/);
    await page.locator('#manuscript-comparison-buffer-label').click();
    assert.equal(await page.locator('#manuscript-comparison').getByText('Unsaved — retry').count(), 0,
      'Opening the comparison uses draft language rather than a failure message');
    assert.ok((await page.locator('#manuscript-recovery option[data-kind="draft"]').allTextContents())
      .every(label => label.startsWith('Draft to review')));
    const summaries = page.locator('#manuscript-comparison .manuscript-compare-metrics');
    const baseSummary = summaries.nth(0);
    const currentSummary = summaries.nth(1);
    const draftSummary = summaries.nth(2);
    const chaptersCompare = page.locator('#manuscript-comparison-chapters');
    await baseSummary.filter({hasText:'Average words per sentence'}).waitFor();
    await currentSummary.filter({hasText:'25%'}).waitFor();
    await draftSummary.filter({hasText:'Average words per sentence'}).waitFor();
    await page.locator('#manuscript-comparison-draft').fill('# External\n\n“Rain falls. Storm clouds” bring rain again soon.\n');
    await draftSummary.filter({hasText:'50% (Δ +25.0 percentage points)'}).waitFor();
    await chaptersCompare.filter({hasText:'+25.0 percentage points'}).waitFor();
    await page.locator('#manuscript-comparison-draft').fill('# External\n\n“Rain falls.” It was only a matter of the time that he had to go.\n');
    await draftSummary.filter({hasText:'50.0% (Δ +50.0 percentage points)'}).waitFor();
    await page.locator('#manuscript-comparison-draft').fill(reviewed);
    await draftSummary.filter({hasText:'Average words per sentence 2.5'}).waitFor();
    page.once('dialog', dialog => dialog.dismiss());
    await page.locator('#manuscript-comparison-cancel').click();
    assert.equal(await page.locator('#manuscript-comparison').evaluate(el=>el.open),true,'Cancelled discard keeps edited comparison');
    await page.screenshot({path:path.join(root,'comparison-desktop.png')});
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(root,'comparison-mobile.png')});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.setViewportSize({width:320,height:844});
    assert.equal(await summaries.evaluateAll(nodes => nodes.every(node => node.scrollWidth <= node.clientWidth)), true);
    await page.locator('#manuscript-comparison-buffer-label').click();
    assert.equal(await editorBuffer.evaluate(node => {
      const bounds = node.getBoundingClientRect();
      const body = node.closest('.modal-body');
      return bounds.width > 0 && bounds.left >= 0 && bounds.right <= innerWidth && body.scrollWidth <= body.clientWidth;
    }), true, 'The original unsaved text remains readable at 320 CSS pixels');
    await page.locator('#manuscript-comparison-buffer-label').click();
    const useDraft = page.locator('#manuscript-comparison-use');
    let prompt;
    page.once('dialog', async dialog => {
      prompt = dialog.message();
      await dialog.dismiss();
    });
    await useDraft.click();
    assert.match(prompt, /Replace the unsaved text/);
    assert.ok(await page.locator('#manuscript-comparison').isVisible(), 'Declining to replace unsaved text keeps the comparison open');
    assert.match(await page.locator('.cm-content').innerText(), /Newer unsaved text/);
    assert.equal(await page.locator('#manuscript-comparison-draft').inputValue(), reviewed);
    page.once('dialog', dialog => dialog.accept());
    await useDraft.click();
    assert.equal(fs.readFileSync(source,'utf8'), external, 'Comparison adoption does not write');
    await page.locator('#manuscript-save').click();
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state==='saved');
    assert.equal(fs.readFileSync(source,'utf8'),reviewed);
    await page.locator('#manuscript-versions > summary').click();
    await recovery.selectOption('');
    await page.locator('#manuscript-compare').click();
    await page.locator('#manuscript-comparison[open]').waitFor();
    await currentSummary.filter({hasText:'Average words per sentence 2.5'}).waitFor();
    assert.equal(await page.locator('#manuscript-comparison-draft').inputValue(),reviewed);
    assert.doesNotMatch(await draftSummary.textContent(), /Δ|1\.7/, 'An abbreviation in identical prose produces no change');
    assert.match(await currentSummary.textContent(), /Average words per sentence 2\.5/);
    assert.equal(await baseSummary.textContent(), await currentSummary.textContent(), 'The same stored revision is measured consistently');
    assert.equal(await draftSummary.textContent(), await currentSummary.textContent(), 'Identical draft uses the same backend measurements');
    const delayedDraft = '# Reviewed\n\nOlder candidate now.\n';
    let olderReady, releaseOlder, olderFinished;
    const olderMeasured = new Promise(resolve => {olderReady = resolve;});
    const olderHeld = new Promise(resolve => {releaseOlder = resolve;});
    const olderReleased = new Promise(resolve => {olderFinished = resolve;});
    await page.route('**/manuscript-compare', async route => {
      if (route.request().postDataJSON().draft_text !== delayedDraft) return route.continue();
      const response = await route.fetch();
      olderReady();
      await olderHeld;
      try {await route.fulfill({response});}
      catch (_) { /* An aborted comparison may discard the response. */ }
      finally {olderFinished();}
    });
    await page.locator('#manuscript-comparison-draft').fill(delayedDraft);
    await olderMeasured;
    const compareAfterEdit = page.waitForResponse(res => res.url().includes('/manuscript-compare') && res.request().method() === 'POST');
    await page.locator('#manuscript-comparison-draft').fill('# Reviewed\n\nThe later reviewed draft stays here.\n');
    assert.equal(await draftSummary.textContent(), 'Calculating measurements…');
    await compareAfterEdit;
    await draftSummary.filter({hasText:'Average words per sentence 6.0'}).waitFor();
    releaseOlder();
    await olderReleased;
    assert.match(await draftSummary.textContent(), /Average words per sentence 6\.0/, 'An older response cannot replace a newer draft measurement');
    assert.doesNotMatch(await draftSummary.textContent(), /today/, 'Draft deltas refer to the preceding version');
    // Ambiguous chapter correspondence withholds false chapter-level deltas.
    const compareUnclear = page.waitForResponse(res => res.url().includes('/manuscript-compare') && res.request().method() === 'POST');
    await page.locator('#manuscript-comparison-draft').fill('# Chapter\n\nSame words.\n\n# Chapter\n\nDifferent words.\n');
    await compareUnclear;
    await chaptersCompare.filter({hasText:/corresponds|entspricht/i}).waitFor();
    fs.writeFileSync(source,'A newer external edit');
    await page.locator('#manuscript-comparison-draft').fill('Keep this editable after the file changes.');
    await draftSummary.filter({hasText:'The file or settings changed. Reopen the comparison.'}).waitFor();
    await page.locator('#manuscript-comparison-use').click(); await page.locator('#manuscript-save').click();
    await page.waitForFunction(() => document.querySelector('#manuscript-save-status').dataset.state==='conflict');
    assert.equal(fs.readFileSync(source,'utf8'),'A newer external edit');
    assert.deepEqual(outsideWorkspace, [], 'Editor comparison remains inside the local workspace');
    console.log('Editor search/replace, single undo, comparison and stale adoption passed: '+root);
  } finally {if(browser)await browser.close();server.stdin.end();}
})().catch(e=>{console.error(e);process.exitCode=1;});
