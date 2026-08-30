"""Deriving slugs and titles from a bare name.

Shared by `loom.note` (`--site` front matter prepopulation) and available
to `loom.site` for the same purpose in the future.
"""

from __future__ import annotations

import re

_NON_SLUG_CHARS = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Lowercase `text` and collapse runs of non-alphanumerics into `-`.

    Does not guarantee a non-empty result -- a name made entirely of
    punctuation slugifies to `""`, which callers should let downstream
    validation (e.g. `loom.site.validation.validate_site`) catch rather
    than special-casing here.
    """
    slug = _NON_SLUG_CHARS.sub("-", text.lower()).strip("-")
    return slug


def titleize(name: str) -> str:
    """Turn a kebab/snake-case name like `new-post` into `New Post`."""
    return name.replace("-", " ").replace("_", " ").title()
