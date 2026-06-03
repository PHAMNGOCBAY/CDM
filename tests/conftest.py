"""Pytest fixtures dùng chung."""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

# Add scripts/ to path
_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


@pytest.fixture(scope="session")
def project_root() -> Path:
    return _ROOT


@pytest.fixture(scope="session")
def db_local_path() -> Path:
    return Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")


@pytest.fixture(scope="session")
def db_project_path() -> Path:
    return _ROOT / "data" / "TTHC.sqlite"


@pytest.fixture(scope="session")
def db_path(db_local_path: Path, db_project_path: Path) -> Path:
    """Prefer LOCAL DB if exists (dev env), else PROJECT DB."""
    return db_local_path if db_local_path.exists() else db_project_path
