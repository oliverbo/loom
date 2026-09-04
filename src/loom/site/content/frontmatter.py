"""Split a Markdown file into YAML front matter and body, and turn that
into a `Document`.

This is the one place that understands the on-disk file format, so that
`Document` construction elsewhere never has to think about `---` fences,
iA Writer content blocks, annotations, or `[%variable]` substitution.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from writer_md import (
    expand_content_blocks,
    split_front_matter,
    strip_annotations,
    substitute_variables,
)
from writer_md.errors import WriterMdError

from loom.errors import ContentError
from loom.site.models import Document

# Front matter keys that map directly onto named `Document` fields.
# Anything else in the front matter is preserved in `Document.extra`.
KNOWN_KEYS = {"title", "date", "slug", "tags", "draft"}


def split_frontmatter(text: str, *, source: Path) -> tuple[dict[str, Any], str]:
    """Split raw file text into (front matter dict, body markdown).

    Raises `ContentError` if the file doesn't start with a `---` fenced
    YAML block, or if that block isn't a mapping.
    """
    try:
        return split_front_matter(text, source=source, required=True)
    except WriterMdError as exc:
        raise ContentError(str(exc)) from exc


def parse_document(path: Path, *, asset_dir: Path | None = None) -> Document:
    """Parse a single Markdown source file into a `Document`.

    `asset_dir` is passed through untouched -- see `Document.asset_dir`.

    The body is expanded for iA Writer content blocks (bare file
    references to images, CSVs, and included text) and `[%variable]`
    placeholders before being stored on the `Document`; references may
    resolve to any file under `asset_dir` for a post directory, or under
    this file's own directory otherwise. A trailing annotations block, if
    present, is stripped first.
    """
    text = strip_annotations(path.read_text(encoding="utf-8"))
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

    root = asset_dir if asset_dir is not None else path.parent
    try:
        expanded = expand_content_blocks(body, current_file=path, root=root, metadata=front_matter)
        body = substitute_variables(expanded, front_matter)
    except WriterMdError as exc:
        raise ContentError(f"{path}: {exc}") from exc

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
