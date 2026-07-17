"""The `DeploymentBackend` protocol every manifest-aware deploy backend implements.

Distinct from `loom.site.deploy.base.DeployTarget`: a `DeployTarget` ships
the whole build directory every time (used by the `git` and `rsync`
targets, which already do their own efficient full-tree sync). A
`DeploymentBackend` exposes per-file operations so `loom.site.deploy.pipeline`
can upload/delete only what changed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from loom.site.deploy.manifest import DeploymentManifest


class DeploymentBackend(Protocol):
    def load_manifest(self) -> DeploymentManifest | None:
        """Return the manifest stored from the last successful deployment, if any."""
        ...

    def upload_file(self, relative_path: str, source_path: Path) -> None:
        """Copy `source_path` to `relative_path` at the destination.

        Raises `loom.errors.DeployError` on failure.
        """
        ...

    def delete_file(self, relative_path: str) -> None:
        """Remove `relative_path` from the destination.

        Raises `loom.errors.DeployError` on failure.
        """
        ...

    def save_manifest(self, manifest: DeploymentManifest) -> None:
        """Store `manifest` as the new record of the last successful deployment."""
        ...
