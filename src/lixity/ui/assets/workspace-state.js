// Display intent has one owner; domain records and drafts keep their own owners.
(function() {
  "use strict";
  var active = document.querySelector(".view-pane.active");
  var value = {view: active ? active.dataset.viewPane : "analysis", analysisVisible: false,
    surface: "document", contextTool: "none", focus: false, transient: null};
  var listeners = [], suspendedTool = "none", focusSnapshot = null;
  function snapshot() { return Object.freeze(Object.assign({}, value)); }
  function dispatch(command) {
    var previous = snapshot();
    // A tool request leaves focus by restoring its arrangement before applying intent.
    if (value.focus && ["analysis", "surface", "tool", "view"].includes(command.type)) {
      Object.assign(value, focusSnapshot); value.focus = false; focusSnapshot = null;
    }
    if (command.type === "view") {
      if (!["analysis", "research", "project"].includes(command.value)) return;
      value.view = command.value; value.transient = null;
    } else if (command.type === "analysis") {
      value.analysisVisible = Boolean(command.value);
      if (!value.analysisVisible) {
        if (value.contextTool === "analysis") value.contextTool = "none";
        if (value.surface === "overview") {
          value.surface = "document";
          value.contextTool = suspendedTool === "dossier" ? "dossier" : "none";
        }
      } else if (value.contextTool === "none" && value.surface === "document") value.contextTool = "analysis";
    } else if (command.type === "surface") {
      if (command.value === "overview") {
        if (value.surface !== "overview") suspendedTool = value.contextTool;
        value.analysisVisible = true; value.surface = "overview"; value.contextTool = "none";
      } else if (value.surface === "overview") {
        value.surface = "document"; value.contextTool = suspendedTool;
      }
      value.transient = null;
    } else if (command.type === "tool") {
      if (!["none", "analysis", "dossier"].includes(command.value)) return;
      value.surface = "document"; value.contextTool = command.value;
      if (command.value === "analysis") value.analysisVisible = true;
      value.transient = null;
    } else if (command.type === "focus") {
      if (command.value && !value.focus) {
        focusSnapshot = snapshot(); value.focus = true; value.surface = "document"; value.contextTool = "none";
      } else if (!command.value && value.focus) {
        Object.assign(value, focusSnapshot); value.focus = false; focusSnapshot = null;
      }
    } else if (command.type === "transient") value.transient = command.value || null;
    else return;
    var next = snapshot();
    if (Object.keys(next).every(function(key) { return next[key] === previous[key]; })) return;
    document.body.classList.toggle("workbench-analysis", next.analysisVisible);
    document.body.classList.toggle("workbench-overview", next.surface === "overview");
    document.body.classList.toggle("reader-focus", next.focus && next.view === "analysis");
    listeners.slice().forEach(function(listener) { listener(next, previous); });
    document.dispatchEvent(new CustomEvent("lixity:workbench-change", {detail: next}));
  }
  window.LixityWorkbench = {state: snapshot, dispatch: dispatch, subscribe: function(listener) {
    listeners.push(listener); return function() { listeners = listeners.filter(function(item) { return item !== listener; }); };
  }};
})();
