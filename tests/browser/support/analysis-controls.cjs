// Exercise the reader's directly available metric selector.
async function openAnalysisSettings(page) {
  await page.locator('#style-layer').waitFor({state: 'visible'});
}

async function selectMetric(page, key) {
  await openAnalysisSettings(page);
  await page.locator('#style-layer').selectOption(key);
}

module.exports = {openAnalysisSettings, selectMetric};
