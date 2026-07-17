from __future__ import annotations

from pathlib import Path

import pytest

from loom.errors import DeployError
from loom.site.config import DeployConfig
from loom.site.deploy.directory_backend import DirectoryDeploymentBackend
from loom.site.deploy.manifest import build_manifest
from loom.site.deploy.pipeline import run_deployment


def _build_dir(tmp_path: Path, files: dict[str, str]) -> Path:
    build_dir = tmp_path / "build"
    for relative_path, content in files.items():
        path = build_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return build_dir


def _backend(tmp_path: Path) -> DirectoryDeploymentBackend:
    config = DeployConfig(target="directory", destination="deployed")
    return DirectoryDeploymentBackend(config, tmp_path)


def test_first_deployment_uploads_everything(tmp_path: Path) -> None:
    build_dir = _build_dir(tmp_path, {"index.html": "a", "feed.xml": "b"})
    manifest = build_manifest(build_dir, commit="abc", dirty=False)
    backend = _backend(tmp_path)

    result = run_deployment(build_dir, backend, manifest, dry_run=False)

    assert sorted(result.delta.added) == ["feed.xml", "index.html"]
    assert (backend.destination / "index.html").read_text(encoding="utf-8") == "a"
    assert backend.load_manifest() == manifest


def test_second_deployment_only_touches_changed_files(tmp_path: Path) -> None:
    build_dir = _build_dir(tmp_path, {"index.html": "a", "feed.xml": "b"})
    backend = _backend(tmp_path)
    first_manifest = build_manifest(build_dir, commit="abc", dirty=False)
    run_deployment(build_dir, backend, first_manifest, dry_run=False)

    (build_dir / "index.html").write_text("a-changed", encoding="utf-8")
    new_manifest = build_manifest(build_dir, commit="def", dirty=False)

    result = run_deployment(build_dir, backend, new_manifest, dry_run=False)

    assert result.delta.modified == ("index.html",)
    assert result.delta.added == ()
    assert result.delta.unchanged == ("feed.xml",)
    assert (backend.destination / "index.html").read_text(encoding="utf-8") == "a-changed"


def test_dry_run_makes_no_destination_changes(tmp_path: Path) -> None:
    build_dir = _build_dir(tmp_path, {"index.html": "a"})
    manifest = build_manifest(build_dir, commit="abc", dirty=False)
    backend = _backend(tmp_path)

    result = run_deployment(build_dir, backend, manifest, dry_run=True)

    assert result.dry_run is True
    assert result.delta.added == ("index.html",)
    assert not backend.destination.exists()
    assert backend.load_manifest() is None


def test_failed_deployment_does_not_update_stored_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_dir = _build_dir(tmp_path, {"index.html": "a"})
    backend = _backend(tmp_path)
    first_manifest = build_manifest(build_dir, commit="abc", dirty=False)
    run_deployment(build_dir, backend, first_manifest, dry_run=False)

    (build_dir / "index.html").write_text("a-changed", encoding="utf-8")
    (build_dir / "new.html").write_text("new", encoding="utf-8")
    second_manifest = build_manifest(build_dir, commit="def", dirty=False)

    def _boom(relative_path: str, source_path: Path) -> None:
        raise DeployError("simulated upload failure")

    monkeypatch.setattr(backend, "upload_file", _boom)

    with pytest.raises(DeployError):
        run_deployment(build_dir, backend, second_manifest, dry_run=False)

    assert backend.load_manifest() == first_manifest
