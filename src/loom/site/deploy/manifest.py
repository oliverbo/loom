"""Deployment manifest: a content-hash fingerprint of every generated file.

Git versions the source inputs; this manifest tracks generated outputs.
Deployment compares two of these (see `loom.site.deploy.delta`) instead of
diffing Git commits, because one source change can affect many generated
files -- or, for a template change, every file in the site.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from loom.errors import ManifestError

MANIFEST_FILENAME = ".loom-manifest.json"
MANIFEST_VERSION = 1

_HASH_CHUNK_SIZE = 1024 * 1024
_DRIVE_LETTER = re.compile(r"^[A-Za-z]:")


@dataclass(frozen=True)
class FileEntry:
    sha256: str


@dataclass(frozen=True)
class SourceInfo:
    commit: str | None
    dirty: bool


@dataclass(frozen=True)
class DeploymentManifest:
    version: int
    source: SourceInfo
    files: dict[str, FileEntry]


def hash_file(path: Path) -> str:
    """Return the hex SHA-256 digest of `path`'s exact bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(build_dir: Path, *, commit: str | None, dirty: bool) -> DeploymentManifest:
    """Hash every file under `build_dir`, except the manifest file itself."""
    files: dict[str, FileEntry] = {}
    for path in build_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(build_dir).as_posix()
        if relative == MANIFEST_FILENAME:
            continue
        files[relative] = FileEntry(sha256=hash_file(path))

    return DeploymentManifest(
        version=MANIFEST_VERSION,
        source=SourceInfo(commit=commit, dirty=dirty),
        files={path: files[path] for path in sorted(files)},
    )


def to_json(manifest: DeploymentManifest) -> str:
    payload: dict[str, Any] = {
        "version": manifest.version,
        "source": {"commit": manifest.source.commit, "dirty": manifest.source.dirty},
        "files": {
            path: {"sha256": entry.sha256} for path, entry in sorted(manifest.files.items())
        },
    }
    return json.dumps(payload, indent=2) + "\n"


def parse_manifest(text: str) -> DeploymentManifest:
    """Parse and validate a manifest JSON document.

    Raises `ManifestError` if the document is malformed, uses an
    unsupported version, or contains an unsafe file path.
    """
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ManifestError("manifest must be a JSON object")

    version = raw.get("version")
    if version != MANIFEST_VERSION:
        raise ManifestError(f"unsupported manifest version: {version!r}")

    source = raw.get("source")
    if not isinstance(source, dict):
        raise ManifestError("manifest is missing a 'source' object")
    commit = source.get("commit")
    if commit is not None and not isinstance(commit, str):
        raise ManifestError("manifest 'source.commit' must be a string or null")
    dirty = source.get("dirty")
    if not isinstance(dirty, bool):
        raise ManifestError("manifest 'source.dirty' must be a boolean")

    raw_files = raw.get("files")
    if not isinstance(raw_files, dict):
        raise ManifestError("manifest is missing a 'files' object")

    files: dict[str, FileEntry] = {}
    for relative_path, entry in raw_files.items():
        validate_relative_path(relative_path)
        if not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str):
            raise ManifestError(f"manifest entry {relative_path!r} is malformed")
        files[relative_path] = FileEntry(sha256=entry["sha256"])

    return DeploymentManifest(
        version=version,
        source=SourceInfo(commit=commit, dirty=dirty),
        files={path: files[path] for path in sorted(files)},
    )


def write_manifest(path: Path, manifest: DeploymentManifest) -> None:
    """Write `manifest` to `path` atomically (temp file + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".loom-manifest-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(to_json(manifest))
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def read_manifest(path: Path) -> DeploymentManifest | None:
    """Read and parse the manifest at `path`, or `None` if it doesn't exist."""
    if not path.is_file():
        return None
    return parse_manifest(path.read_text(encoding="utf-8"))


def validate_relative_path(relative_path: str) -> None:
    """Raise `ManifestError` if `relative_path` isn't a safe, relative path.

    Rejects absolute paths (POSIX or Windows-drive-letter), empty paths,
    and any path containing a `..` segment.
    """
    if not relative_path:
        raise ManifestError("manifest path must not be empty")
    if "\\" in relative_path:
        raise ManifestError(f"manifest path must use forward slashes: {relative_path!r}")
    if _DRIVE_LETTER.match(relative_path):
        raise ManifestError(f"manifest path must be relative: {relative_path!r}")

    pure = PurePosixPath(relative_path)
    if pure.is_absolute():
        raise ManifestError(f"manifest path must be relative: {relative_path!r}")
    if ".." in pure.parts or "." in pure.parts:
        raise ManifestError(f"manifest path is malformed: {relative_path!r}")
