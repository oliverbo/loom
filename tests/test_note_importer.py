from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from loom.errors import ConfigError, ContentError, NoteError
from loom.note.importer import import_note
from loom.site.content.discovery import _resolve_post_directory
from loom.site.content.frontmatter import split_frontmatter

TODAY = "2026-02-01"


def _read_front_matter(path: Path) -> dict:
    meta, _ = split_frontmatter(path.read_text(encoding="utf-8"), source=path)
    return meta


def _set_mtime(path: Path, iso_date: str) -> None:
    timestamp = datetime.fromisoformat(iso_date).timestamp()
    os.utime(path, (timestamp, timestamp))


def test_imports_single_file_with_no_front_matter(sample_site: Path, tmp_path: Path) -> None:
    source = tmp_path / "old-post.md"
    source.write_text("Just a plain post, no front matter.\n", encoding="utf-8")
    _set_mtime(source, "2020-06-01")

    result = import_note(sample_site, source, today=TODAY)

    assert result.path == sample_site / "content" / "posts" / "old-post.md"
    meta = _read_front_matter(result.path)
    assert meta["title"] == "Old Post"
    assert meta["slug"] == "old-post"
    assert meta["date"] == "2020-06-01"
    assert meta["draft"] is False
    assert meta["tags"] == []
    # The original is untouched.
    assert source.read_text(encoding="utf-8") == "Just a plain post, no front matter.\n"


def test_imports_single_file_with_full_front_matter_unchanged(
    sample_site: Path, tmp_path: Path
) -> None:
    content = (
        "---\n"
        "title: Full Post\n"
        "date: '2021-03-04'\n"
        "slug: full-post\n"
        "draft: false\n"
        "tags: []\n"
        "---\n\n"
        "Body.\n"
    )
    source = tmp_path / "full-post.md"
    source.write_text(content, encoding="utf-8")

    result = import_note(sample_site, source, today=TODAY)

    assert result.path.read_text(encoding="utf-8") == content


def test_case_mismatched_keys_normalized_to_canonical_spelling(
    sample_site: Path, tmp_path: Path
) -> None:
    content = (
        "---\n"
        "Title: Mixed Case\n"
        "Date: '2022-02-02'\n"
        "Slug: mixed-case\n"
        "Draft: true\n"
        "Tags:\n"
        "  - a\n"
        "  - b\n"
        "Summary: kept as-is\n"
        "---\n\n"
        "Body.\n"
    )
    source = tmp_path / "mixed.md"
    source.write_text(content, encoding="utf-8")

    result = import_note(sample_site, source, today=TODAY)

    meta = _read_front_matter(result.path)
    assert meta["title"] == "Mixed Case"
    assert meta["date"] == "2022-02-02"
    assert meta["slug"] == "mixed-case"
    assert meta["draft"] is True
    assert meta["tags"] == ["a", "b"]
    assert meta["Summary"] == "kept as-is"
    assert "Title" not in meta
    assert "Date" not in meta
    assert "Slug" not in meta


def test_date_extracted_from_filename_with_title_suffix(sample_site: Path, tmp_path: Path) -> None:
    source = tmp_path / "2024-01-15-my-old-post.md"
    source.write_text("Body.\n", encoding="utf-8")

    result = import_note(sample_site, source, today=TODAY)

    # The date prefix is stripped from the destination filename too.
    assert result.path == sample_site / "content" / "posts" / "my-old-post.md"
    meta = _read_front_matter(result.path)
    assert meta["date"] == "2024-01-15"
    assert meta["title"] == "My Old Post"
    assert meta["slug"] == "my-old-post"


def test_bare_date_filename_falls_back_to_full_stem_for_title(
    sample_site: Path, tmp_path: Path
) -> None:
    source = tmp_path / "2024-01-15.md"
    source.write_text("Body only.\n", encoding="utf-8")

    result = import_note(sample_site, source, today=TODAY)

    meta = _read_front_matter(result.path)
    assert meta["date"] == "2024-01-15"


