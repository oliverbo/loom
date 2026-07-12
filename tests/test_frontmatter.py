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
    assert doc.body_markdown == "Body\n"


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
