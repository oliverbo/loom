from __future__ import annotations

from pathlib import Path

import pytest

from loom.errors import ConfigError
from loom.site.config import load_config


def _write_config(root: Path, text: str) -> None:
    config_dir = root / ".loom"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "loom.toml").write_text(text, encoding="utf-8")


def test_load_config_reads_fixture_site(sample_site: Path) -> None:
    config = load_config(sample_site)
    assert config.title == "Fixture Site"
    assert config.base_url == "https://example.com"
    assert config.site_root == sample_site


def test_load_config_defaults_posts_dir(sample_site: Path) -> None:
    config = load_config(sample_site)
    assert config.posts_dir == "content/posts"


def test_load_config_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="No loom.toml found"):
        load_config(tmp_path)


def test_load_config_rejects_invalid_toml(tmp_path: Path) -> None:
    _write_config(tmp_path, "not valid = = toml")
    with pytest.raises(ConfigError, match="not valid TOML"):
        load_config(tmp_path)


def test_load_config_requires_title(tmp_path: Path) -> None:
    _write_config(tmp_path, 'base_url = "/"\n')
    with pytest.raises(ConfigError, match="failed validation"):
        load_config(tmp_path)


def test_load_config_preserves_unknown_keys(tmp_path: Path) -> None:
    _write_config(tmp_path, 'title = "T"\nfuture_feature = "kept"\n')
    config = load_config(tmp_path)
    assert config.model_extra["future_feature"] == "kept"
