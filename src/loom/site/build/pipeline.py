"""Orchestrates a full build: load -> validate -> render -> copy assets.

This is what `loom build` calls. It is deliberately a full rebuild every
time -- no incremental caching in v1 -- because a site this size builds
in well under a second and correctness is worth more than speed here.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from loom.errors import ContentError, ValidationError
from loom.site.build.assets import copy_assets
from loom.site.build.renderers.base import Renderer
from loom.site.build.renderers.html import HtmlRenderer
from loom.site.build.renderers.rss import RssRenderer
from loom.site.config import load_config
from loom.site.content.discovery import discover_posts
from loom.site.content.frontmatter import parse_document
from loom.site.models import Document, Site
from loom.site.validation import validate_site

# Order doesn't matter between these today, but keeping an explicit list
# (rather than e.g. scanning for Renderer subclasses) is what makes it
# obvious where to plug in search/ActivityPub/newsletter renderers later.
DEFAULT_RENDERERS: list[Renderer] = [HtmlRenderer(), RssRenderer()]


def build_site(site_root: Path, *, include_drafts: bool = False) -> Path:
    """Build the site at `site_root`. Returns the output directory.

    Raises `ValidationError` if the site fails validation; the build
    never proceeds on invalid content.
    """
    errors = validate_site(site_root)
    if errors:
        raise ValidationError(errors)

    config = load_config(site_root)
    content_dir = config.resolve(config.content_dir)

    documents: list[Document] = []
    for path in discover_posts(content_dir):
        try:
            doc = parse_document(path)
        except ContentError as exc:
            # validate_site() already checked this; a failure here would
            # mean the file changed between the two passes.
            raise ValidationError([str(exc)]) from exc
        if doc.draft and not include_drafts:
            continue
        documents.append(doc)

    site = Site(config=config, documents=documents)

    output_dir = config.resolve(config.output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    for renderer in DEFAULT_RENDERERS:
        renderer.render(site, output_dir)

    copy_assets(config.resolve(config.static_dir), output_dir / "static")
    copy_assets(config.resolve(config.images_dir), output_dir / "images")

    return output_dir
