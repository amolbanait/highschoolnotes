import os
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

os.environ.setdefault("HSN_DATABASE_URL", "postgresql+psycopg://hsn:hsn@localhost:5432/hsn_test")
os.environ.setdefault("HSN_SECRET_KEY", "test")


@pytest.fixture(autouse=True)
def _storage_dir(tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("HSN_STORAGE_DIR", str(tmp_path / "files"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def sample_text() -> str:
    return (FIXTURES / "photosynthesis.md").read_text()
