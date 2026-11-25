// The dossier reader preserves authored document structure in every embedding.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-dossier-document-'));
const fixtures = pythonFixture(`
import json
from lixity.ui import render_dashboard
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
fixtures = {language: render_dashboard([], [], controls=True, language_key=language,
    labels={**get_language_profile(language).labels, **WORKSPACE_LABELS[language]},
    enabled_actions=['research-reader']) for language in ('en', 'de')}
fixtures['readonly'] = render_dashboard([], [], controls=True, read_only=True,
    enabled_actions=['research-reader', 'research-dossier-pdf'], research_context_token='0' * 64)
print(json.dumps(fixtures))
`);
const body = '# A\n\nFirst fragment.\n\n## Middle\n\nMiddle fragment.\n\n### Nested\n\nNested fragment.\n\n# A\n\nLast fragment.\n\n## Evidence\n\n> A synthetic quotation.\n\n| Item | Meaning |\n| --- | --- |\n| One | Original evidence |\n';
const detail = {id:'synthetic-dossier', project_id:'synthetic-project', revision:2,
  title:'Synthetic dossier', body, tags:[], citations:[], images:[], media:[],
  editable_sections:['Middle','Nested','Evidence'],
  section_map:{A:'First fragment.\n\n# A\n\nLast fragment.', Middle:'Middle fragment.', Nested:'Nested fragment.', Evidence:'A synthetic quotation.'}};

