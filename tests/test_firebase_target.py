from __future__ import annotations

import gzip
import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests
from google.auth.exceptions import DefaultCredentialsError

import loom.site.deploy.firebase_target as firebase_target
from loom.errors import DeployError
from loom.site.config import DeployConfig
from loom.site.deploy.firebase_target import FirebaseDeployTarget


def _gzip_sha256(data: bytes) -> str:
    return hashlib.sha256(gzip.compress(data, mtime=0)).hexdigest()


def _response(json_data: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.json.return_value = json_data or {}
    return response


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    monkeypatch.setattr(
        firebase_target.google.auth, "default", MagicMock(return_value=(MagicMock(), "proj"))
    )
    mock_session = MagicMock()
    monkeypatch.setattr(firebase_target, "AuthorizedSession", MagicMock(return_value=mock_session))
    return mock_session


def _target(**extra: str) -> FirebaseDeployTarget:
    config = DeployConfig(target="firebase", project="my-project", **extra)
    return FirebaseDeployTarget(config)


def test_requires_project() -> None:
    with pytest.raises(DeployError):
        FirebaseDeployTarget(DeployConfig(target="firebase"))


def test_site_defaults_to_project(session: MagicMock) -> None:
    target = FirebaseDeployTarget(DeployConfig(target="firebase", project="my-project"))
    assert target.site == "my-project"


def test_site_can_be_overridden(session: MagicMock) -> None:
    target = FirebaseDeployTarget(
        DeployConfig(target="firebase", project="my-project", site="other-site")
    )
    assert target.site == "other-site"


def test_auth_failure_raises_deploy_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        firebase_target.google.auth,
        "default",
        MagicMock(side_effect=DefaultCredentialsError("no credentials")),
    )
    with pytest.raises(DeployError):
        FirebaseDeployTarget(DeployConfig(target="firebase", project="my-project"))


def test_missing_dependency_raises_deploy_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(firebase_target, "google", None)
    monkeypatch.setattr(firebase_target, "_IMPORT_ERROR", ImportError("no google-auth"))

    with pytest.raises(DeployError):
        FirebaseDeployTarget(DeployConfig(target="firebase", project="my-project"))


def _build_dir(tmp_path: Path) -> Path:
    build_dir = tmp_path / "build"
    (build_dir / "posts").mkdir(parents=True)
    (build_dir / "index.html").write_text("<html>home</html>", encoding="utf-8")
    (build_dir / "posts" / "index.html").write_text("<html>posts</html>", encoding="utf-8")
    return build_dir


def test_deploy_creates_populates_uploads_finalizes_and_releases(
    tmp_path: Path, session: MagicMock
) -> None:
    build_dir = _build_dir(tmp_path)
    home_hash = _gzip_sha256((build_dir / "index.html").read_bytes())
    posts_hash = _gzip_sha256((build_dir / "posts" / "index.html").read_bytes())

    session.request.side_effect = [
        _response({"name": "sites/my-project/versions/v1"}),
        _response(
            {
                "uploadRequiredHashes": [home_hash],
                "uploadUrl": "https://upload.example/sites/my-project/versions/v1/files",
            }
        ),
        _response({"name": "sites/my-project/versions/v1", "status": "FINALIZED"}),
        _response({"name": "sites/my-project/releases/r1"}),
    ]
    session.post.return_value = _response({})

    target = _target()
    target.deploy(build_dir)

    base = firebase_target.HOSTING_API_BASE
    calls = session.request.call_args_list
    assert calls[0].args[:2] == ("POST", f"{base}/sites/my-project/versions")
    assert calls[1].args[:2] == ("POST", f"{base}/sites/my-project/versions/v1:populateFiles")
    populate_body = calls[1].kwargs["json"]
    assert populate_body == {"files": {"/index.html": home_hash, "/posts/index.html": posts_hash}}
    assert calls[2].args[:2] == ("PATCH", f"{base}/sites/my-project/versions/v1")
    assert calls[2].kwargs["json"] == {"status": "FINALIZED"}
    assert calls[3].args[:2] == ("POST", f"{base}/sites/my-project/releases")
    assert calls[3].kwargs["params"] == {"versionName": "sites/my-project/versions/v1"}

    session.post.assert_called_once_with(
        f"https://upload.example/sites/my-project/versions/v1/files/{home_hash}",
        data=gzip.compress((build_dir / "index.html").read_bytes(), mtime=0),
        headers={"Content-Type": "application/octet-stream"},
    )


def test_deploy_skips_upload_for_hashes_already_present(
    tmp_path: Path, session: MagicMock
) -> None:
    build_dir = _build_dir(tmp_path)

    session.request.side_effect = [
        _response({"name": "sites/my-project/versions/v1"}),
        _response({"uploadRequiredHashes": [], "uploadUrl": "https://upload.example/files"}),
        _response({}),
        _response({}),
    ]

    target = _target()
    target.deploy(build_dir)

    session.post.assert_not_called()


def test_deploy_batches_populate_files_requests(
    tmp_path: Path, session: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(firebase_target, "_POPULATE_FILES_BATCH_SIZE", 1)
    build_dir = _build_dir(tmp_path)

    session.request.side_effect = [
        _response({"name": "sites/my-project/versions/v1"}),
        _response({"uploadRequiredHashes": [], "uploadUrl": "https://upload.example/files"}),
        _response({"uploadRequiredHashes": [], "uploadUrl": "https://upload.example/files"}),
        _response({}),
        _response({}),
    ]

    target = _target()
    target.deploy(build_dir)

    populate_calls = [
        call for call in session.request.call_args_list if call.args[1].endswith(":populateFiles")
    ]
    assert len(populate_calls) == 2


def test_deploy_wraps_request_errors_as_deploy_error(
    tmp_path: Path, session: MagicMock
) -> None:
    build_dir = _build_dir(tmp_path)
    session.request.side_effect = requests.ConnectionError("network down")

    target = _target()
    with pytest.raises(DeployError):
        target.deploy(build_dir)


def test_deploy_error_includes_response_body_for_http_errors(
    tmp_path: Path, session: MagicMock
) -> None:
    build_dir = _build_dir(tmp_path)
    error_response = MagicMock()
    error_response.text = '{"error": {"message": "Permission denied", "status": "DENIED"}}'
    http_error = requests.HTTPError("403 Client Error: Forbidden for url: ...")
    http_error.response = error_response
    session.request.side_effect = http_error

    target = _target()
    with pytest.raises(DeployError, match="Permission denied"):
        target.deploy(build_dir)


def test_deploy_wraps_upload_errors_as_deploy_error(
    tmp_path: Path, session: MagicMock
) -> None:
    build_dir = _build_dir(tmp_path)
    home_hash = _gzip_sha256((build_dir / "index.html").read_bytes())

    session.request.side_effect = [
        _response({"name": "sites/my-project/versions/v1"}),
        _response(
            {"uploadRequiredHashes": [home_hash], "uploadUrl": "https://upload.example/files"}
        ),
    ]
    session.post.side_effect = requests.ConnectionError("network down")

    target = _target()
    with pytest.raises(DeployError):
        target.deploy(build_dir)


def test_gzip_hash_is_deterministic_across_runs(tmp_path: Path) -> None:
    content = b"hello world"
    first = hashlib.sha256(gzip.compress(content, mtime=0)).hexdigest()
    second = hashlib.sha256(gzip.compress(content, mtime=0)).hexdigest()
    assert first == second
    assert len(first) == 64
