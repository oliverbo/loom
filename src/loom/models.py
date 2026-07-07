"""Core data model for site content.

`Document` is the in-memory representation of a single Markdown source
file, produced by `loom.content.frontmatter` and consumed by every
renderer in `loom.build.renderers`. It is intentionally renderer-agnostic:
nothing here knows about HTML or RSS.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from loom.config import SiteConfig

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@dataclass(frozen=True)
class Document:
    """A single piece of content (currently: a blog post).

    `extra` holds any front matter keys Loom doesn't yet know about
    (e.g. a future `summary` or `activitypub_visibility` field) so that
    older Loom versions don't silently drop data a newer version, or a
    downstream renderer, might need.
    """

    slug: str
    title: str
    date: date
    tags: list[str]
    draft: bool
    source_path: Path
    body_markdown: str
    extra: dict[str, Any] = field(default_factory=dict)

    def is_slug_valid(self) -> bool:
        return bool(SLUG_PATTERN.match(self.slug))


@dataclass(frozen=True)
class Site:
    """A fully loaded, ready-to-render site: config plus all documents."""

    config: SiteConfig
    documents: list[Document]

    def sorted_documents(self) -> list[Document]:
        """`self.documents`, newest first.

        Draft filtering happens once, upstream in the build pipeline
        (which decides whether drafts belong in this `Site` at all) --
        renderers should not re-filter by `draft` themselves.
        """
        return sorted(self.documents, key=lambda doc: doc.date, reverse=True)
