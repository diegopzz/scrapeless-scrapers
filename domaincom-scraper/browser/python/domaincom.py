"""Domain.com.au scraper using the official Scrapeless Python SDK + Playwright over CDP.
Targets:
- listed property pages e.g. https://www.domain.com.au/610-399-bourke-street-melbourne-vic-3000-2018835548
- sold property profiles e.g. https://www.domain.com.au/property-profile/308-9-degraves-street-melbourne-vic-3000
- search pages           e.g. https://www.domain.com.au/sale/melbourne-vic-3000/

All pages embed JSON in `<script id="__NEXT_DATA__">`; the per-page-type
structure (componentProps vs __APOLLO_STATE__) is handled in `parse_property_data`.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any, Dict, List

import jmespath
from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "AU"
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
    """Mint a session, goto, wait for __NEXT_DATA__, return HTML."""
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
                    await page.wait_for_selector("script#__NEXT_DATA__", timeout=15000)
                except Exception as e:
                    logger.warning("__NEXT_DATA__ wait failed (continuing): {}", e)
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

def parse_hidden_data(html: str) -> Dict:
    """parse json data from script tags"""
    selector = Selector(text=html)
    script = selector.xpath("//script[@id='__NEXT_DATA__']/text()").get()
    if not script:
        raise RuntimeError("__NEXT_DATA__ script tag not found")
    data = json.loads(script)
    return data["props"]["pageProps"]["componentProps"]

def parse_repoerty_data(html: str) -> Dict:
    """parse json data from script tags (typo preserved from the upstream reference upstream)"""
    selector = Selector(text=html)
    script = selector.xpath("//script[@id='__NEXT_DATA__']/text()").get()
    if not script:
        raise RuntimeError("__NEXT_DATA__ script tag not found")
    json_data = json.loads(script)
    # property pages data are found in different structures
    try:  # listed property
        data = json_data["props"]["pageProps"]["componentProps"]
        return parse_component_props(data)
    except Exception:  # usually sold property has different data structure
        data = json_data["props"]["pageProps"]
        return parse_page_props(data)

def parse_page_props(data: Dict) -> Dict | None:
    """refine property pages data (sold / property-profile pages)"""
    if not data:
        return None
    data = data["__APOLLO_STATE__"]
    key = next(k for k in data if k.startswith("Property:"))
    data = data[key]
    result = jmespath.search(
        """{
        propertyId: propertyId,
        unitNumber: address.unitNumber,
        streetNumber: address.streetNumber,
        suburb: address.suburb,
        postcode: address.postcode
        }""",
        data,
    )
    # parse the photo data
    image_key = next(k for k in data if k.startswith("media("))
    result["gallery"] = []
    for image in data[image_key]:
        result["gallery"].append(image["url"])
    return result

def parse_component_props(data: Dict) -> Dict | None:
    """refine property pages data (listed property pages)"""
    if not data:
        return None
    result = jmespath.search(
        """{
    listingId: listingId,
    listingUrl: listingUrl,
    unitNumber: unitNumber,
    streetNumber: streetNumber,
    street: street,
    suburb: suburb,
    postcode: postcode,
    createdOn: createdOn,
    propertyType: propertyType,
    beds: beds,
    phone: phone,
    agencyName: agencyName,
    propertyDeveloperName: propertyDeveloperName,
    agencyProfileUrl: agencyProfileUrl,
    propertyDeveloperUrl: propertyDeveloperUrl,
    description: description,
    loanfinder: loanfinder,
    schools: schoolCatchment.schools,
    suburbInsights: suburbInsights,
    gallery: gallery,
    listingSummary: listingSummary,
    agents: agents,
    features: features,
    structuredFeatures: structuredFeatures,
    faqs: faqs
    }""",
        data,
    )
    return result

def parse_search_page(data: Dict) -> List[Dict] | None:
    """refine search pages data"""
    if not data:
        return None
    data = data["listingsMap"]
    result: List[Dict] = []
    # iterate over card items in the search data
    for key in data.keys():
        item = data[key]
        parsed_data = jmespath.search(
            """{
        id: id,
        listingType: listingType,
        listingModel: listingModel
      }""",
            item,
        )
        # exclude the skeletonImages key from the data
        if parsed_data and parsed_data.get("listingModel"):
            parsed_data["listingModel"].pop("skeletonImages", None)
        result.append(parsed_data)
    return result

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_properties(urls: List[str]) -> List[Dict]:
    """scrape listing data from property pages"""
    properties: List[Dict] = []
    for url in urls:
        try:
            html = await _fetch_rendered_html(url)
            data = parse_repoerty_data(html)
            if data is not None:
                data["url"] = url
                properties.append(data)
        except Exception as e:
            logger.error("An error occurred while scraping property pages: {}", e)
    logger.success(f"scraped {len(properties)} property listings")
    return properties

async def scrape_search(url: str, max_scrape_pages: int | None = None) -> List[Dict]:
    """scrape property listings from search pages"""
    logger.info("scraping search page {}", url)
    first_html = await _fetch_rendered_html(url)
    data = parse_hidden_data(first_html)
    search_data = parse_search_page(data) or []
    max_search_pages = data["totalPages"]

    if max_scrape_pages and max_scrape_pages < max_search_pages:
        max_scrape_pages = max_scrape_pages
    else:
        max_scrape_pages = max_search_pages
    logger.info(
        f"scraping search pagination, remaining ({max_scrape_pages - 1} more pages)"
    )

    for page in range(2, max_scrape_pages + 1):
        page_url = f"{url}?page={page}"
        try:
            html = await _fetch_rendered_html(page_url)
            data = parse_hidden_data(html)
            search_data.extend(parse_search_page(data) or [])
        except Exception as e:
            logger.error("An error occurred while scraping search pages: {}", e)
    logger.success(f"scraped ({len(search_data)}) from {url}")
    return search_data

def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
