# Vendored browser libraries

Pinned third-party files inlined into the single-file dashboard. The dashboard
must stay self-contained and offline; these libraries are therefore vendored
(the installed application needs no build step, package manager or runtime
download). Releases ship the checked-in bytes.

## Native manuscript editor

`codemirror-editor.js` is a native-only, lazily loaded IIFE. It is not inlined
into reports or public reading exports. `scripts/editor/package-lock.json`
records exact dependency versions and registry integrity values; direct packages
are `@codemirror/view` 6.44.0, `@codemirror/state` 6.7.6,
`@codemirror/commands` 6.11.2, `@codemirror/lang-markdown` 6.5.2 and
`@codemirror/search` 6.7.3.
`codemirror.LICENSE` retains all production dependency notices. The esbuild
output inventory, `scripts/editor/bundle-inputs.json`, records the dependency
versions that contribute code to the shipped file.

To rebuild after reviewing upstream changes, run `npm ci --ignore-scripts` and
`npm run build` in `scripts/editor/` (esbuild 0.28.2). Commit the reproducible
bundle, notices, inventory, source and lockfile together. `npm run check`
reproduces them in memory and fails if any checked-in file differs. For a grouped
Dependabot editor update, run `npm run build` against the proposed lock and
include any regenerated files in the same pull request. Node and esbuild are
contributor tools. Installed Lixity needs no Node runtime or network to open the
editor.

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
without `unsafe-eval`. Keep Preact on the reviewed 10.x UMD line while this
loader uses `globalThis.preact`. Preact 11 ships ES modules. A major update
needs a compatible browser artifact or a reviewed change to the loader and CSP
assumptions. [Preact upgrade guide](https://preactjs.com/guide/v11/upgrade-guide/)

Leaflet renders the existing authored GeoJSON locally. Tiles are absent by
default. The separate OpenStreetMap control permits only the current viewport's
standard HTTPS tiles after an explicit action; it adds no prefetch, offline tile
cache, geocoding or routing. Tile approval belongs to the visible map instance
and is cleared when its view or project changes.

## Updating

1. Download the new tarball from the npm registry and verify `dist.integrity`.
2. Replace the file, update the corresponding source loader and record the
   package pin, tarball integrity and shipped file hashes in
   `scripts/browser-vendor.json`.
3. Run `make check` and the browser suites (`make browser`); the browser tests
   cover the component panels end to end.
4. Record the new SHA-512 here and in the release notes.

## Research media

Research uses PhotoSwipe 5.4.4 (MIT, `photoswipe.LICENSE`) for the shared local
image/diagram viewer, and Mermaid Tiny 12.3.0 (MIT, `mermaid.LICENSE`, bundled
third-party notices retained) instead of a second hand-written Mermaid parser.
The pinned UMD PhotoSwipe core and CSS are bundled locally. Review a maintained
alternative if an applicable security issue or supported-browser regression
persists without an upstream fix for the shipped viewer. Any replacement must
preserve the shared offline viewer and its keyboard and focus behavior.

The Mermaid browser bundle is embedded inertly and initialized only for the
first visible diagram. Tiny omits ELK, mindmap, architecture and KaTeX. Lixity
additionally disables diagram images, custom styles, links and configuration
directives before rendering. The source remains readable when syntax is
unsupported or invalid. Tiny 12.3.0 includes DOMPurify 3.4.17, which fixes
advisories affecting the former 3.4.12 pin. The npm tarballʼs `dist/mermaid.tiny.js`
is preserved byte-for-byte, including the DOMPurify and lodash-es notices.

Verified npm tarballs (`dist.integrity`, sha512):

- `https://registry.npmjs.org/photoswipe/-/photoswipe-5.4.4.tgz`:
  `sha512-WNFHoKrkZNnvFFhbHL93WDkW3ifwVOXSW3w1UuZZelSmgXpIGiZSNlZJq37rR8YejqME2rHs9EhH9ZvlvFH2NA==`
- `https://registry.npmjs.org/@mermaid-js/tiny/-/tiny-12.3.0.tgz`:
  `sha512-90BO2kQvmQWj9YjBX2IsLHCw61rN69dPTn5wFfDu+b9aT7qtzfzTA3wpKWeaRAKK85refSo9How5EOeY39DWfA==`

PhotoSwipe's trailing source-map reference is removed as with the older bundles.
PhotoSwipe CSS uses LF line endings; four whitespace-only lines are normalized to empty lines.
Official integration references are [PhotoSwipe](https://photoswipe.com/getting-started/)
and [Mermaid](https://mermaid.js.org/config/usage.html).

## Dependency evidence

The dependency workflow audits the editor lock, including contributor tools,
and queries the npm registry separately for the standalone vendor pins. For
Tiny, this includes the `mermaid` advisory coordinate for the shared renderer
and the verified DOMPurify and lodash-es versions. Review advisory applicability
against the code included in Tiny and Lixity's integration.

The CycloneDX inventory records the exact Python runtime resolution for the
reported interpreter and platform, the standalone vendor files and their known
embedded packages, and the CodeMirror inputs that contributed shipped bytes.
It excludes optional Python extras and contributor-only tools. Exact package
versions inside the prebuilt Mermaid bundle are limited to the retained upstream
notices. The upstream archive supplies no complete dependency manifest for the
minified bundle.