async function checkNativeDossierPdf(browser) {
  const server = await startNativeServer(`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
project = Path(sys.argv[1]) / 'synthetic-dossier-project'
project.mkdir()
manuscript = project / 'manuscript.md'
manuscript.write_text('## Erstes Kapitel\\n\\nDie Tür zum Garten steht offen.\\n', encoding='utf-8')
api.init(project, title='Synthetische Recherche', language='de')
dossier = api.create_dossier(project, 'Original dossier', 'Die erste Notiz zur Figur.')
claim = api.create_claim(project, title='Linked claim', statement='Eine synthetische Aussage.',
                         dossier_id=dossier['dossier_id'])
api.revise_record(project, 'dossier', dossier['dossier_id'], changes={
    'title': 'Current dossier', 'body': 'Die zweite Notiz zur Figur.'},
    expected_revision=1, change_kind='correction', reason='Synthetische Überarbeitung.')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.exports_dir = str(project / 'exports')
LixityServerHandler.language = 'de'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'id': dossier['dossier_id'],
    'claim': claim['claim_id']}), flush=True)
server.serve_forever()
`, artifacts);
  try {
    const {url, id} = server.fixture;
    const recordUrl = `${url}/api/research/record?kind=dossier&id=${encodeURIComponent(id)}`;
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}, acceptDownloads: true});
      page.setDefaultTimeout(8000);
      const requests = [], writes = [], errors = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => {
        const target = new URL(request.url());
        if (target.pathname === '/api/research/dossier-pdf') requests.push(target.searchParams);
        if (request.method() === 'POST' && target.pathname.startsWith('/api/research/')) writes.push(target.pathname);
      });
      try {
        const before = await (await page.request.get(recordUrl)).json();
        assert.equal(before.record.revision, 2);
        await page.goto(url);
        await page.locator('#tab-view-research').click();
        const summary = page.locator(`#research-dossiers-list [data-research-detail=dossier][data-record-id="${id}"]`);
        await summary.click();
        const card = summary.locator('..');
        const filename = {1: 'Original_dossier-v1.pdf', 2: 'Current_dossier-v2.pdf'};
        const downloadPdf = async (host, revision, name) => {
          const button = host.getByRole('button', {name: 'PDF herunterladen', exact: true});
          await expect(button).toBeVisible();
      await expect(button).toHaveAccessibleDescription(`Fassung ${revision} · Gespeicherter Text, vorhandene Ortsangaben und Quellenzitate`);
          await expect(button).toHaveAttribute('data-record-revision', String(revision));
          const requestCount = requests.length;
          const downloading = page.waitForEvent('download');
          await button.press('Enter');
          const download = await downloading;
          assert.equal(download.suggestedFilename(), filename[revision]);
          const downloaded = path.join(artifacts, `${name}-${width}.pdf`);
          await download.saveAs(downloaded);
          const bytes = fs.readFileSync(downloaded);
          assert.ok(bytes.subarray(0, 5).equals(Buffer.from('%PDF-')) && bytes.subarray(-20).toString().includes('%%EOF'));
          const extracted = spawnSync('pdftotext', [downloaded, '-'], {encoding: 'utf8'});
          if (!extracted.error || extracted.error.code !== 'ENOENT') {
            assert.equal(extracted.status, 0, extracted.stderr || extracted.error);
            assert.match(extracted.stdout, new RegExp(`Fassung ${revision}`));
            assert.ok(extracted.stdout.includes(`Die ${revision === 1 ? 'erste' : 'zweite'} Notiz zur Figur.`));
          }
          assert.equal(requests.length, requestCount + 1);
          assert.equal(requests.at(-1).get('id'), id);
          assert.equal(requests.at(-1).get('revision'), String(revision));
          assert.match(requests.at(-1).get('research_token'), /^[0-9a-f]{64}$/);
          await expect(host.locator('[data-dossier-pdf-status][role=status]')).toHaveText('PDF-Download gestartet.');
          await expect(button).toBeFocused();
        };
        if (width === 1440) {
          const button = card.locator('[data-dossier-pdf-export]');
          const errors = [
            [503, {}, 'Das PDF konnte nicht erzeugt werden.'],
            [409, {code: 'stale-context'}, 'Öffne das Projekt erneut'],
            [404, {}, 'Diese Fassung ist nicht verfügbar.'],
          ];
          for (const [status, data, message] of errors) {
            await page.route('**/api/research/dossier-pdf?*', route => route.fulfill({status, json: {ok: false, ...data}}), {times: 1});
            await button.press('Enter');
            await expect(card.locator('[data-dossier-pdf-status]')).toContainText(message);
            await expect(button).toBeEnabled();
            await expect(button).toBeFocused();
          }
        }
        await downloadPdf(card, 2, 'current-card');
        const toolbar = card.locator('.research-dossier-toolbar');
        await expect(toolbar.locator('[data-dossier-pdf-scope]')).toBeVisible();
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        if (width === 320) {
          await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
          try {
            for (const group of [toolbar, card.locator('.research-prose-bar')]) {
              assert.ok(await group.evaluate(node => node.scrollWidth <= node.clientWidth),
                'Dossier actions wrap within their group at 200% text size');
            }
          } finally {
            await page.evaluate(() => document.documentElement.style.removeProperty('font-size'));
          }
        }
        await card.locator('.research-dossier-folder').screenshot({path: path.join(artifacts, `dossier-pdf-${width}.png`)});
        await page.locator(`#research-dossiers-list [data-research-history=dossier][data-record-id="${id}"]`).click();
        const revisions = page.locator('#research-revision-versions');
        await revisions.locator(':scope > summary').click();
        await revisions.locator('[data-research-revision="1"]').click();
        const history = page.locator('#research-revision-history-detail');
        await expect(history).toContainText('Die erste Notiz zur Figur.');
        await expect(history.locator('[data-dossier-withdraw]')).toHaveCount(0);
        await downloadPdf(history, 1, 'pinned-version');
        if (width === 1440) {
          await page.evaluate(() => {
            window.lixityDesktop = {saveExport: (spec, filename) => new Promise((resolve, reject) => {
              window.pendingDossierExport = {spec, filename, resolve, reject};
            })};
          });
          const requestCount = requests.length;
          const button = history.locator('[data-dossier-pdf-export]');
          const status = history.locator('[data-dossier-pdf-status]');
          for (const [result, expected] of [
            [{saved: false}, ''],
            [{status: 404}, 'Diese Fassung ist nicht verfügbar.'],
            [{status: 409, serverCode: 'stale-context'}, 'Öffne das Projekt erneut'],
            [{status: 410}, 'Öffne das Projekt erneut'],
            [{saved: true}, 'PDF-Download gestartet.'],
          ]) {
            await button.press('Enter');
            await expect(button).toBeDisabled();
            const {spec, filename} = await page.evaluate(() => {
              const {spec, filename} = window.pendingDossierExport;
              return {spec, filename};
            });
            const target = new URL(spec.path, url);
            assert.equal(spec.method, 'GET');
            assert.equal(target.pathname, '/api/research/dossier-pdf');
            assert.equal(target.searchParams.get('id'), id);
            assert.equal(target.searchParams.get('revision'), '1');
            assert.equal(target.searchParams.get('research_token'), await button.getAttribute('data-research-token'));
            assert.equal(filename, 'dossier-v1.pdf');
            await page.evaluate(result => {
              const {resolve, reject} = window.pendingDossierExport;
              if (result.status) reject(result);
              else resolve(result);
            }, result);
            await expect(button).toBeEnabled();
            if (expected) await expect(status).toContainText(expected);
            else await expect(status).toHaveText('');
          }
          assert.equal(requests.length, requestCount, 'The desktop bridge owns every native PDF request');
          await page.evaluate(() => { delete window.lixityDesktop; });
        }
        await page.keyboard.press('Escape');
        await page.locator(`[data-workspace-dossier="${id}"]`).click();
        await downloadPdf(page.locator('#workspace-reader-body'), 2, 'alongside');
        assert.deepEqual(await (await page.request.get(recordUrl)).json(), before);
        assert.deepEqual(writes, []);
        assert.deepEqual(errors, []);
      } finally { await page.close(); }
    }
    await checkDossierWithdrawal(browser, server.fixture, recordUrl);
  } finally { await server.close(); }
}

