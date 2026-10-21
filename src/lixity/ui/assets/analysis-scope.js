// Display only: every value and reference remains the accepted book analysis.
(function() {
  var scope = document.getElementById("analysis-scope");
  if (!scope) return;
  var register = document.getElementById("analysis-scope-register");
  var pov = document.getElementById("analysis-scope-pov");
  var fdr = document.getElementById("heatmap-fdr-only");
  var status = document.getElementById("analysis-scope-status");
  var empty = document.getElementById("heatmap-empty");
  var rows = Array.prototype.slice.call(document.querySelectorAll("#heatmap tbody tr[data-chapter-num]"));
  var numbers = new Intl.NumberFormat(document.documentElement.lang || "en");

  function apply() {
    var shown = 0;
    rows.forEach(function(row) {
      var matchesRegister = !register || !register.value || row.dataset.scopeRegister === register.value;
      var matchesPov = !pov || !pov.value || row.dataset.scopePov.split(" ").includes(pov.value);
      row.hidden = !(matchesRegister && matchesPov && (!fdr || !fdr.checked || Number(row.dataset.fdrCount) > 0));
      if (!row.hidden) shown++;
    });
    if (status) status.textContent = status.dataset.template
      .replace("{shown}", numbers.format(shown)).replace("{total}", numbers.format(rows.length));
    if (empty) {
      empty.textContent = scope.dataset.emptyLabel;
      empty.hidden = shown > 0;
    }
  }

  function clear() {
    if (register) register.value = "";
    if (pov) pov.value = "";
    if (fdr) fdr.checked = false;
    apply();
  }

  // Existing jump/hash owners call this before revealing their destination.
  function reveal(target) {
    var row = target && target.closest("#heatmap tbody tr[data-chapter-num]");
    if (row && row.hidden) clear();
  }

  [register, pov].forEach(function(control) {
    if (control) control.addEventListener("change", apply);
  });
  document.getElementById("analysis-scope-reset").addEventListener("click", clear);
  window.LixityAnalysisScope = {apply: apply, reveal: reveal};
  scope.hidden = false;
  apply();
})();
