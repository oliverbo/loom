"""Google Cloud Storage deployment backend.

Requires the optional `google-cloud-storage` dependency (`pip install
loom[gcs]`); the import is deferred so importing `loom.site.deploy` doesn't
require it unless a site actually deploys to `gcs`.

Authenticates via Application Default Credentials -- whatever `gcloud auth
application-default login` or `GOOGLE_APPLICATION_CREDENTIALS` provides --
rather than a Loom-specific auth flow.

Example `loom.toml`:

    [deploy]
    target = "gcs"
    bucket = "my-site-bucket"
    prefix = "blog"  # optional
"""

from __future__ import annotations

import mimetypes
import posixpath
from pathlib import Path

from loom.errors import DeployError
from loom.site.config import DeployConfig
from loom.site.deploy.manifest import (
    MANIFEST_FILENAME,
    DeploymentManifest,
    parse_manifest,
    to_json,
    validate_relative_path,
)

try:
    from google.api_core.exceptions import GoogleAPICallError, NotFound
    from google.auth.exceptions import GoogleAuthError
    from google.cloud import storage
except ImportError as exc:
    storage = None  # type: ignore[assignment]
    _IMPORT_ERROR: ImportError | None = exc
else:
    _IMPORT_ERROR = None


class GcsDeploymentBackend:
    def __init__(self, config: DeployConfig, site_root: Path) -> None:
        if storage is None:
            raise DeployError(
                "gcs deploy target requires the 'google-cloud-storage' package; "
                "install it with `pip install loom[gcs]`"
            ) from _IMPORT_ERROR

        extra = config.model_extra or {}
        bucket_name = extra.get("bucket")
        if not bucket_name:
            raise DeployError("gcs deploy target requires a 'bucket' in [deploy]")
        self.bucket_name: str = bucket_name
        self.prefix: str = (extra.get("prefix") or "").strip("/")

        try:
            client = storage.Client()
        except GoogleAuthError as exc:
            raise DeployError(
                f"failed to create a GCS client (check Application Default "
                f"Credentials): {exc}"
            ) from exc
        self.bucket = client.bucket(self.bucket_name)

    def load_manifest(self) -> DeploymentManifest | None:
        blob = self.bucket.blob(self._blob_path(MANIFEST_FILENAME))
        try:
            text = blob.download_as_text()
        except NotFound:
            return None
        except GoogleAPICallError as exc:
            raise DeployError(
                f"failed to load manifest from gs://{self.bucket_name}: {exc}"
            ) from exc
        return parse_manifest(text)

    def upload_file(self, relative_path: str, source_path: Path) -> None:
        blob = self.bucket.blob(self._blob_path(relative_path))
        content_type, _ = mimetypes.guess_type(relative_path)
        try:
            blob.upload_from_filename(str(source_path), content_type=content_type)
        except GoogleAPICallError as exc:
            raise DeployError(
                f"failed to upload {relative_path!r} to gs://{self.bucket_name}: {exc}"
            ) from exc

    def delete_file(self, relative_path: str) -> None:
        blob = self.bucket.blob(self._blob_path(relative_path))
        try:
            blob.delete()
        except NotFound:
            pass
        except GoogleAPICallError as exc:
            raise DeployError(
                f"failed to delete {relative_path!r} from gs://{self.bucket_name}: {exc}"
            ) from exc

    def save_manifest(self, manifest: DeploymentManifest) -> None:
        blob = self.bucket.blob(self._blob_path(MANIFEST_FILENAME))
        try:
            blob.upload_from_string(to_json(manifest), content_type="application/json")
        except GoogleAPICallError as exc:
            raise DeployError(
                f"failed to save manifest to gs://{self.bucket_name}: {exc}"
            ) from exc

    def _blob_path(self, relative_path: str) -> str:
        validate_relative_path(relative_path)
        if self.prefix:
            return posixpath.join(self.prefix, relative_path)
        return relative_path
