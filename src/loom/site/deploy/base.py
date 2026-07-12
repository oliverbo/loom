"""The `DeployTarget` protocol every deploy backend implements."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from loom.site.config import DeployConfig


class DeployTarget(Protocol):
    def __init__(self, config: DeployConfig) -> None: ...

    def deploy(self, build_dir: Path) -> None:
        """Ship the contents of `build_dir` to the configured destination.

        Raises `loom.errors.DeployError` on failure.
        """
        ...
