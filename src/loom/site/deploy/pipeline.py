"""Orchestrates an incremental deploy: delta -> upload -> delete -> save manifest.

Mirrors how `loom.site.build.pipeline` separates orchestration from the CLI
-- `loom.site.cli` handles flags and printing, this module does the work.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loom.site.deploy.backend import DeploymentBackend
from loom.site.deploy.delta import DeploymentDelta, compute_delta
from loom.site.deploy.manifest import DeploymentManifest


@dataclass(frozen=True)
class DeploymentResult:
    delta: DeploymentDelta
    commit: str | None
    dirty: bool
    dry_run: bool


def run_deployment(
    build_dir: Path,
    backend: DeploymentBackend,
    new_manifest: DeploymentManifest,
    *,
    dry_run: bool,
) -> DeploymentResult:
    """Ship `new_manifest`'s changes (relative to the backend's stored manifest).

    The backend's stored manifest is only overwritten after every upload and
    deletion succeeds -- if `upload_file`/`delete_file` raises partway
    through, `save_manifest` is never reached, so the previous manifest
    remains authoritative. Performs no backend writes at all when
    `dry_run` is set.
    """
    previous = backend.load_manifest()
    delta = compute_delta(previous, new_manifest)

    if not dry_run:
        for relative_path in (*delta.added, *delta.modified):
            backend.upload_file(relative_path, build_dir / relative_path)
        for relative_path in delta.deleted:
            backend.delete_file(relative_path)
        backend.save_manifest(new_manifest)

    return DeploymentResult(
        delta=delta,
        commit=new_manifest.source.commit,
        dirty=new_manifest.source.dirty,
        dry_run=dry_run,
    )
