# Loom

Loom is a site-independent publishing tool. Point it at a folder of Markdown
content, images, templates, and configuration; it validates the content,
compiles a static site into a disposable `build/` folder, and deploys the
result to static hosting.

Markdown files are the source of truth. Nothing under a Loom site's source
tree is ever generated — `build/` is the only compiler output, and it is
always safe to delete.

## Status

Early scaffolding. Implemented so far: `loom init`. `validate`, `build`,
`preview`, and `deploy` are stubs — see the implementation plan below.

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

- `loom init [path]` — scaffold a new site.
- `loom validate [path]` — check content and config for errors.
- `loom build [path]` — compile the site into `build/`.
- `loom preview [path]` — serve `build/` locally.
- `loom deploy [path]` — build, then ship `build/` to the configured target.
