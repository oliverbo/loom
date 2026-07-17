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

Each post is a single Markdown file directly under `content/posts/` (no
subdirectories) with a `---`-fenced YAML front matter block at the top:

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

Reference images from `images/` with normal Markdown image syntax and just
the filename, e.g. `![a photo](sunset.jpg)` for `images/sunset.jpg` —
`loom site validate` checks that every referenced image actually exists.
External images (`http://`, `https://`, or protocol-relative `//` URLs) are
left as-is.

The source filename itself doesn't need to match the slug — `slug` in the
front matter is what determines the post's output path — but a matching
name (e.g. `my-first-post.md`) keeps things easy to navigate.

## Commands

- `loom site init [path]` — scaffold a new site.
- `loom site validate [path]` — check content and config for errors.
- `loom site build [path]` — compile the site into `build/`.
- `loom site preview [path]` — serve `build/` locally.
- `loom site deploy [path]` — build, then ship `build/` to the configured target.
