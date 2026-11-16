// Follow the same source-detail entry as the author; never assign controller state.
const path = require('node:path');
const {playwrightModule} = require('../../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));

async function openSourceComparison(page, sourceId) {
  await page.locator('[data-rtab=sources]').click();
  const summary = page.locator(`#research-sources-list [data-research-detail=source][data-record-id="${sourceId}"]`);
  await expect(summary).toBeVisible();
  if (!await summary.evaluate(node => node.parentElement.open)) await summary.click();
  await summary.locator('..').locator(`[data-research-source-compare="${sourceId}"]`).click();
  await expect(page.locator('#research-tool-host')).toBeVisible();
  await expect(page.locator('#r-ground-btn')).toBeVisible();
}

module.exports = {openSourceComparison};
