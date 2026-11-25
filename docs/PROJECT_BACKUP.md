# Verified project backup and restore

Choose the procedure by what you need to recover. Save your changes and stop
project writers before capture. The project bundle verifies its declared inventory
of saved files during copying.

| What you need to recover | Backup and restore |
| --- | --- |
| Selected manuscript, explicitly selected settings and assets, and any accepted research | `lixity project-backup` and `lixity project-restore` |
| Accepted research history and retained sources, with root `lixity.toml` when present | [Research archive export and restoration](research/USAGE.md#export-and-restoration) |
| Accepted research plus a Zotero data directory and its stored attachments | [Paired Zotero/research backup and restore](research/USAGE.md#paired-zoteroresearch-backup-and-restore) |
| Saved voice references, passage directions or chapter recordings | [Separate private audio backup](#back-up-private-audio-separately) |

## Back up and verify a restored copy

```bash
lixity project-backup --project ./novel --manuscript manuscript.md \
  --settings lixity.toml --attachment images/cover.png --output ./novel-backup
lixity project-restore --from ./novel-backup --to ./restored-novel
lixity project --project ./restored-novel --json
```

Successful backup and restore commands print JSON with `research_included` and
the exclusions. Failures report a diagnostic and return a nonzero exit status.
Choose a new backup directory outside the project and a restore destination that
does not exist. Failed verification does not publish a restored project.

Check the restored manuscript selection, settings and file paths. If the restore
reports `research_included: true`, run `lixity research audit --project ./restored-novel`
and check a quotation you expect to find. To continue in the browser, use
**Open Project** and select the restored copy in the existing app.

## Inventory and scope

`--manuscript` selects exactly one project-relative source file, preserving its
bytes and relative path. Repeat `--attachment` for each additional source or asset
file you intend to retain. No directories are recursively selected. Repeat
`--settings` for root-local `lixity.toml` or `pyproject.toml`; these files are copied
whole, so review them for credentials and machine-specific paths before selection.
No settings are silently inferred, sanitized or rewritten.

If `research/` exists, its accepted immutable history, retained source bytes and
research configuration are exported using the existing research archive API. Root
`lixity.toml` is excluded from that nested archive; project settings are retained
only through explicit file selection. A damaged or
uninitialized research directory fails capture instead of appearing absent.
Capture verifies the research export by restoring a temporary copy; restoration
uses the existing archive validation and audits the resulting store. The project
wrapper does not change the research schema or rebind manuscript evidence.

`BACKUP.json` records the `lixity-project-backup/1` wrapper schema, selected paths,
research export metadata, exclusions, file sizes and SHA-256 hashes. The bundle
contains selected files under `files/` and, when present, `research.tar.gz`.
Keep the entire bundle together. Hashes detect accidental corruption, not forgery
by someone able to replace both the files and the manifest.

Unselected manuscript files, external linked attachments, hidden files and
directories, browser drafts, recovery and undo history, application profiles,
Zotero databases, caches and generated exports are excluded. Explicit attachments
must be visible files inside the project; hidden paths and the managed top-level
`research`, `exports` and `node_modules` directories are refused. File selection is
an explicit retention decision: visible filenames are not a guarantee that their
contents contain no secrets. Research retains only bytes already accepted into
its store. This is a complete backup of the stated inventory, not a disk image.

To retain a recovery draft for use in a restored folder, open the draft in the
original workspace and save the text you need as a separate file. The recovery
journal can hold private manuscript bytes and its document keys depend on the
original project and source paths. Copying the main SQLite file of a running
workspace can omit committed WAL transactions. A future journal backup needs a
consistent SQLite snapshot and a reviewed way to associate the recovered text
with its destination. [SQLite backup semantics](https://www.sqlite.org/backup.html)

## Back up private audio separately

The bundle excludes these three paths. Copy the ones you need to protected backup
storage while project writers are stopped. Keep their project-relative paths,
the corresponding manuscript bytes and the root settings that select the saved
profiles.

| Project path | What to keep and check |
| --- | --- |
| `.lixity/audio-references/` | The recorded voice and reviewed transcript in each immutable reference record. Check **Author’s voice → Choose from recordings** or run `lixity audio-reference inspect --project ./restored-novel --reference-id ID`. |
| `.lixity/audio-directions.json` | Passage range choices bound to the saved manuscript. Review them with `lixity audio-direction inspect --project ./restored-novel`. |
| `.lixity/audio/exports/` | Complete chapter WAVs and their source-bound metadata. Open the intended chapter and check that **Chapter recording** is ready for reader export. |

Restore these bytes only into the corresponding paths of a separate test copy.
Keep a verified copy before changing a live project. If a direction is stale or
a chapter recording is ineligible, check the restored manuscript revision and
saved settings using the [audio workflow](AUDIO.md). Preserve the original hashes
and references when investigating the mismatch.

## Verification limits

The wrapper permits up to 10,000 files, 20,000 filesystem entries and 10 GiB of
bundle bytes, with a 4 MiB manifest limit. The nested research archive retains its
own 10 GiB uncompressed ceiling and schema validation. Symlinks, special files,
absolute selected paths, traversal and backslash/drive paths are rejected.
Use physical source and destination paths when a directory alias is a symlink.
Files are streamed when hashed. Bundle inventories must match exactly, and restored
selected files are verified again before placement. Publication uses the existing
atomic no-replace directory primitive; unsupported platforms/filesystems fail
explicitly instead of replacing a concurrently created destination.

Restoration preserves file bytes and project-relative paths, not filesystem
permissions, timestamps or external absolute paths. Check restored settings and
external references before resuming work. Existing evidence links remain pinned
to their retained research versions; an audit does not claim that changed prose
still matches every manuscript quotation. Rebuild disposable research search
indexes when needed with `lixity research reindex --project ./restored-novel`.
Test restoration on the intended filesystem before adopting a backup as the
working copy.
