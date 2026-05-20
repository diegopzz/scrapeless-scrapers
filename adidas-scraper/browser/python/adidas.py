"""Adidas scraper using the official Scrapeless Python SDK + Playwright over CDP.

Surfaces:
- scrape_product(urls)         -> list of Product dicts (PDP fields lifted from JSON-LD + DOM)
- scrape_search(url, max_pages) -> list of SearchResult dicts (PLP product cards)

Under the hood:
- `client.browser.create()` mints a cloud session on Scrapeless's Scraping Browser,
  returning a CDP WebSocket endpoint (`browser_ws_endpoint`).
- Playwright connects over CDP, drives the page, returns rendered HTML.
- Parsel parses the HTML; we prefer JSON-LD blobs over CSS classes when possible.

Adidas.com is protected by Akamai Bot Manager so retries + Scrapeless's residential
fingerprinting matter; we ship `retries=2` by default and wait on a stable marker.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 180

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
    retries: int = 2,
) -> str:
    """Discover -> extract: mint a session, goto, wait for stable marker, return HTML."""
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
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=20000)
                    except Exception as e:
                        logger.warning("wait_for_selector {!r} failed (continuing): {}", ready_selector, e)
                html = await page.content()
                if html and "<html" in html.lower():
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

# ---------------------------------------------------------------------------
# JSON-LD helpers
# ---------------------------------------------------------------------------

def _iter_jsonld_nodes(raw_blocks: List[str]):
    for raw in raw_blocks:
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            graph = node.get("@graph")
            if isinstance(graph, list):
                for sub in graph:
                    if isinstance(sub, dict):
                        yield sub
            else:
                yield node

def _type_matches(node: Dict[str, Any], wanted: str) -> bool:
    t = node.get("@type")
    if isinstance(t, str):
        return t == wanted
    if isinstance(t, list):
        return wanted in t
    return False

def _first_offer(node: Dict[str, Any]) -> Dict[str, Any]:
    offers = node.get("offers")
    if isinstance(offers, list) and offers:
        return offers[0] if isinstance(offers[0], dict) else {}
    if isinstance(offers, dict):
        nested = offers.get("offers")
        if isinstance(nested, list) and nested:
            return nested[0] if isinstance(nested[0], dict) else {}
        return offers
    return {}

def _aggregate_rating(node: Dict[str, Any]) -> Dict[str, Any]:
    ar = node.get("aggregateRating")
    return ar if isinstance(ar, dict) else {}

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

_PRODUCT_ID_RE = re.compile(r"/([A-Z]{2}\d{4}|[A-Z]{3}\d{2}|[A-Z]{2}\d{3}[A-Z]?|[A-Z]{1,3}\d{3,4})\.html", re.I)

def _extract_product_id(url: str) -> str:
    m = _PRODUCT_ID_RE.search(url)
    if m:
        return m.group(1).upper()
    # fallback: last path segment minus .html
    path = urlparse(url).path.rstrip("/")
    last = path.split("/")[-1]
    return last.replace(".html", "")

def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = re.sub(r"\s+", " ", value).strip()
    return v or None

def parse_product(html: str, url: str) -> Dict[str, Any]:
    """Parse an Adidas PDP. Prefers JSON-LD Product; falls back to DOM."""
    sel = Selector(text=html)
    raw_blocks = sel.css('script[type="application/ld+json"]::text').getall()

    ld: Dict[str, Any] = {}
    for node in _iter_jsonld_nodes(raw_blocks):
        if _type_matches(node, "Product"):
            ld = node
            break

    offer = _first_offer(ld)
    rating = _aggregate_rating(ld)

    images_raw = ld.get("image") if ld else None
    if isinstance(images_raw, str):
        images = [images_raw]
    elif isinstance(images_raw, list):
        images = [str(x) for x in images_raw if x]
    else:
        images = sel.css('meta[property="og:image"]::attr(content)').getall()

    name = ld.get("name") if ld else None
    if not name:
        name = _clean(sel.css("h1::text").get())

    description = ld.get("description") if ld else None
    if not description:
        description = _clean(sel.css('meta[name="description"]::attr(content)').get())

    sku = ld.get("sku") or ld.get("productID") or _extract_product_id(url)

    brand_node = ld.get("brand") if ld else None
    if isinstance(brand_node, dict):
        brand = brand_node.get("name")
    elif isinstance(brand_node, str):
        brand = brand_node
    else:
        brand = "adidas"

    price_value: Optional[float] = None
    raw_price = offer.get("price") if offer else None
    if raw_price is not None:
        try:
            price_value = float(str(raw_price).replace(",", ""))
        except (TypeError, ValueError):
            price_value = None

    currency = offer.get("priceCurrency") if offer else None

    availability = offer.get("availability") if offer else None
    if isinstance(availability, str) and "/" in availability:
        availability = availability.rsplit("/", 1)[-1]

    return {
        "id": str(sku),
        "url": url,
        "name": _clean(name) or "",
        "brand": _clean(brand) or "adidas",
        "description": _clean(description),
        "price": price_value,
        "priceCurrency": currency,
        "availability": availability,
        "images": images,
        "rating": float(rating["ratingValue"]) if rating.get("ratingValue") else None,
        "reviewCount": int(rating["reviewCount"]) if rating.get("reviewCount") else None,
        "category": _clean(ld.get("category")) if ld else None,
        "color": _clean(ld.get("color")) if ld else None,
    }

def parse_search(html: str) -> Dict[str, Any]:
    """Parse an Adidas PLP / search page.

    Adidas's PLP injects card data into ItemList JSON-LD AND into the rendered DOM
    via `[data-testid="plp-product-card"]`. We prefer JSON-LD ItemList; fall back to DOM cards.
    """
    sel = Selector(text=html)
    raw_blocks = sel.css('script[type="application/ld+json"]::text').getall()

    items: List[Dict[str, Any]] = []
    for node in _iter_jsonld_nodes(raw_blocks):
        if not _type_matches(node, "ItemList"):
            continue
        for el in node.get("itemListElement") or []:
            if not isinstance(el, dict):
                continue
            item = el.get("item") if isinstance(el.get("item"), dict) else el
            offer = _first_offer(item)
            url = item.get("url") or el.get("url") or ""
            sku = item.get("sku") or item.get("productID") or _extract_product_id(url)
            price_value = None
            raw_price = offer.get("price") if offer else None
            if raw_price is not None:
                try:
                    price_value = float(str(raw_price).replace(",", ""))
                except (TypeError, ValueError):
                    price_value = None
            items.append({
                "id": str(sku) if sku else "",
                "url": url,
                "name": item.get("name") or "",
                "image": (item.get("image") if isinstance(item.get("image"), str)
                          else (item.get("image") or [None])[0] if isinstance(item.get("image"), list) else None),
                "price": price_value,
                "priceCurrency": offer.get("priceCurrency") if offer else None,
            })
        if items:
            break

    if not items:
        # DOM fallback - works for adidas.com PLPs rendered by glass UI
        for card in sel.css('[data-testid="plp-product-card"], article[data-testid="product-card"]'):
            link = card.css('a::attr(href)').get("") or ""
            absolute = urljoin("https://www.adidas.com", link) if link else ""
            sku = _extract_product_id(absolute) if absolute else (card.attrib.get("data-grid-id") or "")
            name = _clean(card.css('[data-testid="product-card-title"]::text').get()
                          or card.css('p::text').get())
            price_text = _clean(
                card.css('[data-testid="primary-price"]::text').get()
                or card.css('div[class*="price"] *::text').get()
            )
            price_value = None
            if price_text:
                m = re.search(r"[\d,.]+", price_text)
                if m:
                    try:
                        price_value = float(m.group(0).replace(",", ""))
                    except ValueError:
                        price_value = None
            img = (card.css('img::attr(src)').get()
                   or card.css('img::attr(data-src)').get())
            items.append({
                "id": sku or "",
                "url": absolute,
                "name": name or "",
                "image": img,
                "price": price_value,
                "priceCurrency": "USD" if price_text and "$" in price_text else None,
            })

    return {"results": items}

# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def _add_query(url: str, **params: Any) -> str:
    parsed = urlparse(url)
    q = dict(parse_qsl(parsed.query))
    q.update({k: str(v) for k, v in params.items()})
    return urlunparse(parsed._replace(query=urlencode(q)))

# ---------------------------------------------------------------------------
# Scrape functions
# ---------------------------------------------------------------------------

async def scrape_product(urls: List[str]) -> List[Dict[str, Any]]:
    """Scrape one or more Adidas PDP URLs."""
    results: List[Dict[str, Any]] = []
    for url in urls:
        logger.info("scraping product {}", url)
        html = await _fetch_rendered_html(url, ready_selector='script[type="application/ld+json"]')
        results.append(parse_product(html, url))
    return results

async def scrape_search(url: str, max_pages: int = 1) -> List[Dict[str, Any]]:
    """Scrape an Adidas PLP / search URL and follow pagination (`?start=` offsets of 48)."""
    logger.info("scraping search {}", url)
    first_html = await _fetch_rendered_html(url, ready_selector='script[type="application/ld+json"]')
    parsed = parse_search(first_html)
    out: List[Dict[str, Any]] = list(parsed["results"])

    # Adidas uses ?start=48,96,... (page size 48) on most US PLPs
    page_size = 48
    for page in range(2, max_pages + 1):
        offset = (page - 1) * page_size
        page_url = _add_query(url, start=offset)
        page_html = await _fetch_rendered_html(page_url, ready_selector='script[type="application/ld+json"]')
        out.extend(parse_search(page_html)["results"])
    logger.success("search {} returned {} items", url, len(out))
    return out

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
