"""Find content source files on disk."""

from __future__ import annotations

from pathlib import Path


def discover_posts(content_dir: Path) -> list[Path]:
    """Return all Markdown post source files, sorted for deterministic builds."""
    posts_dir = content_dir / "posts"
    if not posts_dir.is_dir():
        return []
    return sorted(posts_dir.glob("*.md"))
