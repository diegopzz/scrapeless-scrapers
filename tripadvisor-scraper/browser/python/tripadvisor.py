"""Tripadvisor scraper using the official Scrapeless Python SDK + Playwright over CDP.
the function names and emitted field shapes match verbatim, so downstream code
can Public entry points:
- `scrape_location_data(query)` -> list of typeahead autocomplete results
- `scrape_search(search_url, max_pages=None)` -> hotel previews
- `scrape_hotel(url, max_review_pages=None)` -> hotel detail + reviews
"""

from __future__ import annotations

import asyncio
import json
import math
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse, urlunparse

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

def _looks_blocked(html: str) -> bool:
    if not html or len(html) < 5000:
        return True
    if "Captcha Interception" in html or "Pardon Our Interruption" in html:
        return True
    return False


async def _fetch_rendered_html(
    url: str,
    ready_selector: Optional[str] = None,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 2,
    warmup: bool = True,
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
                if warmup:
                    try:
                        await page.goto("https://www.tripadvisor.com/", wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(2.5)
                    except Exception:
                        pass
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=15000)
                    except Exception as e:
                        logger.warning("wait_for_selector failed (continuing): {}", e)
                await asyncio.sleep(2)
                html = await page.content()
                if html and not _looks_blocked(html):
                    return html
                last_error = RuntimeError("captcha block" if _looks_blocked(html) else "empty HTML")
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
# Location autocomplete (intercept TripAdvisor's GraphQL XHR)
# ---------------------------------------------------------------------------

async def scrape_location_data(query: str) -> List[Dict[str, Any]]:
    """Scrape TripAdvisor typeahead autocomplete results for `query`."""
    logger.info(f"scraping location data: {query}")
    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=DEFAULT_PROXY_COUNTRY, session_ttl=DEFAULT_SESSION_TTL)
    )
    captured: List[Dict[str, Any]] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
        try:
            ctx = await browser.new_context()
            page = await ctx.new_page()

            async def on_response(resp):
                try:
                    if "graphql" not in resp.url:
                        return
                    body = await resp.json()
                    entries = body if isinstance(body, list) else [body]
                    for entry in entries:
                        if isinstance(entry, dict) and "Typeahead_autocomplete" in entry.get("data", {}):
                            captured.extend(entry["data"]["Typeahead_autocomplete"].get("results", []))
                except Exception:
                    pass

            page.on("response", on_response)
            await page.goto("https://www.tripadvisor.com/", wait_until="domcontentloaded", timeout=30000)
            # TripAdvisor's homepage initially renders the search input as a
            # visually-hidden field behind a "Where to?" prompt. A click on
            # the document brings the real <input name="q"> into focus; once
            # that input has focus, the typeahead XHR fires on every keystroke.
            await page.wait_for_timeout(4000)
            try:
                await page.evaluate("document.documentElement.click()")
            except Exception:
                pass
            await page.wait_for_timeout(1500)
            try:
                await page.keyboard.type(query, delay=120)
            except Exception as e:
                logger.warning("type failed: {}", e)
            await page.wait_for_timeout(6000)
        finally:
            try:
                await browser.close()
            except Exception:
                pass
    logger.info(f"found {len(captured)} results")
    return captured

# ---------------------------------------------------------------------------
# Search (hotel listings)
# ---------------------------------------------------------------------------

def parse_search_page(html: str, base_url: str) -> List[Dict[str, Any]]:
    """Parse result previews from a TripAdvisor hotel search page."""
    sel = Selector(text=html)
    parsed: List[Dict[str, Any]] = []
    # location #1: modern hotels-main-list cards
    for box in sel.xpath("//div[@data-test-target='hotels-main-list']//ol/li"):
        title_list = box.xpath(".//div[@data-automation='hotel-card-title']/a/h3/text()").getall()
        title = title_list[1] if len(title_list) > 1 else (title_list[0] if title_list else None)
        url = box.css("div[data-automation=hotel-card-title] a::attr(href)").get()
        if not url:
            continue
        parsed_url = urlparse(urljoin(base_url, url))
        clean_url = urlunparse(parsed_url._replace(query="", fragment=""))
        parsed.append({"url": clean_url, "name": title})
    if parsed:
        return parsed
    # location #2: legacy listing_title cards
    for box in sel.css("div.listing_title>a"):
        parsed.append(
            {
                "url": urljoin(base_url, box.xpath("@href").get() or ""),
                "name": (box.xpath("text()").get("") or "").split(". ")[-1],
            }
        )
    return parsed

