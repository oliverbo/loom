from __future__ import annotations

from pathlib import Path

import pytest

from loom.errors import ValidationError
from loom.site.build.pipeline import build_site


def test_build_produces_expected_files(sample_site: Path) -> None:
    output_dir = build_site(sample_site)

    assert output_dir == sample_site / "build"
    assert (output_dir / "index.html").is_file()
    assert (output_dir / "feed.xml").is_file()
    assert (output_dir / "hello-world" / "index.html").is_file()


def test_build_excludes_drafts_by_default(sample_site: Path) -> None:
    output_dir = build_site(sample_site)
    assert not (output_dir / "unfinished-thoughts").exists()


def test_build_includes_drafts_when_requested(sample_site: Path) -> None:
    output_dir = build_site(sample_site, include_drafts=True)
    assert (output_dir / "unfinished-thoughts" / "index.html").is_file()


def test_build_renders_post_content(sample_site: Path) -> None:
    output_dir = build_site(sample_site)
    html = (output_dir / "hello-world" / "index.html").read_text()
    assert "<strong>first</strong>" in html
    assert "Hello World" in html


def test_build_copies_static_assets(sample_site: Path) -> None:
    (sample_site / "static" / "style.css").write_text("body {}", encoding="utf-8")
    output_dir = build_site(sample_site)
    assert (output_dir / "static" / "style.css").is_file()


def test_build_fails_fast_on_invalid_content(sample_site: Path) -> None:
    (sample_site / "content" / "posts" / "broken.md").write_text(
        "no front matter here\n", encoding="utf-8"
    )
    with pytest.raises(ValidationError):
        build_site(sample_site)


def test_build_is_idempotent_and_clears_stale_output(sample_site: Path) -> None:
    output_dir = build_site(sample_site)
    stale_file = output_dir / "stale.html"
    stale_file.write_text("leftover", encoding="utf-8")

    build_site(sample_site)

    assert not stale_file.exists()
