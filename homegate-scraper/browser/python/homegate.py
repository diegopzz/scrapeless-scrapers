"""Homegate scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names match verbatim.

- Property pages: regex-extract the JSON object after `window.__PINIA_INITIAL_STATE__ =`.
- Search pages: regex-extract the JSON object after `window.__INITIAL_STATE__ =`.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Dict, List

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

PROXY_COUNTRY = "CH"
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
    retries: int = 2,
    warmup: bool = True,
) -> str:
    """Homegate blocks direct deep-links from cold sessions; a homepage warm-up
    gets the session cookie so the listing URL renders.
    """
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
                if warmup:
                    try:
                        await page.goto("https://www.homegate.ch/", wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(3.5)
                    except Exception:
                        pass
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                try:
                    await page.wait_for_selector(ready_selector, timeout=20000)
                except Exception as e:
                    logger.warning("wait_for_selector failed (continuing): {}", e)
                try:
                    await page.wait_for_function(
                        "window.__INITIAL_STATE__ || document.body.innerText.length > 5000",
                        timeout=15000,
                    )
                except Exception:
                    pass
                html = await page.content()
                if html and len(html) > 20000:
                    return html
                last_error = RuntimeError("interstitial / short HTML")
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

def parse_property_page(html: str) -> Dict[str, Any] | None:
    sel = Selector(text=html)
    script = sel.xpath(
        "//script[contains(., 'window.__PINIA_INITIAL_STATE__')]/text()"
    ).get()
    if not script:
        return None
    m = re.search(r"window\.__PINIA_INITIAL_STATE__\s*=\s*(\{.+\})\s*$", script, re.DOTALL)
    if not m:
        # fallback: bracket-depth match
        idx = script.find("window.__PINIA_INITIAL_STATE__")
        start = script.find("{", idx)
        if start == -1:
            return None
        depth = 0
        end = start
        for i in range(start, len(script)):
            ch = script[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        json_str = script[start:end]
    else:
        json_str = m.group(1)
    json_str = json_str.replace("undefined", "null")
    try:
        data = json.loads(json_str)
        return data["listing"]["listing"]
    except Exception as e:  # noqa: BLE001
        logger.warning("PINIA parse failed: {}", e)
        return None

def parse_next_data(html: str) -> Dict[str, Any] | None:
    sel = Selector(text=html)
    next_data = sel.xpath(
        "//script[contains(text(), 'window.__INITIAL_STATE__')]/text()"
    ).get()
    if not next_data:
        return None
    try:
        return json.loads(next_data.split("=", 1)[1].strip())
    except Exception as e:  # noqa: BLE001
        logger.warning("INITIAL_STATE parse failed: {}", e)
        return None

def parse_search_listings(html: str) -> List[Dict[str, Any]]:
    data = parse_next_data(html)
    if not data:
        return []
    try:
        return data["resultList"]["search"]["fullSearch"]["result"]["listings"]
    except (KeyError, TypeError):
        return []

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

_READY = "script"

async def scrape_properties(urls: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for u in urls:
        html = await _fetch_rendered_html(u, ready_selector=_READY)
        parsed = parse_property_page(html)
        out.append(parsed if parsed is not None else {})
    return out

async def scrape_search(
    url: str,
    scrape_all_pages: bool = False,
    max_scrape_pages: int = 10,
) -> List[Dict[str, Any]]:
    first = await _fetch_rendered_html(url, ready_selector=_READY)
    results = parse_search_listings(first)

    data = parse_next_data(first) or {}
    total_pages = 1
    try:
        total_pages = int(data["resultList"]["search"]["fullSearch"]["result"].get("numberOfPages", 1))
    except (KeyError, TypeError, ValueError):
        pass
    if not scrape_all_pages:
        total_pages = min(total_pages, max_scrape_pages)

    for page in range(2, total_pages + 1):
        sep = "&" if "?" in url else "?"
        page_url = f"{url}{sep}ep={page}"
        html = await _fetch_rendered_html(page_url, ready_selector=_READY)
        page_items = parse_search_listings(html)
        if not page_items:
            break
        results.extend(page_items)
    return results

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
