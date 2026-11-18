// Follow the native editorial workflow chooser through visible controls.
const assert = require('node:assert/strict');

async function openAnalysisSection(page, target, {touch = false} = {}) {
  const navigation = page.locator('[data-analysis-workflows]');
  if (!await navigation.isVisible()) await page.locator('#workbench-overview-open').click();
  const choice = navigation.locator(`[data-analysis-section-target="${target}"]`);
  assert.equal(await choice.count(), 1, `The workflow exposes the ${target} view`);
  const workflow = await choice.getAttribute('data-analysis-section-workflow');
  await navigation.locator(`[data-analysis-workflow="${workflow}"]`)[touch ? 'tap' : 'click']();
  await choice[touch ? 'tap' : 'click']();
  assert.equal(await choice.getAttribute('aria-pressed'), 'true');
  assert.equal(await page.locator(`#${target}`).isVisible(), true, `The chosen ${target} view is visible`);
}

module.exports = {openAnalysisSection};
