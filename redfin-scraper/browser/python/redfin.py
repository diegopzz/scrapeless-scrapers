"""Redfin scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names + emitted field names match verbatim.

Three surfaces:
- `scrape_search(url)`             — JSONP from the stingray `gis` endpoint.
- `scrape_property_for_sale(urls)` — DOM-parse the listing page.
- `scrape_property_for_rent(urls)` — extract rental UUID from `og:image`,
  then call `/stingray/api/v1/rentals/{id}/floorPlans` and return its JSON.

All requests run through a Scrapeless Scraping Browser session with a US
residential proxy.
"""

from __future__ import annotations

import json
import os
from typing import Any

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

async def _fetch(url: str, *, as_text: bool = True, ready_selector: str | None = None) -> str:
    """Render a URL and return either the body innerText (for JSON endpoints) or full HTML."""
    ws = await _new_browser()
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(ws)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            if ready_selector:
                try:
                    await page.wait_for_selector(ready_selector, timeout=15000)
                except Exception as e:
                    logger.warning("wait_for_selector failed (continuing): {}", e)
            if as_text:
                body = await page.evaluate("() => document.body && document.body.innerText")
                if body and body.strip():
                    return body
            return await page.content()
        finally:
            try:
                await browser.close()
            except Exception:
                pass

# ---------------------------------------------------------------------------
# Parsers — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

def parse_search_api(body: str) -> list[dict]:
    """Strip JSONP prefix `{}&&` and return `payload.homes`."""
    return json.loads(body.replace("{}&&", ""))["payload"]["homes"]

def parse_property_for_sale(html: str, url: str) -> dict:
    """"""
    sel = Selector(text=html)
    price = sel.xpath("//div[@data-rf-test-id='abp-price']/div/text()").get()
    estimated_monthly_price = "".join(
        sel.xpath("//span[@class='est-monthly-payment']/text()").getall()
    )
    address = (
        "".join(sel.xpath("//div[contains(@class, 'street-address')]/text()").getall())
        + " "
        + "".join(sel.xpath("//div[contains(@class, 'cityStateZip')]/text()").getall())
    )
    description = sel.xpath("//div[@id='marketing-remarks-scroll']/p/span/text()").get()
    images = [
        image.attrib.get("src", "")
        for image in sel.xpath("//img[contains(@class, 'widenPhoto')]")
    ]
    details = [
        "".join(t.getall())
        for t in sel.css("div .keyDetails-value::text")
    ]
    features_data: dict[str, list[str]] = {}
    for feature_block in sel.css(".amenity-group ul div.title"):
        label = feature_block.css("::text").get()
        features = feature_block.xpath("following-sibling::li/span")
        features_data[label or ""] = [
            "".join(feat.xpath(".//text()").getall()).strip() for feat in features
        ]
    return {
        "address": address.strip(),
        "description": description,
        "price": price,
        "estimatedMonthlyPrice": estimated_monthly_price,
        "propertyUrl": url,
        "attachments": images,
        "details": details,
        "features": features_data,
    }

def parse_property_for_rent(html: str) -> str | None:
    """Extract the 36-char rental UUID from `og:image`. """
    sel = Selector(text=html)
    data = sel.xpath("//meta[@property='og:image']/@content").get()
    if not data:
        return None
    try:
        rental_id = data.split("rent/")[1].split("/")[0]
        assert len(rental_id) == 36
        return rental_id
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_search(url: str) -> list[dict]:
    """Scrape search data from Redfin's gis search API."""
    body = await _fetch(url, as_text=True)
    data = parse_search_api(body)
    logger.success("scraped ({}) search results from the search API", len(data))
    return data

async def scrape_property_for_sale(urls: list[str]) -> list[dict]:
    """Scrape properties for sale data from HTML."""
    out: list[dict] = []
    for url in urls:
        html = await _fetch(
            url,
            as_text=False,
            ready_selector="div[data-rf-test-id='abp-price'], div[class*='street-address']",
        )
        out.append(parse_property_for_sale(html, url))
    logger.success("scraped {} property listings for sale", len(out))
    return out

async def scrape_property_for_rent(urls: list[str]) -> list[dict]:
    """Scrape rentals via the floorPlans API."""
    api_urls: list[str] = []
    for url in urls:
        html = await _fetch(url, as_text=False, ready_selector="meta[property='og:image']")
        rental_id = parse_property_for_rent(html)
        if rental_id:
            api_urls.append(
                f"https://www.redfin.com/stingray/api/v1/rentals/{rental_id}/floorPlans"
            )
    properties: list[dict] = []
    for api_url in api_urls:
        body = await _fetch(api_url, as_text=True)
        properties.append(json.loads(body))
    logger.success("scraped {} property listings for rent", len(properties))
    return properties

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
