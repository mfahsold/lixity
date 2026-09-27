# Discoverability and product communication review

Reviewed 2026-09-27 against the repository, public HTTP responses and the primary
sources linked below. GEO here means visibility in generative search answers,
not geographic metadata. Recommendations are not measured ranking improvements.
No analytics, paid tools, search-account verification, link outreach or external
submissions were enabled. The scope is public product material, never manuscripts
or research archives.

## Findings and changes

| Finding | Product change | Remaining limit |
| --- | --- | --- |
| Most useful instructions were Markdown links off the landing page | Three substantial HTML guides: installation, metric interpretation and research/PDF; descriptive URLs and links from the homepage | Search indexing and citation selection are external decisions |
| Long homepage duplicated all style rules inline | Homepage and guides use one cacheable stylesheet and the same visual system | No claim of a measured Core Web Vitals gain |
| Sitemap contained only the homepage | Added the three real canonical guide URLs, with actual content-update dates | Submit the sitemap in verified search accounts when available |
| OCR and publication wording overpromised core capabilities | Separate native PDF extraction, configured scan workers and adapter publication features; distinguish current-main changes from the release | Worker availability is not inference/model verification |
| Geographic GEO tags, keyword metadata and a German alternate locale suggested signals without corresponding content | Removed misleading/redundant metadata; retained accurate canonical/social metadata | A German page would need a real maintained translation |
| Machine-readable software metadata used source-code properties on a single application type | Identify both SoftwareApplication and SoftwareSourceCode; remove unsupported organization/service detail | No fake ratings, review counts or rich-result guarantee |
| Existing `llms.txt` was useful but incomplete | Link practical HTML guides; state release scope and research limits | Convenience index, not an indexing prerequisite or visibility guarantee |

The new guides answer user tasks rather than repeat a feature catalogue:

