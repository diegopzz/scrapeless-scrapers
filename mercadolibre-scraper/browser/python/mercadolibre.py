"""MercadoLibre scraper using the official Scrapeless Python SDK + Playwright over CDP.

Product pages at articulo.mercadolibre.com.mx/MLM-<id> ship a schema.org Product ld+json
blob plus a BreadcrumbList ld+json. Search/listing pages at listado.mercadolibre.com.mx/<query>
render result cards in li[class*="ui-search-layout__item"]; ld+json carries only FAQPage so
we extract from DOM selectors.
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

DEFAULT_PROXY_COUNTRY = "MX"
DEFAULT_SESSION_TTL = 300
ORIGIN = "https://www.mercadolibre.com.mx"

MLM_ID_RE = re.compile(r"/(MLM[\d]+)", re.IGNORECASE)


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
    settle_ms: int = 6000,
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
                await page.set_extra_http_headers({"accept-language": "es-MX,es;q=0.9"})
                await page.set_viewport_size({"width": 1280, "height": 900})
                # Use load to survive ML's micro-landing redirect
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
            out.append(json.loads(raw))
        except Exception:
            continue
    return out


def _find_type(blocks: List[Dict[str, Any]], type_name: str) -> Optional[Dict[str, Any]]:
    for b in blocks:
        if str(b.get("@type") or "").lower() == type_name.lower():
            return b
    return None


def _extract_mlm_id(url: str) -> str:
    m = MLM_ID_RE.search(url)
    return m.group(1) if m else ""


def _parse_price(text: str) -> Optional[float]:
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

    breadcrumb_ld = _find_type(blocks, "BreadcrumbList")
    def _bc_entry(b: Dict[str, Any]) -> Dict[str, Any]:
        # ML uses item.name + item["@id"] (not top-level name/item)
        item = b.get("item") if isinstance(b.get("item"), dict) else None
        return {
            "name": item.get("name") if item else b.get("name"),
            "url": item.get("@id") if item else (b.get("item") if isinstance(b.get("item"), str) else None),
            "position": b.get("position"),
        }

    breadcrumb = [
        _bc_entry(b)
        for b in (breadcrumb_ld.get("itemListElement") if breadcrumb_ld else []) or []
    ]

    offers = prod.get("offers")
    offer = offers[0] if isinstance(offers, list) else (offers or {})
    rating = prod.get("aggregateRating") or {}

    image = prod.get("image")
    if isinstance(image, list):
        image = image[0] if image else None

    price = offer.get("price")
    price_val = float(price) if price is not None else None

    return {
        "id": str(prod.get("sku") or ""),
        "name": prod.get("name") or "",
        "brand": str(prod["brand"]) if prod.get("brand") else None,
        "description": prod.get("description") or None,
        "image": image,
        "price": price_val,
        "priceCurrency": offer.get("priceCurrency"),
        "availability": offer.get("availability"),
        "ratingValue": float(rating["ratingValue"]) if rating.get("ratingValue") is not None else None,
        "reviewCount": int(rating["reviewCount"]) if rating.get("reviewCount") is not None else None,
        "url": prod.get("url") or url,
        "breadcrumb": breadcrumb,
    }


async def scrape_product(product_url: str) -> Product:
    url = (
        product_url if product_url.startswith("http")
        else f"{ORIGIN}{'/' if not product_url.startswith('/') else ''}{product_url}"
    )
    html = await _fetch_rendered_html(url, settle_ms=6000)
    return parse_product(html, url)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def parse_search(html: str) -> List[SearchResult]:
    sel = Selector(text=html)
    items: List[SearchResult] = []

    for card in sel.css("li[class*='ui-search-layout__item']"):
        name = (
            card.css("[class*='poly-component__title']::text").get() or
            card.css("h2::text").get() or ""
        ).strip()
        raw_link = card.css("a[href*='/MLM-']::attr(href)").get() or ""
        url = raw_link.split("?")[0] if raw_link else None
        item_id = _extract_mlm_id(url) if url else ""
        image = (
            card.css("img::attr(src)").get() or
            card.css("img::attr(data-src)").get()
        )
        price_text = (
            card.css("[class*='price__fraction']::text").get() or
            card.css("[class*='andes-money-amount__fraction']::text").get() or ""
        )
        price = _parse_price(price_text)

        if name or url:
            items.append({
                "id": item_id,
                "name": name,
                "url": url,
                "image": image,
                "price": price,
                "priceCurrency": "MXN",
            })

    return items


async def scrape_search(search_url: str, max_pages: int = 1) -> List[SearchResult]:
    out: List[SearchResult] = []
    html = await _fetch_rendered_html(search_url, settle_ms=5000)
    out.extend(parse_search(html))

    page_size = 48
    for page in range(2, max_pages + 1):
        import urllib.parse as urlparse
        parsed = urlparse.urlparse(search_url)
        qs = urlparse.parse_qs(parsed.query)
        qs["from"] = [str((page - 1) * page_size)]
        new_qs = urlparse.urlencode(qs, doseq=True)
        page_url = urlparse.urlunparse(parsed._replace(query=new_qs))
        html = await _fetch_rendered_html(page_url, settle_ms=5000)
        out.extend(parse_search(html))

    return out


def to_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
