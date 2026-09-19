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
    result = runner.invoke(app, ["note", "add", "new-post", str(tmp_path), "-f", "draft=nonsense"])

    assert result.exit_code == 1
    assert "draft" in result.output
    assert not (tmp_path / "new-post.md").exists()


def test_add_trims_comma_separated_tags(tmp_path: Path) -> None:
    result = runner.invoke(app, ["note", "add", "new-post", str(tmp_path), "-f", "tags=foo, bar"])

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


def test_import_happy_path(tmp_path: Path) -> None:
    site = tmp_path / "site"
    init_result = runner.invoke(app, ["site", "init", str(site)])
    assert init_result.exit_code == 0, init_result.output

    source = tmp_path / "old-post.md"
    source.write_text("---\ntitle: Old Post\n---\n\nBody.\n", encoding="utf-8")

    result = runner.invoke(app, ["note", "import", str(source), str(site)])

    assert result.exit_code == 0, result.output
    assert "Imported" in result.output
    assert (site / "content" / "posts" / "old-post.md").is_file()


def test_import_rejects_missing_source(tmp_path: Path) -> None:
    site = tmp_path / "site"
    init_result = runner.invoke(app, ["site", "init", str(site)])
    assert init_result.exit_code == 0, init_result.output

    result = runner.invoke(app, ["note", "import", str(tmp_path / "missing.md"), str(site)])

    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_import_directory_bundle(tmp_path: Path) -> None:
    site = tmp_path / "site"
    init_result = runner.invoke(app, ["site", "init", str(site)])
    assert init_result.exit_code == 0, init_result.output

    bundle = tmp_path / "my-post"
    bundle.mkdir()
    (bundle / "my-post.md").write_text("Body.\n", encoding="utf-8")
    (bundle / "photo.jpg").write_bytes(b"fake-image-bytes")

    result = runner.invoke(app, ["note", "import", str(bundle), str(site)])

    assert result.exit_code == 0, result.output
    dest_dir = site / "content" / "posts" / "my-post"
    assert (dest_dir / "my-post.md").is_file()
    assert (dest_dir / "photo.jpg").read_bytes() == b"fake-image-bytes"


def test_import_reports_validation_errors_but_keeps_file(sample_site: Path, tmp_path: Path) -> None:
    # sample_site already has content/posts/hello-world.md with slug
    # "hello-world"; "hello world" titleizes/slugifies to the same slug.
    source = tmp_path / "hello world.md"
    source.write_text("Body.\n", encoding="utf-8")

    result = runner.invoke(app, ["note", "import", str(source), str(sample_site)])

    assert result.exit_code == 1
    assert (sample_site / "content" / "posts" / "hello world.md").is_file()


def test_import_requires_site(tmp_path: Path) -> None:
    source = tmp_path / "post.md"
    source.write_text("Body.\n", encoding="utf-8")

    result = runner.invoke(app, ["note", "import", str(source), str(tmp_path)])

    assert result.exit_code == 1
    assert "loom.toml" in result.output
