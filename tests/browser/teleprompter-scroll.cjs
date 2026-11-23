const {launchChromium} = require('../../scripts/browser_tools.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
 const browser = await launchChromium();
 try {
  const page = await browser.newPage({viewport:{width:1280,height:900}});
  await page.setContent('<button id="reader-teleprompter">Read</button><main id="chapters">'+[1,2].map(n=>`<section class="chapter" id="ch-${n}"><h2>Chapter ${n}</h2><div class="ptext" data-start="${n}" data-end="${n}" data-paragraph-sha256="paragraph-${n}"><div class="ptext-inner"><p>${'A synthetic sentence with several words. '.repeat(200)}</p></div></div></section>`).join('')+'</main>');
  const assets = path.join(__dirname,'../../src/lixity/ui/assets');
  for (const filename of ['design-tokens.css', 'teleprompter.css']) {
   await page.addStyleTag({content:fs.readFileSync(path.join(assets,filename),'utf8')});
  }
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
  const clock = await page.evaluateHandle(() => {
   let nextFrame = null;
   let timestamp = 1000;
   window.requestAnimationFrame = callback => {
    nextFrame = callback;
    return 1;
   };
   window.cancelAnimationFrame = () => { nextFrame = null; };
   return {
    advance(count) {
     for (let index = 0; index < count; index++) {
      const callback = nextFrame;
      nextFrame = null;
      timestamp += 8;
      callback?.(timestamp);
     }
    },
   };
  });
  const playback = page.locator('.teleprompter-btn-primary');
  await playback.click();
  // At 130 words/minute and 28px, 8ms frames each contribute about 0.46px.
  await clock.evaluate(frames => frames.advance(46)); // The first frame establishes the timestamp.
  assert.equal(await pane.evaluate(el => el.scrollTop), start + 20, 'Playback advances between short frames');
  await pane.evaluate(el => { el.scrollTop += 100; });
  await clock.evaluate(frames => frames.advance(45));
  const pausedAt = start + 100 + 41;
  assert.equal(await pane.evaluate(el => el.scrollTop), pausedAt, 'Playback continues from the manually scrolled position');
  await playback.click();
  await clock.evaluate(frames => frames.advance(45));
  assert.equal(await pane.evaluate(el => el.scrollTop), pausedAt, 'Pause stops the automatic scroll');
  const speed = page.locator('.teleprompter-speed-control input');
  await speed.press('Home');
  assert.equal(await speed.inputValue(), '60');
  await playback.click();
  await clock.evaluate(frames => frames.advance(91));
  assert.equal(await pane.evaluate(el => el.scrollTop), pausedAt + 19, 'Slow playback covers 19 pixels in 720ms');
  await playback.click();
  await clock.dispose();
  await page.screenshot({path:'/tmp/lixity-teleprompter-scroll.png'});
  console.log('Long-paragraph reading position and chapter synchronization passed.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
