// Tense observations and author decisions remain separate from manuscript work markers.
(function() {
  "use strict";
  var panel = document.getElementById("flags");
  if (!panel) return;
  var rows = Array.from(panel.querySelectorAll(".flag-row"));
  var chapter = document.getElementById("triage-chapter");
  var severity = document.getElementById("triage-severity");
  var filter = document.getElementById("triage-status-filter");
  var progress = document.getElementById("triage-progress");
  var next = document.getElementById("triage-next");
  var status = document.getElementById("triage-save-status");
  var reload = document.getElementById("triage-reload");
  if (!rows.length || !next) return;
  var native = panel.dataset.reviewCapable === "true" && !window.LixitySite.readOnly;
  var accepted = null, pending = false, cursor = null;
  function token() { return document.body.dataset.manuscriptProjectToken; }
  function label(key) { return uiLabel("triage_" + key); }
  function visible() { return rows.filter(function(row) {return !row.hidden;}); }
  function apply() {
    rows.forEach(function(row) {
      row.hidden = Boolean(chapter.value && row.dataset.triageChapter !== chapter.value ||
        severity.value && row.dataset.triageSeverity !== severity.value ||
        filter && filter.value && row.dataset.reviewState !== filter.value);
    });
    var count = visible().length;
    progress.textContent = uiFormat("triage_progress", {shown:count, total:rows.length}) +
      (accepted ? " · " + uiFormat("triage_completed", {completed:accepted.completed, total:accepted.total}) : "");
    next.disabled = !count;
  }
  function controls(disabled) {
    panel.querySelectorAll(".triage-choice, [data-triage-save]").forEach(function(control) {
      control.disabled = disabled || !control.closest(".flag-row").dataset.observationId;
    });
  }
  function failed() {
    accepted = null;
    controls(true);
    rows.forEach(function(row) {
      row.dataset.reviewState = "unknown";
      row.querySelector(".triage-saved-state").textContent = label("unknown");
    });
    if (status) {status.textContent = label("unavailable"); status.className = "ctl-status err";}
    if (reload) reload.hidden = false;
    if (window.LixityLog) LixityLog.warn("Analysis review state unavailable");
    apply();
  }
  function accept(data) {
    if (!data.ok || data.schema_version !== "lixity-analysis-review/1" || !Array.isArray(data.observations) ||
        data.source_sha256 !== document.body.dataset.manuscriptSourceSha256 ||
        !["analysis_sha256", "review_sha256"].every(function(key) {return /^[0-9a-f]{64}$/.test(data[key] || "");}) ||
        !Number.isSafeInteger(data.total) || data.total !== rows.length || data.observations.length !== rows.length ||
        !Number.isSafeInteger(data.completed) || data.completed < 0 || data.completed > data.total ||
        !data.observations.every(function(item) {
          return item && Number.isSafeInteger(item.start_line) &&
            /^[0-9a-f]{64}$/.test(item.id || "") && /^[0-9a-f]{64}$/.test(item.paragraph_sha256 || "") &&
            ["unreviewed", "stale", "kept", "changed", "later"].includes(item.status);
        })) return false;
    var observations = new Map(data.observations.map(function(item) {
      return [item.start_line + ":" + item.paragraph_sha256, item];
    }));
    if (!rows.every(function(row) {return observations.has(row.dataset.line + ":" + row.dataset.reviewSha);})) return false;
    accepted = data;
    rows.forEach(function(row) {
      var item = observations.get(row.dataset.line + ":" + row.dataset.reviewSha);
      row.dataset.observationId = item.id;
      row.dataset.reviewState = item.status;
      row.querySelector(".triage-saved-state").textContent = label(item.status);
      row.querySelector(".triage-choice").value = ["kept", "changed", "later"].includes(item.status) ? item.status : "";
    });
    controls(false);
    reload.hidden = true;
    apply();
    return true;
  }
  async function load() {
    if (!native || pending) return;
    pending = true; controls(true);
    status.textContent = label("loading"); status.className = "ctl-status";
    var selected = token();
    var data = await jsonApi(API + "/analysis-review?project_token=" + encodeURIComponent(selected));
    pending = false;
    if (selected !== token() || !accept(data)) {failed(); return;}
    status.textContent = "";
  }
  if (reload) reload.addEventListener("click", load);
  [chapter, severity, filter].forEach(function(control) {if (control) control.addEventListener("change", apply);});
  next.addEventListener("click", function() {
    var candidates = visible();
    if (!candidates.length) return;
    var index = candidates.indexOf(cursor);
    cursor = candidates[(index + 1) % candidates.length];
    cursor.querySelector("[data-target]").click();
  });
  panel.addEventListener("click", function(event) {
    var save = event.target.closest("[data-triage-save]");
    if (event.target.closest("select, .triage-reason, [data-triage-save]")) event.stopPropagation();
    else if (event.target.closest(".flag-row")) cursor = event.target.closest(".flag-row");
    if (!save || pending || !accepted) return;
    var row = save.closest(".flag-row"), choice = row.querySelector(".triage-choice").value;
    if (!choice) {row.querySelector(".triage-choice").focus(); return;}
    var selected = token(), before = accepted;
    pending = true; controls(true);
    status.textContent = uiLabel("form_saving"); status.className = "ctl-status";
    jsonApi(API + "/analysis-review", {method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({project_token:selected, observation_id:row.dataset.observationId, status:choice,
        expected_source_sha256:before.source_sha256, expected_analysis_sha256:before.analysis_sha256,
        expected_review_sha256:before.review_sha256})}).then(function(data) {
      pending = false;
      if (selected !== token() || !accept(data)) {failed(); return;}
      status.textContent = label("saved"); status.className = "ctl-status ok";
      if (row.hidden) next.focus();
    });
  });
  panel.addEventListener("keydown", function(event) {
    if (event.key !== "Escape" && event.target.closest("select, .triage-reason, [data-triage-save]")) event.stopPropagation();
  });
  document.addEventListener("lixity:workbench-change", function() {
    if (native && !accepted && !pending && LixityWorkbench.state().surface === "overview") load();
  });
  apply();
})();
