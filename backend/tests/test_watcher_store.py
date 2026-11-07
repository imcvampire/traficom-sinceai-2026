import sqlite3
from datetime import date
from pathlib import Path

import pytest

from ific.watcher.source import IficListing
from ific.watcher.store import WatcherStore


def _listing(no: int) -> IficListing:
    return IficListing(no, date(2026, 1, 1), f"https://www.itu.int/sns/ific10/ific{no}.zip")


@pytest.fixture
def store(tmp_path: Path) -> WatcherStore:
    return WatcherStore(tmp_path / "watcher.sqlite3")


def test_store_first_run_inserts_all_newest_page_rows_as_new(store: WatcherStore) -> None:
    newest = [_listing(n) for n in (3064, 3063, 3062)]
    older = [_listing(n) for n in (3061, 3060)]

    assert store.upsert_listings(newest, older) == 3
    assert [f.ific_no for f in store.pending_downloads()] == [3064, 3063, 3062]
    assert {f.status for f in store.list_files()} == {"new"}


def test_store_ignores_older_backlog_after_first_run(store: WatcherStore) -> None:
    store.upsert_listings([_listing(3063), _listing(3062)])

    added = store.upsert_listings([_listing(3065), _listing(3064)], [_listing(3061), _listing(3063)])

    assert added == 2
    assert [f.ific_no for f in store.list_files()] == [3065, 3064, 3063, 3062]


def test_store_upsert_is_idempotent(store: WatcherStore) -> None:
    store.upsert_listings([_listing(3062)])

    assert store.upsert_listings([_listing(3062)]) == 0


def test_store_ui_override_roundtrip_and_absent_is_none(store: WatcherStore, tmp_path: Path) -> None:
    assert store.get_ui_enabled() is None

    store.set_ui_enabled(False)
    assert WatcherStore(tmp_path / "watcher.sqlite3").get_ui_enabled() is False

    store.set_ui_enabled(True)
    assert store.get_ui_enabled() is True


def test_store_reset_stale_downloading_to_failed(store: WatcherStore) -> None:
    store.upsert_listings([_listing(3063), _listing(3062)])
    store.mark_downloading(3063)

    assert store.reset_stale_downloading() == 1
    row = store.list_files()[0]
    assert row.status == "failed"
    assert row.error == "interrupted by restart"
    assert row.attempts == 1
    assert [f.ific_no for f in store.pending_downloads()] == [3063, 3062]


def test_store_rejects_unknown_schema_version(tmp_path: Path) -> None:

    path = tmp_path / "watcher.sqlite3"
    with sqlite3.connect(path) as con:
        con.execute("PRAGMA user_version = 99")

    with pytest.raises(RuntimeError, match="schema v99"):
        WatcherStore(path)
