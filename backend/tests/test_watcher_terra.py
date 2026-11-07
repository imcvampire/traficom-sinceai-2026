import asyncio
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from watcher_fakes import FakeItu, terra_url, year_page

from ific.api import app
from ific.config import Settings, settings
from ific.watcher.service import WatcherService
from ific.watcher.store import SCHEMA_VERSION, WatcherStore

PAGE_2026 = "https://www.itu.int/sns/wic/demowic26.html"
PAGE_2025 = "https://www.itu.int/sns/wic/demowic25.html"
SPACE_ISSUES = (3083, 3082, 3081, 3060)


def _published(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).strftime("%d.%m.%Y")


@pytest.fixture
def itu() -> FakeItu:
    """3083 and 3082 have terrestrial extracts, 3081 is not published yet, 3060 is older than 12 months."""
    fake = FakeItu()
    fake.pages[PAGE_2026] = year_page(
        (_published(10), 3083), (_published(24), 3082), (_published(38), 3081), (_published(400), 3060)
    )
    # Below the stored floor, so later runs never pull it in.
    fake.pages[PAGE_2025] = year_page((_published(420), 3059))
    for no in SPACE_ISSUES:
        fake.serve_zip(no)
    fake.serve_terra(3083)
    fake.serve_terra(3082)
    return fake


def _settings(tmp_path: Path, **overrides: bool) -> Settings:
    return Settings(
        watcher_enabled=True,
        watcher_state_path=tmp_path / "state" / "watcher.sqlite3",
        watcher_download_dir=tmp_path / "ific",
        terra_download_dir=tmp_path / "brific",
        **overrides,
    )


@pytest.fixture
def watcher(tmp_path: Path, itu: FakeItu) -> WatcherService:
    return WatcherService(_settings(tmp_path), client_factory=itu.client)


def _terra(watcher: WatcherService) -> dict[int, tuple[str, int]]:
    return {f.ific_no: (f.status, f.attempts) for f in watcher.store.list_files("terrestrial")}


def test_terrestrial_issues_downloaded_from_recent_space_issues(
    watcher: WatcherService, itu: FakeItu, tmp_path: Path
) -> None:
    result = asyncio.run(watcher.check("manual"))

    assert (result.outcome, result.new_count, result.failed_count) == ("ok", 4, 0)
    assert result.downloaded_count == len(SPACE_ISSUES) + 2
    assert _terra(watcher) == {3083: ("downloaded", 1), 3082: ("downloaded", 1), 3081: ("new", 0)}
    mdb = tmp_path / "brific" / "3083" / "brific3083.mdb"
    assert mdb.read_bytes() == b"brific 3083"
    assert watcher.store.list_files("terrestrial")[0].mdb_path == str(mdb)
    assert sorted(p.name for p in (tmp_path / "brific").rglob("*")) == [
        "3082",
        "3083",
        "brific3082.mdb",
        "brific3083.mdb",
    ]
    assert [str(r.url) for r in itu.terra_requests()] == [terra_url(n) for n in (3083, 3082, 3081)]
    assert all("if-none-match" not in r.headers for r in itu.terra_requests())


def test_second_run_sends_conditional_headers_and_downloads_nothing(
    watcher: WatcherService, itu: FakeItu, tmp_path: Path
) -> None:
    asyncio.run(watcher.check("manual"))
    before = watcher.store.list_files("terrestrial")
    itu.requests.clear()

    result = asyncio.run(watcher.check("manual"))

    assert (result.outcome, result.new_count, result.downloaded_count, result.failed_count) == ("ok", 0, 0, 0)
    sent = {str(r.url): r.headers for r in itu.terra_requests()}
    assert sent[terra_url(3083)]["if-none-match"] == '"brific3083-v1"'
    assert sent[terra_url(3083)]["if-modified-since"] == "Tue, 27 Oct 2026 10:00:00 GMT"
    assert "if-none-match" not in sent[terra_url(3081)]
    assert watcher.store.list_files("terrestrial") == before
    assert (tmp_path / "brific" / "3083" / "brific3083.mdb").read_bytes() == b"brific 3083"


