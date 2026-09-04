from __future__ import annotations

from pathlib import Path

import pytest

from loom.errors import LoomError
from loom.site.scaffold import init_site


def test_init_creates_expected_structure(tmp_path: Path) -> None:
    init_site(tmp_path, today="2026-01-01")

    assert (tmp_path / ".loom" / "loom.toml").is_file()
    assert (tmp_path / "content" / "posts" / "my-first-post.md").is_file()
    for directory in ("content/posts", "images", "templates", "static"):
        assert (tmp_path / directory).is_dir()


def test_init_copies_default_templates(tmp_path: Path) -> None:
    init_site(tmp_path, today="2026-01-01")

    templates_dir = tmp_path / "templates"
    for name in ("post.html.j2", "index.html.j2", "feed.xml.j2"):
        assert (templates_dir / name).is_file()


def test_init_refuses_to_overwrite_existing_site(tmp_path: Path) -> None:
    init_site(tmp_path, today="2026-01-01")
    with pytest.raises(LoomError, match="already exists"):
        init_site(tmp_path, today="2026-01-02")
