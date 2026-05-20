"""Big Lots scraper using the official Scrapeless Python SDK + Playwright over CDP.

Surfaces:
- scrape_product(urls)                  -> list of Product dicts (PDP fields lifted from JSON-LD)
- scrape_search(category_url, max_pages) -> list of SearchResult dicts (WooCommerce cards)

biglots.com runs WordPress + WooCommerce; JSON-LD Product blocks are emitted on every PDP,
and the category templates render `<li class="wp-block-post post-<id> product ...">` cards.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

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
    retries: int = 1,
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
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=15000)
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
# Helpers
# ---------------------------------------------------------------------------

def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = re.sub(r"\s+", " ", str(value)).strip()
    return s or None

def _to_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = re.sub(r"[^\d.\-]", "", str(value))
    try:
        return float(s)
    except (TypeError, ValueError):
        return None

def _iter_jsonld_nodes(sel: Selector):
    for raw in sel.css('script[type="application/ld+json"]::text').getall():
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        stack: List[Any] = list(data) if isinstance(data, list) else [data]
        while stack:
            node = stack.pop(0)
            if not isinstance(node, dict):
                continue
            graph = node.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)
            else:
                yield node

def _type_matches(node: Dict[str, Any], wanted: str) -> bool:
    t = node.get("@type")
    if isinstance(t, str):
        return t == wanted
    if isinstance(t, list):
        return wanted in t
    return False

def _pick_offer_price(offer: Dict[str, Any]) -> Optional[float]:
    if not isinstance(offer, dict):
        return None
    if offer.get("price") is not None:
        return _to_number(offer["price"])
    spec = offer.get("priceSpecification")
    if isinstance(spec, list) and spec and isinstance(spec[0], dict):
        return _to_number(spec[0].get("price"))
    if isinstance(spec, dict):
        return _to_number(spec.get("price"))
    return None

def _pick_offer_currency(offer: Dict[str, Any]) -> Optional[str]:
    if not isinstance(offer, dict):
        return None
    if offer.get("priceCurrency"):
        return str(offer["priceCurrency"])
    spec = offer.get("priceSpecification")
    if isinstance(spec, list) and spec and isinstance(spec[0], dict):
        return spec[0].get("priceCurrency")
    if isinstance(spec, dict):
        return spec.get("priceCurrency")
    return None

def _short_availability(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    return value.rsplit("/", 1)[-1] if "/" in value else value

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_product(html: str, url: str) -> Dict[str, Any]:
    sel = Selector(text=html)

    ld: Dict[str, Any] = {}
    for node in _iter_jsonld_nodes(sel):
        if _type_matches(node, "Product"):
            ld = node
            break

    offers = ld.get("offers")
    if isinstance(offers, list) and offers:
        offer = offers[0] if isinstance(offers[0], dict) else {}
    elif isinstance(offers, dict):
        offer = offers
    else:
        offer = {}

    images_raw = ld.get("image")
    if isinstance(images_raw, str):
        images = [images_raw]
    elif isinstance(images_raw, list):
        images = [str(x) for x in images_raw if x]
    else:
        images = sel.css('meta[property="og:image"]::attr(content)').getall()

    categories: List[str] = []
    for t in sel.css('.woocommerce-breadcrumb a::text, .wp-block-woocommerce-breadcrumbs a::text').getall():
        c = _clean(t)
        if c and c not in categories:
            categories.append(c)

    seller_node = offer.get("seller")
    seller_name: Optional[str] = None
    if isinstance(seller_node, dict):
        seller_name = seller_node.get("name")
    elif isinstance(seller_node, str):
        seller_name = seller_node

    sku = ld.get("sku")
    sku_str = str(sku) if sku is not None else (ld.get("@id") or url)

    return {
        "id": str(sku_str),
        "url": url,
        "name": _clean(ld.get("name")) or _clean(sel.css("h1::text").get()) or "",
        "description": _clean(ld.get("description")) or _clean(sel.css('meta[name="description"]::attr(content)').get()),
        "price": _pick_offer_price(offer),
        "priceCurrency": _pick_offer_currency(offer),
        "availability": _short_availability(offer.get("availability")),
        "images": images,
        "categories": categories,
        "sellerName": _clean(seller_name),
    }

_POST_CLASS_RE = re.compile(r"^post-(\d+)$")

def parse_search(html: str) -> List[Dict[str, Any]]:
    sel = Selector(text=html)
    items: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for card in sel.css('li.product, li.wp-block-post.product'):
        classes = (card.attrib.get("class") or "").split()
        post_id = ""
        for c in classes:
            m = _POST_CLASS_RE.match(c)
            if m:
                post_id = m.group(1)
                break
        card_id = post_id or card.attrib.get("data-id", "")

        href = card.css('a[href*="/product/"]::attr(href)').get() or ""
        if not href:
            continue
        abs_url = href if href.startswith("http") else f"https://biglots.com{href}"
        if abs_url in seen:
            continue
        seen.add(abs_url)

        name = _clean(
            card.css('h3 a::text, h2 a::text, h3::text, h2::text').get()
            or card.css('a[href*="/product/"]::attr(aria-label)').get()
            or card.css('img::attr(alt)').get()
        ) or ""

        price_text = _clean(
            " ".join(card.css(
                '.wp-block-woocommerce-product-price *::text, '
                '.wc-block-components-product-price *::text, '
                '.price *::text'
            ).getall())
        )
        price = _to_number(price_text)

        image = card.css('img::attr(src)').get() or card.css('img::attr(data-src)').get()

        category = _clean(card.css('.wp-block-post-terms a::text, .wc-block-grid__product-category::text').get())

        items.append({
            "id": str(card_id or ""),
            "url": abs_url,
            "name": name,
            "image": image,
            "price": price,
            "priceCurrency": "USD" if price_text and "$" in price_text else None,
            "category": category,
        })

    return items

# ---------------------------------------------------------------------------
# Scrape functions
# ---------------------------------------------------------------------------

async def scrape_product(urls: List[str]) -> List[Dict[str, Any]]:
    if isinstance(urls, str):
        urls = [urls]
    out: List[Dict[str, Any]] = []
    for url in urls:
        logger.info("scraping product {}", url)
        html = await _fetch_rendered_html(url, ready_selector='script[type="application/ld+json"]')
        out.append(parse_product(html, url))
    return out

async def scrape_search(category_url: str, max_pages: int = 1) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    base = category_url.rstrip("/")
    for page in range(1, max_pages + 1):
        url = category_url if page == 1 else f"{base}/page/{page}/"
        logger.info("scraping search {} (page {})", url, page)
        html = await _fetch_rendered_html(url, ready_selector='li.product, li.wp-block-post.product')
        out.extend(parse_search(html))
    logger.success("search returned {} items", len(out))
    return out

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
