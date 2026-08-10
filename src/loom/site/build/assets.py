"""Copies static assets into the build output.

`static/` and `images/` are copied verbatim -- Loom doesn't process them,
it just makes sure they end up alongside the generated HTML.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from loom.errors import ContentError
from loom.site.content.discovery import bundle_assets


def copy_assets(source_dir: Path, dest_dir: Path) -> None:
    if not source_dir.is_dir():
        return
    shutil.copytree(source_dir, dest_dir, dirs_exist_ok=True)


def copy_bundle_assets(source_path: Path, asset_dir: Path, post_output_dir: Path) -> None:
    """Copy a post directory's sibling assets into its rendered output dir.

    Raises `ContentError` if an asset is named `index.html` -- copying it
    would silently clobber the rendered post page.
    """
    for item in bundle_assets(source_path, asset_dir):
        if item.name == "index.html":
            raise ContentError(
                f"{item}: bundle asset named 'index.html' collides with the generated post page"
            )
        dest = post_output_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
