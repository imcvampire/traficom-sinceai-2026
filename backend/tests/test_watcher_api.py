import asyncio
import threading
import time
from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner
from watcher_fakes import FakeItu

from ific.api import app
from ific.cli import app as cli_app
from ific.config import settings
from ific.watcher import service as service_module
from ific.watcher.service import WatcherService


@pytest.fixture
def itu(monkeypatch: pytest.MonkeyPatch) -> FakeItu:
    fake = FakeItu()
    fake.serve_zip(3083)
    fake.serve_zip(3082)
    monkeypatch.setattr(service_module, "make_client", lambda _settings: fake.client())
    return fake


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "watcher_enabled", True)


def _wait_for(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition not reached in time")
        time.sleep(0.02)


def test_env_disabled_locks_patch_409(client: TestClient, itu: FakeItu) -> None:
    state = client.get("/api/watcher").json()

    assert state["locked"] is True
    assert state["enabled"] is False
    assert state["next_run_at"] is None
    assert client.patch("/api/watcher", json={"enabled": True}).status_code == 409
    assert client.post("/api/watcher/check").status_code == 409
    assert itu.requests == []


@pytest.mark.usefixtures("enabled")
def test_startup_check_downloads_and_lists_files(itu: FakeItu) -> None:
    with TestClient(app) as client:
        _wait_for(lambda: client.get("/api/watcher").json()["last_run"] is not None)
        state = client.get("/api/watcher").json()
        files = client.get("/api/watcher/files").json()

    assert state["enabled"] is True
    assert state["last_run"]["outcome"] == "ok"
    assert state["last_run"]["trigger"] == "schedule"
    assert state["next_run_at"] is not None
    assert [(f["ific_no"], f["status"], f["published_on"]) for f in files] == [
        (3083, "downloaded", "2026-10-27"),
        (3082, "downloaded", "2026-10-13"),
    ]
    assert files[0]["local_path"] == "3083/ific3083.mdb"
    assert not Path(files[0]["local_path"]).is_absolute()


@pytest.mark.usefixtures("enabled")
def test_patch_pause_persists_across_new_service_instance(itu: FakeItu) -> None:
    with TestClient(app) as client:
        _wait_for(lambda: client.get("/api/watcher").json()["last_run"] is not None)
        state = client.patch("/api/watcher", json={"enabled": False}).json()
        assert (state["enabled"], state["ui_enabled"], state["locked"]) == (False, False, False)

    assert WatcherService(settings).state().ui_enabled is False
    itu.requests.clear()
    with TestClient(app) as client:
        time.sleep(0.2)
        state = client.get("/api/watcher").json()
    assert (state["enabled"], state["ui_enabled"], state["next_run_at"]) == (False, False, None)
    assert itu.requests == []


@pytest.mark.usefixtures("enabled")
def test_resume_triggers_check_immediately(itu: FakeItu) -> None:
    WatcherService(settings).store.set_ui_enabled(False)
    with TestClient(app) as client:
        time.sleep(0.1)
        assert client.get("/api/watcher").json()["last_run"] is None

        client.patch("/api/watcher", json={"enabled": True})

        _wait_for(lambda: client.get("/api/watcher").json()["last_run"] is not None)
    assert len(itu.zip_requests()) == 2


@pytest.mark.usefixtures("enabled")
def test_manual_check_runs_while_paused(itu: FakeItu) -> None:
    WatcherService(settings).store.set_ui_enabled(False)
    with TestClient(app) as client:
        response = client.post("/api/watcher/check")
        assert response.status_code == 202
        assert response.json() == {"accepted": True}
        _wait_for(lambda: client.get("/api/watcher").json()["last_run"] is not None)
        assert client.get("/api/watcher").json()["last_run"]["trigger"] == "manual"


@pytest.mark.usefixtures("enabled")
def test_check_now_409_while_running(itu: FakeItu) -> None:
    release = threading.Event()

    async def blocked(_request: httpx2.Request) -> httpx2.Response:
        while not release.is_set():
            await asyncio.sleep(0.01)
        return httpx2.Response(503)

    itu.override = blocked
    with TestClient(app) as client:
        _wait_for(lambda: client.get("/api/watcher").json()["running"])

        response = client.post("/api/watcher/check")

        assert response.status_code == 409
        assert response.json()["detail"] == "check already running"
        release.set()
        _wait_for(lambda: not client.get("/api/watcher").json()["running"])
        assert client.get("/api/watcher").json()["last_run"]["outcome"] == "error"


def test_cli_check_respects_master_switch(itu: FakeItu) -> None:
    result = CliRunner().invoke(cli_app, ["watch", "check"])

    assert result.exit_code == 2
    assert itu.requests == []


@pytest.mark.usefixtures("enabled")
def test_cli_check_shares_state_with_api(itu: FakeItu) -> None:
    result = CliRunner().invoke(cli_app, ["watch", "check"])

    assert result.exit_code == 0, result.output
    assert "ok: new=2 downloaded=2 failed=0" in result.output
    with TestClient(app) as client:
        assert [f["status"] for f in client.get("/api/watcher/files").json()] == ["downloaded"] * 2
