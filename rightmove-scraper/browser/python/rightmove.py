"""Rightmove scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names + emitted field names match verbatim.

Three surfaces:
- `scrape_properties(urls)`                    — `window.PAGE_MODEL.propertyData`, JMESPath-reduced.
- `find_locations(query)`                      — typeahead API → `"<type>^<id>"` strings.
- `scrape_search(name, id, all, max_props)`    — `/api/property-search/listing/search` paginated.

Uses a GB residential proxy (Rightmove is geo-locked).
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode

import jmespath
from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "GB"
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

async def _fetch(
    url: str,
    *,
    as_text: bool = False,
    ready_selector: str | None = None,
    wait_for_global: str | None = None,
    eval_global: str | None = None,
):
    """Fetch a page over CDP.

    Returns:
        - if `eval_global` is set: a tuple `(html, evaluated)` where `evaluated`
          is whatever the JS expression returned (or None on failure).
        - otherwise: the raw HTML (or `document.body.innerText` if `as_text`).
    """
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
                    logger.warning("wait_for_selector failed: {}", e)
            if wait_for_global:
                try:
                    await page.wait_for_function(f"!!window.{wait_for_global}", timeout=15000)
                except Exception as e:
                    logger.warning("wait_for_function({}) failed: {}", wait_for_global, e)
            if as_text:
                body = await page.evaluate("() => document.body && document.body.innerText")
                if body and body.strip():
                    return body
            evaluated = None
            if eval_global:
                try:
                    evaluated = await page.evaluate(eval_global)
                except Exception as e:
                    logger.warning("page.evaluate failed: {}", e)
            html = await page.content()
            if eval_global is not None:
                return html, evaluated
            return html
        finally:
            try:
                await browser.close()
            except Exception:
                pass

# ---------------------------------------------------------------------------
# Parsers — mirror the upstream reference verbatim
# ---------------------------------------------------------------------------

PROPERTY_PARSE_MAP = {
    "id": "id",
    "available": "status.published",
    "archived": "status.archived",
    "phone": "contactInfo.telephoneNumbers.localNumber",
    "bedrooms": "bedrooms",
    "bathrooms": "bathrooms",
    "type": "transactionType",
    "property_type": "propertySubType",
    "tags": "tags",
    "description": "text.description",
    "title": "text.pageTitle",
    "subtitle": "text.propertyPhrase",
    "price": "prices.primaryPrice",
    "price_sqft": "prices.pricePerSqFt",
    "address": "address",
    "latitude": "location.latitude",
    "longitude": "location.longitude",
    "features": "keyFeatures",
    "history": "listingHistory",
    "photos": "images[*].{url: url, caption: caption}",
    "floorplans": "floorplans[*].{url: url, caption: caption}",
    "agency": """customer.{
        id: branchId,
        branch: branchName,
        company: companyName,
        address: displayAddress,
        commercial: commercial,
        buildToRent: buildToRent,
        isNew: isNewHomeDeveloper
    }""",
    "industryAffiliations": "industryAffiliations[*].name",
    "nearest_airports": "nearestAirports[*].{name: name, distance: distance}",
    "nearest_stations": "nearestStations[*].{name: name, distance: distance}",
    "sizings": "sizings[*].{unit: unit, min: minimumSize, max: maximumSize}",
    "brochures": "brochures",
}

def parse_property(data: dict) -> dict:
    """"""
    out: dict[str, Any] = {}
    for key, path in PROPERTY_PARSE_MAP.items():
        out[key] = jmespath.search(path, data)
    return out

def find_json_objects(text: str, decoder: json.JSONDecoder | None = None):
    """Walk a JS payload yielding parsed JSON objects. """
    decoder = decoder or json.JSONDecoder()
    pos = 0
    while True:
        match = text.find("{", pos)
        if match == -1:
            break
        try:
            result, index = decoder.raw_decode(text[match:])
            yield result
            pos = match + index
        except ValueError:
            pos = match + 1

def _revive_devalue(arr: list) -> Any:
    """Revive a Devalue-flattened array (slot 0 is root, numeric values point at
    other slots). Rightmove emits propertyData via this format."""
    seen: dict[int, Any] = {}

    def r(i):
        if not isinstance(i, int) or isinstance(i, bool):
            return i
        if i in seen:
            return seen[i]
        if i < 0 or i >= len(arr):
            return None
        v = arr[i]
        if v is None or not isinstance(v, (dict, list)):
            seen[i] = v
            return v
        if isinstance(v, list):
            out: list = []
            seen[i] = out
            for e in v:
                out.append(r(e) if isinstance(e, int) and not isinstance(e, bool) else e)
            return out
        out_d: dict = {}
        seen[i] = out_d
        for k, val in v.items():
            out_d[k] = r(val) if isinstance(val, int) and not isinstance(val, bool) else val
        return out_d

    return r(0)


def extract_property(html: str) -> dict:
    """Extract `propertyData` from the inline `PAGE_MODEL` JS."""
    sel = Selector(text=html)
    script = sel.xpath("//script[contains(.,'PAGE_MODEL = ')]/text()").get()
    if not script:
        raise RuntimeError("PAGE_MODEL script not found")
    for obj in find_json_objects(script):
        if not isinstance(obj, dict):
            continue
        # New Devalue-encoded form: {"data": "<stringified array>", "encoding": "..."}
        if isinstance(obj.get("data"), str) and "encoding" in obj:
            try:
                arr = json.loads(obj["data"])
            except Exception:
                arr = None
            if isinstance(arr, list) and arr:
                root = _revive_devalue(arr)
                if isinstance(root, dict) and isinstance(root.get("propertyData"), dict):
                    return root["propertyData"]
        # Legacy form: {"propertyData": {...}}
        if isinstance(obj.get("propertyData"), dict):
            return obj["propertyData"]
    raise RuntimeError("propertyData not found in PAGE_MODEL")

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference verbatim
# ---------------------------------------------------------------------------

async def scrape_properties(urls: list[str]) -> list[dict]:
    """Scrape Rightmove property listings for property data."""
    properties: list[dict] = []
    for url in urls:
        html = await _fetch(
            url,
            ready_selector='#propertyHeader, [data-test="property-header"]',
        )
        logger.info("scraping property page {}", url)
        property_data = extract_property(html)
        if not property_data:
            raise RuntimeError(f"propertyData missing for {url}")
        properties.append(parse_property(property_data))
    return properties

async def find_locations(query: str) -> list[str]:
    """Use Rightmove's typeahead API to find location IDs."""
    url = f"https://los.rightmove.co.uk/typeahead?query={query}&limit=10&exclude=STREET"
    body = await _fetch(url, as_text=True)
    data = json.loads(body)
    return [f"{p['type']}^{p['id']}" for p in data.get("matches", [])]

