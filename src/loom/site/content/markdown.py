"""Markdown -> HTML rendering.

Isolated behind this function so the rest of Loom depends on "render this
Markdown string" rather than on writer_md/markdown-it-py directly;
swapping the Markdown engine later only touches this file.
"""

from __future__ import annotations

from writer_md import create_renderer, render

_renderer = create_renderer()

EXCERPT_MARKER = "<!--more-->"


def render_markdown(text: str) -> str:
    return render(text, renderer=_renderer)


def excerpt_markdown(text: str) -> str:
    """Markdown for a post's excerpt.

    Everything before an explicit `<!--more-->` marker, or the first
    paragraph if the body has no marker.
    """
    if EXCERPT_MARKER in text:
        return text.split(EXCERPT_MARKER, 1)[0].rstrip()
    return text.strip().split("\n\n", 1)[0]
