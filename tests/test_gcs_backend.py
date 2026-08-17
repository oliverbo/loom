from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import NotFound, ServiceUnavailable
from google.auth.exceptions import DefaultCredentialsError

import loom.site.deploy.gcs_backend as gcs_backend
from loom.errors import DeployError, ManifestError
from loom.site.config import DeployConfig
from loom.site.deploy.gcs_backend import GcsDeploymentBackend
from loom.site.deploy.manifest import DeploymentManifest, FileEntry, SourceInfo, to_json


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock_client = MagicMock()
    monkeypatch.setattr(gcs_backend.storage, "Client", MagicMock(return_value=mock_client))
    return mock_client


def _backend(tmp_path: Path, **extra: str) -> GcsDeploymentBackend:
    config = DeployConfig(target="gcs", bucket="my-bucket", **extra)
    return GcsDeploymentBackend(config, tmp_path)


def _manifest() -> DeploymentManifest:
    return DeploymentManifest(
        version=1,
        source=SourceInfo(commit="abc", dirty=False),
        files={"index.html": FileEntry(sha256="deadbeef")},
    )


def test_requires_bucket(tmp_path: Path, client: MagicMock) -> None:
    with pytest.raises(DeployError):
        GcsDeploymentBackend(DeployConfig(target="gcs"), tmp_path)


def test_wraps_bucket_from_client(tmp_path: Path, client: MagicMock) -> None:
    backend = _backend(tmp_path)
    client.bucket.assert_called_once_with("my-bucket")
    assert backend.bucket is client.bucket.return_value


def test_strips_slashes_from_prefix(tmp_path: Path, client: MagicMock) -> None:
    backend = _backend(tmp_path, prefix="/blog/")
    assert backend.prefix == "blog"


def test_auth_failure_raises_deploy_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        gcs_backend.storage,
        "Client",
        MagicMock(side_effect=DefaultCredentialsError("no credentials")),
    )
    with pytest.raises(DeployError):
        _backend(tmp_path)


def test_load_manifest_returns_none_when_missing(tmp_path: Path, client: MagicMock) -> None:
    backend = _backend(tmp_path)
    blob = client.bucket.return_value.blob.return_value
    blob.download_as_text.side_effect = NotFound("no manifest")

    assert backend.load_manifest() is None
    client.bucket.return_value.blob.assert_called_with(".loom-manifest.json")


def test_load_manifest_parses_existing_blob(tmp_path: Path, client: MagicMock) -> None:
    backend = _backend(tmp_path)
    blob = client.bucket.return_value.blob.return_value
    blob.download_as_text.return_value = to_json(_manifest())

    assert backend.load_manifest() == _manifest()


def test_load_manifest_wraps_api_errors(tmp_path: Path, client: MagicMock) -> None:
    backend = _backend(tmp_path)
    blob = client.bucket.return_value.blob.return_value
    blob.download_as_text.side_effect = ServiceUnavailable("down")

    with pytest.raises(DeployError):
        backend.load_manifest()


def test_upload_file_sets_content_type_and_uploads(tmp_path: Path, client: MagicMock) -> None:
    source = tmp_path / "index.html"
    source.write_text("<html></html>", encoding="utf-8")

    backend = _backend(tmp_path)
    backend.upload_file("index.html", source)

    backend.bucket.blob.assert_called_with("index.html")
    blob = backend.bucket.blob.return_value
    blob.upload_from_filename.assert_called_once_with(str(source), content_type="text/html")


def test_upload_file_applies_prefix(tmp_path: Path, client: MagicMock) -> None:
    source = tmp_path / "index.html"
    source.write_text("x", encoding="utf-8")

    backend = _backend(tmp_path, prefix="blog")
    backend.upload_file("index.html", source)

    backend.bucket.blob.assert_called_with("blog/index.html")


def test_upload_file_wraps_api_errors(tmp_path: Path, client: MagicMock) -> None:
    source = tmp_path / "index.html"
    source.write_text("x", encoding="utf-8")

    backend = _backend(tmp_path)
    backend.bucket.blob.return_value.upload_from_filename.side_effect = ServiceUnavailable("down")

    with pytest.raises(DeployError):
        backend.upload_file("index.html", source)


def test_delete_file_deletes_blob(tmp_path: Path, client: MagicMock) -> None:
    backend = _backend(tmp_path)

    backend.delete_file("posts/old.html")

    backend.bucket.blob.assert_called_with("posts/old.html")
    backend.bucket.blob.return_value.delete.assert_called_once()


def test_delete_file_ignores_already_missing_blob(tmp_path: Path, client: MagicMock) -> None:
    backend = _backend(tmp_path)
    backend.bucket.blob.return_value.delete.side_effect = NotFound("gone")

    backend.delete_file("posts/old.html")  # should not raise


def test_delete_file_wraps_api_errors(tmp_path: Path, client: MagicMock) -> None:
    backend = _backend(tmp_path)
    backend.bucket.blob.return_value.delete.side_effect = ServiceUnavailable("down")

    with pytest.raises(DeployError):
        backend.delete_file("posts/old.html")


def test_save_manifest_uploads_json(tmp_path: Path, client: MagicMock) -> None:
    backend = _backend(tmp_path)
    manifest = _manifest()

    backend.save_manifest(manifest)

    backend.bucket.blob.assert_called_with(".loom-manifest.json")
    backend.bucket.blob.return_value.upload_from_string.assert_called_once_with(
        to_json(manifest), content_type="application/json"
    )


@pytest.mark.parametrize("bad_path", ["../escape.txt", "/etc/passwd", ""])
def test_upload_file_rejects_path_traversal(
    tmp_path: Path, client: MagicMock, bad_path: str
) -> None:
    backend = _backend(tmp_path)
    source = tmp_path / "source.txt"
    source.write_text("x", encoding="utf-8")

    with pytest.raises(ManifestError):
        backend.upload_file(bad_path, source)


@pytest.mark.parametrize("bad_path", ["../escape.txt", "/etc/passwd", ""])
def test_delete_file_rejects_path_traversal(
    tmp_path: Path, client: MagicMock, bad_path: str
) -> None:
    backend = _backend(tmp_path)

    with pytest.raises(ManifestError):
        backend.delete_file(bad_path)


def test_missing_dependency_raises_deploy_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gcs_backend, "storage", None)
    monkeypatch.setattr(gcs_backend, "_IMPORT_ERROR", ImportError("no google-cloud-storage"))

    with pytest.raises(DeployError):
        GcsDeploymentBackend(DeployConfig(target="gcs", bucket="my-bucket"), tmp_path)
