"""Realestate.com.au scraper using the official Scrapeless Python SDK + Playwright over CDP.
Targets:
- property pages e.g. https://www.realestate.com.au/property-house-vic-tarneit-143160680
- search pages   e.g. https://www.realestate.com.au/buy/in-melbourne+-+northern+region,+vic/list-1

Both pages embed a hidden JSON cache inside
`<script>window.ArgonautExchange = {...}</script>`, which we decode and
re-shape with jmespath — same approach the upstream reference uses.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
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

# Property pages render the Argonaut cache after a short hydrate; this selector
# is the closest stable hook on both property + search pages.
READY_SELECTOR = "script:contains('ArgonautExchange')"

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
    retries: int = 2,
    warmup: bool = True,
) -> str:
    """Mint a session, goto, wait for the Argonaut cache to appear, return HTML.

    Realestate.com.au is fronted by Akamai Bot Manager; a homepage warm-up
    gets the session cookie before the deep navigation.
    """
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        if attempt > 0:
            await asyncio.sleep(6 * attempt)
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
        )
        ws = session.browser_ws_endpoint
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(ws)
            try:
                page = await browser.new_page()
                if warmup:
                    try:
                        await page.goto("https://www.realestate.com.au/", wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(4)
                    except Exception:
                        pass
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    await page.wait_for_function(
                        "() => !!document.documentElement.outerHTML.match(/ArgonautExchange/)",
                        timeout=15000,
                    )
                except Exception as e:
                    logger.warning("ArgonautExchange wait failed (continuing): {}", e)
                html = await page.content()
                if html and len(html) > 10000:
                    return html
                last_error = RuntimeError("Akamai interstitial / short HTML")
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
    """parse JSON data from script tag"""
    selector = Selector(text=html)
    script = selector.xpath(
        "//script[contains(text(),'window.ArgonautExchange')]/text()"
    ).get()
    if not script:
        raise RuntimeError("ArgonautExchange cache not found")
    # data needs to be parsed multiple times
    data = json.loads(re.findall(r"window.ArgonautExchange=(\{.+\});", script)[0])
    data = json.loads(data["resi-property_listing-experience-web"]["urqlClientCache"])
    data = json.loads(list(data.values())[0]["data"])
    return data

def parse_property_data(data: Dict) -> Dict:
    """refine property data from JSON"""
    if not data:
        return None
    result = jmespath.search(
        """{
        id: id,
        propertyType: propertyType.display,
        description: description,
        propertyLink: _links.canonical.href,
        address: address,
        propertySizes: propertySizes,
        generalFeatures: generalFeatures,
        propertyFeatures: propertyFeatures[].{featureName: displayLabel, value: value},
        images: media.images[].templatedUrl,
        videos: videos,
        floorplans: floorplans,
        listingCompany: listingCompany.{name: name, id: id, companyLink: _links.canonical.href, phoneNumber: businessPhone, address: address.display.fullAddress, ratingsReviews: ratingsReviews, description: description},
        listers: listers,
        auction: auction
        }""",
        data,
    )
    return result

def parse_search_data(data: Dict) -> Dict:
    """refine search data"""
    search_data: List[Dict] = []
    data = list(data.values())[0]
    for listing in data["results"]["exact"]["items"]:
        search_data.append(parse_property_data(listing["listing"]))
    max_search_pages = data["results"]["pagination"]["maxPageNumberAvailable"]
    return {"search_data": search_data, "max_search_pages": max_search_pages}

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_properties(urls: List[str]) -> List[Dict]:
    """scrape listing data from property pages"""
    properties: List[Dict] = []
    for url in urls:
        try:
            html = await _fetch_rendered_html(url)
            data = parse_hidden_data(html)["details"]["listing"]
            data = parse_property_data(data)
            if data is not None:
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
    parsed = parse_search_data(data)
    search_data: List[Dict] = parsed["search_data"]
    max_search_pages = parsed["max_search_pages"]

    if max_scrape_pages and max_scrape_pages < max_search_pages:
        max_scrape_pages = max_scrape_pages
    else:
        max_scrape_pages = max_search_pages
    logger.info(
        f"scraping search pagination, remaining ({max_scrape_pages - 1} more pages)"
    )

    base = url.split("/list")[0]
    for page in range(2, max_scrape_pages + 1):
        page_url = f"{base}/list-{page}"
        try:
            html = await _fetch_rendered_html(page_url)
            data = parse_hidden_data(html)
            search_data.extend(parse_search_data(data)["search_data"])
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
