from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ific import __version__
from ific.api import app
from ific.config import settings


def test_health(client: TestClient, tmp_db_dir: Path) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["db"]["path"] == str(tmp_db_dir / "ific.duckdb")
    assert body["db"]["m4_edition"] == "4 AG/2026M"
    assert body["db"]["tables"]["m4_allocation"] == 5917
    assert body["db"]["tables"]["m4_page"] > 0
    assert body["db"]["tables"]["special_interest_station"] == 873


def test_restart_reuses_loaded_data() -> None:
    with TestClient(app):
        assert {s.action for s in app.state.ref_status} == {"loaded"}
    with TestClient(app):
        assert {s.action for s in app.state.ref_status} == {"up_to_date"}


def test_startup_fails_without_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(settings, "data_dir", empty)

    with pytest.raises(FileNotFoundError, match="IFIC_DATA_DIR"), TestClient(app):
        pass
