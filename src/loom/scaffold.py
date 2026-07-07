"""`loom init`: generate a new site's directory structure."""

from __future__ import annotations

from pathlib import Path

from loom.errors import LoomError

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

    for directory in ("content/posts", "images", "templates", "static"):
        (site_root / directory).mkdir(parents=True, exist_ok=True)

    (site_root / "loom.toml").write_text(DEFAULT_CONFIG, encoding="utf-8")
    (site_root / "content" / "posts" / "my-first-post.md").write_text(
        SAMPLE_POST.format(date=today), encoding="utf-8"
    )
