// Tooltip popups for help terms and measurable values (data-help).
// Logging lives in logging.js; this module only consumes window.LixityLog.
(function () {
  var LixityLog = window.LixityLog || {
    debug: function () {}, info: function () {},
    warn: function () { if (console.warn) console.warn.apply(console, arguments); },
    error: function () { if (console.error) console.error.apply(console, arguments); },
    api: function () {}, event: function () {},
  };

  var tip = document.createElement("div");
  tip.id = "lixity-tooltip";
  tip.className = "tooltip-popup";
  tip.setAttribute("role", "tooltip");
  tip.setAttribute("aria-hidden", "true");
  var heading = document.createElement("strong"), copy = document.createElement("div");
  heading.className = "tooltip-heading";
  // The control already supplies its accessible name; announce only new help.
  heading.setAttribute("aria-hidden", "true");
  copy.className = "tooltip-copy";
  tip.append(heading, copy);
  document.body.appendChild(tip);
  document.body.classList.add("has-js-tooltips");

  var activeEl = null;
  var touchUntil = 0;
  var touchHelp = null;
  var touchFocusEl = null;
  var activatedEl = null;
  var activatedHover = false;
  var activatingAction = false;
  var dismissedHover = null;
  var pointerX = null, pointerY = null;
  var hideTimer = null;
  var showTimer = null, pendingEl = null, warmUntil = 0;
  var pointerHelp = false, pointerOffsetX = 0, pointerOffsetY = 0;
  var textObserver = new MutationObserver(function() { if (activeEl) show(activeEl, pointerHelp); });

  function cancelPending() {
    clearTimeout(showTimer);
    showTimer = null; pendingEl = null;
  }

  var HELP_TRIGGER_SELECTOR = "[data-help], [data-tip], [title], [aria-keyshortcuts]";

  function formatShortcutKey(key) {
    if (!key) return "";
    var k = key.trim().replace(/^Control\+/i, "Ctrl+");
    var lower = k.toLowerCase();
    if (lower === "escape") return "Esc";
    if (lower === "arrowleft") return "←";
    if (lower === "arrowright") return "→";
    if (lower === "arrowup") return "↑";
    if (lower === "arrowdown") return "↓";
    return k;
  }

  var SHORTCUT_SUFFIX_RE = /\s*\((Alt\+[A-Za-z0-9]|Shift\+[A-Za-z0-9]|Ctrl\+[A-Za-z0-9]|Strg\+[A-Za-z0-9]|Cmd\+[A-Za-z0-9]|Meta\+[A-Za-z0-9]|Esc|Escape|Enter|Shift\+Enter|P)\)\s*$/i;

  function visibleControlText(el) {
    if (!el || !el.matches("button, a, summary")) return "";
    var labelNode = el.querySelector(".reader-control-label, .editor-tool-label, .teleprompter-btn-label");
    if (labelNode) {
      if (labelNode.hidden || getComputedStyle(labelNode).display === "none" || getComputedStyle(labelNode).visibility === "hidden") {
        return "";
      }
      return (labelNode.textContent || "").replace(/\s+/g, " ").trim();
    }
    var parts = [];
    Array.from(el.childNodes).forEach(function(node) {
      if (node.nodeType === 3) {
        parts.push(node.textContent || "");
      } else if (node.nodeType === 1) {
        if (node.hidden || node.getAttribute("aria-hidden") === "true") return;
        var st = getComputedStyle(node);
        if (st.display === "none" || st.visibility === "hidden") return;
        parts.push(node.textContent || "");
      }
    });
    return parts.join(" ").replace(/\s+/g, " ").trim();
  }

  function helpText(el) {
    var text = el.getAttribute("data-help") || el.getAttribute("title") || el.getAttribute("data-tip");
    // Suppress the browser's separate title bubble even during dwell.
    if (text && el.hasAttribute("title")) {
      el.setAttribute("data-tip", text); el.removeAttribute("title");
    }
    if (!text && el.hasAttribute("aria-keyshortcuts")) {
      text = el.getAttribute("aria-label") ||
        (el.labels && el.labels.length ? el.labels[0].textContent :
          el.matches("button, a, summary, .help") ? el.textContent : "");
    }
    text = text ? text.trim() : "";
    if (text && el.matches("button, a, summary") && !el.hasAttribute("aria-keyshortcuts") && !SHORTCUT_SUFFIX_RE.test(text)) {
      var visibleText = visibleControlText(el);
      if (visibleText && visibleText.toLowerCase() === text.replace(/\s+/g, " ").toLowerCase()) {
        return "";
      }
    }
    return text;
  }

  function hasPersistentFocus(el) {
    // Standalone touch help focuses its trigger for assistive technology, but
    // that synthetic focus must not pin a later mouse-only explanation.
    return el && el.contains(document.activeElement) &&
      (!touchFocusEl || !el.contains(touchFocusEl));
  }

  function hover(el) {
    if (el === activeEl) {
      clearTimeout(hideTimer);
      if (!pointerHelp) { pointerAnchor(el); updatePos(el); }
      return;
    }
    // A pointer passing over another control must not replace the help that
    // remains associated with the current keyboard focus.
    if (hasPersistentFocus(activeEl)) return;
    if (el === pendingEl || el === activatedEl || el.closest(".pswp")) return;
    if (activeEl) hide();
    cancelPending();
    var text = helpText(el);
    if (!text || !text.trim()) return;
    pendingEl = el;
    // Deliberate first dwell, then quick inspection of neighboring tools.
    showTimer = setTimeout(function() {
      cancelPending();
      if (el.isConnected && el.matches(":hover")) show(el, true);
    }, Date.now() < warmUntil ? 80 : 600);
  }

  function pointerAnchor(el) {
    var rect = el.getBoundingClientRect();
    pointerHelp = true;
    pointerOffsetX = Math.max(0, Math.min(rect.width, (pointerX === null ? rect.left : pointerX) - rect.left));
    pointerOffsetY = Math.max(0, Math.min(rect.height, (pointerY === null ? rect.top : pointerY) - rect.top));
  }

  function show(el, fromPointer) {
    cancelPending();
    if (!el.isConnected || el === activatedEl || el.closest(".pswp")) return;
    clearTimeout(hideTimer);
    var text = helpText(el);
    if (!text || !text.trim()) { if (activeEl === el) hide(); return; }
    textObserver.disconnect();
    var samePointer = fromPointer && pointerHelp && activeEl === el;
    if (activeEl && activeEl !== el) hide();
    activeEl = el;
    if (fromPointer) { if (!samePointer) pointerAnchor(el); }
    else pointerHelp = false;
    // Keep help in the native dialog's top layer when its control is inside one.
    var host = el.closest("dialog[open]") || document.body;
    if (tip.parentElement !== host) host.appendChild(tip);
    var descriptions = (el.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
    if (descriptions.indexOf(tip.id) === -1) descriptions.push(tip.id);
    el.setAttribute("aria-describedby", descriptions.join(" "));
    var name = el.getAttribute("aria-label") ||
      (el.labels && el.labels.length ? el.labels[0].textContent :
        el.matches("button, a, summary, .help") ? el.textContent : "");
    name = (name || "").trim();

    var shortcut = el.getAttribute("aria-keyshortcuts") || "";
    var shortcutMatch =
      (text && text.match(SHORTCUT_SUFFIX_RE)) ||
      (name && name.match(SHORTCUT_SUFFIX_RE));
    if (shortcutMatch) {
      if (!shortcut) shortcut = shortcutMatch[1];
      if (text) text = text.replace(shortcutMatch[0], "").trim();
      if (name) name = name.replace(shortcutMatch[0], "").trim();
    }

    var hasShortcut = Boolean(shortcut && shortcut.trim());
    var showHeading = hasShortcut || (name && name !== text.trim() && name.length <= 120);
    heading.replaceChildren();
    heading.hidden = !showHeading;
    if (showHeading) {
      var displayName = (name && name.length <= 120) ? name : (text && text.length <= 60 ? text : "");
      if (displayName) {
        heading.appendChild(document.createTextNode(displayName));
      }
      if (hasShortcut) {
        var combos = shortcut.trim().split(/\s+/);
        combos.forEach(function(combo) {
          if (!combo) return;
          var key = document.createElement("kbd");
          key.textContent = formatShortcutKey(combo);
          heading.appendChild(key);
        });
      }
    }
    if (hasShortcut && name && text && text.trim() === name) {
      copy.textContent = "";
      copy.hidden = true;
    } else {
      copy.textContent = text;
      copy.hidden = !text || !text.trim();
    }
    tip.setAttribute("aria-hidden", "false");
    tip.classList.add("visible");
    warmUntil = Date.now() + 1000;
    updatePos(el);
    if (activeEl) textObserver.observe(el, {attributes: true,
      attributeFilter: ["title", "data-tip", "data-help", "aria-label", "aria-keyshortcuts"]});
  }

  function hide() {
    cancelPending();
    clearTimeout(hideTimer);
    textObserver.disconnect();
    if (activeEl) {
      warmUntil = Date.now() + 1000;
      var descriptions = (activeEl.getAttribute("aria-describedby") || "").split(/\s+/).filter(function(id) { return id && id !== tip.id; });
      if (descriptions.length) activeEl.setAttribute("aria-describedby", descriptions.join(" "));
      else activeEl.removeAttribute("aria-describedby");
    }
    activeEl = null;
    pointerHelp = false;
    tip.style.left = "";
    tip.style.top = "";
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
    var visible = {left: 10, right: innerWidth - 10, top: 10, bottom: innerHeight - 10};
    // A backdrop filter or transform makes fixed descendants relative to that
    // ancestor. Convert viewport geometry through the actual containing block.
    var space = LixityComponents.overlaySpace(tip);
    if (space.bounds) {
      visible.left = Math.max(visible.left, space.bounds.left);
      visible.right = Math.min(visible.right, space.bounds.right);
      visible.top = Math.max(visible.top, space.bounds.top);
      visible.bottom = Math.min(visible.bottom, space.bounds.bottom);
    }
    function place(left, top) {
      LixityComponents.placeOverlay(tip, left, top, space);
    }
    for (var parent = el.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
      var style = getComputedStyle(parent), box = parent.getBoundingClientRect();
      var clipX = /auto|scroll|hidden|clip/.test(style.overflowX);
      var clipY = /auto|scroll|hidden|clip/.test(style.overflowY);
      var left = box.left + parent.clientLeft, top = box.top + parent.clientTop;
      if ((clipX && (rect.right <= left || rect.left >= left + parent.clientWidth)) ||
          (clipY && (rect.bottom <= top || rect.top >= top + parent.clientHeight))) {
        hide(); return;
      }
      // The fixed popup may sit outside the reader toolbar's bounded scrollport.
      // Only its trigger must remain visible inside those compact controls.
      if (parent.matches(".manuscript-reader-controls, .workspace-shell")) continue;
      if (clipX && parent.scrollWidth > parent.clientWidth) {
        visible.left = Math.max(visible.left, left);
        visible.right = Math.min(visible.right, left + parent.clientWidth);
      }
      if (clipY && parent.scrollHeight > parent.clientHeight) {
        visible.top = Math.max(visible.top, top);
        visible.bottom = Math.min(visible.bottom, top + parent.clientHeight);
      }
    }
    var anchorTop = rect.top, anchorBottom = rect.bottom;
    if (el.matches("input, select, textarea")) {
      // Keep a field and its immediate actions available while its help owns
      // focus. A popup covering Apply would otherwise prevent leaving the field.
      var field = el.closest(".setting-field, .form-group, .form-row");
      if (field) {
        var fieldBox = field.getBoundingClientRect();
        anchorTop = fieldBox.top; anchorBottom = fieldBox.bottom;
        for (var action = field.nextElementSibling; action &&
            action.matches("button, .row, .settings-actions, .form-actions"); action = action.nextElementSibling) {
          if (!action.getClientRects().length) continue;
          var actionBox = action.getBoundingClientRect();
          anchorTop = Math.min(anchorTop, actionBox.top);
          anchorBottom = Math.max(anchorBottom, actionBox.bottom);
        }
      }
    }
    if (pointerHelp && rect.height > 60) {
      // For tall elements (paragraphs, full cards), stay beside the dwell point while clearing the line.
      anchorTop = Math.max(rect.top, rect.top + pointerOffsetY - 14);
      anchorBottom = Math.min(rect.bottom, rect.top + pointerOffsetY + 16);
    }
    var toolbarSelector = ".manuscript-reader-controls, .toolbar, .selection-toolbar, [role=toolbar]";
    var toolbar = el.closest(toolbarSelector);
    if (toolbar && !pointerHelp) {
      var bar = toolbar.getBoundingClientRect();
      anchorTop = bar.top; anchorBottom = bar.bottom;
      // Wrapped actions and their adjacent search row form one control area.
      // A popup below only its trigger would cover the next row's buttons.
      var toolbarScope = toolbar.closest(".view-pane") || toolbar.parentElement;
      Array.from(toolbarScope.querySelectorAll(toolbarSelector)).forEach(function(sibling) {
        if (!sibling.matches(toolbarSelector) || !sibling.getClientRects().length) return;
        var bounds = sibling.getBoundingClientRect();
        if (bounds.right > bar.left && bounds.left < bar.right &&
            bounds.top <= anchorBottom + 16 && bounds.bottom >= anchorTop - 16) {
          anchorTop = Math.min(anchorTop, bounds.top);
          anchorBottom = Math.max(anchorBottom, bounds.bottom);
        }
      });
      anchorTop = Math.max(anchorTop, visible.top);
      anchorBottom = Math.min(anchorBottom, visible.bottom);
    }
    // Measure without a previous placement narrowing the fixed box. Prefer the
    // space below help so it does not cover the navigation preceding a form.
    place(visible.left, visible.top);
    tip.style.maxHeight = "";
    tip.style.maxWidth = "";
    var naturalW = Math.ceil(tip.getBoundingClientRect().width);
    tip.style.maxWidth = Math.min(naturalW, Math.max(0, visible.right - visible.left)) + "px";
    var tipW = Math.ceil(tip.getBoundingClientRect().width);
    var tipH = Math.ceil(tip.getBoundingClientRect().height);
    var below = Math.max(0, visible.bottom - anchorBottom - 8);
    var above = Math.max(0, anchorTop - visible.top - 8);
    if (Math.max(below, above) < 16) { hide(); return; }
    var useBelow = below >= Math.min(tipH, 160) || below >= above;
    var available = useBelow ? below : above;
    // Long explanations scroll on their chosen side rather than being clamped
    // across the trigger (which also made touch dismissal unreachable).
    tip.style.maxHeight = available + "px";
    tipH = tip.offsetHeight;
    if (el.closest(".workspace-shell") && rect.right + tipW + 16 < innerWidth) {
      place(rect.right + 10, Math.max(10, Math.min(innerHeight - tipH - 10, rect.top + (rect.height - tipH) / 2)));
      return;
    }
    var left = rect.left + (pointerHelp ? pointerOffsetX + 12 : 0);
    left = Math.max(visible.left, Math.min(visible.right - tipW, left));
    var top = useBelow ? anchorBottom + 6 : anchorTop - tipH - 6;
    place(left, top);
  }

  document.addEventListener("mouseout", function (e) {
    if (Date.now() < touchUntil) return;
    if (dismissedHover && dismissedHover.contains(e.target) && !dismissedHover.contains(e.relatedTarget)) {
      dismissedHover = null;
    }
    var el = e.target.closest(HELP_TRIGGER_SELECTOR);
    if (el && el === pendingEl && !el.contains(e.relatedTarget)) cancelPending();
    if (el && el === activeEl && !el.contains(e.relatedTarget) && !tip.contains(e.relatedTarget)) {
      // Reflow can emit departures from inactive help. One owned timer must
      // never outlive a later explicit touch or keyboard explanation.
      clearTimeout(hideTimer);
      hideTimer = setTimeout(function() {
        if (activeEl === el && !hasPersistentFocus(el)) hide();
      }, 160);
    }
  }, { passive: true });
  tip.addEventListener("mouseenter", function() { clearTimeout(hideTimer); });
  tip.addEventListener("mouseleave", function(e) {
    if (activeEl && !activeEl.contains(e.relatedTarget) &&
        !hasPersistentFocus(activeEl)) hide();
  });

  document.addEventListener("focusin", function(e) {
    if (activatingAction && dismissAction(e.target)) return;
    var el = e.target.closest(HELP_TRIGGER_SELECTOR);
    if (Date.now() >= touchUntil) touchFocusEl = null;
    // Touch can restore button focus without requesting another explanation.
    if (el && (Date.now() >= touchUntil || e.target.matches(":focus-visible"))) show(el);
  });
  document.addEventListener("focusout", function(e) {
    if (touchFocusEl && touchFocusEl.contains(e.target)) touchFocusEl = null;
    if (activatedEl && activatedEl.contains(e.target)) activatedEl = null;
    // Hover and keyboard focus are independent owners of the same help.
    // Keep it open while a real pointer remains over the trigger or popup.
    if (activeEl && Date.now() >= touchUntil &&
        (activeEl.matches(":hover") || tip.matches(":hover"))) return;
    hide();
  });
  document.addEventListener("pointermove", function(e) {
    var moved = pointerX !== e.clientX || pointerY !== e.clientY;
    pointerX = e.clientX; pointerY = e.clientY;
    // Reflow can put new metadata under a stationary pointer. Only physical
    // movement requests hover help; focus and explicit touch keep their owners.
    if (!moved || e.pointerType === "touch" || Date.now() < touchUntil ||
        activatedEl && activatedHover && activatedEl.contains(e.target)) return;
    if (dismissedHover && !dismissedHover.contains(e.target)) dismissedHover = null;
    if (dismissedHover && dismissedHover.contains(e.target)) return;
    activatedEl = null;
    var el = e.target.closest(HELP_TRIGGER_SELECTOR);
    if (el && !el.closest(".tooltip-popup")) hover(el);
    else if (!el && !tip.contains(e.target)) cancelPending();
  }, {passive: true});

  function isActionControl(target) {
    if (!target || !target.closest) return false;
    var action = target.closest("button, a, [role=button], input[type=button], input[type=submit]");
    var trigger = target.closest(HELP_TRIGGER_SELECTOR);
    if (!action) return false;
    if (trigger && trigger.matches(".help[data-help]") && !trigger.closest("button, a")) return false;
    return true;
  }

  function dismissAction(target) {
    if (!isActionControl(target)) return false;
    var trigger = target.closest(HELP_TRIGGER_SELECTOR);
    if (!trigger) return false;
    activatedEl = trigger;
    activatedHover = trigger.matches(":hover");
    hide();
    return true;
  }

  document.addEventListener("pointerdown", function(e) {
    cancelPending();
    pointerX = e.clientX; pointerY = e.clientY;
    if (activatedEl && !activatedEl.contains(e.target)) activatedEl = null;
    dismissAction(e.target);
    if (e.pointerType === "touch") {
      touchUntil = Date.now() + 1000;
      touchFocusEl = e.target.closest(HELP_TRIGGER_SELECTOR);
    }
    var el = e.target.closest(".help[data-help]");
    if (e.pointerType === "touch" && el && !el.closest("button, a")) {
      touchHelp = el;
      var wasOpen = activeEl === el;
      e.preventDefault();
      el.focus({preventScroll: true});
      if (wasOpen) hide();
      else show(el);
    } else if (!e.target.closest(HELP_TRIGGER_SELECTOR + ", .tooltip-popup")) {
      hide();
    }
  });
  document.addEventListener("click", function(e) {
    if (touchHelp && Date.now() < touchUntil && touchHelp.contains(e.target)) {
      e.preventDefault();
      e.stopPropagation();
    }
    activatingAction = isActionControl(e.target);
    if (activatingAction) setTimeout(function() { activatingAction = false; }, 0);
    dismissAction(e.target);
    touchHelp = null;
  }, true);
  document.addEventListener("click", function() {
    activatingAction = false;
  });

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
    if (event.target !== tip && !tip.contains(event.target)) { cancelPending(); scheduleUpdatePos(); }
  }, { passive: true, capture: true });
  window.addEventListener("resize", function() { cancelPending(); scheduleUpdatePos(); }, { passive: true });
  window.addEventListener("blur", hide);

  // Handle help before the reader's capture-phase Escape shortcuts.
  // Help must not cover prose or form content while the user is entering text.
  document.addEventListener("input", function(e) {
    if (e.target.matches('textarea, input[type="search"], input[type="text"], input:not([type])') && (activeEl === e.target || pendingEl === e.target)) hide();
  });
  document.addEventListener("keydown", function (e) {
    if (touchFocusEl && touchFocusEl.contains(e.target)) touchFocusEl = null;
    if (e.key === "Enter" || e.key === " ") {
      activatingAction = isActionControl(e.target);
      if (activatingAction) setTimeout(function() { activatingAction = false; }, 0);
      dismissAction(e.target);
    }
    if (e.key === "Escape" && (activeEl || pendingEl)) {
      var visibleHelp = Boolean(activeEl);
      var helpOwnsFocus = visibleHelp && (activeEl.contains(e.target) || tip.contains(e.target) ||
        e.target === document.body || e.target === document.documentElement);
      // A dialog action advertising Escape must keep that shortcut even when
      // its own focused hint is visible (notably the native Close button).
      var escapeAction = e.target.closest('button[aria-keyshortcuts~="Escape"]');
      if (escapeAction && escapeAction.closest("dialog")) helpOwnsFocus = false;
      // Transient menus own dismissal; their focused action help closes with them.
      if (e.target.closest('[role="menu"]')) helpOwnsFocus = false;
      // A dismissed hover must not reappear on small movements within the
      // same trigger. Leaving and returning can request it again.
      if (activeEl && activeEl.matches(":hover")) dismissedHover = activeEl;
      if (helpOwnsFocus) e.preventDefault();
      // A hovered hint must not steal Escape from an unrelated focused control.
      // Focused help is the innermost layer; search still clears its query.
      if (helpOwnsFocus && e.target.id !== "text-search") e.stopImmediatePropagation();
      hide();
    } else if ((e.key === "Enter" || e.key === " ") &&
        e.target.matches(".help[data-help]") && !e.target.closest("button, a")) {
      e.preventDefault();
      if (activeEl === e.target) hide();
      else show(e.target);
    }
  }, true);
  document.addEventListener("keyup", function(e) {
    // Closing a menu can restore focus to its help-bearing opener during
    // keydown. The same Escape must not leave a new hint over that control.
    if (e.key === "Escape") hide();
  });
})();
