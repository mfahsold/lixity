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
The current example is generated with Lixity 2.3.0, as stated in its introductory
notice and report header.

From the repository root after [installation](../INSTALLATION.md), regenerate
with the public Python API and explicit code defaults:

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
import html
from pathlib import Path

from lixity.api import dashboard

root = Path.cwd()
text = (root / "samples/first-look.md").read_text(encoding="utf-8")
report = dashboard(
    text, language="en", project_config={}, title="An invented night shift"
)
assert report.count("</head>") == 1
report = report.replace("</head>", '<link rel="canonical" href="https://mfahsold.github.io/lixity/demo/report.html"/>\n</head>', 1)
notice = '''
<section class="panel" id="demo-context" aria-labelledby="demo-heading">
<h2 id="demo-heading">Synthetic read-only example</h2>
<p><strong>Generated with Lixity 2.3.0.</strong> This example includes paragraph
Values disclosures, review links and the tabbed style area.</p>
<p>Six invented English chapters about a night shift at a river signal house.
This report contains no real manuscript. It accepts no uploads and saves no edits.</p>
<p>Compare chapters, choose a style layer or open a paragraph to read its text and
source lines. The 3D view explores the same measured chapter data. These short
samples and language-dependent heuristics support human review; they are not a
benchmark, a calibration corpus or a writing-quality verdict.</p>
<div class="license-links"><a href="../guides/first-look.html">Follow the three-minute walkthrough</a>
<a href="#demo-license">Read the complete distribution license</a></div>
</section>
'''
license_text = (root / "LICENSE").read_text(encoding="utf-8")
appendix = '''
<section class="panel" id="demo-license" aria-labelledby="demo-license-heading">
<h2 id="demo-license-heading">Distribution license (LNCL-1.0)</h2>
<p>This report and its original synthetic example are distributed under the
existing Lixity Non-Commercial License. Commercial use requires a separate
written license. The complete, unchanged repository LICENSE is included below;
it is an appendix, not part of the analyzed text.</p>
<details><summary>Read the complete LICENSE</summary>
<pre id="demo-license-text" style="white-space:pre-wrap;overflow-wrap:anywhere;font-size:var(--text-note)">'''
appendix += html.escape(license_text)
appendix += "</pre></details>\n</section>\n"
assert report.count("</header>") == 1
report = report.replace("</header>", "</header>" + notice, 1)
boundary = "\n</div>\n<footer>"
assert report.count(boundary) == 1
report = report.replace(boundary, appendix + boundary, 1)
(root / "docs/demo/report.html").write_text(
    "\n".join(line.rstrip() for line in report.splitlines()) + "\n", encoding="utf-8"
)
PY
```

Review the regenerated HTML and run `make docs-check` plus the public documentation
browser check described in [`tests/browser/README.md`](../../tests/browser/README.md).
The Pages staging script explicitly includes `demo/report.html`; this recipe,
source Markdown, JSON, archives and other adjacent files are not demo publications.
