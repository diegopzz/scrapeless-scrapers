"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from youtube import (
    scrape_channel,
    scrape_channel_videos,
    scrape_comments,
    scrape_search,
    scrape_shorts,
    scrape_video,
)


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


VIDEO_SCHEMA = {
    "video": {
        "type": "dict",
        "required": True,
        "schema": {
            "videoId": {"type": "string", "required": True, "minlength": 1},
            "title": {"type": "string", "required": True, "minlength": 1},
            "publishingDate": {"type": "string", "nullable": True},
            "lengthSeconds": {"type": "integer", "nullable": True},
            "keywords": {"type": "list", "nullable": True, "schema": {"type": "string"}},
            "description": {"type": "string", "nullable": True},
            "thumbnail": {"type": "list", "nullable": True},
            "stats": {
                "type": "dict",
                "required": True,
                "schema": {
                    "viewCount": {"type": "integer", "nullable": True},
                    "likeCount": {"type": "integer", "nullable": True},
                    "commentCount": {"type": "integer", "nullable": True},
                },
            },
        },
    },
    "channel": {
        "type": "dict",
        "required": True,
        "schema": {
            "name": {"type": "string", "nullable": True},
            "identifierId": {"type": "string", "nullable": True},
            "id": {"type": "string", "nullable": True},
            "verified": {"type": "boolean", "required": True},
            "channelUrl": {"type": "string", "nullable": True},
            "subscriberCount": {"type": "string", "nullable": True},
            "thumbnails": {"type": "list", "nullable": True},
        },
    },
    "commentContinuationToken": {"type": "string", "nullable": True},
}

COMMENT_SCHEMA = {
    "comment": {
        "type": "dict",
        "required": True,
        "schema": {
            "id": {"type": "string", "required": True, "minlength": 1},
            "text": {"type": "string", "required": True},
            "publishedTime": {"type": "string", "required": True},
        },
    },
    "author": {
        "type": "dict",
        "required": True,
        "schema": {
            "id": {"type": "string", "required": True},
            "displayName": {"type": "string", "required": True},
            "avatarThumbnail": {"type": "string", "required": True},
            "isVerified": {"type": "boolean", "required": True},
            "isCurrentUser": {"type": "boolean", "required": True},
            "isCreator": {"type": "boolean", "required": True},
        },
    },
    "stats": {
        "type": "dict",
        "required": True,
        "schema": {
            "likeCount": {"type": "string", "nullable": True},
            "replyCount": {"type": "string", "nullable": True},
        },
    },
}

CHANNEL_SCHEMA = {
    "description": {"type": "string", "nullable": True},
    "url": {"type": "string", "nullable": True},
    "subscriberCount": {"type": "string", "nullable": True},
    "videoCount": {"type": "string", "nullable": True},
    "viewCount": {"type": "string", "nullable": True},
    "joinedDate": {"type": "string", "nullable": True},
    "country": {"type": "string", "nullable": True},
    "links": {"type": "list", "required": True},
}

CHANNEL_VIDEO_SCHEMA = {
    "videoId": {"type": "string", "required": True, "minlength": 1},
    "title": {"type": "string", "required": True, "minlength": 1},
    "description": {"type": "string", "nullable": True},
    "publishedTime": {"type": "string", "nullable": True},
    "lengthText": {"type": "string", "nullable": True},
    "viewCount": {"type": "string", "nullable": True},
    "thumbnails": {"type": "list", "required": True},
    "url": {"type": "string", "required": True, "minlength": 1},
}

SEARCH_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "title": {"type": "string", "required": True, "minlength": 1},
    "description": {"type": "string", "nullable": True},
    "publishedTime": {"type": "string", "nullable": True},
    "videoLength": {"type": "string", "nullable": True},
    "viewCount": {"type": "string", "nullable": True},
    "videoBadges": {"type": "list", "nullable": True},
    "channelBadges": {"type": "list", "nullable": True},
    "videoThumbnails": {"type": "list", "required": True},
    "channelThumbnails": {"type": "list", "nullable": True},
    "url": {"type": "string", "required": True, "minlength": 1},
}

SHORT_SCHEMA = {
    "videoId": {"type": "string", "required": True, "minlength": 1},
    "title": {"type": "string", "required": True, "minlength": 1},
    "lengthSeconds": {"type": "string", "required": True},
    "channelId": {"type": "string", "required": True},
    "thumbnail": {"type": "list", "required": True},
    "viewCount": {"type": "string", "required": True},
    "author": {"type": "string", "required": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


SAMPLE_VIDEO_IDS = ["1Y-XvvWlyzk"]
SAMPLE_COMMENTS_VIDEO = "FgakZw6K1QQ"
SAMPLE_CHANNEL = "statquest"
SAMPLE_SEARCH = "python"
SAMPLE_SEARCH_PARAMS = "EgQIAxAB"
SAMPLE_SHORT_IDS = ["rZ2qqtNPSBk"]


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_video():
    results = await scrape_video(SAMPLE_VIDEO_IDS)
    assert len(results) >= 1
    for r in results:
        _validate(r, VIDEO_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_comments():
    results = await scrape_comments(SAMPLE_COMMENTS_VIDEO, max_scrape_pages=1)
    assert isinstance(results, list)
    for r in results:
        _validate(r, COMMENT_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_channel():
    results = await scrape_channel([SAMPLE_CHANNEL])
    assert len(results) >= 1
    for r in results:
        _validate(r, CHANNEL_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_channel_videos():
    results = await scrape_channel_videos(SAMPLE_CHANNEL, sort_by="Latest", max_scrape_pages=1)
    assert isinstance(results, list)
    for r in results:
        _validate(r, CHANNEL_VIDEO_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    results = await scrape_search(SAMPLE_SEARCH, max_scrape_pages=1, search_params=SAMPLE_SEARCH_PARAMS)
    assert len(results) >= 1
    for r in results:
        _validate(r, SEARCH_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_shorts():
    results = await scrape_shorts(SAMPLE_SHORT_IDS)
    assert len(results) >= 1
    for r in results:
        _validate(r, SHORT_SCHEMA)
