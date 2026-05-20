"""Expedia scraper using the official Scrapeless Python SDK + Playwright over CDP.

Two surfaces:
- ``scrape_search(destination, checkin, checkout, max_pages)`` —
  ``[data-stid="lodging-card-responsive"]`` cards on `/Hotel-Search`.
- ``scrape_hotel(hotel_url)`` — hotel detail page.

Expedia ships an aggressive "Bot or Not?" interstitial on cold visits to
`/Hotel-Search`. We warm up on the homepage first so the session has the
cookies it expects before navigating to the search URL.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, List, Optional
from urllib.parse import urlencode

from loguru import logger
from parsel import Selector
from playwright.async_api import Page, async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 300
HOMEPAGE_URL = "https://www.expedia.com/"


TRANSIENT_NET_ERRORS = (
    "ERR_TUNNEL_CONNECTION_FAILED",
    "ERR_CONNECTION_CLOSED",
    "ERR_CONNECTION_RESET",
    "ERR_TIMED_OUT",
    "net::",
)


def _is_transient_error(err: BaseException) -> bool:
    msg = str(err)
    return any(s in msg for s in TRANSIENT_NET_ERRORS)


@dataclass
class SearchResult:
    id: str
    name: str
    url: str
    price: Optional[str] = None
    review: Optional[str] = None
    image: Optional[str] = None


@dataclass
class Hotel:
    id: str
    url: str
    name: str
    description: str
    amenities: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    address: Optional[str] = None
    review: Optional[str] = None
    price: Optional[str] = None


def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError(
            "SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com"
        )
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()


async def _warm_page(page: Page) -> None:
    try:
        await page.goto(HOMEPAGE_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(4500)
        try:
            await page.evaluate("() => window.scrollBy(0, 600)")
        except Exception:
            pass
        await page.wait_for_timeout(2500)
        try:
            await page.evaluate("() => window.scrollBy(0, 600)")
        except Exception:
            pass
        await page.wait_for_timeout(1500)
    except Exception as e:  # noqa: BLE001
        logger.warning("homepage warm-up failed (continuing): {}", e)


async def _with_warmed_browser(
    fn,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 3,
    label: str = "navigation",
):
    last_error: BaseException | None = None
    for attempt in range(retries + 1):
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
        )
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
            try:
                page = await browser.new_page()
                await _warm_page(page)
                result = await fn(page)
                try:
                    title = await page.title()
                except Exception:
                    title = ""
                if "bot or not" in (title or "").lower():
                    last_error = RuntimeError(f'hit anti-bot interstitial (title="{title}")')
                else:
                    return result
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("{} attempt {} failed: {}", label, attempt + 1, e)
                if attempt == retries and not _is_transient_error(e) and "bot or not" not in str(e).lower():
                    raise
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
        if attempt < retries:
            await asyncio.sleep(6 * (1.5 ** attempt))
    raise RuntimeError(f"{label}: giving up after {retries + 1} attempts: {last_error}")


_HTML_ENTITY_RE = (
    ("&amp;", "&"),
    ("&quot;", '"'),
    ("&#x27;", "'"),
    ("&#39;", "'"),
    ("&lt;", "<"),
    ("&gt;", ">"),
)


def _decode_entities(s: Optional[str]) -> str:
    if not s:
        return s or ""
    for a, b in _HTML_ENTITY_RE:
        s = s.replace(a, b)
    return s


def _abs(rel: str) -> str:
    if not rel:
        return ""
    if rel.startswith("http"):
        return rel
    return f"https://www.expedia.com{'' if rel.startswith('/') else '/'}{rel}"


_HOTEL_ID_RE = re.compile(r"\.h(\d+)\.Hotel-Information")


def _extract_hotel_id(url: str) -> str:
    m = _HOTEL_ID_RE.search(url or "")
    return m.group(1) if m else ""


# ---------------- search ----------------


def parse_search(html: str) -> List[SearchResult]:
    sel = Selector(text=html)
    out: List[SearchResult] = []
    for card in sel.css("div[data-stid='lodging-card-responsive']"):
        name = _decode_entities(
            (card.css("h3.uitk-heading::text").get() or card.css("h3::text").get() or "").strip()
        )
        href = (
            card.css("a.uitk-card-link::attr(href)").get()
            or card.css("a[href*='Hotel-Information']::attr(href)").get()
            or ""
        )
        href = _decode_entities(href)
        url = _abs(href)
        hid = _extract_hotel_id(href)
        price_block = " ".join(card.css("[data-test-id='price-summary-message-line'] *::text").getall())
        price_m = re.search(r"\$[\d,]+", price_block) if price_block else None
        price = price_m.group(0) if price_m else None
        review: Optional[str] = None
        for a in card.css("[aria-label]::attr(aria-label)").getall():
            if re.search(r"out of \d+", a):
                review = a
                break
        image = card.css("img::attr(src)").get()
        if name and hid:
            out.append(SearchResult(id=hid, name=name, url=url, price=price, review=review, image=image))
    return out


async def scrape_search(
    destination: str = "New York",
    checkin: str = "2026-06-15",
    checkout: str = "2026-06-16",
    max_pages: int = 1,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
) -> List[SearchResult]:
    out: List[SearchResult] = []
    params: dict[str, str] = {
        "destination": destination,
        "startDate": checkin,
        "endDate": checkout,
        "rooms": "1",
        "adults": "2",
    }
    for page_no in range(1, max_pages + 1):
        if page_no > 1:
            params["pageIndex"] = str(page_no)
        url = f"https://www.expedia.com/Hotel-Search?{urlencode(params)}"

        async def _run(p: Page):
            await p.goto(url, wait_until="domcontentloaded", timeout=60000)
            try:
                await p.wait_for_selector("div[data-stid='lodging-card-responsive']", timeout=30000)
            except Exception as e:
                logger.warning("lodging-card wait failed (continuing): {}", e)
            try:
                await p.evaluate(
                    "() => new Promise(r => { let y = 0; const i = setInterval(() => { window.scrollBy(0, 800); y += 800; if (y >= document.body.scrollHeight) { clearInterval(i); r(); } }, 350); })"
                )
            except Exception:
                pass
            await p.wait_for_timeout(2500)
            html = await p.content()
            return parse_search(html)

        items = await _with_warmed_browser(_run, proxy_country=proxy_country, label=f"scrape_search page={page_no}")
        if not items and page_no > 1:
            break
        out.extend(items)
    return out


# ---------------- hotel ----------------


def parse_hotel(html: str, url: str) -> Hotel:
    sel = Selector(text=html)
    name = _decode_entities(
        (sel.css("h1.uitk-heading::text").get() or sel.css("h1::text").get() or sel.css("meta[property='og:title']::attr(content)").get() or "").strip()
    )
    address = (
        sel.css("[data-stid='content-hotel-address']::text").get()
        or sel.css("[data-stid='content-hotel-address-link']::text").get()
        or sel.css("button[aria-label*='address']::text").get()
    )
    description = (
        "".join(sel.css("div[data-stid='content-section-section-content'] *::text").getall()).strip()
        or "".join(sel.css("section[data-stid='content-section-about-this-property'] *::text").getall()).strip()
        or sel.css("meta[property='og:description']::attr(content)").get(default="")
    )
    amenities = [
        t.strip()
        for t in sel.css(
            "[data-stid*='amenity'] li *::text, [data-stid='content-amenities-list'] li *::text"
        ).getall()
        if t.strip()
    ]
    images: List[str] = []
    for src in sel.css("img::attr(src), img::attr(data-src)").getall():
        if src and re.search(r"/(media|images|gold|hotels)/", src, re.I) and src not in images:
            images.append(src)
    review: Optional[str] = None
    for a in sel.css("[aria-label]::attr(aria-label)").getall():
        if re.search(r"out of \d+", a):
            review = a
            break
    price = (
        (sel.css("[data-test-id='price-summary'] span::text").get() or "").strip()
        or (sel.css("[data-stid='price-and-discount']::text").get() or "").strip()
        or None
    )
    return Hotel(
        id=_extract_hotel_id(url),
        url=url,
        name=name,
        address=address,
        description=description,
        amenities=amenities,
        images=images[:30],
        review=review,
        price=price,
    )


async def scrape_hotel(hotel_url: str, *, proxy_country: str = DEFAULT_PROXY_COUNTRY) -> Hotel:
    async def _run(p: Page):
        await p.goto(hotel_url, wait_until="domcontentloaded", timeout=60000)
        try:
            await p.wait_for_selector("h1", timeout=30000)
        except Exception as e:
            logger.warning("h1 wait failed (continuing): {}", e)
        try:
            await p.evaluate("() => window.scrollBy(0, 1200)")
        except Exception:
            pass
        await p.wait_for_timeout(2500)
        html = await p.content()
        return parse_hotel(html, hotel_url)

    return await _with_warmed_browser(_run, proxy_country=proxy_country, label="scrape_hotel")


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
