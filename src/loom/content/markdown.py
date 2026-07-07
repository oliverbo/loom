"""Markdown -> HTML rendering.

Isolated behind this function so the rest of Loom depends on "render this
Markdown string" rather than on markdown-it-py directly; swapping the
Markdown engine later only touches this file.
"""

from __future__ import annotations

from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark").enable("table")


def render_markdown(text: str) -> str:
    return _md.render(text)
