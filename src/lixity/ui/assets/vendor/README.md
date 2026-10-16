# Vendored browser libraries

Pinned third-party files inlined into the single-file dashboard. The dashboard
must stay self-contained and offline; these libraries are therefore vendored
(unminified originals are not fetched at runtime, and there is no build step or
package manager in the release flow).

| File | Library | Version | License | Upstream |
| :--- | :--- | :--- | :--- | :--- |
| `preact-10.29.8.min.js` | [Preact](https://preactjs.com/) | 10.29.8 | MIT (`preact.LICENSE`) | `https://registry.npmjs.org/preact/-/preact-10.29.8.tgz` |
| `htm-3.1.1.umd.js` | [htm](https://github.com/developit/htm) | 3.1.1 | Apache-2.0 (`htm.LICENSE`) | `https://registry.npmjs.org/htm/-/htm-3.1.1.tgz` |

Verified when vendored (npm registry `dist.integrity`, sha512):

- preact-10.29.8.tgz: `sha512-ej2aVZ+vZ8WO7tvlQWRM9N63A0KzF9q4mWJfDUHgYaIofWY9hu74QdnQrjoPMmZi2/nZ5gN0bJCQF49xQqx09Q==`
- htm-3.1.1.tgz: `sha512-983Vyg8NwUE7JkZ6NmOqpCZ+sh1bKv2iYTlUkzlWmA5JD2acKoxd4KVxbMmxX/85mtfdnDmTFoNKcg5DGAvxNQ==`

Local changes to the originals: only trailing `//# sourceMappingURL=…` comment
lines were removed so the inlined bundle never requests a file we do not ship.
They are used through UMD/IIFE globals (`preact`, `htm`), not as ES modules,
because the dashboard bundle is one classic inline script under a nonce CSP
without `unsafe-eval`.

## Updating

1. Download the new tarball from the npm registry and verify `dist.integrity`.
2. Replace the file, update the table above and `_JS_FILES` in `ui/dashboard.py`.
3. Run `make check` and the browser suites (`make browser`); the browser tests
   cover the component panels end to end.
4. Record the new sha512 here and in the release notes.
