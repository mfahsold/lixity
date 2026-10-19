# Vendored browser libraries

Pinned third-party files inlined into the single-file dashboard. The dashboard
must stay self-contained and offline; these libraries are therefore vendored
(unminified originals are not fetched at runtime, and there is no build step or
package manager in the release flow).

| File | Library | Version | License | Upstream |
| :--- | :--- | :--- | :--- | :--- |
| `preact-10.29.8.min.js` | [Preact](https://preactjs.com/) | 10.29.8 | MIT (`preact.LICENSE`) | `https://registry.npmjs.org/preact/-/preact-10.29.8.tgz` |
| `htm-3.1.1.umd.js` | [htm](https://github.com/developit/htm) | 3.1.1 | Apache-2.0 (`htm.LICENSE`) | `https://registry.npmjs.org/htm/-/htm-3.1.1.tgz` |
| `leaflet-1.9.4.min.js`, `leaflet-1.9.4.css` | [Leaflet](https://leafletjs.com/) | 1.9.4 | BSD-2-Clause (`leaflet.LICENSE`) | `https://registry.npmjs.org/leaflet/-/leaflet-1.9.4.tgz` |

Verified when vendored (npm registry `dist.integrity`, sha512):

- preact-10.29.8.tgz: `sha512-ej2aVZ+vZ8WO7tvlQWRM9N63A0KzF9q4mWJfDUHgYaIofWY9hu74QdnQrjoPMmZi2/nZ5gN0bJCQF49xQqx09Q==`
- htm-3.1.1.tgz: `sha512-983Vyg8NwUE7JkZ6NmOqpCZ+sh1bKv2iYTlUkzlWmA5JD2acKoxd4KVxbMmxX/85mtfdnDmTFoNKcg5DGAvxNQ==`
- leaflet-1.9.4.tgz: `sha512-nxS1ynzJOmOlHp+iL3FyWqK89GtNL8U8rvlMOsQdTTssxZwCXh8N2NB3GDQOL+YR3XnWyZAxwQixURb+FA74PA==`

Local changes to the JavaScript originals: only trailing
`//# sourceMappingURL=…` comment lines were removed so the inlined bundle never
requests a file we do not ship. Leaflet's three referenced PNG resources are
embedded as data URLs in its CSS; their original bytes come from the same
verified tarball, and no separate image requests are needed.
They are used through UMD/IIFE globals (`preact`, `htm`), not as ES modules,
because the dashboard bundle is one classic inline script under a nonce CSP
without `unsafe-eval`.

Leaflet renders the existing authored GeoJSON locally. Tiles are absent by
default. The separate OpenStreetMap control permits only the current viewport's
standard HTTPS tiles after an explicit action; it adds no prefetch, offline tile
cache, geocoding or routing. Tile approval belongs to the visible map instance
and is cleared when its view or project changes.

## Updating

1. Download the new tarball from the npm registry and verify `dist.integrity`.
2. Replace the file, update the table above and `_JS_FILES` in `ui/dashboard.py`.
3. Run `make check` and the browser suites (`make browser`); the browser tests
   cover the component panels end to end.
4. Record the new sha512 here and in the release notes.

## Research media

Research uses PhotoSwipe 5.4.4 (MIT, `photoswipe.LICENSE`) for the shared local
image/diagram viewer, and Mermaid Tiny 12.2.0 (MIT, `mermaid.LICENSE`, bundled
third-party notices retained) instead of a second hand-written Mermaid parser.
The pinned UMD PhotoSwipe core and CSS are bundled locally. The Mermaid browser
bundle is embedded inertly and initialized only for the first visible diagram;
no CDN, package manager or external diagram service runs in the application.
Tiny omits mindmap, architecture and KaTeX. Lixity additionally disables diagram
images, custom styles, links and configuration directives before rendering.
The source remains readable when syntax is unsupported or invalid.

Verified npm tarballs (`dist.integrity`, sha512):

- `https://registry.npmjs.org/photoswipe/-/photoswipe-5.4.4.tgz`:
  `sha512-WNFHoKrkZNnvFFhbHL93WDkW3ifwVOXSW3w1UuZZelSmgXpIGiZSNlZJq37rR8YejqME2rHs9EhH9ZvlvFH2NA==`
- `https://registry.npmjs.org/@mermaid-js/tiny/-/tiny-12.2.0.tgz`:
  `sha512-9bEE+R974NTh1YJlfc6ztgwhy6+9sE+wAFiFrqvSdtlJHdxGfLytQmHYHNpFKmj94+Z+uMicYrQeGXnTTjILAQ==`

PhotoSwipe's trailing source-map reference is removed as with the older bundles.
PhotoSwipe CSS uses LF line endings; four whitespace-only lines are normalized to empty lines.
Mermaid is otherwise unchanged. Official integration references:
[PhotoSwipe](https://photoswipe.com/getting-started/) and
[Mermaid](https://mermaid.js.org/config/usage.html).
