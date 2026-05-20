"""Immoscout24 (Swiss) scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names match verbatim.

Both surfaces extract from `window.__PINIA_INITIAL_STATE__`. the upstream reference returns
the nested JSON verbatim — Scrapeless mirrors it.
"""

from __future__ import annotations

import asyncio
import json
import os
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
    """ImmoScout24 (SIX-fronted) interstitial-gates direct deep-links from
    cold sessions; a homepage warm-up gets the session cookie first.
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
                        await page.goto(
                            "https://www.immoscout24.ch/",
                            wait_until="domcontentloaded",
                            timeout=30000,
                        )
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
                        "window.__PINIA_INITIAL_STATE__ || document.body.innerText.length > 5000",
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
# Pinia state extraction (bracket-depth matching — mirrors the upstream reference)
# ---------------------------------------------------------------------------

def _extract_pinia_state(html: str) -> Dict[str, Any] | None:
    sel = Selector(text=html)
    script_content = sel.xpath(
        "//script[contains(., 'window.__PINIA_INITIAL_STATE__')]/text()"
    ).get()
    if not script_content:
        return None
    idx = script_content.find("window.__PINIA_INITIAL_STATE__")
    start = script_content.find("{", idx)
    if start == -1:
        return None
    depth = 0
    end = start
    for i in range(start, len(script_content)):
        ch = script_content[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    json_str = script_content[start:end].replace("undefined", "null")
    try:
        return json.loads(json_str)
    except Exception as e:  # noqa: BLE001
        logger.warning("PINIA parse failed: {}", e)
        return None

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_property_page(html: str) -> Dict[str, Any]:
    data = _extract_pinia_state(html)
    if not data:
        return {}
    try:
        return data["listing"]["listing"]
    except (KeyError, TypeError):
        return {}

def parse_search_page(html: str) -> List[Dict[str, Any]]:
    """Each listing on the modern Immoscout24 SERP carries a schema.org
    `Product` JSON-LD block — the Pinia state isn't exposed on the window
    anymore. Fall back to JSON-LD when the legacy path returns nothing.
    """
    data = _extract_pinia_state(html)
    if data:
        try:
            legacy = data["resultList"]["search"]["fullSearch"]["result"]["listings"]
            if isinstance(legacy, list) and legacy:
                return legacy
        except (KeyError, TypeError):
            pass
    sel = Selector(text=html)
    out: List[Dict[str, Any]] = []
    for raw in sel.xpath('//script[@type="application/ld+json"]/text()').getall():
        try:
            node = json.loads(raw)
        except Exception:
            continue
        nodes = node if isinstance(node, list) else [node]
        for n in nodes:
            if not isinstance(n, dict):
                continue
            t = n.get("@type")
            types = t if isinstance(t, list) else [t]
            if "Product" not in types:
                continue
            name = str(n.get("name") or "")
            if "CHF" not in name.upper():
                continue
            offers = n.get("offers")
            offer = offers[0] if isinstance(offers, list) and offers else (offers if isinstance(offers, dict) else None)
            url = n.get("url")
            try:
                price = float(offer["price"]) if offer and "price" in offer else None
            except (TypeError, ValueError):
                price = None
            out.append({
                "id": url.rsplit("/", 1)[-1] if isinstance(url, str) else None,
                "name": name,
                "url": url,
                "image": n.get("image"),
                "description": n.get("description"),
                "price": price,
                "priceCurrency": offer.get("priceCurrency") if offer else None,
                "rawJsonLd": n,
            })
    return out

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_properties(urls: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for u in urls:
        html = await _fetch_rendered_html(
            u, ready_selector="script:has-text('__PINIA_INITIAL_STATE__')"
        )
        out.append(parse_property_page(html))
    return out

async def scrape_search(
    url: str,
    scrape_all_pages: bool = False,
    max_scrape_pages: int = 10,
) -> List[Dict[str, Any]]:
    first = await _fetch_rendered_html(
        url, ready_selector="script:has-text('__PINIA_INITIAL_STATE__')"
    )
    results = parse_search_page(first)

    # discover total pages
    data = _extract_pinia_state(first) or {}
    total_pages = 1
    try:
        total_pages = int(data["resultList"]["search"]["fullSearch"]["result"].get("numberOfPages", 1))
    except (KeyError, TypeError, ValueError):
        pass
    if not scrape_all_pages:
        total_pages = min(total_pages, max_scrape_pages)

    for page in range(2, total_pages + 1):
        sep = "&" if "?" in url else "?"
        page_url = f"{url}{sep}pn={page}"
        html = await _fetch_rendered_html(
            page_url, ready_selector="script:has-text('__PINIA_INITIAL_STATE__')"
        )
        page_items = parse_search_page(html)
        if not page_items:
            break
        results.extend(page_items)
    return results

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
