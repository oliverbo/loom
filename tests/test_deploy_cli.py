from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from loom.cli import app

runner = CliRunner()


def _add_directory_deploy_target(site: Path, *, destination: str = "../deployed") -> None:
    with (site / "loom.toml").open("a", encoding="utf-8") as handle:
        handle.write(f'\n[deploy]\ntarget = "directory"\ndestination = "{destination}"\n')


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )


def test_deploy_first_run_uploads_everything(sample_site: Path) -> None:
    _add_directory_deploy_target(sample_site)

    result = runner.invoke(app, ["site", "deploy", str(sample_site)])

    assert result.exit_code == 0, result.output
    assert "added" in result.output
    assert "Deployment complete." in result.output
    destination = sample_site.parent / "deployed"
    assert (destination / "index.html").is_file()
    assert (destination / ".loom-manifest.json").is_file()


def test_deploy_dry_run_leaves_destination_untouched(sample_site: Path) -> None:
    _add_directory_deploy_target(sample_site)

    result = runner.invoke(app, ["site", "deploy", str(sample_site), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Dry run: no changes made." in result.output
    destination = sample_site.parent / "deployed"
    assert not destination.exists()


def test_deploy_rejects_dirty_tree_without_allow_dirty(sample_site: Path) -> None:
    _add_directory_deploy_target(sample_site)
    _git("init", cwd=sample_site)
    _git("-c", "user.email=test@example.com", "-c", "user.name=Test", "add", "-A", cwd=sample_site)
    _git(
        "-c", "user.email=test@example.com", "-c", "user.name=Test",
        "commit", "-m", "init", cwd=sample_site,
    )
    post_path = sample_site / "content" / "posts" / "hello-world.md"
    post_path.write_text(post_path.read_text(encoding="utf-8") + "\nextra\n", encoding="utf-8")

    blocked = runner.invoke(app, ["site", "deploy", str(sample_site)])
    assert blocked.exit_code == 1
    assert "dirty" in blocked.output.lower()
    assert not (sample_site.parent / "deployed").exists()

    allowed = runner.invoke(app, ["site", "deploy", str(sample_site), "--allow-dirty"])
    assert allowed.exit_code == 0, allowed.output
    assert (sample_site.parent / "deployed" / "index.html").is_file()
