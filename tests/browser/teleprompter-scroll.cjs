const {launchChromium} = require('../../scripts/browser_tools.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
 const browser = await launchChromium();
 try {
  const page = await browser.newPage({viewport:{width:1280,height:900}});
  await page.setContent('<button id="reader-teleprompter">Read</button><main id="chapters">'+[1,2].map(n=>`<section class="chapter" id="ch-${n}"><h2>Chapter ${n}</h2><div class="ptext" data-start="${n}" data-end="${n}" data-paragraph-sha256="paragraph-${n}"><div class="ptext-inner"><p>${'A synthetic sentence with several words. '.repeat(200)}</p></div></div></section>`).join('')+'</main>');
  await page.addStyleTag({content:fs.readFileSync(path.join(__dirname,'../../src/lixity/ui/assets/teleprompter.css'),'utf8')});
  await page.addScriptTag({content:fs.readFileSync(path.join(__dirname,'../../src/lixity/ui/assets/teleprompter.js'),'utf8')});
  await page.locator('#reader-teleprompter').click();
  const pane=page.locator('.teleprompter-scroll-pane');
  // Leave the reading line well inside the long first paragraph, nearer the next start.
  await pane.evaluate(el=>{
   el.style.scrollBehavior='auto';
   const p=el.querySelector('.teleprompter-paragraph');
   el.scrollTop=p.offsetTop + p.offsetHeight*.8;
   el.dispatchEvent(new Event('scroll'));
  });
  assert.equal(await page.locator('.teleprompter-paragraph.is-active').getAttribute('data-sha'),'paragraph-1');
  await pane.evaluate(el=>{
   const p=el.querySelectorAll('.teleprompter-paragraph')[1];
   el.scrollTop=p.offsetTop + 100;
   el.dispatchEvent(new Event('scroll'));
  });
  assert.equal(await page.locator('.teleprompter-select').inputValue(),'ch-2');
  await pane.evaluate(el=>{el.style.removeProperty('scroll-behavior');el.scrollTop=200;});
  const start=await pane.evaluate(el=>el.scrollTop);
  await page.locator('.teleprompter-btn-primary').click();
  await page.waitForTimeout(700);
  await page.locator('.teleprompter-btn-primary').click();
  const distance=await pane.evaluate(el=>el.scrollTop)-start;
  assert(distance > 15, `Playback advances continuously instead of restarting smooth scroll: ${distance}px`);
  await page.screenshot({path:'/tmp/lixity-teleprompter-scroll.png'});
  console.log('Long-paragraph reading position and chapter synchronization passed.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
