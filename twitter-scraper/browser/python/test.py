"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

Public data only — matches """

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from twitter import scrape_profile, scrape_tweet, to_dict

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

TWEET_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "user_id": {"type": "string", "required": True, "minlength": 1},
    "conversation_id": {"type": "string", "required": True, "minlength": 1},
    "text": {"type": "string", "required": True},
    "created_at": {"type": "string", "required": True, "minlength": 1},
    "favorite_count": {"type": "integer", "required": True, "min": 0},
    "reply_count": {"type": "integer", "required": True, "min": 0},
    "retweet_count": {"type": "integer", "required": True, "min": 0},
    "quote_count": {"type": "integer", "required": True, "min": 0},
    "is_quote": {"type": "boolean", "required": True},
    "is_retweet": {"type": "boolean", "required": True},
    "language": {"type": "string", "required": True},
}

PROFILE_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "rest_id": {"type": "string", "required": True, "minlength": 1},
    "verified": {"type": "boolean", "required": True},
    "screen_name": {"type": "string", "required": True, "minlength": 1},
    "name": {"type": "string", "required": True, "minlength": 1},
}

def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"

SAMPLE_TWEET = os.environ.get(
    "TWITTER_SAMPLE_TWEET", "https://x.com/robinhanson/status/1872047986873885082"
)
SAMPLE_PROFILE = os.environ.get("TWITTER_SAMPLE_PROFILE", "https://x.com/robinhanson/")

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_tweet():
    tweet = to_dict(await scrape_tweet(SAMPLE_TWEET))
    _validate(tweet, TWEET_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_profile():
    profile = to_dict(await scrape_profile(SAMPLE_PROFILE))
    _validate(profile, PROFILE_SCHEMA)
