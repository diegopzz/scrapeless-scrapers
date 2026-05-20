"""Realtor.com scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names + emitted field names match verbatim.

Three surfaces:
- `scrape_property(url)`       — extracts `__NEXT_DATA__` JSON, reduces via JMESPath.
- `scrape_search(state, city, max_pages)` — `__NEXT_DATA__` array of property cards.
- `scrape_feed(url)`           — XML sitemap with `<loc>` + `<lastmod>` pairs.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
from datetime import datetime
from typing import Any

import jmespath
from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 180

def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError(
            "SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com"
        )
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()

async def _new_browser(proxy_country: str = DEFAULT_PROXY_COUNTRY) -> str:
    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
    )
    return session.browser_ws_endpoint

async def _fetch_html(
    url: str,
    ready_selector: str | None = None,
    *,
    retries: int = 2,
    warmup: bool = True,
) -> str:
    """Realtor.com is fronted by PerimeterX; a homepage warm-up gets the
    `_px*` cookies before navigating to the search / property page.
    """
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        if attempt > 0:
            await asyncio.sleep(6 * attempt)
        ws = await _new_browser()
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(ws)
            try:
                page = await browser.new_page()
                if warmup and not url.endswith(".xml"):
                    try:
                        await page.goto("https://www.realtor.com/", wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(3)
                    except Exception:
                        pass
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=15000)
                    except Exception as e:
                        logger.warning("wait_for_selector failed: {}", e)
                html = await page.content()
                if html and (url.endswith(".xml") or len(html) > 10000):
                    return html
                last_error = RuntimeError("PerimeterX interstitial / short HTML")
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
# Parsers — mirror the upstream reference verbatim
# ---------------------------------------------------------------------------

PROPERTY_JMESPATH = """{
    id: propertyDetails.listing_id,
    slug: slug,
    url: propertyDetails.href,
    status: propertyDetails.status,
    tags: propertyDetails.tags,
    sold_date: propertyDetails.last_sold_date,
    sold_price: propertyDetails.last_sold_price,
    list_date: propertyDetails.list_date,
    list_price: propertyDetails.list_price,
    list_price_last_change: propertyDetails.last_price_change_amount,
    details: propertyDetails.description,
    flags: propertyDetails.flags,
    local: propertyDetails.local,
    location: propertyDetails.location,
    agent: propertyDetails.source.agents,
    advertisers: propertyDetails.advertisers,
    tax_history: propertyDetails.tax_history,
    history: propertyDetails.property_history[].{
        date: date,
        event: event_name,
        price: price,
        price_sqft: price_sqft
    },
    photos: propertyDetails.photos[].{
        url: href,
        tags: tags[].label
    },
    phones: propertyDetails.lead_attributes.opcity_lead_attributes.phones[].{
        type: category,
        number: number
    },
    features: propertyDetails.details[].{
        name: category,
        values: text
    }
}"""

def parse_property(html: str, url: str) -> dict | None:
    """Returns the JMESPath-reduced property dict."""
    sel = Selector(text=html)
    data = sel.css("script#__NEXT_DATA__::text").get()
    if not data:
        logger.warning("page {} is not a property listing page", url)
        return None
    parsed = json.loads(data)
    raw_data = parsed["props"]["pageProps"]["initialReduxState"]
    reduced = jmespath.search(PROPERTY_JMESPATH, raw_data)
    if reduced and reduced.get("features"):
        reduced["features"] = {f["name"]: f["values"] for f in reduced["features"] if f.get("name")}
    return reduced

def parse_search(html: str, url: str) -> dict | None:
    """"""
    sel = Selector(text=html)
    data = sel.css("script#__NEXT_DATA__::text").get()
    if not data:
        logger.warning("page {} is not a property listing page", url)
        return None
    parsed = json.loads(data)["props"]["pageProps"]
    if not parsed.get("properties"):
        parsed["properties"] = parsed["searchResults"]["home_search"]["results"]
    if not parsed.get("totalProperties"):
        parsed["totalProperties"] = parsed["searchResults"]["home_search"]["total"]
    return parsed

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference verbatim
# ---------------------------------------------------------------------------

async def scrape_property(url: str) -> dict | None:
    """Scrape realtor.com's property page for property data."""
    logger.info("scraping {} property page", url)
    html = await _fetch_html(url, ready_selector="script#__NEXT_DATA__")
    return parse_property(html, url)

async def scrape_search(state: str, city: str, max_pages: int | None = None) -> list[dict]:
    """Scrape realtor.com's search and find properties for given query."""
    logger.info("scraping first property search page for {}, {}", city, state)
    first_url = f"https://www.realtor.com/realestateandhomes-search/{city}_{state}/pg-1"
    first_html = await _fetch_html(first_url, ready_selector="script#__NEXT_DATA__")
    first_data = parse_search(first_html, first_url)
    if not first_data:
        return []
    results: list[dict] = list(first_data["properties"])
    total_pages = math.ceil(first_data["totalProperties"] / len(results)) if results else 1
    if max_pages and total_pages > max_pages:
        total_pages = max_pages
    logger.info("found {} total pages", total_pages)
    for page in range(2, total_pages + 1):
        page_url = first_url.replace("pg-1", f"pg-{page}")
        try:
            html = await _fetch_html(page_url, ready_selector="script#__NEXT_DATA__")
            parsed = parse_search(html, page_url)
            if parsed:
                results.extend(parsed["properties"])
        except Exception as e:
            logger.warning("failed page {}: {}", page, e)
    logger.info("scraped search of {} results for {}, {}", len(results), city, state)
    return results

async def scrape_feed(url: str) -> dict[str, datetime]:
    """Scrape Realtor.com's sitemap-style atom feed -> { url: datetime }."""
    body = await _fetch_html(url)
    sel = Selector(text=body)
    out: dict[str, datetime] = {}
    for item in sel.xpath("//sitemap"):
        loc = item.xpath("loc/text()").get()
        pub = item.xpath("lastmod/text()").get()
        if loc and pub:
            try:
                out[loc] = datetime.fromisoformat(pub)
            except ValueError:
                pass
    return out

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj
