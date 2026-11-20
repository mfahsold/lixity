// Native editorial workflows progressively reveal existing, stateful panels.
(function() {
  "use strict";
  var host = document.querySelector('#analysis-outline-document[data-guided-analysis="1"]');
  var controls = host && host.querySelector('[data-analysis-workflows]');
  var panels = host && host.querySelector('#manuscript-analysis-panels');
  if (!controls || !panels) return;
  var groups;
  try { groups = JSON.parse(controls.dataset.analysisWorkflows); }
  catch (_) { return; } // Keep the full readable document when configuration is unavailable.
  var ids = Object.values(groups).flat();
  var sections = Array.from(panels.children).filter(function(node) {
    return ids.includes(node.id);
  });
  document.body.classList.add("has-guided-analysis");
  var entries = Array.from(controls.querySelectorAll('[data-analysis-workflow]'));
  var choices = Array.from(controls.querySelectorAll('[data-analysis-section-target]'));
  var chooser = controls.querySelector('.analysis-workflow-sections');
  var current = null, remembered = {};
  function major(target) {
    if (!target || target === panels || !panels.contains(target)) return null;
    while (target.parentElement !== panels) target = target.parentElement;
    return sections.includes(target) ? target : null;
  }
  function workflowFor(section) {
    return Object.keys(groups).find(function(key) { return groups[key].includes(section.id); }) || "explore";
  }
  function select(workflow, target) {
    var ids = groups[workflow] || [];
    target = target || document.getElementById(remembered[workflow] || ids[0]);
    target = major(target);
    current = workflow;
    if (workflow && target) remembered[workflow] = target.id;
    sections.forEach(function(section) { section.hidden = section !== target; });
    if (target && target.id === "analysis-measurements") target.open = true;
    entries.forEach(function(entry) { entry.setAttribute('aria-pressed', String(entry.dataset.analysisWorkflow === current)); });
    choices.forEach(function(choice) {
      choice.hidden = choice.dataset.analysisSectionWorkflow !== current;
      choice.setAttribute('aria-pressed', String(Boolean(target && choice.dataset.analysisSectionTarget === target.id)));
    });
    if (chooser) chooser.hidden = !current;
    host.dataset.analysisActiveWorkflow = current || "";
    document.dispatchEvent(new CustomEvent('lixity:analysisworkflow', {detail: {workflow:current, section:target && target.id}}));
  }
  function reveal(target) {
    var section = major(target);
    if (section && (section.hidden || (section.id === "analysis-measurements" && !section.open))) {
      select(workflowFor(section), section);
    }
    return Boolean(section);
  }
  controls.addEventListener('click', function(event) {
    var entry = event.target.closest('[data-analysis-workflow]');
    if (entry) { select(entry.dataset.analysisWorkflow); return; }
    var choice = event.target.closest('[data-analysis-section-target]');
    if (choice) {
      var target = document.getElementById(choice.dataset.analysisSectionTarget);
      select(choice.dataset.analysisSectionWorkflow, target);
      if (target && typeof scrollAndFlash === 'function') scrollAndFlash(target, {analysisVisible:true});
    }
  });
  function hashTarget() {
    var id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch (_) { return null; }
    return id ? document.getElementById(id) : null;
  }
  // Stable existing navigation remains in the DOM for links and command search;
  // the workflow chooser replaces its exhaustive visual feature lists.
  ['analysis-sections', 'analysis-outline-nav'].forEach(function(id) {
    var nav = document.getElementById(id);
    if (!nav) return;
    var contents = nav.closest('[data-section-contents]');
    (contents || nav).hidden = true;
  });
  window.LixityAnalysisNavigation = {reveal:reveal};
  window.addEventListener('hashchange', function() { reveal(hashTarget()); });
  var linkedSection = major(hashTarget());
  var landing = sections.find(function(section) { return section.id === "analysis-measurements"; }) || sections[0];
  select(linkedSection ? workflowFor(linkedSection) : null, linkedSection || landing);
})();
