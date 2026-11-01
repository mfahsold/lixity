// Real native routes: scoped exports, provider settings/rendering and local audit.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

(async () => {
  const browser = await launchChromium();
  const artifacts = fs.mkdtempSync('/tmp/lixity-audio-export-browser-');
  try {
    for (const width of [1440, 320]) {
      const folder = path.join(artifacts, String(width)); fs.mkdirSync(folder);
      const server = await startNativeServer(`
import json, os, sys, threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from lixity.server import LixityServerHandler
from lixity.speech import generate_silence_wav
import lixity.speech_status as status
base = Path(sys.argv[1]); root = base / 'project'; root.mkdir()
os.environ['XDG_DATA_HOME'] = str(base / 'app-data')
os.environ['XDG_CACHE_HOME'] = str(base / 'cache')
source = root / 'draft.md'
source.write_text('## First\\n\\nThe red bird sings.\\n\\nThe blue bird answers.\\n\\n## Second\\n\\nThe river flows.\\n')
(root / 'lixity.toml').write_text('language="en"\\nmanuscript="draft.md"\\n')
audio = base / 'chapter.wav'; audio.write_bytes(generate_silence_wav(1))
requests = base / 'requests.json'; requests.write_text('[]')
class Provider(BaseHTTPRequestHandler):
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        rows = json.loads(requests.read_text()); rows.append(payload); requests.write_text(json.dumps(rows))
        data = generate_silence_wav(0.1)
        self.send_response(200); self.send_header('Content-Type','audio/wav')
        self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    def log_message(self, *args): pass
provider = ThreadingHTTPServer(('127.0.0.1',0), Provider)
threading.Thread(target=provider.serve_forever, daemon=True).start()
status.worker_health = lambda target: {'target':target,'state':'unavailable','model':None}
LixityServerHandler.workspace_root = str(root)
LixityServerHandler.source_input = str(source)
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.language = 'en'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1',0),LixityServerHandler)
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}', 'provider':f'http://127.0.0.1:{provider.server_port}/v1',
                  'source':str(source),'requests':str(requests),'audio':str(audio)}),flush=True)
server.serve_forever()
`, folder);
      const page = await browser.newPage({viewport: {width, height: 960}});
      const errors = []; page.on('pageerror', error => errors.push(error.message));
      const before = fs.readFileSync(server.fixture.source);
      try {
        await page.goto(server.fixture.url);
        assert.equal(await page.locator('#reader-speech').getAttribute('data-help'),
          await page.evaluate(() => uiLabel('speech_reader_help')),
          'Audio-capable workspaces describe rendering and plan export');
        await page.locator('#tab-view-project').click();
        await page.locator('#settings-speech-output').click();
        await page.waitForFunction(() => document.querySelector('#speech-name')?.value === 'Narrator');
        assert.equal(await page.locator('#settings-form #settings-speech-output').count(), 0,
          'Audio actions are separate from applying project settings');
        assert.equal(await page.locator('.speech-export-section [data-speech-action=direction_plan]').isVisible(), true);
        assert.equal(await page.evaluate(() => Boolean(document.querySelector('.speech-export-section')
          .compareDocumentPosition(document.querySelector('.speech-render-section')) & Node.DOCUMENT_POSITION_FOLLOWING)), true,
          'The export entry presents portable direction before synthesis controls');
        assert.equal(await page.locator('#speech-export_scope').inputValue(), 'chapter');
        await page.locator('[data-speech-action=direction_plan]').click();
        await page.waitForSelector('[data-speech-action=export_json]');
        assert.match(await page.locator('.speech-plan').textContent(), /The blue bird answers/);
        assert.doesNotMatch(await page.locator('.speech-plan').textContent(), /The river flows/);
        assert.doesNotMatch(await page.locator('#modal-speech [role=status]').textContent(), /Queued/);
        const chapterDownload = page.waitForEvent('download');
        await page.locator('[data-speech-action=export_json]').click();
        const chapter = JSON.parse(fs.readFileSync(await (await chapterDownload).path(), 'utf8'));
        assert.equal(chapter.schema_version, 'lixity-audio-timeline/1');
        assert.ok(chapter.segments.some(row => row.text === 'The blue bird answers.'));
        await page.locator('#speech-export_scope').selectOption('manuscript');
        await page.locator('[data-speech-action=direction_plan]').click();
        await page.waitForFunction(() => document.querySelector('.speech-plan')?.textContent.includes('The river flows'));
        const ssmlDownload = page.waitForEvent('download');
        await page.locator('[data-speech-action=export_ssml]').click();
        const ssml = fs.readFileSync(await (await ssmlDownload).path(), 'utf8');
        assert.match(ssml, /xml:lang="en"/); assert.match(ssml, /The river flows/);
        assert.deepEqual(JSON.parse(fs.readFileSync(server.fixture.requests)), []);
        await page.locator('.speech-plan').screenshot({path: path.join(folder, 'export.png')});
        await page.locator('.settings-section').filter({has: page.locator('#speech-audit_audio')}).locator('summary').click();
        await page.locator('#speech-audit_audio').setInputFiles(server.fixture.audio);
        await page.locator('[data-speech-action=audit_run]').click();
        await page.waitForSelector('[data-speech-action=audit_download]');
        const auditDownload = page.waitForEvent('download');
        await page.locator('[data-speech-action=audit_download]').click();
        const audit = JSON.parse(fs.readFileSync(await (await auditDownload).path(), 'utf8'));
        assert.equal(audit.alignment.status, 'unknown');
        const transcript = {schema_version: 'lixity-audio-transcript/1', model: 'synthetic',
          audio_sha256: crypto.createHash('sha256').update(fs.readFileSync(server.fixture.audio)).digest('hex'),
          words: 'First The red bird sings The bird answers Second The river flows'.split(' ').map((text, i) => ({text, start: i * 0.05, end: i * 0.05 + 0.04}))};
        await page.locator('#speech-audit_transcript').setInputFiles({name: 'transcript.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(transcript))});
        assert.equal(await page.locator('[data-speech-action=audit_download]').count(), 0, 'Changing evidence clears stale audit results');
        await page.locator('[data-speech-action=audit_run]').click();
        await page.waitForSelector('[data-speech-action=audit_download]');
        const comparedDownload = page.waitForEvent('download');
        await page.locator('[data-speech-action=audit_download]').click();
        const compared = JSON.parse(fs.readFileSync(await (await comparedDownload).path(), 'utf8'));
        assert.equal(compared.alignment.status, 'compared');
        assert.deepEqual(compared.alignment.missing_words.map(row => row.text), ['blue']);
        await page.locator('#modal-speech [data-speech-action=close]').click();
        await page.locator('#settings-speech').click();
        await page.waitForFunction(() => !document.querySelector('[data-speech-action=schema_preview]')?.hidden);
        await page.locator('[data-speech-action=schema_preview]').click();
        await page.waitForFunction(() => document.querySelector('#speech-schema-review')?.textContent.includes('lixity-audio-settings/4'));
        assert.match(await page.locator('#speech-schema-review').textContent(), /implicit narrator/);
        await page.locator('[data-speech-action=schema_apply]').click();
        await page.waitForFunction(() => !document.querySelector('#modal-speech')?.open);
        await page.locator('#tab-view-project').click();
        await page.locator('#settings-speech').click();
        await page.waitForFunction(() => document.querySelector('#speech-name')?.value === 'Narrator');
        await page.locator('#speech-engine').selectOption('openai-compatible');
        assert.equal(await page.locator('#speech-worker-guide').isVisible(), false,
          'The native worker setup guide is hidden for external providers');
        await page.locator('#speech-base_url').fill(server.fixture.provider);
        await page.locator('#speech-provider_model').fill('synthetic-model');
        await page.locator('#speech-provider_voice').fill('synthetic-voice');
        await page.locator('#speech-provider_language').fill('en');
        await page.locator('#modal-speech').screenshot({path: path.join(folder, 'provider.png')});
        await page.locator('[data-speech-action=save]').click();
        await page.waitForFunction(() => !document.querySelector('#modal-speech')?.open);
        await page.locator('#tab-view-project').click();
        await page.locator('#settings-speech-output').click();
        await page.waitForFunction(() => document.querySelector('#speech-engine')?.value === 'openai-compatible');
        await page.locator('[data-speech-action=preview]').click();
        await page.waitForFunction(() => !document.querySelector('#modal-speech audio')?.hidden);
        const requests = JSON.parse(fs.readFileSync(server.fixture.requests));
        assert.ok(requests.length > 0); assert.equal(requests[0].model, 'synthetic-model');
        assert.equal(requests[0].voice, 'synthetic-voice');
        await page.locator('[data-speech-action=chapter_render]').click();
        await page.waitForFunction(() => !document.querySelector('#modal-speech audio')?.hidden);
        const chapterRequests = JSON.parse(fs.readFileSync(server.fixture.requests));
        assert.ok(chapterRequests.some(row => row.input === 'The blue bird answers.'), 'Chapter rendering includes later paragraphs');
        await page.locator('[data-speech-action=chapter_render]').click();
        await page.waitForFunction(() => !document.querySelector('#modal-speech audio')?.hidden);
        assert.equal(JSON.parse(fs.readFileSync(server.fixture.requests)).length, chapterRequests.length, 'An unchanged external chapter reuses its cached audio');
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
        await page.route(server.fixture.url + '/', async route => {
          const response = await route.fetch();
          const html = (await response.text()).replace('data-speech-render-capable="true"', 'data-speech-render-capable="false"');
          await route.fulfill({response, body: html});
        });
        await page.goto(server.fixture.url);
        await page.locator('#tab-view-project').click();
        await page.locator('#settings-speech-output').click();
        await page.waitForFunction(() => document.querySelector('#speech-engine')?.value === 'openai-compatible');
        assert.equal(await page.locator('[data-speech-action=preview]').isVisible(), false);
        assert.equal(await page.locator('[data-speech-action=chapter_render]').isVisible(), false);
        await page.locator('[data-speech-action=direction_plan]').click();
        await page.waitForSelector('[data-speech-action=export_json]');
        assert.equal(JSON.parse(fs.readFileSync(server.fixture.requests)).length, chapterRequests.length);
        assert.deepEqual(fs.readFileSync(server.fixture.source), before);
        assert.deepEqual(errors, []);
      } finally { await page.close(); await server.close(); }
    }
    const bootstrapFolder = path.join(artifacts, 'dutch-bootstrap'); fs.mkdirSync(bootstrapFolder);
    const bootstrap = await startNativeServer(`
import json, os, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
import lixity.speech_status as status
base = Path(sys.argv[1]); root = base / 'project'; root.mkdir()
os.environ['XDG_DATA_HOME'] = str(base / 'app-data')
source = root / 'draft.md'; source.write_text('De rivier stroomt.')
(root / 'lixity.toml').write_text('language="nl"\\nmanuscript="draft.md"\\n')
status.worker_health = lambda target: {'target':target,'state':'unavailable','model':None}
LixityServerHandler.workspace_root = str(root)
LixityServerHandler.source_input = str(source)
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.language = 'nl'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1',0),LixityServerHandler)
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}'}),flush=True)
server.serve_forever()
`, bootstrapFolder);
    const page = await browser.newPage({viewport: {width: 320, height: 960}});
    try {
      await page.goto(bootstrap.fixture.url);
      await page.locator('#tab-view-project').click();
      await page.locator('#settings-speech').click();
      await page.locator('[data-speech-action=schema_preview]').click();
      await page.waitForFunction(() => document.querySelector('#speech-schema-review')?.textContent.includes('lixity-audio-settings/4'));
      assert.match(await page.locator('#speech-schema-review').textContent(), /nog geen stem/);
      await page.locator('[data-speech-action=schema_apply]').click();
      await page.waitForFunction(() => !document.querySelector('#modal-speech')?.open);
      await page.locator('#tab-view-project').click();
      await page.locator('#settings-speech-output').click();
      await page.waitForFunction(() => document.querySelector('#speech-chapter')?.options.length === 1);
      assert.equal(await page.locator('[data-speech-action=direction_plan]').isDisabled(), true, 'Unconfigured profiles cannot export a plan');
      await page.locator('#modal-speech [data-speech-action=close]').click();
      await page.locator('#settings-speech').click();
      await page.locator('[data-speech-action=create]').click();
      assert.equal(await page.locator('#speech-engine').inputValue(), 'openai-compatible');
      assert.equal(await page.locator('#speech-provider_language').inputValue(), 'nl');
      await page.locator('#speech-base_url').fill('http://127.0.0.1:8000/v1');
      await page.locator('#speech-provider_model').fill('synthetic');
      await page.locator('#speech-provider_voice').fill('synthetic');
      const saveRequest = page.waitForRequest(request => request.url().endsWith('/api/settings'));
      await page.locator('[data-speech-action=save]').click();
      assert.equal((await saveRequest).postDataJSON().audio.profiles.narrator.language, 'nl');
      await page.waitForFunction(() => !document.querySelector('#modal-speech')?.open);
      await page.locator('#tab-view-project').click();
      await page.locator('#settings-speech-output').click();
      await page.locator('[data-speech-action=direction_plan]').click();
      await page.waitForSelector('[data-speech-action=export_json]');
      assert.match(await page.locator('.speech-plan').textContent(), /De rivier stroomt/);
    } finally { await page.close(); await bootstrap.close(); }
    console.log(`Audio export/provider/audit desktop+mobile passed: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
