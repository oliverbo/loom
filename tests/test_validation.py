from __future__ import annotations

from pathlib import Path

from loom.validation import validate_site


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
