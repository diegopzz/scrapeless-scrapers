"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from leboncoin import scrape_ad, scrape_search

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

# Leboncoin's NextJS cache keys vary slightly per ad category — we validate the
# fields the upstream site relies on and pass-through the rest.

AD_SCHEMA = {
    "list_id": {"type": "integer", "required": True},
    "subject": {"type": "string", "required": True, "minlength": 1},
    "body": {"type": "string", "nullable": True},
    "url": {"type": "string", "required": True},
    "category_id": {"type": "string", "nullable": True},
    "category_name": {"type": "string", "nullable": True},
    "price": {"nullable": True},
    "images": {"type": "dict", "nullable": True},
    "attributes": {"type": "list", "nullable": True},
    "location": {"type": "dict", "nullable": True},
    "owner": {"type": "dict", "nullable": True},
}

SEARCH_AD_SCHEMA = {
    "list_id": {"type": "integer", "required": True},
    "subject": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True},
    "category_id": {"type": "string", "nullable": True},
    "category_name": {"type": "string", "nullable": True},
    "price": {"nullable": True},
}

def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    url = os.environ.get(
        "LEBONCOIN_SAMPLE_SEARCH", "https://www.leboncoin.fr/recherche?text=coffe"
    )
    results = await scrape_search(url, max_pages=1, scrape_all_pages=False)
    assert len(results) >= 1, "expected at least one ad in search"
    for r in results:
        _validate(r, SEARCH_AD_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_ad():
    url = os.environ.get(
        "LEBONCOIN_SAMPLE_AD",
        "https://www.leboncoin.fr/ad/ventes_immobilieres/2919253293",
    )
    ad = await scrape_ad(url)
    assert ad is not None, "expected ad payload, got None (DataDome block?)"
    _validate(ad, AD_SCHEMA)
