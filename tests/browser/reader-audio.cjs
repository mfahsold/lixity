// A shared static player must never imply synthesis, auto-reveal or autoplay.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {launchChromium, launchFirefox, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const {pythonFixture} = require('./support/python-fixture.cjs');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-reader-audio-'));
function observeSpectrum(page) {
  return page.addInitScript(()=>{
    window.measuredFrequencyPeak=0;window.mediaGraphSources=0;
    const measure=AnalyserNode.prototype.getByteFrequencyData;
    AnalyserNode.prototype.getByteFrequencyData=function(values){measure.call(this,values);window.measuredFrequencyPeak=Math.max(window.measuredFrequencyPeak,...values);};
    const attach=AudioContext.prototype.createMediaElementSource;
    AudioContext.prototype.createMediaElementSource=function(element){window.mediaGraphSources++;return attach.call(this,element);};
  });
}
const fixtures = pythonFixture(String.raw`
import base64, hashlib, io, json, math, struct, wave
from lixity.language import get_language_profile
from lixity.ui.publication import render_publication
from lixity.ui.dashboard import _script_json
from lixity.ui.manuscript_document import ReaderBlock
recordings = {}
tracks = []
for number in (1, 2):
    output = io.BytesIO()
    with wave.open(output, 'wb') as writer:
        writer.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        # A real spectrum must be observed even when the browser output is muted.
        writer.writeframes(b''.join(struct.pack('<h', int(8000 * math.sin(2 * math.pi * 440 * sample / 24000)))
                                    for sample in range(24000 * number)))
    content = output.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    filename = 'assets/audio/' + digest + '.wav'
    recordings[filename] = base64.b64encode(content).decode()
    tracks.append({'chapter':number,'title':'Arrival' if number == 1 else 'Return',
        'file':filename,'sha256':digest,'byte_length':len(content),'duration_seconds':float(number),
        'origin':'generated' if number == 1 else 'imported'})
publication = {'schema_version':'lixity-reader-publication/2','mode':'reader','title':'Synthetic reading copy',
    'introduction':'Read, listen and consult the context.','max_chapter':3,'chapters':[{'number':i} for i in (1,2,3)],
    'identity':'a'*64,'source_sha256':'b'*64,'profile':'readers','project_id':'synthetic',
    'entries':[{'id':'entry-1','title':'Before reading','body':'A public place.','reveal_after_chapter':0},
               {'id':'entry-2','title':'Later context','body':'The hidden key.','reveal_after_chapter':2}],
    'audio':{'schema_version':'lixity-reader-audio/1','source_sha256':'b'*64,'tracks':tracks}}
blocks = []
for i, title in enumerate(('Arrival', 'Return', 'A new morning'), 1):
    blocks.extend([ReaderBlock('heading',title,i*4,i*4,is_chapter=True),
                   ReaderBlock('paragraph','The gate opened in the morning.',i*4+2,i*4+2)])
documents = {}
for locale in ('en', 'de'):
    html = render_publication(publication, reader_document=blocks,
        labels=get_language_profile(locale).labels,language_key=locale,analysis_available=True)
    envelope = {'schema_version':'lixity-read-only-site-data/1','responses':{},'resources':{},'publication':publication}
    documents[locale] = html.replace('<script>', '<script type="application/json" id="lixity-site-data">' + _script_json(envelope) + '</script><script>', 1)
print(json.dumps({'documents':documents,'recordings':recordings}))
`);
(async () => {
  const browser = await (process.argv.includes('--firefox') ? launchFirefox() : launchChromium());
  try {
    for (const [locale, html] of Object.entries(fixtures.documents)) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce'});
      const errors = [], requests = [];
      page.on('pageerror', e => errors.push(e.message));
      page.on('request', r => requests.push(r.url()));
      await observeSpectrum(page);
      await page.route('http://reader.test/**', route => {
        const member = new URL(route.request().url()).pathname.slice(1);
        const audio = fixtures.recordings[member];
        return route.fulfill(audio ? {contentType:'audio/wav',body:Buffer.from(audio, 'base64')} :
          {contentType:'text/html',body:html});
      });
      await page.goto('http://reader.test/');
      const section = page.locator('#publication-audio');
      const audio = page.locator('#publication-audio-player');
      await expect(section).not.toHaveAttribute('open', '');
      if (width === 1440) assert.ok((await page.locator('#publication-chapter-1').boundingBox()).y < 650);
      await page.locator('a[href="#publication-audio"]').click();
      await expect(section.locator('.speech-player')).toBeVisible();
      await expect(section).toContainText(locale === 'de' ? '2 von 3' : '2 of 3');
      assert.equal(await audio.evaluate(a => a.paused), true);
      await expect(page.locator('#publication-entries article')).toHaveCount(1);
      await section.locator('.speech-player-controls > button').click();
      await expect.poll(() => audio.evaluate(a => a.currentTime)).toBeGreaterThan(0);
      await section.locator('summary').click();
      await expect.poll(() => audio.evaluate(a => a.paused)).toBe(true);
      await page.locator('a[href="#publication-audio"]').click();
      assert.equal(await audio.evaluate(a => a.paused), true);
      await expect.poll(()=>page.evaluate(()=>window.measuredFrequencyPeak)).toBeGreaterThan(0);
      await section.locator('.speech-player-volume input').fill('0.3');
      assert.equal(await audio.evaluate(a => a.volume), 0.3);
      await page.locator('#publication-audio-chapter').selectOption('2');
      await expect.poll(() => audio.evaluate(a => a.duration)).toBe(2);
      assert.equal(await audio.evaluate(a => a.paused), true);
      assert.equal(await audio.evaluate(a => a.currentTime), 0);
      await expect(page.locator('#publication-audio-status')).toContainText(locale === 'de' ? 'Importierte' : 'Imported');
      await expect(page.locator('#publication-audio-text')).toHaveAttribute('href', '#publication-chapter-2');
      const download = await Promise.all([page.waitForEvent('download'), page.locator('#publication-audio-download').click()]);
      assert.equal(download[0].suggestedFilename(), 'chapter-2.wav');
      await expect(page.locator('#publication-progress')).toHaveValue('0');
      await expect(page.locator('#publication-entries article')).toHaveCount(1);
      await page.locator('#publication-audio-text').click();
      await expect(page.locator('#publication-chapter-2')).toBeInViewport();
      await expect(page.locator('#publication-progress')).toHaveValue('0');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
      await section.scrollIntoViewIfNeeded();
      await page.screenshot({path:path.join(artifacts,`${locale}-${width}.png`)});
      assert.deepEqual(errors, []);
      assert(requests.every(url => url.startsWith('http://reader.test/')));
      assert(!requests.some(url => url.includes('/api/')));
      await page.close();
    }
    // The documented unzip-and-open route has a file origin, unlike hosted copies.
    const local=path.join(artifacts,'offline');fs.mkdirSync(path.join(local,'assets/audio'),{recursive:true});
    fs.writeFileSync(path.join(local,'index.html'),fixtures.documents.en);
    for(const [name,encoded] of Object.entries(fixtures.recordings))fs.writeFileSync(path.join(local,name),Buffer.from(encoded,'base64'));
    const offline=await browser.newPage({viewport:{width:320,height:900}}),offlineRequests=[],offlineErrors=[];
    offline.on('request',request=>offlineRequests.push(request.url()));offline.on('pageerror',error=>offlineErrors.push(error.message));
    await observeSpectrum(offline);
    await offline.goto(pathToFileURL(path.join(local,'index.html')).href);
    const offlineAudio=offline.locator('#publication-audio-player');
    await offline.locator('a[href="#publication-audio"]').click();
    assert.equal(await offlineAudio.evaluate(audio=>audio.paused),true);
    await offline.locator('#publication-audio-chapter').selectOption('2');
    await offline.locator('#publication-audio .speech-player-controls > button').click();
    await expect.poll(()=>offlineAudio.evaluate(audio=>audio.currentTime)).toBeGreaterThan(0);
    assert.equal(await offline.evaluate(()=>window.mediaGraphSources),0,
      'Local-file playback must not enter the Chromium-silent cross-origin Web Audio graph');
    await expect(offline.locator('.speech-player-spectrum-state')).toHaveText(await offline.evaluate(()=>uiLabel('speech_player_spectrum_unavailable')));
    await offlineAudio.evaluate(audio=>audio.pause());
    assert.deepEqual(offlineErrors,[]);assert.ok(offlineRequests.every(url=>url.startsWith('file:')));
    assert.ok(!offlineRequests.some(url=>url.includes('/api/')));
    await offline.close();
    console.log(`Reader audio passed; screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
