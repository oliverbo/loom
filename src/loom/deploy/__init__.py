"""Deploy targets.

Each target implements `DeployTarget` (see `base.py`) and is selected by
name via `loom.toml`'s `[deploy] target = "..."` key. `TARGETS` is the
registry `loom deploy` looks up the configured target in.
"""

from __future__ import annotations

from loom.deploy.base import DeployTarget
from loom.deploy.git_target import GitDeployTarget
from loom.deploy.rsync_target import RsyncDeployTarget

TARGETS: dict[str, type[DeployTarget]] = {
    "rsync": RsyncDeployTarget,
    "git": GitDeployTarget,
}
