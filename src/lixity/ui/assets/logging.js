// Shared diagnostics for the native workspace and standalone reports.
(function () {
  'use strict';
  if (window.LixityLog) return;

  var KEY = 'lixity_debug';
  var isDebug = (function () {
    try {
      var saved = localStorage.getItem(KEY);
      if (saved === '1') return true;
      if (saved === '0') return false;
    } catch (_) {}
    if (window.LIXITY_DEBUG) return true;
    var meta = document.querySelector('meta[name="lixity-debug"]');
    return Boolean(meta && meta.content === 'true');
  })();

  function write(level, args) {
    if (typeof console[level] === 'function') console[level]('[Lixity:' + level + ']', ...args);
  }

  function diagnosticId() {
    try {
      var key = 'lixity_diagnostic_id';
      var id = sessionStorage.getItem(key);
      if (id) return id;
      var bytes = crypto.getRandomValues(new Uint8Array(8));
      id = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
      sessionStorage.setItem(key, id);
      return id;
    } catch (_) { return null; }
  }

  window.LixityLog = {
    isDebug: function () { return isDebug; },
    setDebug: function (enable) {
      isDebug = Boolean(enable);
      try { localStorage.setItem(KEY, isDebug ? '1' : '0'); } catch (_) {}
    },
    debug: function (...args) { if (isDebug) write('debug', args); },
    info: function (...args) { if (isDebug) write('info', args); },
    perf: function (operation, durationMs, details) {
      if (!isDebug) return;
      write('debug', [operation + ' (' + Number(durationMs).toFixed(1) + 'ms)', details]);
    },
    warn: function (...args) { write('warn', args); },
    error: function (...args) { write('error', args); },
    event: function (name, fields) {
      if (!isDebug) return;
      var parts = ['event=' + name];
      var id = diagnosticId();
      if (id) parts.push('id=' + id);
      Object.keys(fields || {}).sort().forEach(function (key) {
        var value = fields[key];
        if (value === null || value === undefined) return;
        parts.push(key + '=' + (typeof value === 'string' && /[\s="]/.test(value) ? JSON.stringify(value) : String(value)));
      });
      write('debug', [parts.join(' ')]);
    },
    api: function (method, url, durationMs, status) {
      if (!isDebug) return;
      var route = String(url).split(/[?#]/, 1)[0];
      var message = method + ' ' + route + ' -> ' + status + ' (' + Number(durationMs).toFixed(1) + 'ms)';
      write(status >= 400 ? 'error' : 'debug', ['API', message]);
    }
  };
  window.setLixityDebug = window.LixityLog.setDebug;
})();
