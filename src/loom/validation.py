"""`loom validate`: check a site's content and config for problems.

All checks run and all problems are collected, rather than stopping at
the first failure, so a single invocation reports everything wrong with
the site at once.
"""

from __future__ import annotations

import re
from pathlib import Path

from loom.config import SiteConfig, load_config
from loom.content.discovery import discover_posts
from loom.content.frontmatter import parse_document
from loom.errors import ConfigError, ContentError
from loom.models import Document

IMAGE_REF_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")


def validate_site(site_root: Path) -> list[str]:
    """Return a list of human-readable problems. Empty list means the site is valid."""
    errors: list[str] = []

    try:
        config = load_config(site_root)
    except ConfigError as exc:
        return [str(exc)]

    templates_dir = config.resolve(config.templates_dir)
    if not templates_dir.is_dir():
        errors.append(f"Templates directory not found: {templates_dir}")

    content_dir = config.resolve(config.content_dir)
    post_paths = discover_posts(content_dir)

    documents: list[Document] = []
    for path in post_paths:
        try:
            documents.append(parse_document(path))
        except ContentError as exc:
            errors.append(str(exc))

    errors.extend(_check_slugs(documents))
    errors.extend(_check_images(documents, config))

    return errors


def _check_slugs(documents: list[Document]) -> list[str]:
    errors: list[str] = []
    seen: dict[str, Path] = {}
    for doc in documents:
        if not doc.is_slug_valid():
            errors.append(
                f"{doc.source_path}: slug {doc.slug!r} must be lowercase "
                "alphanumeric with hyphens (e.g. 'my-first-post')"
            )
        if doc.slug in seen:
            errors.append(f"{doc.source_path}: slug {doc.slug!r} duplicates {seen[doc.slug]}")
        else:
            seen[doc.slug] = doc.source_path
    return errors


def _check_images(documents: list[Document], config: SiteConfig) -> list[str]:
    errors: list[str] = []
    images_dir = config.resolve(config.images_dir)
    for doc in documents:
        for ref in IMAGE_REF_PATTERN.findall(doc.body_markdown):
            if ref.startswith(("http://", "https://", "//")):
                continue
            image_path = images_dir / Path(ref).name
            if not image_path.is_file():
                errors.append(f"{doc.source_path}: referenced image not found: {ref}")
    return errors
