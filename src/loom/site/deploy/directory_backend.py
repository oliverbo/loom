"""Local-directory deployment backend.

Copies build output directly into a destination directory on the local
filesystem (or anything reachable as one, e.g. a mounted network share).
The first concrete `DeploymentBackend` -- a dependency-free way to develop
and test the incremental deploy model before adding cloud storage or SFTP
backends.

Example `loom.toml`:

    [deploy]
    target = "directory"
    destination = "../deployed-site"
"""

from __future__ import annotations

import shutil
from pathlib import Path

from loom.errors import DeployError
from loom.site.config import DeployConfig
from loom.site.deploy.manifest import (
    MANIFEST_FILENAME,
    DeploymentManifest,
    read_manifest,
    validate_relative_path,
    write_manifest,
)


class DirectoryDeploymentBackend:
    def __init__(self, config: DeployConfig, site_root: Path) -> None:
        extra = config.model_extra or {}
        destination = extra.get("destination")
        if not destination:
            raise DeployError("directory deploy target requires a 'destination' in [deploy]")
        self.destination: Path = (site_root / destination).resolve()

    def load_manifest(self) -> DeploymentManifest | None:
        return read_manifest(self.destination / MANIFEST_FILENAME)

    def upload_file(self, relative_path: str, source_path: Path) -> None:
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(source_path, target)
        except OSError as exc:
            raise DeployError(f"failed to copy {relative_path!r} to {target}: {exc}") from exc

    def delete_file(self, relative_path: str) -> None:
        target = self._resolve(relative_path)
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            raise DeployError(f"failed to delete {relative_path!r} at {target}: {exc}") from exc
        self._prune_empty_parents(target.parent)

    def save_manifest(self, manifest: DeploymentManifest) -> None:
        write_manifest(self.destination / MANIFEST_FILENAME, manifest)

    def _resolve(self, relative_path: str) -> Path:
        validate_relative_path(relative_path)
        target = (self.destination / relative_path).resolve()
        if target != self.destination and self.destination not in target.parents:
            raise DeployError(f"manifest path escapes the deploy destination: {relative_path!r}")
        return target

    def _prune_empty_parents(self, directory: Path) -> None:
        """Remove now-empty parent directories left behind by a deletion.

        Walks upward from `directory`, removing it while it's empty, and
        stops at the first non-empty directory or at `self.destination`
        itself -- the destination root and directories holding files
        unrelated to this deploy are never removed.
        """
        while directory != self.destination:
            try:
                next(directory.iterdir())
            except StopIteration:
                directory.rmdir()
                directory = directory.parent
            except FileNotFoundError:
                directory = directory.parent
            else:
                return
