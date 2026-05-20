"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest
from cerberus import Validator


HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("scrapeless_1688", HERE / "1688.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
scrape_product = _mod.scrape_product
scrape_search = _mod.scrape_search
to_dict = _mod.to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PRODUCT_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True},
    "title": {"type": "string", "required": True},
    "price": {"type": "string", "nullable": True},
    "priceRange": {"type": "string", "nullable": True},
    "moq": {"type": "string", "nullable": True},
    "images": {"type": "list", "required": True, "schema": {"type": "string"}},
    "seller": {"type": "string", "nullable": True},
    "sellerUrl": {"type": "string", "nullable": True},
    "location": {"type": "string", "nullable": True},
    "description": {"type": "string", "nullable": True},
    "categories": {"type": "list", "required": True, "schema": {"type": "string"}},
}

SEARCH_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "title": {"type": "string", "required": True},
    "url": {"type": "string", "required": True},
    "image": {"type": "string", "nullable": True},
    "price": {"type": "string", "nullable": True},
    "moq": {"type": "string", "nullable": True},
    "seller": {"type": "string", "nullable": True},
    "location": {"type": "string", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_product():
    sample_id = os.environ.get("SCRAPELESS_1688_SAMPLE_ID", "611499776800")
    product = to_dict(await scrape_product(sample_id))
    _validate(product, PRODUCT_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    sample_query = os.environ.get("SCRAPELESS_1688_SAMPLE_QUERY", "phone case")
    results = [to_dict(r) for r in await scrape_search(sample_query, 1)]
    assert isinstance(results, list)
    for r in results:
        _validate(r, SEARCH_SCHEMA)
