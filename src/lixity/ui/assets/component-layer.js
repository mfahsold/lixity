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
