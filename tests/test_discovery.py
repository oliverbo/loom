from __future__ import annotations

from pathlib import Path

import pytest

from loom.errors import ContentError
from loom.site.content.discovery import bundle_assets, discover_posts


def _write(path: Path, text: str = "---\ntitle: T\ndate: 2026-01-01\nslug: t\n---\nBody\n") -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_discover_posts_finds_flat_files(tmp_path: Path) -> None:
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()
    _write(posts_dir / "b.md")
    _write(posts_dir / "a.md")

    sources = discover_posts(tmp_path)

    assert [s.md_path.name for s in sources] == ["a.md", "b.md"]
    assert all(s.asset_dir is None for s in sources)


def test_discover_posts_missing_posts_dir_returns_empty(tmp_path: Path) -> None:
    assert discover_posts(tmp_path) == []


def test_discover_posts_ignores_dotfiles_and_dot_directories(tmp_path: Path) -> None:
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()
    _write(posts_dir / "a.md")
    (posts_dir / ".DS_Store").write_text("junk", encoding="utf-8")
    (posts_dir / ".git").mkdir()

    sources = discover_posts(tmp_path)

    assert [s.md_path.name for s in sources] == ["a.md"]


def test_discover_posts_resolves_single_md_directory(tmp_path: Path) -> None:
    posts_dir = tmp_path / "posts"
    bundle_dir = posts_dir / "my-post"
    bundle_dir.mkdir(parents=True)
    _write(bundle_dir / "notes.md")
    (bundle_dir / "photo.jpg").write_bytes(b"fake-jpeg")

    sources = discover_posts(tmp_path)

    assert len(sources) == 1
    assert sources[0].md_path == bundle_dir / "notes.md"
    assert sources[0].asset_dir == bundle_dir


def test_discover_posts_resolves_matching_named_file_among_several(tmp_path: Path) -> None:
    posts_dir = tmp_path / "posts"
    bundle_dir = posts_dir / "my-post"
    bundle_dir.mkdir(parents=True)
    _write(bundle_dir / "my-post.md")
    _write(bundle_dir / "draft.md")

    sources = discover_posts(tmp_path)

    assert len(sources) == 1
    assert sources[0].md_path == bundle_dir / "my-post.md"
    assert sources[0].asset_dir == bundle_dir


def test_discover_posts_raises_when_no_file_matches_directory_name(tmp_path: Path) -> None:
    posts_dir = tmp_path / "posts"
    bundle_dir = posts_dir / "my-post"
    bundle_dir.mkdir(parents=True)
    _write(bundle_dir / "one.md")
    _write(bundle_dir / "two.md")

    with pytest.raises(ContentError, match="none is named 'my-post.md'"):
        discover_posts(tmp_path)


def test_discover_posts_raises_on_empty_directory(tmp_path: Path) -> None:
    posts_dir = tmp_path / "posts"
    bundle_dir = posts_dir / "empty-post"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "photo.jpg").write_bytes(b"fake-jpeg")

    with pytest.raises(ContentError, match="contains no Markdown file"):
        discover_posts(tmp_path)


def test_bundle_assets_excludes_post_file_other_md_and_dotfiles(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "my-post"
    bundle_dir.mkdir()
    post = _write(bundle_dir / "my-post.md")
    _write(bundle_dir / "draft.md")
    (bundle_dir / "photo.jpg").write_bytes(b"fake-jpeg")
    (bundle_dir / ".DS_Store").write_text("junk", encoding="utf-8")

    assets = bundle_assets(post, bundle_dir)

    assert [a.name for a in assets] == ["photo.jpg"]
