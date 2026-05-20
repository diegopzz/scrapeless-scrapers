"""G2 scraper using the official Scrapeless Python SDK + Playwright over CDP.
the function names and emitted field shapes match verbatim, so downstream code
can Public entry points:
- `scrape_search(url, max_scrape_pages=None)` -> product cards from `/search?query=...`
- `scrape_reviews(url, max_review_pages=None)` -> reviews from `/products/<slug>/reviews`
- `scrape_alternatives(product, alternatives="")` -> competitor list
"""

from __future__ import annotations

import math
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

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
    ready_selector: Optional[str] = None,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 1,
    auto_scroll: bool = False,
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
                if auto_scroll:
                    try:
                        await page.evaluate(
                            "async () => { await new Promise(r => { let y = 0; const t = setInterval(() => { window.scrollBy(0, 400); y += 400; if (y >= document.body.scrollHeight) { clearInterval(t); r(); } }, 100); }); }"
                        )
                    except Exception:
                        pass
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

def parse_search_page(html: str, base_url: str) -> Dict[str, Any]:
    """Parse product cards from G2 search pages."""
    sel = Selector(text=html)
    data: List[Dict[str, Any]] = []

    total_results_text = sel.xpath(
        "//div[contains(text(), 'Products')]/following-sibling::div/text()"
    ).get()
    total_results = 0
    if total_results_text:
        m = re.search(r"\((\d+)\)", total_results_text)
        if m:
            total_results = int(m.group(1))
    _search_page_size = 20
    total_pages = math.ceil(total_results / _search_page_size) if total_results else 0

    for result in sel.xpath("//section[.//a[contains(@href, '/products/')]]"):
        name = result.xpath(".//div[contains(@class, 'elv-text-lg')]/text()").get()
        relative_link = result.xpath(
            ".//div[contains(@class, 'elv-text-lg')]/parent::a/@href"
        ).get()
        link = urljoin(base_url, relative_link) if relative_link else None
        image = result.xpath(".//img[@alt='Product Avatar Image']/@src").get()
        raw_rate = result.xpath(".//label[contains(text(), '/5')]/text()").get()
        rate = float(raw_rate.split("/")[0]) if raw_rate else None
        raw_reviews = result.xpath(
            ".//a[contains(@href, '#reviews')]//label[not(contains(text(), '/5'))]/text()"
        ).get()
        reviews_number = int(raw_reviews.strip("()")) if raw_reviews else None
        description_parts = result.xpath(
            ".//div[div[contains(text(), 'Product Description')]]/p//text()"
        ).getall()
        description = "".join(description_parts).strip() if description_parts else None
        categories = result.xpath(
            ".//aside//div[contains(@class, 'elv-whitespace-nowrap')]/text()"
        ).getall()

        if not name:
            continue
        data.append(
            {
                "name": name.strip(),
                "link": link,
                "image": image,
                "rate": rate,
                "reviewsNumber": reviews_number,
                "description": description,
                "categories": [c.strip() for c in categories],
            }
        )
    return {"search_data": data, "total_pages": total_pages}

def parse_review_page(html: str) -> Dict[str, Any]:
    """Parse reviews from a G2 product reviews page."""
    sel = Selector(text=html)

    total_reviews_text = sel.xpath(
        "//a[contains(@href, '/reviews#reviews') and contains(text(), 'reviews')]/text()"
    ).get()
    if total_reviews_text:
        try:
            total_reviews = int(total_reviews_text.split()[2])
        except (IndexError, ValueError):
            total_reviews = 0
        _review_page_size = 10
        total_pages = math.ceil(total_reviews / _review_page_size) if total_reviews else 0
    else:
        total_pages = 0

    data: List[Dict[str, Any]] = []
    for review in sel.xpath("//article[.//div[@itemprop='reviewBody']]"):
        author_name = review.xpath(".//div[@itemprop='author']/meta[@itemprop='name']/@content").get()
        author_profile = review.xpath(".//div[contains(@class, 'avatar')]/parent::a/@href").get()
        author_details = review.xpath(
            ".//div[div[@itemprop='author']]//div[contains(@class, 'elv-text-subtle')]/text()"
        ).getall()
        author_position = author_details[0] if author_details else None
        author_company_size = next((d for d in author_details if "emp." in d), None)

        review_tags = review.xpath(
            ".//div[contains(@class, 'gap-3') and contains(@class, 'flex-wrap')]//label/text()"
        ).getall()
        review_date = review.xpath(".//meta[@itemprop='datePublished']/@content").get()
        review_rate = review.xpath(
            ".//span[@itemprop='reviewRating']/meta[@itemprop='ratingValue']/@content"
        ).get()
        review_title = review.xpath(".//div[@itemprop='name']//text()").get()

        likes_parts = review.xpath(
            ".//section[div[contains(text(), 'What do you like best')]]/p//text()"
        ).getall()
        review_likes = "".join(likes_parts).replace("Review collected by and hosted on G2.com.", "").strip()
        dislikes_parts = review.xpath(
            ".//section[div[contains(text(), 'What do you dislike')]]/p//text()"
        ).getall()
        review_dislikes = "".join(dislikes_parts).replace("Review collected by and hosted on G2.com.", "").strip()

        data.append(
            {
                "author": {
                    "authorName": author_name.strip() if author_name else None,
                    "authorProfile": author_profile,
                    "authorPosition": author_position.strip() if author_position else None,
                    "authorCompanySize": author_company_size.strip() if author_company_size else None,
                },
                "review": {
                    "reviewTags": [t.strip() for t in review_tags if t.strip()],
                    # NB: the upstream reference key is `reviewData` (sic) — preserved for parity.
                    "reviewData": review_date,
                    "reviewRate": float(review_rate) if review_rate else None,
                    "reviewTitle": review_title.replace('"', "").strip() if review_title else None,
                    "reviewLikes": review_likes,
                    "reviewDislikes": review_dislikes,
                },
            }
        )
    return {"total_pages": total_pages, "reviews_data": data}

