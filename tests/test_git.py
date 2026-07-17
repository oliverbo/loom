from __future__ import annotations

import subprocess
from pathlib import Path

from loom.git import get_git_info


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _init_repo(root: Path) -> None:
    _git("init", cwd=root)
    _git(
        "-c", "user.email=test@example.com", "-c", "user.name=Test",
        "commit", "--allow-empty", "-m", "init",
        cwd=root,
    )


def test_get_git_info_on_clean_tree(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    info = get_git_info(tmp_path)

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.strip()

    assert info.commit == commit
    assert info.dirty is False


def test_get_git_info_on_dirty_tree(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "untracked.txt").write_text("hi", encoding="utf-8")

    info = get_git_info(tmp_path)

    assert info.commit is not None
    assert info.dirty is True


def test_get_git_info_outside_a_repo(tmp_path: Path) -> None:
    info = get_git_info(tmp_path)

    assert info.commit is None
    assert info.dirty is False
