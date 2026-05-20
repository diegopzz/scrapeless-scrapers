"""Zara scraper using the official Scrapeless Python SDK + Playwright over CDP.

Surfaces:
- scrape_product(urls)          -> list of Product dicts (PDP fields from JSON-LD + DOM)
- scrape_search(url, max_pages) -> list of SearchResult dicts (PLP / category cards)

Zara.com is Cloudflare-fronted; Scrapeless's residential fingerprinting handles the JS
challenge transparently. We wait on `script[type="application/ld+json"]` for both surfaces.
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


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = re.sub(r"\s+", " ", str(value)).strip()
    return v or None

# Zara product URLs end with `-p<digits>.html`; the trailing digits are the productId.
_PRODUCT_ID_RE = re.compile(r"-p(\d+)\.html", re.I)


def _extract_product_id(url: str) -> str:
    m = _PRODUCT_ID_RE.search(url or "")
    if m:
        return m.group(1)
    return urlparse(url or "").path.rstrip("/").split("/")[-1].replace(".html", "")

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_product(html: str, url: str) -> Dict[str, Any]:
    sel = Selector(text=html)
    raw_blocks = sel.css('script[type="application/ld+json"]::text').getall()

    ld: Dict[str, Any] = {}
    for node in _iter_jsonld_nodes(raw_blocks):
        if _type_matches(node, "Product"):
            ld = node
            break

    offer = _first_offer(ld)

    images_raw = ld.get("image")
    if isinstance(images_raw, str):
        images = [images_raw]
    elif isinstance(images_raw, list):
        images = [str(x) for x in images_raw if x]
    else:
        images = sel.css('meta[property="og:image"]::attr(content)').getall()

    name = ld.get("name") or _clean(sel.css('meta[property="og:title"]::attr(content)').get()) \
        or _clean(sel.css("h1::text").get())

    description = ld.get("description") or _clean(
        sel.css('meta[name="description"]::attr(content)').get()
    )

    sku = ld.get("sku") or ld.get("productID") or _extract_product_id(url)

    brand_node = ld.get("brand")
    if isinstance(brand_node, dict):
        brand = brand_node.get("name") or "ZARA"
    elif isinstance(brand_node, str):
        brand = brand_node
    else:
        brand = "ZARA"

    price_value: Optional[float] = None
    raw_price = offer.get("price") if offer else None
    if raw_price is None:
        raw_price = _clean(sel.css('meta[property="product:price:amount"]::attr(content)').get())
    if raw_price is not None:
        try:
            price_value = float(str(raw_price).replace(",", ""))
        except (TypeError, ValueError):
            price_value = None

    currency = offer.get("priceCurrency") if offer else None
    if not currency:
        currency = _clean(sel.css('meta[property="product:price:currency"]::attr(content)').get())

    availability = offer.get("availability") if offer else None
    if isinstance(availability, str) and "/" in availability:
        availability = availability.rsplit("/", 1)[-1]

    color = ld.get("color")
    if not color:
        color = _clean(sel.css('[data-qa-qualifier="product-detail-color"] *::text').get()
                       or sel.css('p.product-detail-info__color::text').get())

    return {
        "id": str(sku) if sku else "",
        "url": url,
        "name": _clean(name) or "",
        "brand": _clean(brand) or "ZARA",
        "description": _clean(description),
        "price": price_value,
        "priceCurrency": currency,
        "availability": availability,
        "images": images,
        "color": _clean(color) if isinstance(color, str) else None,
        "category": _clean(ld.get("category")) if ld.get("category") else None,
    }


def parse_search(html: str) -> Dict[str, Any]:
    sel = Selector(text=html)
    raw_blocks = sel.css('script[type="application/ld+json"]::text').getall()

    # Build a name/pid -> product URL map from DOM anchors, since Zara's ItemList
    # JSON-LD omits per-item URLs.
    url_by_key: Dict[str, str] = {}
    for a in sel.css('a[href*="-p0"][href$=".html"], a[href*="-p1"][href$=".html"]'):
        href = a.attrib.get("href", "")
        if not href:
            continue
        absolute = urljoin("https://www.zara.com", href)
        label_raw = a.attrib.get("aria-label") or " ".join(a.css("*::text").getall())
        label = _clean(label_raw)
        if label and label.upper() not in url_by_key:
            url_by_key[label.upper()] = absolute
        img = a.css("img::attr(src)").get() or a.css("img::attr(data-src)").get()
        if img:
            m = re.search(r"/(\d{8,11})", img)
            if m:
                pid8 = m.group(1)[:8]
                key = f"PID:{pid8}"
                if key not in url_by_key:
                    url_by_key[key] = absolute

    items: List[Dict[str, Any]] = []

    for node in _iter_jsonld_nodes(raw_blocks):
        if not _type_matches(node, "ItemList"):
            continue
        for el in node.get("itemListElement") or []:
            if not isinstance(el, dict):
                continue
            item = el.get("item") if isinstance(el.get("item"), dict) else el
            offer = _first_offer(item)
            name = _clean(item.get("name")) or ""
            # Zara now ships per-item URL inside the offer; fall back to legacy slots.
            url = (offer.get("url") if isinstance(offer, dict) else None) or item.get("url") or el.get("url") or ""
            image = item.get("image")
            if isinstance(image, list) and image:
                image = str(image[0])
            elif not isinstance(image, str):
                image = None
            if not url and name:
                url = url_by_key.get(name.upper(), "")
            if not url and image:
                m = re.search(r"/(\d{8,11})", image)
                if m:
                    url = url_by_key.get(f"PID:{m.group(1)[:8]}", "")
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
                "name": name,
                "image": image,
                "price": price_value,
                "priceCurrency": offer.get("priceCurrency") if offer else None,
            })
        if items:
            break

    if not items:
        seen = set()
        for a in sel.css('a[href*="-p"][href$=".html"]'):
            href = a.attrib.get("href", "")
            absolute = urljoin("https://www.zara.com", href)
            sku = _extract_product_id(absolute)
            if not sku or sku in seen:
                continue
            seen.add(sku)
            name = _clean(a.css("::attr(aria-label)").get()
                          or a.css("h2::text, h3::text, span::text").get())
            img = a.css("img::attr(src)").get() or a.css("img::attr(data-src)").get()
            items.append({
                "id": sku,
                "url": absolute,
                "name": name or "",
                "image": img,
                "price": None,
                "priceCurrency": None,
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
    out: List[Dict[str, Any]] = []
    for url in urls:
        logger.info("scraping product {}", url)
        html = await _fetch_rendered_html(url, ready_selector='script[type="application/ld+json"]')
        out.append(parse_product(html, url))
    return out


async def scrape_search(url: str, max_pages: int = 1) -> List[Dict[str, Any]]:
    """Scrape a Zara PLP. Zara is mostly infinite-scroll; one fetch returns the first batch.
    Pass `?page=N` for sections that accept pagination."""
    logger.info("scraping search {}", url)
    first_html = await _fetch_rendered_html(url, ready_selector='script[type="application/ld+json"]')
    out: List[Dict[str, Any]] = list(parse_search(first_html)["results"])
    for page in range(2, max_pages + 1):
        page_url = _add_query(url, page=page)
        page_html = await _fetch_rendered_html(page_url, ready_selector='script[type="application/ld+json"]')
        out.extend(parse_search(page_html)["results"])
    return out


def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
