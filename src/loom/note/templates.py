"""Locating and resolving `loom note add` templates in `.loom/templates`.

A template is either a single Markdown file (`.loom/templates/foo.md`) or
a directory (`.loom/templates/foo/`) bundling a Markdown file with sibling
asset files -- the same "post directory" convention `loom site` uses for
posts with their own images, reused here rather than reimplemented (see
`resolve_template`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loom.errors import NoteError
from loom.paths import LOOM_DIR
from loom.site.content.discovery import _resolve_post_directory

TEMPLATES_DIRNAME = "templates"
DEFAULT_TEMPLATE_NAME = "default"

DEFAULT_TEMPLATE_CONTENT = """\
---
title:
date:
---

"""


@dataclass(frozen=True)
class TemplateSource:
    """A resolved template: its Markdown file, and its asset directory
    if it's a directory template (`None` for a single-file template).
    """

    md_path: Path
    asset_dir: Path | None = None


def templates_dir_for(root: Path) -> Path:
    return root / LOOM_DIR / TEMPLATES_DIRNAME


def ensure_templates_dir(root: Path) -> Path:
    """Bootstrap `.loom/templates/default.md` the first time a folder is
    used as a notes repository. Only fires if `.loom/templates` doesn't
    exist at all, so a repository with a customized template set (even
    one missing `default.md`) is never silently modified.
    """
    templates_dir = templates_dir_for(root)
    if not templates_dir.is_dir():
        templates_dir.mkdir(parents=True, exist_ok=True)
        (templates_dir / f"{DEFAULT_TEMPLATE_NAME}.md").write_text(
            DEFAULT_TEMPLATE_CONTENT, encoding="utf-8"
        )
    return templates_dir


def resolve_template(root: Path, name: str) -> TemplateSource:
    """Resolve a template by name to its Markdown file (and asset dir, if any).

    Raises `NoteError` if `name` matches neither a `{name}.md` file nor a
    `{name}/` directory under `.loom/templates`.
    """
    templates_dir = templates_dir_for(root)

    md_candidate = templates_dir / f"{name}.md"
    if md_candidate.is_file():
        return TemplateSource(md_path=md_candidate)

    dir_candidate = templates_dir / name
    if dir_candidate.is_dir():
        # `_resolve_post_directory`'s error messages say "post directory"
        # even when called on a template directory -- still accurate
        # (same single-md-file-or-name-matched-tiebreak rule), not worth
        # a rewrite just to reword them.
        source = _resolve_post_directory(dir_candidate)
        return TemplateSource(md_path=source.md_path, asset_dir=source.asset_dir)

    available = sorted(_available_template_names(templates_dir))
    choices = ", ".join(available) if available else "(none)"
    raise NoteError(f"No template named {name!r} in {templates_dir}. Available: {choices}")


def _available_template_names(templates_dir: Path) -> set[str]:
    if not templates_dir.is_dir():
        return set()
    names = set()
    for entry in templates_dir.iterdir():
        if entry.name.startswith("."):
            continue
        if entry.is_file() and entry.suffix == ".md":
            names.add(entry.stem)
        elif entry.is_dir():
            names.add(entry.name)
    return names
