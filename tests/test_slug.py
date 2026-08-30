from __future__ import annotations

from loom.slug import slugify, titleize


def test_slugify_lowercases_and_hyphenates() -> None:
    assert slugify("New Post") == "new-post"


def test_slugify_collapses_punctuation_runs() -> None:
    assert slugify("Hello, World!!") == "hello-world"


def test_slugify_strips_leading_and_trailing_hyphens() -> None:
    assert slugify("  --hello--  ") == "hello"


def test_slugify_all_punctuation_is_empty() -> None:
    assert slugify("!!!") == ""


def test_slugify_preserves_existing_hyphens() -> None:
    assert slugify("already-a-slug") == "already-a-slug"


def test_titleize_kebab_case() -> None:
    assert titleize("new-post") == "New Post"


def test_titleize_snake_case() -> None:
    assert titleize("new_post") == "New Post"
