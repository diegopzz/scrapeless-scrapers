"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from opensea import scrape_asset, scrape_collection, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


COLLECTION_SCHEMA = {
    "slug": {"type": "string", "required": True, "minlength": 1},
    "name": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True, "minlength": 1},
    "description": {"type": "string"},
    "chain": {"type": "string"},
    "total_supply": {"type": "integer", "nullable": True},
    "floor_price": {"type": "float", "nullable": True},
    "floor_currency": {"type": "string"},
    "floor_price_usd": {"type": "float", "nullable": True},
    "volume_native": {"type": "float", "nullable": True},
    "volume_usd": {"type": "float", "nullable": True},
    "image": {"type": "string"},
}

TRAIT_SCHEMA = {
    "trait_type": {"type": "string"},
    "value": {"type": "string"},
}

ASSET_SCHEMA = {
    "chain": {"type": "string", "required": True, "minlength": 1},
    "contract": {"type": "string", "required": True, "minlength": 1},
    "token_id": {"type": "string", "required": True, "minlength": 1},
    "name": {"type": "string", "required": True},
    "url": {"type": "string", "required": True, "minlength": 1},
    "collection_slug": {"type": "string"},
    "collection_name": {"type": "string"},
    "owner": {"type": "string"},
    "owner_address": {"type": "string"},
    "rarity_rank": {"type": "integer", "nullable": True},
    "image": {"type": "string"},
    "traits": {"type": "list", "schema": {"type": "dict", "schema": TRAIT_SCHEMA, "allow_unknown": True}},
    "best_offer": {"type": "float", "nullable": True},
    "best_offer_currency": {"type": "string"},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_collection():
    slug = os.environ.get("OPENSEA_SAMPLE_SLUG", "boredapeyachtclub")
    result = to_dict(await scrape_collection(slug))
    _validate(result, COLLECTION_SCHEMA)
    assert result["slug"] == slug


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_asset():
    chain = os.environ.get("OPENSEA_SAMPLE_CHAIN", "ethereum")
    contract = os.environ.get("OPENSEA_SAMPLE_CONTRACT", "0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d")
    token_id = os.environ.get("OPENSEA_SAMPLE_TOKEN_ID", "1")
    result = to_dict(await scrape_asset(chain, contract, token_id))
    _validate(result, ASSET_SCHEMA)
    assert result["token_id"] == token_id
