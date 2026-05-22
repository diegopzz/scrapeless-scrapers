"""Flipkart scraper using the official Scrapeless Python SDK + Playwright over CDP.

Product pages at www.flipkart.com/<slug>/p/<id> ship a schema.org Product ld+json array
(dynamically injected after ~12 s of JS hydration). The block contains name, sku, brand,
description, image[], offers (price, priceCurrency, availability) and aggregateRating.
No BreadcrumbList ld+json is present so breadcrumb is always [].

Search pages at www.flipkart.com/search?q=<query> render product cards in [data-id]
elements; name from .RG5Slk (img alt fallback), price from .hZ3P6w, rating from .MKiFS6.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Dict, List, Optional, TypedDict

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "IN"
DEFAULT_SESSION_TTL = 300
ORIGIN = "https://www.flipkart.com"


class Product(TypedDict, total=False):
    id: str
    name: str
    brand: Optional[str]
    description: Optional[str]
    image: Optional[str]
    price: Optional[float]
    priceCurrency: Optional[str]
    availability: Optional[str]
    ratingValue: Optional[float]
    reviewCount: Optional[int]
    url: str
    breadcrumb: List[Dict[str, Any]]


class SearchResult(TypedDict, total=False):
    id: str
    name: str
    url: Optional[str]
    image: Optional[str]
    price: Optional[float]
    priceCurrency: Optional[str]
    ratingValue: Optional[float]


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
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 2,
    settle_ms: int = 12000,
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
                await page.set_extra_http_headers({"accept-language": "en-IN,en;q=0.9"})
                await page.set_viewport_size({"width": 1366, "height": 900})
                # Flipkart requires ~12 s for JS hydration to inject ld+json and render price
                await page.goto(url, wait_until="load", timeout=90000)
                if settle_ms > 0:
                    await asyncio.sleep(settle_ms / 1000)
                html = await page.content()
                if html and len(html) > 10000:
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


def _ld_blocks(html: str) -> List[Dict[str, Any]]:
    sel = Selector(text=html)
    out: List[Dict[str, Any]] = []
    for raw in sel.css('script[type="application/ld+json"]::text').getall():
        try:
            parsed = json.loads(raw)
            # Flipkart wraps the Product in a top-level array
            if isinstance(parsed, list):
                out.extend(parsed)
            else:
                out.append(parsed)
        except Exception:
            continue
    return out


def _find_type(blocks: List[Dict[str, Any]], type_name: str) -> Optional[Dict[str, Any]]:
    for b in blocks:
        if str(b.get("@type") or "").lower() == type_name.lower():
            return b
    return None


def _parse_price_text(text: str) -> Optional[float]:
    if not text:
        return None
    m = re.search(r"[\d,]+", text)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

def parse_product(html: str, url: str) -> Product:
    blocks = _ld_blocks(html)
    prod = _find_type(blocks, "Product")
    if not prod:
        raise RuntimeError("could not find Product ld+json on page")

    # Flipkart does not ship a BreadcrumbList ld+json block
    breadcrumb: List[Dict[str, Any]] = []

    offers = prod.get("offers")
    offer = offers[0] if isinstance(offers, list) else (offers or {})
    rating = prod.get("aggregateRating") or {}

    image = prod.get("image")
    if isinstance(image, list):
        image = image[0] if image else None

    brand_raw = prod.get("brand")
    if isinstance(brand_raw, dict):
        brand = brand_raw.get("name")
    elif isinstance(brand_raw, str):
        brand = brand_raw
    else:
        brand = None

    price = offer.get("price")
    price_val = float(price) if price is not None else None

    review_count = rating.get("reviewCount")

    return {
        "id": str(prod.get("sku") or ""),
        "name": prod.get("name") or "",
        "brand": brand,
        "description": prod.get("description") or None,
        "image": image,
        "price": price_val,
        "priceCurrency": offer.get("priceCurrency") or "INR",
        "availability": offer.get("availability"),
        "ratingValue": float(rating["ratingValue"]) if rating.get("ratingValue") is not None else None,
        "reviewCount": int(review_count) if review_count is not None else None,
        "url": url,
        "breadcrumb": breadcrumb,
    }


async def scrape_product(product_url: str) -> Product:
    url = (
        product_url if product_url.startswith("http")
        else f"{ORIGIN}{'/' if not product_url.startswith('/') else ''}{product_url}"
    )
    html = await _fetch_rendered_html(url, settle_ms=12000)
    return parse_product(html, url)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def parse_search(html: str) -> List[SearchResult]:
    sel = Selector(text=html)
    items: List[SearchResult] = []

    for card in sel.css("[data-id]"):
        item_id = card.attrib.get("data-id", "")

        # Product link
        href = card.css('a[href*="/p/"]::attr(href)').get() or ""
        url = (ORIGIN + href.split("?")[0]) if href else None

        # Name: .RG5Slk is the current product title class; img alt is the fallback
        name = (
            card.css(".RG5Slk::text").get() or
            card.css("img::attr(alt)").get() or ""
        ).strip()

        # Image
        image = card.css("img::attr(src)").get()

        # Price: .hZ3P6w holds the formatted price (e.g. "₹69,900")
        price_text = (card.css(".hZ3P6w::text").get() or "").strip()
        price = _parse_price_text(price_text)

        # Rating: .MKiFS6 holds the numeric rating (e.g. "4.6")
        rating_text = (card.css(".MKiFS6::text").get() or "").strip()
        rating_value = float(rating_text) if rating_text else None

        if item_id and (name or url):
            items.append({
                "id": item_id,
                "name": name,
                "url": url,
                "image": image,
                "price": price,
                "priceCurrency": "INR",
                "ratingValue": rating_value,
            })

    return items


async def scrape_search(search_url: str, max_pages: int = 1) -> List[SearchResult]:
    out: List[SearchResult] = []
    html = await _fetch_rendered_html(search_url, settle_ms=6000)
    out.extend(parse_search(html))

    # Flipkart search pagination: &page=2, &page=3, …
    import urllib.parse as urlparse
    for page in range(2, max_pages + 1):
        parsed = urlparse.urlparse(search_url)
        qs = urlparse.parse_qs(parsed.query)
        qs["page"] = [str(page)]
        new_qs = urlparse.urlencode(qs, doseq=True)
        page_url = urlparse.urlunparse(parsed._replace(query=new_qs))
        html = await _fetch_rendered_html(page_url, settle_ms=6000)
        out.extend(parse_search(html))

    return out


def to_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
