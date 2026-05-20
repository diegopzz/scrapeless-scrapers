"""Trivago scraper using the official Scrapeless Python SDK + Playwright over CDP.

Two surfaces:
- ``scrape_search(destination_url, max_pages)`` — parses the JSON-LD `ItemList`
  that Trivago server-renders on every odr/srl destination page.
- ``scrape_destination(destination_url)`` — adds breadcrumb + FAQ context from
  the same SSR payload.

Trivago is anti-bot-heavy in the DOM (results load via GraphQL after JS
hydration) but the JSON-LD `ItemList` is rendered server side, so we extract
hotels with rating/review data without chasing the GraphQL XHR.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 240


@dataclass
class SearchResult:
    position: int
    name: str
    url: str
    address: Optional[str] = None
    image: Optional[str] = None
    description: Optional[str] = None
    priceRange: Optional[str] = None
    ratingValue: Optional[float] = None
    reviewCount: Optional[int] = None
    bestRating: Optional[float] = None
    worstRating: Optional[float] = None


@dataclass
class Destination:
    url: str
    name: str
    breadcrumbs: List[str] = field(default_factory=list)
    faq: List[Dict[str, Optional[str]]] = field(default_factory=list)
    topHotels: List[Dict[str, Any]] = field(default_factory=list)
    totalHotels: Optional[int] = None


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
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=20000)
                    except Exception as e:
                        logger.warning("wait_for_selector {!r} failed (continuing): {}", ready_selector, e)
                await page.wait_for_timeout(3000)
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


def _extract_json_ld_blocks(html: str) -> List[Any]:
    sel = Selector(text=html)
    out: List[Any] = []
    for raw in sel.css("script[type='application/ld+json']::text").getall():
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except Exception:
            continue
    return out


def _find_item_list(blocks: List[Any]) -> Optional[Dict[str, Any]]:
    for b in blocks:
        if isinstance(b, dict) and b.get("@type") == "ItemList" and isinstance(b.get("itemListElement"), list):
            return b
    return None


def _find_faq(blocks: List[Any]) -> List[Dict[str, Optional[str]]]:
    for b in blocks:
        if isinstance(b, dict) and b.get("@type") == "FAQPage" and isinstance(b.get("mainEntity"), list):
            out: List[Dict[str, Optional[str]]] = []
            for q in b["mainEntity"]:
                if not isinstance(q, dict):
                    continue
                ans = (q.get("acceptedAnswer") or {}).get("text") if isinstance(q.get("acceptedAnswer"), dict) else None
                out.append({"question": q.get("name"), "answer": ans})
            return [o for o in out if o["question"]]
    return []


def _find_breadcrumbs(blocks: List[Any]) -> List[str]:
    for b in blocks:
        if isinstance(b, dict) and b.get("@type") == "BreadcrumbList" and isinstance(b.get("itemListElement"), list):
            crumbs: List[str] = []
            for li in b["itemListElement"]:
                item = li.get("item") if isinstance(li, dict) else None
                if isinstance(item, dict) and item.get("name"):
                    crumbs.append(item["name"])
            return crumbs
    return []


def _to_number(v: Any) -> Optional[float]:
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v: Any) -> Optional[int]:
    if v in (None, ""):
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        try:
            return int(str(v).replace(",", ""))
        except (TypeError, ValueError):
            return None


def _map_hotel_item(el: Dict[str, Any]) -> SearchResult:
    item = el.get("item") if isinstance(el, dict) and isinstance(el.get("item"), dict) else el
    if not isinstance(item, dict):
        item = {}
    rating = item.get("aggregateRating") if isinstance(item.get("aggregateRating"), dict) else {}
    return SearchResult(
        position=_to_int(el.get("position") if isinstance(el, dict) else None) or 0,
        name=item.get("name", "") or "",
        url=item.get("url", "") or "",
        address=item.get("address") or None,
        image=item.get("image") or None,
        description=item.get("description") or None,
        priceRange=item.get("priceRange") or None,
        ratingValue=_to_number(rating.get("ratingValue")),
        reviewCount=_to_int(rating.get("reviewCount")),
        bestRating=_to_number(rating.get("bestRating")),
        worstRating=_to_number(rating.get("worstRating")),
    )


# ---------------- search ----------------


def parse_search(html: str) -> List[SearchResult]:
    blocks = _extract_json_ld_blocks(html)
    item_list = _find_item_list(blocks)
    if not item_list:
        return []
    out: List[SearchResult] = []
    for el in item_list.get("itemListElement", []):
        item = el.get("item") if isinstance(el, dict) else None
        if not isinstance(item, dict) or item.get("@type") != "Hotel":
            continue
        h = _map_hotel_item(el)
        if h.name:
            out.append(h)
    return out


def _append_offset(url: str, offset: int) -> str:
    parsed = urlparse(url)
    params = dict(parse_qsl(parsed.query))
    params["offset"] = str(offset)
    return urlunparse(parsed._replace(query=urlencode(params)))


async def scrape_search(
    destination_url: str,
    max_pages: int = 1,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
) -> List[SearchResult]:
    out: List[SearchResult] = []
    for page in range(1, max_pages + 1):
        url = destination_url if page == 1 else _append_offset(destination_url, (page - 1) * 25)
        html = await _fetch_rendered_html(
            url,
            ready_selector="script[type='application/ld+json']",
            proxy_country=proxy_country,
        )
        items = parse_search(html)
        if not items and page > 1:
            break
        out.extend(items)
    return out


# ---------------- destination ----------------


def parse_destination(html: str, url: str) -> Destination:
    sel = Selector(text=html)
    blocks = _extract_json_ld_blocks(html)
    item_list = _find_item_list(blocks)
    breadcrumbs = _find_breadcrumbs(blocks)
    faq = _find_faq(blocks)
    title_text = (sel.css("title::text").get() or "").strip()
    name = breadcrumbs[-1] if breadcrumbs else ""
    if not name:
        name = (sel.css("h1::text").get() or "").strip() or title_text.split("|")[0].strip()
    total_hotels = None
    top_hotels: List[Dict[str, Any]] = []
    if item_list:
        total_hotels = _to_int(item_list.get("numberOfItems")) or len(item_list.get("itemListElement", []))
        for el in item_list.get("itemListElement", []):
            item = el.get("item") if isinstance(el, dict) else None
            if isinstance(item, dict) and item.get("@type") == "Hotel":
                h = _map_hotel_item(el)
                if h.name:
                    top_hotels.append(asdict(h))
    return Destination(
        url=url,
        name=name,
        breadcrumbs=breadcrumbs,
        totalHotels=total_hotels,
        faq=faq,
        topHotels=top_hotels,
    )


async def scrape_destination(
    destination_url: str,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
) -> Destination:
    html = await _fetch_rendered_html(
        destination_url,
        ready_selector="script[type='application/ld+json']",
        proxy_country=proxy_country,
    )
    return parse_destination(html, destination_url)


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
