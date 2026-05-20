"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from seloger import scrape_property, scrape_search


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


SEARCH_SCHEMA = {
    "title": {"type": "string", "required": True},
    "url": {"type": "string", "required": True, "minlength": 1},
    "images": {"type": "list", "required": True, "schema": {"type": "string"}},
    "price": {"type": "string", "required": True},
    "price_per_m2": {"type": "string", "nullable": True},
    "property_facts": {"type": "list", "required": True, "schema": {"type": "string"}},
    "address": {"type": "string", "required": True},
    "agency": {"type": "string", "nullable": True},
}

PROPERTY_SCHEMA = {
    "classified": {"type": "dict", "required": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


SAMPLE_SEARCH = "https://www.seloger.com/classified-search?distributionTypes=Buy&estateTypes=Apartment&locations=AD08FR13100"
SAMPLE_PROPERTIES = [
    "https://www.seloger.com/annonces/achat/appartement/bordeaux-33/193612259.htm",
]


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    results = await scrape_search(SAMPLE_SEARCH, max_pages=1)
    assert len(results) >= 1
    for r in results:
        _validate(r, SEARCH_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_property():
    results = await scrape_property(SAMPLE_PROPERTIES)
    assert len(results) == 1
    _validate(results[0], PROPERTY_SCHEMA)
