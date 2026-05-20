"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from rightmove import find_locations, scrape_properties, scrape_search, to_dict

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

DEFAULT_PROPERTY_URL = "https://www.rightmove.co.uk/properties/149360984#/"
DEFAULT_LOCATION_QUERY = "cornwall"
DEFAULT_LOCATION_NAME = "Cornwall"

PROPERTY_SCHEMA = {
    "id": {"type": "integer", "nullable": True},
    "available": {"type": "boolean", "nullable": True},
    "archived": {"type": "boolean", "nullable": True},
    "bedrooms": {"type": "integer", "nullable": True},
    "bathrooms": {"type": "integer", "nullable": True},
    "type": {"type": "string", "nullable": True},
    "property_type": {"type": "string", "nullable": True},
    "title": {"type": "string", "nullable": True},
    "price": {"type": "string", "nullable": True},
}

# Verbatim Rightmove search result fields.
SEARCH_RESULT_SCHEMA = {
    "id": {"type": "integer", "required": True},
}

def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_properties():
    url = os.environ.get("RIGHTMOVE_PROPERTY_URL", DEFAULT_PROPERTY_URL)
    results = await scrape_properties([url])
    assert len(results) == 1
    _validate(to_dict(results[0]), PROPERTY_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_find_locations_and_search():
    query = os.environ.get("RIGHTMOVE_LOCATION_QUERY", DEFAULT_LOCATION_QUERY)
    name = os.environ.get("RIGHTMOVE_LOCATION_NAME", DEFAULT_LOCATION_NAME)
    locations = await find_locations(query)
    assert isinstance(locations, list) and len(locations) >= 1
    results = await scrape_search(
        location_name=name,
        location_id=locations[0],
        scrape_all_properties=False,
        max_properties=24,
    )
    assert len(results) >= 1
    for r in results[:5]:
        _validate(r, SEARCH_RESULT_SCHEMA)
