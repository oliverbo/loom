"""Git-based deploy target: commit `build/` output to a branch and push.

Works for GitHub Pages, GitLab Pages, and similar hosts without needing
a hosting-provider API or SDK -- just `git`.

Example `loom.toml`:

    [deploy]
    target = "git"
    remote = "git@github.com:me/me.github.io.git"
    branch = "gh-pages"
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from loom.config import DeployConfig
from loom.errors import DeployError

DEFAULT_BRANCH = "gh-pages"


class GitDeployTarget:
    def __init__(self, config: DeployConfig) -> None:
        extra = config.model_extra or {}
        remote = extra.get("remote")
        if not remote:
            raise DeployError("git deploy target requires a 'remote' in [deploy]")
        self.remote: str = remote
        self.branch: str = extra.get("branch", DEFAULT_BRANCH)
        self.commit_message: str = extra.get("commit_message", "Deploy site")

    def deploy(self, build_dir: Path) -> None:
        self._run(["git", "init"], cwd=build_dir)
        self._run(["git", "checkout", "-B", self.branch], cwd=build_dir)
        self._run(["git", "add", "-A"], cwd=build_dir)
        # Nothing to commit is not a failure -- the site may be unchanged.
        commit = subprocess.run(
            ["git", "commit", "-m", self.commit_message],
            cwd=build_dir,
            capture_output=True,
            text=True,
        )
        if commit.returncode != 0 and "nothing to commit" not in commit.stdout.lower():
            raise DeployError(f"git commit failed:\n{commit.stderr}")

        # build_dir is re-initialized as a fresh repo every deploy, so its
        # history never relates to the remote's -- force is required.
        self._run(
            ["git", "push", "--force", self.remote, f"HEAD:{self.branch}"],
            cwd=build_dir,
        )

    def _run(self, command: list[str], *, cwd: Path) -> None:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            raise DeployError(f"{' '.join(command)} failed:\n{result.stderr}")
