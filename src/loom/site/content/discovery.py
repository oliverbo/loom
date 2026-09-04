"""Find content source files on disk."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loom.errors import ContentError


@dataclass(frozen=True)
class PostSource:
    """One discovered post: its Markdown file, and where its assets live.

    `asset_dir` is `None` for a plain `posts/foo.md` file. For a post
    directory (`posts/foo/foo.md`), it's that directory -- the bundle's
    sibling images and other assets get copied alongside the post's output
    from there.
    """

    md_path: Path
    asset_dir: Path | None = None


def discover_posts(posts_dir: Path) -> list[PostSource]:
    """Return all posts under `posts_dir`, sorted for deterministic builds.

    A post is either a `.md` file directly in `posts_dir`, or a
    subdirectory of it (a "post directory") resolved to a single Markdown
    file by `_resolve_post_directory`. Dotfiles/dot-directories
    (`.DS_Store`, `.gitkeep`, ...) are ignored. A symlinked directory under
    `posts_dir` is treated as a post directory like any other (default
    `Path.is_dir()` behavior; not specially handled).

    Raises `ContentError` if a post directory can't be resolved to a
    single post file.
    """
    if not posts_dir.is_dir():
        return []

    sources: list[PostSource] = []
    for entry in sorted(posts_dir.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            sources.append(_resolve_post_directory(entry))
        elif entry.suffix == ".md":
            sources.append(PostSource(md_path=entry))
    return sources


def _resolve_post_directory(directory: Path) -> PostSource:
    """Pick the Markdown file a post directory's bundle is built from.

    A single `.md` file is used as-is. With more than one, the file named
    after the directory wins, so images and other assets can sit alongside
    it unambiguously. Anything else -- no match, or no Markdown file at
    all -- is an error rather than a silent guess.
    """
    md_files = sorted(p for p in directory.glob("*.md") if not p.name.startswith("."))

    if not md_files:
        raise ContentError(f"{directory}: post directory contains no Markdown file")

    if len(md_files) == 1:
        return PostSource(md_path=md_files[0], asset_dir=directory)

    named = directory / f"{directory.name}.md"
    if named in md_files:
        return PostSource(md_path=named, asset_dir=directory)

    found = ", ".join(p.name for p in md_files)
    raise ContentError(
        f"{directory}: multiple Markdown files found ({found}) and none is "
        f"named '{directory.name}.md' to disambiguate"
    )


def bundle_assets(source_path: Path, asset_dir: Path) -> list[Path]:
    """Sibling files in a post directory that should ship as static assets.

    Excludes the post's own Markdown file, every other `.md` file (drafts,
    notes -- not meant for output), and dotfiles.
    """
    return sorted(
        item
        for item in asset_dir.iterdir()
        if item != source_path and item.suffix != ".md" and not item.name.startswith(".")
    )
