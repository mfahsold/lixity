// Shared destinations must arrive inside their real scrollport before feedback.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');

const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-anchor-navigation-'));
const html = pythonFixture(`
import json
from dashboard_fixtures import full_dashboard
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
original = full_dashboard.__globals__['render_dashboard']
full_dashboard.__globals__['SAMPLE'] += '\\n\\n## Synthetic destinations\\n\\n' + '\\n\\n'.join(
    'Synthetic passage %d. ' % number + 'The quiet garden gives this scene room to continue. ' * 6
    for number in range(40))
def render(*args, **kwargs):
    return original(*args, **{**kwargs,
        'labels': {**get_language_profile('en').labels, **WORKSPACE_LABELS['en']},
        'language_key': 'en', 'title': 'Synthetic destinations', 'enabled_actions': ['analyze', 'research-reader'],
        'manuscript_pdf_token': 'synthetic-project', 'research_context_token': 'synthetic-research',
        'manuscript_source_sha256': 'a' * 64})
full_dashboard.__globals__['render_dashboard'] = render
print(json.dumps(full_dashboard()))
`, {root});

async function createPage(browser, width, height, reducedMotion) {
  const page = await browser.newPage({viewport: {width, height}, reducedMotion});
  page.setDefaultTimeout(10000);
  const errors = [], writes = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => {
    if (['error', 'warning'].includes(message.type())) errors.push(message.text());
  });
  await page.route('**/*', route => {
    const request = route.request(), url = new URL(request.url());
    if (request.method() !== 'GET') {
      writes.push(url.pathname);
      return route.fulfill({status: 400, json: {ok: false, message: 'Navigation cannot save'}});
    }
    if (url.origin !== 'http://lixity.test') return route.abort();
    if (url.pathname.startsWith('/api/')) return route.fulfill({json: {
      ok: true, initialized: true, project_id: 'synthetic-project', records: [], sources: [],
      dossiers: [], claims: [], decisions: [], candidates: [], links: [],
    }});
    return route.fulfill({contentType: 'text/html', body: html});
  });
  await page.goto('http://lixity.test/');
  assert.match(await page.title(), /^Synthetic destinations – /);
  await page.locator('#tab-view-analysis').click();
  const source = await manuscript(page);
  return {page, errors, writes, source};
}

function manuscript(page) {
  return page.locator('#chapters .ptext').evaluateAll(nodes => nodes.map(node => ({
    id: node.id, start: node.dataset.start, end: node.dataset.end,
    text: node.querySelector('.ptext-inner > p').textContent,
  })));
}

