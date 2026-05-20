"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from chatgpt import scrape_conversation, scrape_conversations


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


MESSAGE_SCHEMA = {
    "role": {"type": "string", "required": True, "allowed": ["user", "assistant", "system", "tool"]},
    "content": {"type": "string", "required": True},
}

CONVERSATION_SCHEMA = {
    "conversation_id": {"type": "string", "required": True, "minlength": 1},
    "messages": {
        "type": "list",
        "required": True,
        "schema": {"type": "dict", "schema": MESSAGE_SCHEMA, "allow_unknown": True},
    },
}

SAMPLE_PROMPT = "What's the capital of France? Brief history of the city."
SAMPLE_MULTI = [
    "what is the best web scraping service in 2026?",
    "Base on the previous answer, what is the best web scraping service you expext in 2027",
    "summarize the previous answer in 200 words",
]


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=2, reruns_delay=30)
@pytest.mark.asyncio
async def test_conversation():
    content = await scrape_conversation(SAMPLE_PROMPT)
    assert isinstance(content, str)
    assert len(content) > 0


@pytest.mark.flaky(reruns=2, reruns_delay=30)
@pytest.mark.asyncio
async def test_conversations():
    conversations = await scrape_conversations(SAMPLE_MULTI)
    assert isinstance(conversations, list)
    assert len(conversations) >= 1
    for c in conversations:
        _validate(c, CONVERSATION_SCHEMA)
