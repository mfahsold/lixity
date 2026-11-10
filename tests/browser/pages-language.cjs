// Exercise real generated pages: suggestions must never replace explicit URLs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const {spawnSync} = require('node:child_process');
const os = require('node:os');
const repository = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-pages-language-'));
const docs = path.join(artifacts, 'site');
const staged = spawnSync(process.env.PYTHON_BIN || path.join(repository, '.venv/bin/python'), ['scripts/stage_pages.py', '--output', docs], {cwd: repository, encoding: 'utf8'});
assert.equal(staged.status, 0, staged.stderr);
const origin = 'https://pages.example';
(async () => {
  const browser = await launchChromium();
  async function open({languages = ['de-DE', 'en'], saved, blocked = false, javaScriptEnabled = true, route = 'index.html', width = 390} = {}) {
    const context = await browser.newContext({javaScriptEnabled, viewport: {width, height: 900}});
    await context.addInitScript(({languages, saved, blocked}) => {
      Object.defineProperty(navigator, 'languages', {get: () => languages});
      if (saved && !localStorage.getItem('lixity-site-language')) localStorage.setItem('lixity-site-language', saved);
      if (blocked) Object.defineProperty(window, 'localStorage', {get() {throw new Error('Storage blocked');}});
    }, {languages, saved, blocked});
    await context.route('**/*', async intercepted => {
      const url = new URL(intercepted.request().url());
      assert.equal(url.origin, origin, 'Language selection makes no external requests');
      const file = path.join(docs, url.pathname.replace(/^\/lixity\//, '') || 'index.html');
      await intercepted.fulfill({path: file});
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${origin}/lixity/${route}`);
    return {context, page, errors};
  }
  try {
    let state = await open();
    await expect(state.page.locator('#language-suggestion')).toBeVisible();
    await expect(state.page.locator('#language-suggestion a')).toHaveAttribute('href', 'index-de.html');
    assert.equal(new URL(state.page.url()).pathname, '/lixity/index.html');
    await state.page.locator('#language-suggestion a').click();
    await expect(state.page.locator('html')).toHaveAttribute('lang', 'de');
    assert.equal(await state.page.evaluate(() => localStorage.getItem('lixity-site-language')), 'de');
    await state.page.goto(`${origin}/lixity/index-fr.html#features`);
    await expect(state.page.locator('html')).toHaveAttribute('lang', 'fr');
    await expect(state.page.locator('#language-suggestion a')).toHaveAttribute('href', 'index-de.html');
    await state.page.locator('#language-suggestion button').click();
    await expect(state.page.locator('#language-suggestion')).toBeHidden();
    await state.page.reload();
    await expect(state.page.locator('#language-suggestion')).toBeHidden();
    assert.equal(await state.page.evaluate(() => localStorage.getItem('lixity-site-language')), 'fr');
    assert.deepEqual(state.errors, []);
    await state.context.close();
    for (const [languages, target] of [[['ja', 'pt-BR'], 'pt'], [['nl-NL'], 'nl'], [['fr-CA'], 'fr']]) {
      state = await open({languages, blocked: true});
      await expect(state.page.locator('#language-suggestion a')).toHaveAttribute('href', `index-${target}.html`);
      await state.page.locator('#language-suggestion button').click();
      await expect(state.page.locator('#language-suggestion')).toBeHidden();
      assert.deepEqual(state.errors, []);
      await state.context.close();
    }
    for (const options of [{languages: ['ja']}, {saved: 'en'}, {languages: ['en-GB']}, {javaScriptEnabled: false}, {route: 'guides/first-look.html'}]) {
      state = await open(options);
      await expect(state.page.locator('#language-suggestion')).toBeHidden();
      if (options.javaScriptEnabled === false) {
        await state.page.locator('.language-picker summary').click();
        await state.page.locator('.language-picker a[lang="de"]').click();
        await expect(state.page.locator('html')).toHaveAttribute('lang', 'de');
      }
      assert.deepEqual(state.errors, []);
      await state.context.close();
    }
    state = await open({saved: 'invalid', languages: ['de']});
    await expect(state.page.locator('#language-suggestion')).toBeVisible();
    await state.page.locator('.language-picker summary').click();
    await state.page.locator('.language-picker a[lang="it"]').click();
    await expect(state.page.locator('html')).toHaveAttribute('lang', 'it');
    assert.equal(await state.page.evaluate(() => localStorage.getItem('lixity-site-language')), 'it');
    await state.context.close();
    for (const language of ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl']) {
      for (const width of [320, 1440]) {
        state = await open({route: language === 'en' ? 'index.html' : `index-${language}.html`, languages: ['de'], width});
        assert.equal(await state.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${language} at ${width}px`);
        await expect(state.page.locator('.language-picker a[aria-current="page"]')).toHaveAttribute('lang', language);
        if (language === 'en' || language === 'de') {
          await state.page.screenshot({path: path.join(artifacts, `${language}-${width}.png`), fullPage: true});
        }
        assert.deepEqual(state.errors, []);
        await state.context.close();
      }
    }
    console.log(`Screenshots: ${artifacts}`);
    console.log('Public language suggestions, saved choices, direct links, storage failure and seven responsive pages passed.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
