"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from realestatecom import scrape_properties, scrape_search


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PROPERTY_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "propertyType": {"type": "string", "nullable": True},
    "description": {"type": "string", "nullable": True},
    "propertyLink": {"type": "string", "nullable": True},
    "address": {"type": "dict", "nullable": True},
    "propertySizes": {"type": "dict", "nullable": True},
    "generalFeatures": {"type": "dict", "nullable": True},
    "propertyFeatures": {"type": "list", "nullable": True},
    "images": {"type": "list", "nullable": True},
    "videos": {"nullable": True},
    "floorplans": {"nullable": True},
    "listingCompany": {"type": "dict", "nullable": True},
    "listers": {"type": "list", "nullable": True},
    "auction": {"nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_properties():
    urls = [
        os.environ.get(
            "REALESTATECOM_SAMPLE_URL",
            "https://www.realestate.com.au/property-house-vic-tarneit-143160680",
        )
    ]
    properties = await scrape_properties(urls)
    assert len(properties) >= 1, "expected at least one property"
    for p in properties:
        _validate(p, PROPERTY_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    url = os.environ.get(
        "REALESTATECOM_SAMPLE_SEARCH",
        "https://www.realestate.com.au/buy/in-melbourne+-+northern+region,+vic/list-1",
    )
    results = await scrape_search(url, max_scrape_pages=1)
    assert len(results) >= 1, "expected at least one search result"
    for r in results:
        _validate(r, PROPERTY_SCHEMA)
