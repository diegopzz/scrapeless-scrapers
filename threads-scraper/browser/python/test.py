"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

Public data only — matches """

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from threads import scrape_profile, scrape_thread

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

THREAD_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "pk": {"type": "string", "required": True, "minlength": 1},
    "code": {"type": "string", "required": True, "minlength": 1},
    "username": {"type": "string", "required": True, "minlength": 1},
    "user_pic": {"type": "string", "required": True},
    "user_verified": {"type": "boolean", "required": True},
    "user_pk": {"type": "string", "required": True, "minlength": 1},
    "user_id": {"type": "string", "required": True, "minlength": 1},
    "reply_count": {"type": "integer", "required": True, "min": 0},
    "like_count": {"type": "integer", "required": True, "min": 0},
    "image_count": {"type": "integer", "required": True, "min": 0},
    "url": {"type": "string", "required": True},
    "published_on": {"type": "integer", "required": True},
}

PROFILE_SCHEMA = {
    "is_private": {"type": "boolean", "required": True},
    "is_verified": {"type": "boolean", "required": True},
    "profile_pic": {"type": "string", "required": True},
    "username": {"type": "string", "required": True, "minlength": 1},
    "full_name": {"type": "string", "required": True},
    "followers": {"type": "integer", "required": True, "min": 0},
    "url": {"type": "string", "required": True},
}

def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"

SAMPLE_THREAD = os.environ.get("THREADS_SAMPLE_THREAD", "https://www.threads.net/t/C8CTu0iswgv")
SAMPLE_PROFILE = os.environ.get("THREADS_SAMPLE_PROFILE", "https://www.threads.net/@natgeo")

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_thread():
    result = await scrape_thread(SAMPLE_THREAD)
    assert result.get("thread"), "expected a parent thread"
    _validate(result["thread"], THREAD_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_profile():
    result = await scrape_profile(SAMPLE_PROFILE)
    _validate(result["user"], PROFILE_SCHEMA)
