"""ChatGPT scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names match verbatim, so downstream code
can Flow:
- `client.browser.create()` mints a cloud browser session (CDP WS endpoint).
- Playwright connects over CDP, opens `https://chatgpt.com/?prompt=<text>`.
- We dismiss the credential picker / notice, click the send button, and
  capture the streaming SSE response from `/backend-anon/f/conversation`.
- `parse_chatgpt_stream` (identical to the upstream reference's) folds the SSE event log
  into a `ChatgptConversation` dict.

Public/anonymous content only — ChatGPT requires a real session for any
authenticated history, which this scraper does NOT attempt.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Dict, List, Optional, TypedDict
from urllib.parse import quote_plus
from uuid import uuid4

from loguru import logger
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 300

TRANSIENT_NET_ERRORS = (
    "ERR_TUNNEL_CONNECTION_FAILED",
    "ERR_CONNECTION_CLOSED",
    "ERR_CONNECTION_RESET",
    "ERR_CONNECTION_REFUSED",
    "ERR_TIMED_OUT",
    "ERR_NETWORK_CHANGED",
    "ERR_EMPTY_RESPONSE",
    "ERR_PROXY_CONNECTION_FAILED",
    "Navigation timeout",
    "net::",
)

def _is_transient_error(err: Exception) -> bool:
    msg = str(err)
    return any(s in msg for s in TRANSIENT_NET_ERRORS)

async def _warmup_chatgpt(page) -> None:
    """Warm up the cloud browser against chat.openai.com so Cloudflare sets
    its cookies before we hit chatgpt.com. Without this the first TLS
    handshake to chatgpt.com often gets ripped down with ERR_CONNECTION_CLOSED.
    """
    try:
        await page.goto("https://chat.openai.com/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2.0)
    except Exception:
        pass

async def _with_session_retry(fn, *, retries: int = 2, label: str = "chatgpt"):
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=DEFAULT_PROXY_COUNTRY, session_ttl=DEFAULT_SESSION_TTL)
        )
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
            try:
                page = await browser.new_page()
                return await fn(page)
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("{} attempt {} failed: {}", label, attempt + 1, e)
                if not _is_transient_error(e) and attempt > 0:
                    raise
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
        if attempt < retries:
            await asyncio.sleep(5.0 * (2 ** attempt))
    raise RuntimeError(f"{label}: giving up after {retries + 1} attempts: {last_error}")

# ---------------------------------------------------------------------------
# Types — mirror the upstream reference's TypedDicts verbatim
# ---------------------------------------------------------------------------

class ChatgptMessage(TypedDict):
    role: str
    content: str

class ChatgptConversation(TypedDict):
    conversation_id: str
    messages: List[ChatgptMessage]

# ---------------------------------------------------------------------------
# Scrapeless plumbing
# ---------------------------------------------------------------------------

def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError(
            "SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com"
        )
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()

# ---------------------------------------------------------------------------
# SSE parser — verbatim from the upstream reference
# ---------------------------------------------------------------------------

def parse_chatgpt_stream(raw_sse: str) -> Dict:
    """Parse a ChatGPT SSE stream body into structured messages JSON object.

    ChatGPT SSE events come in three shapes (besides "input_message"):
      1. ``v={"message": {...}}`` — seed/finalization of a message object.
      2. ``v=[{p, o, v}, ...]`` — list of JSON-Patch-like operations.
      3. ``v="text"`` with sticky ``p``/``o`` inherited from the previous event.
    """
    messages: Dict[str, dict] = {}
    conversation_id: Optional[str] = None
    current_id: Optional[str] = None
    last_o: Optional[str] = None
    last_p: Optional[str] = None

    def store(msg: dict) -> Optional[str]:
        msg_id = msg.get("id")
        if not msg_id:
            return None
        parts = msg.get("content", {}).get("parts") or [""]
        messages[msg_id] = {
            "role": msg.get("author", {}).get("role", ""),
            "content": parts[0] if isinstance(parts[0], str) else "",
        }
        return msg_id

    def append(path: Optional[str], op: Optional[str], val) -> None:
        if (
            op == "append"
            and isinstance(val, str)
            and path
            and "content/parts/0" in path
            and current_id in messages
        ):
            messages[current_id]["content"] += val

    for line in raw_sse.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        raw = line[len("data:"):].strip()
        if raw == "[DONE]":
            break
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue

        if data.get("type") == "input_message":
            current_id = store(data.get("input_message", {})) or current_id
            conversation_id = conversation_id or data.get("conversation_id")
            continue

        last_o = data.get("o", last_o)
        last_p = data.get("p", last_p)
        v = data.get("v")

        if isinstance(v, dict) and "message" in v:
            current_id = store(v["message"]) or current_id
            conversation_id = (
                conversation_id
                or v.get("conversation_id")
                or v["message"].get("metadata", {}).get("conversation_id")
            )
        elif isinstance(v, list):
            for patch in v:
                append(patch.get("p"), patch.get("o"), patch.get("v"))
        else:
            append(last_p, last_o, v)

    parent_message_id = next(
        (mid for mid, m in reversed(messages.items()) if m["role"] == "assistant"),
        None,
    )
    result_messages: List[ChatgptMessage] = [
        {"role": m["role"], "content": m["content"]}
        for m in messages.values()
        if m["role"] and m["content"]
    ]

    return {
        "conversation_id": conversation_id,
        "parent_message_id": parent_message_id,
        "messages": result_messages,
    }

# ---------------------------------------------------------------------------
# Browser orchestration
# ---------------------------------------------------------------------------

async def _dismiss_overlays(page) -> None:
    """Best-effort: dismiss the credentials picker and notice overlays."""
    try:
        await page.click("#credentials-picker-container #close", timeout=2000)
    except Exception:
        pass
    try:
        await page.click("div[aria-live='polite'] button", timeout=2000)
    except Exception:
        pass

async def _send_and_capture(page, *, timeout_ms: int = 60000) -> Dict[str, str]:
    """Click the send button and capture the SSE conversation response.

    Returns dict with keys: ``sse_body``, ``request_body``, ``request_headers``.
    """
    captured: Dict[str, str] = {}

    async def on_response(response):
        try:
            url = response.url
            if "backend-anon/f/conversation" not in url and "backend-anon/conversation" not in url:
                return
            ctype = (response.headers or {}).get("content-type", "")
            if "event-stream" not in ctype and "stream" not in ctype:
                return
            body = await response.text()
            req = response.request
            captured["sse_body"] = body
            captured["request_body"] = req.post_data or ""
            try:
                captured["request_headers"] = json.dumps(await req.all_headers())
            except Exception:
                captured["request_headers"] = json.dumps(req.headers)
        except Exception as e:
            logger.warning("response capture failed: {}", e)

    page.on("response", lambda r: asyncio.ensure_future(on_response(r)))

    await page.wait_for_selector("button[data-testid='send-button']", timeout=15000)
    await _dismiss_overlays(page)
    await page.click("button[data-testid='send-button']")

    # Wait for SSE body or timeout.
    deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000.0)
    while "sse_body" not in captured and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.5)
    return captured

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_conversation(prompt: str) -> str:
    """Scrape a single ChatGPT response and return the rendered markdown."""
    url = f"https://chatgpt.com/?prompt={quote_plus(prompt)}"
    logger.info("scraping conversation for prompt: {}", prompt)

    async def _run(page):
        await _warmup_chatgpt(page)
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        captured = await _send_and_capture(page, timeout_ms=60000)
        sse_body = captured.get("sse_body", "")
        parsed = parse_chatgpt_stream(sse_body)
        # Return the most recent assistant message as plain text (mirrors
        # the upstream reference's `format="markdown"` content-return contract).
        assistant_msgs = [m["content"] for m in parsed.get("messages", []) if m["role"] == "assistant"]
        content = "\n\n".join(assistant_msgs).strip()
        logger.success("finished scraping ChatGPT for the prompt: {}", prompt)
        return content

    return await _with_session_retry(_run, label="scrape_conversation")

def _build_post_request(
    prompt: str,
    conversation_id: str,
    parent_message_id: str,
    original_body: dict,
    headers: dict,
) -> dict:
    """Build the JSON body and headers for a follow-up POST to /backend-anon/conversation."""
    new_body = dict(original_body)
    new_body["conversation_id"] = conversation_id
    new_body["parent_message_id"] = parent_message_id
    new_body["messages"] = [
        {
            "id": str(uuid4()),
            "author": {"role": "user"},
            "create_time": time.time(),
            "content": {"content_type": "text", "parts": [prompt]},
        }
    ]
    return {"headers": headers, "body": new_body}

async def scrape_conversations(prompt: List[str]) -> List[ChatgptConversation]:
    """Drive a multi-turn anonymous conversation and return the message log."""
    if not prompt:
        return []

    first_url = f"https://chatgpt.com/?prompt={quote_plus(prompt[0])}"

    async def _run(page):
        prompt_index = 0
        conversations: List[ChatgptConversation] = []
        await _warmup_chatgpt(page)
        await page.goto(first_url, wait_until="domcontentloaded", timeout=45000)
        captured = await _send_and_capture(page, timeout_ms=60000)

        sse_body = captured.get("sse_body", "")
        parsed = parse_chatgpt_stream(sse_body)
        conversation_id = parsed.get("conversation_id")
        parent_message_id = parsed.get("parent_message_id")

        if conversation_id:
            conversations.append(
                {
                    "conversation_id": conversation_id,
                    "messages": parsed.get("messages", []),
                }
            )

        try:
            original_body = json.loads(captured.get("request_body") or "{}")
        except json.JSONDecodeError:
            original_body = {}
        try:
            headers = json.loads(captured.get("request_headers") or "{}")
        except json.JSONDecodeError:
            headers = {}

        while prompt_index < len(prompt) - 1:
            prompt_index += 1
            if not conversation_id:
                logger.warning("no conversation_id captured; stopping multi-turn loop")
                break
            req = _build_post_request(
                prompt[prompt_index],
                conversation_id,
                parent_message_id or "",
                original_body,
                headers,
            )
            # POST from within the page so cookies + cloudflare cookies stick.
            text = await page.evaluate(
                """async ({ url, body, headers }) => {
                    const res = await fetch(url, {
                        method: "POST",
                        headers,
                        body: JSON.stringify(body),
                        credentials: "include",
                    });
                    return await res.text();
                }""",
                {
                    "url": "https://chatgpt.com/backend-anon/conversation",
                    "body": req["body"],
                    "headers": req["headers"],
                },
            )
            post_parsed = parse_chatgpt_stream(text)
            if post_parsed.get("parent_message_id"):
                parent_message_id = post_parsed["parent_message_id"]
            if conversations and post_parsed.get("messages"):
                conversations[-1]["messages"].extend(post_parsed["messages"])
        return conversations

    return await _with_session_retry(_run, label="scrape_conversations")

def to_dict(obj):
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
