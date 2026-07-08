"""Copies static assets into the build output.

`static/` and `images/` are copied verbatim -- Loom doesn't process them,
it just makes sure they end up alongside the generated HTML.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def copy_assets(source_dir: Path, dest_dir: Path) -> None:
    if not source_dir.is_dir():
        return
    shutil.copytree(source_dir, dest_dir, dirs_exist_ok=True)
