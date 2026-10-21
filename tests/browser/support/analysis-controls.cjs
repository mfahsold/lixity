// Exercise the reader's single native metric selector through its visible disclosure.
async function openAnalysisSettings(page) {
  const settings = page.locator('#reader-analysis-settings');
  if (await settings.count() && !await settings.evaluate(node => node.open)) await settings.locator('summary').first().click();
}

async function selectMetric(page, key) {
  await openAnalysisSettings(page);
  await page.locator('#style-layer').selectOption(key);
  const settings = page.locator('#reader-analysis-settings');
  if (await settings.count() && await settings.evaluate(node => node.open)) await settings.locator('summary').first().click();
}

module.exports = {openAnalysisSettings, selectMetric};
