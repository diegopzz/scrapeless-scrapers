"""SeLoger scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names match verbatim.

Two extraction techniques:
- search: DOM cards via `data-testid` attributes (parsel).
- property: decode JSON embedded in `window.__UFRN_LIFECYCLE_SERVERREQUEST__`.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List
from urllib.parse import urljoin

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

PROXY_COUNTRY = "FR"
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
# Parsers
# ---------------------------------------------------------------------------

def parse_search(html: str, base_url: str) -> List[Dict[str, Any]]:
    sel = Selector(text=html)
    out: List[Dict[str, Any]] = []
    cards = sel.xpath("//div[@data-testid='serp-core-classified-card-testid']")
    for card in cards:
        link = card.xpath(".//a[@data-testid='card-mfe-covering-link-testid']/@href").get() or ""
        title = card.xpath(".//a[@data-testid='card-mfe-covering-link-testid']/@title").get() or ""
        price = (
            card.xpath(".//div[contains(@data-testid, 'cardmfe-price')]/@aria-label").get()
            or "".join(card.xpath(".//div[contains(@data-testid, 'cardmfe-price')]//text()").getall())
        ).strip()
        price_per_m2 = card.xpath(".//div[contains(@data-testid, 'price-per-m2')]/text()").get()
        property_facts = [
            t.strip()
            for t in card.xpath(".//div[contains(@data-testid, 'description')]//text()").getall()
            if t.strip()
        ]
        address = "".join(
            card.xpath(".//div[contains(@data-testid, 'address')]//text()").getall()
        ).strip()
        agency = card.xpath(".//div[contains(@data-testid, 'agency')]//text()").get()
        images = card.xpath(".//img/@src").getall()
        out.append(
            {
                "title": title,
                "url": urljoin(base_url, link),
                "images": images,
                "price": price,
                "price_per_m2": price_per_m2,
                "property_facts": property_facts,
                "address": address,
                "agency": agency,
            }
        )
    return out

def parse_property(html: str) -> Dict[str, Any]:
    """Decode the bootstrap state and return {'classified': ...}."""
    sel = Selector(text=html)
    scripts = sel.xpath("//body/script/text()").getall()
    payload: Dict[str, Any] = {}
    for script in scripts:
        if "__UFRN_LIFECYCLE_SERVERREQUEST__" not in script:
            continue
        m = re.search(r'JSON\.parse\("(.+)"\)', script, re.DOTALL)
        if not m:
            continue
        try:
            raw = bytes(m.group(1), "utf-8").decode("unicode_escape")
            data = json.loads(raw)
            classified = data.get("app_cldp", {}).get("data", {}).get("classified")
            if classified is not None:
                payload = {"classified": classified}
                break
        except Exception as e:  # noqa: BLE001
            logger.warning("classified parse failed: {}", e)
    return payload

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_search(url: str, max_pages: int = 10) -> List[Dict[str, Any]]:
    first = await _fetch_rendered_html(
        url, ready_selector="div[data-testid='serp-core-classified-card-testid']"
    )
    results = parse_search(first, url)
    for page in range(2, max_pages + 1):
        sep = "&" if "?" in url else "?"
        page_url = f"{url}{sep}page={page}"
        html = await _fetch_rendered_html(
            page_url, ready_selector="div[data-testid='serp-core-classified-card-testid']"
        )
        page_items = parse_search(html, url)
        if not page_items:
            break
        results.extend(page_items)
    return results

async def scrape_property(urls: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for u in urls:
        html = await _fetch_rendered_html(u, ready_selector="body")
        out.append(parse_property(html))
    return out

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
