"""Immobilienscout24 scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names (including the upstream reference's typos like
`propertyLlink`, `propertySepcs`, `priceWithoutHeadting`) match verbatim.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

PROXY_COUNTRY = "DE"
DEFAULT_SESSION_TTL = 180

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
    ready_selector: str,
    *,
    proxy_country: str = PROXY_COUNTRY,
    retries: int = 1,
) -> str:
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
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    await page.wait_for_selector(ready_selector, timeout=20000)
                except Exception as e:
                    logger.warning("wait_for_selector failed (continuing): {}", e)
                html = await page.content()
                if html:
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
# Parsers — field names mirror the upstream reference verbatim (including typos)
# ---------------------------------------------------------------------------

def _txt(sel, xpath: str) -> str | None:
    v = sel.xpath(xpath).get()
    return v.strip() if v else None

def parse_property(html: str, url: str) -> Dict[str, Any]:
    sel = Selector(text=html)

    canonical = sel.xpath("//link[@rel='canonical']/@href").get() or url
    listing_id = ""
    m = re.search(r"/expose/(\d+)", canonical)
    if m:
        listing_id = m.group(1)

    price_text = _txt(sel, "//dd[contains(@class, 'kaltmiete')]/text()") or ""
    currency_match = re.search(r"([€$£])", price_text)
    price_currency = currency_match.group(1) if currency_match else None

    images = sel.xpath(
        "//div[@class='sp-slides']//div[contains(@class, 'sp-slide')]//img/@data-src"
    ).getall()
    video_available = bool(sel.xpath("//div[@class='sp-slides']//div[contains(@class, 'sp-video')]"))
    internet_text = _txt(sel, "//a[contains(@class, 'mediaavailcheck')]/text()") or ""

    additional_specs = [
        t.strip()
        for t in sel.xpath("//div[contains(@class, 'criteriagroup')]//dd/text()").getall()
        if t and t.strip()
    ]

    return {
        "id": listing_id,
        "title": _txt(sel, "//h1[@id='expose-title']/text()") or "",
        "description": sel.xpath("//meta[@name='description']/@content").get(),
        "address": _txt(sel, "//div[@class='address-block']/div/span[2]/text()"),
        "propertyLlink": canonical,
        "propertySepcs": {
            "floorsNumber": _txt(sel, "//dd[contains(@class, 'etage')]/text()"),
            "livingSpace": _txt(sel, "//dd[contains(@class, 'wohnflaeche')]/text()"),
            "livingSpaceUnit": _txt(sel, "//dd[contains(@class, 'wohnflaeche')]/span/text()"),
            "vacantFrom": _txt(sel, "//dd[contains(@class, 'bezugsfrei')]/text()"),
            "numberOfRooms": _txt(sel, "//dd[contains(@class, 'zimmer')]/text()"),
            "Garage/parking space": _txt(sel, "//dd[contains(@class, 'garage-stellplatz')]/text()"),
            "additionalSpecs": additional_specs,
            "internetAvailable": "verfügbar" in internet_text.lower() or "available" in internet_text.lower(),
        },
        "price": {
            "priceWithoutHeadting": price_text.strip() or None,
            "priceperMeter": _txt(sel, "//dd[contains(@class, 'preism2')]/text()"),
            "additionalCosts": _txt(sel, "//dd[contains(@class, 'nebenkosten')]/text()"),
            "heatingCosts": _txt(sel, "//dd[contains(@class, 'heizkosten')]/text()"),
            "totalRent": _txt(sel, "//dd[contains(@class, 'gesamtmiete')]/text()"),
            "basisRent": _txt(sel, "//dd[contains(@class, 'baseprice')]/text()"),
            "deposit": _txt(sel, "//dd[contains(@class, 'kaution')]/text()"),
            "garage/parkingRent": _txt(sel, "//dd[contains(@class, 'stellplatzmiete')]/text()"),
            "priceCurrency": price_currency,
        },
        "building": {
            "constructionYear": _txt(sel, "//dd[contains(@class, 'baujahr')]/text()"),
            "energySources": _txt(sel, "//dd[contains(@class, 'energietraeger')]/text()"),
            "energyCertificate": _txt(sel, "//dd[contains(@class, 'energieausweis')]/text()"),
            "energyCertificateType": _txt(sel, "//dd[contains(@class, 'energieausweistyp')]/text()"),
            "energyCertificateDate": _txt(sel, "//dd[contains(@class, 'energieausweis-gueltig')]/text()"),
            "finalEnergyRrequirement": _txt(sel, "//dd[contains(@class, 'endenergiebedarf')]/text()"),
        },
        "attachments": {
            "propertyImages": images,
            "videoAvailable": video_available,
        },
        "agencyName": _txt(sel, "//span[@data-qa='companyName']/text()"),
        "agencyAddress": _txt(sel, "//div[@data-qa='companyAddress']/text()"),
    }

def _search_property_urls(html: str) -> List[str]:
    sel = Selector(text=html)
    hrefs = sel.css("a.result-list-entry__brand-title-container::attr(href)").getall()
    if not hrefs:
        hrefs = sel.xpath("//a[contains(@href, '/expose/')]/@href").getall()
    out: List[str] = []
    seen = set()
    for h in hrefs:
        if h.startswith("/"):
            h = "https://www.immobilienscout24.de" + h
        # strip trailing fragments
        h = h.split("#", 1)[0]
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_properties(urls: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for u in urls:
        html = await _fetch_rendered_html(u, ready_selector="h1#expose-title")
        out.append(parse_property(html, u))
    return out

async def scrape_search(
    url: str,
    scrape_all_pages: bool = False,
    max_scrape_pages: int = 10,
) -> List[Dict[str, Any]]:
    first = await _fetch_rendered_html(url, ready_selector="a[href*='/expose/']")
    property_urls = _search_property_urls(first)

    sel = Selector(text=first)
    total_pages = 1
    for href in sel.css("a[href*='pagenumber=']::attr(href)").getall():
        m = re.search(r"pagenumber=(\d+)", href)
        if m:
            total_pages = max(total_pages, int(m.group(1)))
    if not scrape_all_pages:
        total_pages = min(total_pages, max_scrape_pages)

    for page in range(2, total_pages + 1):
        sep = "&" if "?" in url else "?"
        page_url = f"{url}{sep}pagenumber={page}"
        html = await _fetch_rendered_html(page_url, ready_selector="a[href*='/expose/']")
        property_urls.extend(_search_property_urls(html))

    # dedupe
    seen = set()
    unique = []
    for u in property_urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    return await scrape_properties(unique)

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
