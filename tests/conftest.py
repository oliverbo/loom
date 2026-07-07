from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURE_SITE = Path(__file__).parent / "fixtures" / "sample_site"


@pytest.fixture
def sample_site(tmp_path: Path) -> Path:
    """A writable copy of the fixture site, so tests can build/mutate it
    without touching the checked-in fixture.
    """
    dest = tmp_path / "sample_site"
    shutil.copytree(FIXTURE_SITE, dest)
    return dest
