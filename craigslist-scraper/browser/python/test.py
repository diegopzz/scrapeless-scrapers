"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from craigslist import scrape_listing, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


SEARCH_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "title": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True},
    "price": {"type": "string", "nullable": True},
    "location": {"type": "string", "nullable": True},
    "postedAt": {"type": "string", "nullable": True},
    "image": {"type": "string", "nullable": True},
}

LISTING_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True},
    "title": {"type": "string", "required": True, "minlength": 1},
    "description": {"type": "string", "required": True},
    "attributes": {"type": "list", "required": True},
    "images": {"type": "list", "required": True},
    "price": {"type": "string", "nullable": True},
    "location": {"type": "string", "nullable": True},
    "postedAt": {"type": "string", "nullable": True},
    "latitude": {"type": "string", "nullable": True},
    "longitude": {"type": "string", "nullable": True},
    "section": {"type": "string", "nullable": True},
    "category": {"type": "string", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=2, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    sample_city = os.environ.get("CRAIGSLIST_SAMPLE_CITY", "newyork")
    sample_category = os.environ.get("CRAIGSLIST_SAMPLE_CATEGORY", "sss")
    sample_query = os.environ.get("CRAIGSLIST_SAMPLE_QUERY", "bicycle")
    results = [to_dict(r) for r in await scrape_search(sample_city, sample_category, sample_query, 1)]
    assert len(results) >= 1, "expected at least one search result"
    for r in results:
        _validate(r, SEARCH_SCHEMA)


@pytest.mark.flaky(reruns=2, reruns_delay=30)
@pytest.mark.asyncio
async def test_listing():
    sample_city = os.environ.get("CRAIGSLIST_SAMPLE_CITY", "newyork")
    sample_category = os.environ.get("CRAIGSLIST_SAMPLE_CATEGORY", "sss")
    sample_query = os.environ.get("CRAIGSLIST_SAMPLE_QUERY", "bicycle")
    results = await scrape_search(sample_city, sample_category, sample_query, 1)
    assert results, "no search results to derive a listing URL from"
    listing = to_dict(await scrape_listing(results[0].url))
    _validate(listing, LISTING_SCHEMA)
    assert listing["url"] == results[0].url
