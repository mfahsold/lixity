// Browser verification of the Lixity Markdown Editor component.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { launchChromium } = require('../../scripts/browser_tools.cjs');

(async () => {
  const browser = await launchChromium();
  const context = await browser.newContext();
  const page = await context.newPage();

  const iconsJs = fs.readFileSync('src/lixity/ui/assets/icons.js', 'utf8');
  const editorJs = fs.readFileSync('src/lixity/ui/assets/markdown-editor.js', 'utf8');
  const css = fs.readFileSync('src/lixity/ui/assets/components.css', 'utf8');

  await page.setContent(`<!DOCTYPE html>
<html>
<head>
  <style>${css}</style>
  <script>${iconsJs}</script>
  <script>${editorJs}</script>
</head>
<body>
  <div id="container">
    <label for="body-field">Body</label>
    <textarea id="body-field" class="ctl" rows="8"></textarea>
  </div>
</body>
</html>`);

  // Mount editor
  const mounted = await page.evaluate(() => {
    const ta = document.getElementById('body-field');
    const editor = window.LixityMarkdownEditor.mount(ta);
    return Boolean(editor && editor.wrap && ta.closest('.markdown-editor-wrap'));
  });
  assert.ok(mounted, 'Markdown editor wraps the textarea');

  // Verify toolbar buttons exist and use icons
  const toolCount = await page.locator('.editor-tool-btn').count();
  assert.ok(toolCount >= 10, 'Editor toolbar has at least 10 formatting buttons');

  // Type text into textarea and check stats footer
  await page.locator('#body-field').fill('Hello Lixity world');
  const statsText = await page.locator('.editor-stats').textContent();
  assert.ok(statsText.includes('3 words'), 'Stats footer counts words');
  assert.ok(statsText.includes('18 chars'), 'Stats footer counts characters');

  // Test bold tool
  await page.evaluate(() => {
    const ta = document.getElementById('body-field');
    ta.selectionStart = 6;
    ta.selectionEnd = 12; // "Lixity"
    const boldBtn = document.querySelector('.editor-tool-btn[title*="Bold"]');
    boldBtn.click();
  });

  const valueAfterBold = await page.locator('#body-field').inputValue();
  assert.equal(valueAfterBold, 'Hello **Lixity** world', 'Bold button wraps selected text with **');

  // Test wikilink tool
  await page.evaluate(() => {
    const ta = document.getElementById('body-field');
    ta.selectionStart = 17;
    ta.selectionEnd = 22; // "world"
    const wikiBtn = document.querySelector('.editor-tool-btn[title*="Wikilink"]');
    wikiBtn.click();
  });

  const valueAfterWiki = await page.locator('#body-field').inputValue();
  assert.equal(valueAfterWiki, 'Hello **Lixity** [[world]]', 'Wikilink button wraps selected text with [[ ]]');

  // Test keyboard shortcut Ctrl+B
  await page.evaluate(() => {
    const ta = document.getElementById('body-field');
    ta.selectionStart = 0;
    ta.selectionEnd = 5; // "Hello"
    const evt = new KeyboardEvent('keydown', { key: 'b', ctrlKey: true, bubbles: true });
    ta.dispatchEvent(evt);
  });
  const valueAfterCtrlB = await page.locator('#body-field').inputValue();
  assert.equal(valueAfterCtrlB, '**Hello** **Lixity** [[world]]', 'Ctrl+B shortcut wraps selected text');

  await browser.close();
  console.log('Markdown editor browser tests passed successfully.');
})().catch(err => {
  console.error(err);
  process.exit(1);
});
