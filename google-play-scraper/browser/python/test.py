"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from google_play import scrape_app, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


APP_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "name": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True, "minlength": 1},
    "developer": {"type": "string"},
    "rating": {"type": "float", "nullable": True},
    "rating_count": {"type": "integer", "nullable": True},
    "price": {"type": "string"},
    "installs": {"type": "string"},
    "description": {"type": "string"},
    "categories": {"type": "list", "schema": {"type": "string"}},
    "latest_update": {"type": "string"},
    "screenshots": {"type": "list", "schema": {"type": "string"}},
    "icon": {"type": "string"},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_app():
    sample_id = os.environ.get("GOOGLE_PLAY_SAMPLE_ID", "com.spotify.music")
    app = to_dict(await scrape_app(sample_id))
    _validate(app, APP_SCHEMA)
    assert app["id"] == sample_id