def test_invalid_calendar_date_in_filename_falls_through_to_mtime(
    sample_site: Path, tmp_path: Path
) -> None:
    source = tmp_path / "2024-13-45-post.md"
    source.write_text("Body.\n", encoding="utf-8")
    _set_mtime(source, "2019-05-05")

    result = import_note(sample_site, source, today=TODAY)

    # No valid date to strip, so the destination keeps the full name.
    assert result.path == sample_site / "content" / "posts" / "2024-13-45-post.md"
    meta = _read_front_matter(result.path)
    assert meta["date"] == "2019-05-05"


def test_mtime_fallback_when_no_date_available(sample_site: Path, tmp_path: Path) -> None:
    source = tmp_path / "undated-post.md"
    source.write_text("Body.\n", encoding="utf-8")
    _set_mtime(source, "2018-11-20")

    result = import_note(sample_site, source, today=TODAY)

    meta = _read_front_matter(result.path)
    assert meta["date"] == "2018-11-20"


def test_existing_front_matter_date_wins_over_filename_and_mtime(
    sample_site: Path, tmp_path: Path
) -> None:
    source = tmp_path / "2024-01-15-post.md"
    source.write_text("---\ndate: '2020-06-01'\n---\n\nBody.\n", encoding="utf-8")
    _set_mtime(source, "2019-01-01")

    result = import_note(sample_site, source, today=TODAY)

    # The filename's date prefix is still stripped from the destination
    # name even though front matter supplied a different date.
    assert result.path == sample_site / "content" / "posts" / "post.md"
    meta = _read_front_matter(result.path)
    assert meta["date"] == "2020-06-01"


def test_directory_import_copies_bundle_with_assets_and_subdirectories(
    sample_site: Path, tmp_path: Path
) -> None:
    bundle = tmp_path / "my-post"
    bundle.mkdir()
    (bundle / "my-post.md").write_text("Body.\n", encoding="utf-8")
    (bundle / "photo.jpg").write_bytes(b"fake-image-bytes")
    nested = bundle / "assets"
    nested.mkdir()
    (nested / "diagram.png").write_bytes(b"fake-diagram-bytes")

    result = import_note(sample_site, bundle, today=TODAY)

    dest_dir = sample_site / "content" / "posts" / "my-post"
    assert result.path == dest_dir / "my-post.md"
    assert (dest_dir / "photo.jpg").read_bytes() == b"fake-image-bytes"
    assert (dest_dir / "assets" / "diagram.png").read_bytes() == b"fake-diagram-bytes"
    meta = _read_front_matter(result.path)
    assert meta["title"] == "My Post"
    assert meta["slug"] == "my-post"


def test_directory_import_leaves_sibling_md_files_byte_for_byte(
    sample_site: Path, tmp_path: Path
) -> None:
    bundle = tmp_path / "my-post"
    bundle.mkdir()
    (bundle / "my-post.md").write_text("Body.\n", encoding="utf-8")
    sibling_content = "Just some draft notes, not front matter at all.\n"
    (bundle / "draft-notes.md").write_text(sibling_content, encoding="utf-8")

    result = import_note(sample_site, bundle, today=TODAY)

    assert (result.path.parent / "draft-notes.md").read_text(encoding="utf-8") == sibling_content


def test_directory_import_normalizes_main_file_name_to_match_directory(
    sample_site: Path, tmp_path: Path
) -> None:
    # A directory with a single `.md` file accepts any name for it, but
    # import renames it to match the (date-stripped) directory name
    # anyway, so a later `loom site build`/`validate` can still find it
    # unambiguously if a sibling `.md` file is ever added.
    bundle = tmp_path / "2024-01-15-my-post"
    bundle.mkdir()
    (bundle / "notes.md").write_text("Body.\n", encoding="utf-8")

    result = import_note(sample_site, bundle, today=TODAY)

    dest_dir = sample_site / "content" / "posts" / "my-post"
    assert result.path == dest_dir / "my-post.md"
    assert not (dest_dir / "notes.md").exists()
    meta = _read_front_matter(result.path)
    assert meta["date"] == "2024-01-15"
    assert meta["title"] == "My Post"
    assert meta["slug"] == "my-post"


