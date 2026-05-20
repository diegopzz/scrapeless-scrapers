"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from immobilienscout24 import scrape_properties, scrape_search


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PROPERTY_SCHEMA = {
    "id": {"type": "string", "required": True},
    "title": {"type": "string", "required": True},
    "description": {"type": "string", "nullable": True},
    "address": {"type": "string", "nullable": True},
    "propertyLlink": {"type": "string", "required": True},
    "propertySepcs": {"type": "dict", "required": True},
    "price": {"type": "dict", "required": True},
    "building": {"type": "dict", "required": True},
    "attachments": {"type": "dict", "required": True},
    "agencyName": {"type": "string", "nullable": True},
    "agencyAddress": {"type": "string", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


SAMPLE_PROPERTIES = ["https://www.immobilienscout24.de/expose/160519246"]
SAMPLE_SEARCH = "https://www.immobilienscout24.de/Suche/de/bayern/muenchen/wohnung-mieten"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_properties():
    results = await scrape_properties(SAMPLE_PROPERTIES)
    assert len(results) >= 1
    for r in results:
        _validate(r, PROPERTY_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    results = await scrape_search(SAMPLE_SEARCH, scrape_all_pages=False, max_scrape_pages=1)
    assert len(results) >= 1
    for r in results:
        _validate(r, PROPERTY_SCHEMA)
