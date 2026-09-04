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
validate`, `loom site build`, `loom site preview`, `loom site deploy`, and
`loom note add`.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)

## Installation

Loom isn't published to a package index — install it as a global command
directly from a clone with `uv` (no `pip` needed; `uv` manages its own
Python and dependencies independently of whatever's on your system):

```bash
git clone git@github.com:oliverbo/loom.git
cd loom
uv tool install .
```

This puts `loom` on your `PATH` (`~/.local/bin/loom` by default), separate
from any project's own virtual environment. For the optional deploy
targets, install with their extras:

```bash
uv tool install ".[gcs,firebase]"
```

`uv tool install` copies the package in at install time; it won't pick up
later changes to your checkout on its own. After pulling or finishing work
on Loom itself, reinstall to update the command:

```bash
uv tool install --force ".[gcs,firebase]"
```

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
├── .loom/
│   └── loom.toml
├── content/
│   └── posts/
├── images/
├── templates/
├── static/
└── build/          # generated, disposable, gitignored
```

## Writing posts

A post is a single Markdown file under `content/posts/` (configurable via
`posts_dir` in `loom.toml`), either directly
(`content/posts/my-first-post.md`) or as a **post directory**
(`content/posts/my-first-post/my-first-post.md`) — see "Post directories"
below for when to use the latter. Either way it starts with a
`---`-fenced YAML front matter block:

```markdown
---
title: My First Post
date: 2026-07-17
slug: my-first-post
tags:
  - personal
draft: false
---

Post body in **Markdown** goes here.
```

Front matter fields:

| Field   | Required | Type                    | Notes |
|---------|----------|--------------------------|-------|
| `title` | yes      | string                  | |
| `date`  | yes      | ISO date (`YYYY-MM-DD`) | Used for sort order and the RSS feed. |
| `slug`  | yes      | string                  | Must be lowercase alphanumeric with single hyphens (e.g. `my-first-post`), matching `^[a-z0-9]+(-[a-z0-9]+)*$`, and unique across all posts. Determines the output URL (`build/<slug>/index.html`), independent of the source filename. |
| `tags`  | no       | list of strings         | Defaults to `[]`. |
| `draft` | no       | boolean                 | Defaults to `false`. Draft posts are excluded from `loom site build` unless `--drafts` is passed. |

Any other front matter key is preserved (available to custom templates) but
not otherwise interpreted by Loom.

The index page's blog roll needs an excerpt for each post. Add a
`<!--more-->` line in the body to mark where the excerpt should end;
without one, the excerpt defaults to the post's first paragraph. The index
template (`index.html.j2`) receives this as an `excerpts` dict keyed by
post slug, alongside a `content` dict with each post's full rendered HTML
for themes that want a full-text blog roll instead.

Reference images from `images/` with normal Markdown image syntax and just
the filename, e.g. `![a photo](sunset.jpg)` for `images/sunset.jpg` —
`loom site validate` checks that every referenced image actually exists.
External images (`http://`, `https://`, or protocol-relative `//` URLs) are
left as-is.

The source filename itself doesn't need to match the slug — `slug` in the
front matter is what determines the post's output path — but a matching
name (e.g. `my-first-post.md`) keeps things easy to navigate.

### Post directories

For a post with its own images, give it a directory instead of a lone
file:

```text
content/posts/my-first-post/
├── my-first-post.md
└── sunset.jpg
```

The directory is built exactly like a single-file post — `slug` in its
front matter still decides the output URL. Images alongside it are
referenced by bare filename, e.g. `![a photo](sunset.jpg)`, and are
copied straight into that post's output directory
(`build/<slug>/sunset.jpg`), so the relative reference resolves as-is; a
bundle post can also fall back to `images/` for a shared, site-wide image.
Any file named `index.html` in the directory is rejected, since it would
collide with the generated post page.

If a post directory contains more than one `.md` file, Loom looks for one
named after the directory (`my-first-post.md`) to use as the post; every
other `.md` file in the directory is treated as a non-post file (kept out
of the build output, like an unpublished draft). An ambiguous directory —
several `.md` files with none matching the directory name, or none at
all — makes the build abort with an error rather than guess.

## Notes

`loom note add` scaffolds a new Markdown+front-matter file from a
template. Unlike `site`, it works in *any* folder — a folder becomes a
Loom notes repository the first time you add a note to it, with metadata
(templates, and — for a `loom site` — its `loom.toml` config) stored in a
`.loom` directory:

```console
$ loom note add new-post
Created new-post.md
```

