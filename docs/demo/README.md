# Read-only public examples

`report.html` is a self-contained Lixity dashboard of
[`samples/first-look.md`](../../samples/first-look.md): six entirely invented
English chapters. It uses real paragraph, chapter, filter and 3D interactions
from the existing renderer, with no server controls. The small example is not
a benchmark, a calibration corpus or a quality score.

The notice and complete, unchanged distribution license are appended to the
rendered document, outside the analyzed input. Do not substitute private
manuscripts or local project configuration when regenerating this public file.
The example's introductory notice and report header state the generating
version. Regenerate it when the maintained UI or release version changes.

From the repository root after [installation](../INSTALLATION.md), regenerate
the analysis and manuscript PDF examples with the maintained script:

```bash
make examples
# or: .venv/bin/python scripts/build_examples.py
```

The script uses the public Python API with explicit code defaults, injects the
canonical and social metadata plus the provenance notice, and rebuilds this
synthetic demo together with the two public-domain dashboards
(`examples/effi-briest.html`, `examples/pride-and-prejudice.html`) and their
complete PDF reports. It reproduces the demo byte for byte and refuses to ship
an example page beyond its size budget.

Review the regenerated HTML and run `make docs-check` plus the public documentation
browser check described in [`tests/browser/README.md`](../../tests/browser/README.md).
`research.html` reuses the native research reader with a generated, GET-only
`research-data.json` fixture. It has no editing, import or local-machine actions.
Current main (unreleased) adds a [synthetic manuscript](../research/examples/harbour-manuscript.md):
follow a dossier's claim to retained evidence, then open Review to inspect the
saved manuscript quotation and its claim revision. The same API creates the
records used by the page and screenshots; there is no live Zotero connection.
The historical Hamburg map and photochrom are reviewed public-domain sources;
[their manifest](../assets/research/sources.json) records credits and exact file
hashes. Prose, claims, people and journeys are fictional demonstration material.
The coordinate view is not georeferenced to the historical map.

Regenerate the research fixture, page and screenshots with `make screenshots`.
Both examples use the maintained application renderer; neither contacts Zotero
or a user's running service. Research geography and this public research example
are available since v0.7.0.

The Pages boundary explicitly includes these three demo files and the reviewed
visual assets. Other adjacent inputs, archives and local fixtures stay excluded.