- [Install and open a project](https://mfahsold.github.io/lixity/guides/installation.html): reproducible install, synthetic first run and inaccessible project troubleshooting.
- [Interpret manuscript metrics](https://mfahsold.github.io/lixity/guides/interpretation.html): consistency, unavailable data, sample floors and a human review workflow.
- [Archive sources and PDFs](https://mfahsold.github.io/lixity/guides/research-pdf.html): provenance, native PDFs versus scans, worker setup and backup verification.

## What the best-practice sources support

### Useful pages and discoverable navigation

Google recommends clear organization, descriptive titles and link text, useful
original content and current information. It does not use the keywords meta tag.
For Lixity this supports a small set of specific guides with copyable examples,
visible limitations and links to the implemented API, rather than many shallow
keyword variants. [Google SEO Starter Guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide).

### AI search uses the same technical foundations

Google describes ordinary SEO fundamentals as applicable to AI Overviews and AI
Mode. Important content should be available as text and linked internally;
there is no special required AI file or schema. Eligibility does not guarantee
inclusion. Lixity's response is readable static HTML and precise answers, with
`llms.txt` kept as an optional convenience. [Google AI features guidance](https://developers.google.com/search/docs/appearance/ai-features).

### Structured data must describe the visible product

Structured data should match visible, accurate content and not advertise hidden
or misleading claims. Lixity marks the real software entity, license and source
repository. It does not invent reviews, prices for unoffered services or FAQ
eligibility. `codeRepository` belongs to SoftwareSourceCode.
[Google structured-data policies](https://developers.google.com/search/docs/appearance/structured-data/sd-policies),
[Schema.org SoftwareSourceCode](https://schema.org/SoftwareSourceCode).

### Crawling policy belongs at the host root

A robots file controls crawling only at the corresponding host root. The public
check on 2026-09-27 returned HTTP 404 for `https://mfahsold.github.io/robots.txt`
and HTTP 200 for the project homepage. The repository file is served at
`/lixity/robots.txt`, so its bot rules are a template, not effective host policy.
A missing root file is not evidence of a block; recheck actual hosting responses
and search inspection tools. Do not change unrelated host policy from this repo.
[Google robots placement](https://developers.google.com/crawling/docs/robots-txt/create-robots-txt).

The sitemap lists canonical public HTML pages only. Dates reflect content edits,
not every deployment. It is a discovery hint, not an indexing command.
[Google sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap).

### Search retrieval and model training are different choices

OpenAI documents OAI-SearchBot for search discovery and GPTBot for model training;
the controls are independent. Enabling training is not a prerequisite for search
visibility. The existing training-crawler policy was not changed. If the maintainer
later configures host-root robots or a custom domain, decide these policies
separately and verify them at the actual origin.
[OpenAI crawler documentation](https://developers.openai.com/api/docs/bots).

### Measure citations separately from adoption

Bing's AI Performance preview reports citations, cited pages and grounding
queries for supported experiences. These are channel-specific observations;
they do not measure installs, trust or revenue. Its documentation also describes
preview dimensions such as topics and citation share; availability may vary.
Use actual account data before making claims about Lixity's visibility.
[Bing AI Performance announcement](https://blogs.bing.com/webmaster/February-2026/Introducing-AI-Performance-in-Bing-Webmaster-Tools-Public-Preview),
[Bing AI Performance reference](https://www.bing.com/webmasters/help/ai-performance-9f8e7d6c).

## Prioritized follow-up opportunities

| Priority | Next action | Evidence of success | Owner / prerequisite |
| --- | --- | --- | --- |
| P1 | Verify this URL-prefix property in Google Search Console and Bing Webmaster Tools; submit the sitemap | Canonical URLs discovered, indexed status inspected, baseline queries recorded | Maintainer access to the accounts; no credentials were available in this review |
| P1 | Publish a genuinely translated German entry guide after language review | Useful German content with reciprocal hreflang and consistent limitations | Maintained translation, not seven keyword-swapped copies |
| P1 | Provide a compact public-domain interactive sample and a two-minute walkthrough | A new user can inspect a chapter and explain why a signal is not a verdict | Public-domain rights checked; no private archive or adapter endpoints |
| P2 | Expand the methods walkthrough with one reproducible public example per common question | Readers can reproduce the result and find the estimator reference | Existing methods and sample corpus; no unsupported accuracy claims |
| P2 | Review actual query gaps before writing further guides | Impressions/query intent align with a useful new answer | Baseline account data; avoid speculative content volume |
| P2 | Consider an independently maintained project domain only if operationally useful | Stable canonical redirects, host-root control and no broken links | Maintainer decision and domain access; not required for these improvements |
| P2 | Share useful examples with relevant writing/digital-humanities communities | Qualified feedback and voluntary references | Separate authorization for any outreach or posting |

These are recommendations, not scheduled work or external actions. Commercial
positioning must continue to reflect LNCL-1.0: books intended for sale, including
self-publishing, need a separate written commercial license. Do not label the
project open source or imply that research use exempts commercial projects.

## Measurement after publication

**First 30 days:** verify public responses, canonical and sitemap selection,
mobile usability and indexing in the maintainer's search accounts. Record a
baseline of landing pages, queries, impressions and clicks. If available, record
Bing's cited pages and citation counts separately. Do not treat an ad-hoc chatbot
answer as a stable rank.

**At 60 days:** compare like periods and annotate releases, outages and content
changes. Review branded versus non-branded discovery and which guide answers
actual questions. Inspect citation context for correctness, not only frequency.
Without an experimental control, correlation is not proof that an edit caused
an increase.

**At 90 days:** prioritize one or two demonstrated gaps, such as German
onboarding or a worked method example. Assess whether users can complete a
synthetic first-dashboard task. Use opt-in feedback or existing aggregate data;
adding telemetry requires a separate privacy/product decision.

The review cannot report current search impressions, indexing coverage, AI
citations or conversion rates: no authenticated search-performance data was
available. This distinction should remain explicit in future updates.
