"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from google_maps import scrape_place, scrape_places, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PLACE_SCHEMA = {
    "name": {"type": "string", "required": True, "minlength": 1},
    "category": {"type": "string", "nullable": True},
    "address": {"type": "string", "nullable": True},
    "phone": {"type": "string", "nullable": True},
    "website": {"type": "string", "nullable": True},
    "rating": {"type": "float", "nullable": True},
    "review_count": {"type": "integer", "nullable": True},
    "price_level": {"type": "string", "nullable": True},
    "description": {"type": "string", "nullable": True},
    "url": {"type": "string", "required": True, "minlength": 1},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_places():
    query = os.environ.get("GOOGLE_MAPS_SEARCH_QUERY", "coffee shops in Austin TX")
    places = to_dict(await scrape_places(query))
    assert isinstance(places, list) and len(places) > 0
    for p in places[:3]:
        _validate(p, PLACE_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_place():
    url = os.environ.get(
        "GOOGLE_MAPS_PLACE_URL",
        "https://www.google.com/maps/place/Epoch+Coffee/@30.3186037,-97.7296551,15z"
        "/data=!4m6!3m5!1s0x8644ca6bc309e81b:0x1f1a903bbb66839!8m2!3d30.3186037!4d-97.7245402!16s%2Fg%2F1v76_180",
    )
    place = to_dict(await scrape_place(url))
    _validate(place, PLACE_SCHEMA)
    assert place["name"], "expected non-empty name"
