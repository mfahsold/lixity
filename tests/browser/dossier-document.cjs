// The dossier reader preserves authored document structure in every embedding.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-dossier-document-'));
const fixtures = pythonFixture(`
import json
from lixity.ui import render_dashboard
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
print(json.dumps({language: render_dashboard([], [], controls=True, language_key=language,
    labels={**get_language_profile(language).labels, **WORKSPACE_LABELS[language]},
    enabled_actions=['research-reader']) for language in ('en', 'de')}))
`);
const body = '# A\n\nFirst fragment.\n\n## Middle\n\nMiddle fragment.\n\n### Nested\n\nNested fragment.\n\n# A\n\nLast fragment.\n\n## Evidence\n\n> A synthetic quotation.\n\n| Item | Meaning |\n| --- | --- |\n| One | Original evidence |\n';
const detail = {id:'synthetic-dossier', project_id:'synthetic-project', revision:2,
  title:'Synthetic dossier', body, tags:[], citations:[], images:[], media:[],
  editable_sections:['Middle','Nested','Evidence'],
  section_map:{A:'First fragment.\n\n# A\n\nLast fragment.', Middle:'Middle fragment.', Nested:'Nested fragment.', Evidence:'A synthetic quotation.'}};

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
      await page.locator('#current-document').screenshot({path:path.join(artifacts,`document-${locale}-${width}.png`)});
      assert.deepEqual(errors, []);
      assert.deepEqual(writes, []);
      await page.close();
    }
    console.log('Dossier document: source order/depth, repeated headings, exact edit targets, quotes/tables, source bytes, independent embeddings and adjacent headings passed at desktop/mobile. ' + artifacts);
  } finally {await browser.close();}
})().catch(error => {console.error(error);process.exitCode=1;});
