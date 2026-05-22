"""Grok scraper using the official Scrapeless Python SDK + Playwright over CDP.

Grok conversation sessions require login, but shared conversations at
``grok.com/share/<id>`` are publicly readable without authentication.

Flow:
- ``_client()`` mints a cloud browser session (CDP WS endpoint).
- Playwright connects over CDP and opens ``https://grok.com/share/<id>``.
- The page renders user turns in ``[data-testid="user-message"]`` elements
  and assistant turns in ``[data-testid="assistant-message"]`` elements.
- ``parse_share`` reads those elements and returns a ``SharedConversation``.

Public/shared content only — Grok requires a real session for any
authenticated history or sending messages, which this scraper does NOT attempt.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse

from loguru import logger
from parsel import Selector
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

# Strip the `?rid=...` redirect token Grok appends to share URLs.
_RID_RE = re.compile(r"\?rid=[^&]+(&|$)")


def _is_transient(err: Exception) -> bool:
    msg = str(err)
    return any(s in msg for s in TRANSIENT_NET_ERRORS)


@dataclass
class GrokMessage:
    role: str
    content: str


@dataclass
class SharedConversation:
    url: str
    title: str
    messages: list[GrokMessage] = field(default_factory=list)


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


async def _with_session_retry(fn, *, retries: int = 2, label: str = "grok"):
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=DEFAULT_PROXY_COUNTRY, session_ttl=DEFAULT_SESSION_TTL)
        )
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
            try:
                page = await browser.new_page(viewport={"width": 1366, "height": 900})
                return await fn(page)
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("{} attempt {} failed: {}", label, attempt + 1, e)
                if not _is_transient(e) and attempt > 0:
                    raise
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
        if attempt < retries:
            await asyncio.sleep(5.0 * (2**attempt))
    raise RuntimeError(f"{label}: giving up after {retries + 1} attempts: {last_error}")


# ---------------------------------------------------------------------------
# Parser — anchors on data-testid="user-message" / "assistant-message"
# ---------------------------------------------------------------------------


def parse_share(html: str, final_url: str) -> SharedConversation:
    """Parse a Grok shared-conversation page into a ``SharedConversation``.

    Stable anchors (live-verified 2026-05-21):
    - ``[data-testid="user-message"]``  — each user turn
    - ``[data-testid="assistant-message"]`` — each assistant turn
    - ``<title>`` — "{topic} | Shared Grok Conversation"

    DOM order matches conversation order (user first, then assistant, repeating).
    """
    sel = Selector(text=html)

    # Strip the ?rid=... redirect token so the URL is canonical.
    clean_url = _RID_RE.sub("", final_url).rstrip("?&")

    title = (sel.css("title::text").get() or "").strip()

    messages: list[GrokMessage] = []

    # Collect all message elements in document order using both testid values.
    # parsel doesn't support the CSS `:is()` pseudo; walk elements manually.
    user_texts = sel.css("[data-testid='user-message'] *::text").getall()
    assistant_texts = sel.css("[data-testid='assistant-message'] *::text").getall()

    # Build ordered list by interleaving user and assistant turns.
    # Grok share pages always start with the user turn.
    # We use the raw HTML to preserve document order.
    import re as _re

    # Extract elements in DOM order via a regex over the serialised HTML.
    # data-testid is always on the outermost turn container.
    pattern = _re.compile(
        r'data-testid="(user-message|assistant-message)"[^>]*>(.*?)</[a-z]+>',
        _re.DOTALL | _re.IGNORECASE,
    )

    for m in pattern.finditer(html):
        testid = m.group(1)
        inner_html = m.group(2)
        # Strip HTML tags and normalise whitespace.
        raw_text = _re.sub(r"<[^>]+>", " ", inner_html)
        raw_text = _re.sub(r"\s+", " ", raw_text).strip()
        if not raw_text:
            continue
        role = "user" if testid == "user-message" else "assistant"
        messages.append(GrokMessage(role=role, content=raw_text))

    # Fallback: if regex found nothing (JS-rendered DOM not in static HTML),
    # try parsel selectors on the pre-rendered Playwright HTML.
    if not messages:
        for node in sel.css("[data-testid='user-message'], [data-testid='assistant-message']"):
            testid = node.attrib.get("data-testid", "")
            text = " ".join(node.css("*::text").getall()).strip()
            text = _re.sub(r"\s+", " ", text)
            if not text:
                continue
            role = "user" if testid == "user-message" else "assistant"
            messages.append(GrokMessage(role=role, content=text))

    return SharedConversation(url=clean_url, title=title, messages=messages)


# ---------------------------------------------------------------------------
# Scrape function
# ---------------------------------------------------------------------------


async def scrape_share(url: str) -> SharedConversation:
    """Open a public Grok shared-conversation page and return its transcript.

    ``url`` must be a ``grok.com/share/<id>`` URL. The page renders the full
    conversation without authentication. Navigation may time out on the first
    hop due to Cloudflare challenges — the session-retry wrapper handles that.
    """
    logger.info("scraping Grok share: {}", url)

    async def _run(page):
        # Grok's Cloudflare layer sometimes aborts the first navigation.
        # Even when goto raises a Timeout, the page is already JS-rendered by
        # the time the error fires. Catch timeouts and proceed to evaluate()
        # the live DOM.
        try:
            await page.goto(url, wait_until="load", timeout=30000)
        except Exception as e:
            if "Timeout" not in str(e) and not _is_transient(e):
                raise
            logger.warning("goto timed out / aborted (proceeding to read rendered DOM): {}", e)

        # Extract from the live DOM via evaluate() — Grok's content is
        # JS-rendered so page.content() returns only the static shell.
        raw = await page.evaluate(
            """() => {
                var cleanUrl = (location.href || "").replace(/\\?rid=[^&]+(&|$)/, "").replace(/\\?$/, "");
                var title = document.title || "";
                var msgs = [];
                document.querySelectorAll(
                    "[data-testid='user-message'], [data-testid='assistant-message']"
                ).forEach(function(el) {
                    var testid = el.getAttribute("data-testid") || "";
                    var text = (el.textContent || "").replace(/\\s+/g, " ").trim();
                    if (!text) return;
                    msgs.push({
                        role: testid === "user-message" ? "user" : "assistant",
                        content: text
                    });
                });
                return { url: cleanUrl, title: title, messages: msgs };
            }"""
        )

        messages = [GrokMessage(role=m["role"], content=m["content"]) for m in raw.get("messages", [])]
        result = SharedConversation(url=raw["url"], title=raw["title"], messages=messages)
        logger.success("finished scraping Grok share: {} ({} messages)", url, len(result.messages))
        return result

    return await _with_session_retry(_run, label="scrape_share")


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
