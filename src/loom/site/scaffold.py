"""`loom init`: generate a new site's directory structure."""

from __future__ import annotations

import shutil
from pathlib import Path

from loom.errors import LoomError
from loom.site.resources import DEFAULT_THEME_DIR

DEFAULT_CONFIG = """\
title = "My Site"
base_url = "/"
description = ""
author = ""
language = "en"
"""

SAMPLE_POST = """\
---
title: My First Post
date: {date}
slug: my-first-post
tags:
  - personal
draft: false
---

Welcome to your new Loom site. Edit this file at
`content/posts/my-first-post.md` to get started.
"""


def init_site(site_root: Path, *, today: str) -> None:
    """Create the standard Loom directory structure at `site_root`.

    Refuses to run if `loom.toml` already exists, so `loom init` can't
    silently clobber an existing site.
    """
    if (site_root / "loom.toml").exists():
        raise LoomError(f"{site_root} already contains a loom.toml; refusing to overwrite")

    for directory in ("content/posts", "images", "static"):
        (site_root / directory).mkdir(parents=True, exist_ok=True)

    # Templates are meant to be edited, not just fallen back to -- copy
    # Loom's bundled theme in as a starting point rather than leaving
    # templates/ empty. (build/ still falls back to the bundled theme for
    # any file this directory doesn't have, e.g. if one is deleted later.)
    shutil.copytree(DEFAULT_THEME_DIR, site_root / "templates", dirs_exist_ok=True)

    (site_root / "loom.toml").write_text(DEFAULT_CONFIG, encoding="utf-8")
    (site_root / "content" / "posts" / "my-first-post.md").write_text(
        SAMPLE_POST.format(date=today), encoding="utf-8"
    )
