"""Craigslist scraper using the official Scrapeless Python SDK + Playwright over CDP.

Under the hood:
- `client.browser.create()` mints a cloud session on Scrapeless's Scraping Browser,
  returning a CDP WebSocket endpoint (`browser_ws_endpoint`).
- Playwright connects to that WebSocket, drives the page, returns rendered HTML.
- Parsel parses the HTML into typed dataclasses matching DATA_MODEL.md.

Two surfaces:
- ``scrape_search(city, category, query, max_pages)`` — gallery cards on a city search page.
- ``scrape_listing(url)`` — standalone listing detail page.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, List, Optional
from urllib.parse import urljoin, urlencode

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 180
SEARCH_PAGE_SLEEP_S = 4.5

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


@dataclass
class SearchResult:
    id: str
    title: str
    url: str
    price: Optional[str] = None
    location: Optional[str] = None
    postedAt: Optional[str] = None
    image: Optional[str] = None


@dataclass
class Listing:
    id: str
    url: str
    title: str
    description: str
    attributes: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    price: Optional[str] = None
    location: Optional[str] = None
    postedAt: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    section: Optional[str] = None
    category: Optional[str] = None


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


async def _fetch_rendered_html(
    url: str,
    ready_selector: Optional[str] = None,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 1,
) -> str:
    """Mint a session, navigate, wait for stable marker, return HTML."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
        )
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=20000)
                    except Exception as e:
                        logger.warning("wait_for_selector {!r} failed (continuing): {}", ready_selector, e)
                # Lazy gallery cards: nudge with a scroll.
                try:
                    await page.evaluate("() => window.scrollBy(0, 800)")
                except Exception:
                    pass
                await page.wait_for_timeout(2500)
                html = await page.content()
                if html:
                    return html
                last_error = RuntimeError("empty HTML")
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("attempt {} failed: {}", attempt + 1, e)
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
    raise RuntimeError(f"giving up after {retries + 1} attempts: {last_error}")


def _abs(base: str, rel: str) -> str:
    try:
        return urljoin(base, rel)
    except Exception:
        return rel


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def parse_search(html: str, base_url: str) -> List[SearchResult]:
    sel = Selector(text=html)
    out: List[SearchResult] = []
    for li in sel.css(".cl-search-result"):
        pid = li.attrib.get("data-pid", "")
        if not pid:
            continue
        title = (
            li.css("a.posting-title span.label::text").get(default="").strip()
            or li.attrib.get("title", "")
        )
        href = (
            li.css("a.posting-title::attr(href)").get()
            or li.css("a.main::attr(href)").get()
            or ""
        )
        url = _abs(base_url, href) if href else ""
        price = li.css("span.priceinfo::text").get()
        location = li.css("span.result-location::text").get()
        posted_at = li.css("span.result-posted-date::text").get()
        image = li.css("div.swipe img::attr(src)").get()
        if pid and title:
            out.append(
                SearchResult(
                    id=pid,
                    title=title.strip(),
                    url=url,
                    price=price.strip() if price else None,
                    location=location.strip() if location else None,
                    postedAt=posted_at.strip() if posted_at else None,
                    image=image,
                )
            )
    return out


async def scrape_search(
    city: str = "newyork",
    category: str = "sss",
    query: str = "",
    max_pages: int = 1,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
) -> List[SearchResult]:
    base = f"https://{city}.craigslist.org/search/{category}"
    out: List[SearchResult] = []
    for page in range(max_pages):
        params: dict[str, str] = {}
        if query:
            params["query"] = query
        if page > 0:
            params["s"] = str(page * 120)
        url = f"{base}?{urlencode(params)}" if params else base
        html = await _fetch_rendered_html(
            url,
            ready_selector=".cl-search-result, ol.cl-static-search-results",
            proxy_country=proxy_country,
        )
        items = parse_search(html, url)
        if not items and page > 0:
            break
        out.extend(items)
        if page + 1 < max_pages:
            await asyncio.sleep(SEARCH_PAGE_SLEEP_S)
    return out


# ---------------------------------------------------------------------------
# Listing detail
# ---------------------------------------------------------------------------


_LISTING_ID_RE = re.compile(r"/(\d+)\.html")


def _extract_listing_id(url: str) -> str:
    m = _LISTING_ID_RE.search(url)
    return m.group(1) if m else ""


def parse_listing(html: str, url: str) -> Listing:
    sel = Selector(text=html)
    title = (sel.css("#titletextonly::text").get() or "").strip()
    price = sel.css("h1.postingtitle span.price::text").get() or sel.css("span.price::text").get()
    # Location: parenthetical after the title in postingtitle.
    title_html = sel.css("h1.postingtitle").get() or ""
    loc_match = re.search(r"\(([^()]+)\)\s*<", title_html)
    location = loc_match.group(1).strip() if loc_match else None
    posted_at = sel.css("time.date.timeago::attr(datetime)").get()
    description_parts = sel.css("#postingbody *::text").getall()
    description = "".join(description_parts)
    description = re.sub(r"^\s*QR Code Link to This Post\s*", "", description, count=1).strip()
    attributes = [t.strip() for t in sel.css("p.attrgroup span::text").getall() if t.strip()]
    images = [h for h in sel.css("#thumbs a::attr(href)").getall() if h]
    if not images:
        images = [s for s in sel.css("div.slide img::attr(src)").getall() if s]
    latitude = sel.css("div#map::attr(data-latitude)").get()
    longitude = sel.css("div#map::attr(data-longitude)").get()
    crumbs = [t.strip() for t in sel.css("ul.breadcrumbs li::text").getall() if t.strip()]
    section = crumbs[1] if len(crumbs) >= 2 else None
    category = crumbs[2] if len(crumbs) >= 3 else None
    return Listing(
        id=_extract_listing_id(url),
        url=url,
        title=title,
        price=price.strip() if price else None,
        location=location,
        postedAt=posted_at,
        description=description,
        attributes=attributes,
        images=images,
        latitude=latitude,
        longitude=longitude,
        section=section,
        category=category,
    )


async def scrape_listing(url: str, *, proxy_country: str = DEFAULT_PROXY_COUNTRY) -> Listing:
    html = await _fetch_rendered_html(
        url,
        ready_selector="#titletextonly, h1.postingtitle",
        proxy_country=proxy_country,
    )
    return parse_listing(html, url)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