async def scrape_search(
    location_name: str,
    location_id: str,
    scrape_all_properties: bool,
    max_properties: int = 1000,
) -> list[dict]:
    """Scrape properties from Rightmove's search API. """
    RESULTS_PER_PAGE = 24

    def make_url(offset: int) -> str:
        params = {
            "searchLocation": location_name,
            "useLocationIdentifier": True,
            "locationIdentifier": location_id,
            "radius": "0.0",
            "_includeSSTC": True,
            "index": offset,
            "sortType": "2",
            "channel": "BUY",
            "transactionType": "BUY",
        }
        return "https://www.rightmove.co.uk/api/property-search/listing/search?" + urlencode(params)

    first_body = await _fetch(make_url(0), as_text=True)
    first_data = json.loads(first_body)
    results: list[dict] = list(first_data["properties"])
    total_results = int(str(first_data["resultCount"]).replace(",", ""))

    if not scrape_all_properties and max_properties < total_results:
        MAX = max_properties
    else:
        MAX = total_results

    MAX_API = 1000
    offsets = []
    for offset in range(RESULTS_PER_PAGE, MAX, RESULTS_PER_PAGE):
        if offset >= MAX_API:
            break
        offsets.append(offset)
    logger.info("scraping {} more search pages", len(offsets))
    for offset in offsets:
        try:
            body = await _fetch(make_url(offset), as_text=True)
            data = json.loads(body)
            results.extend(data["properties"])
        except Exception as e:
            logger.warning("failed offset {}: {}", offset, e)
    logger.info("scraped {} properties from location id {}", len(results), location_id)
    return results

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj
