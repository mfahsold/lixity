async function openAnalysisSettings(page) {
  await page.locator('#style-layer').waitFor({state: 'visible'});
  const options = page.locator('#reader-analysis-options');
  if (await options.count() && !await options.evaluate(details => details.open)) {
    await options.locator(':scope > summary').click();
  }
}

async function selectMetric(page, key) {
  await page.locator('#style-layer').selectOption(key);
}

async function closeAnalysisSettings(page) {
  const options = page.locator('#reader-analysis-options[open]');
  if (await options.count()) await options.locator(':scope > summary').press('Enter');
}

async function setAnalysisOption(page, id, checked) {
  const alreadyOpen = await page.locator('#reader-analysis-options[open]').count();
  await openAnalysisSettings(page);
  await page.locator(`#${id}`).setChecked(checked);
  if (!alreadyOpen) await closeAnalysisSettings(page);
}

module.exports = {closeAnalysisSettings, openAnalysisSettings, selectMetric, setAnalysisOption};
