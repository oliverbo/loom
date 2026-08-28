"""Firebase Hosting deploy target.

Requires the optional `google-auth` and `requests` dependencies (`pip
install 'loom[firebase]'`); the imports are deferred so importing
`loom.site.deploy` doesn't require them unless a site actually deploys to
`firebase`.

Authenticates via Application Default Credentials -- whatever `gcloud auth
application-default login` or `GOOGLE_APPLICATION_CREDENTIALS` provides --
same as the `gcs` target, rather than requiring the `firebase` CLI and its
own `firebase login` flow.

Unlike `directory`/`gcs`, this is a full-tree target: Firebase Hosting's
deploy protocol is atomic and does its own content-hash diffing server
side, so every deploy declares the build's complete file manifest and lets
Firebase decide what it still needs uploaded -- there's no Loom-side
incremental manifest for this target.

Example `loom.toml`:

    [deploy]
    target = "firebase"
    project = "my-firebase-project"
    site = "my-site"  # optional; defaults to `project`
"""

from __future__ import annotations

import gzip
import hashlib
from pathlib import Path
from typing import Any

from loom.errors import DeployError
from loom.site.config import DeployConfig

try:
    import google.auth
    import requests
    from google.auth.exceptions import GoogleAuthError
    from google.auth.transport.requests import AuthorizedSession
except ImportError as exc:
    google = None  # type: ignore[assignment]
    _IMPORT_ERROR: ImportError | None = exc
else:
    _IMPORT_ERROR = None

HOSTING_API_BASE = "https://firebasehosting.googleapis.com/v1beta1"
HOSTING_UPLOAD_SCOPE = "https://www.googleapis.com/auth/firebase"
_POPULATE_FILES_BATCH_SIZE = 1000


class FirebaseDeployTarget:
    def __init__(self, config: DeployConfig) -> None:
        if google is None:
            raise DeployError(
                "firebase deploy target requires the 'google-auth' and 'requests' "
                "packages; install them with `pip install 'loom[firebase]'`"
            ) from _IMPORT_ERROR

        extra = config.model_extra or {}
        project = extra.get("project")
        if not project:
            raise DeployError("firebase deploy target requires a 'project' in [deploy]")
        self.project: str = project
        self.site: str = extra.get("site") or project

        try:
            credentials, _ = google.auth.default(scopes=[HOSTING_UPLOAD_SCOPE])
        except GoogleAuthError as exc:
            raise DeployError(
                f"failed to create Firebase credentials (check Application Default "
                f"Credentials): {exc}"
            ) from exc
        self.session = AuthorizedSession(credentials)

    def deploy(self, build_dir: Path) -> None:
        files = {
            path.relative_to(build_dir).as_posix(): path
            for path in build_dir.rglob("*")
            if path.is_file()
        }
        compressed = {
            relative_path: gzip.compress(source.read_bytes(), mtime=0)
            for relative_path, source in files.items()
        }
        hashes = {
            relative_path: hashlib.sha256(data).hexdigest()
            for relative_path, data in compressed.items()
        }

        version_name = self._create_version()

        # populateFiles caps each call at 1000 file hashes, so a large site
        # is declared to the new version in batches.
        required_hashes: set[str] = set()
        upload_url = ""
        items = list(hashes.items())
        for start in range(0, len(items), _POPULATE_FILES_BATCH_SIZE):
            batch = dict(items[start : start + _POPULATE_FILES_BATCH_SIZE])
            batch_required, upload_url = self._populate_files(version_name, batch)
            required_hashes.update(batch_required)

        hash_to_path = {digest: relative_path for relative_path, digest in hashes.items()}
        for digest in required_hashes:
            relative_path = hash_to_path[digest]
            self._upload_file(upload_url, digest, relative_path, compressed[relative_path])

        self._finalize_version(version_name)
        self._create_release(version_name)

    def _create_version(self) -> str:
        response = self._request("POST", f"{HOSTING_API_BASE}/sites/{self.site}/versions", json={})
        return response["name"]

    def _populate_files(
        self, version_name: str, hashes: dict[str, str]
    ) -> tuple[list[str], str]:
        payload = {"files": {f"/{path}": digest for path, digest in hashes.items()}}
        response = self._request(
            "POST", f"{HOSTING_API_BASE}/{version_name}:populateFiles", json=payload
        )
        return response.get("uploadRequiredHashes", []), response["uploadUrl"]

    def _upload_file(
        self, upload_url: str, digest: str, relative_path: str, data: bytes
    ) -> None:
        # The body is the gzip-compressed bytes themselves, not the
        # underlying asset -- Firebase infers each file's served
        # Content-Type from its path (declared in populateFiles), not from
        # this upload request, so this header is always octet-stream.
        try:
            response = self.session.post(
                f"{upload_url}/{digest}",
                data=data,
                headers={"Content-Type": "application/octet-stream"},
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DeployError(
                f"failed to upload {relative_path!r} to Firebase Hosting: {exc}{_error_detail(exc)}"
            ) from exc

    def _finalize_version(self, version_name: str) -> None:
        # No `updateMask` param: the API defaults to a mask of just `status`
        # when omitted, and that's the only field this ever sets, so there's
        # no need to pin the mask's query-param casing (docs show both
        # `updateMask` and `update_mask` in different places).
        self._request("PATCH", f"{HOSTING_API_BASE}/{version_name}", json={"status": "FINALIZED"})

    def _create_release(self, version_name: str) -> None:
        self._request(
            "POST",
            f"{HOSTING_API_BASE}/sites/{self.site}/releases",
            params={"versionName": version_name},
            json={},
        )

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DeployError(
                f"Firebase Hosting API request failed ({method} {url}): {exc}{_error_detail(exc)}"
            ) from exc
        return response.json()


def _error_detail(exc: requests.RequestException) -> str:
    """Append the response body to an HTTP error, e.g. Google's JSON `error.message`.

    `requests.HTTPError`'s default `str()` is just the status line ("403
    Client Error: Forbidden for url: ..."), which drops the actual reason
    Google sends back (insufficient scope vs. IAM permission vs. a disabled
    API are all otherwise indistinguishable 403s).
    """
    response = getattr(exc, "response", None)
    if response is None:
        return ""
    return f"\n{response.text}"
