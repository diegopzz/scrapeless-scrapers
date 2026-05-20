"""Glassdoor scraper using the official Scrapeless Python SDK + Playwright over CDP.
the function names and emitted field shapes match verbatim, so downstream code
can Public entry points:
- `scrape_jobs(url, max_pages=None)` -> list of job cards
- `scrape_reviews(url, max_pages=None)` -> list of reviews via Glassdoor's bff API
- `scrape_salaries(url, max_pages=None)` -> salary payload
- `find_companies(query)` -> employer autocomplete
- `Url.jobs/reviews/salaries/overview/change_page(...)` URL helpers
- `Region` enum of glassdoor.com country ids
"""

from __future__ import annotations

import json
import os
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
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

async def _fetch_rendered(
    url: str,
    ready_selector: Optional[str] = None,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 1,
) -> Tuple[str, str]:
    """Return (html, final_url)."""
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
                final_url = page.url
                if html:
                    return html, final_url
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
    url: str, *, proxy_country: str = DEFAULT_PROXY_COUNTRY
) -> str:
    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
    )
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
        try:
            ctx = await browser.new_context()
            warm = await ctx.new_page()
            try:
                await warm.goto("https://www.glassdoor.com/", wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass
            response = await ctx.request.get(url)
            return await response.text()
        finally:
            try:
                await browser.close()
            except Exception:
                pass

async def _post_json(
    url: str,
    body: Dict[str, Any],
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
) -> str:
    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
    )
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
        try:
            ctx = await browser.new_context()
            warm = await ctx.new_page()
            try:
                await warm.goto("https://www.glassdoor.com/", wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass
            response = await ctx.request.post(
                url,
                data=json.dumps(body),
                headers={"content-type": "application/json"},
            )
            return await response.text()
        finally:
            try:
                await browser.close()
            except Exception:
                pass

# ---------------------------------------------------------------------------
# Hidden data extractor (Apollo cache)
# ---------------------------------------------------------------------------

def find_hidden_data(html: str, url: str = "") -> Optional[dict]:
    """Extract Apollo GraphQL hidden cache from Glassdoor page HTML.

    Either __NEXT_DATA__ JSON or inline `apolloState` JS variable.
    """
    sel = Selector(text=html)
    data = sel.css("script#__NEXT_DATA__::text").get()
    if data:
        try:
            data = json.loads(data)["props"]["pageProps"]["apolloCache"]
        except (KeyError, ValueError):
            return None
    else:
        m = re.search(r'apolloState":\s*({.+})};', html)
        if m:
            data = json.loads(m.group(1))
        else:
            logger.warning(f"Could not find __NEXT_DATA__ or apolloState on page {url}")
            return None

    def resolve_refs(node, root):
        if isinstance(node, dict):
            if "__ref" in node:
                return resolve_refs(root[node["__ref"]], root)
            return {k: resolve_refs(v, root) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve_refs(i, root) for i in node]
        return node

    if not data:
        return {}
    return resolve_refs(data.get("ROOT_QUERY") or data, data)

# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def parse_jobs(html: str, url: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    sel = Selector(text=html)
    job_data: List[Dict[str, Any]] = []
    for box in sel.xpath("//div[contains(@class, 'jobCard JobCard')]"):
        job_data.append(
            {
                "jobTitle": box.xpath(".//a/text()").get(),
                "jobLink": box.xpath(".//a/@href").get(),
                "job_location": box.xpath(".//div[@data-test='emp-location']/text()").get(),
                "jobSalary": box.xpath(".//div[@data-test='detailSalary']/text()").get(),
                "jobDate": box.xpath("//div[@data-test='job-age']/text()").get(),
            }
        )

    script_data = sel.xpath("//script[contains(text(), 'paginationLinks')]/text()").get()
    other_pages: List[str] = []
    if script_data:
        m = re.search(r'\\"paginationLinks\\":\s*(\[.*?\])\s*,\s*\\"searchResultsMetadata\\"', script_data)
        if m:
            unescaped = m.group(1).replace('\\"', '"').replace("\\u0026", "&")
            try:
                pagination_links = json.loads(unescaped)
                other_pages = [
                    urljoin(url, page["urlLink"])
                    for page in pagination_links
                    if page.get("isCurrentPage") is False
                ]
            except Exception:
                pass
    return job_data, other_pages

async def scrape_jobs(url: str, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
    logger.info("scraping job listings from {}", url)
    html, final_url = await _fetch_rendered(url, ready_selector="div[class*='jobCard']")
    jobs, other_page_urls = parse_jobs(html, final_url)
    total_pages = len(other_page_urls) + 1
    if max_pages and total_pages > max_pages:
        other_page_urls = other_page_urls[: max_pages - 1]
    logger.info("scraped first page of jobs of {}, scraping remaining {} pages", url, len(other_page_urls))
    for page_url in other_page_urls:
        try:
            html2, final2 = await _fetch_rendered(page_url, ready_selector="div[class*='jobCard']")
            jobs.extend(parse_jobs(html2, final2)[0])
        except Exception as e:  # noqa: BLE001
            logger.error("failed to scrape {}: {}", page_url, e)
    logger.info("scraped {} jobs from {}", len(jobs), url)
    return jobs

# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

def parse_reviews_api_metadata(html: str) -> Dict[str, int]:
    sel = Selector(text=html)
    script_data = sel.xpath("//script[contains(text(), 'profileId')]/text()").get()
    if not script_data:
        raise RuntimeError("reviews api metadata not found on page")
    employer_match = re.search(r'"employer"\s*:\s*(\{[^}]+\})', script_data)
    if not employer_match:
        raise RuntimeError("could not parse employer metadata")
    employer_metadata = json.loads(employer_match.group(1))
    return {
        "employer_id": int(employer_metadata["id"]),
        "dynamic_profile_id": int(employer_metadata["profileId"]),
    }

async def scrape_reviews(url: str, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
    def build_body(page_number: int) -> Dict[str, Any]:
        return {
            "applyDefaultCriteria": True,
            "employerId": metadata["employer_id"],
            "employmentStatuses": ["REGULAR", "PART_TIME"],
            "jobTitle": None,
            "goc": None,
            "location": {},
            "defaultLanguage": "eng",
            "language": "eng",
            "mlHighlightSearch": None,
            "onlyCurrentEmployees": False,
            "overallRating": None,
            "pageSize": 5,
            "page": page_number,
            "preferredTldId": 0,
            "reviewCategories": [],
            "sort": "DATE",
            "textSearch": "",
            "worldwideFilter": False,
            "dynamicProfileId": metadata["dynamic_profile_id"],
            "useRowProfileTldForRatings": True,
            "enableKeywordSearch": True,
        }

    logger.info("scraping reviews api requirements from {}", url)
    html, _ = await _fetch_rendered(url, ready_selector="script:has-text('profileId')")
    metadata = parse_reviews_api_metadata(html)

    api_url = "https://www.glassdoor.com/bff/employer-profile-mono/employer-reviews"
    first_text = await _post_json(api_url, build_body(1))
    first = json.loads(first_text)
    review_data: List[Dict[str, Any]] = list(first["data"]["employerReviews"]["reviews"])
    total_pages = first["data"]["employerReviews"]["numberOfPages"]
    if max_pages and max_pages < total_pages:
        total_pages = max_pages

    logger.info("scraping reviews pagination from {}, remaining {} pages", url, total_pages - 1)
    for page in range(2, total_pages + 1):
        try:
            text = await _post_json(api_url, build_body(page))
            page_data = json.loads(text)
            review_data.extend(page_data["data"]["employerReviews"]["reviews"])
        except Exception as e:  # noqa: BLE001
            logger.error("failed to scrape reviews page {}: {}", page, e)
    logger.info("scraped {} reviews from {}", len(review_data), url)
    return review_data

# ---------------------------------------------------------------------------
# Salaries
# ---------------------------------------------------------------------------

def parse_salaries(html: str) -> Dict[str, Any]:
    sel = Selector(text=html)
    salary_data: Dict[str, Any] = {"results": [], "numPages": 1, "salaryCount": 0, "jobTitleCount": 0}

    for item in sel.css('[data-test="salary-item"]'):
        job_title = item.css(".SalaryItem_jobTitle__XWGpT::text").get()
        if not job_title:
            continue
        salary_range = item.css(".SalaryItem_salaryRange__UL9vQ::text").get()
        salary_count_text = item.css(".SalaryItem_salaryCount__GT665::text").get() or ""
        salary_count = 0
        if "Salaries submitted" in salary_count_text:
            try:
                salary_count = int(salary_count_text.split()[0])
            except (ValueError, IndexError):
                pass
        entry: Dict[str, Any] = {
            "jobTitle": {"text": job_title},
            "salaryCount": salary_count,
            "basePayStatistics": {"percentiles": []},
        }
        if salary_range:
            range_clean = salary_range.replace("$", "").replace("K", "000")
            if " - " in range_clean:
                try:
                    min_str, max_str = range_clean.split(" - ")
                    min_salary = float(min_str.replace(",", ""))
                    max_salary = float(max_str.replace(",", ""))
                    entry["basePayStatistics"]["percentiles"] = [
                        {"ident": "min", "value": min_salary},
                        {"ident": "max", "value": max_salary},
                    ]
                except ValueError:
                    pass
        salary_data["results"].append(entry)

    page_links = sel.css(".pagination_PageNumberText__F7427::text").getall()
    if page_links:
        try:
            salary_data["numPages"] = max(int(p) for p in page_links if p.isdigit())
        except ValueError:
            pass
    count_text = sel.css(".SortBar_SearchCount__cYwt6::text").get() or ""
    if "job titles" in count_text:
        try:
            salary_data["jobTitleCount"] = int(count_text.split()[0].replace(",", ""))
        except (ValueError, IndexError):
            pass
    salary_data["salaryCount"] = len(salary_data["results"])
    return salary_data

async def scrape_salaries(url: str, max_pages: Optional[int] = None) -> Dict[str, Any]:
    logger.info("scraping salaries from {}", url)
    html, final_url = await _fetch_rendered(url, ready_selector='[data-test="salary-item"]')
    salaries = parse_salaries(html)
    total_pages = salaries["numPages"]
    if max_pages and total_pages > max_pages:
        total_pages = max_pages
    logger.info("scraped first page of salaries, remaining {} pages", total_pages - 1)
    for page in range(2, total_pages + 1):
        page_url = Url.change_page(final_url, page=page)
        try:
            html2, _ = await _fetch_rendered(page_url, ready_selector='[data-test="salary-item"]')
            salaries["results"].extend(parse_salaries(html2)["results"])
        except Exception as e:  # noqa: BLE001
            logger.error("failed to scrape {}: {}", page_url, e)
    salaries["salaryCount"] = len(salaries["results"])
    return salaries

# ---------------------------------------------------------------------------
# Find companies
# ---------------------------------------------------------------------------

async def find_companies(query: str) -> List[Dict[str, Any]]:
    """Resolve company name -> Glassdoor id via the autocomplete endpoint."""
    url = f"https://www.glassdoor.com/autocomplete/employers?term={query}"
    text = await _fetch_json(url)
    data = json.loads(text)
    return [
        {
            "name": result["label"],
            "id": result["id"],
            "shortName": result.get("shortName", ""),
            "logoURL": result.get("logoURL"),
            "websiteURL": result.get("websiteURL", ""),
        }
        for result in data
    ]

# ---------------------------------------------------------------------------
# URL helpers + region enum (mirror the upstream reference verbatim)
# ---------------------------------------------------------------------------

class Region(Enum):
    UNITED_STATES = "1"
    UNITED_KINGDOM = "2"
    CANADA_ENGLISH = "3"
    INDIA = "4"
    AUSTRALIA = "5"
    FRANCE = "6"
    GERMANY = "7"
    SPAIN = "8"
    BRAZIL = "9"
    NETHERLANDS = "10"
    AUSTRIA = "11"
    MEXICO = "12"
    ARGENTINA = "13"
    BELGIUM_NEDERLANDS = "14"
    BELGIUM_FRENCH = "15"
    SWITZERLAND_GERMAN = "16"
    SWITZERLAND_FRENCH = "17"
    IRELAND = "18"
    CANADA_FRENCH = "19"
    HONG_KONG = "20"
    NEW_ZEALAND = "21"
    SINGAPORE = "22"
    ITALY = "23"

class Url:
    @staticmethod
    def overview(employer: str, employer_id: str, region: Optional[Region] = None) -> str:
        employer = employer.replace(" ", "-")
        url = f"https://www.glassdoor.com/Overview/Working-at-{employer}-EI_IE{employer_id}"
        _start = url.split("/Overview/")[1].find(employer)
        _end = _start + len(employer)
        url += f".{_start},{_end}.htm"
        if region:
            return url + f"?filter.countryId={region.value}"
        return url

    @staticmethod
    def reviews(employer: str, employer_id: str, region: Optional[Region] = None) -> str:
        employer = employer.replace(" ", "-")
        url = f"https://www.glassdoor.com/Reviews/{employer}-Reviews-E{employer_id}.htm?"
        if region:
            return url + f"?filter.countryId={region.value}"
        return url

    @staticmethod
    def salaries(employer: str, employer_id: str, region: Optional[Region] = None) -> str:
        employer = employer.replace(" ", "-")
        url = f"https://www.glassdoor.com/Salary/{employer}-Salaries-E{employer_id}.htm?"
        if region:
            return url + f"?filter.countryId={region.value}"
        return url

    @staticmethod
    def jobs(employer: str, employer_id: str, region: Optional[Region] = None) -> str:
        employer = employer.replace(" ", "-")
        url = f"https://www.glassdoor.com/Jobs/{employer}-Jobs-E{employer_id}.htm?"
        if region:
            return url + f"?filter.countryId={region.value}"
        return url

    @staticmethod
    def change_page(url: str, page: int) -> str:
        if re.search(r"_P\d+\.htm", url):
            new = re.sub(r"(?:_P\d+)*.htm", f"_P{page}.htm", url)
        else:
            new = re.sub(".htm", f"_P{page}.htm", url)
        assert new != url
        return new

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
