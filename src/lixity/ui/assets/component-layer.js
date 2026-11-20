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
  var SHARED_CHROME_SELECTOR = [
    "#manuscript-reader-controls",
    ".manuscript-reading .toolbar",
    ".manuscript-editor-toolbar",
    "#manuscript-reading .manuscript-reading-bar",
    ".teleprompter-toolbar",
    ".pane-ribbon",
    ".research-pane-navigation"
  ].join(", ");
  var SHARED_TOOLBAR_SELECTOR = [
    ".manuscript-reader-controls",
    ".toolbar",
    ".selection-toolbar",
    ".pane-ribbon",
    ".research-pane-navigation",
    "[role=toolbar]"
  ].join(", ");

  var _cachedLabelsRaw = null;
  var _cachedLabelsMap = {};
  var jumpBarParts = new WeakMap();
  function readUiLabels() {
    var raw = (typeof document !== "undefined" && document.body && document.body.dataset)
      ? (document.body.dataset.uiLabels || "")
      : "";
    if (raw !== _cachedLabelsRaw) {
      _cachedLabelsRaw = raw;
      try { _cachedLabelsMap = raw ? JSON.parse(raw) : {}; } catch (_) { _cachedLabelsMap = {}; }
    }
    return _cachedLabelsMap;
  }
  function _uiLabel(key) {
    var map = readUiLabels();
    return Object.prototype.hasOwnProperty.call(map, key) && map[key] ? map[key] : key;
  }
  function _uiFormat(key, values) {
    var template = typeof window.uiLabel === "function" ? window.uiLabel(key) : _uiLabel(key);
    return String(template).replace(/\{([a-z_]+)\}/g, function (match, name) {
      return values && Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match;
    });
  }
  function _uiCountFormat(key, count, values) {
    var map = readUiLabels();
    var singular = key + "_one";
    var chosen = count === 1 && Object.prototype.hasOwnProperty.call(map, singular) ? singular : key;
    var payload = Object.assign({}, values || {});
    if (!Object.prototype.hasOwnProperty.call(payload, "count")) payload.count = count;
    return _uiFormat(chosen, payload);
  }
  window.LixityLabels = {
    get: _uiLabel,
    format: _uiFormat,
    countFormat: _uiCountFormat,
    all: readUiLabels
  };
  if (typeof window.uiLabel !== "function") window.uiLabel = _uiLabel;
  if (typeof window.uiFormat !== "function") window.uiFormat = _uiFormat;
  if (typeof window.uiCountFormat !== "function") window.uiCountFormat = _uiCountFormat;

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  window.LixityComponents = {
    CHROME_SELECTOR: SHARED_CHROME_SELECTOR,
    TOOLBAR_SELECTOR: SHARED_TOOLBAR_SELECTOR,
    escapeHtml: escapeHtml,
    escapeAttr: escapeHtml,
    uiLabel: _uiLabel,
    uiFormat: _uiFormat,
    uiCountFormat: _uiCountFormat,
    changeSelectOption: function (select, value) {
      if (!select || select.disabled || !Array.from(select.options).some(function(option) {
        return option.value === value && !option.disabled && !option.parentElement.disabled;
      })) return false;
      select.value = value;
      select.dispatchEvent(new Event("change", {bubbles:true}));
      return true;
    },
    scopedLabel: function (prefix, aliases) {
      return function (key) {
        var mapped = aliases && Object.prototype.hasOwnProperty.call(aliases, key) ? aliases[key] : null;
        var resolvedKey = mapped || (prefix ? prefix + key : key);
        return typeof window.uiLabel === "function" ? window.uiLabel(resolvedKey) : _uiLabel(resolvedKey);
      };
    },
    setStatus: function (elOrId, message, state, options) {
      var el = typeof elOrId === "string" ? document.getElementById(elOrId) : elOrId;
      if (!el) return null;
      var opts = options || {};
      var baseClass = opts.baseClass || "ctl-status";
      var text = message == null ? "" : String(message);
      if (state === "loading") {
        el.className = baseClass + " loading";
        el.textContent = text;
      } else if (!text && !state) {
        el.className = baseClass;
        el.textContent = "";
      } else {
        var cls = state === true ? "ok" : state === false ? "err" : (state || "");
        el.className = baseClass + (cls ? " " + cls : "");
        var prefix = opts.prefix && cls === "ok" ? "✓ " : (opts.prefix && cls === "err" ? "✗ " : "");
        el.textContent = text ? (prefix + text) : "";
      }
      return el;
    },
    downloadBlob: function (blob, filename, revokeMs) {
      var url = URL.createObjectURL(blob);
      var link = document.createElement("a");
      link.href = url;
      if (filename) link.download = filename;
      link.click();
      setTimeout(function () { URL.revokeObjectURL(url); }, typeof revokeMs === "number" ? revokeMs : 1500);
      return url;
    },
    jsonApi: async function (url, options, responseType) {
      var t0 = performance.now();
      try {
        var response = await fetch(url, options);
        var data;
        if (response.ok && responseType === "markdown") {
          if (!/^text\/(markdown|plain)\b/i.test(response.headers.get("Content-Type") || "")) {
            throw new Error(window.uiLabel("research_matrix_failed"));
          }
          data = { ok: true, text: await response.text() };
        } else {
          data = await response.json();
        }
        if (!data || typeof data !== "object" || Array.isArray(data)) data = { ok: false };
        if (!response.ok) data.ok = false;
        data.http_status = response.status;
        if (window.LixityLog && typeof window.LixityLog.api === "function") {
          window.LixityLog.api((options && options.method) || "GET", url, performance.now() - t0, response.status);
        }
        return data;
      } catch (error) {
        return { ok: false, message: String(error), http_status: 0 };
      }
    },
    postJson: function (url, payload, options) {
      var opts = Object.assign({ method: "POST" }, options || {});
      opts.headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
      opts.body = JSON.stringify(payload == null ? {} : payload);
      return this.jsonApi(url, opts);
    },
    el: function (tag, props) {
      var node = document.createElement(tag);
      if (typeof props === "string") {
        if (props) node.className = props;
      } else if (props && typeof props === "object") {
        if (props.className) node.className = props.className;
        if (props.id) node.id = props.id;
        if (props.type) node.type = props.type;
        if (props.text != null) node.textContent = String(props.text);
        if (props.title != null) node.title = String(props.title);
        if (props.value != null) node.value = String(props.value);
        if (props.hidden !== undefined) node.hidden = Boolean(props.hidden);
        if (props.disabled !== undefined) node.disabled = Boolean(props.disabled);
        if (props.dataset) {
          Object.keys(props.dataset).forEach(function (k) {
            if (props.dataset[k] !== undefined && props.dataset[k] !== null) {
              node.dataset[k] = String(props.dataset[k]);
            }
          });
        }
        if (props.attrs) {
          Object.keys(props.attrs).forEach(function (k) {
            if (props.attrs[k] !== undefined && props.attrs[k] !== null) {
              node.setAttribute(k, String(props.attrs[k]));
            }
          });
        }
        if (props.on) {
          Object.keys(props.on).forEach(function (evt) {
            if (typeof props.on[evt] === "function") node.addEventListener(evt, props.on[evt]);
          });
        }
      }
      for (var i = 2; i < arguments.length; i++) {
        var child = arguments[i];
        if (child === null || child === undefined || child === false) continue;
        if (Array.isArray(child)) {
          child.forEach(function (item) {
            if (item !== null && item !== undefined && item !== false) {
              node.appendChild(typeof item === "string" ? document.createTextNode(item) : item);
            }
          });
        } else {
          node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
        }
      }
      return node;
    },
    cpOffsets: function (text) {
      var offsets = [0], offset = 0;
      for (var ch of String(text || "")) { offset += ch.length; offsets.push(offset); }
      return offsets;
    },
    utf16ToCp: function (text, utf16Pos) {
      var str = String(text || ""), cp = 0, i = 0;
      while (i < utf16Pos && i < str.length) {
        var code = str.codePointAt(i);
        i += code > 0xffff ? 2 : 1;
        cp += 1;
      }
      return cp;
    },
    literalWhitespaceRegex: function (text, flags) {
      var trimmed = String(text == null ? "" : text).trim();
      if (!trimmed) return null;
      var parts = trimmed.split(/\s+/).map(function (part) {
        return part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      });
      return new RegExp(parts.join("\\s+"), flags || "i");
    },
    scrollIntoViewSafe: function (target, options) {
      if (!target || typeof target.scrollIntoView !== "function") return;
      var opts = Object.assign({ block: "start", inline: "nearest" }, options || {});
      var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reduced && (!opts.behavior || opts.behavior === "smooth")) opts.behavior = "auto";
      target.scrollIntoView(opts);
    },
    ensureJumpBar: function (id, className, anchorEl) {
      var bar = document.getElementById(id);
      if (bar) return bar;
      bar = this.el("div", {
        id: id,
        className: "passage-jump-bar " + className,
        hidden: true,
        attrs: { role: "region" }
      });
      var toolbar = anchorEl && anchorEl.closest("#analysis-outline-document")?.querySelector(".toolbar");
      if (toolbar) toolbar.appendChild(bar);
      else if (anchorEl && anchorEl.before) anchorEl.before(bar);
      return bar;
    },
    renderJumpBar: function (bar, config) {
      if (!bar) return;
      if (!config || !config.visible) {
        bar.hidden = true;
        return;
      }
      var el = this.el.bind(this);
      var parts = jumpBarParts.get(bar);
      if (!parts) {
        var info = el("span", { attrs: { role: "status" } });
        var previous = el("button", { type: "button", className: "ctl ctl-sm", text: "←" });
        var next = el("button", { type: "button", className: "ctl ctl-sm", text: "→" });
        var close = el("button", { type: "button", className: "ctl ctl-sm" });
        parts = { info: info, previous: previous, next: next, close: close };
        jumpBarParts.set(bar, parts);
        bar.replaceChildren(info, el("div", "passage-jump-actions", previous, next, close));
      }
      parts.info.className = "passage-jump-label" + (config.labelClass ? " " + config.labelClass : "");
      if (parts.info.textContent !== config.label) parts.info.textContent = config.label || "";
      parts.previous.setAttribute("aria-label", config.prevLabel || _uiLabel("evidence_previous"));
      parts.next.setAttribute("aria-label", config.nextLabel || _uiLabel("evidence_next"));
      parts.close.setAttribute("aria-label", config.closeLabel || config.closeText || _uiLabel("evidence_close"));
      parts.close.textContent = config.closeText || "✕";
      parts.previous.onclick = config.onPrev || null;
      parts.next.onclick = config.onNext || null;
      parts.close.onclick = config.onClose || null;
      bar.setAttribute("aria-label", config.regionLabel || config.label || _uiLabel("evidence_inspect"));
      bar.hidden = false;
    },
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
      else {
        input.value = spec.value == null ? "" : spec.value;
        var control = input;
        if (type === "select" && window.LixityIcons) {
          control = this.el("span", {className: "ctl-select"});
          control.append(input, window.LixityIcons.create("chevron-down"));
        }
        wrapper.append(label, control);
      }
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
    placeClampedOverlay: function (node, left, top, options) {
      var opts = options || {};
      var gutter = typeof opts.gutter === "number" ? opts.gutter : 8;
      var bounds = opts.bounds || node.getBoundingClientRect();
      var space = opts.space || this.overlaySpace(node);
      var maxLeft = Math.max(gutter, window.innerWidth - bounds.width - gutter);
      var maxTop = Math.max(gutter, window.innerHeight - bounds.height - gutter);
      this.placeOverlay(
        node,
        Math.max(gutter, Math.min(maxLeft, left)),
        Math.max(gutter, Math.min(maxTop, top)),
        space
      );
    },
    // Keep floating overlays hidden with transitions suppressed while computing
    // viewport coordinates so the first painted frame never flashes at (0, 0).
    measureOverlay: function (node, fn) {
      var prevVisibility = node.style.visibility;
      var prevTransition = node.style.transition;
      node.style.transition = "none";
      node.style.visibility = "hidden";
      try {
        return fn();
      } finally {
        node.style.visibility = prevVisibility;
        void node.offsetWidth;
        node.style.transition = prevTransition;
      }
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
    renderTagSuggestions: function (hostOrId, entries, headingLabel) {
      var host = typeof hostOrId === "string" ? document.getElementById(hostOrId) : hostOrId;
      if (!host) return;
      var inputId = host.getAttribute("data-tag-suggestions-for") || "";
      var normalized = (entries || []).map(function (entry) {
        if (typeof entry === "string") return { value: entry.trim(), label: entry.trim() };
        return {
          value: String((entry && entry.value) || "").trim(),
          label: String((entry && (entry.label || entry.value)) || "").trim()
        };
      }).filter(function (item) { return Boolean(item.value); });
      var seen = Object.create(null);
      var unique = [];
      normalized.forEach(function (item) {
        if (!seen[item.value]) { seen[item.value] = true; unique.push(item); }
      });
      if (!unique.length) {
        host.hidden = true;
        host.replaceChildren();
        return;
      }
      var frag = document.createDocumentFragment();
      if (headingLabel) {
        var note = document.createElement("span");
        note.className = "ctl-note";
        note.textContent = headingLabel;
        frag.appendChild(note);
      }
      unique.forEach(function (item) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "ctl ctl-sm";
        btn.setAttribute("data-tag-pick", item.value);
        if (inputId) btn.setAttribute("data-tag-target", inputId);
        btn.setAttribute("aria-pressed", "false");
        btn.textContent = item.label;
        frag.appendChild(btn);
      });
      host.replaceChildren(frag);
      host.hidden = false;
      var targetInput = inputId ? document.getElementById(inputId) : null;
      if (targetInput) this.syncTagChips(targetInput);
    },
    syncTagChips: function (inputEl) {
      if (!inputEl || !inputEl.id) return;
      var values = String(inputEl.value || "").split(",").map(function (s) { return s.trim(); }).filter(Boolean);
      document.querySelectorAll('[data-tag-suggestions-for="' + inputEl.id + '"] [data-tag-pick]').forEach(function (btn) {
        var active = values.indexOf(btn.getAttribute("data-tag-pick")) !== -1;
        btn.classList.toggle("active", active);
        btn.setAttribute("aria-pressed", String(active));
      });
    },
    syncEmptySelect: function (selectOrId) {
      var select = typeof selectOrId === "string" ? document.getElementById(selectOrId) : selectOrId;
      if (!select) return;
      var hintId = select.getAttribute("data-empty-hint");
      var hint = hintId ? document.getElementById(hintId) : null;
      if (!hint) return;
      var empty = select.options.length === 0;
      hint.hidden = !empty;
      select.hidden = empty;
    },
  };

  (function initLixityFormHelpers() {
    document.addEventListener("click", function (event) {
      var tplBtn = event.target.closest("[data-template-target]");
      if (tplBtn) {
        var target = document.getElementById(tplBtn.getAttribute("data-template-target") || "");
        var body = tplBtn.getAttribute("data-template-body") || "";
        if (target && body) {
          var existing = target.value.trim();
          target.value = existing ? (existing + "\n\n" + body) : body;
          target.focus();
        }
        var tagTargetId = tplBtn.getAttribute("data-template-tag-target");
        var tagVal = tplBtn.getAttribute("data-template-tag");
        if (tagTargetId && tagVal) {
          var tagInput = document.getElementById(tagTargetId);
          if (tagInput) {
            var parts = tagInput.value.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
            if (parts.indexOf(tagVal) === -1) parts.push(tagVal);
            tagInput.value = parts.join(", ");
            window.LixityComponents.syncTagChips(tagInput);
          }
        }
        return;
      }

      var pickBtn = event.target.closest("[data-tag-pick]");
      if (pickBtn) {
        var picked = pickBtn.getAttribute("data-tag-pick");
        var input = document.getElementById(pickBtn.getAttribute("data-tag-target") || "");
        if (picked && input) {
          var current = input.value.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
          var idx = current.indexOf(picked);
          if (idx === -1) current.push(picked);
          else current.splice(idx, 1);
          input.value = current.join(", ");
          window.LixityComponents.syncTagChips(input);
          input.focus();
        }
      }
    });

    document.addEventListener("input", function (event) {
      var input = event.target.closest('[data-tag-input="true"]');
      if (input) window.LixityComponents.syncTagChips(input);
    });
  })();

  // Central distraction-free chrome controller (Headroom scroll-direction + idle timeout).
  // Anchors auto-hide behavior across reader, editor, saved-revision reader, and teleprompter
  // toolbars without shifting document layout or breaking keyboard focus (:focus-within).
  (function initLixityChrome() {
    var CHROME_SELECTOR = SHARED_CHROME_SELECTOR;
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
      if (document.querySelector("#reader-settings[open], #reader-analysis-guide[open], #manuscript-versions[open]")) return true;
      if (Array.from(document.querySelectorAll(".passage-jump-bar:not([hidden])")).some(function (bar) {
        return bar.getClientRects().length > 0;
      })) return true;
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
      var prevTop = lastScrollTops.has(key) ? lastScrollTops.get(key) : (key === document ? 0 : currentTop);
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
        } else if (
          hidden &&
          event.target && event.target.closest &&
          event.target.closest("#chapters, #manuscript-reading")
        ) {
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

  // Shared Project/Pane jump ribbon handler: keeps hidden targets synchronized,
  // collapses labels to icon-only cleanly when text overflows horizontally,
  // scales scroll-margin-top with ribbon geometry, opens collapsed <details>,
  // and moves keyboard focus cleanly without shifting prose.
  (function initPaneRibbons() {
    if (typeof document === "undefined") return;
    var observed = new WeakSet();

    function syncRibbonDensity(targetRibbon) {
      var list = targetRibbon ? [targetRibbon] : Array.from(document.querySelectorAll(".pane-ribbon, .research-pane-navigation"));
      var maxHeight = 0;
      list.forEach(function (ribbon) {
        if (!ribbon || !ribbon.isConnected) return;
        if (typeof ResizeObserver === "function" && !observed.has(ribbon)) {
          observed.add(ribbon);
          new ResizeObserver(function () { syncRibbonDensity(ribbon); }).observe(ribbon);
        }
        if (ribbon.offsetParent === null) return;
        delete ribbon.dataset.ribbonCompact;
        delete ribbon.dataset.ribbonWrap;
        if (ribbon.scrollWidth > ribbon.clientWidth + 1) {
          ribbon.dataset.ribbonCompact = "true";
          if (ribbon.scrollWidth > ribbon.clientWidth + 1) {
            ribbon.dataset.ribbonWrap = "true";
          }
        }
        maxHeight = Math.max(maxHeight, ribbon.getBoundingClientRect().height || 0);
      });
      if (maxHeight > 0 && document.documentElement) {
        document.documentElement.style.setProperty("--pane-ribbon-height", Math.ceil(maxHeight) + "px");
      }
    }

    function syncRibbons() {
      document.querySelectorAll(".pane-ribbon").forEach(function (ribbon) {
        ribbon.querySelectorAll("[data-ribbon-target]").forEach(function (btn) {
          var sel = btn.getAttribute("data-ribbon-target");
          if (!sel || sel === "#controls") {
            btn.hidden = false;
            return;
          }
          var target = document.querySelector(sel);
          if (target) target.setAttribute("data-ribbon-section", "");
          btn.hidden = !target || target.hidden;
        });
      });
      syncRibbonDensity();
    }

    window.LixityRibbonDensity = { sync: syncRibbonDensity };

    document.addEventListener("click", function (event) {
      var btn = event.target && event.target.closest ? event.target.closest(".pane-ribbon [data-ribbon-target]") : null;
      if (!btn) return;
      var ribbon = btn.closest(".pane-ribbon");
      var sel = btn.getAttribute("data-ribbon-target");
      var target = sel ? document.querySelector(sel) : null;
      if (!target) return;
      if (window.LixityChrome && typeof window.LixityChrome.show === "function") {
        window.LixityChrome.show();
      }
      if (target.tagName === "DETAILS") target.open = true;
      if (ribbon) {
        ribbon.querySelectorAll("[aria-current='location']").forEach(function (b) {
          b.removeAttribute("aria-current");
        });
        if (sel !== "#controls") btn.setAttribute("aria-current", "location");
        var ribbonHeight = ribbon.getBoundingClientRect().height || 0;
        if (ribbonHeight > 0 && document.documentElement) {
          document.documentElement.style.setProperty("--pane-ribbon-height", Math.ceil(ribbonHeight) + "px");
        }
      }
      window.LixityComponents.scrollIntoViewSafe(target, { behavior: "smooth", block: "start", inline: "nearest" });
      var focusTarget = sel === "#controls"
        ? target.querySelector(":scope > h2, :scope > summary") || target
        : target.querySelector(":scope > summary, :scope > legend, :scope > h2, :scope > h3, :scope > h4, [tabindex='-1']") || target;
      if (focusTarget) {
        if (!focusTarget.hasAttribute("tabindex") && !focusTarget.matches("a, button, input, select, textarea, summary")) {
          focusTarget.setAttribute("tabindex", "-1");
        }
        focusTarget.focus({ preventScroll: true });
      }
    });

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", syncRibbons);
    } else {
      syncRibbons();
    }
    window.addEventListener("resize", syncRibbons);
    document.addEventListener("lixity:viewchange", function () {
      window.requestAnimationFrame(syncRibbons);
    });
    document.addEventListener("lixity:workbench-change", function () {
      window.requestAnimationFrame(syncRibbons);
    });
  })();
})();
