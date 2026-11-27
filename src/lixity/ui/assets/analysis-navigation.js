// Native editorial workflows progressively reveal existing, stateful panels.
(function() {
  "use strict";
  var host = document.querySelector('#analysis-outline-document[data-guided-analysis="1"]');
  var controls = host && host.querySelector('[data-analysis-workflows]');
  var panels = host && host.querySelector('#manuscript-analysis-panels');
  if (!controls || !panels) return;
  var landingButton = controls.querySelector('#analysis-measurements-tab');
  var nextPassage = host.querySelector('#analysis-next-passage');
  var entries = Array.from(controls.querySelectorAll('[data-analysis-workflow]'));
  var choices = Array.from(controls.querySelectorAll('[data-analysis-section-target]'));
  var chooser = controls.querySelector('.analysis-workflow-sections');
  var byId = new Map(Array.from(panels.children, function(panel) { return [panel.id, panel]; }));
  var landing = byId.get("analysis-measurements");
  if (!landing || !landingButton) return;
  var workflowByPanel = new Map([[landing, null]]);
  var firstByWorkflow = new Map();
  choices.forEach(function(choice) {
    var section = byId.get(choice.dataset.analysisSectionTarget);
    var workflow = choice.dataset.analysisSectionWorkflow;
    if (!section) return;
    workflowByPanel.set(section, workflow);
    if (!firstByWorkflow.has(workflow)) firstByWorkflow.set(workflow, section);
  });
  // Leave the readable document and its direct links in place if the chooser
  // cannot address all of its advertised sections.
  if (choices.some(function(choice) { return !byId.has(choice.dataset.analysisSectionTarget); }) ||
      entries.some(function(entry) { return !firstByWorkflow.has(entry.dataset.analysisWorkflow); })) return;
  var remembered = new Map();
  var current = null;
  function major(target) {
    if (!target || target === panels || !panels.contains(target)) return null;
    while (target.parentElement !== panels) target = target.parentElement;
    return workflowByPanel.has(target) ? target : null;
  }
  function select(workflow, target) {
    target = target || remembered.get(workflow) || firstByWorkflow.get(workflow);
    if (!target || !workflowByPanel.has(target)) return;
    current = workflow;
    if (workflow) remembered.set(workflow, target);
    workflowByPanel.forEach(function(_, section) { section.hidden = section !== target; });
    landingButton.setAttribute('aria-pressed', String(target === landing));
    if (nextPassage) nextPassage.hidden = target !== landing;
    entries.forEach(function(entry) { entry.setAttribute('aria-pressed', String(entry.dataset.analysisWorkflow === current)); });
    choices.forEach(function(choice) {
      choice.hidden = choice.dataset.analysisSectionWorkflow !== current;
      choice.setAttribute('aria-pressed', String(choice.dataset.analysisSectionTarget === target.id));
    });
    if (chooser) chooser.hidden = !current;
    document.dispatchEvent(new CustomEvent('lixity:analysisworkflow', {
      detail: {workflow: current, section: target.id}
    }));
  }
  function reveal(target) {
    var section = major(target);
    if (section && section.hidden) select(workflowByPanel.get(section), section);
    return Boolean(section);
  }
  function openReport(target) {
    if (!workflowByPanel.has(target)) return;
    scrollAndFlash(target, {analysisVisible: true});
    var heading = target.querySelector(":scope > summary, :scope > h2, :scope > header h2") ||
      document.getElementById(target.getAttribute("aria-labelledby")) || target;
    if (!heading.matches("summary, [tabindex]")) heading.tabIndex = -1;
    heading.focus({preventScroll: true});
  }
  landingButton.addEventListener('click', function() {
    select(null, landing);
    openReport(landing);
  });
  controls.addEventListener('click', function(event) {
    var entry = event.target.closest('[data-analysis-workflow]');
    if (entry) { select(entry.dataset.analysisWorkflow); return; }
    var choice = event.target.closest('[data-analysis-section-target]');
    if (choice) openReport(byId.get(choice.dataset.analysisSectionTarget));
  });
  function hashTarget() {
    var id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch (_) { return null; }
    return id ? document.getElementById(id) : null;
  }
  function showSections(event) {
    event.preventDefault();
    var entry = entries.find(function(button) { return button.dataset.analysisWorkflow === current; }) || landingButton;
    entry.focus({preventScroll: true});
    if (typeof scrollAndFlash === "function") scrollAndFlash(entry, {behavior: "instant"});
  }
  var sectionsLink = document.getElementById("workbench-overview-sections");
  if (sectionsLink) sectionsLink.addEventListener("click", showSections);
  document.body.classList.add("has-guided-analysis");
  window.LixityAnalysisNavigation = {
    reveal: reveal,
    showMeasurements: function() { select(null, landing); }
  };
  window.addEventListener('hashchange', function() { reveal(hashTarget()); });
  var linkedSection = major(hashTarget());
  select(linkedSection ? workflowByPanel.get(linkedSection) : null, linkedSection || landing);
})();
