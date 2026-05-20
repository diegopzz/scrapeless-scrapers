"""eBay scraper using the official Scrapeless Python SDK + Playwright over CDP.
the function names and emitted field names match verbatim.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from loguru import logger as log
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 240
HOME = "https://www.ebay.com/"

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
    ready_selector: Optional[str] = None,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 2,
) -> str:
    """eBay is fronted by Akamai Bot Manager; warm up each session at the homepage
    so Akamai issues a session cookie before navigating to the target URL.
    """
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
        )
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
            try:
                page = await browser.new_page()
                await page.set_extra_http_headers({"accept-language": "en-US,en;q=0.9"})
                await page.goto(HOME, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(3500)
                try:
                    await page.evaluate("window.scrollBy(0, 600)")
                except Exception:
                    pass
                await page.wait_for_timeout(1500)
                await page.goto(url, wait_until="domcontentloaded", timeout=60000, referer=HOME)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=20000)
                    except Exception as e:
                        log.warning("wait_for_selector {!r} failed (continuing): {}", ready_selector, e)
                html = await page.content()
                title = await page.title()
                blocked = title == "Access Denied" or "Access Denied" in html[:2000]
                if blocked:
                    last_error = RuntimeError("blocked by Akamai (Access Denied)")
                elif html:
                    return html
                else:
                    last_error = RuntimeError("empty HTML")
            except Exception as e:  # noqa: BLE001
                last_error = e
                log.warning("attempt {} failed: {}", attempt + 1, e)
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
    raise RuntimeError(f"giving up after {retries + 1} attempts: {last_error}")

# ---------------------------------------------------------------------------
# Variants — parse the MSKU JS blob
# ---------------------------------------------------------------------------

def _find_json_objects(text: str, decoder=json.JSONDecoder()):
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

def _nested_lookup(key: str, document: Any) -> List[Any]:
    """Mini reimplementation of nested_lookup to avoid an extra dep."""
    out: List[Any] = []

    def _walk(d):
        if isinstance(d, dict):
            for k, v in d.items():
                if k == key:
                    out.append(v)
                _walk(v)
        elif isinstance(d, list):
            for v in d:
                _walk(v)

    _walk(document)
    return out

def parse_variants(html: str) -> List[Dict]:
    """Parse variant data from eBay's listing page (data lives in a JS MSKU blob)."""
    sel = Selector(text=html)
    script = sel.xpath('//script[contains(., "MSKU")]/text()').get()
    if not script:
        return []
    all_data = list(_find_json_objects(script))
    msku_data = _nested_lookup("MSKU", all_data)
    if not msku_data:
        return []
    data = msku_data[0]
    selection_names = {}
    for menu in data.get("selectMenus", []):
        for id_ in menu.get("menuItemValueIds", []):
            selection_names[id_] = menu.get("displayLabel")
    selections = []
    for v in data.get("menuItemMap", {}).values():
        selections.append(
            {
                "name": v.get("valueName"),
                "variants": v.get("matchingVariationIds", []),
                "label": selection_names.get(v.get("valueId")),
            }
        )
    results: List[Dict] = []
    variant_data_lookup = _nested_lookup("variationsMap", data)
    if not variant_data_lookup:
        return []
    variant_data = variant_data_lookup[0]
    for id_, variant in variant_data.items():
        item: Dict[str, Any] = defaultdict(list)
        item["id"] = id_
        for selection in selections:
            try:
                if int(id_) in selection["variants"]:
                    item[selection["label"]] = selection["name"]
            except (TypeError, ValueError):
                pass
        price_val = variant.get("binModel", {}).get("price", {}).get("value", {})
        item["price_original"] = price_val.get("convertedFromValue", price_val.get("value"))
        item["price_original_currency"] = price_val.get("convertedFromCurrency", price_val.get("currency"))
        item["price_converted"] = price_val.get("value")
        item["price_converted_currency"] = price_val.get("currency")
        item["out_of_stock"] = variant.get("quantity", {}).get("outOfStock")
        results.append(dict(item))
    return results

# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

