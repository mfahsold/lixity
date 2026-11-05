// Browser regression test for Obsidian-style Command Palette and Focus Mode
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { launchChromium } = require('../../scripts/browser_tools.cjs');

(async () => {
  const browser = await launchChromium();
  const context = await browser.newContext();
  const page = await context.newPage();

  const iconsJs = fs.readFileSync('src/lixity/ui/assets/icons.js', 'utf8');
  const paletteJs = fs.readFileSync('src/lixity/ui/assets/command-palette.js', 'utf8');
  const css = fs.readFileSync('src/lixity/ui/assets/components.css', 'utf8');

  await page.setContent(`<!DOCTYPE html>
<html lang="de">
<head>
  <style>${css}</style>
  <script>${iconsJs}</script>
  <script>
    window.LixityWorkbench = {
      _state: { view: "analysis", focus: false },
      state: function() { return this._state; },
      dispatch: function(cmd) {
        if (cmd.type === "view") this._state.view = cmd.value;
        if (cmd.type === "focus") this._state.focus = cmd.value;
      }
    };
  </script>
  <script>${paletteJs}</script>
</head>
<body class="manuscript-reading">
  <div id="workspace">
    <button id="reader-focus" type="button">Focus</button>
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

  // 7. Test Ctrl+P shortcut opens palette
  await page.keyboard.press('Control+p');
  assert.equal(await page.locator('#command-palette-dialog').isVisible(), true, 'Ctrl+P shortcut opens palette');

  // 8. Close with Escape again
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('#command-palette-dialog').isVisible(), false);

  // 9. Test Ctrl+K shortcut opens palette
  await page.keyboard.press('Control+k');
  assert.equal(await page.locator('#command-palette-dialog').isVisible(), true, 'Ctrl+K shortcut opens palette');
  await page.keyboard.press('Escape');

  await browser.close();
  console.log('Command palette browser checks passed successfully.');
})();
