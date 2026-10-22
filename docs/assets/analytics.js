// Public Pages aggregates: https://www.goatcounter.com/help/pixel
(() => {
  'use strict';
  const origin = 'https://mfahsold.github.io';
  if (location.origin !== origin || !location.pathname.startsWith('/lixity/')) return;
  if (navigator.globalPrivacyControl === true ||
      [navigator.doNotTrack, window.doNotTrack].some(value => value === '1' || value === 'yes')) return;
  if (window.lixityPagesAnalyticsLoaded) return;
  window.lixityPagesAnalyticsLoaded = true;

  let warned = false;
  function warn(reason) {
    if (warned) return;
    warned = true;
    console.warn('Lixity Pages analytics: ' + reason);
  }
  const loader = document.currentScript;
  if (!loader || !loader.src) { warn('configuration location is unavailable.'); return; }
  const configUrl = new URL('analytics.json', loader.src);
  if (configUrl.origin !== origin || configUrl.pathname !== '/lixity/assets/analytics.json') {
    warn('configuration location is invalid.'); return;
  }

  // Prepared public pages may pin the reviewed site code without widening the
  // product website's closed read transport. Private exports never add this script.
  const configuration = loader.hasAttribute('data-site-code')
    ? Promise.resolve().then(() => ({site_code: JSON.parse(loader.getAttribute('data-site-code'))}))
    : fetch(configUrl.href, {credentials: 'omit', redirect: 'error', cache: 'no-cache', referrerPolicy: 'no-referrer'})
      .then(response => {
        if (!response.ok) throw new Error('configuration');
        return response.json();
      });
  configuration.then(config => {
      if (!config || Array.isArray(config) || typeof config !== 'object') {
        warn('configuration is invalid.'); return;
      }
      if (config.site_code === null) return;
      if (typeof config.site_code !== 'string' ||
          !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(config.site_code)) {
        warn('site code is invalid.'); return;
      }
      const endpoint = 'https://' + config.site_code + '.goatcounter.com/count';
      const images = new Set();
      function count(path, title, referrer, event) {
        if (images.size >= 20) { warn('pending measurement limit reached.'); return; }
        const pixel = new Image();
        pixel.referrerPolicy = 'no-referrer';
        images.add(pixel);
        let timer;
        function release() {
          clearTimeout(timer);
          pixel.onload = pixel.onerror = null;
          images.delete(pixel);
        }
        pixel.onload = release;
        pixel.onerror = () => { release(); warn('measurement could not be delivered.'); };
        timer = setTimeout(() => { release(); warn('measurement did not finish.'); }, 10000);
        // rnd is a per-request cache buster, not a stored or session identifier.
        const params = new URLSearchParams({p: path, t: title, r: referrer,
          e: String(event), rnd: Math.random().toString(36).slice(2, 10) || '0'});
        pixel.src = endpoint + '?' + params.toString();
      }
      let referrer = '';
      try {
        const previous = new URL(document.referrer);
        if (previous.protocol === 'https:' || previous.protocol === 'http:') referrer = previous.origin;
      } catch { /* Direct arrivals have no referrer. */ }
      count(location.pathname, document.title.slice(0, 200) || location.pathname, referrer, false);

      const labels = {'demo-open': 'Open demo', 'install-open': 'Open installation',
        'repository-open': 'Open repository', 'pdf-download': 'Download PDF'};
      if (location.pathname === '/lixity/demo/report.html') {
        document.addEventListener('lixity:public-pdf-download', () => {
          count('pdf-download', labels['pdf-download'], '', true);
        });
      }
      document.addEventListener('click', event => {
        const anchor = event.target instanceof Element && event.target.closest('a[href]');
        if (!anchor) return;
        let destination;
        try { destination = new URL(anchor.href); } catch { return; }
        let name;
        if (destination.origin === origin) {
          if (destination.pathname === '/lixity/demo/report.html') name = 'demo-open';
          else if (['/lixity/INSTALLATION.md', '/lixity/guides/installation.html'].includes(destination.pathname) ||
                   (destination.pathname === '/lixity/' && ['#install', '#installation'].includes(destination.hash))) name = 'install-open';
          else if (/^\/lixity\/demo\/warehouse-4-(book|editor|sheet|report|document)\.pdf$/.test(destination.pathname)) name = 'pdf-download';
        } else if (destination.origin === 'https://github.com' &&
                   /^\/mfahsold\/lixity\/?$/.test(destination.pathname)) name = 'repository-open';
        if (name) count(name, labels[name], '', true);
      });
    }).catch(() => warn('configuration could not be loaded.'));
})();
