"""Google Maps scraper using the official Scrapeless Python SDK + Playwright over CDP.

Two kinds:
- places (list): search-results feed on `/maps/search/<query>` — parsed from
  `[role='feed'] [role='article']` card text, one row per visible card.
- place (detail): single place panel on `/maps/place/<slug>/<coords>` — parsed
  from `h1`, `aria-label` anchors (Address/Website/Phone), and `div.F7nice`.

Google Maps renders entirely client-side. We connect with `waitUntil="domcontentloaded"`
and settle for 8 s so the React/JS panel mounts before we read the DOM.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Dict, List, Optional, TypedDict
from urllib.parse import quote_plus

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 240
MAPS_BASE = "https://www.google.com/maps"

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class Place(TypedDict, total=False):
    name: str
    category: Optional[str]
    address: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    rating: Optional[float]
    review_count: Optional[int]
    price_level: Optional[str]
    description: Optional[str]
    url: str


# ---------------------------------------------------------------------------
# Scrapeless plumbing
# ---------------------------------------------------------------------------


def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com")
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()


async def _fetch_rendered_html(
    url: str,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 2,
    settle_ms: int = 8000,
) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
        )
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
            try:
                page = await browser.new_page()
                await page.set_viewport_size({"width": 1366, "height": 900})
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                if settle_ms > 0:
                    await asyncio.sleep(settle_ms / 1000)
                html = await page.content()
                if html and len(html) > 5000:
                    return html
                last_error = RuntimeError(f"short HTML len={len(html) if html else 0}")
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("attempt {} failed: {}", attempt + 1, e)
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
    raise RuntimeError(f"giving up after {retries + 1} attempts: {last_error}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RATING_RE = re.compile(r"(\d+(?:[.,]\d+)?)")
_REVIEW_RE = re.compile(r"([\d,]+)\s*reviews?", re.I)


def _parse_rating(text: str) -> Optional[float]:
    m = _RATING_RE.search(text)
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def _parse_review_count(text: str) -> Optional[int]:
    m = _REVIEW_RE.search(text)
    if m:
        return int(m.group(1).replace(",", ""))
    return None


def _aria_val(sel: Selector, prefix: str) -> Optional[str]:
    """Extract the value after a known aria-label prefix."""
    raw = sel.xpath(f"//*[starts-with(@aria-label, '{prefix}')]/@aria-label").get()
    if raw:
        return raw[len(prefix):].strip() or None
    return None


# ---------------------------------------------------------------------------
# Place list — /maps/search/<query>
# ---------------------------------------------------------------------------


def parse_places(html: str, base_url: str) -> List[Place]:
    sel = Selector(text=html)
    out: List[Place] = []
    for article in sel.css("[role='feed'] [role='article']"):
        link = article.css("a.hfpxzc")
        name = link.attrib.get("aria-label", "").strip()
        href = link.attrib.get("href", "")
        if not name:
            continue
        text = "\n".join(article.css("::text").getall())
        # Text lines: "Name\nRating\nCategory · Price · Address\nDescription\nHours"
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        # Rating is usually the second token (digits + decimals)
        rating: Optional[float] = None
        review_count: Optional[int] = None
        category: Optional[str] = None
        address: Optional[str] = None
        price_level: Optional[str] = None
        description: Optional[str] = None
        for ln in lines:
            if not rating:
                r = _RATING_RE.match(ln)
                if r:
                    val = float(r.group(1).replace(",", "."))
                    if 1.0 <= val <= 5.0:
                        rating = val
                        continue
            # "Coffee shop · $1-10 · 221 W N Loop Blvd"
            if " · " in ln:
                parts = [p.strip() for p in ln.split(" · ")]
                for i, p in enumerate(parts):
                    if not category and re.search(r"shop|cafe|restaurant|bar|store|market|gym|salon|hotel|diner|bakery|lounge", p, re.I):
                        category = p
                    elif not price_level and re.match(r"\$[\d–\-]", p):
                        price_level = p
                    elif not address and re.search(r"\d+\s+\w", p) and len(p) > 6:
                        address = p
            # Description is a standalone line that's not a category/address/hours
            elif ln and not rating and not re.match(r"(Open|Closed|Opens|Closes)", ln, re.I):
                if not description and len(ln) > 15:
                    description = ln
        out.append(
            Place(
                name=name,
                category=category,
                address=address,
                phone=None,
                website=None,
                rating=rating,
                review_count=review_count,
                price_level=price_level,
                description=description,
                url=href if href.startswith("http") else f"{MAPS_BASE}{href}",
            )
        )
    return out


async def scrape_places(query: str, *, proxy_country: str = DEFAULT_PROXY_COUNTRY) -> List[Place]:
    url = f"{MAPS_BASE}/search/{quote_plus(query)}"
    html = await _fetch_rendered_html(url, proxy_country=proxy_country)
    return parse_places(html, url)


# ---------------------------------------------------------------------------
# Place detail — /maps/place/<slug>/<coords>
# ---------------------------------------------------------------------------


def parse_place(html: str, url: str) -> Place:
    sel = Selector(text=html)
    name = "".join(sel.css("h1 ::text").getall()).strip()

    address = _aria_val(sel, "Address: ")
    website = _aria_val(sel, "Website: ")
    phone = _aria_val(sel, "Phone: ")

    # Rating from div.F7nice or aria-label on the rating widget
    rating_text = "".join(sel.css("div.F7nice ::text").getall()).strip()
    rating = _parse_rating(rating_text)

    # Review count from [aria-label*="reviews"]
    review_label = sel.xpath("//*[contains(@aria-label, 'reviews')]/@aria-label").get() or ""
    review_count = _parse_review_count(review_label)

    # Category from button.DkEaL (primary type button)
    category = sel.css("button.DkEaL::text").get()
    if category:
        category = category.strip()

    # Price level and description from body text snippet
    body_text = " ".join(sel.css("body ::text").getall())
    price_m = re.search(r"\$[\d\–\-]+(?:\s*per\s+person)?", body_text)
    price_level = price_m.group(0) if price_m else None

    # Short editorial description is usually in a span after the buttons row
    desc_m = re.search(
        r"(?:Cool|Hip|Trendy|Cozy|Popular|Vibrant|Classic|Modern|Casual)[^.]{10,200}\.",
        body_text,
    )
    description = desc_m.group(0).strip() if desc_m else None

    return Place(
        name=name,
        category=category,
        address=address,
        phone=phone,
        website=website,
        rating=rating,
        review_count=review_count,
        price_level=price_level,
        description=description,
        url=url,
    )


async def scrape_place(place_url: str, *, proxy_country: str = DEFAULT_PROXY_COUNTRY) -> Place:
    html = await _fetch_rendered_html(place_url, proxy_country=proxy_country)
    return parse_place(html, place_url)


def to_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
