# Verified project backup and restore

Implemented on current main; unreleased. A project backup is a local directory
bundle, separate from reading websites and research-only exports. Stop manuscript
editing and other project writers before capture. Selected files are checked for
changes during copying, but this is not a transactional snapshot of running apps.

```bash
lixity project-backup --project ./novel --manuscript manuscript.md \
  --settings lixity.toml --attachment images/cover.png --output ./novel-backup
lixity project-restore --from ./novel-backup --to ./restored-novel
lixity research audit --project ./restored-novel
```

Both commands print JSON, including explicit exclusions, and return a nonzero exit
status on failure. Backup output must be a new directory outside the project.
Restore requires a destination that does not exist, even if an existing directory
is empty. Failed verification does not publish a restored project.

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

## Verification limits

The wrapper permits up to 10,000 files, 20,000 filesystem entries and 10 GiB of
bundle bytes, with a 4 MiB manifest limit. The nested research archive retains its
own 10 GiB uncompressed ceiling and schema validation. Symlinks, special files,
absolute selected paths, traversal and backslash/drive paths are rejected. Files
are streamed when hashed. Bundle inventories must match exactly, and restored
selected files are verified again before placement. Publication uses the existing
atomic no-replace directory primitive; unsupported platforms/filesystems fail
explicitly instead of replacing a concurrently created destination.

Restoration preserves file bytes and project-relative paths, not filesystem
permissions, timestamps or external absolute paths. Check restored settings and
external references before resuming work. Existing evidence links remain pinned
to their retained research versions; an audit does not claim that changed prose
still matches every manuscript quotation. Rebuild disposable research search
indexes when needed with `lixity research reindex --project ./restored-novel`.
Linux synthetic tests cover the documented flow; they do not establish equivalent
Windows/macOS filesystem behavior.
