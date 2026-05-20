"""Zoopla scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names + emitted field names match verbatim.

Two surfaces:
- `scrape_properties(urls)` — DOM-parse a Zoopla property page (no clean cache).
- `scrape_search(...)`      — DOM-parse cards + `__ZAD_TARGETING__` totals JSON.

Uses a GB residential proxy (Zoopla is geo-locked + Akamai-protected).
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal

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

async def _fetch_html(url: str, ready_selector: str | None, *, auto_scroll: bool = False) -> str:
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
            if auto_scroll:
                # Trigger lazy-loaded sections before grabbing HTML.
                try:
                    await page.evaluate(
                        """async () => {
                            const sleep = ms => new Promise(r => setTimeout(r, ms));
                            const step = 600;
                            for (let y = 0; y < document.body.scrollHeight; y += step) {
                                window.scrollTo(0, y);
                                await sleep(150);
                            }
                            window.scrollTo(0, 0);
                        }"""
                    )
                    await page.wait_for_timeout(1000)
                except Exception as e:
                    logger.warning("auto-scroll failed: {}", e)
            return await page.content()
        finally:
            try:
                await browser.close()
            except Exception:
                pass

# ---------------------------------------------------------------------------
# Parsers — mirror the upstream reference verbatim
# ---------------------------------------------------------------------------

def parse_property(html: str) -> dict:
    """"""
    selector = Selector(text=html)
    url = selector.xpath("//meta[@property='og:url']/@content").get()
    price = selector.xpath("//p[contains(text(),'£')]/text()").get()
    receptions = selector.xpath("//p[contains(text(),'reception')]/text()").get()
    baths = selector.xpath("//p[contains(text(),'bath')]/text()").get()
    beds = selector.xpath("//p[contains(text(),'bed')]/text()").get()
    gmap_source = selector.xpath(
        "(//section[@aria-labelledby='local-area']//picture/source/@srcset)[last()]"
    ).get()
    coordinates = gmap_source.split("/static/")[1].split("/")[0] if gmap_source else None
    agent_path = selector.xpath("//section[@aria-label='Contact agent']//a/@href").get()

    info = []
    for i in selector.xpath("//section[@aria-labelledby='key-info']//li"):
        title = i.xpath(".//p/text()").get()
        value = i.xpath(".//div/p/text()").get()
        if value is not None:
            info.append({"title": title, "value": value})

    nearby = []
    for i in selector.xpath("//div[section[contains(@aria-label,'Travel')]]/section[3]//li/div"):
        distance = i.xpath(".//p[2]/text()").get()
        nearby.append(
            {
                "title": i.xpath(".//p[1]/text()").get(),
                "distance": float(distance.split(" ")[0]) if distance else None,
                "unit": distance.split(" ")[1] if distance else None,
            }
        )

    return {
        "id": int(url.split("details/")[-1].split("/")[0]) if url and "details/" in url else None,
        "url": url,
        "title": selector.xpath("//title/text()").get(),
        "address": selector.xpath("//address/text()").get(),
        "price": {
            "amount": int(price.replace("£", "").replace(",", "")) if price else None,
            "currency": "£",
        },
        "gallery": selector.xpath(
            "//li[contains(@data-key,'gallery')]/picture/source[last()]/@srcset"
        ).getall(),
        "epcRating": selector.xpath("//p[contains(text(),'EPC')]/text()").get(),
        "floorArea": selector.xpath("//p[contains(text(),'ft')]/text()").get(),
        "numOfReceptions": int(receptions.split(" ")[0]) if receptions else None,
        "numOfBathrooms": int(baths.split(" ")[0]) if baths else None,
        "numOfBedrooms": int(beds.split(" ")[0]) if beds else None,
        "propertyTags": selector.xpath("(//section/ul)[1]/li/p/text()").getall(),
        "propertyInfo": info,
        "propertyDescription": selector.xpath(
            "//section[@aria-labelledby='about']/ul/li/p/span/text()"
        ).getall(),
        "coordinates": {
            "googleMapeSource": gmap_source,
            "latitude": float(coordinates.split(",")[0]) if coordinates else None,
            "longitude": float(coordinates.split(",")[1]) if coordinates else None,
        },
        "nearby": nearby,
        "agent": {
            "name": selector.xpath("//section[@aria-label='Contact agent']//p/text()").get(),
            "logo": selector.xpath("//section[@aria-label='Contact agent']//img/@src").get(),
            "url": "https://www.zoopla.co.uk" + agent_path if agent_path else None,
        },
    }

def parse_search(html: str) -> dict:
    """Returns {search_data, total_pages}."""
    selector = Selector(text=html)
    data = []
    targeting = selector.xpath("//script[@id='__ZAD_TARGETING__']/text()").get()
    total_results = int(json.loads(targeting)["search_results_count"]) if targeting else 0
    boxes = selector.xpath("//div[@data-testid='regular-listings']/div")
    results_count = len(boxes) or 1
    total_pages = total_results // results_count

    for box in boxes:
        url = box.xpath(".//a/@href").get()
        if not url:
            continue
        price = box.xpath(".//p[contains(@class, 'priceText')]/text()").get()
        sq_ft = box.xpath(".//span[contains(text(),'sq ft')]/text()").get()
        sq_ft = int(sq_ft.split(" ")[0].strip("~,")) if sq_ft else None
        bathrooms = box.xpath(".//span[(contains(text(), 'bath'))]/text()").get()
        bedrooms = box.xpath(".//span[(contains(text(), 'bed'))]/text()").get()
        livingrooms = box.xpath(".//span[(contains(text(), 'reception'))]/text()").get()
        image = box.xpath(".//picture/source/@srcset").get()
        agency = box.xpath("//img[contains(@src,'agent')]/@alt").get()
        item = {
            "price": int(price.split(" ")[0].replace("£", "").replace(",", "")) if price else None,
            "priceCurrency": "Sterling pound £",
            "url": "https://www.zoopla.co.uk" + url.split("?")[0] if url else None,
            "image": image.split(":p")[0] if image else None,
            "address": box.xpath(".//address/text()").get(),
            "squareFt": sq_ft,
            "numBathrooms": int(bathrooms.split(" ")[0]) if bathrooms else None,
            "numBedrooms": int(bedrooms.split(" ")[0]) if bedrooms else None,
            "numLivingRoom": int(livingrooms.split(" ")[0]) if livingrooms else None,
            "description": box.xpath(".//a[address]/p/text()").get(),
            "justAdded": bool(box.xpath(".//div[text()='Just added']/text()").get()),
            "agency": agency,
        }
        data.append(item)
    return {"search_data": data, "total_pages": total_pages}

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference verbatim
# ---------------------------------------------------------------------------

async def scrape_properties(urls: list[str]) -> list[dict]:
    """Scrape Zoopla property listings."""
    out: list[dict] = []
    for url in urls:
        try:
            logger.info("scraping property page {}", url)
            html = await _fetch_html(
                url,
                ready_selector="section[aria-labelledby='local-area']",
                auto_scroll=True,
            )
            out.append(parse_property(html))
        except Exception as e:
            logger.error("error scraping {}: {}", url, e)
    return out

async def scrape_search(
    scrape_all_pages: bool,
    location_slug: str,
    max_scrape_pages: int = 10,
    query_type: Literal["for-sale", "to-rent"] = "for-sale",
) -> list[dict]:
    """Scrape Zoopla search pages for property listings."""
    first_url = f"https://www.zoopla.co.uk/{query_type}/property/{location_slug}"
    first_html = await _fetch_html(
        first_url,
        ready_selector="p[data-testid='total-results']",
        auto_scroll=True,
    )
    first_data = parse_search(first_html)
    search_data = list(first_data["search_data"])
    max_search_pages = first_data["total_pages"]
    total_pages_to_scrape = (
        max_search_pages if scrape_all_pages or max_scrape_pages >= max_search_pages
        else max_scrape_pages
    )
    logger.info("scraping {} more search pages", max(0, total_pages_to_scrape - 1))
    for p in range(2, total_pages_to_scrape + 1):
        try:
            html = await _fetch_html(
                f"{first_url}?pn={p}",
                ready_selector="div[data-testid='regular-listings']",
            )
            search_data.extend(parse_search(html)["search_data"])
        except Exception as e:
            logger.warning("failed page {}: {}", p, e)
    logger.info("scraped {} search listings from {}", len(search_data), first_url)
    return search_data

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj
