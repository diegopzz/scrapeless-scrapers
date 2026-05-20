"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from tripadvisor import scrape_hotel, scrape_location_data, scrape_search


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


LOCATION_SCHEMA = {
    "localizedName": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True},
}

SEARCH_SCHEMA = {
    "url": {"type": "string", "required": True, "minlength": 1},
    "name": {"type": "string", "required": True, "nullable": True},
}

HOTEL_SCHEMA = {
    "basic_data": {"type": "dict", "required": True},
    "description": {"type": "string", "nullable": True},
    "featues": {"type": "list", "required": True},
    "reviews": {"type": "list", "required": True},
}

REVIEW_SCHEMA = {
    "title": {"type": "string", "nullable": True},
    "text": {"type": "string", "nullable": True},
    "rate": {"type": "float", "nullable": True},
    "tripDate": {"type": "string", "nullable": True},
    "tripType": {"type": "string", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_location():
    query = os.environ.get("TRIPADVISOR_SAMPLE_QUERY", "Malta")
    results = await scrape_location_data(query)
    assert len(results) >= 1
    for r in results:
        _validate(r, LOCATION_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    url = os.environ.get(
        "TRIPADVISOR_SAMPLE_SEARCH_URL",
        "https://www.tripadvisor.com/Hotels-g60763-oa30-New_York_City_New_York-Hotels.html",
    )
    results = await scrape_search(url, max_pages=1)
    assert len(results) >= 1
    for r in results:
        _validate(r, SEARCH_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_hotel():
    url = os.environ.get(
        "TRIPADVISOR_SAMPLE_HOTEL_URL",
        "https://www.tripadvisor.com/Hotel_Review-g190327-d264936-Reviews-1926_Hotel_Spa-Sliema_Island_of_Malta.html",
    )
    hotel = await scrape_hotel(url, max_review_pages=1)
    _validate(hotel, HOTEL_SCHEMA)
    for r in hotel["reviews"]:
        _validate(r, REVIEW_SCHEMA)
