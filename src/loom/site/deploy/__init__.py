"""Deploy targets.

Selected by name via `loom.toml`'s `[deploy] target = "..."` key. There are
two families:

- `TARGETS` -- `DeployTarget` (see `base.py`), a full "ship everything"
  sync every deploy. Used by `git` and `rsync`, which already do their own
  efficient full-tree sync natively.
- `INCREMENTAL_BACKENDS` -- `DeploymentBackend` (see `backend.py`), which
  exposes per-file upload/delete so `loom.site.deploy.pipeline` can ship
  only what changed since the last successful deployment, per the manifest
  in `loom.site.deploy.manifest`.

`loom site deploy` looks the configured target name up in whichever
registry has it.
"""

from __future__ import annotations

from loom.site.deploy.backend import DeploymentBackend
from loom.site.deploy.base import DeployTarget
from loom.site.deploy.directory_backend import DirectoryDeploymentBackend
from loom.site.deploy.gcs_backend import GcsDeploymentBackend
from loom.site.deploy.git_target import GitDeployTarget
from loom.site.deploy.rsync_target import RsyncDeployTarget

TARGETS: dict[str, type[DeployTarget]] = {
    "rsync": RsyncDeployTarget,
    "git": GitDeployTarget,
}

INCREMENTAL_BACKENDS: dict[str, type[DeploymentBackend]] = {
    "directory": DirectoryDeploymentBackend,
    "gcs": GcsDeploymentBackend,
}
