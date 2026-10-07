const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-decision-ack-ui-'));
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
import copy
import json
import tempfile
from pathlib import Path
from lixity.server import build_server_dashboard
from lixity.research import api
from lixity.research.repository import Repository
from lixity.workspace_labels import WORKSPACE_LABELS
with tempfile.TemporaryDirectory() as directory:
    p = Path(directory) / 'synthetic-project'
    api.init(p, title='Synthetic author assessment')
    first = api.create_dossier(p, title='First <img src=x onerror=alert(1)> dossier', body='Synthetic notes.')['dossier_id']
    second = api.create_dossier(p, title='Second dossier', body='Other synthetic notes.')['dossier_id']
    decision = api.record_decision(p, title='Synthetic decision', rationale='Synthetic author choice.', dossier_ids=[first, second])['decision_id']
    initial = {'review': api.editorial_review(p), 'impact': api.decision_impact(p, decision)}
    def acknowledge(status):
        s = Repository(p).snapshot()
        return api.acknowledge_decision(p, decision, first, expected_snapshot=s.digest,
                    expected_decision_revision=s.records[decision].revision,
                    expected_dossier_revision=s.records[first].revision, status=status)
    applied = acknowledge('applied')
    reopened = acknowledge('review_needed')
    loaded = api.get_record(p, 'dossier', first)
    api.revise_record(p, 'dossier', first, changes={'body':'Synthetic revised notes.'},
                      expected_snapshot=loaded['snapshot'], expected_revision=1,
                      change_kind='supersession', reason='Synthetic author update.')
    stale = {'review': api.editorial_review(p), 'impact': api.decision_impact(p, decision)}
    withdrawn = copy.deepcopy(stale)
    for c in withdrawn['review']['candidates']:
        if c['dossier_id'] == first: c['flags'].append('withdrawn_dossier')
    for d in withdrawn['impact']['dossiers']:
        if d['id'] == first:
            d['flags'].append('withdrawn_dossier')
            d['withdrawn'] = True
    fixtures = {}
    for language in ('en','de','fr','es','it','pt','nl'):
        html, _ = build_server_dashboard(None, language=language, title='Synthetic author assessment')
        fixtures[language] = {'html': html, 'labels':WORKSPACE_LABELS[language]}
    print(json.dumps({'fixtures':fixtures, 'initial':initial, 'applied':applied, 'reopened':reopened,
                     'stale':stale, 'withdrawn':withdrawn, 'decision':decision, 'first':first,
                     'decisions':api.list_decisions(p), 'dossiers':api.list_dossiers(p)}))
`], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding:'utf8', maxBuffer:32 * 1024 * 1024});
assert.equal(fixture.status, 0, fixture.stderr);
const data = JSON.parse(fixture.stdout);

(async () => {
  const browser = await launchChromium();
  const posts = [];
  const errors = [];
  let state = data.initial;
  let response = {ok:false, message:'Synthetic stale archive', conflict:true};
  let responseStatus = 409;
  let reviewReads = 0;
  async function open(language) {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    page.setDefaultTimeout(5000);
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://lixity.test/**', route => {
      const request = route.request();
      const url = new URL(request.url());
      if (url.pathname === '/api/research-decision-acknowledge') {
        posts.push(request.postDataJSON());
        return route.fulfill({status:responseStatus,json:response});
      }
      if (url.pathname === '/api/research/review') {
        reviewReads++;
        return route.fulfill({json:{ok:true,...state.review}});
      }
      if (url.pathname === '/api/research/decision-impact') return route.fulfill({json:{ok:true,...state.impact}});
      if (url.pathname === '/api/research/status') return route.fulfill({json:{
        ok:true,initialized:true,project_root:'/synthetic',project_id:state.impact.project_id,
        sources_count:0,dossiers_count:2,claims_count:0,decisions_count:1
      }});
      if (url.pathname === '/api/research/decisions') return route.fulfill({json:{ok:true,...data.decisions}});
      if (url.pathname === '/api/research/dossiers') return route.fulfill({json:{ok:true,...data.dossiers}});
      if (url.pathname.startsWith('/api/')) return route.fulfill({json:{ok:true,sources:[],claims:[],dossiers:[],decisions:[]}});
      return route.fulfill({contentType:'text/html',body:data.fixtures[language].html});
    });
    await page.goto('http://lixity.test/');
    await page.locator('[data-rtab=review]').click();
    await page.locator('#research-editorial-review .research-card').first().waitFor();
    return page;
  }
  try {
    const page = await open('en');
    const host = page.locator('#research-editorial-review');
    assert.equal(await host.locator('[data-decision-ack-status=applied]').count(), 2, 'Each affected dossier has an explicit author action');
    assert.equal(await host.locator('img').count(), 0, 'Dossier titles stay inert');
    const first = host.locator(`[data-decision-ack-dossier="${data.first}"]`);
    const oldTokens = await first.getAttribute('data-decision-ack-snapshot');
    const reads = reviewReads;
    await first.locator('[data-decision-ack-status=applied]').click();
    await first.locator('[data-decision-ack-feedback]').waitFor({state:'visible'});
    assert.equal(posts.length, 1, 'A conflict never retries automatically');
    assert.equal(reviewReads, reads, 'A conflict never silently refreshes or rebases');
    assert.equal(await first.getAttribute('data-decision-ack-snapshot'), oldTokens);
    assert.ok((await first.locator('[data-decision-ack-feedback]').textContent()).includes('Refresh'));
    assert.equal(await first.locator('[data-decision-ack-status=applied]').isDisabled(), false);
    assert.deepEqual(posts[0], {decision_id:data.decision,dossier_id:data.first,
      expected_snapshot:data.initial.review.snapshot,expected_decision_revision:1,expected_dossier_revision:1,status:'applied'});
    responseStatus = 500;
    response = {ok:false,message:'Synthetic save failure'};
    await first.locator('[data-decision-ack-status=applied]').click();
    await page.waitForFunction(() => Array.from(document.querySelectorAll('[data-decision-ack-feedback]')).some(el => el.textContent.includes('Synthetic save failure')));
    assert.equal(await first.getAttribute('data-decision-ack-snapshot'), oldTokens);
    assert.equal(reviewReads, reads);
    response = {ok:true,...data.applied};
    await first.locator('[data-decision-ack-status=applied]').click();
    await page.waitForFunction(id => {
      const pair = document.querySelector('#research-editorial-review [data-decision-ack-dossier="' + id + '"]');
      return pair && pair.dataset.decisionAckPending !== '1';
    }, data.first);
    assert.equal(await first.getAttribute('data-decision-ack-snapshot'), oldTokens, 'HTTP errors cannot mark a pair as applied');
    responseStatus = 200;
    response = {ok:true,...data.applied};
    await first.locator('[data-decision-ack-status=applied]').click();
    await first.locator('[data-decision-ack-status=review_needed]').waitFor();
    assert.ok((await first.textContent()).includes('author'));
    assert.ok((await first.textContent()).includes('not verified'));
    assert.equal(await host.locator('[data-decision-ack-status=applied]').count(), 1, 'Marking one pair leaves the other pair untouched');
    response = {ok:true,...data.reopened};
    await first.locator('[data-decision-ack-status=review_needed]').click();
    await first.locator('[data-decision-ack-status=applied]').waitFor();
    assert.equal(posts.at(-1).expected_snapshot, data.applied.snapshot);
    assert.equal(posts.at(-1).status, 'review_needed');
    state = data.stale;
    await page.locator('#r-review-refresh').click();
    await host.locator(`[data-decision-ack-dossier="${data.first}"][data-decision-ack-dossier-revision="2"]`).waitFor();
    assert.ok((await host.textContent()).includes('earlier'));
    assert.ok((await host.textContent()).includes('review'));
    await page.close();
    for (const language of ['en','de','fr','es','it','pt','nl']) {
      state = data.stale;
      const page = await open(language);
      for (const width of [1440,320]) {
        await page.setViewportSize({width,height:1000});
        const labels = data.fixtures[language].labels;
        assert.equal(await page.locator('#research-editorial-review [data-decision-ack-status=applied]').first().textContent(), labels.research_decision_mark_applied);
        await page.locator('#rtab-review').scrollIntoViewIfNeeded();
        await page.locator('#rtab-review').screenshot({path:path.join(artifacts,`review-${language}-${width}.png`)});
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        await page.locator('[data-rtab=decisions]').click();
        await page.locator('[data-decision-impact]').click();
        await page.locator('[data-decision-impact]').locator('..').locator('[data-decision-ack-status=applied]').first().waitFor();
        await page.locator('[data-decision-impact]').locator('..').screenshot({path:path.join(artifacts,`impact-${language}-${width}.png`)});
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        await page.locator('[data-decision-impact]').click();
        await page.locator('[data-rtab=review]').click();
      }
      state = data.withdrawn;
      await page.locator('#r-review-refresh').click();
      const withdrawn = page.locator(`#research-editorial-review [data-decision-ack-dossier="${data.first}"][data-decision-ack-dossier-revision="2"]`);
      await page.waitForFunction(id => Array.from(document.querySelectorAll('#research-editorial-review [data-decision-ack-dossier]')).some(el => el.dataset.decisionAckDossier === id && el.querySelector('[data-decision-ack-status=applied]').disabled), data.first);
      assert.equal(await withdrawn.locator('[data-decision-ack-status=applied]').isDisabled(), true);
      assert.ok((await page.locator('#research-editorial-review').textContent()).includes(data.fixtures[language].labels.research_editorial_withdrawn_dossier));
      await page.close();
    }
    assert.deepEqual(errors,[]);
    console.log(`Author acknowledgements: exact pins, conflict/failure preservation, per-pair status and seven locales at 1440/320 passed. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