async function checkDossierWithdrawal(browser, fixture, recordUrl) {
  const {url, id, claim} = fixture;
  const page = await browser.newPage({viewport:{width:320,height:900}});
  page.setDefaultTimeout(8000);
  const posts = [], errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/research-dossier') {
      posts.push(request.postDataJSON());
    }
  });
  function respondToConfirm(accept) {
    return page.waitForEvent('dialog').then(async dialog => {
      const message = dialog.message();
      await (accept ? dialog.accept() : dialog.dismiss());
      return message;
    });
  }
  try {
    await page.goto(url);
    await page.locator('#tab-view-research').click();
    const composer = page.locator('#r-dos-composer');
    const composerSummary = composer.locator(':scope > summary');
    await composerSummary.click();
    await page.locator('#r-dos-title').fill('Unsaved title');
    await page.locator('#r-dos-body').fill('Unsaved notes.');
    const discard = composer.getByRole('button', {name:'Entwurf verwerfen', exact:true});
    let confirmation = respondToConfirm(false);
    await discard.click();
    assert.match(await confirmation, /Dossierentwurf verwerfen/);
    await expect(page.locator('#r-dos-body')).toHaveValue('Unsaved notes.');
    confirmation = respondToConfirm(true);
    await discard.click();
    await confirmation;
    await expect(composerSummary).toBeFocused();
    await expect(page.locator('#r-dos-title')).toHaveValue('');
    await expect(page.locator('#r-dos-body')).toHaveValue('');
    assert.deepEqual(posts, [], 'Discard must neither create nor withdraw a dossier');

    const card = page.locator(`#research-dossiers-list [data-research-detail=dossier][data-record-id="${id}"]`).locator('..');
    const dialog = page.locator('#modal-research-revision');
    const edit = page.locator(`#research-dossiers-list [data-research-revise=dossier][data-record-id="${id}"]`);
    await edit.click();
    const editBody = dialog.locator('textarea[name=body]');
    await expect(editBody).toHaveValue('Die zweite Notiz zur Figur.');
    await dialog.locator('#research-revision-history-tab').click();
    await expect(dialog.locator('[data-dossier-withdraw]')).toBeVisible();
    await dialog.locator('#research-revision-edit-tab').click();
    await editBody.fill('Discard this unsaved revision.');
    await dialog.locator('#research-revision-history-tab').click();
    await expect(dialog.locator('[data-dossier-withdraw]')).toBeHidden();
    await dialog.locator('#research-revision-edit-tab').click();
    await dialog.getByRole('button', {name:'Änderungen verwerfen', exact:true}).click();
    await expect(dialog).toBeHidden();
    await expect(edit).toBeFocused();
    await edit.click();
    await expect(editBody).toHaveValue('Die zweite Notiz zur Figur.');
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    assert.deepEqual(posts, []);

    await card.locator('summary[data-research-detail]').click();
    const remove = card.getByRole('button', {name:'Dossier zurückziehen', exact:true});
    const before = await (await page.request.get(recordUrl)).json();
    const rootToken = await page.locator('#research-manager').getAttribute('data-research-token');
    const payload = {action:'withdraw', dossier_id:id, expected_revision:2, expected_snapshot:before.snapshot, dry_run:false};
    const endpoint = url + '/api/research-dossier';
    assert.equal((await page.request.post(endpoint,{data:payload})).status(),400,'A write without a root token is rejected');
    assert.equal((await page.request.post(endpoint,{data:{...payload,research_token:rootToken,dry_run:null}})).status(),400,
      'An absent or invalid preview/apply choice cannot withdraw the dossier');
    assert.equal((await page.request.post(endpoint,{data:{...payload,research_token:'0'.repeat(64)}})).status(),409,
      'A token from another root is rejected');
    assert.equal((await page.request.post(endpoint,{data:{...payload,research_token:rootToken,expected_revision:1}})).status(),409,
      'A stale dossier revision is rejected');
    assert.equal((await page.request.post(endpoint,{data:{...payload,research_token:rootToken,expected_snapshot:'0'.repeat(64)}})).status(),409,
      'A stale archive snapshot is rejected');
    confirmation = respondToConfirm(false);
    await remove.press('Enter');
    assert.match(await confirmation, /Current dossier.*Fassungen.*Verknüpfungen bleiben im Archiv/);
    await expect(remove).toBeFocused();
    assert.equal((await (await page.request.get(recordUrl)).json()).snapshot, before.snapshot);
    assert.deepEqual(posts.map(post => post.dry_run), [true], 'Cancel leaves the dry-run as the only request');

    await page.locator(`[data-workspace-dossier="${id}"]`).click();
    await expect(page.locator('#workspace-reader-body')).toContainText('Die zweite Notiz zur Figur.');
    await expect(page.locator('#workspace-reader-body [data-dossier-withdraw]')).toHaveCount(0);
    await page.locator('#tab-view-research').click();
    await page.locator(`#research-dossiers-list [data-research-history=dossier][data-record-id="${id}"]`).click();
    const withdraw = dialog.locator('[data-dossier-withdraw]');
    await expect(withdraw).toBeVisible();
    let releasePreview;
    const blockedPreview = new Promise(resolve => { releasePreview = resolve; });
    await page.route('**/api/research-dossier', async route => {
      await blockedPreview;
      await route.continue();
    }, {times:1});
    await withdraw.click();
    await expect(withdraw).toHaveAttribute('aria-busy','true');
    await dialog.locator('#research-revision-edit-tab').click();
    await expect(dialog.locator('#research-revision-history-tab')).toHaveAttribute('aria-selected','true');
    await page.keyboard.press('Escape');
    await expect(dialog).toBeVisible();
    confirmation = respondToConfirm(true);
    releasePreview();
    await confirmation;
    await expect(dialog).toBeHidden();
    await expect(card).toHaveCount(0);
    await expect(page.locator('#research-status-bar')).toContainText('Dossier zurückgezogen');
    await expect(page.locator('#workspace-reader-dossier')).not.toHaveValue(id);
    await expect(page.locator('#workspace-reader-body')).not.toContainText('Die zweite Notiz zur Figur.');
    assert.deepEqual(posts.map(post => post.dry_run), [true,true,false]);
    for (const actual of posts) {
      assert.equal(actual.research_token, rootToken);
      assert.equal(actual.expected_revision, 2);
      assert.equal(actual.expected_snapshot, before.snapshot);
    }
    const historical = await (await page.request.get(recordUrl + '&revision=1')).json();
    assert.equal(historical.record.body, 'Die erste Notiz zur Figur.');
    assert.equal(historical.availability, 'withdrawn');
    const linked = await (await page.request.get(`${url}/api/research/record?kind=claim&id=${encodeURIComponent(claim)}`)).json();
    assert.deepEqual(linked.record.dossier_ref, {id,revision:1});
    assert.deepEqual(errors, []);
  } finally { await page.close(); }
}

