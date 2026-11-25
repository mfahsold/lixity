/* Measure the production counted-results action and its reading-position return. */
async function benchmarkReader() {
  const select = (selector) => document.querySelector(selector);
  const nextFrame = () => new Promise(requestAnimationFrame);
  const visible = (node) => {
    if (!node?.getClientRects().length || getComputedStyle(node).visibility !== 'visible') return false;
    const box = node.getBoundingClientRect();
    return box.bottom > readingViewportTop() && box.top < innerHeight && box.right > 0 && box.left < innerWidth;
  };
  async function waitFor(check, failure) {
    const deadline = performance.now() + 20000;
    while (performance.now() < deadline) {
      const result = check();
      if (result) return result;
      await nextFrame();
    }
    throw new Error(failure);
  }

  await nextFrame();
  await nextFrame();
  await waitFor(() => !document.hidden && visible(select('#chapters .ptext-inner > p')),
    'No readable manuscript in the native viewport');
  const navigationMs = performance.now();

  if (!window.LixityWorkbench.state().analysisVisible) select('#manuscript-analysis-toggle').click();
  const metric = select('#style-layer');
  metric.value = 'dialogue';
  metric.dispatchEvent(new Event('change', {bubbles: true}));
  const opener = await waitFor(() => {
    const button = select('#reader-counted-results');
    return button?.getClientRects().length && !button.disabled && button;
  }, 'Counted results are unavailable');
  // Keep the initial paragraph below the sticky controls and leave the evidence off-screen.
  select('#chapters .ptext').scrollIntoView({block: 'center', behavior: 'instant'});
  await nextFrame();
  await nextFrame();
  opener.focus({preventScroll: true});
  const origin = window.LixityReader.capture();
  if (!origin?.panel.matches('.ptext')) throw new Error('Missing reading position');
  const target = [...document.querySelectorAll('#chapters .ptext')].find((panel) =>
    paragraphEvidenceCount(panel.id, 'dialogue') > 0);
  const batch = target && paragraphContent[target.id]?.[4]?.batch;
  const evidenceRequests = () => performance.getEntriesByType('resource').filter((entry) => {
    const url = new URL(entry.name);
    return url.pathname.endsWith('/paragraph-evidence') && url.searchParams.get('batch') === batch;
  });
  if (!batch || visible(target) || evidenceRequests().length || paragraphContent[target.id][3]) {
    throw new Error('The distant evidence batch is not cold');
  }

  const start = performance.now();
  opener.click();
  await waitFor(() => {
    const close = select('#analysis-evidence-card .analysis-evidence-close');
    const quote = select('#analysis-evidence-card blockquote');
    const count = select('#analysis-evidence-card .analysis-evidence-number');
    return quote?.textContent.includes('Wait here') && count?.textContent.trim() === '2' &&
      visible(target.querySelector('.ptext-inner > p')) && close === document.activeElement && visible(close);
  }, 'The counted two-word quotation did not arrive visibly with focus');
  await nextFrame();
  const jumpMs = performance.now() - start;
  const requests = evidenceRequests();
  if (requests.length !== 1) throw new Error('Expected one real evidence batch request');

  const back = select('#craft-jump-bar .passage-jump-actions button:last-child');
  if (!back?.getClientRects().length) throw new Error('The return control did not appear');
  const returning = performance.now();
  back.click();
  await waitFor(() => select('#analysis-evidence-card').hidden && select('#craft-jump-bar').hidden &&
    window.LixityReader.capture()?.panel === origin.panel && document.activeElement === opener &&
    Math.abs(origin.panel.getBoundingClientRect().top - origin.top) <= 2,
  'The reader did not return to the same position and control');
  await nextFrame();
  return JSON.stringify({
    navigation_to_readable_ms: +navigationMs.toFixed(2),
    first_evidence_jump_ms: +jumpMs.toFixed(2),
    evidence_request_ms: +requests[0].duration.toFixed(2),
    return_to_passage_ms: +(performance.now() - returning).toFixed(2),
    evidence_body_bytes: requests[0].decodedBodySize,
    return_offset_css_px: +(origin.panel.getBoundingClientRect().top - origin.top).toFixed(2),
  });
}
