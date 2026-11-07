"""Stream one IFIC or BR IFIC zip to disk, verify it, and extract its .mdb members safely."""

import asyncio
import hashlib
import shutil
import stat
import zipfile
import zlib
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import httpx2

from ific.watcher.source import IficListing

_CHUNK = 1 << 20


class DownloadError(Exception):
    """A single IFIC file could not be downloaded or extracted; other files are unaffected."""


class NotPublished(DownloadError):
    """The server answered 404. For a derived terrestrial URL this means the issue is not out yet."""


class NotModified(Exception):
    """The server answered 304 to a conditional request: the file already on disk is current."""


def describe_error(e: BaseException) -> str:
    """Error text safe to store and show in the UI: OS errors lose their absolute paths."""
    if isinstance(e, OSError) and e.strerror:
        name = f" ({Path(str(e.filename)).name})" if e.filename else ""
        return f"{type(e).__name__}: {e.strerror}{name}"
    return f"{type(e).__name__}: {e}"


@dataclass(frozen=True)
class DownloadResult:
    zip_bytes: int
    sha256: str
    mdb_paths: list[Path]
    mdb_bytes: int
    etag: str | None
    last_modified: str | None


def _safe_member_name(info: zipfile.ZipInfo) -> str:
    name = info.filename.replace("\\", "/")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        raise DownloadError(f"unsafe path in zip: {info.filename!r}")
    if stat.S_ISLNK(info.external_attr >> 16):
        raise DownloadError(f"symlink in zip: {info.filename!r}")
    return path.name


def _extract_mdbs(zip_path: Path, dest: Path, single_name: str, max_bytes: int) -> list[Path]:
    try:
        with zipfile.ZipFile(zip_path) as zf:
            members = [i for i in zf.infolist() if not i.is_dir() and i.filename.lower().endswith(".mdb")]
            if not members:
                raise DownloadError("zip contains no .mdb file")
            names = [_safe_member_name(i) for i in members]
            if len(names) == 1:
                names = [single_name]
            if len(set(names)) != len(names):
                raise DownloadError("zip contains duplicate .mdb names")
            if sum(i.file_size for i in members) > max_bytes:
                raise DownloadError(f"uncompressed .mdb size exceeds {max_bytes} bytes")
            extracted: list[Path] = []
            for info, name in zip(members, names, strict=True):
                part = dest / f"{name}.part"
                with zf.open(info) as src, part.open("wb") as out:
                    shutil.copyfileobj(src, out, _CHUNK)
                final = dest / name
                part.replace(final)
                extracted.append(final)
            return extracted
    except (zipfile.BadZipFile, zlib.error, EOFError, RuntimeError, NotImplementedError) as e:
        raise DownloadError(f"bad zip: {type(e).__name__}: {e}") from e


def _cleanup(dest: Path, zip_path: Path) -> None:
    zip_path.unlink(missing_ok=True)
    for part in dest.glob("*.part"):
        part.unlink(missing_ok=True)


async def download_and_extract(
    client: httpx2.AsyncClient,
    listing: IficListing,
    dest_dir: Path,
    max_bytes: int,
    *,
    prefix: str = "ific",
    etag: str | None = None,
    last_modified: str | None = None,
) -> DownloadResult:
    """Save `<dest_dir>/<no>/<prefix><no>.mdb`. With `etag` or `last_modified` the request is conditional.

    Raises NotModified on 304, NotPublished on 404 and DownloadError on any other failure.
    """
    dest = dest_dir / str(listing.ific_no)
    zip_path = dest / f"{prefix}{listing.ific_no}.zip"
    zip_part = dest / f"{prefix}{listing.ific_no}.zip.part"
    headers: dict[str, str] = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    try:
        digest = hashlib.sha256()
        received = 0
        async with client.stream("GET", listing.zip_url, headers=headers) as response:
            if response.status_code == 304 and headers:
                raise NotModified(listing.zip_url)
            if response.status_code == 404:
                raise NotPublished(f"HTTP 404 for {listing.zip_url}")
            if response.status_code != 200:
                raise DownloadError(f"HTTP {response.status_code} for {listing.zip_url}")
            # Created only once there is a body, so a 304 or 404 leaves no empty directory behind.
            dest.mkdir(parents=True, exist_ok=True)
            declared = response.headers.get("content-length")
            # A content-encoded body is decoded on read, so its length is not comparable to the header.
            encoded = response.headers.get("content-encoding", "identity") != "identity"
            expected = int(declared) if declared and declared.isdigit() and not encoded else None
            if expected is not None and expected > max_bytes:
                raise DownloadError(f"declared size {expected} exceeds {max_bytes} bytes")
            with zip_part.open("wb") as out:
                async for chunk in response.aiter_bytes(_CHUNK):
                    received += len(chunk)
                    if received > max_bytes:
                        raise DownloadError(f"download exceeds {max_bytes} bytes")
                    digest.update(chunk)
                    out.write(chunk)
            etag = response.headers.get("etag")
            last_modified = response.headers.get("last-modified")
        if expected is not None and received != expected:
            raise DownloadError(f"size mismatch: received {received} of {expected} bytes")
        zip_part.replace(zip_path)
        extraction = asyncio.ensure_future(
            asyncio.to_thread(_extract_mdbs, zip_path, dest, f"{prefix}{listing.ific_no}.mdb", max_bytes)
        )
        try:
            mdb_paths = await asyncio.shield(extraction)
        except asyncio.CancelledError:
            # The worker thread cannot be cancelled; let it finish before cleanup removes its files.
            with suppress(Exception):
                await extraction
            raise
        zip_path.unlink()
        return DownloadResult(
            zip_bytes=received,
            sha256=digest.hexdigest(),
            mdb_paths=mdb_paths,
            mdb_bytes=sum(p.stat().st_size for p in mdb_paths),
            etag=etag,
            last_modified=last_modified,
        )
    except NotModified:
        raise
    except DownloadError:
        _cleanup(dest, zip_path)
        raise
    except (httpx2.HTTPError, OSError) as e:
        _cleanup(dest, zip_path)
        raise DownloadError(describe_error(e)) from e
    except BaseException:
        _cleanup(dest, zip_path)
        raise
