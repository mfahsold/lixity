// Tooltip popups for help terms and measurable values (data-help).
(function () {
  var isDebug = (function() {
    try {
      var saved = localStorage.getItem("lixity_debug");
      if (saved === "1") return true;
      if (saved === "0") return false;
    } catch (_) {}
    if (window.LIXITY_DEBUG) return true;
    var meta = document.querySelector('meta[name="lixity-debug"]');
    return !!(meta && meta.content === "true");
  })();

  var LixityLog = {
    isDebug: function() { return isDebug; },
    setDebug: function(enable) {
      isDebug = !!enable;
      try {
        localStorage.setItem("lixity_debug", isDebug ? "1" : "0");
      } catch (_) {}
      console.info("[Lixity] Debug logging " + (isDebug ? "enabled" : "disabled"));
    },
    debug: function() {
      if (isDebug && console.debug) {
        console.debug.apply(console, ["[Lixity:debug]"].concat(Array.prototype.slice.call(arguments)));
      }
    },
    info: function() {
      if (isDebug && console.info) {
        console.info.apply(console, ["[Lixity:info]"].concat(Array.prototype.slice.call(arguments)));
      }
    },
    warn: function() {
      if (console.warn) {
        console.warn.apply(console, ["[Lixity:warn]"].concat(Array.prototype.slice.call(arguments)));
      }
    },
    error: function() {
      if (console.error) {
        console.error.apply(console, ["[Lixity:error]"].concat(Array.prototype.slice.call(arguments)));
      }
    },
    api: function(method, url, durationMs, status) {
      if (!isDebug) return;
      var label = "[Lixity:api] " + method + " " + url + " -> " + status + " (" + durationMs.toFixed(1) + "ms)";
      if (status >= 400) {
        console.error(label);
      } else {
        console.debug(label);
      }
    }
  };

  window.LixityLog = LixityLog;
  window.setLixityDebug = LixityLog.setDebug;

  if (isDebug) {
    console.info("[Lixity] Debug mode active. API logs and runtime diagnostics are enabled. Use setLixityDebug(false) to disable.");
  }

  var tip = document.createElement("div");
  tip.id = "lixity-tooltip";
  tip.className = "tooltip-popup";
  tip.setAttribute("role", "tooltip");
  tip.setAttribute("aria-hidden", "true");
  document.body.appendChild(tip);
  document.body.classList.add("has-js-tooltips");

  var activeEl = null;
  var touchUntil = 0;
  var touchHelp = null;
  var hideTimer = null;
  var textObserver = new MutationObserver(function() { if (activeEl) show(activeEl); });

  function show(el) {
    clearTimeout(hideTimer);
    var text = el.getAttribute("data-help") || el.getAttribute("title") || el.getAttribute("data-tip");
    if (!text || !text.trim()) { if (activeEl === el) hide(); return; }
    textObserver.disconnect();
    if (el.hasAttribute("title")) {
      el.setAttribute("data-tip", text);
      el.removeAttribute("title");
    }
    if (activeEl && activeEl !== el) hide();
    activeEl = el;
    // Keep help in the native dialog's top layer when its control is inside one.
    var host = el.closest("dialog[open]") || document.body;
    if (tip.parentElement !== host) host.appendChild(tip);
    var descriptions = (el.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
    if (descriptions.indexOf(tip.id) === -1) descriptions.push(tip.id);
    el.setAttribute("aria-describedby", descriptions.join(" "));
    tip.textContent = text;
    tip.setAttribute("aria-hidden", "false");
    tip.classList.add("visible");
    updatePos(el);
    if (activeEl) textObserver.observe(el, {attributes: true, attributeFilter: ["title", "data-tip", "data-help"]});
  }

  function hide() {
    clearTimeout(hideTimer);
    textObserver.disconnect();
    if (activeEl) {
      var descriptions = (activeEl.getAttribute("aria-describedby") || "").split(/\s+/).filter(function(id) { return id && id !== tip.id; });
      if (descriptions.length) activeEl.setAttribute("aria-describedby", descriptions.join(" "));
      else activeEl.removeAttribute("aria-describedby");
    }
    activeEl = null;
    tip.setAttribute("aria-hidden", "true");
    tip.classList.remove("visible");
  }

  function updatePos(el) {
    if (!el || !tip.classList.contains("visible")) return;
    var rect = el.getBoundingClientRect();
    if (!el.isConnected || !el.getClientRects().length ||
        getComputedStyle(el).visibility !== "visible" ||
        rect.bottom <= 0 || rect.top >= window.innerHeight ||
        rect.right <= 0 || rect.left >= window.innerWidth) {
      hide();
      return;
    }
    // A trigger can still be inside the viewport after its nested scrollport
    // clips it. Keep help attached only while some of the trigger is visible.
    for (var parent = el.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
      var style = getComputedStyle(parent), box = parent.getBoundingClientRect();
      var clipX = /auto|scroll|hidden|clip/.test(style.overflowX);
      var clipY = /auto|scroll|hidden|clip/.test(style.overflowY);
      var left = box.left + parent.clientLeft, top = box.top + parent.clientTop;
      if ((clipX && (rect.right <= left || rect.left >= left + parent.clientWidth)) ||
          (clipY && (rect.bottom <= top || rect.top >= top + parent.clientHeight))) {
        hide(); return;
      }
    }
    // Measure without a previous placement narrowing the fixed box. Prefer the
    // space below help so it does not cover the navigation preceding a form.
    tip.style.left = "10px";
    tip.style.maxHeight = "";
    var tipW = tip.offsetWidth;
    var tipH = tip.offsetHeight;
    var below = Math.max(0, window.innerHeight - rect.bottom - 18);
    var above = Math.max(0, rect.top - 18);
    var useBelow = below >= Math.min(tipH, 160) || below >= above;
    var available = useBelow ? below : above;
    // Long explanations scroll on their chosen side rather than being clamped
    // across the trigger (which also made touch dismissal unreachable).
    tip.style.maxHeight = available + "px";
    tipH = tip.offsetHeight;
    var left = rect.left + (rect.width - tipW) / 2;
    left = Math.max(10, Math.min(window.innerWidth - tipW - 10, left));
    var top = useBelow ? rect.bottom + 8 : rect.top - tipH - 8;
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }

  document.addEventListener("mouseover", function (e) {
    if (Date.now() < touchUntil) return;
    var el = e.target.closest("[data-help], [data-tip], [title]");
    if (el && !el.closest(".tooltip-popup")) show(el);
  }, { passive: true });

  document.addEventListener("mouseout", function (e) {
    if (Date.now() < touchUntil) return;
    var el = e.target.closest("[data-help], [data-tip]");
    if (el && !el.contains(e.relatedTarget) && !tip.contains(e.relatedTarget)) {
      hideTimer = setTimeout(hide, 160);
    }
  }, { passive: true });
  tip.addEventListener("mouseenter", function() { clearTimeout(hideTimer); });
  tip.addEventListener("mouseleave", function(e) {
    if (!activeEl || !activeEl.contains(e.relatedTarget)) hide();
  });

  document.addEventListener("focusin", function(e) {
    var el = e.target.closest("[data-help], [data-tip], [title]");
    if (el) show(el);
  });
  document.addEventListener("focusout", hide);

  document.addEventListener("pointerdown", function(e) {
    if (e.pointerType === "touch") touchUntil = Date.now() + 1000;
    var el = e.target.closest(".help[data-help]");
    if (e.pointerType === "touch" && el && !el.closest("button, a")) {
      touchHelp = el;
      var wasOpen = activeEl === el;
      e.preventDefault();
      el.focus({preventScroll: true});
      if (wasOpen) hide();
      else show(el);
    } else if (!e.target.closest("[data-help], [data-tip], [title], .tooltip-popup")) {
      hide();
    }
  });
  document.addEventListener("click", function(e) {
    if (touchHelp && Date.now() < touchUntil && touchHelp.contains(e.target)) {
      e.preventDefault();
      e.stopPropagation();
    }
    touchHelp = null;
  }, true);

  document.addEventListener("close", function(e) {
    if (activeEl && e.target.contains(activeEl)) hide();
  }, true);
  document.addEventListener("lixity:viewchange", hide);
  document.addEventListener("lixity:workbench-change", hide);

  var posTicking = false;
  function scheduleUpdatePos() {
    if (!posTicking && activeEl) {
      posTicking = true;
      requestAnimationFrame(function () {
        posTicking = false;
        if (activeEl) updatePos(activeEl);
      });
    }
  }

  document.addEventListener("scroll", function(event) {
    if (event.target !== tip && !tip.contains(event.target)) scheduleUpdatePos();
  }, { passive: true, capture: true });
  window.addEventListener("resize", scheduleUpdatePos, { passive: true });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && activeEl) {
      e.preventDefault();
      hide();
    } else if ((e.key === "Enter" || e.key === " ") &&
        e.target.matches(".help[data-help]") && !e.target.closest("button, a")) {
      e.preventDefault();
      if (activeEl === e.target) hide();
      else show(e.target);
    }
  });
})();
