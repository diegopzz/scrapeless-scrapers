"""GoogleAiMode scraper using the official Scrapeless Python SDK + Playwright over CDP.

Google's AI Mode is the streaming AI overlay reachable at
``https://www.google.com/search?q=<query>&udm=50``. The scraper drives the
SERP, waits for the AI panel to stream in, and extracts the answer text
plus cited links.

Flow:
- ``client.browser.create()`` mints a cloud session on Scrapeless's Scraping Browser.
- Playwright connects over CDP, navigates to the SERP with ``udm=50``.
- Wait for the AI panel container, then settle for streamed content.
- Parsel parses the rendered HTML into a single ``AiResponse`` dataclass.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import quote_plus, urlparse

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 240
AI_READY_SELECTOR = "div[data-subtree='aimc'], div[jsname][data-md], div[role='region']"

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


@dataclass
class Citation:
    title: str
    url: str
    source: str


@dataclass
class AiLink:
    url: str
    text: str


@dataclass
class AiResponse:
    query: str
    url: str
    response_text: str
    citations: list[Citation] = field(default_factory=list)
    links: list[AiLink] = field(default_factory=list)


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


async def _settle_for_streamed_content(page, *, idle_ms: int = 3000, ceiling_ms: int = 30000) -> None:
    """Wait for the AI panel to stop changing. Google paints the answer
    incrementally; we bail once ``document.body.innerText.length`` is stable
    for ``idle_ms`` or after a hard ceiling.
    """
    loop = asyncio.get_event_loop()
    start = loop.time()
    last_len = 0
    last_change = loop.time()
    while (loop.time() - start) * 1000 < ceiling_ms:
        await asyncio.sleep(0.5)
        try:
            length = await page.evaluate(
                "() => document.body && document.body.innerText ? document.body.innerText.length : 0"
            )
        except Exception:
            length = 0
        if length != last_len:
            last_len = length
            last_change = loop.time()
        elif (loop.time() - last_change) * 1000 >= idle_ms:
            return


async def _warmup_google(page) -> None:
    """Land on the bare homepage first so Google's NID/consent cookies are
    minted on a less-defended endpoint before hitting the AI Mode SERP.
    """
    try:
        await page.goto("https://www.google.com/", wait_until="domcontentloaded", timeout=30000)
        for selector in ("button[aria-label*='Accept']", "#L2AGLb"):
            try:
                await page.click(selector, timeout=1500)
            except Exception:
                pass
        await asyncio.sleep(1.5)
    except Exception:
        pass


def _is_captcha(page) -> bool:
    u = page.url or ""
    return "/sorry/" in u or "captcha" in u


async def _fetch_ai_mode_html(
    query: str, *, proxy_country: str = DEFAULT_PROXY_COUNTRY, retries: int = 3
) -> tuple[str, str]:
    url = f"https://www.google.com/search?q={quote_plus(query)}&udm=50&hl=en"
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
        )
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
            try:
                page = await browser.new_page(viewport={"width": 1366, "height": 900})
                await _warmup_google(page)
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                if _is_captcha(page):
                    last_error = RuntimeError("captcha interstitial")
                else:
                    try:
                        await page.wait_for_selector(AI_READY_SELECTOR, timeout=20000)
                    except Exception as e:
                        logger.warning("ai panel selector not seen (continuing): {}", e)
                    await _settle_for_streamed_content(page)
                    if _is_captcha(page):
                        last_error = RuntimeError("captcha interstitial")
                    else:
                        html = await page.content()
                        if html:
                            return html, page.url
                        last_error = RuntimeError("empty HTML")
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("attempt {} failed: {}", attempt + 1, e)
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
        if attempt < retries:
            await asyncio.sleep(4 + attempt * 3)
    raise RuntimeError(f"giving up after {retries + 1} attempts: {last_error}")


# ---------------------------------------------------------------------------
# Scrape functions
# ---------------------------------------------------------------------------


async def scrape_ai_response(query: str) -> AiResponse:
    html, final_url = await _fetch_ai_mode_html(query)
    return parse_ai_response(html, query, final_url)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


_WS_RE = re.compile(r"\s+")


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


def parse_ai_response(html: str, query: str, final_url: str) -> AiResponse:
    sel = Selector(text=html)

    candidates = [
        "div[data-subtree='aimc']",
        "div[jsname][data-md]",
        "div[role='region'][aria-label]",
        "#main",
    ]
    panel = None
    for css in candidates:
        for node in sel.css(css):
            text_content = "".join(node.css("*::text").getall()).strip()
            if len(text_content) > 80:
                panel = node
                break
        if panel is not None:
            break
    if panel is None:
        panel = sel.css("body")

    raw_text = " ".join(panel.css("*::text").getall())
    response_text = _normalise(raw_text)

    citations: list[Citation] = []
    seen_cite: set[str] = set()
    links: list[AiLink] = []
    seen_link: set[str] = set()

    for a in panel.css("a[href^='http']"):
        href = a.attrib.get("href", "")
        if not href or "google.com/search" in href or "/url?" in href:
            continue
        text = _normalise("".join(a.css("*::text").getall()))
        aria = a.attrib.get("aria-label", "")
        has_favicon = bool(a.css("img"))
        source = _domain_of(href)

        if has_favicon or aria:
            key = f"{href}|{text}"
            if key not in seen_cite:
                seen_cite.add(key)
                citations.append(Citation(title=text or aria or source, url=href, source=source))

        if href not in seen_link:
            seen_link.add(href)
            links.append(AiLink(url=href, text=text or aria))

    return AiResponse(
        query=query,
        url=final_url or f"https://www.google.com/search?q={quote_plus(query)}&udm=50",
        response_text=response_text,
        citations=citations,
        links=links,
    )


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
