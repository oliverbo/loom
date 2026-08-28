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

## Writing posts

A post is a single Markdown file under `content/posts/`, either directly
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

The `gcs` target ships the same comparison to a Google Cloud Storage
bucket, uploading/deleting only changed objects and storing its manifest
at `<prefix>/.loom-manifest.json` in the bucket:

```toml
[deploy]
target = "gcs"
bucket = "my-site-bucket"
prefix = "blog"  # optional; omit to deploy at the bucket root
```

It requires the optional `google-cloud-storage` dependency
(`pip install 'loom[gcs]'` — quote it, since an unquoted `[gcs]` is
parsed as a glob by zsh) and authenticates via Application Default
Credentials — run `gcloud auth application-default login`, or set
`GOOGLE_APPLICATION_CREDENTIALS` to a service account key.

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

It requires the optional `google-auth` and `requests` dependencies
(`pip install 'loom[firebase]'`) and authenticates via Application Default
Credentials — the same `gcloud auth application-default login` /
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
