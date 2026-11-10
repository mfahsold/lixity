// Exercise actual media decoding, localized captions and deliberate playback.
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(require('node:path').join(playwrightModule, 'test'));
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const repository = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-home-tour-'));
const root = path.join(artifacts, 'site');
assert.equal(spawnSync(path.join(repository, '.venv/bin/python'), ['scripts/stage_pages.py', '--output', root], {cwd: repository}).status, 0);
(async () => {
  const browser = await launchChromium();
  try {
    for (const width of [1440, 390]) {
      const context = await browser.newContext({viewport: {width, height: 950}, reducedMotion: 'reduce'});
      await context.route('https://tour.test/**', route => {
        const name = new URL(route.request().url()).pathname.slice(1) || 'index.html';
        const file = path.resolve(root, name);
        assert.ok(file.startsWith(root + path.sep));
        const bytes = fs.readFileSync(file);
        const range = /^bytes=(\d+)-(\d*)$/.exec(route.request().headers().range || '');
        const start = range ? Number(range[1]) : 0;
        const end = range && range[2] ? Math.min(Number(range[2]), bytes.length - 1) : bytes.length - 1;
        return route.fulfill({status: range ? 206 : 200,
          headers: {'Accept-Ranges': 'bytes', ...(range ? {'Content-Range': `bytes ${start}-${end}/${bytes.length}`} : {})},
          body: bytes.subarray(start, end + 1), contentType: {
          '.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.png':'image/png',
          '.mp4':'video/mp4', '.webm':'video/webm', '.webp':'image/webp', '.json':'application/json',
        }[path.extname(file)] || 'application/octet-stream'});
      });
      const page = await context.newPage();
      const errors = []; page.on('pageerror', e => errors.push(e.message));
      await page.goto('https://tour.test/index-de.html');
      await expect(page.locator('.hero-cta a')).toHaveCount(1);
      await expect(page.locator('.hero-cta a')).toHaveAttribute('href', '#product-tour-preview');
      assert.equal(await page.locator('h1').evaluate(node => getComputedStyle(node).hyphens), 'none');
      const video = page.locator('#product-tour');
      await video.scrollIntoViewIfNeeded();
      await page.waitForTimeout(700);
      assert.ok(await video.evaluate(v => v.paused && v.currentTime === 0), 'Reduced motion never autoplays');
      const button = page.locator('.tour-toggle');
      await button.click();
      await expect.poll(() => video.evaluate(v => v.currentTime)).toBeGreaterThan(.2);
      await expect(button).toHaveText('Rundgang pausieren');
      await button.click();
      await expect.poll(() => video.evaluate(v => v.paused)).toBe(true);
      await video.evaluate(v => { v.currentTime = 26; });
      await expect(page.locator('.tour-caption')).toHaveText('Notizen und Belege zusammenhalten.');
      await expect.poll(() => video.evaluate(v => ({seeking:v.seeking, ready:v.readyState}))).toEqual({seeking:false, ready:4});
      await expect(page.locator('.tour-caption')).toBeVisible();
      await page.locator('#tour-transcript summary').click();
      await expect(page.locator('#tour-transcript li')).toHaveCount(6);
      await page.locator('#tour-transcript summary').click();
      await page.locator('.product-tour').screenshot({path: path.join(artifacts, `tour-${width}.png`)});
      const caption = await page.locator('.tour-caption').boundingBox();
      const frame = await video.boundingBox();
      assert.ok(caption.x >= frame.x && caption.x + caption.width <= frame.x + frame.width + 1);
      await button.click();
      await page.locator('#impressum').scrollIntoViewIfNeeded();
      await expect.poll(() => video.evaluate(v => v.paused)).toBe(true);
      await video.scrollIntoViewIfNeeded();
      await page.waitForTimeout(500);
      assert.ok(await video.evaluate(v => v.paused), 'A pause is not undone on re-entry');
      // A fresh, unrestricted visit can autoplay once, but respects later pause.
      await page.emulateMedia({reducedMotion: 'no-preference'});
      await page.goto('https://tour.test/');
      await video.scrollIntoViewIfNeeded();
      await expect.poll(() => video.evaluate(v => v.currentTime)).toBeGreaterThan(.2);
      await video.evaluate(v => { v.currentTime = 8.35; });
      await expect.poll(() => video.evaluate(v => ({seeking:v.seeking, ready:v.readyState}))).toEqual({seeking:false, ready:4});
      await expect.poll(() => page.locator('.tour-caption [data-letter]').evaluateAll(nodes =>
        nodes.filter(node => getComputedStyle(node).visibility === 'visible').length)).toBeGreaterThan(0);
      assert.ok(await page.locator('.tour-caption [data-letter]').evaluateAll(nodes =>
        nodes.some(node => getComputedStyle(node).visibility === 'hidden')), 'Caption types in progressively');
      await page.emulateMedia({reducedMotion: 'reduce'});
      // Media-query changes are asynchronous; a fully visible caption alone can
      // precede the pause handler, letting Chromium coalesce the next preference.
      await expect.poll(() => video.evaluate(v => v.paused)).toBe(true);
      await expect(button).toHaveText('Play tour');
      await expect.poll(() => page.locator('.tour-caption [data-letter]').evaluateAll(nodes =>
        nodes.every(node => getComputedStyle(node).visibility === 'visible'))).toBe(true);
      await page.emulateMedia({reducedMotion: 'no-preference'});
      await button.click();
      await expect.poll(() => video.evaluate(v => v.paused)).toBe(false);
      await button.click();
      await expect.poll(() => video.evaluate(v => v.paused)).toBe(true);
      // Exercise real source exhaustion, not an invented media-element event.
      await page.route('**/videos/product-tour.*', route => /\.(mp4|webm)$/.test(route.request().url())
        ? route.abort() : route.fallback());
      await page.goto('https://tour.test/');
      await video.scrollIntoViewIfNeeded();
      await expect(page.locator('.tour-error')).toBeVisible();
      await expect(page.locator('.tour-caption')).toBeHidden();
      await page.unroute('**/videos/product-tour.*');
      await page.route('**/videos/product-tour.webm', route => route.abort());
      await page.goto('https://tour.test/');
      await video.scrollIntoViewIfNeeded();
      await expect.poll(() => video.evaluate(v => v.currentTime)).toBeGreaterThan(.2);
      assert.ok((await video.evaluate(v => v.currentSrc)).endsWith('.mp4'), 'AV1 failure falls back to H.264');
      await expect(page.locator('.tour-error')).toBeHidden();
      assert.deepEqual(errors, []);
      await context.close();
    }
    console.log('Homepage tour: actual playback, reduced motion, pause/offscreen, seeking, DE/EN captions, mobile layout and failure fallback passed. Screenshots: ' + artifacts);
  } finally { await browser.close(); fs.rmSync(root, {recursive:true, force:true}); }
})().catch(e => { console.error(e); process.exitCode=1; });
