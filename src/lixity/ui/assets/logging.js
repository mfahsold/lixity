// Central structured logging for the native workspace (SoC: logging lives here,
// tooltips and features only call window.LixityLog).
(function () {
  'use strict';
  var KEY = 'lixity_debug';
  var isDebug = (function () {
    try {
      var saved = null;
      try { saved = localStorage.getItem(KEY); } catch (_) {}
      if (saved === '1') return true;
      if (saved === '0') return false;
    } catch (_) {}
    if (window.LIXITY_DEBUG) return true;
    var meta = document.querySelector('meta[name="lixity-debug"]');
    return !!(meta && meta.content === 'true');
  })();

  var BADGE_BRAND = 'background: #2563eb; color: #ffffff; font-weight: 700; font-size: 10px; padding: 2px 5px; border-radius: 3px 0 0 3px;';
  var BADGE_CAT = 'background: #334155; color: #f1f5f9; font-weight: 600; font-size: 10px; padding: 2px 5px; border-radius: 0 3px 3px 0;';
  var BADGE_PERF = 'background: #059669; color: #ffffff; font-weight: 600; font-size: 10px; padding: 2px 5px; border-radius: 0 3px 3px 0;';
  var BADGE_WARN = 'background: #d97706; color: #ffffff; font-weight: 600; font-size: 10px; padding: 2px 5px; border-radius: 0 3px 3px 0;';
  var BADGE_ERR = 'background: #dc2626; color: #ffffff; font-weight: 700; font-size: 10px; padding: 2px 5px; border-radius: 0 3px 3px 0;';

  function prefix(kind) { return '[Lixity:' + kind + ']'; }
  function withId() {
    try {
      var id = sessionStorage.getItem('lixity_diagnostic_id');
      if (!id) {
        var bytes = new Uint8Array(8);
        (window.crypto || {}).getRandomValues ? crypto.getRandomValues(bytes) : bytes.fill(Date.now() % 256);
        id = Array.from(bytes).map(function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
        try { sessionStorage.setItem('lixity_diagnostic_id', id); } catch (_) {}
      }
      return id;
    } catch (_) { return null; }
  }

  function formatParams(kind, args, defaultBadge) {
    var first = args[0];
    var cat = kind;
    var rest = [].slice.call(args, 1);
    var msg = first;
    if (typeof first === 'string') {
      var colon = first.indexOf(':');
      if (colon > 0 && colon < 24) {
        cat = first.slice(0, colon);
        msg = first.slice(colon + 1).trim();
      }
    }
    return {
      format: '%c Lixity %c ' + cat + ' %c ' + (typeof msg === 'string' ? msg : ''),
      styles: [BADGE_BRAND, defaultBadge, 'color: inherit;'],
      extra: (typeof msg === 'string' ? rest : [msg].concat(rest))
    };
  }

  var LixityLog = {
    isDebug: function () { return isDebug; },
    setDebug: function (enable) {
      isDebug = !!enable;
      try { localStorage.setItem(KEY, isDebug ? '1' : '0'); } catch (_) {}
      try {
        console.info(
          '%c Lixity %c Debug Mode ' + (isDebug ? 'ENABLED' : 'DISABLED'),
          BADGE_BRAND,
          isDebug ? 'background: #059669; color: #fff; padding: 2px 5px; border-radius: 0 3px 3px 0;' : BADGE_CAT
        );
      } catch (_) {}
    },
    debug: function () {
      if (!isDebug || !console.debug) return;
      var p = formatParams('debug', arguments, BADGE_CAT);
      console.debug.apply(console, [p.format].concat(p.styles, p.extra));
    },
    info: function () {
      if (!isDebug || !console.info) return;
      var p = formatParams('info', arguments, BADGE_CAT);
      console.info.apply(console, [p.format].concat(p.styles, p.extra));
    },
    perf: function (operation, durationMs, details) {
      if (!console.info) return;
      var label = operation + ' (' + Number(durationMs).toFixed(1) + 'ms)';
      if (details !== undefined) {
        console.info('%c Lixity %c PERF %c ' + label, BADGE_BRAND, BADGE_PERF, 'color: inherit;', details);
      } else {
        console.info('%c Lixity %c PERF %c ' + label, BADGE_BRAND, BADGE_PERF, 'color: inherit;');
      }
    },
    warn: function () {
      if (!console.warn) return;
      var p = formatParams('warn', arguments, BADGE_WARN);
      console.warn.apply(console, [p.format].concat(p.styles, p.extra));
    },
    error: function () {
      if (!console.error) return;
      var p = formatParams('error', arguments, BADGE_ERR);
      console.error.apply(console, [p.format].concat(p.styles, p.extra));
    },
    event: function (name, fields) {
      if (!isDebug) return;
      var parts = ['event=' + name];
      var id = withId();
      if (id) parts.push('id=' + id);
      Object.keys(fields || {}).sort().forEach(function (k) {
        var v = fields[k];
        if (v === null || v === undefined) return;
        parts.push(k + '=' + (typeof v === 'string' && /[\s="]/.test(v) ? '"' + v.replace(/"/g, '\\"') + '"' : String(v)));
      });
      if (console.debug) console.debug('%c Lixity %c event ', BADGE_BRAND, BADGE_CAT, parts.join(' '));
    },
    api: function (method, url, durationMs, status) {
      if (!isDebug) return;
      var clean = String(url).split('?')[0];
      var label = method + ' ' + clean + ' -> ' + status + ' (' + Number(durationMs).toFixed(1) + 'ms)';
      var badge = status >= 400 ? BADGE_ERR : BADGE_PERF;
      if (status >= 400) {
        if (console.error) console.error('%c Lixity %c API ', BADGE_BRAND, badge, label);
      } else if (console.debug) {
        console.debug('%c Lixity %c API ', BADGE_BRAND, badge, label);
      }
    },
  };

  if (!window.LixityLog) {
    window.LixityLog = LixityLog;
    window.setLixityDebug = LixityLog.setDebug;
    if (console.info) {
      console.info(
        '%c Lixity %c Manuscript Engine ready %c [Ctrl+F] Search · [P] Audio/Teleprompter · [?] Guide',
        BADGE_BRAND,
        'background: #1e293b; color: #cbd5e1; font-size: 10px; padding: 2px 6px;',
        'background: transparent; color: var(--muted, #64748b); font-size: 10px; padding: 2px 4px;'
      );
      if (isDebug) {
        console.info('[Lixity] Debug mode active. Use setLixityDebug(false) to disable.');
      }
    }
  } else {
    // Older bundle order: keep the single instance, add the structured event API.
    if (!window.LixityLog.event) window.LixityLog.event = LixityLog.event;
    if (!window.LixityLog.api) window.LixityLog.api = LixityLog.api;
    if (!window.LixityLog.perf) window.LixityLog.perf = LixityLog.perf;
  }

  function redact(value) {
    if (typeof value !== 'string') return 'non-string';
    return value.length > 120 ? value.slice(0, 120) + '…' : value;
  }
  window.addEventListener('error', function (e) {
    if (!e || !e.message) return;
    // Never include manuscript bytes: log the failure kind and location only.
    LixityLog.error('window.onerror', {message: redact(String(e.message)), file: redact(String(e.filename || '')), line: e.lineno || 0});
  });
  window.addEventListener('unhandledrejection', function (e) {
    var reason = e && e.reason;
    var message = reason && reason.message ? String(reason.message) : String(reason);
    LixityLog.error('unhandledrejection', {message: redact(message)});
  });
})();
