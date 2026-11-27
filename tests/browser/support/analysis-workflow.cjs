// Follow the native editorial workflow chooser through visible controls.
const assert = require('node:assert/strict');

async function openAnalysisSection(page, target, {touch = false} = {}) {
  const navigation = page.locator('[data-analysis-workflows]');
  if (!await navigation.isVisible()) await page.locator('#workbench-overview-open').click();
  const activate = touch ? 'tap' : 'click';
  if (target === 'analysis-measurements') {
    const landing = navigation.locator('#analysis-measurements-tab');
    await landing[activate]();
    assert.equal(await landing.getAttribute('aria-pressed'), 'true');
    assert.equal(await page.locator(`#${target}`).isVisible(), true, 'The measured summary is visible');
    return;
  }
  const choice = navigation.locator(`[data-analysis-section-target="${target}"]`);
  assert.equal(await choice.count(), 1, `The workflow exposes the ${target} view`);
  const workflow = await choice.getAttribute('data-analysis-section-workflow');
  await navigation.locator(`[data-analysis-workflow="${workflow}"]`)[activate]();
  await choice[activate]();
  assert.equal(await choice.getAttribute('aria-pressed'), 'true');
  assert.equal(await page.locator(`#${target}`).isVisible(), true, `The chosen ${target} view is visible`);
}

module.exports = {openAnalysisSection};
