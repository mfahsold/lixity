let playwrightMod = process.env.PLAYWRIGHT_MODULE || 'playwright';
const fs = require('node:fs');
try {
  require.resolve(playwrightMod);
} catch {
  const fallback = '/home/codeai/.npm/_npx/b234c773f454f454/node_modules/playwright';
  if (fs.existsSync(fallback)) playwrightMod = fallback;
}
const {chromium} = require(playwrightMod);
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '../..');
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
import json
import runpy
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
render = runpy.run_path('tests/test_ui_contract.py')['_full_dashboard']
original = render.__globals__['render_dashboard']
fixtures = {}
for language in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = {**get_language_profile(language).labels, **WORKSPACE_LABELS[language]}
    def localized(*args, **kwargs):
        return original(*args, **kwargs, labels=labels, language_key=language,
                        current_language=language)
    render.__globals__['render_dashboard'] = localized
    fixtures[language] = {'html': render(), 'labels': labels}
def standalone(*args, **kwargs):
    return original(*args, **kwargs, language_key='en', current_language='en',
                    enabled_actions=['analyze', 'rebuild'])
render.__globals__['render_dashboard'] = standalone
print(json.dumps({'fixtures': fixtures, 'standalone': render()}))
`], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8', maxBuffer: 32*1024*1024});
assert.equal(fixture.status, 0, fixture.error ? fixture.error.message : fixture.stderr);
const {fixtures, standalone} = JSON.parse(fixture.stdout);
const screenshotDir = fs.mkdtempSync('/tmp/lixity-project-controls-');
const syntheticContent = '## Synthetic chapter\r\n\r\nThe rain stopped.\r\nA café opened.\r\n';
const hostileFilename = 'chapter-<img onerror=alert(1)>.markdown';
const readStateOnly = process.argv.includes('--read-state-only');

// Synthetic drag data exercises the real DOM listeners; all HTTP stays intercepted.
async function dropFiles(page, files) {
  return page.locator('#manuscript-dropzone').evaluate((element, items) => {
    const transfer = new DataTransfer();
    for (const item of items) transfer.items.add(new File([item.content], item.name, {type: item.type || 'text/plain'}));
    const dragover = new DragEvent('dragover', {bubbles: true, cancelable: true, dataTransfer: transfer});
    element.dispatchEvent(dragover);
    const drop = new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: transfer});
    element.dispatchEvent(drop);
    return {dragoverPrevented: dragover.defaultPrevented, dropPrevented: drop.defaultPrevented};
  }, files);
}

// Read actual synthetic bytes, but hold delivery of native completion events.
async function holdFileReadCompletions(page) {
  await page.evaluate(() => {
    window.projectControlReads = [];
    window.projectControlNativeRead = FileReader.prototype.readAsText;
    FileReader.prototype.readAsText = function(file) {
      const held = {reader: this, callback: this.onload};
      window.projectControlReads.push(held);
      this.onload = event => {held.event = event;};
      window.projectControlNativeRead.call(this, file);
    };
  });
}

async function releaseFileRead(page, index) {
  await page.waitForFunction(i => Boolean(window.projectControlReads[i].event), index);
  await page.evaluate(i => {
    const held = window.projectControlReads[i];
    held.callback.call(held.reader, held.event);
  }, index);
}

async function restoreFileReads(page) {
  await page.evaluate(() => {FileReader.prototype.readAsText = window.projectControlNativeRead;});
}

(async () => {
  const launchOptions = {headless: true};
  const execPath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ||
    (fs.existsSync('/usr/bin/chromium-browser') ? '/usr/bin/chromium-browser' :
     fs.existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);
  if (execPath) launchOptions.executablePath = execPath;
  const browser = await chromium.launch(launchOptions);
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 900}});
    // Keep chooser interception enabled between waits: removing the last listener
    // makes Playwright toggle it asynchronously and race the next activation.
    page.on('filechooser', () => {});
    const errors = [];
    const submissions = [];
    const projectSubmissions = [];
    const posts = [];
    let language = 'en';
    let isStandalone = false;
    let response = {ok: true, message: 'Synthetic manuscript loaded', reload: false};
    let pendingLoad = null;
    let pendingCreate = null;
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => {if (message.type() === 'error') errors.push(message.text());});
    await page.route('http://lixity.test/**', async route => {
      const request = route.request();
      if (request.method() === 'POST') posts.push(request.url());
      if (request.url().endsWith('/api/load')) {
        submissions.push(request.postDataJSON());
        if (pendingLoad) await pendingLoad;
        await route.fulfill({json: response});
      } else if (request.url().endsWith('/api/project-create')) {
        projectSubmissions.push(request.postDataJSON());
        if (pendingCreate) await pendingCreate;
        await route.fulfill({json: {ok: false, message: 'Synthetic import rejected'}});
      } else if (request.url().includes('/api/')) {
        await route.fulfill({json: {ok: false, locked: true, records: [], message: 'Synthetic locked store'}});
      } else await route.fulfill({contentType: 'text/html', body: isStandalone ? standalone : fixtures[language].html});
    });

    for (const width of readStateOnly ? [] : [1440, 320]) {
      await page.setViewportSize({width, height: 900});
      await page.goto('http://lixity.test/');
      await page.locator('#tab-view-project').click();
      // Removing file-selection state or accidental auto-upload breaks these checks.
      assert.equal(await page.locator('#manuscript-dropzone').count(), 1, 'A manuscript drop target is available');
      const dropzone = page.locator('#manuscript-dropzone');
      const loadButton = page.locator('[data-action="load"]');
      assert.equal(await loadButton.isDisabled(), true, 'Loading waits for a file selection');
      assert.equal(await dropzone.evaluate(element => element.tagName), 'BUTTON');
      assert.equal(await dropzone.getAttribute('type'), 'button');
      assert.equal(await page.getByRole('button', {name: fixtures.en.labels.wizard_drop_aria, exact: true}).getAttribute('id'), 'manuscript-dropzone');
      assert.ok(await dropzone.getAttribute('aria-label'), 'The file chooser has an accessible name');
      assert.equal(await page.locator('#manuscript-file-name').getAttribute('aria-live'), 'polite');
      assert.equal(await page.locator('#ms-file').getAttribute('accept'), '.md,.markdown,.txt');
      assert.deepEqual(errors, [], 'Project control listeners initialize without runtime errors');
      const beforeSelection = submissions.length;

      for (const key of ['Space', 'Enter']) {
        await dropzone.focus();
        assert.equal(await dropzone.evaluate(element => document.activeElement === element), true, `Dropzone focused for ${key} at ${width}`);
        const [chooser] = await Promise.all([page.waitForEvent('filechooser').catch(async error => {
          const state = await page.evaluate(() => ({active: document.activeElement.id, input: manuscriptInput && manuscriptInput.id}));
          throw new Error(`${key} at ${width}px: ${error.message}; focus/input ${JSON.stringify(state)}`);
        }), page.keyboard.press(key)]);
        await chooser.setFiles({name: 'keyboard.txt', mimeType: 'text/plain', buffer: Buffer.from(syntheticContent)});
        assert.equal(await loadButton.isDisabled(), false);
        assert.equal((await page.locator('#manuscript-file-name').textContent()).trim(), 'keyboard.txt');
      }
      await page.locator('#ms-file').setInputFiles({name: 'picker.md', mimeType: 'text/markdown', buffer: Buffer.from(syntheticContent)});
      assert.equal((await page.locator('#manuscript-file-name').textContent()).trim(), 'picker.md');
      assert.equal(submissions.length, beforeSelection, 'Choosing a manuscript does not upload it');

      const dropResult = await dropFiles(page, [{name: hostileFilename, content: syntheticContent}]);
      assert.deepEqual(dropResult, {dragoverPrevented: true, dropPrevented: true}, 'Dropping files cannot navigate the page');
      assert.equal((await page.locator('#manuscript-file-name').textContent()).trim(), hostileFilename);
      assert.equal(await page.locator('#manuscript-file-name img').count(), 0, 'A filename stays inert text');
      assert.equal(submissions.length, beforeSelection, 'Dropping a manuscript does not upload it');

      // Invalid inputs must keep the last valid selection available for explicit retry.
      for (const invalidFiles of [
        [{name: 'scan.pdf', type: 'application/pdf', content: '%PDF-synthetic'}],
        [],
        [{name: 'one.md', content: 'One'}, {name: 'two.txt', content: 'Two'}],
      ]) {
        const outcome = await dropFiles(page, invalidFiles);
        assert.equal(outcome.dropPrevented, true);
        assert.equal((await page.locator('#manuscript-file-name').textContent()).trim(), hostileFilename);
        assert.equal(await loadButton.isDisabled(), false);
        assert.equal(submissions.length, beforeSelection);
        if (invalidFiles.length) {
          assert.ok((await page.locator('#ctl-status').textContent()).includes(fixtures.en.labels.manuscript_file_invalid), 'Rejected file types have a clear localized explanation');
        }
      }
      assert.equal(page.url(), 'http://lixity.test/');

      response = {ok: false, message: 'Synthetic duplicate filename', reload: false};
      let releaseLoad;
      pendingLoad = new Promise(resolve => {releaseLoad = resolve;});
      await Promise.all([page.waitForRequest(request => request.url().endsWith('/api/load')), loadButton.click()]);
      assert.equal(await loadButton.isDisabled(), true, 'The load action cannot be submitted twice while running');
      assert.equal(await loadButton.getAttribute('aria-busy'), 'true');
      assert.deepEqual(submissions.at(-1), {name: hostileFilename, content: syntheticContent}, 'The existing load contract preserves the selected filename and decoded text');
      releaseLoad();
      pendingLoad = null;
      await page.waitForFunction(() => document.querySelector('#ctl-status').textContent.includes('Synthetic duplicate filename'));
      assert.equal(await loadButton.isDisabled(), false, 'A failed load can be retried');
      assert.equal((await page.locator('#manuscript-file-name').textContent()).trim(), hostileFilename);
      response = {ok: true, message: 'Synthetic manuscript loaded', reload: false};
      await Promise.all([page.waitForResponse(result => result.url().endsWith('/api/load')), loadButton.click()]);
      await page.waitForFunction(() => document.querySelector('#ctl-status').textContent.includes('Synthetic manuscript loaded'));
      assert.deepEqual(submissions.at(-1), {name: hostileFilename, content: syntheticContent});
      assert.equal(await loadButton.isDisabled(), false);

      const nda = page.locator('#nda-manager');
      assert.equal(await nda.evaluate(element => element.tagName), 'DETAILS');
      assert.equal(await nda.evaluate(element => element.open), false, 'The NDA manager starts collapsed');
      const summary = nda.locator('summary');
      assert.ok((await summary.textContent()).includes(fixtures.en.labels.nda_accordion));
      await summary.focus();
      await page.keyboard.press('Enter');
      assert.equal(await nda.evaluate(element => element.open), true);
      assert.ok(await page.locator('#nda-unlock-btn').isVisible());
      await summary.focus();
      await page.keyboard.press('Space');
      assert.equal(await nda.evaluate(element => element.open), false);
      await summary.click();
      await page.evaluate(() => ndaRender([{id: '" data-injected="yes', name: '<img src=x onerror="window.ndaInjected=1">', contact: '<script>bad()</script>', pdf: '<svg onload="window.ndaInjected=1">', status: 'entwurf'}]));
      assert.equal(await page.locator('#nda-table img, #nda-table script, #nda-table svg, #nda-table [data-injected]').count(), 0);
      assert.equal(await page.locator('#nda-table [data-nda-export]').getAttribute('data-nda-export'), '" data-injected="yes');
      assert.ok((await page.locator('#nda-table').textContent()).includes('<img src=x'));
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `No page overflow at ${width}px`);
      await page.locator('#controls').screenshot({path: path.join(screenshotDir, `controls-${width}.png`)});
      await nda.screenshot({path: path.join(screenshotDir, `nda-${width}.png`)});
    }

    if (!readStateOnly) {
      // Embeddings may link to analysis from another pane through the shared hook.
      await page.locator('#tab-view-project').click();
      await page.locator('#view-pane-project').evaluate(element => {
        const button = document.createElement('button');
        button.type = 'button';
        button.dataset.jump = '#ch-1';
        button.textContent = 'Review synthetic chapter';
        element.appendChild(button);
      });
      await page.getByRole('button', {name: 'Review synthetic chapter'}).click();
      assert.equal(await page.locator('#tab-view-analysis').getAttribute('aria-selected'), 'true', 'A cross-view chapter link reveals the analysis pane');
      assert.ok(await page.locator('#ch-1').isVisible());
    }

    // Selecting another file during the read phase cannot start a second load.
    await page.goto('http://lixity.test/');
    await page.locator('#tab-view-project').click();
    await page.locator('#ms-file').setInputFiles({name: 'reading-a.md', mimeType: 'text/markdown', buffer: Buffer.from(syntheticContent)});
    await holdFileReadCompletions(page);
    const beforeRead = submissions.length;
    await page.locator('[data-action="load"]').click();
    assert.equal(await page.locator('[data-action="load"]').getAttribute('aria-busy'), 'true', 'The load action is busy while reading the file');
    await page.locator('#ms-file').setInputFiles({name: 'reading-b.md', mimeType: 'text/markdown', buffer: Buffer.from('## New selection\n\nB content.\n')});
    assert.equal(await page.locator('[data-action="load"]').isDisabled(), true, 'A new selection cannot unlock an in-flight read');
    assert.equal(submissions.length, beforeRead);
    await releaseFileRead(page, 0);
    await page.waitForFunction(() => document.querySelector('#ctl-status').textContent.includes('Synthetic manuscript loaded'));
    assert.equal(submissions.length, beforeRead + 1);
    assert.deepEqual(submissions.at(-1), {name: 'reading-a.md', content: syntheticContent});
    assert.equal(await page.locator('[data-action="load"]').isDisabled(), false);
    await restoreFileReads(page);

    await page.setViewportSize({width: 320, height: 900});
    for (language of readStateOnly ? [] : Object.keys(fixtures)) {
      await page.goto('http://lixity.test/');
      await page.locator('#tab-view-project').click();
      assert.equal(await page.locator('#nda-manager').evaluate(element => element.open), false);
      assert.ok((await page.locator('#nda-manager summary').textContent()).includes(fixtures[language].labels.nda_accordion), `Localized NDA summary: ${language}`);
      await dropFiles(page, [{name: 'scan.pdf', type: 'application/pdf', content: '%PDF-synthetic'}]);
      assert.ok((await page.locator('#ctl-status').textContent()).includes(fixtures[language].labels.manuscript_file_invalid), `Localized rejected-file explanation: ${language}`);
      assert.equal(await page.locator('[data-action="load"]').isDisabled(), true);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `No page overflow: ${language}`);
      await page.locator('#controls').screenshot({path: path.join(screenshotDir, `controls-${language}-320.png`)});
    }

    isStandalone = true;
    for (const width of readStateOnly ? [] : [1440, 320]) {
      await page.setViewportSize({width, height: 900});
      await page.goto('http://lixity.test/');
      await page.locator('#tab-view-project').click();
      assert.equal(await page.locator('#ms-file, [data-action="load"]').count(), 0, 'Standalone hosts retain their advertised action boundary');
      assert.equal(await page.locator('#manuscript-import-btn').isDisabled(), true);
      const beforeImport = posts.length;
      await page.locator('#manuscript-import-file').setInputFiles({name: 'standalone.md', mimeType: 'text/markdown', buffer: Buffer.from(syntheticContent)});
      assert.equal((await page.locator('#manuscript-file-name').textContent()).trim(), 'standalone.md');
      assert.equal(await page.locator('#manuscript-import-btn').isDisabled(), false);
      await dropFiles(page, [{name: 'standalone-dropped.txt', content: syntheticContent}]);
      assert.equal(posts.length, beforeImport, 'Standalone selection stays local until explicit dialog submission');
      await page.locator('#manuscript-import-btn').click();
      await page.waitForFunction(() => document.querySelector('#import-fpc-filename').textContent === 'standalone-dropped.txt');
      assert.ok(await page.locator('#modal-project-create').isVisible());
      assert.equal(await page.locator('#tab-btn-import').getAttribute('aria-selected'), 'true');
      assert.ok(await page.locator('#import-preview-box').isVisible());
      assert.equal(await page.locator('#import-proj-lang').inputValue(), 'en', 'Import starts with the current analysis language');
      await page.locator('#import-proj-title').fill('Synthetic import review');
      await page.locator('#import-proj-lang').selectOption('fr');
      await page.locator('#import-proj-path').fill('/tmp/synthetic-review-project');
      await page.locator('#import-proj-research').check();
      assert.equal(await page.locator('#btn-submit-import-project').isDisabled(), false);
      assert.equal(posts.length, beforeImport, 'Editing import options cannot mutate the project');
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Standalone import has no overflow at ${width}px`);
      await page.locator('#modal-project-create').screenshot({path: path.join(screenshotDir, `standalone-import-${width}.png`)});
      await page.locator('#form-project-import [data-close-modal]').click();
      assert.equal(await page.locator('#modal-project-create').isVisible(), false);
      assert.equal(posts.length, beforeImport, 'Cancelling the import leaves the project untouched');
    }

    // A cancelled preview must not remain confirmable while another file reads.
    await page.goto('http://lixity.test/');
    await page.locator('#tab-view-project').click();
    await page.locator('#manuscript-import-file').setInputFiles({name: 'preview-a.md', mimeType: 'text/markdown', buffer: Buffer.from(syntheticContent)});
    await page.locator('#manuscript-import-btn').click();
    await page.waitForFunction(() => document.querySelector('#import-fpc-filename').textContent === 'preview-a.md');
    await page.locator('#form-project-import [data-close-modal]').click();
    const beforePendingImport = posts.length;
    await page.locator('#manuscript-import-file').setInputFiles({name: 'preview-b.md', mimeType: 'text/markdown', buffer: Buffer.from('## Pending B\n\nB content.\n')});
    await holdFileReadCompletions(page);
    await page.locator('#manuscript-import-btn').click();
    assert.equal(await page.locator('#btn-submit-import-project').isDisabled(), true, 'Previous import content cannot be confirmed during a new read');
    assert.equal(await page.locator('#import-preview-box').isVisible(), false);
    assert.equal(await page.evaluate(() => importedFileContent), '');
    // A platform read error cannot revive the previous successful preview.
    await page.evaluate(() => window.projectControlReads[0].reader.dispatchEvent(new ProgressEvent('error')));
    assert.equal(await page.locator('#btn-submit-import-project').isDisabled(), true);
    assert.ok((await page.locator('#import-project-status').textContent()).includes(fixtures.en.labels.manuscript_read_failed));
    assert.equal(await page.locator('#import-preview-box').isVisible(), false);
    assert.equal(await page.evaluate(() => importedFileContent), '');
    const contentB = '## Retry B\n\nNew B content.\n';
    const contentC = '## Latest C\n\nNew C content.\n';
    await page.locator('#import-file-input').setInputFiles({name: 'retry-b.md', mimeType: 'text/markdown', buffer: Buffer.from(contentB)});
    await page.locator('#import-file-input').setInputFiles({name: 'latest-c.md', mimeType: 'text/markdown', buffer: Buffer.from(contentC)});
    await releaseFileRead(page, 2);
    assert.equal((await page.locator('#import-fpc-filename').textContent()).trim(), 'latest-c.md');
    assert.equal(await page.evaluate(() => importedFileContent), contentC);
    await releaseFileRead(page, 1);
    assert.equal((await page.locator('#import-fpc-filename').textContent()).trim(), 'latest-c.md', 'A slower obsolete read cannot replace the latest selection');
    assert.equal(await page.evaluate(() => importedFileContent), contentC);
    assert.equal(await page.locator('#btn-submit-import-project').isDisabled(), false);
    assert.equal(posts.length, beforePendingImport);
    await restoreFileReads(page);
    // A new file choice cannot replace or unlock an import already being saved.
    let releaseCreate;
    pendingCreate = new Promise(resolve => {releaseCreate = resolve;});
    await Promise.all([page.waitForRequest(request => request.url().endsWith('/api/project-create')), page.locator('#btn-submit-import-project').click()]);
    assert.equal(await page.locator('#btn-submit-import-project').isDisabled(), true);
    await page.locator('#import-file-input').setInputFiles({name: 'pending-replacement.md', mimeType: 'text/markdown', buffer: Buffer.from(contentB)});
    assert.equal(await page.locator('#btn-submit-import-project').isDisabled(), true);
    assert.equal((await page.locator('#import-fpc-filename').textContent()).trim(), 'latest-c.md');
    assert.equal(await page.evaluate(() => importedFileContent), contentC);
    assert.equal(projectSubmissions.length, 1);
    assert.equal(projectSubmissions[0].content, contentC);
    releaseCreate();
    pendingCreate = null;
    await page.waitForFunction(() => document.querySelector('#import-project-status').textContent.includes('Synthetic import rejected'));
    assert.equal(await page.locator('#btn-submit-import-project').isDisabled(), false);
    await page.locator('#import-file-input').setInputFiles({name: 'retry-after-save.md', mimeType: 'text/markdown', buffer: Buffer.from(contentB)});
    await page.waitForFunction(() => document.querySelector('#import-fpc-filename').textContent === 'retry-after-save.md');
    assert.equal(await page.evaluate(() => importedFileContent), contentB);
    assert.equal(projectSubmissions.length, 1);
    await page.locator('#form-project-import [data-close-modal]').click();
    // The reused dialog keeps its own file chooser reachable by pointer and keyboard.
    await page.locator('#btn-modal-new-project').click();
    const importDropzone = page.locator('#import-dropzone');
    for (const method of ['click', 'Space', 'Enter']) {
      await importDropzone.focus();
      assert.equal(await importDropzone.evaluate(element => document.activeElement === element), true);
      const [chooser] = await Promise.all([
        page.waitForEvent('filechooser'),
        method === 'click' ? importDropzone.click() : page.keyboard.press(method),
      ]);
      assert.deepEqual(errors, [], `The import dialog ${method} file-picker action is error-free`);
      const filename = `dialog-${method.toLowerCase()}.md`;
      await chooser.setFiles({name: filename, mimeType: 'text/markdown', buffer: Buffer.from(syntheticContent)});
      await page.waitForFunction(name => document.querySelector('#import-fpc-filename').textContent === name, filename);
    }
    assert.equal(projectSubmissions.length, 1, 'Using the modal file chooser never submits the import');
    await page.locator('#form-project-import [data-close-modal]').click();
    assert.deepEqual(errors, []);
    console.log(readStateOnly
      ? 'Project controls: pending reads/imports, latest-selection protection, read-error recovery and modal file-picker keyboard access passed'
      : `Project controls: explicit selection/drop/load, keyboard access, pending reads/imports, retry, inert NDA records and seven mobile locales passed; screenshots: ${screenshotDir}`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
