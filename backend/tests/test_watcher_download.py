import asyncio
import contextlib
import io
import sqlite3
import zipfile
from pathlib import Path

import httpx2
import pytest
from watcher_fakes import ROOT_URL, FakeItu, make_zip, year_page, zip_url

from ific.config import Settings
from ific.watcher.download import describe_error
from ific.watcher.service import WatcherService, _process_lock
from ific.watcher.store import WatcherStore

PAGE_2026 = "https://www.itu.int/sns/wic/demowic26.html"
PAGE_2025 = "https://www.itu.int/sns/wic/demowic25.html"


@pytest.fixture
def itu() -> FakeItu:
    fake = FakeItu()
    fake.serve_zip(3083)
    fake.serve_zip(3082)
    return fake


@pytest.fixture
def watcher(tmp_path: Path, itu: FakeItu) -> WatcherService:
    settings = Settings(
        watcher_enabled=True,
        watcher_state_path=tmp_path / "state" / "watcher.sqlite3",
        watcher_download_dir=tmp_path / "ific",
    )
    return WatcherService(settings, client_factory=itu.client)


def _files(watcher: WatcherService) -> dict[int, str]:
    return {f.ific_no: f.status for f in watcher.store.list_files()}


def _leftovers(root: Path) -> list[str]:
    return sorted(p.name for p in root.rglob("*") if p.suffix in (".part", ".zip"))


def test_check_downloads_new_and_is_idempotent(watcher: WatcherService, itu: FakeItu, tmp_path: Path) -> None:
    first = asyncio.run(watcher.check("manual"))

    assert (first.outcome, first.new_count, first.downloaded_count, first.failed_count) == ("ok", 2, 2, 0)
    assert _files(watcher) == {3083: "downloaded", 3082: "downloaded"}
    mdb = tmp_path / "ific" / "3083" / "ific3083.mdb"
    assert mdb.read_bytes() == b"mdb 3083"
    assert watcher.store.list_files()[0].mdb_path == str(mdb)
    assert _leftovers(tmp_path / "ific") == []
    assert itu.zip_requests() == [zip_url(3083), zip_url(3082)]

    itu.requests.clear()
    second = asyncio.run(watcher.check("manual"))

    assert (second.outcome, second.new_count, second.downloaded_count) == ("ok", 0, 0)
    assert itu.zip_requests() == []


def test_new_issue_on_later_run_is_downloaded(watcher: WatcherService, itu: FakeItu) -> None:
    asyncio.run(watcher.check("schedule"))
    itu.pages[PAGE_2026] = year_page(("10.11.2026", 3084), ("27.10.2026", 3083), ("13.10.2026", 3082))
    itu.serve_zip(3084)

    result = asyncio.run(watcher.check("schedule"))

    assert (result.new_count, result.downloaded_count) == (1, 1)
    assert 3061 not in _files(watcher)


def test_size_mismatch_marks_failed_and_leaves_no_part_file(
    watcher: WatcherService, itu: FakeItu, tmp_path: Path
) -> None:
    content = make_zip({"ific3083.mdb": b"x"})
    itu.files[zip_url(3083)] = httpx2.Response(
        200, content=content, headers={"content-length": str(len(content) + 10)}
    )

    result = asyncio.run(watcher.check("manual"))

    assert result.failed_count == 1
    row = next(f for f in watcher.store.list_files() if f.ific_no == 3083)
    assert row.status == "failed"
    assert "size mismatch" in (row.error or "")
    assert _leftovers(tmp_path / "ific") == []
    assert not (tmp_path / "ific" / "3083" / "ific3083.mdb").exists()


def test_zip_slip_member_rejected(watcher: WatcherService, itu: FakeItu, tmp_path: Path) -> None:
    itu.serve_zip(3083, {"../../evil.mdb": b"pwned"})

    asyncio.run(watcher.check("manual"))

    row = next(f for f in watcher.store.list_files() if f.ific_no == 3083)
    assert row.status == "failed"
    assert "unsafe path" in (row.error or "")
    assert not list(tmp_path.rglob("evil.mdb*"))


def _corrupt_deflate_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ific3083.mdb", b"x" * 4096)
    data = bytearray(buf.getvalue())
    data[40:48] = b"\xff" * 8  # inside the compressed stream; headers stay valid
    return bytes(data)


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (httpx2.Response(200, content=b"not a zip"), "bad zip"),
        (httpx2.Response(200, content=make_zip({"readme.txt": b"hi"})), "no .mdb"),
        (httpx2.Response(503), "HTTP 503"),
        (httpx2.Response(200, content=_corrupt_deflate_zip()), "bad zip"),
    ],
)
def test_one_failure_does_not_block_other_files(
    watcher: WatcherService, itu: FakeItu, response: httpx2.Response, reason: str
) -> None:
    itu.files[zip_url(3083)] = response

    result = asyncio.run(watcher.check("manual"))

    assert (result.outcome, result.downloaded_count, result.failed_count) == ("ok", 1, 1)
    assert _files(watcher) == {3083: "failed", 3082: "downloaded"}
    assert reason in (watcher.store.list_files()[0].error or "")

    itu.serve_zip(3083)
    retry = asyncio.run(watcher.check("manual"))

    assert retry.downloaded_count == 1
    assert _files(watcher) == {3083: "downloaded", 3082: "downloaded"}
    assert watcher.store.list_files()[0].attempts == 2


