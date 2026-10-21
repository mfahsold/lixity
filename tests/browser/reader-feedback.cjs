// Reading feedback keeps text legible and persistent state independent of arrival.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-reader-feedback-'));
const html = pythonFixture(`
import json
from dashboard_fixtures import full_dashboard
print(json.dumps(full_dashboard()))
`, {root});

async function frames(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

(async () => {
  const browser = await launchChromium();
  try {
    for (const [width, height] of [[1440, 900], [320, 480]]) {
      for (const reducedMotion of ['no-preference', 'reduce']) for (const colorScheme of ['light', 'dark']) {
        const page = await browser.newPage({viewport: {width, height}, reducedMotion, colorScheme, hasTouch: width === 320});
        const errors = [], writes = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', route => {
          const request = route.request(), url = new URL(request.url());
          if (request.method() !== 'GET') writes.push(url.pathname);
          if (url.origin !== 'http://lixity.test') return route.abort();
          if (url.pathname.startsWith('/api/')) return route.fulfill({json: {ok: true, locked: true, records: []}});
          return route.fulfill({contentType: 'text/html', body: html});
        });
        await page.goto('http://lixity.test/');
        await page.locator('#tab-view-analysis').click();
        await frames(page);
        const paints = await page.evaluate(() => {
          function luminance(color) {
            const values = color.match(/[\d.]+/g).slice(0, 3).map(Number).map(value => {
              const channel = value / 255;
              return channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4;
            });
            return values.reduce((sum, value, i) => sum + value * [.2126, .7152, .0722][i], 0);
          }
          const toggle = document.getElementById('manuscript-analysis-toggle'), results = [];
          for (const pressed of [true, false]) {
            if ((toggle.getAttribute('aria-pressed') === 'true') !== pressed) toggle.click();
            const animations = toggle.getAnimations();
            animations.forEach(animation => animation.pause());
            for (const time of [0, 16, 60, 120, 180]) {
              animations.forEach(animation => { animation.currentTime = time; });
              const style = getComputedStyle(toggle);
              const foreground = luminance(style.color), background = luminance(style.backgroundColor);
              results.push({pressed, time, contrast: (Math.max(foreground, background) + .05) / (Math.min(foreground, background) + .05)});
            }
            animations.forEach(animation => animation.finish());
          }
          return results;
        });
        assert.ok(paints.every(paint => paint.contrast >= 4.5), JSON.stringify({width, reducedMotion, colorScheme, paints}));
        const paragraph = page.locator('#chapters .ptext').first();
        await paragraph.locator('[data-reader-paragraph]').click();
        const menu = page.locator('#manuscript-context-menu');
        assert.ok(await menu.evaluate(node => parseFloat(getComputedStyle(node).paddingTop)) >= 8, 'Menu has deliberate border-to-content spacing');
        await menu.locator('[data-reader-action=values]').click();
        await frames(page);
        const reversal = await page.evaluate(() => {
          const dock = document.getElementById('workspace-context-panel');
          LixityMotion.reveal(dock);
          const active = dock.getAnimations().find(animation => animation.id === 'lixity-reveal');
          if (!active) return null;
          active.pause(); active.currentTime = 80;
          const before = Number(getComputedStyle(dock).opacity);
          LixityMotion.reveal(dock);
          const after = Number(getComputedStyle(dock).opacity);
          return {before, after};
        });
        if (reducedMotion === 'reduce') assert.equal(reversal, null, 'Reduced motion never animates the dock');
        else assert.ok(reversal && reversal.after >= reversal.before - .001, JSON.stringify(reversal));
        const localCue = await paragraph.evaluate(node => {
          const style = getComputedStyle(node, '::before');
          const state = {content: style.content, width: parseFloat(style.width)};
          document.getElementById('manuscript-analysis-toggle').click();
          return state;
        });
        assert.notEqual(localCue.content, 'none', 'Local Values stays identifiable with global Analysis Off');
        assert.ok(localCue.width >= 2, 'Local Values has a persistent gutter');
        await paragraph.scrollIntoViewIfNeeded();
        await page.waitForFunction(id => !document.getElementById(id).classList.contains('reader-layer-enter'), await paragraph.getAttribute('id'));
        const before = await paragraph.evaluate(node => {
          const prose = node.querySelector('.ptext-inner > p'), selection = getSelection();
          selection.setBaseAndExtent(prose.firstChild, prose.firstChild.length, prose.firstChild, 0);
          const state = {text: prose.textContent, hash: node.dataset.paragraphSha256,
            anchor: selection.anchorOffset, focus: selection.focusOffset, box: node.getBoundingClientRect().toJSON()};
          flashOnArrival(node);
          return state;
        });
        await page.waitForFunction(id => {
          const node = document.getElementById(id);
          return node.classList.contains('flash') && node.classList.contains('reader-return-target');
        }, await paragraph.getAttribute('id'));
        const paint = await paragraph.evaluate(node => {
          const arrival = node.getAnimations({subtree: true}).find(animation => animation.animationName === 'reader-passage-arrival');
          if (arrival) { arrival.pause(); arrival.currentTime = 1390; }
          return {animated: Boolean(arrival), persistentOpacity: Number(getComputedStyle(node, '::before').opacity),
            shadow: getComputedStyle(node).boxShadow, temporary: getComputedStyle(node, '::after').content};
        });
        assert.equal(paint.animated, reducedMotion !== 'reduce', 'The live arrival respects the motion preference');
        assert.notEqual(paint.temporary, 'none', 'The actual settled arrival has its own paint');
        assert.equal(paint.persistentOpacity, 1, 'Arrival expiry cannot fade or rebound a persistent gutter');
        assert.equal(paint.shadow, 'none', 'Prose uses one gutter instead of a duplicate outline');
        await page.waitForFunction(id => !document.getElementById(id).classList.contains('reader-return-target'), await paragraph.getAttribute('id'));
        const after = await paragraph.evaluate(node => {
          const prose = node.querySelector('.ptext-inner > p'), selection = getSelection();
          return {text: prose.textContent, hash: node.dataset.paragraphSha256,
            anchor: selection.anchorOffset, focus: selection.focusOffset, box: node.getBoundingClientRect().toJSON()};
        });
        assert.deepEqual(after, before, 'Actual cue expiry preserves prose, hash, backward selection and geometry');
        assert.equal(await paragraph.evaluate(node => Number(getComputedStyle(node, '::before').opacity)), 1,
          'The persistent gutter stays stable after the actual arrival timer expires');
        await page.emulateMedia({reducedMotion: 'reduce'});
        await frames(page);
        assert.equal(await page.locator('#workspace-context-panel').evaluate(node => node.getAnimations().length), 0);
        await page.screenshot({path: path.join(artifacts, `${width}-${reducedMotion}-${colorScheme}.png`)});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
        assert.deepEqual(errors, []); assert.deepEqual(writes, []);
        await page.close();
      }
    }
    console.log(`Reader feedback: contrast throughout transitions, interruption, local/persistent gutters, reduced motion and unchanged prose at desktop/short mobile passed. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
