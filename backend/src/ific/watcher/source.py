"""Parse the ITU Space IFIC download pages (root page -> year pages -> per-issue zip rows)."""

import re
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urljoin

_YEAR_HREF_RE = re.compile(r"demowic(\d{2})\.html$")
_ZIP_HREF_RE = re.compile(r"ific(\d+)\.zip$", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")


class SourceLayoutError(ValueError):
    """The page no longer has the structure the parser relies on."""


@dataclass(frozen=True)
class YearPage:
    year: int
    url: str


@dataclass(frozen=True)
class IficListing:
    ific_no: int
    published_on: date | None
    zip_url: str


@dataclass
class _Row:
    hrefs: list[str]
    text: list[str]


class _RowParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[_Row] = []
        self.hrefs: list[str] = []
        self._row: _Row | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._close_row()
            self._row = _Row([], [])
        elif tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)
                if self._row is not None:
                    self._row.hrefs.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("tr", "table"):
            self._close_row()

    def handle_data(self, data: str) -> None:
        if self._row is not None:
            self._row.text.append(data)

    def close(self) -> None:
        super().close()
        self._close_row()

    def _close_row(self) -> None:
        if self._row is not None:
            self.rows.append(self._row)
            self._row = None


def _parse(html: str) -> _RowParser:
    parser = _RowParser()
    parser.feed(html)
    parser.close()
    return parser


def parse_year_links(html: str, base_url: str) -> list[YearPage]:
    pages: dict[int, YearPage] = {}
    for href in _parse(html).hrefs:
        match = _YEAR_HREF_RE.search(href)
        if match:
            yy = int(match.group(1))
            year = (1900 if yy >= 98 else 2000) + yy
            pages[year] = YearPage(year, urljoin(base_url, href))
    if not pages:
        raise SourceLayoutError(f"no demowicYY.html year links found on {base_url}")
    return sorted(pages.values(), key=lambda p: p.year, reverse=True)


def parse_listings(html: str, page_url: str) -> list[IficListing]:
    listings: dict[int, IficListing] = {}
    for row in _parse(html).rows:
        for href in row.hrefs:
            match = _ZIP_HREF_RE.search(href)
            if not match:
                continue
            ific_no = int(match.group(1))
            date_match = _DATE_RE.search(" ".join(row.text))
            published_on = None
            if date_match:
                day, month, year = (int(g) for g in date_match.groups())
                try:
                    published_on = date(year, month, day)
                except ValueError:
                    published_on = None
            listings.setdefault(ific_no, IficListing(ific_no, published_on, urljoin(page_url, href)))
    if not listings:
        raise SourceLayoutError(f"no ificNNNN.zip rows found on {page_url}")
    return sorted(listings.values(), key=lambda listing: listing.ific_no, reverse=True)
