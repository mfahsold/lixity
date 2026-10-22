// Automatic consumers share only a currently pending, exact-context status read.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../../../src/lixity/ui/assets/research-core.js'), 'utf8');

function runtime() {
  const calls = [];
  const manager = {dataset: {researchToken: 'root-a'}};
  const body = {dataset: {manuscriptProjectToken: 'project-a', manuscriptSourceSha256: 'source-a'}};
  const context = {API: '/api', document: {body,
    getElementById(id) { return id === 'research-manager' ? manager : null; }},
    jsonApi(url, options, responseType) {
      let resolve, reject;
      const promise = new Promise((yes, no) => {resolve = yes; reject = no;});
      calls.push({url, options, responseType, resolve, reject});
      return promise;
    }, refreshResearchProjectInfo: async () => {}};
  vm.runInNewContext(source, context);
  return {context, calls, manager, body};
}

test('overlapping automatic status consumers share one request and expire on settlement', async () => {
  const {context, calls} = runtime();
  const first = context.researchApiGet('research/status', undefined, true);
  const second = context.researchApiGet('research/status', undefined, true);
  assert.equal(calls.length, 1);
  const status = {ok: true, initialized: true, snapshot: 'before'};
  calls[0].resolve(status);
  assert.equal(await first, status);
  assert.equal(await second, status);
  const later = context.researchApiGet('research/status', undefined, true);
  assert.equal(calls.length, 2, 'Settled status must never become a body cache');
  calls[1].resolve({ok: true, snapshot: 'after'});
  assert.equal((await later).snapshot, 'after');
});

test('explicit refresh supersedes sharing without an older completion evicting the newer read', async () => {
  const {context, calls} = runtime();
  const old = context.researchApiGet('research/status', undefined, true);
  const refresh = context.researchApiGet('research/status');
  assert.equal(calls.length, 2, 'Explicit reads must observe status again');
  calls[0].resolve({ok: true, snapshot: 'old'});
  await old;
  const automatic = context.researchApiGet('research/status', undefined, true);
  assert.equal(calls.length, 2, 'Old settlement must preserve the newer pending owner');
  calls[1].resolve({ok: true, snapshot: 'fresh'});
  assert.equal((await refresh).snapshot, 'fresh');
  assert.equal((await automatic).snapshot, 'fresh');
});

test('sharing is isolated by root, project, source, exact URL and response type', async () => {
  const {context, calls, manager, body} = runtime();
  const reads = [context.researchApiGet('research/status', undefined, true)];
  manager.dataset.researchToken = 'restored-root-b';
  reads.push(context.researchApiGet('research/status', undefined, true));
  manager.dataset.researchToken = 'root-a';
  reads.push(context.researchApiGet('research/status', undefined, true));
  body.dataset.manuscriptProjectToken = 'other-project';
  reads.push(context.researchApiGet('research/status', undefined, true));
  body.dataset.manuscriptSourceSha256 = 'changed-source';
  reads.push(context.researchApiGet('research/status', undefined, true));
  reads.push(context.researchApiGet('research/status?project_token=explicit', undefined, true));
  reads.push(context.researchApiGet('research/status', 'markdown', true));
  assert.equal(calls.length, 7);
  calls.forEach(call => call.resolve({ok: true}));
  await Promise.all(reads);
});

test('other research reads retain their existing independent observation behavior', async () => {
  const {context, calls} = runtime();
  const first = context.researchApiGet('research/dossiers', undefined, true);
  const second = context.researchApiGet('research/dossiers', undefined, true);
  assert.equal(calls.length, 2);
  calls.forEach(call => call.resolve({ok: true}));
  await Promise.all([first, second]);
});

test('failed status requests are evicted and remain retryable', async () => {
  const {context, calls} = runtime();
  const first = context.researchApiGet('research/status', undefined, true);
  const second = context.researchApiGet('research/status', undefined, true);
  assert.equal(calls.length, 1);
  calls[0].reject(new Error('Synthetic connection failure'));
  await Promise.all([assert.rejects(first, /Synthetic/), assert.rejects(second, /Synthetic/)]);
  const retry = context.researchApiGet('research/status', undefined, true);
  assert.equal(calls.length, 2);
  calls[1].resolve({ok: false, code: 'stale-context'});
  assert.equal((await retry).code, 'stale-context');
  const next = context.researchApiGet('research/status', undefined, true);
  assert.equal(calls.length, 3);
  calls[2].resolve({ok: true});
  await next;
});

for (const accepted of [true, false]) test(`a mutation invalidates status sharing before and after settlement (ok=${accepted})`, async () => {
  const {context, calls} = runtime();
  const before = context.researchApiGet('research/status', undefined, true);
  const write = context.researchApiPost('research-revise', {record_id: 'synthetic'});
  const during = context.researchApiGet('research/status', undefined, true);
  assert.equal(calls.length, 3, 'A read predating a mutation cannot serve a new consumer');
  calls[1].resolve({ok: accepted});
  await write;
  const after = context.researchApiGet('research/status', undefined, true);
  assert.equal(calls.length, 4, 'Post-write consumers cannot reuse an observation started during the write');
  for (const index of [0, 2, 3]) calls[index].resolve({ok: true});
  await Promise.all([before, during, after]);
});
