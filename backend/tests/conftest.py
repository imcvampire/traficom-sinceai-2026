from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ific.api import app
from ific.config import settings


@pytest.fixture(autouse=True)
def tmp_db_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_dir = tmp_path / "db"
    monkeypatch.setattr(settings, "db_dir", db_dir)
    monkeypatch.setattr(settings, "watcher_enabled", False)
    monkeypatch.setattr(settings, "watcher_state_path", tmp_path / "watcher" / "watcher.sqlite3")
    monkeypatch.setattr(settings, "watcher_download_dir", tmp_path / "ific")
    # The root .env holds a real provider key; tests must never reach the paid API.
    monkeypatch.setattr(settings, "llm_api_key", None)
    monkeypatch.setattr(settings, "llm_model", None)
    return db_dir


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client