def parse_product(html: str) -> Dict:
    """Parse eBay's product listing page for core product data."""
    sel = Selector(text=html)
    css_join = lambda c: "".join(sel.css(c).getall()).strip()
    css = lambda c: sel.css(c).get("").strip()

    item: Dict[str, Any] = {}
    item["url"] = css('link[rel="canonical"]::attr(href)')
    try:
        item["id"] = item["url"].split("/itm/")[1].split("?")[0]
    except Exception:
        item["id"] = ""
    item["price_original"] = css(".x-price-primary>span::text") or None
    item["price_converted"] = css(".x-price-approx__price ::text") or None
    item["name"] = css_join("h1 span::text")
    item["seller_name"] = sel.xpath("//div[contains(@class,'info__about-seller')]/a/span/text()").get()
    seller_href = sel.xpath("//div[contains(@class,'info__about-seller')]/a/@href").get() or ""
    item["seller_url"] = seller_href.split("?")[0] if seller_href else None
    item["photos"] = sel.css('.ux-image-filmstrip-carousel-item.image img::attr("src")').getall()
    item["photos"].extend(sel.css('.ux-image-carousel-item.image img::attr("src")').getall())
    item["description_url"] = css("iframe#desc_ifr::attr(src)") or None

    feature_table = sel.css("div.ux-layout-section--features")
    features: Dict[str, str] = {}
    for feature in feature_table.css("dl.ux-labels-values"):
        label = "".join(feature.css(".ux-labels-values__labels-content > div > span::text").getall()).strip(":\n ")
        value = "".join(feature.css(".ux-labels-values__values-content > div > span *::text").getall()).strip(":\n ")
        if label:
            features[label] = value
    item["features"] = features
    return item

async def scrape_product(url: str) -> Dict:
    """Scrape ebay.com product listing page for product data."""
    log.info(f"scraping product: {url}")
    html = await _fetch_rendered_html(url, ready_selector="h1")
    product = parse_product(html)
    product["variants"] = parse_variants(html)
    return product

# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def _get_url_parameter(url: str, param: str, default: Optional[str] = None) -> Optional[str]:
    query_params = dict(parse_qsl(urlparse(url).query))
    return query_params.get(param) or default

def _update_url_param(url: str, **params) -> str:
    parsed_url = urlparse(url)
    query_params = dict(parse_qsl(parsed_url.query))
    query_params.update({k: str(v) for k, v in params.items()})
    return urlunparse(parsed_url._replace(query=urlencode(query_params)))

def parse_search(html: str) -> List[Dict]:
    """Parse ebay.com search result page for product previews."""
    sel = Selector(text=html)
    previews: List[Dict] = []
    for box in sel.css("ul.srp-results li"):
        css = lambda c: (box.css(c).get("").strip() or None)
        location = box.xpath(".//*[contains(text(),'Located')]/text()").get()
        price = css(".s-card__price::text") or css(".s-item__price::text")
        url = css("a.s-card__link::attr(href)") or css("a.su-link::attr(href)")
        rating = box.xpath(".//span[contains(text(), 'positive')]/text()").get()

        if price is None:
            continue

        rating_count = None
        if rating:
            count_match = re.search(r"\(([\d.]+)K?\)", rating)
            if count_match:
                count_str = count_match.group(1)
                if "K)" in count_match.group(0):
                    rating_count = int(float(count_str) * 1000)
                else:
                    rating_count = int(count_str)

        previews.append(
            {
                "url": url.split("?")[0] if url else None,
                "title": css(".s-card__title span::text"),
                "price": css(".s-card__price::text") or css(".s-item__price::text"),
                "shipping": box.xpath(".//*[contains(text(),'delivery')]/text()").get(),
                "location": location.split("Located in ")[1] if location else None,
                "subtitles": css(".s-card__subtitle span::text"),
                "photo": css("img::attr(data-src)") or css("img::attr(src)"),
                "rating": re.search(r"[\d.]+%", rating).group() if rating and re.search(r"[\d.]+%", rating) else None,
                "rating_count": rating_count,
            }
        )
    return previews

async def scrape_search(url: str, max_pages: Optional[int] = None) -> List[Dict]:
    """Scrape eBay's search for product preview data."""
    log.info("Scraping search for {}", url)
    first_html = await _fetch_rendered_html(url, ready_selector="ul.srp-results")
    results = parse_search(first_html)

    sel = Selector(text=first_html)
    total_results_text = sel.css(".srp-controls__count-heading>span::text").get() or "0"
    try:
        total_results = int(total_results_text.replace(",", "").replace(".", ""))
    except ValueError:
        total_results = 0
    items_per_page = int(_get_url_parameter(url, "_ipg", default="60") or "60")
    total_pages = math.ceil(total_results / items_per_page) if items_per_page else 1
    if max_pages and total_pages > max_pages:
        total_pages = max_pages

    for i in range(2, total_pages + 1):
        page_url = _update_url_param(url, _pgn=i)
        page_html = await _fetch_rendered_html(page_url, ready_selector="ul.srp-results")
        try:
            results.extend(parse_search(page_html))
        except Exception as e:
            log.error(f"failed to parse search page {i}: {e}")
    return results

def to_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
