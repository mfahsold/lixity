// A prepared website has no server: every API read belongs to its inline snapshot.
(function () {
  "use strict";
  var readOnly = document.body.dataset.readOnly === "true";
  var resources = new Map(), responses = new Map(), localResources = new Set();
  var nativeFetch = window.fetch.bind(window);
  var base = new URL(document.baseURI);

  function canonical(value) {
    try {
      var url = new URL(value, base);
      if (url.origin !== base.origin || url.protocol !== base.protocol || url.username || url.password || url.hash ||
          !url.pathname.startsWith("/api/")) return null;
      url.searchParams.sort();
      return url.pathname + url.search;
    } catch (_) { return null; }
  }
  function safeResource(value) {
    if (typeof value !== "string" || !value || /[\\?#:]/.test(value) || value.startsWith("/")) return null;
    try {
      var decoded = decodeURIComponent(value);
      if (decoded.split("/").some(function(part) { return !part || part === "." || part === ".."; }) ||
          /[\\?#:]/.test(decoded)) return null;
      var url = new URL(value, base);
      return url.href.startsWith(new URL(".", base).href) ? value : null;
    } catch (_) { return null; }
  }
  window.LixitySite = {
    readOnly: readOnly,
    publication: null,
    resourceUrl: function(value) {
      var mapped = resources.get(canonical(value));
      if (mapped) return mapped;
      var relative = safeResource(value);
      return relative && localResources.has(new URL(relative, base).href) ? relative : null;
    },
  };
  if (!readOnly) return;

  try {
    var envelope = JSON.parse(document.getElementById("lixity-site-data").textContent);
    if (envelope.schema_version !== "lixity-read-only-site-data/1") throw new Error("Unknown website data format");
    window.LixitySite.publication = envelope.publication || null;
    Object.entries(envelope.responses || {}).forEach(function(entry) {
      var key = canonical(entry[0]);
      if (key) responses.set(key, entry[1]);
    });
    Object.entries(envelope.resources || {}).forEach(function(entry) {
      var key = canonical(entry[0]), relative = safeResource(entry[1]);
      if (!key || !relative) return;
      resources.set(key, relative);
      localResources.add(new URL(relative, base).href);
    });
  } catch (_) { /* An absent or invalid snapshot remains closed to all network reads. */ }

  window.fetch = async function(input, init) {
    var method = String(init && init.method || input && input.method || "GET").toUpperCase();
    var signal = init && init.signal || input && input.signal;
    if (signal && signal.aborted) throw signal.reason || new Error("Request aborted");
    if (method !== "GET") throw new Error("This website is read-only.");
    var value = typeof input === "string" || input instanceof URL ? String(input) : input.url;
    var key = canonical(value);
    if (key && responses.has(key)) {
      var payload = responses.get(key);
      var markdown = key.startsWith("/api/research/matrix?") && new URL(value, base).searchParams.get("format") === "md";
      return new Response(markdown ? payload.text : JSON.stringify(payload), {
        status: 200, headers: {"Content-Type": markdown ? "text/markdown; charset=utf-8" : "application/json; charset=utf-8"},
      });
    }
    var resource = key && resources.get(key);
    var url = new URL(resource || value, base);
    if (localResources.has(url.href)) return nativeFetch(url.href, {method: "GET", signal: signal});
    throw new Error("This read is not included in the website snapshot.");
  };
})();
