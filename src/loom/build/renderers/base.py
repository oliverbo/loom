"""The `Renderer` protocol.

Every output format Loom produces (HTML pages, RSS today; search index,
ActivityPub actor/outbox, newsletter export, social post drafts later) is
a `Renderer`. `build/pipeline.py` only knows this interface, so adding a
new output format never requires touching the pipeline itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from loom.models import Site


class Renderer(Protocol):
    """Something that writes output files for a `Site` into `output_dir`."""

    def render(self, site: Site, output_dir: Path) -> None: ...
