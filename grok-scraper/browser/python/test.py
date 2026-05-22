"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from grok import scrape_share

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

SAMPLE_SHARE_URL = "https://grok.com/share/bGVnYWN5_d6991719-5568-4608-b613-609cbd3f2842"

MESSAGE_SCHEMA = {
    "role": {"type": "string", "required": True, "allowed": ["user", "assistant"]},
    "content": {"type": "string", "required": True},
}

SHARE_SCHEMA = {
    "url": {"type": "string", "required": True, "minlength": 1},
    "title": {"type": "string", "required": True},
    "messages": {
        "type": "list",
        "required": True,
        "schema": {"type": "dict", "schema": MESSAGE_SCHEMA, "allow_unknown": True},
    },
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=2, reruns_delay=30)
@pytest.mark.asyncio
async def test_scrape_share():
    result = await scrape_share(SAMPLE_SHARE_URL)
    d = {
        "url": result.url,
        "title": result.title,
        "messages": [{"role": m.role, "content": m.content} for m in result.messages],
    }
    _validate(d, SHARE_SCHEMA)
    assert result.title, "title must not be empty"
    assert len(result.messages) >= 1, "must have at least one message"
    assert any(m.role == "user" for m in result.messages), "must have at least one user message"
    assert any(m.role == "assistant" for m in result.messages), "must have at least one assistant message"