def test_oversized_download_rejected(tmp_path: Path, itu: FakeItu) -> None:
    settings = Settings(
        watcher_state_path=tmp_path / "watcher.sqlite3",
        watcher_download_dir=tmp_path / "ific",
        watcher_max_download_bytes=50,
    )
    watcher = WatcherService(settings, client_factory=itu.client)

    asyncio.run(watcher.check("manual"))

    assert set(_files(watcher).values()) == {"failed"}
    assert _leftovers(tmp_path / "ific") == []


def test_page_304_uses_etag(watcher: WatcherService, itu: FakeItu) -> None:
    itu.etags[ROOT_URL] = '"root-v1"'
    asyncio.run(watcher.check("manual"))
    itu.requests.clear()

    result = asyncio.run(watcher.check("manual"))

    root_request = next(r for r in itu.requests if str(r.url) == ROOT_URL)
    assert root_request.headers["if-none-match"] == '"root-v1"'
    assert result.outcome == "ok"


def test_empty_new_year_page_falls_back_to_previous_year(watcher: WatcherService, itu: FakeItu) -> None:
    itu.pages[PAGE_2026] = "<html><table><tr><td>No databases yet</td></tr></table>"
    itu.serve_zip(3061)

    result = asyncio.run(watcher.check("schedule"))

    assert (result.outcome, result.new_count, result.downloaded_count) == ("ok", 1, 1)
    assert _files(watcher) == {3061: "downloaded"}


def test_layout_change_is_reported_as_error(watcher: WatcherService, itu: FakeItu) -> None:
    for url in (PAGE_2026, PAGE_2025):
        itu.pages[url] = "<html><table><tr><td>moved</td></tr></table>"

    result = asyncio.run(watcher.check("schedule"))

    assert result.outcome == "error"
    assert "SourceLayoutError" in (result.error or "")
    assert watcher.store.last_run().outcome == "error"  # type: ignore[union-attr]


def test_second_process_skips_while_lock_held(watcher: WatcherService, tmp_path: Path) -> None:
    other = WatcherService(watcher.settings, store=WatcherStore(watcher.settings.watcher_state_path))

    async def both() -> tuple[str, str]:
        gate = asyncio.Event()
        original = watcher._fetch_page

        async def slow_fetch(client, url):  # type: ignore[no-untyped-def]
            gate.set()
            await asyncio.sleep(0.05)
            return await original(client, url)

        watcher._fetch_page = slow_fetch  # type: ignore[method-assign]
        first = asyncio.create_task(watcher.check("schedule"))
        await gate.wait()
        second = await other.check("cli")
        return (await first).outcome, second.outcome

    assert asyncio.run(both()) == ("ok", "skipped")


def test_pause_mid_run_stops_remaining_scheduled_downloads(watcher: WatcherService, itu: FakeItu) -> None:
    original = itu.handle

    async def handle(request: httpx2.Request) -> httpx2.Response:
        if str(request.url) == zip_url(3083):
            watcher.set_ui_enabled(False)
        return await original(request)

    itu.handle = handle  # type: ignore[method-assign]

    result = asyncio.run(watcher.check("schedule"))

    assert (result.downloaded_count, result.failed_count) == (1, 0)
    assert _files(watcher) == {3083: "downloaded", 3082: "new"}
    assert itu.zip_requests() == [zip_url(3083)]


def test_single_member_is_renamed_to_ific_number(
    watcher: WatcherService, itu: FakeItu, tmp_path: Path
) -> None:
    itu.serve_zip(3083, {"data/SRS_IFIC.MDB": b"renamed"})

    asyncio.run(watcher.check("manual"))

    assert (tmp_path / "ific" / "3083" / "ific3083.mdb").read_bytes() == b"renamed"


def test_os_error_text_hides_absolute_paths() -> None:
    error = describe_error(
        FileNotFoundError(2, "No such file or directory", "/abs/secret/dir/ific3083.zip.part")
    )

    assert error == "FileNotFoundError: No such file or directory (ific3083.zip.part)"


def test_running_reflects_check_held_by_another_process(watcher: WatcherService) -> None:
    with _process_lock(watcher.settings.watcher_state_path.with_name("watcher.lock")) as acquired:
        assert acquired
        assert watcher.running is True
        assert watcher.request_check() is False
    assert watcher.running is False


def test_scheduler_loop_survives_iteration_error(watcher: WatcherService, itu: FakeItu) -> None:
    calls = 0
    original = watcher.is_enabled

    def flaky() -> bool:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise sqlite3.OperationalError("database is locked")
        return original()

    watcher.is_enabled = flaky  # type: ignore[method-assign]

    async def scenario() -> None:
        task = asyncio.create_task(watcher.run_forever())
        while calls == 0:
            await asyncio.sleep(0.01)
        assert not task.done()
        assert watcher.request_check()
        while watcher.store.last_run() is None:
            await asyncio.sleep(0.01)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    asyncio.run(scenario())

    assert watcher.store.last_run().trigger == "manual"  # type: ignore[union-attr]


def test_resume_when_already_enabled_does_not_wake_scheduler(watcher: WatcherService) -> None:
    async def scenario() -> tuple[bool, bool]:
        watcher.set_ui_enabled(True)
        noop = watcher._wake.is_set()
        watcher.set_ui_enabled(False)
        watcher._wake.clear()
        watcher.set_ui_enabled(True)
        return noop, watcher._wake.is_set()

    assert asyncio.run(scenario()) == (False, True)
