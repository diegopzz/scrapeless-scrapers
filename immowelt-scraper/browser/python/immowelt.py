"""Immowelt scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names match verbatim.

Two embedded payloads:
- Search: a script tagged `classified-serp-init-data` carries a base64+LZ-String
  compressed JSON whose `pageProps.classifiedsData` holds the listings.
- Property: a script containing `UFRN_LIFECYCLE_SERVERREQUEST` carries the
  decoded payload; the upstream reference filters `{sections, id, brand, tags, contactSections}`.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

# lz-string is optional — only needed for search payloads
try:
    import lzstring  # type: ignore
except Exception:  # noqa: BLE001
    lzstring = None  # type: ignore

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
# Parsers
# ---------------------------------------------------------------------------

_SEARCH_KEYS = ("sections", "id", "brand", "tags", "contactSections")

def parse_search(html: str) -> List[Dict[str, Any]]:
    """Decode the `classified-serp-init-data` JSON.parse payload (LZ-String base64)."""
    sel = Selector(text=html)
    scripts = sel.xpath("//script/text()").getall()
    for script in scripts:
        if "classified-serp-init-data" not in script:
            continue
        m = re.search(r'JSON\.parse\("(.+?)"\)', script, re.DOTALL)
        if not m:
            continue
        try:
            inner = bytes(m.group(1), "utf-8").decode("unicode_escape")
            data = json.loads(inner)
            # Modern Immowelt embeds a GraphQL-response wrapper around the
            # LZ-String base64-encoded `classified-serp-init-data`. Older
            # builds used a `compressed` key at the root.
            payload_str = None
            if isinstance(data, dict):
                inner_data = data.get("data") if isinstance(data.get("data"), dict) else None
                if inner_data and isinstance(inner_data.get("classified-serp-init-data"), str):
                    payload_str = inner_data["classified-serp-init-data"]
                elif isinstance(data.get("compressed"), str):
                    payload_str = data["compressed"]
            if payload_str and lzstring:
                decompressed = lzstring.LZString().decompressFromBase64(payload_str)
                data = json.loads(decompressed)
            classifieds = data.get("pageProps", {}).get("classifiedsData")
            if classifieds is None:
                # sometimes nested differently
                classifieds = data.get("classifiedsData")
            if isinstance(classifieds, dict):
                return list(classifieds.values())
            if isinstance(classifieds, list):
                return classifieds
        except Exception as e:  # noqa: BLE001
            logger.warning("classifieds parse failed: {}", e)
    return []

def parse_property(html: str) -> Dict[str, Any]:
    """Decode the UFRN_LIFECYCLE_SERVERREQUEST payload and project the upstream reference's key subset."""
    sel = Selector(text=html)
    scripts = sel.xpath("//script/text()").getall()
    for script in scripts:
        if "UFRN_LIFECYCLE_SERVERREQUEST" not in script:
            continue
        m = re.search(r'JSON\.parse\("(.+?)"\)', script, re.DOTALL)
        if not m:
            continue
        try:
            inner = bytes(m.group(1), "utf-8").decode("unicode_escape")
            data = json.loads(inner)
        except Exception as e:  # noqa: BLE001
            logger.warning("property payload parse failed: {}", e)
            continue

        # walk the dict to find the listing object
        def find_listing(node):
            if isinstance(node, dict):
                if all(k in node for k in ("sections", "id")):
                    return node
                for v in node.values():
                    found = find_listing(v)
                    if found:
                        return found
            elif isinstance(node, list):
                for v in node:
                    found = find_listing(v)
                    if found:
                        return found
            return None

        listing = find_listing(data)
        if listing:
            return {k: listing.get(k) for k in _SEARCH_KEYS}
    return {}

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_search(url: str, max_scrape_pages: int | None = None) -> List[Dict[str, Any]]:
    first = await _fetch_rendered_html(url, ready_selector="body")
    results = parse_search(first)
    total_pages = 1
    sel = Selector(text=first)
    for href in sel.css("a[href*='page=']::attr(href)").getall():
        m = re.search(r"[?&]page=(\d+)", href)
        if m:
            total_pages = max(total_pages, int(m.group(1)))
    if max_scrape_pages:
        total_pages = min(total_pages, max_scrape_pages)

    for page in range(2, total_pages + 1):
        sep = "&" if "?" in url else "?"
        page_url = f"{url}{sep}page={page}"
        html = await _fetch_rendered_html(page_url, ready_selector="body")
        page_items = parse_search(html)
        if not page_items:
            break
        results.extend(page_items)
    return results

async def scrape_properties(urls: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for u in urls:
        html = await _fetch_rendered_html(u, ready_selector="body")
        out.append(parse_property(html))
    return out

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
