// Present the same backend deltas in the writing view and chapter matrix.
(function () {
  "use strict";
  const language = document.documentElement.lang || "en";
  const signed = [0, 1, 2].map(digits => new Intl.NumberFormat(language, {
    minimumFractionDigits: digits, maximumFractionDigits: digits, signDisplay: "exceptZero",
  }));
  const dateFormat = new Intl.DateTimeFormat(language, {dateStyle: "medium"});
  const formatSigned = (value, digits) => signed[digits].format(value);
  const visibleChange = (value, digits) => Number.isFinite(value) && Math.abs(value) >= 0.5 * 10 ** -digits;
  const percentagePointChange = value => uiFormat("measurement_percentage_point_change", {value: formatSigned(value, 1)});

  function chapterChanges(chapter) {
    if (chapter.match_status !== "matched") return {};
    const changes = {};
    if (visibleChange(chapter.words_delta, 0)) {
      changes.words_delta = formatSigned(chapter.words_delta, 0);
    }
    if (visibleChange(chapter.asl_delta, 1)) {
      changes.asl_delta = formatSigned(chapter.asl_delta, 1);
    }
    if (visibleChange(chapter.dialog_pct_delta, 1)) {
      changes.dialog_pct_delta = percentagePointChange(chapter.dialog_pct_delta);
    }
    return changes;
  }

  function baselineLabel(base) {
    if (!Number.isFinite(base?.created_at)) return "";
    const date = new Date(base.created_at * 1000);
    return Number.isFinite(date.getTime()) ? uiFormat("editor_pulse_since", {date: dateFormat.format(date)}) : "";
  }

  window.LixityRevisionMeasurements = {formatSigned, visibleChange, percentagePointChange, chapterChanges, baselineLabel};

  const matrix = document.getElementById("matrix");
  const baseline = document.getElementById("matrix-revision-baseline");
  if (!baseline || LixitySite.readOnly) return;
  const baselineText = baseline.querySelector("span");
  const rows = new Map(Array.from(matrix.querySelectorAll("[data-chapter-num]"), row => [Number(row.dataset.chapterNum), row]));
  let active = false;
  let generation = 0;

  function show(data) {
    matrix.querySelectorAll(".chapter-revision-delta").forEach(node => node.remove());
    baseline.hidden = true;
    const since = data?.has_baseline ? baselineLabel(data.base) : "";
    if (!since || !Array.isArray(data.chapter_deltas)) return;
    for (const chapter of data.chapter_deltas) {
      const row = rows.get(chapter?.num);
      if (!row) continue;
      const changes = chapterChanges(chapter);
      for (const cell of row.querySelectorAll("[data-revision-metric]")) {
        const value = changes[cell.dataset.revisionMetric];
        if (!value) continue;
        const delta = document.createElement("small");
        delta.className = "chapter-revision-delta";
        delta.textContent = value;
        cell.append(delta);
        baseline.hidden = false;
      }
    }
    baselineText.textContent = since;
  }

  async function load() {
    const request = ++generation;
    const {manuscriptProjectToken, manuscriptSourceSha256} = document.body.dataset;
    show(null);
    if (![manuscriptProjectToken, manuscriptSourceSha256].every(value => /^[a-f0-9]{64}$/.test(value))) return;
    const query = new URLSearchParams({project_token: manuscriptProjectToken});
    const result = await LixityComponents.jsonApi(API + "/manuscript-delta?" + query);
    if (!active || request !== generation || manuscriptProjectToken !== document.body.dataset.manuscriptProjectToken ||
        manuscriptSourceSha256 !== document.body.dataset.manuscriptSourceSha256) return;
    if (result.ok && result.schema_version === "lixity-timeline/1" && result.current?.revision === manuscriptSourceSha256) {
      show(result);
    }
  }

  function update() {
    const state = LixityWorkbench.state();
    const open = state.view === "analysis" && state.surface === "overview" && !matrix.hidden;
    if (open === active) return;
    active = open;
    if (open) load();
  }

  document.addEventListener("lixity:workbench-change", update);
  document.addEventListener("lixity:analysisworkflow", update);
  update();
})();
