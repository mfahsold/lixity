// The inline transport never falls through to a host API or external network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../../../src/lixity/ui/assets/read-only-site.js'), 'utf8');

function runtime(href, envelope) {
  const calls = [];
  const context = {URL, Response, Request, Headers, console, location: new URL(href),
    document: {baseURI: href, body: {dataset: {readOnly: 'true'}},
      getElementById: () => ({textContent: JSON.stringify(envelope)})},
    fetch: async (...args) => {calls.push(args); return new Response('resource');}};
  context.window = context;
  vm.runInNewContext(source, context);
  return {context, calls};
}
const data = {schema_version: 'lixity-read-only-site-data/1', responses: {
  '/api/research/record?b=2&a=1': {record: {title: 'Synthetic </script> entry'}},
  '/api/research/matrix?format=md': {text: '# Synthetic matrix'},
}, resources: {'/api/research/image?id=1': 'assets/image.png'}};

for (const href of ['file:///tmp/site/index.html', 'https://example.test/nested/site/index.html']) {
  test(`prepared GET works without network: ${href}`, async () => {
    const {context, calls} = runtime(href, data);
    const response = await context.fetch('/api/research/record?a=1&b=2');
    assert.deepEqual(await response.json(), data.responses['/api/research/record?b=2&a=1']);
    assert.equal(await (await context.fetch('/api/research/matrix?format=md')).text(), '# Synthetic matrix');
    assert.equal(calls.length, 0);
    assert.equal(context.LixitySite.resourceUrl('/api/research/image?id=1'), 'assets/image.png');
  });
}
test('all writes, unknown reads, external URLs and unsafe resources fail closed', async () => {
  const {context, calls} = runtime('https://example.test/site/index.html', data);
  for (const [url, init] of [
    ['/api/research/record?a=1&b=2', {method: 'POST'}], ['/api/not-prepared'],
    ['https://other.test/api/research/record?a=1&b=2'], ['https://tile.openstreetmap.org/1/1/1.png'],
    ['assets/unlisted.png'],
  ]) await assert.rejects(context.fetch(url, init));
  assert.equal(calls.length, 0);
  assert.equal(context.LixitySite.resourceUrl('/api/not-prepared'), null);
  const bad = runtime('file:///tmp/site/index.html', {...data, resources: {'/api/research/image?id=1': '../private.png'}});
  assert.equal(bad.context.LixitySite.resourceUrl('/api/research/image?id=1'), null);
  await context.fetch('assets/image.png');
  assert.equal(calls.length, 1);
});
test('missing or invalid inline data cannot enable network fallback', async () => {
  const {context, calls} = runtime('https://example.test/index.html', {schema_version: 'unknown'});
  await assert.rejects(context.fetch('/api/research/status'));
  assert.equal(calls.length, 0);
});
