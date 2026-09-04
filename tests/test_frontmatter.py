from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from loom.errors import ContentError
from loom.site.content.frontmatter import parse_document, split_frontmatter


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "post.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_split_frontmatter_returns_metadata_and_body(tmp_path: Path) -> None:
    path = write(tmp_path, "---\ntitle: Hi\n---\nBody text.\n")
    meta, body = split_frontmatter(path.read_text(), source=path)
    assert meta == {"title": "Hi"}
    assert body == "Body text.\n"


def test_split_frontmatter_requires_leading_fence(tmp_path: Path) -> None:
    path = write(tmp_path, "title: Hi\n---\nBody\n")
    with pytest.raises(ContentError, match="missing YAML front matter"):
        split_frontmatter(path.read_text(), source=path)


def test_split_frontmatter_requires_closing_fence(tmp_path: Path) -> None:
    path = write(tmp_path, "---\ntitle: Hi\nBody\n")
    with pytest.raises(ContentError, match="never closed"):
        split_frontmatter(path.read_text(), source=path)


def test_split_frontmatter_rejects_non_mapping(tmp_path: Path) -> None:
    path = write(tmp_path, "---\n- a\n- b\n---\nBody\n")
    with pytest.raises(ContentError, match="must be a mapping"):
        split_frontmatter(path.read_text(), source=path)


def test_parse_document_builds_document(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\ntags: [a, b]\n---\nBody\n",
    )
    doc = parse_document(path)
    assert doc.title == "Hi"
    assert doc.date == date(2026, 1, 2)
    assert doc.slug == "hi"
    assert doc.tags == ["a", "b"]
    assert doc.draft is False
    assert doc.body_markdown == "Body"


def test_parse_document_requires_required_fields(tmp_path: Path) -> None:
    path = write(tmp_path, "---\ntitle: Hi\n---\nBody\n")
    with pytest.raises(ContentError, match="missing required front matter"):
        parse_document(path)


def test_parse_document_preserves_unknown_fields_in_extra(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\nsummary: A teaser.\n---\nBody\n",
    )
    doc = parse_document(path)
    assert doc.extra == {"summary": "A teaser."}


def test_parse_document_rejects_bad_date(tmp_path: Path) -> None:
    path = write(tmp_path, "---\ntitle: Hi\ndate: not-a-date\nslug: hi\n---\nBody\n")
    with pytest.raises(ContentError, match="not a valid ISO date"):
        parse_document(path)


def test_parse_document_substitutes_front_matter_variables(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\nWritten by [%author].\n",
    )
    doc = parse_document(path)
    assert doc.body_markdown == "Written by [%author]."

    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\nauthor: Ada\n---\nWritten by [%author].\n",
    )
    doc = parse_document(path)
    assert doc.body_markdown == "Written by Ada."


def test_parse_document_expands_bare_content_block(tmp_path: Path) -> None:
    (tmp_path / "scores.csv").write_text("Name,Score\nAda,10\n", encoding="utf-8")
    path = write(tmp_path, "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\nscores.csv\n")
    doc = parse_document(path)
    assert "| Name | Score |" in doc.body_markdown
    assert "| Ada | 10 |" in doc.body_markdown


def test_parse_document_strips_trailing_annotations_block(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\n"
        "Body text.\n\n---\n"
        "Annotations: 0,4 SHA-256 ABCDEF0123456789ABCDEF0123456789\n"
        "@Someone: 0,4\n...\n",
    )
    doc = parse_document(path)
    assert doc.body_markdown == "Body text.\n"
    assert "SHA-256" not in doc.body_markdown


def test_parse_document_content_block_confined_to_asset_dir(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "my-bundle"
    bundle_dir.mkdir()
    outside = tmp_path / "outside.csv"
    outside.write_text("a,b\n1,2\n", encoding="utf-8")
    path = bundle_dir / "my-bundle.md"
    path.write_text(
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\n/../outside.csv\n",
        encoding="utf-8",
    )
    with pytest.raises(ContentError, match="escapes the document folder"):
        parse_document(path, asset_dir=bundle_dir)


def test_parse_document_leaves_unresolvable_image_reference_untouched(tmp_path: Path) -> None:
    """A post referencing an image that lives in the site-wide images/ dir
    rather than its own folder must keep working -- see
    `_check_images` in `loom.site.validation`, which allows that fallback.
    """
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\n![shared](shared.png)\n",
    )
    doc = parse_document(path)
    assert doc.body_markdown == "![shared](shared.png)"
