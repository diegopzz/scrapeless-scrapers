"""Perplexity scraper using the official Scrapeless Python SDK + Playwright over CDP.

Perplexity gates its answer pages behind Cloudflare and renders the
prompt input as a Lexical contenteditable, not a ``<textarea>``. The
scraper:

1. Warms up on the homepage to clear the Cloudflare cookie challenge.
2. Focuses ``[role='textbox']``, types the prompt, presses Enter.
3. Waits for the URL to settle on ``/search/<uuid>`` and the answer
   prose to render.
4. Extracts the question (``<h1 class="group/query …">``), the answer
   (``<div class="prose …">``), and outbound citation ``<a href>`` links.
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
DEFAULT_SESSION_TTL = 360

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


@dataclass
class Citation:
    url: str
    domain: str
    title: str


@dataclass
class Search:
    query: str
    url: str
    answer_text: str
    citations: list[Citation] = field(default_factory=list)


def _is_transient(err: Exception) -> bool:
    msg = str(err)
    return any(s in msg for s in TRANSIENT_NET_ERRORS)


def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError(
            "SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com"
        )
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()


async def _with_session_retry(fn, *, retries: int = 2, label: str = "perplexity"):
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
            await asyncio.sleep(4 + attempt * 3)
    raise RuntimeError(f"{label}: giving up after {retries + 1} attempts: {last_error}")


async def _warmup(page) -> None:
    await page.goto("https://www.perplexity.ai/", wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(8)


async def _submit_prompt(page, prompt: str) -> None:
    await page.wait_for_selector("[role='textbox'], [contenteditable='true']", timeout=25000)
    await page.click("[role='textbox'], [contenteditable='true']")
    await page.keyboard.type(prompt, delay=30)
    await asyncio.sleep(0.8)
    await page.keyboard.press("Enter")


_URL_PAT = re.compile(r"/search/[0-9a-f-]{8,}", re.IGNORECASE)


async def _wait_for_answer(page, *, timeout_ms: int = 60000) -> None:
    """1. URL settles on `/search/<uuid>`. 2. Answer prose stops growing."""
    loop = asyncio.get_event_loop()
    url_deadline = loop.time() + 20
    while loop.time() < url_deadline:
        if _URL_PAT.search(page.url or ""):
            break
        await asyncio.sleep(0.5)

    start = loop.time()
    last_len = 0
    last_change = loop.time()
    while (loop.time() - start) * 1000 < timeout_ms:
        await asyncio.sleep(0.8)
        try:
            length = await page.evaluate(
                "() => { const el = document.querySelector('div.prose'); return el ? (el.innerText || '').length : 0; }"
            )
        except Exception:
            length = 0
        if length != last_len:
            last_len = length
            last_change = loop.time()
        elif last_len > 50 and (loop.time() - last_change) >= 3:
            return


# ---------------------------------------------------------------------------
# Scrape function
# ---------------------------------------------------------------------------


async def scrape_search(prompt: str) -> Search:
    async def _run(page):
        await _warmup(page)
        await _submit_prompt(page, prompt)
        await _wait_for_answer(page)
        html = await page.content()
        return parse_search(html, prompt, page.url)
    return await _with_session_retry(_run, label="scrape_search")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


_WS_RE = re.compile(r"\s+")
_PPLX_RE = re.compile(r"perplexity\.ai")
_BAD_HOST_RE = re.compile(r"cloudflare\.com|gstatic\.com|twitter\.com/PerplexityAI", re.IGNORECASE)


def _normalise(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip()


def _domain_of(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def parse_search(html: str, prompt: str, final_url: str) -> Search:
    sel = Selector(text=html)

    query_text = _normalise("".join(sel.css("h1[class*='group/query'] *::text").getall()))
    if not query_text:
        query_text = prompt

    answer_text = _normalise(" ".join(sel.css("div[class*='prose']").css("*::text").getall()))
    # First prose block only.
    proses = sel.css("div[class*='prose']")
    if proses:
        answer_text = _normalise(" ".join(proses[0].css("*::text").getall()))

    citations: list[Citation] = []
    seen: set[str] = set()
    for a in sel.css("a[href^='http']"):
        href = a.attrib.get("href", "")
        if not href or href in seen:
            continue
        if _PPLX_RE.search(href):
            continue
        if _BAD_HOST_RE.search(href):
            continue
        seen.add(href)
        title = _normalise("".join(a.css("*::text").getall()))
        citations.append(Citation(url=href, domain=_domain_of(href), title=title))

    return Search(
        query=query_text,
        url=final_url,
        answer_text=answer_text,
        citations=citations,
    )


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
