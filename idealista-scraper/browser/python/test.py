"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from idealista import scrape_properties, scrape_provinces, scrape_search


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PROPERTY_SCHEMA = {
    "url": {"type": "string", "required": True, "minlength": 1},
    "title": {"type": "string", "required": True},
    "location": {"type": "string", "required": True},
    "price": {"type": "integer", "required": True},
    "currency": {"type": "string", "required": True},
    "description": {"type": "string", "required": True},
    "updated": {"type": "string", "required": False},
    "features": {"type": "dict", "required": True},
    "images": {"type": "dict", "required": True},
    "plans": {"type": "list", "required": True, "schema": {"type": "string"}},
}

SEARCH_SCHEMA = {
    "title": {"type": "string", "required": True},
    "link": {"type": "string", "required": True, "minlength": 1},
    "picture": {"type": "string", "nullable": True},
    "price": {"type": "integer", "required": True},
    "currency": {"type": "string", "required": True},
    "parking_included": {"type": "boolean", "required": True},
    "details": {"type": "list", "required": True, "schema": {"type": "string"}},
    "description": {"type": "string", "required": True},
    "tags": {"type": "list", "required": True, "schema": {"type": "string"}},
    "listing_company": {"type": "string", "nullable": True},
    "listing_company_url": {"type": "string", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


SAMPLE_PROPERTIES = [
    "https://www.idealista.com/en/inmueble/109061254/",
]
SAMPLE_SEARCH = "https://www.idealista.com/en/venta-viviendas/marbella-malaga/con-chalets/"
SAMPLE_PROVINCES = ["https://www.idealista.com/venta-viviendas/almeria-provincia/municipios"]


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
    results = await scrape_search(SAMPLE_SEARCH, max_scrape_pages=1)
    assert len(results) >= 1
    for r in results:
        _validate(r, SEARCH_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_provinces():
    urls = await scrape_provinces(SAMPLE_PROVINCES)
    assert isinstance(urls, list)
    for u in urls:
        assert isinstance(u, str) and u.startswith("http")
