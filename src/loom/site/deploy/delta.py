"""Comparing two deployment manifests to decide what a deploy must ship.

Pure and filesystem-free by design, so it's testable without a backend or
a build directory: given two manifests, what changed?
"""

from __future__ import annotations

from dataclasses import dataclass

from loom.site.deploy.manifest import DeploymentManifest


@dataclass(frozen=True)
class DeploymentDelta:
    added: tuple[str, ...]
    modified: tuple[str, ...]
    deleted: tuple[str, ...]
    unchanged: tuple[str, ...]


def compute_delta(
    previous: DeploymentManifest | None, new: DeploymentManifest
) -> DeploymentDelta:
    """Classify every path in `previous` and/or `new` by what changed.

    `previous=None` (no prior successful deployment) means every path in
    `new` is `added`.
    """
    previous_files = previous.files if previous is not None else {}

    added: list[str] = []
    modified: list[str] = []
    unchanged: list[str] = []
    for path, entry in new.files.items():
        if path not in previous_files:
            added.append(path)
        elif previous_files[path].sha256 != entry.sha256:
            modified.append(path)
        else:
            unchanged.append(path)

    deleted = [path for path in previous_files if path not in new.files]

    return DeploymentDelta(
        added=tuple(sorted(added)),
        modified=tuple(sorted(modified)),
        deleted=tuple(sorted(deleted)),
        unchanged=tuple(sorted(unchanged)),
    )
