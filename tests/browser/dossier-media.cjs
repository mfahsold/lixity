// Real synthetic PDF/video files exercise the shared native and exported UI.
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn, execFileSync} = require('node:child_process');
const {once} = require('node:events');
const {createInterface} = require('node:readline');
const assert = require('node:assert/strict');
const {expect} = require(path.join(playwrightModule, 'test'));
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-dossier-media-'));
const python = process.env.PYTHON_BIN || path.join(root, '.venv/bin/python');
const env = {...process.env, PYTHONPATH: path.join(root, 'src')};

(async () => {
  const server = spawn(python, ['-u', '-c', `
import functools, json, subprocess, sys, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from lixity.research import api
from lixity.server import LixityServerHandler
from tests.test_research_ocr import make_synthetic_pdf
base = Path(sys.argv[1]); project = base / 'project'
api.init(project, title='Synthetic media workspace')
(project / 'manuscript.md').write_text('# The gate\\n\\n## Arrival\\n\\nThe gate was open.\\n')
(project / 'lixity.toml').write_text('manuscript = "manuscript.md"\\nlanguage = "en"\\n')
(base / 'note.pdf').write_bytes(make_synthetic_pdf('A synthetic gate survey.'))
for suffix, codec in [('mp4', 'libx264'), ('webm', 'libvpx')]:
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
        'color=c=0x6594a3:s=160x90:r=10:d=0.5', '-an', '-c:v', codec, '-pix_fmt', 'yuv420p',
        str(base / ('clip.' + suffix))], check=True, timeout=30)
dossier = api.create_dossier(project, title='Synthetic media dossier', body='## Survey\\n\\nRead the evidence, then decide.')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.language = 'en'; LixityServerHandler.refresh()
class Static(SimpleHTTPRequestHandler):
    def log_message(self, *_args): pass
static = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Static, directory=str(base)))
threading.Thread(target=static.serve_forever, daemon=True).start()
native = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{native.server_port}',
    'static': f'http://127.0.0.1:{static.server_port}', 'project': str(project),
    'dossier': dossier['dossier_id']}), flush=True)
native.serve_forever()
`, artifacts], {cwd: root, env, stdio: ['ignore', 'pipe', 'pipe']});
  let stderr = '', browser;
  server.stderr.on('data', data => { stderr += data; });
  const lines = createInterface({input: server.stdout});
  try {
    const fixture = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Fixture startup timed out: ' + stderr)), 60000);
      lines.once('line', line => { clearTimeout(timer); resolve(JSON.parse(line)); });
      server.once('exit', code => { clearTimeout(timer); reject(new Error(`Fixture exited ${code}: ${stderr}`)); });
    });
    browser = await launchChromium();
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [], external = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (!request.url().startsWith(fixture.url) && !request.url().startsWith(fixture.static) &&
          !request.url().startsWith('blob:') && !request.url().startsWith('file:')) external.push(request.url());
    });
    await page.goto(fixture.url);
    await page.locator('#tab-view-research').click();
    await page.locator('[data-rtab=dossiers]').click();
    await page.locator(`[data-research-detail=dossier][data-record-id="${fixture.dossier}"]`).click();
    const dialog = page.locator('#modal-dossier-image');
    for (const [index, filename] of ['note.pdf', 'clip.webm', 'clip.mp4'].entries()) {
      await page.locator('[data-dossier-add-media]').click();
      await expect(dialog).toBeVisible();
      await page.locator('#dossier-image-file').setInputFiles(path.join(artifacts, filename));
      await expect(page.locator('#dossier-image-preview')).toContainText(filename);
      await page.locator('#dossier-image-alt').fill('Synthetic ' + filename);
      await expect(page.locator('#dossier-image-save')).toBeDisabled();
      if (index === 0) {
        await page.keyboard.press('Escape');
        const sources = await (await page.request.get(fixture.url + '/api/research/sources')).json();
        assert.equal(sources.sources.length, 0, 'Cancel retains no bytes');
        await page.locator('[data-dossier-add-media]').click();
        await page.locator('#dossier-image-file').setInputFiles(path.join(artifacts, filename));
        await page.locator('#dossier-image-alt').fill('Synthetic ' + filename);
      }
      await page.locator('#dossier-image-retention').check();
      await page.locator('#dossier-image-save').click();
      await expect(dialog).not.toBeVisible();
      await expect(page.locator('.research-dossier-body-rendered .dossier-retained-media')).toHaveCount(index + 1);
    }
    const rendered = page.locator('.research-dossier-body-rendered');
    await expect(rendered.locator('iframe, object, embed')).toHaveCount(0);
    await expect(rendered.locator('video')).toHaveCount(2);
    await expect(rendered.locator('video').first()).toHaveAttribute('preload', 'none');
    assert.equal(await rendered.locator('video[autoplay]').count(), 0);
    await rendered.locator('video').first().evaluate(video => video.play());
    await expect.poll(() => rendered.locator('video').first().evaluate(video => video.currentTime)).toBeGreaterThan(0);
    await rendered.locator('video').first().evaluate(video => video.pause());
    const download = page.waitForEvent('download');
    await rendered.locator('.dossier-retained-media a[download]').first().click();
    const downloaded = await download;
    assert.equal(await downloaded.failure(), null);
    await downloaded.saveAs(path.join(artifacts, 'downloaded.pdf'));
    assert.deepEqual(fs.readFileSync(path.join(artifacts, 'downloaded.pdf')), fs.readFileSync(path.join(artifacts, 'note.pdf')));
    for (const width of [1440, 320]) {
      await page.setViewportSize({width, height: 1000});
      await rendered.scrollIntoViewIfNeeded();
      assert.ok(await rendered.evaluate(node => node.getBoundingClientRect().right <= innerWidth));
      await page.screenshot({path: path.join(artifacts, `native-${width}.png`), fullPage: true});
    }
    await page.locator(`[data-research-history=dossier][data-record-id="${fixture.dossier}"]`).click();
    await page.locator('#research-revision-versions > summary').click();
    await page.locator('[data-research-revision="2"]').click();
    const history = page.locator('#modal-research-revision .research-revision-dossier');
    await expect(history.locator('.dossier-retained-media')).toHaveCount(1);
    await expect(history.locator('[data-dossier-add-media]')).toHaveCount(0);
    await page.keyboard.press('Escape');
    execFileSync(python, ['-c', `
import sys
from pathlib import Path
from lixity.config import prepare_project_settings
from lixity.site_export import export_site
project, dossier, base = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
prepare_project_settings(project, {'site_publications': {'readers': {
    'title': 'Synthetic media companion', 'entries': [{'dossier_id': dossier}]}}}).commit()
for name, include in [('with-files', True), ('without-files', False)]:
    export_site(project, base / name, mode='companion', publication_profile='readers', include_source_files=include)
`, fixture.project, fixture.dossier, artifacts], {cwd: root, env});
    for (const width of [1440, 320]) {
      await page.setViewportSize({width, height: 1000});
      await page.goto(fixture.static + '/with-files/index.html');
      await expect(page.locator('.dossier-retained-media')).toHaveCount(3);
      await expect(page.locator('video')).toHaveCount(2);
      await expect(page.locator('[data-dossier-add-media]')).toHaveCount(0);
      await page.locator('video').first().evaluate(video => video.play());
      await expect.poll(() => page.locator('video').first().evaluate(video => video.currentTime)).toBeGreaterThan(0);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({path: path.join(artifacts, `companion-${width}.png`), fullPage: true});
    }
    await page.goto(fixture.static + '/without-files/index.html');
    await expect(page.locator('video, .dossier-retained-media a[download]')).toHaveCount(0);
    await expect(page.locator('.dossier-image-unavailable')).toHaveCount(3);
    assert.deepEqual(external, [], 'No remote media requests');
    assert.deepEqual(errors, []);
    console.log(`Dossier media passed: retained PDF/MP4/WebM, native consent/cancel, PDF bytes, WebM playback, pinned history, scoped static export and 1440/320 layouts. Screenshots: ${artifacts}`);
  } finally {
    if (browser) await browser.close();
    lines.close();
    if (server.exitCode === null) { const exited = once(server, 'exit'); server.kill(); await exited; }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
