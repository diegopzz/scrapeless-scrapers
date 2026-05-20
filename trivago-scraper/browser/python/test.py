"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from trivago import scrape_destination, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


SEARCH_SCHEMA = {
    "position": {"type": "integer", "required": True},
    "name": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True},
    "address": {"type": "string", "nullable": True},
    "image": {"type": "string", "nullable": True},
    "description": {"type": "string", "nullable": True},
    "priceRange": {"type": "string", "nullable": True},
    "ratingValue": {"type": "float", "nullable": True},
    "reviewCount": {"type": "integer", "nullable": True},
    "bestRating": {"type": "float", "nullable": True},
    "worstRating": {"type": "float", "nullable": True},
}

DESTINATION_SCHEMA = {
    "url": {"type": "string", "required": True},
    "name": {"type": "string", "required": True},
    "breadcrumbs": {"type": "list", "required": True},
    "totalHotels": {"type": "integer", "nullable": True},
    "faq": {"type": "list", "required": True},
    "topHotels": {"type": "list", "required": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=2, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    sample_url = os.environ.get(
        "TRIVAGO_SAMPLE_DESTINATION_URL",
        "https://www.trivago.com/en-US/odr/hotels-new-york-city-new-york-united-states-of-america?search=200-2755",
    )
    results = [to_dict(r) for r in await scrape_search(sample_url, 1)]
    assert len(results) >= 1, "expected at least one search result"
    for r in results:
        _validate(r, SEARCH_SCHEMA)


@pytest.mark.flaky(reruns=2, reruns_delay=30)
@pytest.mark.asyncio
async def test_destination():
    sample_url = os.environ.get(
        "TRIVAGO_SAMPLE_DESTINATION_URL",
        "https://www.trivago.com/en-US/odr/hotels-new-york-city-new-york-united-states-of-america?search=200-2755",
    )
    dest = to_dict(await scrape_destination(sample_url))
    _validate(dest, DESTINATION_SCHEMA)
