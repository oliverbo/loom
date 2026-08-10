"""Orchestrates a full build: load -> validate -> render -> copy assets.

This is what `loom build` calls. It is deliberately a full rebuild every
time -- no incremental caching in v1 -- because a site this size builds
in well under a second and correctness is worth more than speed here.
Incrementality lives entirely in `loom deploy` (see `loom.site.deploy`),
which compares this build's output manifest against the last deployed one.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from loom.errors import ContentError, ValidationError
from loom.git import get_git_info
from loom.site.build.assets import copy_assets, copy_bundle_assets
from loom.site.build.renderers.base import Renderer
from loom.site.build.renderers.html import HtmlRenderer
from loom.site.build.renderers.rss import RssRenderer
from loom.site.config import load_config
from loom.site.content.discovery import discover_posts
from loom.site.content.frontmatter import parse_document
from loom.site.deploy.manifest import MANIFEST_FILENAME, build_manifest, write_manifest
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

    try:
        sources = discover_posts(content_dir)
    except ContentError as exc:
        # validate_site() already checked this; a failure here would mean
        # the content directory changed between the two passes.
        raise ValidationError([str(exc)]) from exc

    documents: list[Document] = []
    for source in sources:
        try:
            doc = parse_document(source.md_path, asset_dir=source.asset_dir)
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

    for doc in documents:
        if doc.asset_dir is not None:
            try:
                copy_bundle_assets(doc.source_path, doc.asset_dir, output_dir / doc.slug)
            except ContentError as exc:
                # Also checked in validate_site(); same "changed between
                # passes" defense as above.
                raise ValidationError([str(exc)]) from exc

    copy_assets(config.resolve(config.static_dir), output_dir / "static")
    copy_assets(config.resolve(config.images_dir), output_dir / "images")

    git_info = get_git_info(site_root)
    manifest = build_manifest(output_dir, commit=git_info.commit, dirty=git_info.dirty)
    write_manifest(output_dir / MANIFEST_FILENAME, manifest)

    return output_dir
