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
- `loom site build [path]` — compile the site into `build/`.
- `loom site preview [path]` — serve `build/` locally.
- `loom site deploy [path]` — build, then ship `build/` to the configured target.
