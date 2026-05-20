"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from yellowpages import scrape_pages, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


SEARCH_SCHEMA = {
    "data": {"type": "list", "required": True},
    "total_pages": {"type": "integer", "nullable": True, "required": False},
}

PAGE_SCHEMA = {
    "name": {"type": "string", "required": True, "minlength": 1},
    "categories": {"type": "list", "required": False},
    "rating": {"type": "string", "required": False, "nullable": True},
    "ratingCount": {"type": "string", "required": False, "nullable": True},
    "phone": {"type": "string", "required": False, "nullable": True},
    "website": {"type": "string", "required": False, "nullable": True},
    "address": {"type": "string", "required": False, "nullable": True},
    "workingHours": {"type": "dict", "required": False},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    query = os.environ.get("YELLOWPAGES_QUERY", "Plumber")
    location = os.environ.get("YELLOWPAGES_LOCATION", "San Francisco, CA")
    pages = [to_dict(p) for p in await scrape_search(query, location, max_pages=1)]
    assert len(pages) >= 1
    for p in pages:
        _validate(p, SEARCH_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_pages():
    urls = (os.environ.get("YELLOWPAGES_URLS")
            or "https://www.yellowpages.com/san-francisco-ca/mip/abc-plumbing").split(",")
    pages = [to_dict(p) for p in await scrape_pages(urls)]
    assert len(pages) == len(urls)
    for p in pages:
        _validate(p, PAGE_SCHEMA)
