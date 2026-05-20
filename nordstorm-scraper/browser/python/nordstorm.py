"""Nordstrom scraper using the official Scrapeless Python SDK + Playwright over CDP.
(Folder name keeps the upstream typo "nordstorm" — the site itself is
nordstrom.com.)

Targets:
- product pages e.g. https://www.nordstrom.com/s/nike-air-max-90-sneaker-men/6549520
- search pages  e.g. https://www.nordstrom.com/sr?origin=keywordsearch&keyword=indigo

Both pages embed the React/Apollo cache in
`<script>window.__INITIAL_CONFIG__ = {...};</script>`, which we decode and
walk for `stylesById` / `productResults`.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlencode, urlparse

import jmespath
from loguru import logger
from nested_lookup import nested_lookup
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
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 1,
) -> str:
    """Mint a session, goto, wait for __INITIAL_CONFIG__, return HTML."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
        )
        ws = session.browser_ws_endpoint
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(ws)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                try:
                    await page.wait_for_function(
                        "() => !!document.documentElement.outerHTML.match(/__INITIAL_CONFIG__/)",
                        timeout=15000,
                    )
                except Exception as e:
                    logger.warning("__INITIAL_CONFIG__ wait failed (continuing): {}", e)
                html = await page.content()
                if html:
                    return html
                last_error = RuntimeError("empty HTML")
            except Exception as e:
                last_error = e
                logger.warning("attempt {} failed: {}", attempt + 1, e)
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
    raise RuntimeError(f"giving up after {retries + 1} attempts: {last_error}")

# ---------------------------------------------------------------------------
# Parsers — verbatim from the upstream reference
# ---------------------------------------------------------------------------

def find_hidden_data(html: str) -> dict:
    """extract hidden web cache from page html"""
    selector = Selector(text=html)
    data = selector.xpath(
        "//script[contains(.,'__INITIAL_CONFIG__')]/text()"
    ).get()
    if not data:
        raise RuntimeError("__INITIAL_CONFIG__ script not found")
    data = data.split("=", 1)[-1].strip().strip(";")
    return json.loads(data)

def parse_product(data: dict) -> dict:
    """parse product basic data like id, name, features, variants, media."""
    product = jmespath.search(
        """{
        id: id,
        title: productTitle,
        type: productTypeName,
        typeParent: productTypeParentName,
        ageGroups: ageGroups,
        reviewAverageRating: reviewAverageRating,
        numberOfReviews: numberOfReviews,
        brand: brand,
        description: sellingStatement,
        features: features,
        gender: gender,
        isAvailable: isAvailable
        }""",
        data,
    )
    prices_by_sku = data["price"]["bySkuId"] if data.get("price") else None
    colors_by_id = data["filters"]["color"]["byId"]
    product["media"] = []
    for media_item in data["mediaExperiences"]["carouselsByColor"]:
        item = jmespath.search(
            """{
                colorCode: colorCode,
                colorName: colorName
            }""",
            media_item,
        )
        item["urls"] = [i["url"] for i in media_item["orderedShots"]]
        product["media"].append(item)
    product["variants"] = {}
    for sku, sku_data in data["skus"]["byId"].items():
        parsed = jmespath.search(
            """{
                id: id,
                sizeId: sizeId,
                colorId: colorId,
                totalQuantityAvailable: totalQuantityAvailable
            }""",
            sku_data,
        )
        parsed["price"] = (
            prices_by_sku[sku]["regular"]["price"] if prices_by_sku else None
        )
        parsed["color"] = jmespath.search(
            """{
            id: id,
            value: value,
            sizes: isAvailableWith,
            mediaIds: styleMediaIds,
            swatch: swatchMedia.desktop
            }""",
            colors_by_id[parsed["colorId"]],
        )
        product["variants"][sku] = parsed
    return product

def update_url_parameter(url: str, **params) -> str:
    """update url query parameter of an url with new values"""
    current_params = parse_qs(urlparse(url).query)
    updated_query_params = urlencode({**current_params, **params}, doseq=True)
    base = url[: url.find("?")] if "?" in url else url
    return base + "?" + updated_query_params

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_products(urls: List[str]) -> List[Dict]:
    """scrape nordstorm product pages for product data"""
    products: List[Dict] = []
    for url in urls:
        try:
            html = await _fetch_rendered_html(url)
            data = find_hidden_data(html)
            # find first key "stylesById" and take first value (the current product)
            product = nested_lookup("stylesById", data)
            product = list(product[0].values())[0]
            products.append(parse_product(product))
        except Exception as e:
            logger.error("product {} failed: {}", url, e)
    logger.success(f"scraped {len(products)} product listings from product pages")
    return products

async def scrape_search(url: str, max_pages: int = 10) -> List[Dict]:
    """Scrape nordstom search pages for product listings"""
    logger.info(f"scraping search page {url}")
    first_html = await _fetch_rendered_html(url)
    data = find_hidden_data(first_html)
    _first_page_results = nested_lookup("productResults", data)[0]
    products: List[Dict] = list(_first_page_results["productsById"].values())
    paging_info = _first_page_results["query"]
    total_pages = paging_info["pageCount"]

    if max_pages and max_pages < total_pages:
        total_pages = max_pages

    logger.info(f"scraping search pagination, remaining ({total_pages - 1}) more pages")
    for page in range(2, total_pages + 1):
        page_url = update_url_parameter(url, page=page)
        try:
            html = await _fetch_rendered_html(page_url)
            d = find_hidden_data(html)
            d = nested_lookup("productResults", d)[0]
            products.extend(list(d["productsById"].values()))
        except Exception as e:
            logger.error("search page {} failed: {}", page, e)
    logger.success(f"scraped {len(products)} product listings from search pages")
    return products

def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
