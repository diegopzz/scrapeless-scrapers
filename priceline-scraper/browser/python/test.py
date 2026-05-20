"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from priceline import scrape_hotel, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


HOTEL_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True},
    "name": {"type": "string", "required": True},
    "description": {"type": "string", "required": True},
    "amenities": {"type": "list", "required": True},
    "images": {"type": "list", "required": True},
    "policies": {"type": "list", "required": True},
    "address": {"type": "string", "nullable": True},
    "latitude": {"type": "float", "nullable": True},
    "longitude": {"type": "float", "nullable": True},
    "starRating": {"type": "string", "nullable": True},
    "pageTitle": {"type": "string", "nullable": True},
}

SEARCH_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "name": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True},
    "price": {"type": "string", "nullable": True},
    "starRating": {"type": "float", "nullable": True},
    "review": {"type": "float", "nullable": True},
    "reviewCount": {"type": "integer", "nullable": True},
    "image": {"type": "string", "nullable": True},
    "neighborhood": {"type": "string", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=2, reruns_delay=30)
@pytest.mark.asyncio
async def test_hotel():
    sample_hotel = os.environ.get("PRICELINE_SAMPLE_HOTEL_ID", "3000010091")
    sample_checkin = os.environ.get("PRICELINE_SAMPLE_CHECKIN", "2026-06-15")
    sample_checkout = os.environ.get("PRICELINE_SAMPLE_CHECKOUT", "2026-06-16")
    hotel = to_dict(await scrape_hotel(sample_hotel, sample_checkin, sample_checkout))
    _validate(hotel, HOTEL_SCHEMA)
    assert hotel["id"] == sample_hotel


@pytest.mark.flaky(reruns=2, reruns_delay=30)
@pytest.mark.asyncio
async def test_search_shape():
    sample_city = os.environ.get("PRICELINE_SAMPLE_CITY_ID", "15300")
    sample_checkin = os.environ.get("PRICELINE_SAMPLE_CHECKIN", "2026-06-15")
    sample_checkout = os.environ.get("PRICELINE_SAMPLE_CHECKOUT", "2026-06-16")
    results = [to_dict(r) for r in await scrape_search(sample_city, sample_checkin, sample_checkout)]
    # Priceline frequently withholds listings; we accept zero results.
    for r in results:
        _validate(r, SEARCH_SCHEMA)
