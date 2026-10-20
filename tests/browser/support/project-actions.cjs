// Follow the same native disclosure path as a reader before project commands.
async function openProjectActions(page) {
  const disclosure = page.locator('#project-actions');
  if (!(await disclosure.evaluate(element => element.open))) {
    await disclosure.locator(':scope > summary').click();
  }
}

module.exports = {openProjectActions};
