"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import datetime
import os

import pytest
from cerberus import Validator

from bookingcom import scrape_hotel, scrape_hotel_reviews, scrape_search, search_location_suggestions


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


LOCATION_SCHEMA = {
    "dest_id": {"type": "string", "required": True, "minlength": 1},
    "dest_type": {"type": "string", "required": True},
    "value": {"type": "string", "required": True},
}

SEARCH_SCHEMA = {
    "displayName": {
        "type": "dict",
        "required": True,
        "schema": {"text": {"type": "string", "required": True, "minlength": 1}},
    },
    "basicPropertyData": {"type": "dict", "required": True},
    "location": {"type": "dict", "required": True},
    "policies": {
        "type": "dict",
        "required": True,
        "schema": {"showFreeCancellation": {"type": "boolean", "required": True}},
    },
}

HOTEL_SCHEMA = {
    "url": {"type": "string", "required": True, "minlength": 1},
    "id": {"type": "string", "nullable": True},
    "title": {"type": "string", "nullable": True},
    "description": {"type": "string", "required": True},
    "address": {"type": "string", "nullable": True},
    "images": {"type": "list", "required": True},
    "lat": {"type": "string", "required": True},
    "lng": {"type": "string", "required": True},
    "features": {"type": "dict", "required": True},
    "price": {"type": "list", "required": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


_today = datetime.date.today()
SAMPLE_QUERY = "Malta"
SAMPLE_CHECKIN = (_today + datetime.timedelta(days=7)).isoformat()
SAMPLE_CHECKOUT = (_today + datetime.timedelta(days=14)).isoformat()
SAMPLE_HOTEL_URL = "https://www.booking.com/hotel/gb/gardencourthotel.en-gb.html"


@pytest.mark.flaky(reruns=2, reruns_delay=60)
@pytest.mark.asyncio
async def test_location_suggestions():
    data = await search_location_suggestions(SAMPLE_QUERY)
    results = data.get("results") if isinstance(data, dict) else None
    assert isinstance(results, list)
    assert len(results) >= 1
    _validate(results[0], LOCATION_SCHEMA)


@pytest.mark.flaky(reruns=2, reruns_delay=60)
@pytest.mark.asyncio
async def test_search():
    results = await scrape_search(SAMPLE_QUERY, SAMPLE_CHECKIN, SAMPLE_CHECKOUT, max_pages=1)
    assert isinstance(results, list)
    if results:
        _validate(results[0], SEARCH_SCHEMA)


@pytest.mark.flaky(reruns=2, reruns_delay=60)
@pytest.mark.asyncio
async def test_hotel():
    hotel = await scrape_hotel(SAMPLE_HOTEL_URL, SAMPLE_CHECKIN, price_n_days=7)
    _validate(hotel, HOTEL_SCHEMA)


@pytest.mark.flaky(reruns=2, reruns_delay=60)
@pytest.mark.asyncio
async def test_hotel_reviews():
    reviews = await scrape_hotel_reviews(SAMPLE_HOTEL_URL, max_pages=1)
    assert isinstance(reviews, list)
