"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from zoopla import scrape_properties, scrape_search, to_dict

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

DEFAULT_PROPERTY_URL = "https://www.zoopla.co.uk/new-homes/details/70337559/"
DEFAULT_LOCATION_SLUG = "london/islington"
DEFAULT_QUERY_TYPE = "to-rent"

PROPERTY_SCHEMA = {
    "id": {"type": "integer", "nullable": True},
    "url": {"type": "string", "nullable": True},
    "title": {"type": "string", "nullable": True},
    "address": {"type": "string", "nullable": True},
    "price": {"type": "dict", "required": True},
    "coordinates": {"type": "dict", "required": True},
    "agent": {"type": "dict", "required": True},
}

SEARCH_RESULT_SCHEMA = {
    "url": {"type": "string", "nullable": True},
    "priceCurrency": {"type": "string", "required": True},
}

def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_properties():
    url = os.environ.get("ZOOPLA_PROPERTY_URL", DEFAULT_PROPERTY_URL)
    results = await scrape_properties([url])
    assert len(results) == 1
    _validate(to_dict(results[0]), PROPERTY_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    location_slug = os.environ.get("ZOOPLA_LOCATION_SLUG", DEFAULT_LOCATION_SLUG)
    query_type = os.environ.get("ZOOPLA_QUERY_TYPE", DEFAULT_QUERY_TYPE)
    results = await scrape_search(
        scrape_all_pages=False,
        location_slug=location_slug,
        max_scrape_pages=1,
        query_type=query_type,
    )
    assert len(results) >= 1
    for r in results[:5]:
        _validate(r, SEARCH_RESULT_SCHEMA)
