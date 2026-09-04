from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from loom.cli import app
from loom.site.content.frontmatter import split_frontmatter

runner = CliRunner()


def test_add_happy_path(tmp_path: Path) -> None:
    result = runner.invoke(app, ["note", "add", "new-post", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Created" in result.output
    assert (tmp_path / "new-post.md").is_file()


def test_add_rejects_invalid_draft_field(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["note", "add", "new-post", str(tmp_path), "-f", "draft=nonsense"]
    )

    assert result.exit_code == 1
    assert "draft" in result.output
    assert not (tmp_path / "new-post.md").exists()


def test_add_trims_comma_separated_tags(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["note", "add", "new-post", str(tmp_path), "-f", "tags=foo, bar"]
    )

    assert result.exit_code == 0, result.output
    path = tmp_path / "new-post.md"
    meta, _ = split_frontmatter(path.read_text(encoding="utf-8"), source=path)
    assert meta["tags"] == ["foo", "bar"]


def test_add_site_happy_path(tmp_path: Path) -> None:
    site = tmp_path / "site"
    init_result = runner.invoke(app, ["site", "init", str(site)])
    assert init_result.exit_code == 0, init_result.output

    result = runner.invoke(app, ["note", "add", "second-post", str(site), "--site"])

    assert result.exit_code == 0, result.output
    assert (site / "content" / "posts" / "second-post.md").is_file()


def test_add_site_duplicate_slug_fails_but_keeps_file(sample_site: Path) -> None:
    result = runner.invoke(app, ["note", "add", "hello world", str(sample_site), "--site"])

    assert result.exit_code == 1
    assert (sample_site / "content" / "posts" / "hello world.md").is_file()
