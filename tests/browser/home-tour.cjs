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
const staged = spawnSync(process.env.PYTHON_BIN || path.join(repository, '.venv/bin/python'),
  ['scripts/stage_pages.py', '--output', root], {cwd: repository, encoding: 'utf8'});
if (staged.error) throw staged.error;
assert.equal(staged.status, 0, staged.stderr);
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
      await expect(page.locator('.hero-cta a')).toHaveCount(2);
      await expect(page.locator('.hero-cta a').first()).toHaveAttribute('href', '#product-tour-preview');
      await expect(page.locator('.hero-cta a').nth(1)).toHaveAttribute('href', 'sandbox/index.html');
      assert.equal(await page.locator('h1').evaluate(node => getComputedStyle(node).hyphens), 'none');
      const video = page.locator('#product-tour');
      assert.deepEqual(await page.locator('#tour-transcript li').evaluateAll(nodes =>
        nodes.map(node => Number(node.dataset.start))), [0, 8, 16, 24, 32, 40],
      'Caption boundaries must match the six eight-second scenes');
      await video.scrollIntoViewIfNeeded();
      await page.waitForTimeout(700);
      assert.ok(await video.evaluate(v => v.paused && v.currentTime === 0), 'Reduced motion never autoplays');
      const button = page.locator('.tour-toggle');
      await button.click();
      await expect.poll(() => video.evaluate(v => v.currentTime)).toBeGreaterThan(.2);
      await expect(button).toHaveText('Rundgang pausieren');
      await button.click();
      await expect.poll(() => video.evaluate(v => v.paused), {timeout: 15000}).toBe(true);
      await video.evaluate(v => { v.currentTime = 22; });
      await expect(page.locator('.tour-caption')).toHaveText(await page.locator('#tour-transcript li').nth(2).textContent());
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
      await expect.poll(() => video.evaluate(v => v.paused), {timeout: 15000}).toBe(true);
      await video.scrollIntoViewIfNeeded();
      await page.waitForTimeout(500);
      assert.ok(await video.evaluate(v => v.paused), 'A pause is not undone on re-entry');
      // A fresh, unrestricted visit can autoplay once, but respects later pause.
      await page.emulateMedia({reducedMotion: 'no-preference'});
      await page.goto('https://tour.test/');
      await video.scrollIntoViewIfNeeded();
      await expect.poll(() => video.evaluate(v => v.currentTime)).toBeGreaterThan(.2);
      await video.evaluate(v => { v.currentTime = 8.1; });
      await expect.poll(() => video.evaluate(v => ({seeking:v.seeking, ready:v.readyState}))).toEqual({seeking:false, ready:4});
      await expect(page.locator('.tour-caption')).toHaveText(await page.locator('#tour-transcript li').nth(1).textContent());
      assert.ok(await page.locator('.tour-caption span').evaluateAll(nodes =>
        nodes.every(node => getComputedStyle(node).visibility === 'visible')),
      'The complete caption remains readable while the video moves');
      await page.emulateMedia({reducedMotion: 'reduce'});
      // Media-query changes are asynchronous; a fully visible caption alone can
      // precede the pause handler, letting Chromium coalesce the next preference.
      await expect.poll(() => video.evaluate(v => v.paused), {timeout: 15000}).toBe(true);
      await expect(button).toHaveText('Play tour');
      await expect.poll(() => page.locator('.tour-caption span').evaluateAll(nodes =>
        nodes.every(node => getComputedStyle(node).visibility === 'visible'))).toBe(true);
      // Reduced motion stops automatic playback, but an explicit choice can play.
      const reducedStart = await video.evaluate(v => v.currentTime);
      await button.click();
      await expect.poll(() => video.evaluate(v => v.currentTime)).toBeGreaterThan(reducedStart + .1);
      await expect(button).toHaveText('Pause tour');
      await expect.poll(() => page.locator('.tour-caption span').evaluateAll(nodes =>
        nodes.every(node => getComputedStyle(node).visibility === 'visible'))).toBe(true);
      await button.click();
      await expect.poll(() => video.evaluate(v => v.paused), {timeout: 15000}).toBe(true);
      // Rapid media changes can be coalesced; none may undo an intentional pause.
      await page.emulateMedia({reducedMotion: 'no-preference'});
      await page.emulateMedia({reducedMotion: 'reduce'});
      await page.emulateMedia({reducedMotion: 'no-preference'});
      await page.evaluate(() => new Promise(resolve =>
        requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.ok(await video.evaluate(v => v.paused), 'Preference changes never resume an intentional pause');
      await button.click();
      await expect.poll(() => video.evaluate(v => v.paused)).toBe(false);
      await button.click();
      await expect.poll(() => video.evaluate(v => v.paused), {timeout: 15000}).toBe(true);
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
      // Every localized caption uses the same decoded media timeline.
      await page.emulateMedia({reducedMotion: 'reduce'});
      for (const language of ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl']) {
        await page.goto('https://tour.test/' + (language === 'en' ? 'index.html' : `index-${language}.html`));
        await video.scrollIntoViewIfNeeded();
        await button.click();
        await expect.poll(() => video.evaluate(v => v.currentTime)).toBeGreaterThan(.1);
        await button.click();
        await expect.poll(() => video.evaluate(v => v.paused)).toBe(true);
        assert.ok(Math.abs(await video.evaluate(v => v.duration) - 48) <= .04,
          'The complete six-scene tour must decode to 48 seconds');
        const cues = await page.locator('#tour-transcript li').evaluateAll(nodes =>
          nodes.map(node => ({start: Number(node.dataset.start), text: node.textContent})));
        assert.deepEqual(cues.map(cue => cue.start), [0, 8, 16, 24, 32, 40]);
        for (const cue of cues) {
          await video.evaluate((v, start) => { v.currentTime = start + .12; }, cue.start);
          await expect.poll(() => video.evaluate(v => v.seeking)).toBe(false);
          await expect(page.locator('.tour-caption')).toHaveText(cue.text);
          const captionBox = await page.locator('.tour-caption').boundingBox();
          const videoBox = await video.boundingBox();
          assert.ok(captionBox && captionBox.x >= videoBox.x - 1 &&
            captionBox.x + captionBox.width <= videoBox.x + videoBox.width + 1,
          `The ${language} caption must stay within the ${width}px frame`);
        }
      }
      assert.deepEqual(errors, []);
      await context.close();
    }
    console.log('Homepage tour: 48-second playback, six cues in all seven languages, static readable captions, reduced motion, pause/offscreen, mobile layout and codec/error fallback passed. Screenshots: ' + artifacts);
  } finally { await browser.close(); fs.rmSync(root, {recursive:true, force:true}); }
})().catch(e => { console.error(e); process.exitCode=1; });