def test_unpublished_issue_stays_new_and_is_fetched_once_it_appears(
    watcher: WatcherService, itu: FakeItu, tmp_path: Path
) -> None:
    asyncio.run(watcher.check("manual"))
    asyncio.run(watcher.check("manual"))
    row = next(f for f in watcher.store.list_files("terrestrial") if f.ific_no == 3081)
    assert (row.status, row.attempts, row.error) == ("new", 0, None)
    assert not (tmp_path / "brific" / "3081").exists()

    itu.serve_terra(3081)
    result = asyncio.run(watcher.check("manual"))

    assert result.downloaded_count == 1
    assert _terra(watcher)[3081] == ("downloaded", 1)


def test_bad_terrestrial_zip_fails_only_that_file(
    watcher: WatcherService, itu: FakeItu, tmp_path: Path
) -> None:
    itu.serve_terra(3082, content=b"not a zip")

    result = asyncio.run(watcher.check("manual"))

    assert (result.outcome, result.failed_count) == ("ok", 1)
    assert _terra(watcher) == {3083: ("downloaded", 1), 3082: ("failed", 1), 3081: ("new", 0)}
    failed = next(f for f in watcher.store.list_files("terrestrial") if f.ific_no == 3082)
    assert "bad zip" in (failed.error or "")
    assert {f.status for f in watcher.store.list_files("space")} == {"downloaded"}
    assert not [p for p in (tmp_path / "brific").rglob("*") if p.suffix in (".part", ".zip")]


def test_terrestrial_switch_off_skips_terrestrial(tmp_path: Path, itu: FakeItu) -> None:
    watcher = WatcherService(_settings(tmp_path, terra_watcher_enabled=False), client_factory=itu.client)

    result = asyncio.run(watcher.check("manual"))

    assert result.downloaded_count == len(SPACE_ISSUES)
    assert watcher.store.list_files("terrestrial") == []
    assert itu.terra_requests() == []
    assert watcher.state().terrestrial_enabled is False


def test_v1_store_migrates_by_adding_terrestrial_table(tmp_path: Path) -> None:
    path = tmp_path / "watcher.sqlite3"
    with sqlite3.connect(path) as con:
        con.execute(
            "CREATE TABLE ific_files (ific_no INTEGER PRIMARY KEY, published_on TEXT, zip_url TEXT NOT NULL, "
            "status TEXT NOT NULL, size_bytes INTEGER, etag TEXT, last_modified TEXT, sha256 TEXT, "
            "mdb_path TEXT, error TEXT, attempts INTEGER NOT NULL DEFAULT 0, discovered_at TEXT NOT NULL, "
            "downloaded_at TEXT)"
        )
        con.execute(
            "INSERT INTO ific_files (ific_no, published_on, zip_url, status, discovered_at) "
            "VALUES (3083, '2026-10-27', 'https://example.test/ific3083.zip', 'downloaded', '2026-10-28')"
        )
        con.execute("PRAGMA user_version = 1")

    store = WatcherStore(path)

    assert [f.ific_no for f in store.list_files("space")] == [3083]
    assert store.list_files("terrestrial") == []
    with sqlite3.connect(path) as con:
        assert con.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 2


def test_api_lists_terrestrial_files_by_kind(
    itu: FakeItu, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "terra_download_dir", tmp_path / "brific")
    asyncio.run(WatcherService(settings, client_factory=itu.client).check("cli"))

    with TestClient(app) as client:
        space = client.get("/api/watcher/files").json()
        terra = client.get("/api/watcher/files", params={"kind": "terrestrial"}).json()
        bad = client.get("/api/watcher/files", params={"kind": "brific"})
        state = client.get("/api/watcher").json()

    assert [f["ific_no"] for f in space] == list(SPACE_ISSUES)
    assert [(f["ific_no"], f["status"]) for f in terra] == [
        (3083, "downloaded"),
        (3082, "downloaded"),
        (3081, "new"),
    ]
    assert terra[0]["local_path"] == "3083/brific3083.mdb"
    assert terra[0]["zip_url"] == terra_url(3083)
    assert bad.status_code == 422
    assert state["terrestrial_enabled"] is True
