"""Split a Markdown file into YAML front matter and body, and turn that
into a `Document`.

This is the one place that understands the on-disk file format, so that
`Document` construction elsewhere never has to think about `---` fences.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from loom.errors import ContentError
from loom.site.models import Document

FENCE = "---"

# Front matter keys that map directly onto named `Document` fields.
# Anything else in the front matter is preserved in `Document.extra`.
KNOWN_KEYS = {"title", "date", "slug", "tags", "draft"}


def split_frontmatter(text: str, *, source: Path) -> tuple[dict[str, Any], str]:
    """Split raw file text into (front matter dict, body markdown).

    Raises `ContentError` if the file doesn't start with a `---` fenced
    YAML block, or if that block isn't a mapping.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != FENCE:
        raise ContentError(f"{source}: missing YAML front matter (no leading '---')")

    closing_index = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == FENCE:
            closing_index = i
            break

    if closing_index is None:
        raise ContentError(f"{source}: front matter is never closed with '---'")

    raw_yaml = "".join(lines[1:closing_index])
    body = "".join(lines[closing_index + 1 :]).lstrip("\n")

    try:
        parsed = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        raise ContentError(f"{source}: front matter is not valid YAML: {exc}") from exc

    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        raise ContentError(f"{source}: front matter must be a mapping, got {type(parsed).__name__}")

    return parsed, body


def parse_document(path: Path, *, asset_dir: Path | None = None) -> Document:
    """Parse a single Markdown source file into a `Document`.

    `asset_dir` is passed through untouched -- see `Document.asset_dir`.
    """
    text = path.read_text(encoding="utf-8")
    front_matter, body = split_frontmatter(text, source=path)

    missing = [key for key in ("title", "date", "slug") if key not in front_matter]
    if missing:
        raise ContentError(f"{path}: missing required front matter field(s): {', '.join(missing)}")

    doc_date = _coerce_date(front_matter["date"], source=path)
    tags = front_matter.get("tags") or []
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise ContentError(f"{path}: 'tags' must be a list of strings")

    draft = front_matter.get("draft", False)
    if not isinstance(draft, bool):
        raise ContentError(f"{path}: 'draft' must be true or false")

    extra = {k: v for k, v in front_matter.items() if k not in KNOWN_KEYS}

    return Document(
        slug=str(front_matter["slug"]),
        title=str(front_matter["title"]),
        date=doc_date,
        tags=list(tags),
        draft=draft,
        source_path=path,
        body_markdown=body,
        extra=extra,
        asset_dir=asset_dir,
    )


def _coerce_date(value: Any, *, source: Path) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ContentError(f"{source}: 'date' is not a valid ISO date: {value!r}") from exc
    raise ContentError(f"{source}: 'date' must be a date, got {type(value).__name__}")
