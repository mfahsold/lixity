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

  function show(el) {
    clearTimeout(hideTimer);
    var text = el.getAttribute("data-help") || el.getAttribute("data-tip") || el.getAttribute("title");
    if (!text || !text.trim()) return;
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
  }

  function hide() {
    clearTimeout(hideTimer);
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
    var tipW = tip.offsetWidth;
    var tipH = tip.offsetHeight;
    var left = rect.left + (rect.width - tipW) / 2;
    left = Math.max(10, Math.min(window.innerWidth - tipW - 10, left));
    var top = rect.top - tipH - 8;
    if (top < 10) {
      top = rect.bottom + 8;
    }
    top = Math.max(10, Math.min(window.innerHeight - tipH - 10, top));
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

  window.addEventListener("scroll", scheduleUpdatePos, { passive: true });
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
