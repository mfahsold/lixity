(function() {
  "use strict";
  var dialog = document.getElementById("analysis-metric-context");
  if (!dialog) return;
  var data;
  try { data = JSON.parse(dialog.dataset.metricContext); }
  catch (error) {
    LixityLog.error("metric-context: invalid chapter measurements", error);
    return;
  }
  var trigger = null, chapterKey = null, selectedFeature = null, returnFocus = true;
  var body = document.getElementById("metric-context-values");
  var read = document.getElementById("metric-context-read");
  function text(id, value) { document.getElementById(id).textContent = value; }
  function cell(row, tag, value) {
    var node = document.createElement(tag);
    node.textContent = value;
    row.appendChild(node);
    return node;
  }
  function select(feature) {
    selectedFeature = feature;
    document.getElementById("metric-context-origin").hidden =
      !trigger.hasAttribute("data-dimension-loading") || feature !== trigger.dataset.metricFeature;
    var meta = data.features[feature], chapter = data.chapters[chapterKey];
    text("metric-context-title", meta.label);
    text("metric-context-chapter", chapter.title);
    text("metric-context-sample", chapter.sample);
    text("metric-context-definition", meta.help);
    text("metric-context-value", chapter.values[feature].value + " " + meta.unit);
    document.getElementById("metric-context-no-layer").hidden = Boolean(meta.layer);
    read.href = "#ch-" + chapterKey;
    body.replaceChildren();
    Object.keys(data.features).forEach(function(key) {
      var item = data.features[key], values = chapter.values[key];
      var row = document.createElement("tr");
      row.dataset.metricRow = key;
      row.classList.toggle("metric-context-selected", key === feature);
      var name = document.createElement("th"); name.scope = "row";
      var button = document.createElement("button");
      button.type = "button"; button.className = "ctl ctl-sm";
      button.textContent = item.label;
      button.setAttribute("aria-pressed", String(key === feature));
      button.addEventListener("click", function() {
        select(key);
        dialog.querySelector(".modal-body").scrollTop = 0;
        document.getElementById("metric-context-title").focus({preventScroll:true});
      });
      name.appendChild(button); row.appendChild(name);
      cell(row, "td", values.value + " " + item.unit);
      cell(row, "td", item.median + " · n = " + item.n);
      cell(row, "td", values.z);
      body.appendChild(row);
    });
  }
  function open(element) {
    var chapter = element.dataset.chapter;
    if (element.hasAttribute("data-dimension-loading")) {
      var selection = document.getElementById("dim-selection");
      chapter = selection && selection.dataset.chapter;
    }
    var feature = element.dataset.metricFeature;
    if (!data.chapters[chapter] || !data.features[feature]) {
      LixityLog.error("metric-context: selected measurement is unavailable");
      return false;
    }
    trigger = element; chapterKey = chapter; returnFocus = true;
    var origin = document.getElementById("metric-context-origin");
    origin.hidden = !element.hasAttribute("data-dimension-loading");
    origin.textContent = origin.hidden ? "" : "D" + element.dataset.dimensionIndex + " · " +
      data.labels.loading + ": " + new Intl.NumberFormat(document.documentElement.lang, {
        maximumFractionDigits:3, signDisplay:"exceptZero"
      }).format(Number(element.dataset.loading)) + ". " + data.labels.poles;
    select(feature);
    dialog.showModal();
    dialog.querySelector("[data-metric-close]").focus({preventScroll:true});
    return true;
  }
  dialog.querySelectorAll("[data-metric-close]").forEach(function(button) {
    button.addEventListener("click", function() { dialog.close(); });
  });
  dialog.addEventListener("close", function() {
    if (returnFocus && trigger && trigger.isConnected) trigger.focus({preventScroll:true});
  });
  read.addEventListener("click", function(event) {
    event.preventDefault();
    var target = document.getElementById("ch-" + chapterKey);
    if (!target) { LixityLog.error("metric-context: manuscript chapter is unavailable"); return; }
    var action = document.createElement("span");
    action.dataset.chapter = chapterKey;
    action.dataset.layer = data.features[selectedFeature].layer;
    returnFocus = false;
    dialog.close();
    jumpToChapter(action);
  });
  window.LixityMetricContext = {open:open};
})();
