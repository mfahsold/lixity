// Exercise actual media decoding, localized captions and deliberate playback.
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(require('node:path').join(playwrightModule, 'test'));
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const {stagePages} = require('./support/staged-pages.cjs');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-home-tour-'));
const root = stagePages();
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
      const heroActions = page.locator('.hero-cta a');
      await expect(heroActions).toHaveCount(3);
      await expect(heroActions.first()).toHaveAttribute('id', 'download-cta');
      await expect(page.locator('.hero-cta .primary#download-cta')).toHaveAttribute('href', 'guides/installation.html#desktop');
      await expect(page.locator('.hero-cta #try-passage')).toHaveAttribute('href', 'sandbox/index.html?lang=de');
      await expect(page.locator('.hero-cta #examples')).toHaveAttribute('href', '#product-tour-preview');
      await page.locator('#tour-share summary').click();
      await expect(page.locator('#tour-share a[download]')).toHaveCount(3);
      await page.locator('#tour-share summary').click();
      await expect(page.locator('#intro-title br')).toHaveCount(0);
      assert.equal(await page.locator('#intro-title').evaluate(node => getComputedStyle(node).hyphens), 'auto');
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
      if (width === 390) {
        const enlarged = await page.locator('.tour-screen').evaluate(screen => {
          const root = document.documentElement;
          const previous = root.style.fontSize;
          root.style.fontSize = '200%';
          try {
            const frame = screen.querySelector('video').getBoundingClientRect();
            const caption = screen.querySelector('.tour-caption').getBoundingClientRect();
            return caption.top >= frame.bottom - 1 && caption.bottom <= screen.getBoundingClientRect().bottom + 1;
          } finally {
            root.style.fontSize = previous;
          }
        });
        assert.ok(enlarged, 'At 200% text size the complete caption fits below the video on mobile');
      }
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
      const tourSources = url => /\/videos\/product-tour(?:-portrait)?\.(mp4|webm)$/.test(url.pathname);
      await page.route(tourSources, route => route.abort());
      await page.goto('https://tour.test/');
      await video.scrollIntoViewIfNeeded();
      await expect(page.locator('.tour-error')).toBeVisible();
      await expect(page.locator('.tour-caption')).toBeHidden();
      await page.unroute(tourSources);
      const unavailable = width === 390 ? 'product-tour-portrait.mp4' : 'product-tour.webm';
      await page.route(url => url.pathname.endsWith(`/videos/${unavailable}`), route => route.abort());
      await page.goto('https://tour.test/');
      await video.scrollIntoViewIfNeeded();
      await expect.poll(() => video.evaluate(v => v.currentTime)).toBeGreaterThan(.2);
      const fallback = await video.evaluate(v => new URL(v.currentSrc).pathname);
      assert.match(fallback, width === 390 ? /\/product-tour\.(mp4|webm)$/ : /\/product-tour\.mp4$/,
        `Playback continues when ${unavailable} fails`);
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
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode=1; });
