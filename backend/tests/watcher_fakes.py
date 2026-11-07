"""In-memory stand-in for the ITU Space IFIC and terrestrial BR IFIC sites, served via httpx2.MockTransport.

Any URL not served answers 404, which for a terrestrial zip means "not published yet".
"""

import io
import zipfile
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx2

ROOT_URL = "https://www.itu.int/sns/wic/demowic.html"
ROOT_HTML = (Path(__file__).parent / "fixtures" / "itu" / "demowic.html").read_text(encoding="utf-8")

Handler = Callable[[httpx2.Request], httpx2.Response | Awaitable[httpx2.Response]]


def zip_url(no: int) -> str:
    return f"https://www.itu.int/sns/ific10/ific{no}.zip"


def terra_url(no: int) -> str:
    return f"https://www.itu.int/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific{no}.zip"


def year_page(*rows: tuple[str, int]) -> str:
    body = "".join(
        f'<tr><td><b>{published}</b></td><td><b><a href="../ific10/ific{no}.zip">{no}</a></b></td></tr>'
        for published, no in rows
    )
    return f"<html><body><table><tr><th>Publication Date</th></tr>{body}</table></body></html>"


def make_zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


class FakeItu:
    def __init__(self) -> None:
        self.pages: dict[str, str] = {
            ROOT_URL: ROOT_HTML,
            "https://www.itu.int/sns/wic/demowic26.html": year_page(
                ("27.10.2026", 3083), ("13.10.2026", 3082)
            ),
            "https://www.itu.int/sns/wic/demowic25.html": year_page(("16.12.2025", 3061)),
        }
        self.etags: dict[str, str] = {}
        self.files: dict[str, httpx2.Response] = {}
        # Validators of served files: a matching If-None-Match or If-Modified-Since answers 304.
        self.file_validators: dict[str, tuple[str, str]] = {}
        self.requests: list[httpx2.Request] = []
        self.override: Handler | None = None

    def serve_zip(self, no: int, members: dict[str, bytes] | None = None) -> None:
        content = make_zip(members if members is not None else {f"ific{no}.mdb": f"mdb {no}".encode()})
        self.files[zip_url(no)] = httpx2.Response(200, content=content)

    def serve_terra(self, no: int, content: bytes | None = None) -> None:
        url = terra_url(no)
        etag, last_modified = f'"brific{no}-v1"', "Tue, 27 Oct 2026 10:00:00 GMT"
        body = content if content is not None else make_zip({f"brific{no}.mdb": f"brific {no}".encode()})
        self.files[url] = httpx2.Response(
            200, content=body, headers={"etag": etag, "last-modified": last_modified}
        )
        self.file_validators[url] = (etag, last_modified)

    async def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.override is not None:
            response = self.override(request)
            return response if isinstance(response, httpx2.Response) else await response
        url = str(request.url)
        if url in self.pages:
            etag = self.etags.get(url)
            if etag and request.headers.get("if-none-match") == etag:
                return httpx2.Response(304)
            return httpx2.Response(200, text=self.pages[url], headers={"etag": etag} if etag else {})
        if url in self.files:
            validators = self.file_validators.get(url)
            if validators and (
                request.headers.get("if-none-match") == validators[0]
                or request.headers.get("if-modified-since") == validators[1]
            ):
                return httpx2.Response(304)
            return self.files[url]
        return httpx2.Response(404)

    def zip_requests(self) -> list[str]:
        """Space IFIC zip requests only; terrestrial ones are in terra_requests()."""
        return [str(r.url) for r in self.requests if str(r.url).endswith(".zip") and "/sns/" in str(r.url)]

    def terra_requests(self) -> list[httpx2.Request]:
        return [r for r in self.requests if "/terrestrial/" in str(r.url)]

    def client(self) -> httpx2.AsyncClient:
        return httpx2.AsyncClient(transport=httpx2.MockTransport(self.handle))