def test_imported_bundle_with_dated_name_stays_resolvable_by_site_build(
    sample_site: Path, tmp_path: Path
) -> None:
    # Regression test: the source directory's main file is named after
    # its *original* (dated) directory name, and there's a sibling `.md`
    # file too -- exactly the shape that would otherwise make the bundle
    # ambiguous to `loom site build`/`validate` after import, since they
    # apply the same "matches the directory name" rule to find it again.
    bundle = tmp_path / "2024-02-20-trip-report"
    bundle.mkdir()
    (bundle / "2024-02-20-trip-report.md").write_text("Body.\n", encoding="utf-8")
    (bundle / "notes.md").write_text("stray notes\n", encoding="utf-8")

    result = import_note(sample_site, bundle, today=TODAY)

    dest_dir = sample_site / "content" / "posts" / "trip-report"
    assert result.path == dest_dir / "trip-report.md"
    resolved = _resolve_post_directory(dest_dir)
    assert resolved.md_path == result.path


def test_directory_import_ambiguous_raises(sample_site: Path, tmp_path: Path) -> None:
    bundle = tmp_path / "my-post"
    bundle.mkdir()
    (bundle / "one.md").write_text("Body.\n", encoding="utf-8")
    (bundle / "two.md").write_text("Body.\n", encoding="utf-8")

    with pytest.raises(NoteError, match="multiple Markdown files found"):
        import_note(sample_site, bundle, today=TODAY)


def test_directory_import_no_md_file_raises(sample_site: Path, tmp_path: Path) -> None:
    bundle = tmp_path / "empty-post"
    bundle.mkdir()
    (bundle / "notes.txt").write_text("not markdown", encoding="utf-8")

    with pytest.raises(NoteError, match="contains no Markdown file"):
        import_note(sample_site, bundle, today=TODAY)


def test_destination_file_already_exists_raises(sample_site: Path, tmp_path: Path) -> None:
    # sample_site already ships content/posts/hello-world.md.
    source = tmp_path / "hello-world.md"
    source.write_text("A different post.\n", encoding="utf-8")
    original = (sample_site / "content" / "posts" / "hello-world.md").read_text(encoding="utf-8")

    with pytest.raises(NoteError, match="already exists"):
        import_note(sample_site, source, today=TODAY)

    assert (sample_site / "content" / "posts" / "hello-world.md").read_text(
        encoding="utf-8"
    ) == original


def test_destination_directory_already_exists_raises(sample_site: Path, tmp_path: Path) -> None:
    existing = sample_site / "content" / "posts" / "my-post"
    existing.mkdir()
    (existing / "my-post.md").write_text("Already here.\n", encoding="utf-8")

    bundle = tmp_path / "my-post"
    bundle.mkdir()
    (bundle / "my-post.md").write_text("New content.\n", encoding="utf-8")

    with pytest.raises(NoteError, match="already exists"):
        import_note(sample_site, bundle, today=TODAY)


def test_non_site_target_raises_config_error(tmp_path: Path) -> None:
    source = tmp_path / "post.md"
    source.write_text("Body.\n", encoding="utf-8")

    with pytest.raises(ConfigError):
        import_note(tmp_path, source, today=TODAY)


def test_source_does_not_exist_raises(sample_site: Path, tmp_path: Path) -> None:
    with pytest.raises(NoteError, match="does not exist"):
        import_note(sample_site, tmp_path / "missing.md", today=TODAY)


def test_source_not_markdown_file_raises(sample_site: Path, tmp_path: Path) -> None:
    source = tmp_path / "post.txt"
    source.write_text("Body.\n", encoding="utf-8")

    with pytest.raises(NoteError, match="not a Markdown file"):
        import_note(sample_site, source, today=TODAY)


def test_malformed_front_matter_raises_content_error(sample_site: Path, tmp_path: Path) -> None:
    source = tmp_path / "broken.md"
    source.write_text("---\ntitle: [unclosed\n\nBody.\n", encoding="utf-8")

    with pytest.raises(ContentError):
        import_note(sample_site, source, today=TODAY)


def test_reports_validation_errors_but_keeps_the_file(sample_site: Path, tmp_path: Path) -> None:
    # sample_site already has content/posts/hello-world.md with slug
    # "hello-world"; "hello world" titleizes/slugifies to the same slug
    # without colliding on filename.
    source = tmp_path / "hello world.md"
    source.write_text("Body.\n", encoding="utf-8")

    result = import_note(sample_site, source, today=TODAY)

    assert result.path.is_file()
    assert any("hello-world" in error for error in result.validation_errors)
