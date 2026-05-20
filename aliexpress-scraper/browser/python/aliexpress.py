"""AliExpress scraper using the official Scrapeless Python SDK + Playwright over CDP.
the function names and emitted field names match verbatim.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List, Optional, TypedDict, Union
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from loguru import logger as log
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 180

# Localization cookie. cookie` so search /
# product responses come back in USD with the US site context.
LOCALE_COOKIE = "aep_usuc_f=site=glo&province=&city=&c_tp=USD&region=US&b_locale=en_US&ae_u_p_s=2"

class Product(TypedDict):
    info: Dict
    pricing: Dict
    specifications: List[Dict]
    delivery: Optional[str]
    faqs: List[Dict]

def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError(
            "SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com"
        )
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()

def _parse_locale_cookie() -> List[Dict[str, str]]:
    """Convert the LOCALE_COOKIE string into Playwright cookie dicts."""
    cookies: List[Dict[str, str]] = []
    for pair in LOCALE_COOKIE.split(";"):
        if "=" not in pair:
            continue
        name, _, value = pair.strip().partition("=")
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": ".aliexpress.com",
                "path": "/",
            }
        )
    return cookies

async def _fetch_rendered_html(
    url: str,
    ready_selector: Optional[str] = None,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 1,
    auto_scroll: bool = False,
) -> str:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
        )
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
            try:
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                try:
                    await context.add_cookies(_parse_locale_cookie())
                except Exception as e:
                    log.warning("could not set locale cookie: {}", e)
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=20000)
                    except Exception as e:
                        log.warning("wait_for_selector {!r} failed (continuing): {}", ready_selector, e)
                if auto_scroll:
                    try:
                        await page.evaluate(
                            "() => new Promise(r => { let y = 0; const i = setInterval(() => { window.scrollBy(0, 400); y += 400; if (y >= document.body.scrollHeight) { clearInterval(i); r(); } }, 100); })"
                        )
                        await page.wait_for_timeout(1500)
                    except Exception:
                        pass
                html = await page.content()
                if html:
                    return html
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

async def _fetch_json(url: str) -> Dict[str, Any]:
    html = await _fetch_rendered_html(url, ready_selector="pre")
    sel = Selector(text=html)
    raw = sel.css("pre::text").get() or html
    return json.loads(raw)

# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def add_or_replace_url_parameters(url: str, **params) -> str:
    parsed_url = urlparse(url)
    query_params = dict(parse_qsl(parsed_url.query))
    query_params.update({k: str(v) for k, v in params.items()})
    return urlunparse(parsed_url._replace(query=urlencode(query_params)))

def extract_search(html: str) -> Dict[str, Any]:
    """extract json data from search page (`_init_data_` JS variable)"""
    sel = Selector(text=html)
    script_with_data = sel.xpath('//script[contains(.,"_init_data_=")]')
    matches = script_with_data.re(r"_init_data_\s*=\s*{\s*data:\s*({.+}) }")
    if not matches:
        return {}
    data = json.loads(matches[0])
    return data.get("data", {}).get("root", {}).get("fields", {})

def parse_search(html: str) -> List[Dict[str, Any]]:
    """Parse search page response for product preview results"""
    data = extract_search(html)
    return data.get("mods", {}).get("itemList", {}).get("content", []) if data else []

async def scrape_search(url: str, max_pages: int = 60) -> List[Dict[str, Any]]:
    """Scrape all search results and return parsed search result data"""
    log.info("scraping search url {}", url)
    first_html = await _fetch_rendered_html(url, ready_selector="div[class*='card--gallery']")
    first_data = extract_search(first_html)
    page_size = first_data.get("pageInfo", {}).get("pageSize", 60) or 60
    total_results = first_data.get("pageInfo", {}).get("totalResults", 0)
    total_pages = int(math.ceil(total_results / page_size)) if page_size else 1
    if total_pages > max_pages:
        total_pages = max_pages

    product_previews = parse_search(first_html)
    log.info("search {} found {} pages", url, total_pages)
    for page in range(2, total_pages + 1):
        page_url = add_or_replace_url_parameters(url, page=page)
        page_html = await _fetch_rendered_html(page_url, ready_selector="div[class*='card--gallery']")
        product_previews.extend(parse_search(page_html))
    log.info("search {} scraped {} results", url, len(product_previews))
    return product_previews

# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

def _parse_count(text: Optional[str]) -> int:
    """Parse count strings like '100K', '1M', '1,000+', 'similar items', etc."""
    if not text:
        return 0
    text = text.replace(" sold", "").replace(" available", "").replace(",", "").replace("+", "").strip()
    text = text.split()[0] if text else ""
    if not text:
        return 0
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return 0

def parse_product(html: str, url: str) -> Product:
    """parse product HTML page for product data"""
    selector = Selector(text=html)
    reviews = selector.xpath("//a[contains(@class,'reviewer--reviews')]/text()").get()
    rate = selector.xpath("//div[contains(@class,'rating--wrap')]/div").getall()
    sold_count = selector.xpath(
        "//a[contains(@class, 'reviewer--sliderItem')]//span[contains(text(), 'sold')]/text()"
    ).get()
    available_count = selector.xpath(
        "//div[contains(@class,'quantity--info')]/div/span/text()"
    ).get()

    product_id_str = url.split("item/")[-1].split(".")[0] if "item/" in url else ""
    try:
        product_id_int = int(product_id_str)
    except ValueError:
        product_id_int = product_id_str  # type: ignore[assignment]

    info = {
        "name": selector.xpath("//h1[@data-pl]/text()").get(),
        "productId": product_id_int,
        "link": url,
        "media": selector.xpath("//div[contains(@class,'slider--img')]/img/@src").getall(),
        "rate": len(rate) if rate else None,
        "reviews": int(reviews.replace(" Reviews", "")) if reviews else None,
        "soldCount": _parse_count(sold_count),
        "availableCount": _parse_count(available_count),
    }
    price = selector.xpath("//span[contains(@class,'price-default--current')]/text()").get()
    original_price = selector.xpath("//span[contains(@class,'price-default--original')]//text()").get()
    discount = selector.xpath("//span[contains(@class,'price--discount')]/text()").get()
    pricing = {
        "priceCurrency": "USD $",
        "price": float(price.split("$")[-1]) if price else None,
        "originalPrice": float(original_price.split("$")[-1]) if original_price else "No discount",
        "discount": discount if discount else "No discount",
    }
    delivery = selector.xpath("(//div[@class='dynamic-shipping']//strong/text())[2]").get()

    specifications: List[Dict] = []
    for i in selector.xpath("//div[contains(@class,'specification--prop')]"):
        specifications.append(
            {
                "name": i.xpath(".//div[contains(@class,'specification--title')]/span/text()").get(),
                "value": i.xpath(".//div[contains(@class,'specification--desc')]/span/text()").get(),
            }
        )

    faqs: List[Dict] = []
    for i in selector.xpath("//div[@class='ask-list']/ul/li"):
        faqs.append(
            {
                "question": i.xpath(".//p[@class='ask-content']/span/text()").get(),
                "answer": i.xpath(".//ul[@class='answer-box']/li/p/text()").get(),
            }
        )

    return {
        "info": info,
        "pricing": pricing,
        "specifications": specifications,
        "delivery": delivery,
        "faqs": faqs,
    }

async def scrape_product(url: str) -> Product:
    """scrape aliexpress products by URL"""
    log.info("scraping product: {}", url)
    html = await _fetch_rendered_html(url, ready_selector="h1[data-pl]", auto_scroll=True)
    return parse_product(html, url)

# ---------------------------------------------------------------------------
# Product reviews (JSON API)
# ---------------------------------------------------------------------------

def parse_review_page(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = payload.get("data", {})
    return {
        "max_pages": data.get("totalPage", 1),
        "reviews": data.get("evaViewList", []),
        "evaluation_stats": data.get("productEvaluationStatistic", {}),
    }

async def scrape_product_reviews(product_id: Union[str, int], max_scrape_pages: Optional[int] = None) -> Dict[str, Any]:
    """scrape all reviews of an aliexpress product"""

    def url_for_page(page: int) -> str:
        return (
            "https://feedback.aliexpress.com/pc/searchEvaluation.do?"
            f"productId={product_id}&lang=en_US&country=US&page={page}&pageSize=10&filter=all&sort=complex_default"
        )

    first_payload = await _fetch_json(url_for_page(1))
    data = parse_review_page(first_payload)
    max_pages = data["max_pages"]
    if max_scrape_pages and max_scrape_pages < max_pages:
        max_pages = max_scrape_pages

    log.info(f"scraping reviews pagination of product {product_id}, {max(0, max_pages - 1)} pages remaining")
    for page in range(2, max_pages + 1):
        page_payload = await _fetch_json(url_for_page(page))
        data["reviews"].extend(parse_review_page(page_payload)["reviews"])

    log.success(f"scraped {len(data['reviews'])} from review pages")
    data.pop("max_pages", None)
    return data

# ---------------------------------------------------------------------------
# Category pages
# ---------------------------------------------------------------------------

def parse_category_page(html: str) -> Dict[str, Any]:
    selector = Selector(text=html)
    script_data = selector.xpath('//script[contains(.,"_init_data_=")]')
    matches = script_data.re(r"_init_data_\s*=\s*{\s*data:\s*({.+}) }")
    if not matches:
        return {"product_data": [], "total_pages": 1}
    json_data = json.loads(matches[0])["data"]["root"]["fields"]
    product_data = json_data.get("mods", {}).get("itemList", {}).get("content", [])
    total_results = json_data.get("pageInfo", {}).get("totalResults", 0)
    page_size = json_data.get("pageInfo", {}).get("pageSize", 60) or 60
    total_pages = int(math.ceil(total_results / page_size)) if page_size else 1
    return {"product_data": product_data, "total_pages": total_pages}

async def find_aliexpress_products(url: str, max_pages: Optional[int] = None) -> List[Dict]:
    """Find AliExpress products from category pages"""
    log.info(f"finding products from category page: {url}")
    first_html = await _fetch_rendered_html(url, ready_selector="body")
    first = parse_category_page(first_html)
    all_data: List[Dict] = list(first["product_data"])
    total_pages = max(1, first["total_pages"] - 1)
    if max_pages is None:
        max_pages = total_pages
    log.info(f"found {total_pages} pages, scraping {max_pages} pages")
    for page in range(2, max_pages + 1):
        page_html = await _fetch_rendered_html(f"{url}?page={page}", ready_selector="body")
        all_data.extend(parse_category_page(page_html)["product_data"])
    log.success(f"discovered {len(all_data)} products from {url}")
    return all_data

def to_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
