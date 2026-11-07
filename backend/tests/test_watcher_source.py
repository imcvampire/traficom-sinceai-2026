import re
from datetime import date
from pathlib import Path

import pytest

from ific.watcher.source import SourceLayoutError, parse_listings, parse_year_links

FIXTURES = Path(__file__).parent / "fixtures" / "itu"
ROOT_URL = "https://www.itu.int/sns/wic/demowic.html"
PAGE_2026 = "https://www.itu.int/sns/wic/demowic26.html"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_year_links_newest_first() -> None:
    pages = parse_year_links(_fixture("demowic.html"), ROOT_URL)

    assert [p.year for p in pages[:3]] == [2026, 2025, 2024]
    assert pages[0].url == PAGE_2026
    assert pages[-1].year == 1998
    assert len({p.year for p in pages}) == len(pages)


def test_parse_year_links_raises_without_links() -> None:
    with pytest.raises(SourceLayoutError):
        parse_year_links("<html><body>maintenance</body></html>", ROOT_URL)


def test_parse_listings_2026_fixture() -> None:
    listings = parse_listings(_fixture("demowic26.html"), PAGE_2026)

    assert len(listings) == 22
    newest = listings[0]
    assert newest.ific_no == 3083
    assert newest.published_on == date(2026, 10, 27)
    assert newest.zip_url == "https://www.itu.int/sns/ific10/ific3083.zip"
    assert listings[-1].ific_no == 3062
    assert listings[-1].published_on == date(2026, 1, 6)
    assert all(listing.published_on is not None for listing in listings)


def test_parse_listings_raises_on_layout_change() -> None:
    stripped = re.sub(r'<a href="[^"]*ific\d+\.zip">', "<a>", _fixture("demowic26.html"))

    with pytest.raises(SourceLayoutError):
        parse_listings(stripped, PAGE_2026)
