# Loom

Loom is a toolkit for maintaining file-system-based content repositories.
Its functionality is grouped by area — today that's `site`, a
site-independent static-site publisher: point it at a folder of Markdown
content, images, templates, and configuration, and it validates the
content, compiles a static site into a disposable `build/` folder, and
deploys the result to static hosting. More groups (e.g. `notes`) may be
added alongside `site` as Loom grows.

Markdown files are the source of truth. Nothing under a Loom site's source
tree is ever generated — `build/` is the only compiler output, and it is
always safe to delete.

## Status

Early scaffolding. Implemented so far: `loom site init`, `loom site
validate`, `loom site build`, `loom site preview`, and `loom site deploy`.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)

## Development

```bash
uv sync
uv run loom --help
uv run pytest
uv run ruff check .
```

## Site layout

```text
site/
├── content/
│   └── posts/
├── images/
├── templates/
├── static/
├── loom.toml
└── build/          # generated, disposable, gitignored
```

## Commands

- `loom site init [path]` — scaffold a new site.
- `loom site validate [path]` — check content and config for errors.
- `loom site build [path]` — compile the site into `build/`, along with a
  deployment manifest (`build/.loom-manifest.json`) fingerprinting every
  generated file.
- `loom site preview [path]` — serve `build/` locally.
- `loom site deploy [path]` — build, then ship `build/` to the configured
  target.
  - `--no-build` — deploy the existing `build/` output instead of rebuilding.
  - `--dry-run` — show what would be deployed without uploading, deleting,
    or saving a manifest.
  - `--allow-dirty` — deploy even if the Git working tree has uncommitted
    changes (normally rejected).

## Deployment

Git versions the source; it is not used to decide what to deploy. Instead,
`loom site build` writes a manifest of every generated file's SHA-256 hash,
and `loom site deploy` compares that manifest against the one saved from the
last successful deployment to work out what actually changed — a single
source edit, or a template change, can each affect anywhere from one output
file to the whole site, so only comparing the *build output* is reliable.

The `directory` target ships this comparison to a local (or
mounted/synced) filesystem path — the simplest way to try incremental
deployment, and a reasonable target in its own right for e.g. deploying to
a directory served by another web server on the same host:

```toml
[deploy]
target = "directory"
destination = "../deployed-site"
```

```console
$ loom site deploy
Building site...
Generated 43 files.

Deployment changes:
  2 added
  5 modified
  1 deleted
  35 unchanged

Uploading:
  index.html
  posts/new-post/index.html
  feed.xml

Deleting:
  posts/removed-post/index.html

Deployment complete.
Source commit: 6d8b0f2
```

Only the files that changed since the last deploy are copied or removed;
files never tracked in a Loom manifest (e.g. hand-placed files at the
destination) are left alone. The `directory` target stores its own copy of
the manifest at `<destination>/.loom-manifest.json`, which stays untouched
if a deploy fails partway through — the next deploy retries against the
last known-good state.

`git` and `rsync` remain available as full-sync targets (they always ship
the complete `build/` output; see `loom/site/deploy/git_target.py` and
`rsync_target.py`).
