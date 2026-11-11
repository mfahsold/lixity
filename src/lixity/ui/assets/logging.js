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

  function prefix(kind) { return '[Lixity:' + kind + ']'; }
  function withId(fields) {
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

  var LixityLog = {
    isDebug: function () { return isDebug; },
    setDebug: function (enable) {
      isDebug = !!enable;
      try { localStorage.setItem(KEY, isDebug ? '1' : '0'); } catch (_) {}
      try { console.info('[Lixity] Debug logging ' + (isDebug ? 'enabled' : 'disabled')); } catch (_) {}
    },
    debug: function () {
      if (isDebug && console.debug) console.debug.apply(console, [prefix('debug')].concat([].slice.call(arguments)));
    },
    info: function () {
      if (isDebug && console.info) console.info.apply(console, [prefix('info')].concat([].slice.call(arguments)));
    },
    warn: function () {
      if (console.warn) console.warn.apply(console, [prefix('warn')].concat([].slice.call(arguments)));
    },
    error: function () {
      if (console.error) console.error.apply(console, [prefix('error')].concat([].slice.call(arguments)));
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
      if (console.debug) console.debug(prefix('event') + ' ' + parts.join(' '));
    },
    api: function (method, url, durationMs, status) {
      if (!isDebug) return;
      var clean = String(url).split('?')[0];
      var label = prefix('api') + ' ' + method + ' ' + clean + ' -> ' + status + ' (' + Number(durationMs).toFixed(1) + 'ms)';
      if (status >= 400) { if (console.error) console.error(label); }
      else if (console.debug) console.debug(label);
    },
  };

  if (!window.LixityLog) {
    window.LixityLog = LixityLog;
    window.setLixityDebug = LixityLog.setDebug;
    if (isDebug && console.info) console.info('[Lixity] Debug mode active. Use setLixityDebug(false) to disable.');
  } else {
    // Older bundle order: keep the single instance, add the structured event API.
    if (!window.LixityLog.event) window.LixityLog.event = LixityLog.event;
    if (!window.LixityLog.api) window.LixityLog.api = LixityLog.api;
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
