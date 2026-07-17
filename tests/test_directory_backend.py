from __future__ import annotations

from pathlib import Path

import pytest

from loom.errors import DeployError, ManifestError
from loom.site.config import DeployConfig
from loom.site.deploy.directory_backend import DirectoryDeploymentBackend
from loom.site.deploy.manifest import MANIFEST_FILENAME, DeploymentManifest, FileEntry, SourceInfo


def _backend(tmp_path: Path, *, destination: str = "deployed") -> DirectoryDeploymentBackend:
    config = DeployConfig(target="directory", destination=destination)
    return DirectoryDeploymentBackend(config, tmp_path)


def _manifest() -> DeploymentManifest:
    return DeploymentManifest(
        version=1,
        source=SourceInfo(commit="abc", dirty=False),
        files={"index.html": FileEntry(sha256="deadbeef")},
    )


def test_requires_destination(tmp_path: Path) -> None:
    with pytest.raises(DeployError):
        DirectoryDeploymentBackend(DeployConfig(target="directory"), tmp_path)


def test_load_manifest_returns_none_when_destination_is_empty(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    assert backend.load_manifest() is None


def test_upload_file_copies_bytes_and_creates_parents(tmp_path: Path) -> None:
    source = tmp_path / "build" / "posts" / "hello" / "index.html"
    source.parent.mkdir(parents=True)
    source.write_text("<html>hello</html>", encoding="utf-8")

    backend = _backend(tmp_path)
    backend.upload_file("posts/hello/index.html", source)

    target = backend.destination / "posts" / "hello" / "index.html"
    assert target.read_text(encoding="utf-8") == "<html>hello</html>"


def test_delete_file_prunes_empty_parent_dirs_but_not_destination(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    nested = backend.destination / "posts" / "only" / "index.html"
    nested.parent.mkdir(parents=True)
    nested.write_text("x", encoding="utf-8")

    backend.delete_file("posts/only/index.html")

    assert not nested.exists()
    assert not (backend.destination / "posts" / "only").exists()
    assert not (backend.destination / "posts").exists()
    assert backend.destination.exists()


def test_delete_file_stops_pruning_at_non_empty_directory(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    sibling = backend.destination / "posts" / "keep-me.html"
    target = backend.destination / "posts" / "remove-me.html"
    sibling.parent.mkdir(parents=True)
    sibling.write_text("keep", encoding="utf-8")
    target.write_text("remove", encoding="utf-8")

    backend.delete_file("posts/remove-me.html")

    assert not target.exists()
    assert sibling.exists()
    assert (backend.destination / "posts").exists()


def test_unrelated_destination_files_are_preserved(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    backend.destination.mkdir(parents=True)
    unrelated = backend.destination / "robots.txt"
    unrelated.write_text("User-agent: *", encoding="utf-8")

    backend.save_manifest(_manifest())

    assert unrelated.exists()
    assert (backend.destination / MANIFEST_FILENAME).exists()


def test_save_and_load_manifest_round_trips(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    manifest = _manifest()

    backend.save_manifest(manifest)

    assert backend.load_manifest() == manifest


@pytest.mark.parametrize("bad_path", ["../escape.txt", "/etc/passwd", ""])
def test_upload_file_rejects_path_traversal(tmp_path: Path, bad_path: str) -> None:
    backend = _backend(tmp_path)
    source = tmp_path / "source.txt"
    source.write_text("x", encoding="utf-8")

    with pytest.raises((DeployError, ManifestError)):
        backend.upload_file(bad_path, source)


@pytest.mark.parametrize("bad_path", ["../escape.txt", "/etc/passwd", ""])
def test_delete_file_rejects_path_traversal(tmp_path: Path, bad_path: str) -> None:
    backend = _backend(tmp_path)

    with pytest.raises((DeployError, ManifestError)):
        backend.delete_file(bad_path)
