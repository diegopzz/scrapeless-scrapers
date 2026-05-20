"""Idealista scraper using the official Scrapeless Python SDK + Playwright over CDP.
Under the hood:
- `client.browser.create()` mints a cloud browser session, returning a CDP WS endpoint.
- Playwright connects over CDP, drives the page, returns rendered HTML.
- Parsel parses the HTML into dicts matching DATA_MODEL.md.

Idealista is aggressive about anti-bot, so we route through an ES proxy and wait
on stable selectors before reading the DOM.
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from typing import Any, Dict, List
from urllib.parse import urljoin

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

PROXY_COUNTRY = "ES"
DEFAULT_SESSION_TTL = 240
HOME = "https://www.idealista.com/"

# ---------------------------------------------------------------------------
# Scrapeless plumbing
# ---------------------------------------------------------------------------

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
    """Mint a session, goto, wait for stable marker, return HTML.

    Idealista is fronted by DataDome — cold IPs land on a captcha interstitial.
    Warming up the session at the homepage with Spanish locale lets DataDome
    issue a session cookie before we navigate to the target URL.
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
                await page.set_extra_http_headers({"accept-language": "es-ES,es;q=0.9,en;q=0.5"})
                if warmup:
                    try:
                        await page.goto(HOME, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(3000)
                    except Exception:
                        pass
                await page.goto(url, wait_until="domcontentloaded", timeout=60000, referer=HOME)
                try:
                    await page.wait_for_selector(ready_selector, timeout=20000)
                except Exception as e:
                    logger.warning("wait_for_selector failed (continuing): {}", e)
                html = await page.content()
                is_captcha = (
                    len(html) < 5000
                    and ("captcha-delivery.com" in html or "DataDome Device Check" in html)
                )
                if is_captcha:
                    last_error = RuntimeError("DataDome captcha interstitial")
                elif html:
                    return html
                else:
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
# Parsers — mirror the upstream reference's parse_* output dict keys verbatim
# ---------------------------------------------------------------------------

def parse_property(html: str, url: str) -> Dict[str, Any]:
    sel = Selector(text=html)
    css = lambda x: (sel.css(x).get() or "").strip()
    css_all = lambda x: sel.css(x).getall()

    data: Dict[str, Any] = {}
    data["url"] = url
    data["title"] = css("h1 .main-info__title-main::text")
    data["location"] = css(".main-info__title-minor::text")
    data["currency"] = css(".info-data-price::text")
    raw_price = css(".info-data-price span::text").replace(",", "")
    try:
        data["price"] = int(raw_price) if raw_price else 0
    except ValueError:
        data["price"] = 0
    data["description"] = "\n".join(css_all("div.comment ::text")).strip()
    data["updated"] = (
        sel.xpath("//p[@class='stats-text'][contains(text(),'updated on')]/text()").get("") or ""
    ).split(" on ")[-1]

    data["features"] = {}
    for feature_block in sel.css(".details-property-h2"):
        label = feature_block.xpath("text()").get()
        features = feature_block.xpath("following-sibling::div[1]//li")
        data["features"][label] = [
            "".join(feat.xpath(".//text()").getall()).strip() for feat in features
        ]

    images_by_tag: Dict[str, List[str]] = defaultdict(list)
    plans: List[str] = []
    match = re.search(r"fullScreenGalleryPics\s*:\s*(\[.+?\]),", html)
    if match:
        try:
            normalised = re.sub(r"(\w+?):([^/])", r'"\1":\2', match.group(1))
            images = json.loads(normalised)
            for image in images:
                full = urljoin(url, image.get("imageUrl", ""))
                if image.get("isPlan"):
                    plans.append(full)
                else:
                    images_by_tag[image.get("tag", "")].append(full)
        except Exception as e:  # noqa: BLE001
            logger.warning("image gallery parse failed: {}", e)
    data["images"] = dict(images_by_tag)
    data["plans"] = plans
    return data

def parse_search(html: str, base_url: str) -> List[Dict[str, Any]]:
    sel = Selector(text=html)
    out: List[Dict[str, Any]] = []
    for card in sel.css("article.item"):
        link_rel = card.css(".item-link::attr(href)").get() or ""
        title = (card.css(".item-link::attr(title)").get() or card.css(".item-link::text").get() or "").strip()
        price_text = (card.css(".item-price::text").get() or "").strip()
        currency = ""
        price_int = 0
        m = re.search(r"([\d.,]+)\s*([^\d\s]+)", price_text)
        if m:
            try:
                price_int = int(m.group(1).replace(".", "").replace(",", ""))
            except ValueError:
                price_int = 0
            currency = m.group(2)
        details = [d.strip() for d in card.css(".item-detail-char .item-detail::text").getall() if d.strip()]
        description = (card.css(".item-description ::text").get() or "").strip()
        tags = [t.strip() for t in card.css(".item-tags > *::text").getall() if t.strip()]
        listing_company = (card.css(".item-branding .logo-branding::attr(title)").get() or None)
        listing_company_url = card.css(".item-branding a::attr(href)").get()
        if listing_company_url:
            listing_company_url = urljoin(base_url, listing_company_url)
        picture = card.css(".item-multimedia img::attr(src)").get()
        out.append(
            {
                "title": title,
                "link": urljoin(base_url, link_rel),
                "picture": picture,
                "price": price_int,
                "currency": currency,
                "parking_included": "parking" in price_text.lower() or bool(card.css(".item-parking").get()),
                "details": details,
                "description": description,
                "tags": tags,
                "listing_company": listing_company,
                "listing_company_url": listing_company_url,
            }
        )
    return out

def parse_province(html: str, base_url: str) -> List[str]:
    sel = Selector(text=html)
    urls = sel.css("#location_list li>a::attr(href)").getall()
    return [urljoin(base_url, u) for u in urls]

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_properties(urls: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for url in urls:
        html = await _fetch_rendered_html(url, ready_selector="h1 .main-info__title-main")
        out.append(parse_property(html, url))
    return out

async def scrape_search(url: str, max_scrape_pages: int | None = None) -> List[Dict[str, Any]]:
    first_html = await _fetch_rendered_html(url, ready_selector="article.item")
    results = parse_search(first_html, url)

    # discover total pages via pagination links
    sel = Selector(text=first_html)
    page_links = sel.css(".pagination li a::attr(href)").getall()
    total_pages = 1
    for href in page_links:
        m = re.search(r"pagina-(\d+)", href)
        if m:
            total_pages = max(total_pages, int(m.group(1)))
    if max_scrape_pages:
        total_pages = min(total_pages, max_scrape_pages)

    for page in range(2, total_pages + 1):
        page_url = url.rstrip("/") + f"/pagina-{page}.htm"
        html = await _fetch_rendered_html(page_url, ready_selector="article.item")
        results.extend(parse_search(html, url))
    return results

async def scrape_provinces(urls: List[str]) -> List[str]:
    out: List[str] = []
    for url in urls:
        html = await _fetch_rendered_html(url, ready_selector="#location_list")
        out.extend(parse_province(html, url))
    return out

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