async def scrape_search(search_url: str, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
    """Scrape search results from a TripAdvisor hotel listing URL."""
    logger.info(f"{search_url}: scraping first search results page")
    first_html = await _fetch_rendered_html(
        search_url, ready_selector="div[data-test-target='hotels-main-list']"
    )
    results = parse_search_page(first_html, search_url)
    if not results:
        logger.error("query {} found no results", search_url)
        return []

    page_size = len(results)
    sel = Selector(text=first_html)
    counter = sel.xpath("//div[@data-test-target='hotels-main-list']//span").re(r"(\d[\d,]*)")
    total_results = int(counter[0].replace(",", "")) if counter else page_size
    next_page_url = sel.css('a[aria-label="Next page"]::attr(href)').get()
    if next_page_url:
        next_page_url = urljoin(search_url, next_page_url)
    total_pages = int(math.ceil(total_results / max(page_size, 1)))
    if max_pages and total_pages > max_pages:
        total_pages = max_pages

    if not next_page_url or total_pages <= 1:
        return results

    logger.info(f"{search_url}: total_results={total_results}, scraping {total_pages} pages")
    other_page_urls = [
        next_page_url.replace(f"oa{page_size}", f"oa{page_size * i}")
        for i in range(1, total_pages)
    ]
    for url in other_page_urls:
        try:
            html = await _fetch_rendered_html(
                url, ready_selector="div[data-test-target='hotels-main-list']"
            )
            results.extend(parse_search_page(html, url))
        except Exception as e:  # noqa: BLE001
            logger.error("error scraping {}: {}", url, e)
    return results

# ---------------------------------------------------------------------------
# Hotel page (info + reviews)
# ---------------------------------------------------------------------------

def parse_hotel_page(html: str) -> Dict[str, Any]:
    """Parse hotel data + on-page reviews."""
    sel = Selector(text=html)
    basic_data: Dict[str, Any] = {}
    # Prefer the explicit JSON-LD LodgingBusiness/Hotel block.
    for raw in sel.xpath('//script[@type="application/ld+json"]/text()').getall():
        try:
            parsed = json.loads(raw)
        except Exception:
            continue
        if isinstance(parsed, dict) and "@graph" in parsed and isinstance(parsed["@graph"], list):
            candidates = parsed["@graph"]
        elif isinstance(parsed, list):
            candidates = parsed
        else:
            candidates = [parsed]
        for node in candidates:
            if not isinstance(node, dict):
                continue
            t = node.get("@type")
            if t in ("LodgingBusiness", "Hotel") or (
                isinstance(t, list) and any(x in ("LodgingBusiness", "Hotel") for x in t)
            ):
                basic_data = node
                break
        if basic_data:
            break
    if not basic_data:
        basic_script = sel.xpath("//script[contains(text(),'aggregateRating')]/text()").get()
        if basic_script:
            try:
                basic_data = json.loads(basic_script)
            except Exception:
                basic_data = {}
    description = sel.xpath(
        "//div[@data-automation='aboutTabDescription']/div/div/div/text()"
    ).get()
    amenities: List[str] = []
    for feature in sel.xpath("//div[contains(@data-test-target, 'amenity')]/text()"):
        amenities.append(feature.get())

    reviews: List[Dict[str, Any]] = []
    for review in sel.xpath("//div[@data-test-target='HR_CC_CARD']"):
        title = review.xpath(".//div[@data-test-target='review-title']//span//text()").get()
        text = "".join(
            review.xpath(
                ".//div[@class='_c']//div[contains(@class, 'fIrGe')]//span[contains(@class, 'JguWG')]//span/text()"
            ).extract()
        )
        rate_raw = review.xpath(".//*[contains(text(),'of 5 bubbles')]/text()").get()
        rate = float(rate_raw.replace(" of 5 bubbles", "")) if rate_raw else None
        trip_date = review.xpath(
            ".//span[contains(text(), 'Date of stay:')]/parent::div/following-sibling::span/text()"
        ).get()
        trip_type = review.xpath(
            ".//span[contains(text(), 'Trip type:')]/parent::div/following-sibling::span/text()"
        ).get()
        reviews.append(
            {
                "title": title,
                "text": text,
                "rate": rate,
                "tripDate": trip_date,
                "tripType": trip_type,
            }
        )

    return {
        "basic_data": basic_data,
        "description": description,
        # NB: the upstream reference uses the typo "featues" — preserved verbatim for parity.
        "featues": amenities,
        "reviews": reviews,
    }

async def scrape_hotel(url: str, max_review_pages: Optional[int] = None) -> Dict[str, Any]:
    """Scrape a TripAdvisor hotel detail page and paginate reviews."""
    first_html = await _fetch_rendered_html(
        url, ready_selector="div[data-test-target='HR_CC_CARD']"
    )
    hotel_data = parse_hotel_page(first_html)

    _review_page_size = 10
    try:
        total_reviews = int(hotel_data["basic_data"]["aggregateRating"]["reviewCount"])
    except (KeyError, TypeError, ValueError):
        total_reviews = 0
    total_review_pages = math.ceil(total_reviews / _review_page_size) if total_reviews else 0
    if max_review_pages and max_review_pages < total_review_pages:
        total_review_pages = max_review_pages

    review_urls = [
        url.replace("-Reviews-", f"-Reviews-or{_review_page_size * i}-")
        for i in range(1, total_review_pages + 1)
    ]
    for review_url in review_urls:
        try:
            html = await _fetch_rendered_html(
                review_url, ready_selector="div[data-test-target='HR_CC_CARD']"
            )
            data = parse_hotel_page(html)
            hotel_data["reviews"].extend(data["reviews"])
        except Exception as e:  # noqa: BLE001
            logger.error("error scraping {}: {}", review_url, e)
    logger.success(f"scraped one hotel data with {len(hotel_data['reviews'])} reviews")
    return hotel_data

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
