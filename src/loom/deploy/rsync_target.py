"""File-sync deploy target: `rsync` over SSH.

Chosen as the v1 file-sync target because it needs no cloud SDK or
credentials beyond SSH access, and works against any VPS or shared host.

Example `loom.toml`:

    [deploy]
    target = "rsync"
    destination = "user@example.com:/var/www/blog"
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from loom.config import DeployConfig
from loom.errors import DeployError


class RsyncDeployTarget:
    def __init__(self, config: DeployConfig) -> None:
        destination = config.model_extra.get("destination") if config.model_extra else None
        if not destination:
            raise DeployError("rsync deploy target requires a 'destination' in [deploy]")
        self.destination: str = destination

    def deploy(self, build_dir: Path) -> None:
        if shutil.which("rsync") is None:
            raise DeployError("'rsync' was not found on PATH")

        # Trailing slash on the source means "copy contents of build_dir",
        # not "copy build_dir itself" -- required for the destination
        # layout to match what preview/build produce locally.
        source = f"{build_dir}/"
        command = ["rsync", "-avz", "--delete", source, self.destination]

        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise DeployError(f"rsync failed:\n{result.stderr}")
