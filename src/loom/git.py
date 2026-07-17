"""Git plumbing for source traceability.

Deployment manifests record which commit (and whether the tree was dirty)
produced a build, purely for traceability -- Loom never uses Git diffs to
decide what to deploy (see `loom.site.deploy.delta`). Best-effort: a site
need not live in a Git repo at all, so failures here are swallowed rather
than raised.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitInfo:
    commit: str | None
    dirty: bool


def get_git_info(root: Path) -> GitInfo:
    """Return the current commit and dirty-state of the repo containing `root`.

    Returns `GitInfo(commit=None, dirty=False)` if `root` isn't inside a Git
    repository or `git` isn't available -- Git is for traceability, not a
    hard requirement.
    """
    commit = _run(["git", "rev-parse", "HEAD"], cwd=root)
    if commit is None:
        return GitInfo(commit=None, dirty=False)

    status = _run(["git", "status", "--porcelain"], cwd=root)
    dirty = bool(status)

    return GitInfo(commit=commit, dirty=dirty)


def _run(command: list[str], *, cwd: Path) -> str | None:
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()
