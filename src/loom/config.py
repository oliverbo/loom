"""Loading and validating `loom.toml`.

Config is intentionally permissive: unknown top-level keys and unknown
`[deploy]` keys are kept rather than rejected, so a site written for an
older Loom version doesn't break, and a future feature's config section
doesn't require a schema migration here.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from loom.errors import ConfigError

CONFIG_FILENAME = "loom.toml"


class DeployConfig(BaseModel):
    """The `[deploy]` table. `target` selects a `loom.deploy` implementation."""

    model_config = ConfigDict(extra="allow")

    target: str | None = None


class SiteConfig(BaseModel):
    """The parsed, validated contents of `loom.toml`."""

    model_config = ConfigDict(extra="allow")

    title: str
    base_url: str = "/"
    description: str = ""
    author: str = ""
    language: str = "en"

    content_dir: str = "content"
    images_dir: str = "images"
    templates_dir: str = "templates"
    static_dir: str = "static"
    output_dir: str = "build"

    deploy: DeployConfig = Field(default_factory=DeployConfig)

    # Populated after load; not part of the TOML file itself.
    site_root: Path = Field(default=Path("."), exclude=True)

    def resolve(self, relative: str) -> Path:
        """Resolve a configured directory name against the site root."""
        return self.site_root / relative


def load_config(site_root: Path) -> SiteConfig:
    """Load and validate `loom.toml` from `site_root`.

    Raises `ConfigError` if the file is missing, isn't valid TOML, or
    fails schema validation.
    """
    config_path = site_root / CONFIG_FILENAME
    if not config_path.is_file():
        raise ConfigError(f"No {CONFIG_FILENAME} found at {config_path}")

    try:
        raw: dict[str, Any] = tomllib.loads(config_path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{config_path} is not valid TOML: {exc}") from exc

    try:
        config = SiteConfig.model_validate(raw)
    except Exception as exc:  # pydantic.ValidationError
        raise ConfigError(f"{config_path} failed validation: {exc}") from exc

    return config.model_copy(update={"site_root": site_root})
