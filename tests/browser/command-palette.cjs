// Browser regression test for Obsidian-style Command Palette and Focus Mode
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { launchChromium, modShortcut } = require('../../scripts/browser_tools.cjs');

(async () => {
  const browser = await launchChromium();
  const context = await browser.newContext();
  const page = await context.newPage();

  const preactJs = fs.readFileSync('src/lixity/ui/assets/vendor/preact-10.29.8.min.js', 'utf8');
  const htmJs = fs.readFileSync('src/lixity/ui/assets/vendor/htm-3.1.1.umd.js', 'utf8');
  const iconsJs = fs.readFileSync('src/lixity/ui/assets/icons.js', 'utf8');
  const componentLayerJs = fs.readFileSync('src/lixity/ui/assets/component-layer.js', 'utf8');
  const paletteJs = fs.readFileSync('src/lixity/ui/assets/command-palette.js', 'utf8');
  const editorJs = fs.readFileSync('src/lixity/ui/assets/markdown-editor.js', 'utf8');
  const css = fs.readFileSync('src/lixity/ui/assets/components.css', 'utf8');

  await page.setContent(`<!DOCTYPE html>
<html lang="de">
<head>
  <style>${css}</style>
  <script>${preactJs}</script>
  <script>${htmJs}</script>
  <script>${iconsJs}</script>
  <script>${componentLayerJs}</script>
  <script>
    window.LixityWorkbench = {
      _state: { view: "analysis", focus: false },
      state: function() { return this._state; },
      dispatch: function(cmd) {
        if (cmd.type === "view") this._state.view = cmd.value;
        if (cmd.type === "focus") this._state.focus = cmd.value;
      }
    };
    window.scrollAndFlash = function(target) { target.dataset.visited = "1"; };
    window.openResearchDossierComposer = function() {
      document.getElementById("r-dos-composer").dataset.visited = "1";
    };
  </script>
  <script>${paletteJs}</script>
  <script>${editorJs}</script>
</head>
<body class="manuscript-reading">
  <div id="workspace">
    <button id="reader-focus" type="button">Focus</button>
    <select id="style-layer"><option value="">None</option><option value="asl">ASL</option><option value="dialogue">Dialogue</option>
      <option value="disabled-metric" disabled>Unavailable fixture metric</option></select>
    <select id="reader-chapter"><option value="">Choose</option><option value="ch-2">Second fixture chapter</option></select>
    <section id="pacing">Rhythm fixture</section>
    <button id="research-tab-search" data-rtab="search" type="button">Search</button>
    <input id="r-search-query" type="search" />
    <button id="research-tab-dossiers" data-rtab="dossiers" type="button">Dossiers</button>
    <details id="r-dos-composer"><summary>New</summary><input id="r-dos-title" type="text" /></details>
    <textarea id="research-notes" aria-label="Research notes"></textarea>
    <div id="content">Reading Area</div>
  </div>
</body>
</html>`);

  // 1. Verify Command Palette is closed initially
  assert.equal(await page.locator('#command-palette-dialog').count(), 0);

  // 2. Open via API
  await page.evaluate(() => window.LixityCommandPalette.open());
  assert.equal(await page.locator('#command-palette-dialog').isVisible(), true, 'Dialog opens via API');

  // 3. Verify search input focused
  const isInputFocused = await page.evaluate(() => document.activeElement.id === 'command-palette-search');
  assert.equal(isInputFocused, true, 'Search input is automatically focused');

  // 4. Check initial results count
  const initialItemsCount = await page.locator('.command-palette-item').count();
  assert.ok(initialItemsCount >= 10, 'Command palette contains at least 10 commands');

  // 5. Test search filter
  await page.fill('#command-palette-search', 'asl');
  const filteredCount = await page.locator('.command-palette-item').count();
  assert.ok(filteredCount >= 1 && filteredCount < initialItemsCount, 'Search filters command list');

  // 6. Test Escape key closes palette
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('#command-palette-dialog').isVisible(), false, 'Escape closes dialog');

  // 7. Test Mod+P shortcut opens palette
  await page.keyboard.press(modShortcut('p'));
  assert.equal(await page.locator('#command-palette-dialog').isVisible(), true, 'Mod+P shortcut opens palette');

  // 8. Close with Escape again
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('#command-palette-dialog').isVisible(), false);

  // 9. Test Mod+K shortcut opens palette
  await page.keyboard.press(modShortcut('k'));
  assert.equal(await page.locator('#command-palette-dialog').isVisible(), true, 'Mod+K shortcut opens palette');
  await page.keyboard.press('Escape');

  // 10. Test command execution reaches real DOM targets
  await page.keyboard.press(modShortcut('k'));
  await page.fill('#command-palette-search', 'Dialoge');
  await page.keyboard.press('Enter');
  assert.equal(await page.locator('#style-layer').inputValue(), 'dialogue', 'Dialogue command selects real #style-layer option');

  await page.keyboard.press(modShortcut('k'));
  await page.fill('#command-palette-search', 'Unavailable fixture metric');
  assert.equal(await page.locator('.command-palette-item').count(), 0, 'Disabled options have no commands');
  await page.fill('#command-palette-search', 'Second fixture chapter');
  await page.keyboard.press('Enter');
  assert.equal(await page.locator('#reader-chapter').inputValue(), 'ch-2', 'The chapter command selects the real chapter option');

  await page.keyboard.press(modShortcut('k'));
  await page.fill('#command-palette-search', 'Scene Tension');
  await page.keyboard.press('Enter');
  assert.equal(await page.locator('#pacing').getAttribute('data-visited'), '1', 'Section command opens its real destination');

  await page.keyboard.press(modShortcut('k'));
  await page.fill('#command-palette-search', 'Suchmaske');
  assert.equal(await page.locator('.command-palette-item-shortcut').count(), 0, 'Research search does not advertise an inactive letter shortcut');
  await page.keyboard.press('Enter');
  assert.equal(await page.evaluate(() => document.activeElement.id), 'r-search-query', 'Research search command focuses #r-search-query');

  await page.keyboard.press(modShortcut('k'));
  await page.fill('#command-palette-search', 'Neues Forschungs-Dossier');
  await page.keyboard.press('Enter');
  assert.equal(await page.locator('#r-dos-composer').getAttribute('data-visited'), '1', 'New dossier command delegates to the research workspace');

  await page.evaluate(() => ['style-layer', 'pacing'].forEach(id => document.getElementById(id).remove()));
  await page.keyboard.press(modShortcut('k'));
  for (const missing of ['Scene Tension', 'Grammatical Tense', 'Highlight Sentence Length']) {
    await page.fill('#command-palette-search', missing);
    assert.equal(await page.locator('.command-palette-item').count(), 0, 'Unavailable destination ' + missing + ' has no command');
  }
  await page.keyboard.press('Escape');
  await page.evaluate(() => LixityMarkdownEditor.mount(document.getElementById('research-notes')));
  const notes = page.locator('#research-notes');
  await notes.fill('source');
  await notes.evaluate(el => el.select());
  await page.keyboard.press(modShortcut('k'));
  assert.equal(await notes.inputValue(), '[source](https://)', 'The focused Markdown editor owns Mod+K');
  assert.equal(await page.locator('#command-palette-dialog').isVisible(), false);
  assert.equal(await page.getByRole('button', {name: 'Link', exact: true}).getAttribute('aria-keyshortcuts'), 'Control+K Meta+K');
  await page.keyboard.press(modShortcut('Shift+k'));
  assert.equal(await page.locator('#command-palette-dialog').isVisible(), false, 'Modified browser or editor chords remain independent');
  await page.keyboard.press(modShortcut('p'));
  assert.equal(await page.locator('#command-palette-dialog').isVisible(), true, 'Mod+P remains available from Markdown');

  await browser.close();
  console.log('Command palette browser checks passed successfully.');
})();
