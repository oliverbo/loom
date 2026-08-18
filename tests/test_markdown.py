from __future__ import annotations

from loom.site.content.markdown import excerpt_markdown


def test_excerpt_uses_more_marker_when_present() -> None:
    body = "Teaser paragraph.\n\n<!--more-->\n\nRest of the post."
    assert excerpt_markdown(body) == "Teaser paragraph."


def test_excerpt_falls_back_to_first_paragraph() -> None:
    body = "First paragraph.\n\nSecond paragraph."
    assert excerpt_markdown(body) == "First paragraph."


def test_excerpt_of_single_paragraph_post_is_the_whole_body() -> None:
    body = "Only paragraph."
    assert excerpt_markdown(body) == "Only paragraph."
