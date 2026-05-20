"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from realtorcom import scrape_property, scrape_search, to_dict

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

DEFAULT_PROPERTY_URL = (
    "https://www.realtor.com/realestateandhomes-detail/"
    "12355-Attlee-Dr_Houston_TX_77077_M70330-35605"
)
DEFAULT_STATE = "CA"
DEFAULT_CITY = "San-Francisco"

PROPERTY_SCHEMA = {
    "id": {"type": "string", "nullable": True},
    "url": {"type": "string", "nullable": True},
    "status": {"type": "string", "nullable": True},
    "list_price": {"type": "integer", "nullable": True},
}

# Mirror Realtor.com's verbatim search result fields.
SEARCH_RESULT_SCHEMA = {
    "property_id": {"type": "string", "required": True},
}

def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_property():
    url = os.environ.get("REALTORCOM_PROPERTY_URL", DEFAULT_PROPERTY_URL)
    property_data = await scrape_property(url)
    assert isinstance(property_data, dict)
    _validate(to_dict(property_data), PROPERTY_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    state = os.environ.get("REALTORCOM_STATE", DEFAULT_STATE)
    city = os.environ.get("REALTORCOM_CITY", DEFAULT_CITY)
    results = await scrape_search(state, city, max_pages=1)
    assert len(results) >= 1
    for r in results[:5]:
        _validate(r, SEARCH_RESULT_SCHEMA)
