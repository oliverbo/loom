from __future__ import annotations

from datetime import date
from pathlib import Path

from loom.models import Document


def make_document(**overrides) -> Document:
    defaults = dict(
        slug="my-post",
        title="My Post",
        date=date(2026, 1, 1),
        tags=[],
        draft=False,
        source_path=Path("my-post.md"),
        body_markdown="Body",
    )
    defaults.update(overrides)
    return Document(**defaults)


def test_valid_slug_accepted() -> None:
    assert make_document(slug="my-first-post").is_slug_valid()


def test_slug_with_uppercase_rejected() -> None:
    assert not make_document(slug="My-Post").is_slug_valid()


def test_slug_with_underscore_rejected() -> None:
    assert not make_document(slug="my_post").is_slug_valid()


def test_slug_with_leading_hyphen_rejected() -> None:
    assert not make_document(slug="-my-post").is_slug_valid()
