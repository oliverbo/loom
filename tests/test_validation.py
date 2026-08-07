from __future__ import annotations

from pathlib import Path

from loom.site.validation import validate_site


def test_valid_fixture_site_has_no_errors(sample_site: Path) -> None:
    assert validate_site(sample_site) == []


def test_missing_config_reports_error(tmp_path: Path) -> None:
    errors = validate_site(tmp_path)
    assert len(errors) == 1
    assert "loom.toml" in errors[0]


def test_duplicate_slug_reported(sample_site: Path) -> None:
    posts_dir = sample_site / "content" / "posts"
    (posts_dir / "second-hello.md").write_text(
        "---\ntitle: Second\ndate: 2026-01-03\nslug: hello-world\n---\nBody\n",
        encoding="utf-8",
    )
    errors = validate_site(sample_site)
    assert any("duplicates" in e for e in errors)


def test_invalid_slug_reported(sample_site: Path) -> None:
    posts_dir = sample_site / "content" / "posts"
    (posts_dir / "bad-slug.md").write_text(
        "---\ntitle: Bad\ndate: 2026-01-03\nslug: Not_Valid\n---\nBody\n",
        encoding="utf-8",
    )
    errors = validate_site(sample_site)
    assert any("must be lowercase" in e for e in errors)


def test_missing_referenced_image_reported(sample_site: Path) -> None:
    posts_dir = sample_site / "content" / "posts"
    (posts_dir / "with-image.md").write_text(
        "---\ntitle: Img\ndate: 2026-01-03\nslug: img-post\n---\n![alt](missing.png)\n",
        encoding="utf-8",
    )
    errors = validate_site(sample_site)
    assert any("referenced image not found" in e for e in errors)


def test_missing_templates_dir_reported(sample_site: Path) -> None:
    (sample_site / "templates").rmdir()
    errors = validate_site(sample_site)
    assert any("Templates directory not found" in e for e in errors)


def test_bundle_post_image_found_in_own_directory(sample_site: Path) -> None:
    bundle_dir = sample_site / "content" / "posts" / "my-bundle"
    bundle_dir.mkdir()
    (bundle_dir / "my-bundle.md").write_text(
        "---\ntitle: Bundle\ndate: 2026-01-04\nslug: my-bundle\n---\n"
        "![a photo](photo.jpg)\n",
        encoding="utf-8",
    )
    (bundle_dir / "photo.jpg").write_bytes(b"fake-jpeg")

    assert validate_site(sample_site) == []


def test_bundle_post_falls_back_to_site_wide_images_dir(sample_site: Path) -> None:
    (sample_site / "images" / "shared.png").write_bytes(b"fake-png")
    bundle_dir = sample_site / "content" / "posts" / "my-bundle"
    bundle_dir.mkdir()
    (bundle_dir / "my-bundle.md").write_text(
        "---\ntitle: Bundle\ndate: 2026-01-04\nslug: my-bundle\n---\n"
        "![shared](shared.png)\n",
        encoding="utf-8",
    )

    assert validate_site(sample_site) == []


def test_bundle_post_missing_image_reported(sample_site: Path) -> None:
    bundle_dir = sample_site / "content" / "posts" / "my-bundle"
    bundle_dir.mkdir()
    (bundle_dir / "my-bundle.md").write_text(
        "---\ntitle: Bundle\ndate: 2026-01-04\nslug: my-bundle\n---\n"
        "![missing](missing.png)\n",
        encoding="utf-8",
    )

    errors = validate_site(sample_site)
    assert any("referenced image not found" in e for e in errors)


def test_ambiguous_post_directory_reported(sample_site: Path) -> None:
    bundle_dir = sample_site / "content" / "posts" / "my-bundle"
    bundle_dir.mkdir()
    (bundle_dir / "one.md").write_text(
        "---\ntitle: One\ndate: 2026-01-04\nslug: one\n---\nBody\n", encoding="utf-8"
    )
    (bundle_dir / "two.md").write_text(
        "---\ntitle: Two\ndate: 2026-01-04\nslug: two\n---\nBody\n", encoding="utf-8"
    )

    errors = validate_site(sample_site)
    assert len(errors) == 1
    assert "none is named 'my-bundle.md'" in errors[0]


def test_bundle_asset_named_index_html_reported(sample_site: Path) -> None:
    bundle_dir = sample_site / "content" / "posts" / "my-bundle"
    bundle_dir.mkdir()
    (bundle_dir / "my-bundle.md").write_text(
        "---\ntitle: Bundle\ndate: 2026-01-04\nslug: my-bundle\n---\nBody\n",
        encoding="utf-8",
    )
    (bundle_dir / "index.html").write_text("<p>hijack</p>", encoding="utf-8")

    errors = validate_site(sample_site)
    assert any("collides with the generated post page" in e for e in errors)