(async () => {
  const browser = await launchChromium();
  try {
    for (const locale of ['en','de']) for (const width of [1440,320]) {
      const page = await browser.newPage({viewport:{width,height:950},reducedMotion:'reduce'});
      const errors = [], writes = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => {if(request.method() === 'POST') writes.push(request.url());});
      await page.route('http://lixity.test/**', route => route.request().url() === 'http://lixity.test/' ?
        route.fulfill({contentType:'text/html',body:fixtures[locale]}) : route.fulfill({json:{ok:false}}));
      await page.goto('http://lixity.test/');
      await page.locator('#tab-view-research').click();
      await page.evaluate(detail => {
        const host = document.createElement('main');
        host.id = 'synthetic-dossier-documents';
        document.body.appendChild(host);
        host.innerHTML = '<div id="current-document">' + researchDossierDetailHtml(detail, false) + '</div>' +
          '<div id="embedded-document">' + researchDossierDetailHtml(detail, true, {recordView:true}) + '</div>';
      }, detail);
      for (const name of ['current-document','embedded-document']) {
        const host = page.locator('#' + name), prose = host.locator('.research-dossier-body-rendered');
        assert.deepEqual(await prose.locator('h1,h2,h3').evaluateAll(nodes => nodes.map(node => [node.tagName,node.textContent])),
          [['H1','A'],['H2','Middle'],['H3','Nested'],['H1','A'],['H2','Evidence']]);
        const text = await prose.textContent();
        assert.ok(text.indexOf('First fragment.') < text.indexOf('Middle fragment.'));
        assert.ok(text.indexOf('Middle fragment.') < text.indexOf('Nested fragment.'));
        assert.ok(text.indexOf('Nested fragment.') < text.indexOf('Last fragment.'));
        await expect(host.locator('.research-dossier-section-block')).toHaveCount(0);
        await expect(prose.locator('blockquote')).toContainText('A synthetic quotation.');
        await expect(prose.locator('table')).toContainText('Original evidence');
        assert.equal(await host.locator('[data-section-link]').count(), 7);
        await host.locator('[data-source-toggle]').click();
        assert.equal(await host.locator('.research-dossier-body-source').textContent(), body);
        await host.locator('[data-source-toggle]').click();
        await host.scrollIntoViewIfNeeded();
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      }
      const edits = page.locator('#current-document [data-dossier-section]');
      assert.deepEqual(await edits.evaluateAll(nodes => nodes.map(node => node.dataset.dossierSection)), ['Middle','Nested','Evidence']);
      await expect(page.locator('#embedded-document [data-dossier-section]')).toHaveCount(0);
      await expect(page.locator('#synthetic-dossier-documents [data-dossier-pdf-export]')).toHaveCount(0);
      const projected = await page.evaluate(detail => {
        const host = document.createElement('div');
        host.innerHTML = researchDossierDetailHtml({...detail, display_body: '## Reading projection\n\nOne copy.'}, true, {recordView:true});
        return {reading: host.querySelector('.research-dossier-body-rendered').textContent,
          source: host.querySelector('.research-dossier-body-source').textContent};
      }, detail);
      assert.match(projected.reading, /Reading projection[\s\S]*One copy\./);
      assert.ok(!projected.reading.includes('First fragment.'));
      assert.equal(projected.source, body, 'The reading projection preserves access to the pinned source');
      // CommonMark ATX headings need no blank line before following prose.
      const adjacent = await page.evaluate(() => {
        const host = document.createElement('div');
        host.innerHTML = renderSafeMarkdown('## Heading\nImmediate prose.\n### Child\nMore prose.');
        return {headings:Array.from(host.querySelectorAll('h2,h3'),node => node.textContent), text:host.textContent};
      });
      assert.deepEqual(adjacent.headings,['Heading','Child']);
      assert.ok(adjacent.text.includes('Immediate prose.') && adjacent.text.includes('More prose.'));
      const literals = await page.evaluate(() => {
        const host = document.createElement('div');
        host.innerHTML = renderSafeMarkdown('```text\n# Literal heading\n```\n\n## **Name & value** ###\n\nText <script>bad()</script>.');
        return {code:host.querySelector('code').textContent, headings:Array.from(host.querySelectorAll('h2'),node => node.textContent),
          raw:host.querySelector('h2').dataset.dossierHeading, scripts:host.querySelectorAll('script').length};
      });
      assert.equal(literals.code, '# Literal heading');
      assert.deepEqual(literals.headings, ['Name & value']);
      assert.equal(literals.raw, '**Name & value**');
      assert.equal(literals.scripts, 0);
      const attributes = await page.evaluate(() => {
        const title = 'Name " onclick="window.syntheticHeading=true';
        const host = document.createElement('div');
        host.innerHTML = researchDossierBodyHtml('## ' + title + '\n\nOriginal prose.', {
          id:'synthetic', revision:1, image_editable:true, editable_sections:[title]});
        const heading = host.querySelector('h2'), action = host.querySelector('[data-dossier-section]');
        return {heading:heading.dataset.dossierHeading, section:action && action.dataset.dossierSection,
          injected:!!host.querySelector('[onclick]')};
      });
      assert.equal(attributes.heading, 'Name " onclick="window.syntheticHeading=true');
      assert.equal(attributes.section, attributes.heading);
      assert.equal(attributes.injected, false);
      const codeHeadings = await page.evaluate(() => {
        const blocks = ['~~~text\n## Literal\ncode\n~~~', '````text\n## Literal\n```\n````', '    ## Literal\n    code'];
        return blocks.map(block => {
          const host = document.createElement('div');
          host.innerHTML = renderSafeMarkdown(block + '\n\n## Real\n\nOriginal prose.');
          return {headings:Array.from(host.querySelectorAll('h2'),node=>node.textContent), code:host.querySelector('pre code') && host.querySelector('pre code').textContent};
        });
      });
      codeHeadings.forEach(result => {
        assert.deepEqual(result.headings, ['Real']);
        assert.ok(result.code.includes('## Literal'));
      });
      const dollars = await page.evaluate(() => {
        const literal = ['$&', "$'", '$`'].join(' ');
        const host = document.createElement('div');
        host.innerHTML = renderSafeMarkdown('~~~text\n' + literal + '\n~~~');
        return {expected:literal, actual:host.querySelector('pre code').textContent, blocks:host.querySelectorAll('pre').length};
      });
      assert.equal(dollars.actual, dollars.expected);
      assert.equal(dollars.blocks, 1);
      const enhancedFormatting = await page.evaluate(() => {
        const doc = [
          '> [!NOTE]',
          '> **Arbeitsbegriff:** Conservazione senza decoro.',
          '',
          '[!IMPORTANT]',
          'Substanzerhaltung ohne jeden Zierrat.',
          '',
          'Abschnitt\tFrage',
          '1. Prinzip\tWas heißt das?',
          '',
          'Formula: $\\sigma^2 = \\frac{1}{N} \\sum (x_i - \\mu)^2$ and text \\textbf{fett} und \\textit{kursiv}.'
        ].join('\n');
        const host = document.createElement('div');
        host.innerHTML = renderSafeMarkdown(doc);
        return {
          alerts: host.querySelectorAll('.markdown-alert').length,
          alertTypes: Array.from(host.querySelectorAll('.markdown-alert')).map(el => el.className),
          tables: host.querySelectorAll('table.research-table').length,
          thCount: host.querySelectorAll('table.research-table th').length,
          tdCount: host.querySelectorAll('table.research-table td').length,
          mathInline: host.querySelectorAll('.math-inline').length,
          mathFrac: host.querySelectorAll('.math-frac').length,
          strong: Array.from(host.querySelectorAll('strong')).map(el => el.textContent),
          em: Array.from(host.querySelectorAll('em')).map(el => el.textContent)
        };
      });
      assert.equal(enhancedFormatting.alerts, 2);
      assert.ok(enhancedFormatting.alertTypes[0].includes('markdown-alert-note'));
      assert.ok(enhancedFormatting.alertTypes[1].includes('markdown-alert-important'));
      assert.equal(enhancedFormatting.tables, 1);
      assert.equal(enhancedFormatting.thCount, 2);
      assert.equal(enhancedFormatting.tdCount, 2);
      assert.equal(enhancedFormatting.mathInline, 1);
      assert.equal(enhancedFormatting.mathFrac, 1);
      assert.ok(enhancedFormatting.strong.includes('fett'));
      assert.ok(enhancedFormatting.em.includes('kursiv'));
      const mathSafety = await page.evaluate(detail => {
        const tag = '<img src="/synthetic-math.png">';
        const formulas = [
          '$' + tag + '$',
          '$$' + tag + '$$',
          '$&lt;img src="/synthetic-math.png"&gt;$',
          '$$\\begin{pmatrix}' + tag + ' & \\alpha \\\\ x < y & z > 0\\end{pmatrix}$$'
        ];
        const rendered = formulas.map(body => {
          const host = document.createElement('div');
          host.innerHTML = researchDossierDetailHtml({...detail, body}, true);
          const prose = host.querySelector('.research-dossier-body-rendered');
          return {images:prose.querySelectorAll('img').length, text:prose.textContent,
            cells:Array.from(prose.querySelectorAll('.math-cell'), cell => cell.textContent.trim())};
        });
        const literals = ['`$' + tag + '$`', '```text\n$' + tag + '$\n```'].map(body => {
          const host = document.createElement('div');
          host.innerHTML = renderSafeMarkdown(body);
          return {images:host.querySelectorAll('img').length, code:host.querySelector('code').textContent,
            math:host.querySelectorAll('[role="math"]').length};
        });
        return {rendered, literals};
      }, detail);
      mathSafety.rendered.forEach(result => {
        assert.equal(result.images, 0, 'Inline, display and matrix math keep authored HTML inert');
        assert.ok(result.text.includes('<img src="/synthetic-math.png">'), 'Math preserves literal angle-bracket text');
      });
      assert.deepEqual(mathSafety.rendered[3].cells, ['<img src="/synthetic-math.png">', 'α', 'x < y', 'z > 0'],
        'Safe recursive cells preserve comparisons, matrix boundaries and TeX symbols');
      mathSafety.literals.forEach(result => {
        assert.equal(result.images, 0);
        assert.equal(result.code, '$<img src="/synthetic-math.png">$');
        assert.equal(result.math, 0, 'Code literals bypass dollar-math recognition');
      });
      await page.locator('#current-document').screenshot({path:path.join(artifacts,`document-${locale}-${width}.png`)});
      assert.deepEqual(errors, []);
      assert.deepEqual(writes, []);
      await page.close();
    }
    const readOnly = await browser.newPage();
    try {
      await readOnly.route('http://lixity.test/', route => route.fulfill({contentType: 'text/html', body: fixtures.readonly}));
      await readOnly.goto('http://lixity.test/');
      assert.equal(await readOnly.evaluate(detail => {
        const host = document.createElement('div');
        host.innerHTML = researchDossierDetailHtml({...detail, snapshot: 'a'.repeat(64)}, false, {recordView: true});
        return host.querySelectorAll('[data-dossier-pdf-export], [data-dossier-withdraw]').length;
      }, detail), 0, 'Read-only dossier pages never advertise a native download or withdrawal');
    } finally { await readOnly.close(); }
    await checkNativeDossierPdf(browser);
    console.log('Dossier document: authored structure, exact native PDF downloads, draft discard, reviewed withdrawal and preserved history passed. ' + artifacts);
  } finally {await browser.close();}
})().catch(error => {console.error(error);process.exitCode=1;});
