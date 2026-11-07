"""SQLite state for the IFIC source watcher, shared by the API process and the CLI."""

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from ific.watcher.source import IficListing

FileStatus = Literal["new", "downloading", "downloaded", "failed"]
FileKind = Literal["space", "terrestrial"]
RunTrigger = Literal["schedule", "manual", "cli"]
RunOutcome = Literal["ok", "error", "skipped"]

# v2 added brific_files. Every table is CREATE IF NOT EXISTS, so running the schema on a v1 store is the
# whole migration: it creates the new table and leaves the existing rows alone.
SCHEMA_VERSION = 2

_FILE_TABLES: dict[FileKind, str] = {"space": "ific_files", "terrestrial": "brific_files"}

_FILE_COLUMNS = """(
    ific_no       INTEGER PRIMARY KEY,
    published_on  TEXT,
    zip_url       TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('new', 'downloading', 'downloaded', 'failed')),
    size_bytes    INTEGER,
    etag          TEXT,
    last_modified TEXT,
    sha256        TEXT,
    mdb_path      TEXT,
    error         TEXT,
    attempts      INTEGER NOT NULL DEFAULT 0,
    discovered_at TEXT NOT NULL,
    downloaded_at TEXT
)"""

_SCHEMA = (
    "".join(f"CREATE TABLE IF NOT EXISTS {t} {_FILE_COLUMNS};\n" for t in _FILE_TABLES.values())
    + """
CREATE TABLE IF NOT EXISTS watcher_runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at       TEXT NOT NULL,
    finished_at      TEXT NOT NULL,
    trigger          TEXT NOT NULL CHECK (trigger IN ('schedule', 'manual', 'cli')),
    outcome          TEXT NOT NULL CHECK (outcome IN ('ok', 'error', 'skipped')),
    new_count        INTEGER NOT NULL DEFAULT 0,
    downloaded_count INTEGER NOT NULL DEFAULT 0,
    failed_count     INTEGER NOT NULL DEFAULT 0,
    error            TEXT
);
CREATE TABLE IF NOT EXISTS kv (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""
)

_UI_ENABLED_KEY = "ui_enabled"
_PAGE_KEY_PREFIX = "page:"


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class FileRow:
    ific_no: int
    published_on: date | None
    zip_url: str
    status: FileStatus
    size_bytes: int | None
    sha256: str | None
    mdb_path: str | None
    error: str | None
    attempts: int
    discovered_at: datetime
    downloaded_at: datetime | None
    etag: str | None
    last_modified: str | None


@dataclass(frozen=True)
class RunRow:
    started_at: datetime
    finished_at: datetime
    trigger: RunTrigger
    outcome: RunOutcome
    new_count: int
    downloaded_count: int
    failed_count: int
    error: str | None


@dataclass(frozen=True)
class CachedPage:
    etag: str | None
    body: str


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _file_row(row: sqlite3.Row) -> FileRow:
    return FileRow(
        ific_no=row["ific_no"],
        published_on=date.fromisoformat(row["published_on"]) if row["published_on"] else None,
        zip_url=row["zip_url"],
        status=row["status"],
        size_bytes=row["size_bytes"],
        sha256=row["sha256"],
        mdb_path=row["mdb_path"],
        error=row["error"],
        attempts=row["attempts"],
        discovered_at=datetime.fromisoformat(row["discovered_at"]),
        downloaded_at=_dt(row["downloaded_at"]),
        etag=row["etag"],
        last_modified=row["last_modified"],
    )


class WatcherStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            version = con.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, SCHEMA_VERSION):
                raise RuntimeError(
                    f"{path} has watcher schema v{version}, expected v{SCHEMA_VERSION}; delete it to reset"
                )
            con.executescript(_SCHEMA)
            con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA journal_mode = WAL")
            with con:
                yield con
        finally:
            con.close()

    def upsert_listings(self, newest: Iterable[IficListing], older: Iterable[IficListing] = ()) -> int:
        """Record newly published issues and return how many were added.

        On an empty store only the newest year page counts. Afterwards a listing is new only when it
        is above the lowest stored IFIC number, so an older year's backlog is never pulled in.
        """
        now = utcnow().isoformat()
        with self._connect() as con:
            known = {r[0] for r in con.execute("SELECT ific_no FROM ific_files")}
            candidates = list(newest) if not known else [*newest, *older]
            floor = min(known, default=None)
            fresh = {
                listing.ific_no: listing
                for listing in candidates
                if listing.ific_no not in known and (floor is None or listing.ific_no > floor)
            }
            con.executemany(
                "INSERT INTO ific_files (ific_no, published_on, zip_url, status, discovered_at) "
                "VALUES (?, ?, ?, 'new', ?)",
                [
                    (
                        listing.ific_no,
                        listing.published_on.isoformat() if listing.published_on else None,
                        listing.zip_url,
                        now,
                    )
                    for listing in fresh.values()
                ],
            )
        return len(fresh)

    def derive_terrestrial(self, since: date, url_template: str) -> int:
        """Add a terrestrial row for every Space issue published on or after `since`; return how many.

        The terrestrial BR IFIC shares its issue numbers with the Space IFIC, so the Space listing is the
        only index needed and the terrestrial page itself is never scraped.
        """
        now = utcnow().isoformat()
        with self._connect() as con:
            space = con.execute(
                "SELECT ific_no, published_on FROM ific_files WHERE published_on >= ?", (since.isoformat(),)
            ).fetchall()
            return con.executemany(
                "INSERT OR IGNORE INTO brific_files (ific_no, published_on, zip_url, status, discovered_at) "
                "VALUES (?, ?, ?, 'new', ?)",
                [(r[0], r[1], url_template.format(no=r[0]), now) for r in space],
            ).rowcount

    def pending_downloads(self, kind: FileKind = "space") -> list[FileRow]:
        with self._connect() as con:
            rows = con.execute(
                f"SELECT * FROM {_FILE_TABLES[kind]} WHERE status IN ('new', 'failed') ORDER BY ific_no DESC"
            ).fetchall()
        return [_file_row(r) for r in rows]

    def list_files(self, kind: FileKind = "space") -> list[FileRow]:
        with self._connect() as con:
            rows = con.execute(f"SELECT * FROM {_FILE_TABLES[kind]} ORDER BY ific_no DESC").fetchall()
        return [_file_row(r) for r in rows]

    def mark_downloading(self, ific_no: int, kind: FileKind = "space") -> None:
        with self._connect() as con:
            con.execute(
                f"UPDATE {_FILE_TABLES[kind]} SET status = 'downloading', attempts = attempts + 1, "
                "error = NULL WHERE ific_no = ?",
                (ific_no,),
            )

    def mark_downloaded(
        self,
        ific_no: int,
        *,
        size_bytes: int,
        sha256: str,
        mdb_path: Path,
        etag: str | None,
        last_modified: str | None,
        kind: FileKind = "space",
    ) -> None:
        with self._connect() as con:
            con.execute(
                f"UPDATE {_FILE_TABLES[kind]} SET status = 'downloaded', size_bytes = ?, sha256 = ?, "
                "mdb_path = ?, etag = ?, last_modified = ?, error = NULL, downloaded_at = ? "
                "WHERE ific_no = ?",
                (size_bytes, sha256, str(mdb_path), etag, last_modified, utcnow().isoformat(), ific_no),
            )

    def mark_unchanged(self, ific_no: int, kind: FileKind = "space") -> None:
        """The server answered 304: the file on disk is current."""
        with self._connect() as con:
            con.execute(
                f"UPDATE {_FILE_TABLES[kind]} SET status = 'downloaded', error = NULL WHERE ific_no = ?",
                (ific_no,),
            )

    def mark_not_published(self, ific_no: int, kind: FileKind = "space") -> None:
        """The server answered 404: back to `new`, and the attempt `mark_downloading` counted is undone."""
        with self._connect() as con:
            con.execute(
                f"UPDATE {_FILE_TABLES[kind]} SET status = 'new', error = NULL, "
                "attempts = MAX(attempts - 1, 0) WHERE ific_no = ?",
                (ific_no,),
            )

    def mark_failed(self, ific_no: int, error: str, kind: FileKind = "space") -> None:
        with self._connect() as con:
            con.execute(
                f"UPDATE {_FILE_TABLES[kind]} SET status = 'failed', error = ? WHERE ific_no = ?",
                (error, ific_no),
            )

    def reset_stale_downloading(self) -> int:
        with self._connect() as con:
            return sum(
                con.execute(
                    f"UPDATE {table} SET status = 'failed', error = 'interrupted by restart' "
                    "WHERE status = 'downloading'"
                ).rowcount
                for table in _FILE_TABLES.values()
            )

    def get_ui_enabled(self) -> bool | None:
        value = self._get_kv(_UI_ENABLED_KEY)
        return None if value is None else value == "true"

    def set_ui_enabled(self, enabled: bool) -> None:
        self._set_kv(_UI_ENABLED_KEY, "true" if enabled else "false")

    def get_page(self, url: str) -> CachedPage | None:
        value = self._get_kv(_PAGE_KEY_PREFIX + url)
        return CachedPage(**json.loads(value)) if value else None

    def set_page(self, url: str, page: CachedPage) -> None:
        self._set_kv(_PAGE_KEY_PREFIX + url, json.dumps({"etag": page.etag, "body": page.body}))

    def record_run(self, run: RunRow) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO watcher_runs (started_at, finished_at, trigger, outcome, new_count, "
                "downloaded_count, failed_count, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run.started_at.isoformat(),
                    run.finished_at.isoformat(),
                    run.trigger,
                    run.outcome,
                    run.new_count,
                    run.downloaded_count,
                    run.failed_count,
                    run.error,
                ),
            )

    def last_run(self) -> RunRow | None:
        with self._connect() as con:
            row = con.execute("SELECT * FROM watcher_runs ORDER BY id DESC LIMIT 1").fetchone()
        if row is None:
            return None
        return RunRow(
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=datetime.fromisoformat(row["finished_at"]),
            trigger=row["trigger"],
            outcome=row["outcome"],
            new_count=row["new_count"],
            downloaded_count=row["downloaded_count"],
            failed_count=row["failed_count"],
            error=row["error"],
        )

    def _get_kv(self, key: str) -> str | None:
        with self._connect() as con:
            row = con.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def _set_kv(self, key: str, value: str) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO kv (key, value) VALUES (?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
