"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from expedia import scrape_hotel, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


SEARCH_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "name": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True},
    "price": {"type": "string", "nullable": True},
    "review": {"type": "string", "nullable": True},
    "image": {"type": "string", "nullable": True},
}

HOTEL_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True},
    "name": {"type": "string", "required": True, "minlength": 1},
    "address": {"type": "string", "nullable": True},
    "description": {"type": "string", "required": True},
    "amenities": {"type": "list", "required": True},
    "images": {"type": "list", "required": True},
    "review": {"type": "string", "nullable": True},
    "price": {"type": "string", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=2, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    destination = os.environ.get("EXPEDIA_SAMPLE_DESTINATION", "New York")
    checkin = os.environ.get("EXPEDIA_SAMPLE_CHECKIN", "2026-06-15")
    checkout = os.environ.get("EXPEDIA_SAMPLE_CHECKOUT", "2026-06-16")
    results = [to_dict(r) for r in await scrape_search(destination, checkin, checkout, 1)]
    assert len(results) >= 1, "expected at least one search result"
    for r in results:
        _validate(r, SEARCH_SCHEMA)


@pytest.mark.flaky(reruns=2, reruns_delay=30)
@pytest.mark.asyncio
async def test_hotel():
    destination = os.environ.get("EXPEDIA_SAMPLE_DESTINATION", "New York")
    checkin = os.environ.get("EXPEDIA_SAMPLE_CHECKIN", "2026-06-15")
    checkout = os.environ.get("EXPEDIA_SAMPLE_CHECKOUT", "2026-06-16")
    results = await scrape_search(destination, checkin, checkout, 1)
    assert results, "no search results to derive a hotel URL from"
    hotel = to_dict(await scrape_hotel(results[0].url))
    _validate(hotel, HOTEL_SCHEMA)
