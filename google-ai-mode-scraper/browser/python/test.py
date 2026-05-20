"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from google_ai_mode import scrape_ai_response, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


CITATION_SCHEMA = {
    "title": {"type": "string", "required": True},
    "url": {"type": "string", "required": True},
    "source": {"type": "string", "required": True},
}

LINK_SCHEMA = {
    "url": {"type": "string", "required": True},
    "text": {"type": "string", "required": True},
}

AI_RESPONSE_SCHEMA = {
    "query": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True, "minlength": 1},
    "response_text": {"type": "string", "required": True},
    "citations": {
        "type": "list",
        "required": True,
        "schema": {"type": "dict", "schema": CITATION_SCHEMA, "allow_unknown": True},
    },
    "links": {
        "type": "list",
        "required": True,
        "schema": {"type": "dict", "schema": LINK_SCHEMA, "allow_unknown": True},
    },
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_ai_response():
    sample_query = os.environ.get("GOOGLE_AI_MODE_SAMPLE_QUERY", "best health trackers under $200")
    result = to_dict(await scrape_ai_response(sample_query))
    _validate(result, AI_RESPONSE_SCHEMA)
    assert result["query"] == sample_query
