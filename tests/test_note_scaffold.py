from __future__ import annotations

from pathlib import Path

import pytest

from loom.errors import ConfigError, NoteError
from loom.note.scaffold import add_note
from loom.site.content.frontmatter import split_frontmatter

TODAY = "2026-02-01"


def _read_front_matter(path: Path) -> dict:
    meta, _ = split_frontmatter(path.read_text(encoding="utf-8"), source=path)
    return meta


def _write_template(root: Path, name: str, content: str) -> Path:
    templates_dir = root / ".loom" / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    path = templates_dir / f"{name}.md"
    path.write_text(content, encoding="utf-8")
    return path


def test_bootstraps_default_template_in_fresh_directory(tmp_path: Path) -> None:
    result = add_note(tmp_path, "new-post", today=TODAY)

    assert (tmp_path / ".loom" / "templates" / "default.md").is_file()
    assert result.path == tmp_path / "new-post.md"
    assert result.path.is_file()


def test_named_template_is_used(tmp_path: Path) -> None:
    _write_template(tmp_path, "blog", "---\nmood: happy\n---\n\nBody.\n")

    result = add_note(tmp_path, "post-one", template="blog", today=TODAY)

    meta = _read_front_matter(result.path)
    assert meta == {"mood": "happy"}
    assert result.path.read_text(encoding="utf-8").endswith("Body.\n")


def test_directory_template_copies_sibling_assets(tmp_path: Path) -> None:
    template_dir = tmp_path / ".loom" / "templates" / "withimg"
    template_dir.mkdir(parents=True)
    (template_dir / "withimg.md").write_text("---\ntitle: X\n---\n\nBody.\n", encoding="utf-8")
    (template_dir / "photo.txt").write_text("asset", encoding="utf-8")

    result = add_note(tmp_path, "mynote", template="withimg", today=TODAY)

    assert result.path == tmp_path / "mynote" / "mynote.md"
    assert (tmp_path / "mynote" / "photo.txt").read_text(encoding="utf-8") == "asset"


def test_refuses_to_overwrite_existing_file(tmp_path: Path) -> None:
    add_note(tmp_path, "new-post", today=TODAY)

    with pytest.raises(NoteError, match="already exists"):
        add_note(tmp_path, "new-post", today=TODAY)


@pytest.mark.parametrize("name", ["../x", "a/b", "a\\b", ".", "..", ""])
def test_rejects_unsafe_names(tmp_path: Path, name: str) -> None:
    with pytest.raises(NoteError):
        add_note(tmp_path, name, today=TODAY)


def test_field_overrides_template_value(tmp_path: Path) -> None:
    _write_template(tmp_path, "default", "---\ntitle: Template Title\n---\n\nBody.\n")

    result = add_note(tmp_path, "post", fields={"title": "Custom Title"}, today=TODAY)

    assert _read_front_matter(result.path)["title"] == "Custom Title"


def test_unknown_template_raises(tmp_path: Path) -> None:
    with pytest.raises(NoteError, match="doesnotexist"):
        add_note(tmp_path, "post", template="doesnotexist", today=TODAY)


def test_site_fills_missing_front_matter(sample_site: Path) -> None:
    result = add_note(sample_site, "second-post", site=True, today=TODAY)

    assert result.path == sample_site / "content" / "posts" / "second-post.md"
    meta = _read_front_matter(result.path)
    assert meta["title"] == "Second Post"
    assert meta["slug"] == "second-post"
    assert meta["date"] == TODAY
    assert meta["draft"] is False
    assert meta["tags"] == []
    assert result.validation_errors == []


def test_site_leaves_explicit_title_alone_and_derives_slug_from_it(sample_site: Path) -> None:
    result = add_note(
        sample_site, "third-post", fields={"title": "Explicit Title"}, site=True, today=TODAY
    )

    meta = _read_front_matter(result.path)
    assert meta["title"] == "Explicit Title"
    assert meta["slug"] == "explicit-title"


def test_site_reports_duplicate_slug_but_keeps_the_file(sample_site: Path) -> None:
    # sample_site already has content/posts/hello-world.md with slug
    # "hello-world"; "hello world" titleizes/slugifies to the same slug
    # without colliding on filename.
    result = add_note(sample_site, "hello world", site=True, today=TODAY)

    assert result.path.is_file()
    assert any("hello-world" in error for error in result.validation_errors)


def test_site_requires_a_loom_site(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        add_note(tmp_path, "post", site=True, today=TODAY)
