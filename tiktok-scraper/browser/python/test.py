"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

Public data only — matches """

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from tiktok import (
    scrape_channel,
    scrape_comments,
    scrape_posts,
    scrape_profiles,
    scrape_search,
    to_dict,
)

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

POST_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "desc": {"type": "string", "required": True},
    "createTime": {"type": "integer", "required": True},
    "video": {"type": "dict", "required": True},
    "author": {"type": "dict", "required": True},
    "stats": {"type": "dict", "required": True},
}

COMMENT_SCHEMA = {
    "text": {"type": "string", "required": True},
    "digg_count": {"type": "integer", "required": True, "min": 0},
    "reply_comment_total": {"type": "integer", "required": True, "min": 0},
    "create_time": {"type": "integer", "required": True},
    "cid": {"type": "string", "required": True, "minlength": 1},
    "nickname": {"type": "string", "required": True},
    "unique_id": {"type": "string", "required": True},
    "aweme_id": {"type": "string", "required": True},
}

SEARCH_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "desc": {"type": "string", "required": True},
    "createTime": {"type": "integer", "required": True},
    "type": {"type": "integer", "required": True},
}

CHANNEL_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "desc": {"type": "string", "required": True},
    "createTime": {"type": "integer", "required": True},
    "stats": {"type": "dict", "required": True},
}

def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"

SAMPLE_POST = os.environ.get(
    "TIKTOK_SAMPLE_POST", "https://www.tiktok.com/@oddanimalspecimens/video/7198206283571285294"
)
SAMPLE_PROFILE = os.environ.get(
    "TIKTOK_SAMPLE_PROFILE", "https://www.tiktok.com/@oddanimalspecimens"
)
SAMPLE_QUERY = os.environ.get("TIKTOK_SAMPLE_QUERY", "whales")

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_posts():
    posts = to_dict(await scrape_posts([SAMPLE_POST]))
    assert len(posts) == 1
    _validate(posts[0], POST_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_comments():
    comments = to_dict(await scrape_comments(SAMPLE_POST))
    for c in comments:
        _validate(c, COMMENT_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_profiles():
    profiles = await scrape_profiles([SAMPLE_PROFILE])
    assert len(profiles) == 1
    assert "user" in profiles[0]
    assert "stats" in profiles[0]

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    results = to_dict(await scrape_search(SAMPLE_QUERY))
    for r in results:
        _validate(r, SEARCH_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_channel():
    items = to_dict(await scrape_channel(SAMPLE_PROFILE))
    for item in items:
        _validate(item, CHANNEL_SCHEMA)
