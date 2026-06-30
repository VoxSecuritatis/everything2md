# ================================================================
# tests/conftest
# ================================================================
# Shared fixtures for all test modules.
# ================================================================

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def tmp_workspace(tmp_path: Path) -> Path:
    """A temporary directory pre-populated with all fixture files."""
    for src in FIXTURES_DIR.iterdir():
        if src.is_file():
            shutil.copy2(src, tmp_path / src.name)
    return tmp_path


@pytest.fixture()
def sample_txt(tmp_workspace: Path) -> Path:
    return tmp_workspace / "sample.txt"


@pytest.fixture()
def sample_html(tmp_workspace: Path) -> Path:
    return tmp_workspace / "sample.html"
