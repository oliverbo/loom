"""`loom validate`: check a site's content and config for problems.

All checks run and all problems are collected, rather than stopping at
the first failure, so a single invocation reports everything wrong with
the site at once.
"""

from __future__ import annotations

import re
from pathlib import Path

from loom.errors import ConfigError, ContentError
from loom.site.config import SiteConfig, load_config
from loom.site.content.discovery import bundle_assets, discover_posts
from loom.site.content.frontmatter import parse_document
from loom.site.models import Document

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
    try:
        sources = discover_posts(content_dir)
    except ContentError as exc:
        # Can't discover the rest of `posts/` without a valid listing, so
        # this one error is all we can report this run -- a narrower
        # guarantee than usual for this function, but "abort with an
        # error" is the documented behavior for an ambiguous post
        # directory, and the message lists every file found so a fix is
        # still a single round-trip.
        errors.append(str(exc))
        return errors

    documents: list[Document] = []
    for source in sources:
        try:
            documents.append(parse_document(source.md_path, asset_dir=source.asset_dir))
        except ContentError as exc:
            errors.append(str(exc))

    errors.extend(_check_slugs(documents))
    errors.extend(_check_images(documents, config))
    errors.extend(_check_bundle_collisions(documents))

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
            name = Path(ref).name
            # A bundle post's own directory is checked first, but it can
            # still fall back to the site-wide images/ dir.
            candidates = [doc.asset_dir / name] if doc.asset_dir else []
            candidates.append(images_dir / name)
            if not any(candidate.is_file() for candidate in candidates):
                errors.append(f"{doc.source_path}: referenced image not found: {ref}")
    return errors


def _check_bundle_collisions(documents: list[Document]) -> list[str]:
    errors: list[str] = []
    for doc in documents:
        if doc.asset_dir is None:
            continue
        for asset in bundle_assets(doc.source_path, doc.asset_dir):
            if asset.name == "index.html":
                errors.append(
                    f"{asset}: bundle asset named 'index.html' collides with "
                    "the generated post page"
                )
    return errors
