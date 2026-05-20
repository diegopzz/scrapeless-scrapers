"""GoogleNews scraper using the official Scrapeless Python SDK + Playwright over CDP.

Target surface: ``https://news.google.com/search?q=<query>&hl=en`` and any
topic page of the same shape. The scraper renders the SPA, waits for the
headline anchors (``a.JtKRv``) to mount, and yields one ``Article`` per
visible card.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import quote_plus

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 180
# Cards render as `<div class="m5k28">` (sometimes inside `<article>` on
# older layouts). We wait for the headline anchor `a.JtKRv` which is stable
# across both layouts.
READY_SELECTOR = "a.JtKRv, article a"


@dataclass
class Article:
    position: int
    title: str
    url: str
    source: str = ""
    time: str = ""
    thumbnail: str = ""


def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError(
            "SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com"
        )
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()


async def _fetch_rendered_html(
    url: str, ready_selector: str = READY_SELECTOR, *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY, retries: int = 2,
) -> str:
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
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    await page.wait_for_selector(ready_selector, timeout=20000)
                except Exception as e:
                    logger.warning("ready selector not seen (continuing): {}", e)
                await asyncio.sleep(2)
                html = await page.content()
                if html and "JtKRv" in html:
                    return html
                last_error = RuntimeError("no headline anchors in HTML")
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("attempt {} failed: {}", attempt + 1, e)
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
        if attempt < retries:
            await asyncio.sleep(3 + attempt * 2)
    raise RuntimeError(f"giving up after {retries + 1} attempts: {last_error}")


# ---------------------------------------------------------------------------
# Scrape functions
# ---------------------------------------------------------------------------


async def scrape_news(query: str) -> list[Article]:
    url = f"https://news.google.com/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    html = await _fetch_rendered_html(url)
    return parse_news(html)


async def scrape_topic(topic_id: str) -> list[Article]:
    url = f"https://news.google.com/topics/{topic_id}?hl=en-US&gl=US&ceid=US:en"
    html = await _fetch_rendered_html(url)
    return parse_news(html)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


_WS_RE = re.compile(r"\s+")
_HTTP_RE = re.compile(r"^https?:")


def _normalise(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip()


def _split_aria_label(aria: str, title: str) -> tuple[str, str]:
    """aria-label format: "<title> - <source> - <time> - By <author>".

    Returns (source, time).
    """
    if not aria:
        return "", ""
    if aria.startswith(title):
        rest = aria[len(title):]
    else:
        idx = aria.find(" - ")
        rest = aria[idx:] if idx >= 0 else aria
    rest = re.sub(r"^ -\s*", "", rest)
    parts = rest.split(" - ")
    return _normalise(parts[0] if parts else ""), _normalise(parts[1] if len(parts) > 1 else "")


def parse_news(html: str) -> list[Article]:
    sel = Selector(text=html)
    seen: set[str] = set()
    out: list[Article] = []
    position = 0
    for a in sel.css("a.JtKRv"):
        href = a.attrib.get("href", "")
        title = _normalise("".join(a.css("*::text").getall()))
        if not href or not title:
            continue
        abs_url = f"https://news.google.com{href[1:]}" if href.startswith("./") else href
        if abs_url in seen:
            continue
        seen.add(abs_url)

        aria = a.attrib.get("aria-label", "")
        source, time = _split_aria_label(aria, title)

        # Walk up to the card container for the thumbnail.
        thumbnail = ""
        cards = a.xpath(
            "ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' m5k28 ')"
            " or self::article"
            " or contains(concat(' ', normalize-space(@class), ' '), ' IBr9hb ')"
            " or contains(concat(' ', normalize-space(@class), ' '), ' XlKvRb ')][1]"
        )
        if cards:
            for img in cards[0].css("img"):
                src = img.attrib.get("src") or img.attrib.get("data-src") or ""
                if _HTTP_RE.match(src):
                    thumbnail = src
                    break

        position += 1
        out.append(Article(
            position=position,
            title=title,
            url=abs_url,
            source=source,
            time=time,
            thumbnail=thumbnail,
        ))
    return out


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
