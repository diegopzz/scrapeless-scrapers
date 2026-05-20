"""Trustpilot scraper using the official Scrapeless Python SDK + Playwright over CDP.
the function names and emitted field shapes match verbatim, so downstream code
can Public entry points:
- `scrape_company(urls)` -> list of company dicts (`pageUrl`, `companyDetails`, `reviews`)
- `scrape_search(url, max_pages=None)` -> list of business cards
- `scrape_reviews(url, max_pages=None)` -> paginated reviews via Trustpilot's Next.js data API
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

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

async def _fetch_rendered_html(
    url: str,
    ready_selector: Optional[str] = "script#__NEXT_DATA__",
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
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=15000)
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

async def _fetch_json(
    url: str,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
) -> str:
    """GET a JSON URL through the cloud browser so it inherits Trustpilot cookies."""
    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
    )
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
        try:
            ctx = await browser.new_context()
            # Warm cookies on www.trustpilot.com first.
            warm = await ctx.new_page()
            try:
                await warm.goto("https://www.trustpilot.com/", wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass
            response = await ctx.request.get(url)
            return await response.text()
        finally:
            try:
                await browser.close()
            except Exception:
                pass

# ---------------------------------------------------------------------------
# Parsers — mirror the upstream reference's function names
# ---------------------------------------------------------------------------

def parse_hidden_data(html: str) -> Dict[str, Any]:
    """Parse `__NEXT_DATA__` JSON from a Trustpilot HTML page."""
    sel = Selector(text=html)
    script = sel.xpath("//script[@id='__NEXT_DATA__']/text()").get()
    if not script:
        return {}
    return json.loads(script)

def parse_company_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse company data from `__NEXT_DATA__`, excluding web-app plumbing."""
    page_props = data.get("props", {}).get("pageProps", {})
    return {
        "pageUrl": page_props.get("pageUrl"),
        "companyDetails": page_props.get("businessUnit"),
        "reviews": page_props.get("reviews"),
    }

# ---------------------------------------------------------------------------
# Scrape functions
# ---------------------------------------------------------------------------

async def scrape_company(urls: List[str]) -> List[Dict[str, Any]]:
    """Scrape Trustpilot company pages."""
    companies: List[Dict[str, Any]] = []
    for url in urls:
        html = await _fetch_rendered_html(url)
        data = parse_hidden_data(html)
        companies.append(parse_company_data(data))
    logger.success(f"scraped {len(companies)} company listings from company pages")
    return companies

async def scrape_search(url: str, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
    """Scrape Trustpilot category/search pages."""
    logger.info("scraping the first search page")
    first_html = await _fetch_rendered_html(url)
    data = parse_hidden_data(first_html)["props"]["pageProps"]["businessUnits"]
    search_data: List[Dict[str, Any]] = list(data.get("businesses", []))

    total_pages = data.get("totalPages") or 1
    if max_pages and max_pages < total_pages:
        total_pages = max_pages

    logger.info(f"scraping search pagination ({total_pages - 1} more pages)")
    for page_number in range(2, total_pages + 1):
        try:
            page_html = await _fetch_rendered_html(f"{url}?page={page_number}")
            page_data = parse_hidden_data(page_html)["props"]["pageProps"]["businessUnits"][
                "businesses"
            ]
            search_data.extend(page_data)
        except Exception as e:  # noqa: BLE001
            logger.error("error scraping search page {}: {}", page_number, e)
    logger.success(f"scraped {len(search_data)} company listings from search")
    return search_data

async def get_reviews_api_url(url: str) -> str:
    """Build Trustpilot's Next.js review data API URL for `url`."""
    html = await _fetch_rendered_html(url)
    sel = Selector(text=html)
    script = sel.xpath("//script[@id='__NEXT_DATA__']/text()").get()
    build_id = json.loads(script)["buildId"]
    business_unit = url.split("review/")[-1]
    return (
        f"https://www.trustpilot.com/_next/data/{build_id}/review/{business_unit}.json"
        f"?sort=recency&businessUnit={business_unit}"
    )

async def scrape_reviews(url: str, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
    """Scrape reviews for a Trustpilot company page via the Next.js data API."""
    logger.info(f"getting the reviews API for the URL {url}")
    api_url = await get_reviews_api_url(url)
    first_text = await _fetch_json(api_url)
    first_data = json.loads(first_text)["pageProps"]
    reviews_data: List[Dict[str, Any]] = list(first_data.get("reviews", []))

    total_pages = first_data.get("filters", {}).get("pagination", {}).get("totalPages", 1)
    if max_pages and max_pages < total_pages:
        total_pages = max_pages

    logger.info(f"scraping reviews pagination ({total_pages - 1} more pages)")
    for page_number in range(2, total_pages + 1):
        try:
            text = await _fetch_json(f"{api_url}&page={page_number}")
            data = json.loads(text)["pageProps"]["reviews"]
            reviews_data.extend(data)
        except Exception as e:  # noqa: BLE001
            logger.error("error scraping reviews page {}: {}", page_number, e)
    logger.success(f"scraped {len(reviews_data)} company reviews")
    return reviews_data

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
