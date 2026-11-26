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
const homeWidths = [
  {width: 320, height: 568, hasTouch: true},
  {width: 1440, height: 900},
];
const extraHomeWidths = [
  {width: 390, height: 844, hasTouch: true},
  {width: 768, height: 1024, hasTouch: true},
  {width: 1024, height: 768},
  {width: 2560, height: 1440},
];

async function checkHomeGeometry(page, description) {
  const geometryIssues = await page.evaluate(() => {
    const issues = [];
    if (document.documentElement.scrollWidth > innerWidth) issues.push('page');
    const header = document.querySelector('.header-inner').getBoundingClientRect();
    const intro = document.querySelector('.home-intro').getBoundingClientRect();
    if (Math.abs(header.left - intro.left) > 1 || Math.abs(header.right - intro.right) > 1) {
      issues.push('homepage gutters');
    }
    const actionable = '.header-inner .brand, .home-nav a, .language-picker summary, .header-inner button, .hero-cta a, #support-cta';
    const actions = [...document.querySelectorAll(actionable)].filter(element => element.getClientRects().length);
    const controls = [
      ...actions,
      ...document.querySelectorAll('.language-picker[open] nav, .language-picker[open] a, .home-intro h1, .home-support'),
    ];
    for (const element of controls) {
      const {left, right} = element.getBoundingClientRect();
      if (left < -1 || right > innerWidth + 1 || element.scrollWidth > element.clientWidth + 1) {
        issues.push(element.textContent.trim());
      }
    }
    const actionBoxes = actions.map(element => element.getBoundingClientRect());
    for (const [index, a] of actionBoxes.entries()) {
      const overlap = actionBoxes.slice(index + 1).some(b =>
        Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 &&
        Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1);
      if (overlap) issues.push(`overlap at ${actions[index].textContent.trim()}`);
    }
    return issues;
  });
  assert.deepEqual(geometryIssues, [], `Clipping or overlapping controls in ${description}`);
}

async function checkSupportContact(page) {
  await expect(page).toHaveURL(`${origin}/lixity/guides/support.html`);
  const contact = page.getByRole('link', {name: 'info@rost-services.de'});
  await expect(contact).toBeVisible();
  await expect(contact).toHaveAttribute('href', 'mailto:info@rost-services.de');
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
}

(async () => {
  const browser = await launchChromium();
  async function open({languages = ['de-DE', 'en'], saved, blocked = false, javaScriptEnabled = true, route = 'index.html', width = 390, height = 900, hasTouch = false} = {}) {
    const context = await browser.newContext({javaScriptEnabled, hasTouch, viewport: {width, height}});
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
        await state.page.locator('#support-cta').press('Enter');
        await checkSupportContact(state.page);
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
      const reviewLocale = language === 'en' || language === 'de';
      const widths = reviewLocale ? [...homeWidths, ...extraHomeWidths] : homeWidths;
      for (const viewport of widths) {
        const {width, height, hasTouch} = viewport;
        state = await open({route: language === 'en' ? 'index.html' : `index-${language}.html`,
          languages: [language], ...viewport});
        const {page} = state;
        const description = `${language} at ${width}×${height}`;
        await checkHomeGeometry(page, description);
        await expect(page.locator('.language-picker a[aria-current="page"]')).toHaveAttribute('lang', language);
        if (width === 320) {
          const preference = page.locator('.language-picker summary');
          await page.locator('.header-inner .brand').press('Tab');
          await expect(preference).toBeFocused();
          await preference.press('Tab');
          await expect(page.locator('#themeToggle')).toBeFocused();
          await page.locator('#themeToggle').press('Tab');
          await expect(page.locator('.home-nav a').first()).toBeFocused();
        }
        if (reviewLocale && (width === 320 || width === 1440)) {
          await page.screenshot({path: path.join(artifacts, `${language}-${width}.png`), fullPage: true});
        }
        const support = page.locator('main #support-cta');
        await expect(support).toBeVisible();
        await expect(support).toHaveAttribute('href', 'guides/support.html');
        const buttonBox = await support.boundingBox();
        const videoBox = await page.locator('#product-tour-preview').boundingBox();
        assert.ok(buttonBox.y + buttonBox.height <= videoBox.y, `Support precedes the tour in ${description}`);
        assert.ok(buttonBox.y + buttonBox.height <= (width < 480 ? 2 * height : height),
          `Support within the opening content in ${description}`);
        if (hasTouch) assert.ok(buttonBox.height >= 44, `Support touch target in ${description}`);
        await expect(page.locator('.home-footer a[href="guides/support.html"]')).toHaveCount(1);
        if (width === 390 || width === 768) {
          await page.locator('.language-picker summary').click();
          await checkHomeGeometry(page, `${description} with the language menu open`);
          await page.locator('.language-picker summary').click();
        }
        if (width === 390) {
          await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
          await checkHomeGeometry(page, `${description} at 200% text size`);
          await page.locator('.language-picker summary').click();
          await checkHomeGeometry(page, `${description} with the language menu open at 200% text size`);
          await page.locator('.language-picker summary').click();
          await page.evaluate(() => { document.documentElement.style.fontSize = ''; });
        }
        await page.locator('#examples').press('Tab');
        await expect(support).toBeFocused();
        await support.press('Enter');
        await checkSupportContact(page);
        if (homeWidths.includes(viewport)) {
          await page.goBack();
          const sandboxLanguage = language === 'de' ? 'de' : 'en';
          await expect(page.locator('.home-intro :is(.home-example-finding, #sandbox-cta)')).toHaveCount(0);
          await expect(page.locator('#measurement-context .home-example-finding')).toBeVisible();
          const features = await page.locator('#features').boundingBox();
          const measurement = await page.locator('#measurement-context').boundingBox();
          assert.ok(measurement.y >= features.y + features.height, `Example follows the features in ${description}`);
          const link = page.locator('#measurement-context #sandbox-cta');
          await expect(link).toHaveAttribute('hreflang', sandboxLanguage);
          await expect(page.locator('.tour-explore')).toHaveAttribute('hreflang', 'en');
          await link.click();
          await expect(page).toHaveURL(`${origin}/lixity/${sandbox}?lang=${sandboxLanguage}`);
          await expect(page.locator('html')).toHaveAttribute('lang', sandboxLanguage);
          await expect(page.locator('#nav-demo')).toHaveAttribute('hreflang', 'en');
        }
        assert.deepEqual(state.errors, []);
        await state.context.close();
      }
    }
    state = await open({route: 'blog/index.html', width: 768, height: 1024});
    await state.page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
    const featuredArticle = state.page.locator('.blog-featured');
    await expect(featuredArticle).toBeVisible();
    const blogOverflow = await featuredArticle.evaluate(article => {
      const card = article.getBoundingClientRect();
      const grid = article.parentElement.getBoundingClientRect();
      return Math.max(document.documentElement.scrollWidth - innerWidth,
        grid.left - card.left, card.right - grid.right, article.scrollWidth - article.clientWidth);
    });
    assert.ok(blogOverflow <= 1, `Blog cards fit 768px at 200% text size (${blogOverflow}px overflow)`);
    assert.deepEqual(state.errors, []);
    await state.context.close();
    console.log(`Screenshots: ${artifacts}`);
    console.log('Public language suggestions, Sandbox presets, funding contact, storage failure and 320–2560px layouts passed, including enlarged blog text.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