async function finish(state) {
  assert.deepEqual(state.errors, []);
  assert.deepEqual(state.writes, []);
  assert.deepEqual(await manuscript(state.page), state.source, 'Navigation preserves original manuscript text and anchors');
  assert.equal(await state.page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
}

async function observeArrivals(page, ids) {
  await page.evaluate(ids => {
    window.anchorArrivals = [];
    ids.forEach(id => {
      const target = document.getElementById(id);
      let marked = target.classList.contains('flash');
      new MutationObserver(() => {
        const next = target.classList.contains('flash');
        if (next && !marked) {
          const box = target.getBoundingClientRect();
          let top = 0, bottom = innerHeight;
          for (let node = target.parentElement; node; node = node.parentElement) {
            if (!/(auto|scroll|hidden)/.test(getComputedStyle(node).overflowY)) continue;
            const bounds = node.getBoundingClientRect();
            top = Math.max(top, bounds.top + node.clientTop);
            bottom = Math.min(bottom, bounds.top + node.clientTop + node.clientHeight);
          }
          anchorArrivals.push({id, top: box.top, bottom: box.bottom, visibleTop: top, visibleBottom: bottom});
        }
        marked = next;
      }).observe(target, {attributes: true, attributeFilter: ['class']});
    });
  }, ids);
}

async function observeReadingArrivals(page) {
  await page.evaluate(() => {
    window.readingArrivals = [];
    const marked = new Map();
    document.querySelectorAll('#chapters .ptext').forEach(node => {
      marked.set(node, new Set(['flash', 'reader-return-target'].filter(name => node.classList.contains(name))));
    });
    new MutationObserver(records => {
      records.forEach(({target}) => {
        if (!marked.has(target)) return;
        const previous = marked.get(target);
        ['flash', 'reader-return-target'].forEach(name => {
          const active = target.classList.contains(name);
          if (active && !previous.has(name)) {
            const box = target.getBoundingClientRect();
            readingArrivals.push({id: target.id, kind: name, top: box.top, bottom: box.bottom});
          }
          if (active) previous.add(name); else previous.delete(name);
        });
      });
    }).observe(document.getElementById('chapters'), {subtree: true, attributes: true, attributeFilter: ['class']});
  });
}

async function nestedFixture(page) {
  await page.locator('#workspace-reader-toggle').click();
  await page.evaluate(() => {
    const dock = document.getElementById('workspace-context-panel');
    const route = document.createElement('button');
    route.type = 'button'; route.className = 'ctl'; route.id = 'anchor-nested-route';
    route.dataset.jump = '#anchor-nested-a'; route.textContent = 'Read synthetic target';
    const content = document.createElement('div');
    content.innerHTML = '<div style="height:1800px">Synthetic context before the destination</div>' +
      '<section id="anchor-nested-a" style="height:100px">Synthetic arrival target</section>' +
      '<div style="height:500px">Synthetic context between destinations</div>' +
      '<section id="anchor-nested-b" style="height:100px">Synthetic second target</section>' +
      '<div style="height:1200px">Synthetic context after the destinations</div>';
    dock.prepend(route); dock.appendChild(content); dock.scrollTop = 0;
    dock.scrollIntoView({block: 'start', behavior: 'instant'});
  });
}

(async () => {
  const browser = await launchChromium(), failures = [];
  async function check(name, operation) {
    try { await operation(); }
    catch (error) { failures.push(new Error(name + ': ' + error.message, {cause: error})); }
  }
  try {
    for (const [width, height] of [[1440, 900], [320, 480]]) for (const motion of ['no-preference', 'reduce']) {
      await check(`nested arrival ${width} ${motion}`, async () => {
        const state = await createPage(browser, width, height, motion), {page} = state;
        try {
          await nestedFixture(page);
          await observeArrivals(page, ['anchor-nested-a']);
          await page.locator('#anchor-nested-route').click();
          await page.waitForFunction(() => anchorArrivals.length > 0);
          const arrival = await page.evaluate(() => anchorArrivals[0]);
          assert.ok(arrival.top >= arrival.visibleTop - 1 && arrival.bottom <= arrival.visibleBottom + 1,
            'The first arrival hint must appear inside the scrollport, not while its destination is still travelling: ' + JSON.stringify(arrival));
          const box = await page.locator('#anchor-nested-a').boundingBox();
          assert.ok(Math.abs(box.y - arrival.top) <= 1, 'The destination has stopped moving when feedback begins');
          assert.ok(arrival.top - arrival.visibleTop <= 24,
            'A nested destination uses its own clearance instead of unrelated manuscript controls');
          assert.notEqual(await page.locator('#anchor-nested-a').evaluate(node => getComputedStyle(node).boxShadow), 'none',
            'Arrival retains a visible static cue, including reduced motion');
          await page.screenshot({path: path.join(artifacts, `nested-${width}-${motion}.png`)});
          await finish(state);
        } finally { await page.close(); }
      });
    }

    await check('one arrival per jump', async () => {
      const state = await createPage(browser, 1440, 900, 'no-preference'), {page} = state;
      try {
        const id = await page.locator('#chapters .ptext').nth(27).getAttribute('id');
        await page.evaluate(id => {
          const target = document.getElementById(id);
          target.scrollIntoView({block: 'start', behavior: 'instant'});
          scrollBy(0, -100);
        }, id);
        await observeArrivals(page, [id]);
        await page.evaluate(id => scrollAndFlash(document.getElementById(id)), id);
        await page.waitForFunction(() => anchorArrivals.length > 0);
        await page.waitForTimeout(2300);
        assert.equal(await page.evaluate(() => anchorArrivals.length), 1,
          'The completion fallback must not repeat an arrival after the first cue expires');
        await finish(state);
      } finally { await page.close(); }
    });

    await check('new destination cancels older feedback', async () => {
      const state = await createPage(browser, 1440, 900, 'no-preference'), {page} = state;
      try {
        await nestedFixture(page);
        await observeArrivals(page, ['anchor-nested-a', 'anchor-nested-b']);
        await page.evaluate(() => {
          scrollAndFlash(document.getElementById('anchor-nested-a'));
          requestAnimationFrame(() => scrollAndFlash(document.getElementById('anchor-nested-b')));
        });
        await page.waitForFunction(() => anchorArrivals.some(arrival => arrival.id === 'anchor-nested-b'));
        assert.equal(await page.evaluate(() => anchorArrivals.some(arrival => arrival.id === 'anchor-nested-a')), false,
          'A superseded destination cannot announce arrival');
        await page.evaluate(() => scrollAndFlash(document.getElementById('anchor-nested-a')));
        assert.equal(await page.locator('#anchor-nested-b').evaluate(node => node.classList.contains('flash')), false,
          'The next jump removes an already visible hint from the previous destination');
        await page.waitForFunction(() => anchorArrivals.some(arrival => arrival.id === 'anchor-nested-a'));
        await finish(state);
      } finally { await page.close(); }
    });

    for (const supersede of [false, true]) await check('cross-view passage feedback ' + (supersede ? 'superseded' : 'direct'), async () => {
      const state = await createPage(browser, 320, 900, 'no-preference'), {page} = state;
      try {
        const ids = await page.locator('#chapters .ptext').evaluateAll(nodes => [nodes[27].id, nodes[35].id]);
        await page.locator('#tab-view-research').click();
        await page.waitForFunction(() => !document.querySelector('#chapters .reader-return-target, #chapters .flash'));
        await observeReadingArrivals(page);
        await page.evaluate(({ids, supersede}) => {
          scrollAndFlash(document.getElementById(ids[0]));
          if (supersede) requestAnimationFrame(() => {
            switchActiveView('research');
            scrollAndFlash(document.getElementById(ids[1]));
          });
        }, {ids, supersede});
        const destination = supersede ? ids[1] : ids[0];
        await page.waitForFunction(id => document.getElementById(id).classList.contains('flash'), destination);
        const arrivals = await page.evaluate(() => readingArrivals);
        assert.ok(arrivals.every(arrival => arrival.id === destination),
          'A cross-view jump must not mark an incidental paragraph or a superseded destination: ' + JSON.stringify(arrivals));
        assert.deepEqual(arrivals.map(arrival => arrival.kind).sort(), ['flash', 'reader-return-target'],
          'Only the settled destination receives one flash and one reading gutter');
        const box = await page.locator('#' + destination).boundingBox();
        assert.ok(arrivals.every(arrival => Math.abs(arrival.top - box.y) <= 1),
          'Both reading cues begin after the cross-view manuscript scroll settles: ' + JSON.stringify({arrivals, box}));
        await finish(state);
      } finally { await page.close(); }
    });

    for (const width of [1440, 320]) for (const method of ['click', 'keyboard']) await check(`queued hash yields to explicit ${method} view ${width}`, async () => {
      const state = await createPage(browser, width, 900, 'reduce'), {page} = state;
      try {
        const historyLength = await page.evaluate(() => history.length);
        const selected = await page.evaluate(method => new Promise(resolve => {
          const target = document.querySelector('#chapters .ptext');
          window.addEventListener('hashchange', () => resolve(document.getElementById('tab-view-project').getAttribute('aria-selected')), {once: true});
          location.hash = '#' + target.id;
          if (method === 'click') document.getElementById('tab-view-project').click();
          else document.getElementById('tab-view-analysis').dispatchEvent(new KeyboardEvent('keydown', {key: 'End', bubbles: true, cancelable: true}));
        }), method);
        assert.equal(selected, 'true', 'A queued older fragment event cannot reverse the newer explicit workspace choice');
        assert.equal(new URL(page.url()).hash, '#view-project', 'Explicit workspace choice uses its existing fragment route without a new history entry');
        assert.equal(await page.evaluate(() => history.length), historyLength + 1, 'Only the original fragment assignment adds a history entry');
        await page.evaluate(() => switchActiveView('research'));
        assert.equal(new URL(page.url()).hash, '#view-research', 'A programmatic departure keeps the current view reloadable');
        await page.reload();
        assert.equal(await page.locator('#tab-view-research').getAttribute('aria-selected'), 'true');
        const restored = await page.evaluate(() => new Promise(resolve => {
          window.addEventListener('hashchange', () => resolve(document.getElementById('tab-view-analysis').getAttribute('aria-selected')), {once: true});
          location.hash = '#' + document.querySelector('#chapters .ptext').id;
        }));
        assert.equal(restored, 'true', 'A later genuine fragment destination still opens its manuscript view');
        assert.equal(new URL(page.url()).hash, '#' + await page.locator('#chapters .ptext').first().getAttribute('id'), 'A real manuscript fragment remains precise');
        await finish(state);
      } finally { await page.close(); }
    });

    await check('explicit centered instant destination', async () => {
      const state = await createPage(browser, 1440, 900, 'no-preference'), {page} = state;
      try {
        const id = await page.locator('#chapters .ptext').nth(27).getAttribute('id');
        await page.locator('#manuscript-analysis-toggle').focus();
        await page.evaluate(() => {
          window.anchorViewChanges = 0;
          document.addEventListener('lixity:viewchange', () => { anchorViewChanges += 1; });
        });
        await page.evaluate(id => scrollAndFlash(document.getElementById(id), {block: 'center', behavior: 'instant'}), id);
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        const box = await page.locator('#' + id).boundingBox(), controls = await page.locator('#manuscript-reader-controls').boundingBox();
        assert.ok(Math.abs(box.y + box.height / 2 - (900 + controls.height + 12) / 2) <= 1,
          'Explicit centered routes use the available reading area and complete immediately: ' + JSON.stringify({box, controls}));
        assert.equal(await page.locator('#manuscript-analysis-toggle').evaluate(node => node === document.activeElement), true,
          'A shared programmatic jump preserves a visible focus owner');
        assert.equal(await page.evaluate(() => anchorViewChanges), 0,
          'A destination in the current view does not restart navigation or cancel an asynchronous destination follower');
        await finish(state);
      } finally { await page.close(); }
    });

    await check('paragraph diagnostics clear the mobile reader controls', async () => {
      const state = await createPage(browser, 320, 900, 'reduce'), {page} = state;
      try {
        await page.locator('#manuscript-analysis-toggle').click();
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        const id = await page.locator('#chapters .ptext').nth(27).getAttribute('id');
        await page.evaluate(id => {
          const target = document.getElementById(id);
          scrollBy(0, target.getBoundingClientRect().top - 20);
          document.querySelector('.chip[data-target="' + id + '"]').click();
        }, id);
        await page.waitForFunction(id => document.getElementById(id).classList.contains('flash'), id);
        const box = await page.locator('#' + id).boundingBox(), controls = await page.locator('#manuscript-reader-controls').boundingBox();
        assert.ok(box.y >= controls.y + controls.height,
          'Opening paragraph diagnostics keeps its prose below the wrapped mobile reader controls');
        await finish(state);
      } finally { await page.close(); }
    });

    for (const width of [1440, 320]) await check('live reduced motion and reader clearance ' + width, async () => {
      const state = await createPage(browser, width, 900, 'no-preference'), {page} = state;
      try {
        await page.emulateMedia({reducedMotion: 'reduce'});
        const id = await page.locator('#chapters .ptext').nth(27).getAttribute('id');
        await page.evaluate(id => scrollAndFlash(document.getElementById(id)), id);
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        const box = await page.locator('#' + id).boundingBox(), controls = await page.locator('#manuscript-reader-controls').boundingBox();
        assert.ok(box.y >= controls.y + controls.height && box.y <= controls.y + controls.height + 14,
          'A live reduced-motion change reaches the prose immediately and preserves sticky-reader clearance: ' + JSON.stringify({box, controls}));
        await page.waitForFunction(id => document.getElementById(id).classList.contains('flash'), id);
        assert.equal(await page.locator('#' + id).evaluate(node => node.classList.contains('reader-return-target')), true,
          'Prose arrivals use the existing reading gutter even with motion disabled');
        await page.screenshot({path: path.join(artifacts, `reader-${width}-reduce.png`)});
        await finish(state);
      } finally { await page.close(); }
    });
    if (failures.length) throw new AggregateError(failures, 'Anchor navigation regressions');
    console.log('Anchor navigation: nested desktop/short-mobile alignment, settled single arrivals, cancelled obsolete targets, live reduced motion, reader clearance and unchanged source passed. Screenshots: ' + artifacts);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
