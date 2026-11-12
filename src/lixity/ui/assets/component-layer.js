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
    icon: function (name, options) {
      var markup = window.LixityIcons && typeof window.LixityIcons.render === "function"
        ? window.LixityIcons.render(name, options)
        : "";
      return preact.h("span", {
        className: "lixity-icon-slot",
        "aria-hidden": "true",
        dangerouslySetInnerHTML: { __html: markup }
      });
    },
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

  // Central distraction-free chrome controller (Headroom scroll-direction + idle timeout).
  // Anchors auto-hide behavior across reader, editor, saved-revision reader, and teleprompter
  // toolbars without shifting document layout or breaking keyboard focus (:focus-within).
  (function initLixityChrome() {
    var CHROME_SELECTOR = [
      "#manuscript-reader-controls",
      ".manuscript-reading .toolbar",
      ".manuscript-editor-toolbar",
      "#manuscript-reading .manuscript-reading-bar",
      ".teleprompter-toolbar"
    ].join(", ");
    var IDLE_MS = 3500;
    var DOWN_DELTA_THRESHOLD = 36;
    var UP_DELTA_THRESHOLD = -16;
    var TOP_PIN_THRESHOLD = 64;
    var TOP_HOVER_ZONE = 72;

    var hidden = false;
    var idleTimer = 0;
    var userScrollUntil = 0;
    var accumDelta = 0;
    var lastScrollTops = new WeakMap();

    function getBars() {
      return Array.from(document.querySelectorAll(CHROME_SELECTOR));
    }

    function isPrimaryScrollTarget(target) {
      if (!target || target === document || target === document.documentElement || target === document.body) {
        return true;
      }
      return Boolean(
        target.nodeType === 1 &&
        target.matches(".cm-scroller, .teleprompter-scroll-pane")
      );
    }

    function getScrollTop(target) {
      if (!target || target === document || target === document.documentElement || target === document.body) {
        return window.scrollY || document.documentElement.scrollTop || 0;
      }
      return target.scrollTop || 0;
    }

    function getActiveScrollDepth() {
      if (document.body.classList.contains("manuscript-writing")) {
        var cmScroller = document.querySelector("#manuscript-editor-host .cm-scroller");
        if (cmScroller) return Math.max(window.scrollY || 0, cmScroller.scrollTop || 0);
      }
      var telePane = document.querySelector("#teleprompter-modal:not([hidden]) .teleprompter-scroll-pane");
      if (telePane) return telePane.scrollTop || 0;
      return window.scrollY || document.documentElement.scrollTop || 0;
    }

    function shouldHoldVisible() {
      if (!document.body) return true;
      if (document.documentElement.style.fontSize === "200%" || window.innerHeight <= 500) return true;
      var active = document.activeElement;
      if (active && active !== document.body && active.closest && active.closest(CHROME_SELECTOR)) {
        return true;
      }
      if (document.querySelector("#reader-settings[open], #reader-analysis-guide[open]")) return true;
      var ctxMenu = document.getElementById("manuscript-context-menu");
      if (ctxMenu && !ctxMenu.hidden) return true;
      var selTools = document.getElementById("manuscript-selection-tools");
      if (selTools && !selTools.hidden) return true;
      var search = document.getElementById("text-search");
      if (search && (document.activeElement === search || search.value.trim().length > 0)) return true;
      if (document.body.classList.contains("text-search-active")) return true;
      var saveStatus = document.querySelector("#manuscript-save-status");
      if (saveStatus && (saveStatus.dataset.state === "conflict" || saveStatus.dataset.state === "error")) {
        return true;
      }
      var recovery = document.querySelector("#manuscript-recovery");
      if (recovery && recovery.value) return true;
      return false;
    }

    function canAutoHideByIdle() {
      if (!document.body || shouldHoldVisible()) return false;
      if (document.body.classList.contains("reader-focus")) return true;
      if (document.body.classList.contains("manuscript-writing")) return true;
      if (document.querySelector("#teleprompter-modal:not([hidden])")) return true;
      if (document.querySelector("#manuscript-reading[open]")) return true;
      if (
        document.body.classList.contains("manuscript-reading") &&
        !document.body.classList.contains("workbench-overview") &&
        getActiveScrollDepth() > TOP_PIN_THRESHOLD
      ) {
        return true;
      }
      return false;
    }

    function applyState(nextHidden) {
      if (nextHidden && shouldHoldVisible()) nextHidden = false;
      hidden = Boolean(nextHidden);
      if (document.body) {
        document.body.classList.toggle("chrome-autohidden", hidden);
      }
      getBars().forEach(function (bar) {
        if (hidden) bar.setAttribute("data-chrome-hidden", "true");
        else bar.removeAttribute("data-chrome-hidden");
      });
    }

    function scheduleIdle() {
      clearTimeout(idleTimer);
      idleTimer = setTimeout(function () {
        if (canAutoHideByIdle()) {
          applyState(true);
        }
      }, IDLE_MS);
    }

    function show() {
      accumDelta = 0;
      applyState(false);
      scheduleIdle();
    }

    function hide() {
      if (!shouldHoldVisible()) {
        applyState(true);
      }
    }

    function markUserScrollGesture(event) {
      if (event && event.type === "wheel" && typeof event.deltaY === "number") {
        userScrollUntil = performance.now() + 450;
        if (event.deltaY < -6) {
          show();
        }
      } else {
        userScrollUntil = performance.now() + 450;
      }
    }

    function handleScroll(event) {
      var target = event ? event.target : document;
      if (!isPrimaryScrollTarget(target)) return;
      var key = target === document || target === document.documentElement || target === document.body
        ? document
        : target;
      var currentTop = getScrollTop(target);
      var prevTop = lastScrollTops.has(key) ? lastScrollTops.get(key) : currentTop;
      var delta = currentTop - prevTop;
      lastScrollTops.set(key, currentTop);

      if (Math.abs(delta) < 1) return;
      if (currentTop <= TOP_PIN_THRESHOLD) {
        show();
        return;
      }
      var isInteractiveScroll =
        performance.now() <= userScrollUntil ||
        (target && target.nodeType === 1 && target.matches(".cm-scroller, .teleprompter-scroll-pane"));
      if (!isInteractiveScroll) {
        scheduleIdle();
        return;
      }
      if ((delta > 0 && accumDelta < 0) || (delta < 0 && accumDelta > 0)) {
        accumDelta = 0;
      }
      accumDelta += delta;
      if (accumDelta >= DOWN_DELTA_THRESHOLD && currentTop > TOP_PIN_THRESHOLD) {
        hide();
      } else if (accumDelta <= UP_DELTA_THRESHOLD) {
        show();
      }
    }

    if (typeof document !== "undefined") {
      window.addEventListener("wheel", markUserScrollGesture, { passive: true });
      window.addEventListener("touchmove", markUserScrollGesture, { passive: true });
      document.addEventListener("scroll", handleScroll, { capture: true, passive: true });
      document.addEventListener("pointermove", function (event) {
        var nearTop = typeof event.clientY === "number" && event.clientY <= TOP_HOVER_ZONE;
        var inBar = event.target && event.target.closest && event.target.closest(CHROME_SELECTOR);
        if (nearTop || inBar) {
          show();
        }
      }, { passive: true });
      document.addEventListener("pointerdown", function (event) {
        if (event.target && event.target.closest && event.target.closest(CHROME_SELECTOR)) {
          show();
        } else {
          scheduleIdle();
        }
      }, { passive: true });
      document.addEventListener("focusin", function (event) {
        if (event.target && event.target.closest && event.target.closest(CHROME_SELECTOR)) {
          show();
        }
      });
      document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" || event.key === "Alt" || event.key === "F6" || (event.ctrlKey || event.metaKey)) {
          show();
        } else {
          scheduleIdle();
        }
      }, true);
      document.addEventListener("lixity:viewchange", show);
      document.addEventListener("lixity:workbench-change", show);
      scheduleIdle();
    }

    window.LixityChrome = {
      show: show,
      reveal: show,
      hide: hide,
      isHidden: function () { return hidden; },
      resetTimer: scheduleIdle,
      refresh: function () { applyState(hidden); }
    };
  })();
})();
