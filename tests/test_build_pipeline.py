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


def test_build_index_shows_excerpt_and_read_more_link(sample_site: Path) -> None:
    output_dir = build_site(sample_site)
    html = (output_dir / "index.html").read_text()
    assert "<strong>first</strong>" in html
    assert 'href="hello-world/"' in html


def test_build_index_excerpt_stops_at_more_marker(sample_site: Path) -> None:
    (sample_site / "content" / "posts" / "hello-world.md").write_text(
        "---\ntitle: Hello World\ndate: 2026-01-01\nslug: hello-world\n---\n"
        "Teaser text.\n\n<!--more-->\n\nThe rest of the post, hidden from the index.\n",
        encoding="utf-8",
    )
    output_dir = build_site(sample_site)
    index_html = (output_dir / "index.html").read_text()
    post_html = (output_dir / "hello-world" / "index.html").read_text()

    assert "Teaser text." in index_html
    assert "hidden from the index" not in index_html
    assert "hidden from the index" in post_html


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


def test_build_treats_post_directory_as_a_post_and_copies_its_assets(sample_site: Path) -> None:
    bundle_dir = sample_site / "content" / "posts" / "my-bundle"
    bundle_dir.mkdir()
    (bundle_dir / "my-bundle.md").write_text(
        "---\ntitle: Bundle\ndate: 2026-01-04\nslug: my-bundle\n---\n"
        "![a photo](photo.jpg)\n",
        encoding="utf-8",
    )
    image_bytes = b"fake-jpeg-bytes"
    (bundle_dir / "photo.jpg").write_bytes(image_bytes)

    output_dir = build_site(sample_site)

    assert (output_dir / "my-bundle" / "index.html").is_file()
    copied_image = output_dir / "my-bundle" / "photo.jpg"
    assert copied_image.is_file()
    assert copied_image.read_bytes() == image_bytes


def test_build_aborts_on_ambiguous_post_directory(sample_site: Path) -> None:
    bundle_dir = sample_site / "content" / "posts" / "my-bundle"
    bundle_dir.mkdir()
    (bundle_dir / "one.md").write_text(
        "---\ntitle: One\ndate: 2026-01-04\nslug: one\n---\nBody\n", encoding="utf-8"
    )
    (bundle_dir / "two.md").write_text(
        "---\ntitle: Two\ndate: 2026-01-04\nslug: two\n---\nBody\n", encoding="utf-8"
    )

    with pytest.raises(ValidationError):
        build_site(sample_site)
