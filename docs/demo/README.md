# Read-only first-look report

`report.html` is the only file from this directory published to GitHub Pages.
It is a self-contained Lixity dashboard of
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
every published example with the maintained script:

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
The Pages staging script includes `demo/report.html` and the `examples/**` pages;
the source Markdown, JSON, archives and other adjacent files are not publications.
