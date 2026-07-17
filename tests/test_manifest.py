from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from loom.errors import ManifestError
from loom.site.deploy.manifest import (
    MANIFEST_FILENAME,
    MANIFEST_VERSION,
    build_manifest,
    hash_file,
    parse_manifest,
    read_manifest,
    to_json,
    validate_relative_path,
    write_manifest,
)


def test_hash_file_matches_hashlib(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_bytes(b"hello world")

    assert hash_file(path) == hashlib.sha256(b"hello world").hexdigest()


def _make_build_dir(tmp_path: Path) -> Path:
    build_dir = tmp_path / "build"
    (build_dir / "posts" / "hello").mkdir(parents=True)
    (build_dir / "index.html").write_text("<html>index</html>", encoding="utf-8")
    (build_dir / "posts" / "hello" / "index.html").write_text(
        "<html>hello</html>", encoding="utf-8"
    )
    (build_dir / "feed.xml").write_text("<rss></rss>", encoding="utf-8")
    return build_dir


def test_build_manifest_is_deterministic(tmp_path: Path) -> None:
    build_dir = _make_build_dir(tmp_path)

    first = build_manifest(build_dir, commit="abc123", dirty=False)
    second = build_manifest(build_dir, commit="abc123", dirty=False)

    assert to_json(first) == to_json(second)
    assert list(first.files) == sorted(first.files)


def test_build_manifest_uses_forward_slashes(tmp_path: Path) -> None:
    build_dir = _make_build_dir(tmp_path)
    manifest = build_manifest(build_dir, commit=None, dirty=False)

    assert "posts/hello/index.html" in manifest.files
    assert all("\\" not in path for path in manifest.files)


def test_build_manifest_excludes_itself(tmp_path: Path) -> None:
    build_dir = _make_build_dir(tmp_path)
    first = build_manifest(build_dir, commit=None, dirty=False)
    write_manifest(build_dir / MANIFEST_FILENAME, first)

    manifest = build_manifest(build_dir, commit=None, dirty=False)

    assert MANIFEST_FILENAME not in manifest.files


def test_manifest_json_round_trip(tmp_path: Path) -> None:
    build_dir = _make_build_dir(tmp_path)
    manifest = build_manifest(build_dir, commit="deadbeef", dirty=True)

    parsed = parse_manifest(to_json(manifest))

    assert parsed == manifest


def test_write_and_read_manifest(tmp_path: Path) -> None:
    build_dir = _make_build_dir(tmp_path)
    manifest = build_manifest(build_dir, commit="deadbeef", dirty=False)
    manifest_path = build_dir / MANIFEST_FILENAME

    write_manifest(manifest_path, manifest)

    assert read_manifest(manifest_path) == manifest


def test_read_manifest_returns_none_when_missing(tmp_path: Path) -> None:
    assert read_manifest(tmp_path / MANIFEST_FILENAME) is None


def test_parse_manifest_rejects_unsupported_version() -> None:
    with pytest.raises(ManifestError, match="version"):
        parse_manifest('{"version": 999, "source": {"commit": null, "dirty": false}, "files": {}}')


def test_parse_manifest_rejects_malformed_json() -> None:
    with pytest.raises(ManifestError):
        parse_manifest("not json")


@pytest.mark.parametrize(
    "bad_path",
    ["/etc/passwd", "../escape.txt", "posts/../../escape.txt", "", "C:/Windows/x", "a\\b"],
)
def test_validate_relative_path_rejects_unsafe_paths(bad_path: str) -> None:
    with pytest.raises(ManifestError):
        validate_relative_path(bad_path)


def test_validate_relative_path_accepts_safe_paths() -> None:
    validate_relative_path("index.html")
    validate_relative_path("posts/hello-world/index.html")


def test_parse_manifest_rejects_unsafe_file_path() -> None:
    payload = json.dumps(
        {
            "version": MANIFEST_VERSION,
            "source": {"commit": None, "dirty": False},
            "files": {"../escape.txt": {"sha256": "a" * 64}},
        }
    )
    with pytest.raises(ManifestError):
        parse_manifest(payload)
