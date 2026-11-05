// Shared entry point for the vendored Preact + HTM component layer.
//
// Panels render through LixityComponents.mount() so the component layer owns
// its host subtree. Preact appends into a container that still carries
// server-rendered markup (the first render keeps unmatched placeholder
// elements), so the first mount clears the host instead of leaving the
// server-side loading placeholder beside the rendered tree.
//
// Load order: after the vendor files, before any panel that renders
// components (see _JS_FILES in lixity/ui/dashboard.py).
(function () {
  "use strict";
  window.LixityComponents = {
    html: htm.bind(preact.h),
    // Dynamic editors share the same field markup as server-rendered forms.
    createField: function (parent, spec) {
      var type = spec.type || "text", checkbox = type === "checkbox";
      var wrapper = document.createElement("label"), label = document.createElement("span");
      wrapper.className = checkbox ? "form-checkbox" : "setting-field";
      if (!checkbox) label.className = "form-label";
      label.textContent = spec.label;
      var input = document.createElement(type === "select" || type === "textarea" ? type : "input");
      if (input.tagName === "INPUT") input.type = type;
      if (!checkbox) input.className = "ctl";
      if (spec.id) input.id = spec.id;
      if (spec.help) input.dataset.help = spec.help;
      if (checkbox) { input.checked = spec.value === true; wrapper.append(input, label); }
      else { input.value = spec.value == null ? "" : spec.value; wrapper.append(label, input); }
      parent.appendChild(wrapper);
      return input;
    },
    recordLabel: function (record, fallback) {
      if (record) {
        for (var key of ["title", "name"]) {
          if (typeof record[key] === "string" && record[key].trim()) return record[key].trim();
        }
      }
      return fallback;
    },
    overlaySpace: function (node) {
      var host = node.offsetParent;
      if (!host) return {left: 0, top: 0, bounds: null};
      var rect = host.getBoundingClientRect();
      var left = rect.left + host.clientLeft, top = rect.top + host.clientTop;
      return {left: left - host.scrollLeft, top: top - host.scrollTop,
        bounds: {left: left, top: top, right: left + host.clientWidth, bottom: top + host.clientHeight}};
    },
    placeOverlay: function (node, left, top, space) {
      space = space || this.overlaySpace(node);
      node.style.left = (left - space.left) + "px";
      node.style.top = (top - space.top) + "px";
    },
    mount: function (host, vnode) {
      if (!host.__lixityMounted) {
        host.replaceChildren();
        host.__lixityMounted = true;
      }
      preact.render(vnode, host);
    },
    unmount: function (host) {
      host.replaceChildren();
      preact.render(null, host);
      host.__lixityMounted = false;
    },
  };
})();
