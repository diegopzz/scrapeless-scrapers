"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from reddit import (
    scrape_post,
    scrape_subreddit,
    scrape_user_comments,
    scrape_user_posts,
)

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

SUBREDDIT_INFO_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True},
    "description": {"type": "string", "nullable": True},
    "rank": {"type": "string", "nullable": True},
    "members": {"type": "integer", "nullable": True, "min": 0},
}

SUBREDDIT_POST_SCHEMA = {
    "title": {"type": "string", "nullable": True},
    "link": {"type": "string", "nullable": True},
    "postId": {"type": "string", "nullable": True},
    "postUpvotes": {"type": "integer", "nullable": True},
    "commentCount": {"type": "integer", "nullable": True},
}

POST_INFO_SCHEMA = {
    "subreddit": {"type": "string", "required": True},
    "postTitle": {"type": "string", "nullable": True},
    "postLink": {"type": "string", "nullable": True},
    "postId": {"type": "string", "nullable": True},
    "commentCount": {"type": "integer", "nullable": True},
    "upvoteCount": {"type": "integer", "nullable": True},
}

USER_POST_SCHEMA = {
    "postId": {"type": "string", "nullable": True},
    "postLink": {"type": "string", "nullable": True},
    "postTitle": {"type": "string", "nullable": True},
    "postSubreddit": {"type": "string", "nullable": True},
    "postScore": {"type": "integer", "nullable": True},
}

USER_COMMENT_SCHEMA = {
    "commentId": {"type": "string", "nullable": True},
    "commentLink": {"type": "string", "nullable": True},
    "commentBody": {"type": "string", "required": True},
    "replyTo": {"type": "dict", "required": True},
}

def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"

SAMPLE_SUBREDDIT = os.environ.get("REDDIT_SAMPLE_SUBREDDIT", "wallstreetbets")
SAMPLE_POST_URL = os.environ.get(
    "REDDIT_SAMPLE_POST_URL",
    "https://www.reddit.com/r/wallstreetbets/comments/1c4vwlp/what_are_your_moves_tomorrow_april_16_2024/",
)
SAMPLE_USERNAME = os.environ.get("REDDIT_SAMPLE_USERNAME", "the upstream reference")

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_subreddit():
    sub = await scrape_subreddit(SAMPLE_SUBREDDIT, max_pages=1)
    _validate(sub["info"], SUBREDDIT_INFO_SCHEMA)
    assert len(sub["posts"]) >= 1
    for p in sub["posts"]:
        _validate(p, SUBREDDIT_POST_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_post():
    post = await scrape_post(SAMPLE_POST_URL, sort="top")
    _validate(post["info"], POST_INFO_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_user_posts():
    posts = await scrape_user_posts(SAMPLE_USERNAME, sort="top", max_pages=1)
    for p in posts:
        _validate(p, USER_POST_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_user_comments():
    comments = await scrape_user_comments(SAMPLE_USERNAME, sort="top", max_pages=1)
    for c in comments:
        _validate(c, USER_COMMENT_SCHEMA)