def parse_alternatives(html: str) -> List[Dict[str, Any]]:
    """Parse alternative product cards from G2 alternative pages."""
    sel = Selector(text=html)
    data: List[Dict[str, Any]] = []
    for alt in sel.xpath("//div[@data-ordered-events-item='products']"):
        if alt.xpath(".//span[text()='Sponsored']").get():
            continue
        name = alt.xpath(
            ".//div[contains(@class, 'elv-text-lg') and contains(@class, 'elv-font-bold')]/text()"
        ).get()
        link = alt.xpath(".//a[contains(@href, '/products/')]/@href").get()
        if link and not link.startswith("http"):
            link = f"https://www.g2.com{link}"
        ranking = alt.xpath(".//meta[@itemprop='position']/@content").get()
        rating_text = alt.xpath(".//label[contains(@class, 'elv-font-semibold')]/text()").get()
        reviews_text = alt.xpath(".//label[contains(@class, 'elv-font-light')]/text()").get()

        number_of_reviews: Optional[int] = None
        if reviews_text:
            clean = reviews_text.strip("()").replace(",", "")
            try:
                number_of_reviews = int(clean)
            except ValueError:
                pass
        rate: Optional[float] = None
        if rating_text:
            try:
                rate = float(rating_text.split("/")[0])
            except (ValueError, IndexError):
                pass
        description = alt.xpath(".//p[contains(@class, 'elv-text-default')]/text()").get()

        if name:
            data.append(
                {
                    "name": name.strip(),
                    "link": link,
                    "ranking": int(ranking) if ranking else None,
                    "numberOfReviews": number_of_reviews,
                    "rate": rate,
                    "description": description.strip() if description else None,
                }
            )
    return data

# ---------------------------------------------------------------------------
# Scrape functions
# ---------------------------------------------------------------------------

async def scrape_search(url: str, max_scrape_pages: Optional[int] = None) -> List[Dict[str, Any]]:
    """Scrape product cards from G2 search results."""
    logger.info(f"scraping search page {url}")
    first_html = await _fetch_rendered_html(url, ready_selector="section a[href*='/products/']")
    data = parse_search_page(first_html, url)
    search_data = data["search_data"]
    total_pages = data["total_pages"]
    if max_scrape_pages and max_scrape_pages < total_pages:
        total_pages = max_scrape_pages

    logger.info(f"scraping search pagination, remaining ({max(total_pages - 1, 0)}) more pages")
    for page in range(2, total_pages + 1):
        page_url = f"{url}&page={page}"
        try:
            html = await _fetch_rendered_html(page_url, ready_selector="section a[href*='/products/']")
            search_data.extend(parse_search_page(html, page_url)["search_data"])
        except Exception as e:  # noqa: BLE001
            logger.error("error scraping {}: {}", page_url, e)
    return search_data

async def scrape_reviews(url: str, max_review_pages: Optional[int] = None) -> List[Dict[str, Any]]:
    """Scrape reviews from a G2 product reviews page."""
    logger.info(f"scraping first review page from company URL {url}")
    first_html = await _fetch_rendered_html(
        url, ready_selector="section#reviews article", auto_scroll=True
    )
    data = parse_review_page(first_html)
    reviews_data = data["reviews_data"]
    total_pages = data["total_pages"]
    if max_review_pages and max_review_pages < total_pages:
        total_pages = max_review_pages

    logger.info(f"scraping reviews pagination, remaining ({max(total_pages - 1, 0)}) more pages")
    for page in range(2, total_pages + 1):
        page_url = f"{url}?page={page}"
        try:
            html = await _fetch_rendered_html(
                page_url, ready_selector="section#reviews article", auto_scroll=True
            )
            reviews_data.extend(parse_review_page(html)["reviews_data"])
        except Exception as e:  # noqa: BLE001
            logger.error("error scraping {}: {}", page_url, e)
    logger.success(
        f"scraped {len(reviews_data)} company reviews from G2 review pages with the URL {url}"
    )
    return reviews_data

async def scrape_alternatives(product: str, alternatives: str = "") -> List[Dict[str, Any]]:
    """Scrape `top 10` (default) or segment-specific alternatives for a product."""
    url = f"https://www.g2.com/products/{product}/competitors/alternatives/{alternatives}"
    data: List[Dict[str, Any]] = []
    try:
        html = await _fetch_rendered_html(
            url, ready_selector="div[data-ordered-events-item='products']"
        )
        data = parse_alternatives(html)
    except Exception as e:  # noqa: BLE001
        logger.error("an exception occurred during scraping: {}", e)
    logger.success(f"Scraped {len(data)} company alternatives from G2 alternative pages")
    return data

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
