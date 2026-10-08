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
import shutil
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
    def acknowledge(status, dossier_id=first):
        s = Repository(p).snapshot()
        return api.acknowledge_decision(p, decision, dossier_id, expected_snapshot=s.digest,
                    expected_decision_revision=s.records[decision].revision,
                    expected_dossier_revision=s.records[dossier_id].revision, status=status)
    details = {first: api.get_dossier(p, first), second: api.get_dossier(p, second)}
    applied = acknowledge('applied')
    after_applied = {'review': api.editorial_review(p), 'impact': api.decision_impact(p, decision)}
    external = Path(directory) / 'external-synthetic'
    shutil.copytree(p, external)
    b = api.get_record(external, 'dossier', second)
    api.revise_record(external, 'dossier', second, changes={'title':'Externally revised second dossier','body':'External synthetic revision two.'},
                      expected_snapshot=b['snapshot'], expected_revision=1,
                      change_kind='supersession', reason='Synthetic external revision.')
    external_after_applied = {'review':api.editorial_review(external), 'impact':api.decision_impact(external, decision),
                              'detail':api.get_dossier(external,second)}
    early = Path(directory) / 'early-reopen-synthetic'
    shutil.copytree(p, early)
    e = Repository(early).snapshot()
    reopened_early = api.acknowledge_decision(early, decision, first, expected_snapshot=e.digest,
                                            expected_decision_revision=1, expected_dossier_revision=1, status='review_needed')
    after_reopened_early = {'review':api.editorial_review(early), 'impact':api.decision_impact(early,decision)}
    applied_second = acknowledge('applied', second)
    after_second = {'review': api.editorial_review(p), 'impact': api.decision_impact(p, decision)}
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
                     'stale':stale, 'withdrawn':withdrawn, 'decision':decision, 'first':first, 'second':second,
                     'after_applied':after_applied, 'applied_second':applied_second, 'after_second':after_second,
                     'details':details, 'external_after_applied':external_after_applied,
                     'reopened_early':reopened_early, 'after_reopened_early':after_reopened_early,
                     'decisions':api.list_decisions(p), 'dossiers':api.list_dossiers(p)}))
`], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding:'utf8', maxBuffer:32 * 1024 * 1024});
assert.equal(fixture.status, 0, fixture.stderr);
const data = JSON.parse(fixture.stdout);

(async () => {
  const browser = await launchChromium();
  const posts = [];
  const errors = [];
  let state = data.initial;
  let response = {ok:false, message:'Synthetic stale archive'};
  let responseStatus = 409;
  let reviewReads = 0;
  let postWait = null;
  let reviewWait = null;
  async function open(language, width=1440) {
    const page = await browser.newPage({viewport:{width,height:1000}});
    page.setDefaultTimeout(5000);
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://lixity.test/**', async route => {
      const request = route.request();
      const url = new URL(request.url());
      if (url.pathname === '/api/research-decision-acknowledge') {
        posts.push(request.postDataJSON());
        const result = {status:responseStatus,json:{...response}};
        if (postWait) await postWait;
        return route.fulfill(result);
      }
      if (url.pathname === '/api/research/review') {
        reviewReads++;
        const report = {ok:true,...state.review};
        if (reviewWait) await reviewWait;
        return route.fulfill({json:report});
      }
      if (url.pathname === '/api/research/decision-impact') return route.fulfill({json:{ok:true,...state.impact}});
      if (url.pathname === '/api/research/status') return route.fulfill({json:{
        ok:true,initialized:true,project_root:'/synthetic',project_id:state.impact.project_id,
        sources_count:0,dossiers_count:2,claims_count:0,decisions_count:1
      }});
      if (url.pathname === '/api/research/decisions') return route.fulfill({json:{ok:true,...data.decisions}});
      if (url.pathname === '/api/research/dossiers') {
        const id = url.searchParams.get('id');
        const detail = state === data.external_after_applied && id === data.second ? state.detail : data.details[id];
        return route.fulfill({json:{ok:true,...(id ? detail : data.dossiers)}});
      }
      if (url.pathname.startsWith('/api/')) return route.fulfill({json:{ok:true,sources:[],claims:[],dossiers:[],decisions:[]}});
      return route.fulfill({contentType:'text/html',body:data.fixtures[language].html});
    });
    await page.goto('http://lixity.test/');
    await page.locator('[data-rtab=decisions]').click();
    await page.locator('[data-decision-impact]').click();
    await page.locator('#research-decisions-list [data-decision-ack-dossier]').first().waitFor({state:'attached'});
    await page.locator('[data-rtab=review]').click();
    await page.locator('#research-editorial-review .research-card').first().waitFor();
    return page;
  }
  async function finished(page) {
    await page.waitForFunction(() => researchAcknowledgementPending === false);
  }
  async function reviewEdges(edge, width=1440) {
    if (edge === 'all' || edge === 'external') {
      state = data.initial; postWait = reviewWait = null;
      const page = await open('en',width);
      const host = page.locator('#research-editorial-review');
      const secondCard = host.locator('.research-card').filter({has:page.locator(`[data-decision-ack-dossier="${data.second}"]`)});
      await secondCard.locator('[data-research-detail=dossier]').click();
      await secondCard.locator('.research-details-body').waitFor();
      await page.waitForFunction(id => document.querySelector('#research-editorial-review [data-decision-ack-dossier="'+id+'"]').closest('.research-card').textContent.includes('Other synthetic notes.'),data.second);
      await secondCard.locator('.research-details-body').evaluate(element=>{window.originalReviewDetail=element;});
      responseStatus=200; response={ok:true,...data.applied}; state=data.external_after_applied;
      const beforeReads=reviewReads;
      await host.locator(`[data-decision-ack-dossier="${data.first}"] [data-decision-ack-status=applied]`).click();
      await finished(page);
      const second=host.locator(`[data-decision-ack-dossier="${data.second}"]`);
      assert.equal(await second.getAttribute('data-decision-ack-snapshot'),data.applied.snapshot,'Automatic reconciliation cannot adopt an external HEAD');
      assert.equal(await second.getAttribute('data-decision-ack-dossier-revision'),'1','The old visible detail stays paired with its displayed revision');
      assert.ok((await secondCard.textContent()).includes('Other synthetic notes.'));
      assert.equal(await page.evaluate(()=>window.originalReviewDetail.isConnected),true);
      assert.ok((await page.locator('#research-status-bar').textContent()).includes(data.fixtures.en.labels.research_decision_ack_conflict));
      assert.equal(reviewReads,beforeReads+1,'An external review snapshot is not silently retried');
      await page.locator('#research-manager').screenshot({path:path.join(artifacts,`external-review-${width}.png`)});
      responseStatus=409; response={ok:false,message:'Synthetic external revision conflict'};
      await second.locator('[data-decision-ack-status=applied]').click();
      await finished(page);
      assert.equal(posts.at(-1).expected_snapshot,data.applied.snapshot);
      assert.equal(posts.at(-1).expected_dossier_revision,1);
      await page.locator('#r-review-refresh').click();
      await host.locator(`[data-decision-ack-dossier="${data.second}"][data-decision-ack-dossier-revision="2"]`).waitFor();
      assert.ok((await host.textContent()).includes('Externally revised second dossier'),'An explicit refresh loads the new visible context');
      await page.close();
    }
    if (edge === 'all' || edge === 'focus') {
      for (const success of [false,true]) {
        state=data.initial; postWait=reviewWait=null;
        const page=await open('en',width);
        const button=page.locator(`#research-editorial-review [data-decision-ack-dossier="${data.first}"] button`);
        responseStatus=success?200:500; response=success?{ok:true,...data.applied}:{ok:false,message:'Synthetic held failure'};
        state=success?data.after_applied:data.initial;
        let release; postWait=new Promise(resolve=>{release=resolve;});
        // Keep the existing shared draft field beside review, as an embedding can.
        await page.locator('#r-claim-statement').evaluate(element=>document.querySelector('#research-editorial-review').before(element));
        await button.focus(); await button.press('Enter');
        const draft=page.locator('#r-claim-statement');
        await draft.fill('Unrelated nonempty synthetic draft.');
        release(); postWait=null;
        await finished(page);
        assert.equal(await draft.evaluate(element=>document.activeElement===element),true,'A pending acknowledgement must not steal unrelated draft focus');
        assert.equal(await draft.inputValue(),'Unrelated nonempty synthetic draft.');
        await page.close();
      }
      state=data.initial; postWait=reviewWait=null;
      const page=await open('en',width);
      const host=page.locator('#research-editorial-review');
      const secondCard=host.locator('.research-card').filter({has:page.locator(`[data-decision-ack-dossier="${data.second}"]`)});
      await secondCard.locator('[data-research-detail=dossier]').click();
      const toggle=secondCard.locator('[data-source-toggle]');
      await toggle.waitFor();
      responseStatus=200; response={ok:true,...data.applied}; state=data.after_applied;
      let release; reviewWait=new Promise(resolve=>{release=resolve;});
      const button=host.locator(`[data-decision-ack-dossier="${data.first}"] button`);
      const reviewStarted=page.waitForRequest(request=>request.url().endsWith('/api/research/review'));
      await button.focus(); await button.press('Enter');
      await reviewStarted;
      await toggle.focus();
      await toggle.evaluate(element=>{window.retainedFocusedControl=element;});
      release(); reviewWait=null;
      await finished(page);
      assert.equal(await page.evaluate(()=>window.retainedFocusedControl.isConnected&&document.activeElement===window.retainedFocusedControl),true,'A focused retained detail survives review-card reparenting');
      await page.close();
      for (const success of [false,true]) {
        state=data.initial; postWait=reviewWait=null;
        const page=await open('en',width);
        responseStatus=success?200:500; response=success?{ok:true,...data.applied}:{ok:false,message:'Synthetic keyboard failure'};
        state=success?data.after_applied:data.initial;
        const button=page.locator(`#research-editorial-review [data-decision-ack-dossier="${data.first}"] button`);
        await button.focus(); await button.press('Enter'); await finished(page);
        const expected=success?data.second:data.first;
        assert.equal(await page.evaluate(id=>document.activeElement.closest('[data-decision-ack-dossier]')?.dataset.decisionAckDossier===id,expected),true,'Keyboard acknowledgement retains an appropriate action focus');
        await page.close();
      }
    }
    if (edge === 'all' || edge === 'flags') {
      state=data.initial; postWait=reviewWait=null;
      const page=await open('en',width);
      await page.locator('[data-rtab=decisions]').click();
      await page.locator('[data-decision-impact]').click();
      const pair=page.locator(`#research-decisions-list [data-decision-ack-dossier="${data.first}"]`);
      await pair.waitFor();
      const card=pair.locator('..');
      const dateFlag=data.fixtures.en.labels.research_editorial_decision_after_dossier;
      const reviewFlag=data.fixtures.en.labels.research_editorial_author_review_needed;
      assert.ok((await card.locator('.research-editorial-flags').textContent()).includes(dateFlag));
      responseStatus=200; response={ok:true,...data.applied}; state=data.after_applied;
      await pair.locator('[data-decision-ack-status=applied]').click(); await finished(page);
      assert.equal((await card.locator('.research-editorial-flags').textContent()).includes(dateFlag),false,'Applied impact status clears its date-based review flag');
      response={ok:true,...data.reopened_early}; state=data.after_reopened_early;
      await pair.locator('[data-decision-ack-status=review_needed]').click(); await finished(page);
      assert.ok((await card.locator('.research-editorial-flags').textContent()).includes(reviewFlag),'Reopened impact status adds its author-review flag');
      assert.ok((await card.locator('.research-editorial-flags').textContent()).includes(dateFlag),'Reopening restores the underlying date context');
      await page.close();
    }
  }
  try {
    const edge=process.argv.find(value=>value.startsWith('--edge='));
    if(edge) {
      await reviewEdges(edge.slice(7));
      assert.deepEqual(errors,[]);
      console.log('Acknowledgement review edges passed: '+edge.slice(7));
      return;
    }
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
    state = data.after_applied;
    await first.locator('[data-decision-ack-status=applied]').click();
    await host.locator(`[data-decision-ack-dossier="${data.first}"]`).waitFor({state:'detached'});
    const hiddenImpact = page.locator(`#research-decisions-list [data-decision-ack-dossier="${data.first}"]`);
    assert.equal(await hiddenImpact.getAttribute('data-decision-ack-snapshot'), data.applied.snapshot, 'The same acted pair receives the new token in hidden impact widgets');
    assert.equal(await hiddenImpact.locator('[data-decision-ack-status=review_needed]').count(), 1, 'The same acted pair cannot still offer a duplicate Mark as applied action');
    const second = host.locator(`[data-decision-ack-dossier="${data.second}"]`);
    assert.equal(await second.getAttribute('data-decision-ack-snapshot'), data.applied.snapshot, 'Own successful CAS advances the remaining review token');
    assert.ok((await host.textContent()).includes(data.fixtures.en.labels.research_editorial_count.replace('{count}', '1')), 'The review count agrees with the reconciled server view');
    response = {ok:true,...data.applied_second};
    state = data.after_second;
    await second.locator('[data-decision-ack-status=applied]').click();
    await page.waitForFunction(text => document.querySelector('#research-editorial-review').textContent === text, data.fixtures.en.labels.research_editorial_empty);
    assert.equal(posts.at(-1).expected_snapshot, data.applied.snapshot, 'A then B uses the current own-write snapshot');
    assert.equal(posts.at(-1).dossier_id, data.second);
    await page.locator('[data-rtab=decisions]').click();
    await page.locator('[data-decision-impact]').click();
    const appliedFirst = page.locator(`#research-decisions-list [data-decision-ack-dossier="${data.first}"]`);
    await appliedFirst.locator('[data-decision-ack-status=review_needed]').waitFor();
    assert.ok((await appliedFirst.textContent()).includes('author'));
    assert.ok((await appliedFirst.textContent()).includes('not verified'));
    response = {ok:true,...data.reopened};
    await appliedFirst.locator('[data-decision-ack-status=review_needed]').click();
    await appliedFirst.locator('[data-decision-ack-status=applied]').waitFor();
    assert.equal(posts.at(-1).expected_snapshot, data.applied_second.snapshot);
    assert.equal(posts.at(-1).status, 'review_needed');
    await page.locator('[data-rtab=review]').click();
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
    await reviewEdges('all');
    await reviewEdges('all',320);
    assert.deepEqual(errors,[]);
    console.log(`Author acknowledgements: exact pins, conflict/failure preservation, per-pair status and seven locales at 1440/320 passed. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
