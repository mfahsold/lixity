/* Chapter register drafts use the existing token-bound settings transaction. */
(function() {
  "use strict";
  var editor = document.getElementById("register-editor");
  if (!editor) return;
  var initial = JSON.parse(editor.dataset.initial);
  var labels = JSON.parse(editor.dataset.labels);
  var features = JSON.parse(editor.dataset.features);
  var serial = 0;
  var profiles = editor.querySelector("[data-register-profiles]");
  var assignments = editor.querySelector("[data-register-assignments]");
  function control(parent, key, value, options) {
    var wrapper = document.createElement("label");
    wrapper.className = "setting-field";
    wrapper.appendChild(document.createTextNode(labels[key]));
    var input = document.createElement(options ? "select" : "input");
    input.className = "ctl";
    input.id = "register-field-" + (++serial);
    input.dataset.registerField = key;
    if (options) options.forEach(function(option) {
      var item = document.createElement("option");
      item.value = option[0]; item.textContent = option[1]; input.appendChild(item);
    });
    input.value = value == null ? "" : value;
    if (key === "register_lower" || key === "register_upper") {
      input.type = "number"; input.min = "0"; input.step = "any";
    } else input.required = true;
    wrapper.appendChild(input); parent.appendChild(wrapper);
    return input;
  }
  function button(parent, text, action, attribute) {
    var node = document.createElement("button");
    node.type = "button"; node.className = "ctl"; node.textContent = text;
    if (attribute) node.setAttribute(attribute, "");
    node.addEventListener("click", action); parent.appendChild(node); return node;
  }
  function remove(parent, node) {
    button(parent, labels.remove_recent_project, function() {
      var focus = node.previousElementSibling || node.nextElementSibling || node.parentElement;
      var fallback = node.hasAttribute("data-register-profile") ? editor.querySelector("[data-register-add-profile]") :
        node.hasAttribute("data-register-assignment") ? editor.querySelector("[data-register-add-assignment]") :
        node.closest("[data-register-profile]").querySelector("[data-register-add-target]");
      node.remove();
      updateNames();
      var target = focus.querySelector("input, select, button");
      (target || fallback).focus();
    }, "data-register-remove");
  }
  function target(card, feature, bounds) {
    var row = document.createElement("div"); row.className = "register-range";
    row.setAttribute("data-register-range", "");
    control(row, "register_target", feature || features[0][0], features);
    control(row, "register_lower", bounds && bounds[0]);
    control(row, "register_upper", bounds && bounds[1]);
    remove(row, row); card.querySelector("[data-register-ranges]").appendChild(row);
    return row;
  }
  function profile(name, ranges) {
    var card = document.createElement("div"); card.className = "register-profile";
    card.setAttribute("data-register-profile", "");
    control(card, "register_name", name).maxLength = 100;
    var list = document.createElement("div"); list.setAttribute("data-register-ranges", ""); card.appendChild(list);
    Object.keys(ranges || {}).forEach(function(key) {
      var bounds = ranges[key];
      if (typeof bounds === "number") bounds = [bounds, bounds];
      if (!Array.isArray(bounds)) bounds = [bounds.lower, bounds.upper];
      target(card, key, bounds);
    });
    var actions = document.createElement("div"); actions.className = "row"; card.appendChild(actions);
    button(actions, labels.register_add_target, function() { target(card).querySelector("select").focus(); }, "data-register-add-target");
    remove(actions, card); profiles.appendChild(card); return card;
  }
  function assignment(selector, name) {
    var row = document.createElement("div"); row.className = "register-assignment";
    row.setAttribute("data-register-assignment", "");
    control(row, "register_selector", selector);
    control(row, "register_name", name).setAttribute("list", "register-name-options");
    remove(row, row); assignments.appendChild(row); return row;
  }
  var names = document.createElement("datalist"); names.id = "register-name-options"; editor.appendChild(names);
  function updateNames() {
    names.replaceChildren();
    profiles.querySelectorAll('[data-register-field="register_name"]').forEach(function(input) {
      var option = document.createElement("option"); option.value = input.value; names.appendChild(option);
    });
    editor.querySelectorAll("input, select").forEach(function(input) { input.setCustomValidity(""); });
  }
  Object.keys(initial.register_profiles).forEach(function(name) { profile(name, initial.register_profiles[name]); });
  Object.keys(initial.chapter_registers).forEach(function(key) { assignment(key, initial.chapter_registers[key]); });
  updateNames(); editor.addEventListener("input", updateNames);
  editor.querySelector("[data-register-add-profile]").addEventListener("click", function() { profile("").querySelector("input").focus(); });
  editor.querySelector("[data-register-add-assignment]").addEventListener("click", function() { assignment("").querySelector("input").focus(); });
  function field(node, key) { return node.querySelector('[data-register-field="' + key + '"]'); }
  function invalid(input) { input.setCustomValidity(labels.register_invalid); }
  function read() {
    editor.querySelectorAll("input, select").forEach(function(input) { input.setCustomValidity(""); });
    var result = {register_profiles: Object.create(null), chapter_registers: Object.create(null)};
    profiles.querySelectorAll("[data-register-profile]").forEach(function(card) {
      var nameInput = field(card, "register_name"); var name = nameInput.value;
      if (!name.trim() || Object.hasOwn(result.register_profiles, name)) invalid(nameInput);
      var ranges = Object.create(null);
      card.querySelectorAll("[data-register-range]").forEach(function(row) {
        var feature = field(row, "register_target");
        var lower = field(row, "register_lower"); var upper = field(row, "register_upper");
        if (Object.hasOwn(ranges, feature.value)) invalid(feature);
        var bounds = Object.create(null);
        if (lower.value !== "") bounds.lower = lower.valueAsNumber;
        if (upper.value !== "") bounds.upper = upper.valueAsNumber;
        var maximum = feature.value === "hd_d" ? 1 : (/_pct$/.test(feature.value) || feature.value === "first_person_start_rate") ? 100 : Infinity;
        if (!Object.keys(bounds).length || (bounds.lower != null && bounds.upper != null && bounds.lower > bounds.upper) ||
            (bounds.lower != null && bounds.lower > maximum) || (bounds.upper != null && bounds.upper > maximum)) invalid(upper);
        ranges[feature.value] = bounds;
      });
      result.register_profiles[name] = ranges;
    });
    assignments.querySelectorAll("[data-register-assignment]").forEach(function(row) {
      var selector = field(row, "register_selector"); var name = field(row, "register_name");
      if (!selector.value.trim() || Object.hasOwn(result.chapter_registers, selector.value)) invalid(selector);
      if (!Object.hasOwn(result.register_profiles, name.value)) invalid(name);
      result.chapter_registers[selector.value] = name.value;
    });
    return result;
  }
  var initialNormalized = JSON.stringify(read());
  window.LixityRegisterSettings = {
    readChanges: function() {
      if (editor.disabled) return {};
      var value = read();
      return JSON.stringify(value) === initialNormalized ? {} : value;
    },
    accepted: function(value) { initialNormalized = JSON.stringify(value); }
  };
})();
