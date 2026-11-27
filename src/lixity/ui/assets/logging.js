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
    audioClient: function (event, correlation) {
      var workspace = document.body?.dataset;
      if (workspace?.readOnly !== 'false' || workspace.speechCapable !== 'true' ||
          !/^\/(?:w\/[a-f0-9]{32}\/)?api$/.test(workspace.api || '') || !/^https?:$/.test(location.protocol)) return;
      var payload = {event: event};
      if (typeof correlation === 'string' && /^[a-f0-9]{16}$/.test(correlation)) payload.diagnostic_id = correlation;
      var endpoint = new URL(workspace.api + '/audio-client-diagnostic', location.origin);
      // WebKit sends Origin: null on a no-referrer POST in same-origin mode.
      // Pin the URL to this origin and use normal CORS mode to preserve Origin.
      void fetch(endpoint, {
        method: 'POST', mode: 'cors', credentials: 'same-origin', redirect: 'error', referrerPolicy: 'no-referrer', keepalive: true,
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
      }).catch(function () {});
    },
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
