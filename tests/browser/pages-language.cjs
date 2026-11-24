// Exercise real generated pages: suggestions must never replace explicit URLs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const os = require('node:os');
const {stagePages} = require('./support/staged-pages.cjs');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-pages-language-'));
const docs = stagePages();
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
    const sandbox = 'sandbox/index.html';
    for (const [route, saved, languages, expected] of [
      [sandbox, 'de', ['en'], 'de'],
      [sandbox, 'nl', ['ja', 'de-AT'], 'de'],
      [sandbox + '?lang=en&preset=effi-briest', 'de', ['de'], 'en'],
      [sandbox + '?lang=fr&preset=pride-prejudice', 'de', ['de'], 'en'],
    ]) {
      state = await open({route, saved, languages});
      const {page} = state;
      await expect(page.locator('html')).toHaveAttribute('lang', expected);
      const passage = await page.locator('#input').inputValue();
      const words = await page.locator('#k-words').textContent();
      if (route.includes('preset=effi-briest')) assert.match(passage, /Pfarr-/);
      const next = expected === 'de' ? 'en' : 'de';
      await page.locator('#lang-toggle').click();
      await expect(page.locator('html')).toHaveAttribute('lang', next);
      await expect(page).toHaveTitle(next === 'de' ? /Absatz lokal prüfen/ : /Review a passage locally/);
      assert.equal(new URL(page.url()).searchParams.get('lang'), next);
      await expect(page.locator('#input')).toHaveValue(passage);
      await expect(page.locator('#k-words')).toHaveText(words);
      assert.equal(await page.evaluate(() => localStorage.getItem('lixity-site-language')), saved);
      assert.deepEqual(state.errors, []);
      await state.context.close();
    }
    for (const language of ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl']) {
      for (const width of [320, 1440]) {
        state = await open({route: language === 'en' ? 'index.html' : `index-${language}.html`, languages: ['de'], width});
        assert.equal(await state.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${language} at ${width}px`);
        await expect(state.page.locator('.language-picker a[aria-current="page"]')).toHaveAttribute('lang', language);
        if (language === 'en' || language === 'de') {
          await state.page.screenshot({path: path.join(artifacts, `${language}-${width}.png`), fullPage: true});
        }
        const sandboxLanguage = language === 'de' ? 'de' : 'en';
        const link = state.page.locator('#sandbox-cta');
        await expect(link).toHaveAttribute('hreflang', sandboxLanguage);
        await expect(state.page.locator('.tour-explore')).toHaveAttribute('hreflang', 'en');
        await link.click();
        await expect(state.page).toHaveURL(`${origin}/lixity/${sandbox}?lang=${sandboxLanguage}`);
        await expect(state.page.locator('html')).toHaveAttribute('lang', sandboxLanguage);
        await expect(state.page.locator('#nav-demo')).toHaveAttribute('hreflang', 'en');
        assert.deepEqual(state.errors, []);
        await state.context.close();
      }
    }
    console.log(`Screenshots: ${artifacts}`);
    console.log('Public language suggestions, Sandbox language and preset links, storage failure and seven responsive pages passed.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
