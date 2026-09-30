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


def test_parse_document_strips_leading_title_heading(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\n# Hi\nBody text.\n",
    )
    doc = parse_document(path)
    assert doc.body_markdown == "Body text."


def test_parse_document_strips_bare_leading_hash(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\n#\nBody text.\n",
    )
    doc = parse_document(path)
    assert doc.body_markdown == "Body text."


def test_parse_document_keeps_leading_subheading(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\n## Not the title\nBody text.\n",
    )
    doc = parse_document(path)
    assert doc.body_markdown == "## Not the title\nBody text."


def test_parse_document_strips_leading_title_heading_after_blank_lines(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\n\n\n# Hi\nBody text.\n",
    )
    doc = parse_document(path)
    assert doc.body_markdown == "Body text."


def test_parse_document_leaves_unresolvable_image_reference_untouched(tmp_path: Path) -> None:
    """A post referencing an image that lives in the site-wide images/ dir
    rather than its own folder must keep working -- see
    `_check_images` in `loom.site.validation`, which allows that fallback.

    The image sits in its own paragraph after some text so it isn't
    mistaken for a featured photo (see the `featured_photo` tests below).
    """
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\n"
        "Intro text.\n\n![shared](shared.png)\n",
    )
    doc = parse_document(path)
    assert doc.body_markdown == "Intro text.\n\n![shared](shared.png)"


def test_parse_document_extracts_featured_photo_below_title_heading(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\n"
        "# Hi\n\n![a sunset](sunset.jpg)\n\nBody text.\n",
    )
    doc = parse_document(path)
    assert doc.featured_photo is not None
    assert doc.featured_photo.src == "sunset.jpg"
    assert doc.featured_photo.alt == "a sunset"
    assert doc.featured_photo.caption == ""
    assert doc.body_markdown == "Body text."


def test_parse_document_extracts_featured_photo_with_no_title_heading(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\n![a sunset](sunset.jpg)\n\nBody text.\n",
    )
    doc = parse_document(path)
    assert doc.featured_photo is not None
    assert doc.featured_photo.src == "sunset.jpg"
    assert doc.body_markdown == "Body text."


def test_parse_document_extracts_featured_photo_from_bare_content_block(tmp_path: Path) -> None:
    (tmp_path / "sunset.jpg").write_bytes(b"fake-jpeg")
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\nsunset.jpg\n\nBody text.\n",
    )
    doc = parse_document(path)
    assert doc.featured_photo is not None
    assert doc.featured_photo.src == "sunset.jpg"
    assert doc.body_markdown == "Body text."


def test_parse_document_featured_photo_keeps_content_block_caption(tmp_path: Path) -> None:
    (tmp_path / "sunset.jpg").write_bytes(b"fake-jpeg")
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\n"
        'sunset.jpg "A lovely evening"\n\nBody text.\n',
    )
    doc = parse_document(path)
    assert doc.featured_photo is not None
    assert doc.featured_photo.src == "sunset.jpg"
    assert doc.featured_photo.alt == "A lovely evening"
    assert doc.featured_photo.caption == "A lovely evening"
    assert doc.body_markdown == "Body text."


def test_parse_document_featured_photo_unwraps_bracketed_destination(tmp_path: Path) -> None:
    """A destination wrapped in `<...>` (how a content block renders a
    path containing spaces) must resolve to the plain path, not the
    literal `<...>` text.
    """
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\n"
        "![a sunset](<my sunset.jpg>)\n\nBody text.\n",
    )
    doc = parse_document(path)
    assert doc.featured_photo is not None
    assert doc.featured_photo.src == "my sunset.jpg"


def test_parse_document_featured_photo_disabled_by_front_matter(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\nfeatured_photo: false\n---\n"
        "![a sunset](sunset.jpg)\n\nBody text.\n",
    )
    doc = parse_document(path)
    assert doc.featured_photo is None
    assert doc.body_markdown == "![a sunset](sunset.jpg)\n\nBody text."
    assert "featured_photo" not in doc.extra


def test_parse_document_rejects_non_bool_featured_photo(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\nfeatured_photo: not-a-bool\n---\nBody\n",
    )
    with pytest.raises(ContentError, match="'featured_photo' must be true or false"):
        parse_document(path)


def test_parse_document_no_featured_photo_when_first_paragraph_has_other_text(
    tmp_path: Path,
) -> None:
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\n"
        "![a sunset](sunset.jpg) and some words.\n\nBody text.\n",
    )
    doc = parse_document(path)
    assert doc.featured_photo is None
    assert doc.body_markdown == "![a sunset](sunset.jpg) and some words.\n\nBody text."


def test_parse_document_no_featured_photo_when_image_is_not_first_paragraph(
    tmp_path: Path,
) -> None:
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\n"
        "Intro text.\n\n![a sunset](sunset.jpg)\n",
    )
    doc = parse_document(path)
    assert doc.featured_photo is None
    assert doc.body_markdown == "Intro text.\n\n![a sunset](sunset.jpg)"


def test_parse_document_featured_photo_can_be_the_whole_body(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "---\ntitle: Hi\ndate: 2026-01-02\nslug: hi\n---\n![a sunset](sunset.jpg)\n",
    )
    doc = parse_document(path)
    assert doc.featured_photo is not None
    assert doc.body_markdown == ""