The first `loom note add` in a folder auto-creates
`.loom/templates/default.md`, a blank front-matter skeleton, if
`.loom/templates` doesn't exist yet. Add your own templates there —
`.loom/templates/<name>.md` for a single file, or `.loom/templates/<name>/`
for a directory bundling a Markdown file with sibling asset files (the
same convention as a site's [post directories](#post-directories)) — and
select one with `-t`/`--template`:

```console
$ loom note add trip-report -t travel
```

`-f`/`--field key=value` (repeatable) sets or overrides a front matter
field, e.g. `-f "tags=personal, travel" -f draft=true` — `tags` is split
on commas, `draft` must be `true`/`false`.

`--site` prepopulates the front matter a `loom site` post needs and
writes the note into that site's configured posts directory (`posts_dir`
in `loom.toml`, `content/posts` by default) instead of directly into the
given folder: `title` is derived from the note's name if not already set
(via `-f` or the template), and `slug` is derived from the title. The
site is then validated (`loom note add` reuses `loom site validate`), so
a duplicate slug is caught immediately — the note is still created either
way, but the command exits non-zero if validation fails:

```console
$ loom note add hello-world --site
Created content/posts/hello-world.md
```

`loom note add` makes sure it never overwrites an existing file or
directory — pick a different name (or `-t`) if one already exists.

### iA Writer Markdown flavor

Post bodies are parsed with [writer-md](https://github.com/oliverbo/writer-md),
adding a few [iA Writer](https://ia.net/writer)-specific conventions on top of
plain Markdown:

- **Content blocks** — a bare file reference on its own line (`photo.jpg`,
  `data.csv`, `/notes.md`) is expanded in place: images become `![]()`
  Markdown, CSVs become tables, and other Markdown/text files are included
  recursively. A reference must resolve to a file under the post's own
  directory (its bundle directory, or the file's own folder for a
  single-file post) — see [iA Writer's content block
  spec](https://ia.net/writer/support/general/markdown-content-block).
  Ordinary `![]()` image syntax that isn't a content block, e.g. a
  site-wide `images/` reference, is left untouched.
- **`[%variable]` substitution** — front matter values are available in the
  body as `[%key]` placeholders (e.g. `[%author]`, matched
  case-insensitively). A placeholder with no matching key is left as-is.
- **Annotations** — a trailing iA Writer Annotations block is stripped
  before the post is parsed.

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
- `loom note add NAME [path]` — add a new note from a template. See
  "Notes" above.
  - `-t`, `--template` — template name in `.loom/templates` (default:
    `default`).
  - `-f`, `--field key=value` — set a front matter field (repeatable).
  - `--site` — prepopulate front matter for a site post and validate the
    site afterward.

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

The `gcs` target ships the same comparison to a Google Cloud Storage
bucket, uploading/deleting only changed objects and storing its manifest
at `<prefix>/.loom-manifest.json` in the bucket:

```toml
[deploy]
target = "gcs"
bucket = "my-site-bucket"
prefix = "blog"  # optional; omit to deploy at the bucket root
```

It requires the optional `google-cloud-storage` dependency — install with
the `gcs` extra (`uv tool install ".[gcs]"`, see Installation above) — and
authenticates via Application Default Credentials: run `gcloud auth
application-default login`, or set `GOOGLE_APPLICATION_CREDENTIALS` to a
service account key.

**This target uploads objects; it does not by itself give you clean URLs.**
A request like `https://storage.googleapis.com/<bucket>/posts/hello/` hits
Cloud Storage's raw object API, which does a literal key lookup and 404s,
since only `posts/hello/index.html` exists — it does not fall back to an
index file. To get `/posts/hello/` to resolve automatically, front the
bucket with one of:

- **Native GCS static website hosting**: name the bucket exactly after
  your domain, point that domain's DNS at `c.storage.googleapis.com` via
  CNAME, and set `gcloud storage buckets update gs://<bucket>
  --web-main-page-suffix=index.html --web-error-page=404.html`. HTTP only
  — Cloud Storage doesn't terminate HTTPS for custom domains this way.
- **A Load Balancer + Cloud CDN backend bucket**, for HTTPS and a global
  CDN in front of the same bucket (the standard production setup, though
  it still needs its own rule for directory-index resolution).

If you just want a working public site with clean URLs and HTTPS with the
least setup, use the `firebase` target instead — it resolves directory-style
URLs to `index.html` out of the box and gives free managed SSL on custom
domains.

The `firebase` target ships to [Firebase Hosting](https://firebase.google.com/docs/hosting)
via its REST API:

```toml
[deploy]
target = "firebase"
project = "my-firebase-project"
site = "my-site"  # optional; defaults to `project`
```

It requires the optional `google-auth` and `requests` dependencies —
install with the `firebase` extra (`uv tool install ".[firebase]"`, see
Installation above) — and authenticates via Application Default
Credentials, the same `gcloud auth application-default login` /
`GOOGLE_APPLICATION_CREDENTIALS` setup as `gcs`, not a separate
`firebase login`.

Unlike `directory`/`gcs`, `firebase` is a full-tree target: Firebase
Hosting's own deploy protocol is atomic (create a version, declare its
complete file manifest, upload only the content hashes Firebase doesn't
already have, finalize, release) and does its own hash-based diffing
server-side, so there's no Loom-side `Deployment changes:` summary or
`--dry-run` preview for it — same as `git`/`rsync` below.

`git` and `rsync` remain available as full-sync targets (they always ship
the complete `build/` output; see `loom/site/deploy/git_target.py` and
`rsync_target.py`).
