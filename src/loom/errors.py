"""Shared exception types.

Kept in one module so every layer (config, content, validation, build,
deploy) raises something callers can catch as `LoomError` without needing
to know which submodule it came from.
"""

from __future__ import annotations


class LoomError(Exception):
    """Base class for all Loom errors."""


class ConfigError(LoomError):
    """`loom.toml` is missing, malformed, or fails schema validation."""


class ContentError(LoomError):
    """A content file (front matter or body) could not be parsed."""


class ValidationError(LoomError):
    """Raised by the CLI when `loom validate` finds one or more problems.

    Individual problems are collected as plain strings on `.errors` rather
    than raised one at a time, so `loom validate` can report everything
    wrong in a single pass instead of stopping at the first issue.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} validation error(s)")


class DeployError(LoomError):
    """A deploy target failed to ship the build output."""


class ManifestError(LoomError):
    """A deployment manifest is missing, malformed, or uses an unsupported version."""
