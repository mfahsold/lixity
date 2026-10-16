# Licensing

**Lixity is open source under the GNU Affero General Public License v3.0
(AGPL-3.0-or-later), with an optional commercial license for uses that cannot
meet the AGPL.**

| Use of Lixity | Permission |
| :--- | :--- |
| Private writing, research, teaching — any purpose | AGPL-3.0-or-later |
| Preparing or selling a book, including self-publishing | AGPL-3.0-or-later; no separate permission needed |
| Paid editing, commissioned writing or client reports | AGPL-3.0-or-later; no separate permission needed |
| Modifying Lixity for yourself or your organization | AGPL-3.0-or-later (share changes as the AGPL requires) |
| Redistributing Lixity or a modified version | AGPL-3.0-or-later (source and license must travel with it) |
| Embedding Lixity in a closed-source product or service | Separate written commercial license |
| Running a modified Lixity as a network service without releasing the source | Separate written commercial license |

Writing and selling your manuscript is **your** work: the license covers the
software, not the text you produce with it. You do not need permission to sell
a book that was written with Lixity's help.

## The two options in plain terms

- **Default: AGPL-3.0-or-later.** Use Lixity freely — privately, commercially,
  in research and in teaching. If you distribute the software or a modified
  version, the AGPL requires that recipients receive the corresponding source
  under the same license. Section 13 covers modified versions offered over a
  network.
- **Commercial license.** For organizations that cannot accept the AGPL's
  copyleft obligations — for example closed-source product integration,
  proprietary redistribution, or internal policies that exclude AGPL code —
  a separate written commercial license is available. It grants the same
  functional rights without the source-sharing obligations.

The maintainer receives no rights to your manuscript, your research sources or
your book under either option.

## When to talk to the maintainer

Contact [mfahsold@googlemail.com](mailto:mfahsold@googlemail.com?subject=Lixity%20Commercial%20License)
**before** distributing Lixity inside a closed-source product or service, or
when your legal or procurement team needs written commercial terms. Include
your project, how Lixity is integrated and the intended distribution.

Historical note: releases up to v0.3.0 were published under the Lixity
Non-Commercial License 1.0 (LNCL-1.0); its unchanged text remains in
[LICENSE-LNCL-1.0](https://github.com/mfahsold/lixity/blob/main/LICENSE-LNCL-1.0)
for existing users. Code from this change onward is available under the AGPL,
and the commercial option replaces the former non-commercial restriction.

## Rights in imported research sources and citations

Using `lixity research ingest --allow-retention` confirms that you have permission
to retain a local copy of that material. It does not grant or transfer copyright,
authorize redistribution, or place imported text under the AGPL. Your manuscript
text, imported source texts, and Lixity's software code remain under their own
separate respective rights and licenses.

Manual manuscript quote–claim links in v0.3.0 separately require
explicit permission to retain the selected quote locally. That confirmation
does not authorize publishing the quote. Research backups/exports contain these
retained manuscript quotations; keep them in the project's private storage.
See [the retention workflow](research/USAGE.md#associate-a-manuscript-quote-with-a-claim).

## Third-party components

Lixity's own code is AGPL-3.0-or-later. The single-file dashboard vendors two
small browser libraries, pinned and shipped with their license texts:

- **Preact 10.29.8** — MIT, `src/lixity/ui/assets/vendor/preact.LICENSE`.
- **htm 3.1.1** — Apache-2.0, `src/lixity/ui/assets/vendor/htm.LICENSE`.

`src/lixity/ui/assets/vendor/README.md` records the exact upstream tarballs and
sha512 integrity values. Neither library is fetched at runtime, neither is a
Python dependency, and the release wheel ships them as package data.

## Questions

This guide explains the intended policy; the full [AGPL text](https://github.com/mfahsold/lixity/blob/main/LICENSE)
contains the binding terms. Have a qualified lawyer review your situation for
closed-source integration or any agreement that changes these terms.
