"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

Public data only — matches """

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from instagram import scrape_post, scrape_post_comments, scrape_user, scrape_user_posts, to_dict

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

USER_SCHEMA = {
    "name": {"type": "string", "required": True, "minlength": 1},
    "username": {"type": "string", "required": True, "minlength": 1},
    "id": {"type": "string", "required": True, "minlength": 1},
    "category": {"type": "string", "nullable": True},
    "business_category": {"type": "string", "nullable": True},
    "phone": {"type": "string", "nullable": True},
    "email": {"type": "string", "nullable": True},
    "bio": {"type": "string", "nullable": True},
    "bio_links": {"type": "list", "nullable": True, "schema": {"type": "string"}},
    "homepage": {"type": "string", "nullable": True},
    "followers": {"type": "integer", "required": True, "min": 0},
    "follows": {"type": "integer", "required": True, "min": 0},
    "facebook_id": {"type": "string", "nullable": True},
    "is_private": {"type": "boolean", "required": True},
    "is_verified": {"type": "boolean", "required": True},
    "profile_image": {"type": "string", "required": True},
    "video_count": {"type": "integer", "required": True, "min": 0},
    "image_count": {"type": "integer", "required": True, "min": 0},
    "related_profiles": {"type": "list", "nullable": True},
}

POST_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "shortcode": {"type": "string", "required": True, "minlength": 1},
    "src": {"type": "string", "required": True},
    "likes": {"type": "integer", "required": True, "min": 0},
    "taken_at": {"type": "integer", "required": True},
    "is_video": {"type": "boolean", "required": True},
    "comments_count": {"type": "integer", "required": True, "min": 0},
    "comments_disabled": {"type": "boolean", "required": True},
    "captions": {"type": "list", "nullable": True},
    "tagged_users": {"type": "list", "nullable": True},
}

USER_POST_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "shortcode": {"type": "string", "required": True, "minlength": 1},
    "taken_at": {"type": "integer", "required": True},
    "comment_count": {"type": "integer", "required": True, "min": 0},
    "like_count": {"type": "integer", "required": True, "min": 0},
}

POST_COMMENT_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "text": {"type": "string", "required": True},
    "created_at": {"type": "integer", "required": True},
    "owner": {"type": "string", "required": True, "minlength": 1},
    "likes": {"type": "integer", "required": True, "min": 0},
    "replies_count": {"type": "integer", "required": True, "min": 0},
}

def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"

SAMPLE_USERNAME = os.environ.get("INSTAGRAM_SAMPLE_USERNAME", "google")
SAMPLE_POST = os.environ.get("INSTAGRAM_SAMPLE_POST", "https://www.instagram.com/p/Cs9iEotsiGY/")

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_user():
    user = to_dict(await scrape_user(SAMPLE_USERNAME))
    _validate(user, USER_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_post():
    post = to_dict(await scrape_post(SAMPLE_POST))
    _validate(post, POST_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_user_posts():
    items = []
    async for p in scrape_user_posts(SAMPLE_USERNAME, max_pages=1):
        items.append(p)
    assert len(items) >= 1
    for item in items:
        _validate(item, USER_POST_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_post_comments():
    post = await scrape_post(SAMPLE_POST)
    comments = to_dict(await scrape_post_comments(post["id"], max_comments=10))
    for c in comments:
        _validate(c, POST_COMMENT_SCHEMA)
