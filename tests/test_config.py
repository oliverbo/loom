from __future__ import annotations

from pathlib import Path

import pytest

from loom.config import load_config
from loom.errors import ConfigError


def test_load_config_reads_fixture_site(sample_site: Path) -> None:
    config = load_config(sample_site)
    assert config.title == "Fixture Site"
    assert config.base_url == "https://example.com"
    assert config.site_root == sample_site


def test_load_config_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="No loom.toml found"):
        load_config(tmp_path)


def test_load_config_rejects_invalid_toml(tmp_path: Path) -> None:
    (tmp_path / "loom.toml").write_text("not valid = = toml", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid TOML"):
        load_config(tmp_path)


def test_load_config_requires_title(tmp_path: Path) -> None:
    (tmp_path / "loom.toml").write_text('base_url = "/"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="failed validation"):
        load_config(tmp_path)


def test_load_config_preserves_unknown_keys(tmp_path: Path) -> None:
    (tmp_path / "loom.toml").write_text('title = "T"\nfuture_feature = "kept"\n', encoding="utf-8")
    config = load_config(tmp_path)
    assert config.model_extra["future_feature"] == "kept"
