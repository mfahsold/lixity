# Discoverability and product communication review

Reviewed 2026-09-24. These are **proposals**, not evidence of increased traffic,
rankings, citations or revenue. No analytics, tracking, external submissions,
commercial services or license changes have been activated.

## Positioning and constraints

Lixity is a local manuscript-analysis engine, not a hosted editor or a general
AI writing service. Its strongest demonstrable benefits are private/offline
analysis, chapter-level inspection, transparent methods and reproducible
reports. LNCL-1.0 permits non-commercial use; paid editing/publishing workflows
must not be advertised as automatically licensed. See the actual [license](../LICENSE).

## Recommended order

| Priority | Repository finding | Proposed improvement | Verification |
| --- | --- | --- | --- |
| P0 | Installation previously listed competing commands without a clear first outcome | Completed: one default route, explicit dev/release distinction, canonical installation guide, first-dashboard command, Windows/API/update help | Clean-environment install and CLI smoke test |
| P1 | Pages is largely one long feature page; methods and guides link out to GitHub | Publish useful, separately addressable HTML pages for installation, interpretation and methods, with unique titles, canonical URLs and internal links | Check rendered content, navigation, indexing eligibility and sitemap entries |
| P1 | Screenshots demonstrate features but not an end-to-end decision | Add a public-domain, read-only interactive demo and a short walkthrough: identify an unusual chapter, inspect a paragraph, interpret the uncertainty | No private text, contacts or adapter endpoints in the demo |
| P1 | README starts with technical breadth | Lead with the task, intended user, one screenshot, a minimal working example and explicit limitations; retain formulas lower down | Ask new users to create their first dashboard without assistance |
| P1 | Large feature list and structured commercial offer may imply more than the package delivers | Distinguish shipped engine, optional adapters and proposed services; review claims such as bespoke language training before retaining them | Every claim maps to code, documentation or a real available service |
| P2 | No evidence-based search/citation measurement in this review | Verify the site in Google Search Console and Bing Webmaster Tools; inspect queries, indexed pages and AI citations where available | Establish a baseline before changing copy; citations are not installs or revenue |
| P2 | Seven analysis languages but only an English landing page | Add a genuinely translated German landing page first, then further languages only with maintained content parity and correct hreflang | Language-specific examples and human review, not keyword-swapped pages |
| P2 | Installation is source-based | Consider signed/tagged release artifacts and a tested release-install matrix; do not imply PyPI availability until deliberately published | Install the actual release on supported OS/Python combinations |

## SEO: concrete technical observations

- `docs/index.html` already includes a canonical URL, social previews, alt text,
  structured data and meaningful HTML. Improve useful content before adding
  more metadata. Keep screenshot dimensions and version claims synchronized.
- `docs/sitemap.xml` currently lists only the landing page. Expand it only when
  real, public canonical pages exist; fragments are not separate pages.
- `docs/robots.txt` is deployed at `/lixity/robots.txt`. Crawlers use the host-root
  robots file, not a project-subdirectory file. A custom domain or control of
  `mfahsold.github.io/robots.txt` would be required for authoritative robots
  policy. Do not treat the existing file as proof of crawler access rules.
  [Google robots documentation](https://developers.google.com/search/docs/crawling-indexing/robots/intro).
- The deployment uploads `docs/` as static files; Markdown guides are not
  converted into styled documentation by this workflow. A small static build
  can improve readable, indexable guide pages without adding an app framework.
- Avoid unsupported accuracy, performance and popularity claims. In particular,
  review absolute “length-invariant” wording against each estimator's limitations.

## GEO: generative-engine visibility, not geolocation

The geographic meta tags about Hamburg do not implement generative-engine
optimization. Recommended work is clear, citable, accessible content: answer
real questions, identify the software and version consistently, link methods
and caveats, and distinguish observations from claims.

Google says its ordinary search fundamentals remain applicable to AI search;
there is no special required schema markup. Do not promise that `llms.txt`,
FAQ markup or a particular phrase will produce citations. Keep `llms.txt`
accurate as a convenience, not as a replacement for usable HTML.
[Google AI-search guidance](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide).

Bing's AI Performance report can help inspect cited pages and grounding
queries. Use it as one channel-specific signal, not a cross-engine ranking or
a measure of product adoption.
[Bing AI Performance](https://www.bing.com/webmasters/help/ai-performance-9f8e7d6c).

## Adoption and sales communication

Use “Try a public sample”, “Install locally” and “Understand the results” as
the main journey. Make privacy, prerequisites and non-commercial licensing
visible before installation. Keep any commercial-license inquiry separate;
do not advertise a checkout, enterprise support or paid service that is not
actually available and approved.

Potential next assets: a two-minute annotated walkthrough, task-specific
examples for authors and researchers, a truthful comparison of engine versus
adapter capabilities, and a compact FAQ on short-text limits, supported
languages, offline use and licensing. Measure successful onboarding, not
just stars or page views. No tracking should be added without a separate
privacy and consent decision.
