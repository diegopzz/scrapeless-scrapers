"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from worten import scrape_category, scrape_product, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PRODUCT_SCHEMA = {
    "sku": {"type": "string", "required": True, "minlength": 1},
    "name": {"type": "string", "required": True, "minlength": 1},
    "brand": {"type": "string", "nullable": True},
    "description": {"type": "string", "nullable": True},
    "image": {"type": "string", "nullable": True},
    "price": {"type": "string", "nullable": True},
    "priceCurrency": {"type": "string", "nullable": True},
    "availability": {"type": "string", "nullable": True},
    "ratingValue": {"type": "float", "nullable": True},
    "reviewCount": {"type": "integer", "nullable": True},
    "url": {"type": "string", "required": True, "minlength": 1},
    "breadcrumb": {"type": "list", "required": True},
}

CATEGORY_SCHEMA = {
    "name": {"type": "string", "required": True, "minlength": 1},
    "title": {"type": "string", "nullable": True},
    "description": {"type": "string", "nullable": True},
    "url": {"type": "string", "required": True, "minlength": 1},
    "breadcrumb": {"type": "list", "required": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_product():
    sample = os.environ.get(
        "WORTEN_SAMPLE_PRODUCT_URL",
        "https://www.worten.pt/produtos/iphone-15-pro-max-apple-6-7-256-gb-titanio-branco-7851167",
    )
    product = to_dict(await scrape_product(sample))
    _validate(product, PRODUCT_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_category():
    sample = os.environ.get(
        "WORTEN_SAMPLE_CATEGORY_URL", "https://www.worten.pt/promocoes/pequenos-eletrodomesticos"
    )
    cat = to_dict(await scrape_category(sample))
    _validate(cat, CATEGORY_SCHEMA)
