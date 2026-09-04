"""`loom note add`: create a new note from a template."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from loom.errors import NoteError
from loom.note.templates import ensure_templates_dir, resolve_template
from loom.site.config import load_config
from loom.site.content.discovery import bundle_assets
from loom.site.content.frontmatter import split_frontmatter
from loom.site.validation import validate_site
from loom.slug import slugify, titleize


@dataclass(frozen=True)
class AddNoteResult:
    """The outcome of `add_note`. `validation_errors` is only ever
    populated when `site=True` -- the note is created either way; only
    the caller's exit code should depend on whether it's empty.
    """

    path: Path
    validation_errors: list[str] = field(default_factory=list)


def add_note(
    root: Path,
    name: str,
    *,
    template: str = "default",
    fields: dict[str, str] | None = None,
    site: bool = False,
    today: str,
) -> AddNoteResult:
    """Create a new note named `name` under `root` from `template`.

    `fields` overrides front matter keys from the template, taking
    precedence over everything, including the `--site` defaults below.

    With `site=True`, `root` must be a `loom site` (i.e. contain
    `.loom/loom.toml`); the note is written into that site's configured
    posts directory (`posts_dir` in `loom.toml`, `content/posts` by
    default) instead of directly under `root`, and any still-missing
    `title`, `slug`, `date`, `draft`, `tags` front matter is filled in
    before the site is validated (post-creation; the note is kept
    regardless of the result).
    """
    _check_safe_name(name)
    fields = fields or {}

    # Bootstraps `.loom/templates/default.md` on first use of this
    # folder as a notes repository -- runs even if the `--site` check
    # below goes on to fail, since that's harmless and idempotent, and
    # "any folder can become a notes repository" on first touch
    # shouldn't depend on the rest of this particular invocation
    # succeeding.
    ensure_templates_dir(root)
    source = resolve_template(root, template)

    if site:
        config = load_config(root)
        base = config.resolve(config.posts_dir)
    else:
        base = root

    if source.asset_dir is not None:
        note_dir = base / name
        destination = note_dir / f"{name}.md"
        if note_dir.exists():
            raise NoteError(f"{note_dir} already exists")
    else:
        note_dir = None
        destination = base / f"{name}.md"
        if destination.exists():
            raise NoteError(f"{destination} already exists")

    template_text = source.md_path.read_text(encoding="utf-8")
    front_matter, body = split_frontmatter(template_text, source=source.md_path)

    front_matter.update(fields)

    if site:
        _fill_site_defaults(front_matter, name=name, today=today)

    destination.parent.mkdir(parents=True, exist_ok=True)
    if fields or site:
        # Only re-serialize when something actually changed -- otherwise
        # a plain `loom note add` would round-trip an untouched template
        # through YAML and turn a blank `title:` into a literal `null`.
        destination.write_text(_render(front_matter, body), encoding="utf-8")
    else:
        destination.write_text(template_text, encoding="utf-8")

    if note_dir is not None:
        for asset in bundle_assets(source.md_path, source.asset_dir):
            shutil.copy2(asset, note_dir / asset.name)

    validation_errors = validate_site(root) if site else []
    return AddNoteResult(path=destination, validation_errors=validation_errors)


def _check_safe_name(name: str) -> None:
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise NoteError(f"{name!r} is not a valid note name")


def _fill_site_defaults(front_matter: dict[str, Any], *, name: str, today: str) -> None:
    """Fill missing/blank `title`, `slug`, `date`, `draft`, `tags`.

    Order matters: `title` must be resolved before `slug` is derived
    from it, since `slug` falls back to `slugify(title)` -- including a
    title supplied via `fields` a moment ago in `add_note`, not just the
    template's own.
    """
    if not front_matter.get("title"):
        front_matter["title"] = titleize(name)
    if not front_matter.get("slug"):
        front_matter["slug"] = slugify(str(front_matter["title"]))
    if not front_matter.get("date"):
        front_matter["date"] = today
    front_matter.setdefault("draft", False)
    front_matter.setdefault("tags", [])


def _render(front_matter: dict[str, Any], body: str) -> str:
    yaml_text = yaml.safe_dump(front_matter, sort_keys=False)
    return f"---\n{yaml_text}---\n\n{body}"
