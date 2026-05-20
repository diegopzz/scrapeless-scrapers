"""TikTok scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names match verbatim, so downstream code can
TikTok aggressively fingerprints clients. Scrapeless's cloud browser already
ships with anti-detection defaults; for stubborn pages prefer extending
`session_ttl` over reducing wait times.

Approach mirrors the upstream reference:
- Post + profile pages: read the hidden `__UNIVERSAL_DATA_FOR_REHYDRATION__`
  script tag.
- Comments / search / channel: render the page, scroll, and capture the
  matching XHR JSON bodies via Playwright's response listener.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import jmespath
from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "AU"  # the upstream reference default; TikTok ranks better via AU residential
DEFAULT_SESSION_TTL = 300  # TikTok needs a longer-lived session for scroll-triggered XHRs

def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError(
            "SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com"
        )
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()

class _Response:
    """Minimal stand-in for the upstream reference's ScrapeApiResponse — wraps html + captured XHRs."""

    def __init__(self, html: str, xhr_calls: List[Dict]):
        self.selector = Selector(text=html)
        self.scrape_result = {"browser_data": {"xhr_call": xhr_calls}}

async def _render(
    url: str,
    *,
    wait_for_selector: Optional[str] = None,
    auto_scroll: bool = False,
    pre_actions=None,
    rendering_wait_ms: int = 0,
) -> _Response:
    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=DEFAULT_PROXY_COUNTRY, session_ttl=DEFAULT_SESSION_TTL)
    )
    xhr_calls: List[Dict] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
        try:
            page = await browser.new_page()

            async def on_response(resp):
                try:
                    if resp.request.resource_type in ("xhr", "fetch"):
                        body_text: Optional[str] = None
                        try:
                            body_text = await resp.text()
                        except Exception:
                            body_text = None
                        xhr_calls.append({"url": resp.url, "response": {"body": body_text}})
                except Exception:
                    pass

            page.on("response", on_response)
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            if wait_for_selector:
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=15000)
                except Exception as e:
                    logger.warning("wait_for_selector failed: {}", e)
            if pre_actions:
                try:
                    await pre_actions(page)
                except Exception as e:
                    logger.warning("pre_actions failed: {}", e)
            if auto_scroll:
                # scroll up to 10 times with 3s pause between, stop early at end
                for _ in range(10):
                    height_before = await page.evaluate("document.body.scrollHeight")
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(3.0)
                    height_after = await page.evaluate("document.body.scrollHeight")
                    if height_after <= height_before + 10:
                        break
            if rendering_wait_ms:
                await asyncio.sleep(rendering_wait_ms / 1000.0)
            html = await page.content()
            return _Response(html, xhr_calls)
        finally:
            try:
                await browser.close()
            except Exception:
                pass

def parse_post(response: _Response) -> Dict:
    """parse hidden post data from HTML"""
    selector = response.selector
    data = selector.xpath("//script[@id='__UNIVERSAL_DATA_FOR_REHYDRATION__']/text()").get()
    post_data = json.loads(data)["__DEFAULT_SCOPE__"]["webapp.video-detail"]["itemInfo"]["itemStruct"]
    return jmespath.search(
        """{
        id: id,
        desc: desc,
        createTime: createTime,
        video: video.{duration: duration, ratio: ratio, cover: cover, playAddr: playAddr, downloadAddr: downloadAddr, bitrate: bitrate},
        author: author.{id: id, uniqueId: uniqueId, nickname: nickname, avatarLarger: avatarLarger, signature: signature, verified: verified},
        stats: stats,
        locationCreated: locationCreated,
        diversificationLabels: diversificationLabels,
        suggestedWords: suggestedWords,
        contents: contents[].{textExtra: textExtra[].{hashtagName: hashtagName}}
        }""",
        post_data,
    )

async def scrape_posts(urls: List[str]) -> List[Dict]:
    """scrape tiktok posts data from their URLs"""
    out: List[Dict] = []
    for url in urls:
        response = await _render(
            url, wait_for_selector="#__UNIVERSAL_DATA_FOR_REHYDRATION__"
        )
        out.append(parse_post(response))
    logger.success(f"scraped {len(out)} posts from post pages")
    return out

def parse_comments(response: _Response) -> List[Dict]:
    """parse comments data from the API response"""
    data = None
    for xhr in response.scrape_result["browser_data"]["xhr_call"]:
        if "/api/comment/list/" not in xhr["url"] or not xhr["response"]["body"]:
            continue
        try:
            data = json.loads(xhr["response"]["body"])
            break
        except Exception:
            continue
    if not data:
        raise Exception("Comment XHR data not found")
    parsed: List[Dict] = []
    for comment in data.get("comments") or []:
        parsed.append(
            jmespath.search(
                """{
                text: text,
                comment_language: comment_language,
                digg_count: digg_count,
                reply_comment_total: reply_comment_total,
                author_pin: author_pin,
                create_time: create_time,
                cid: cid,
                nickname: user.nickname,
                unique_id: user.unique_id,
                aweme_id: aweme_id
                }""",
                comment,
            )
        )
    return parsed

async def scrape_comments(post_url: str) -> List[Dict]:
    """scrape comments from tiktok posts by triggering the comment XHR"""

    async def click_comment_icon(page):
        try:
            await page.wait_for_selector("span[data-e2e='comment-icon']", timeout=5000)
            await page.click("span[data-e2e='comment-icon']")
            await page.wait_for_selector("div.TUXTabBar", timeout=5000)
        except Exception as e:
            logger.warning("comment icon click failed: {}", e)
        await asyncio.sleep(7.0)

    response = await _render(post_url, pre_actions=click_comment_icon, rendering_wait_ms=5000)
    data = parse_comments(response)
    logger.success(f"scraped {len(data)} comments from the post with the URL {post_url}")
    return data

def parse_profile(response: _Response) -> Dict:
    """parse profile data from hidden scripts on the HTML"""
    selector = response.selector
    data = selector.xpath("//script[@id='__UNIVERSAL_DATA_FOR_REHYDRATION__']/text()").get()
    return json.loads(data)["__DEFAULT_SCOPE__"]["webapp.user-detail"]["userInfo"]

async def scrape_profiles(urls: List[str]) -> List[Dict]:
    """scrape tiktok profiles data from their URLs"""
    out: List[Dict] = []
    for url in urls:
        response = await _render(
            url, wait_for_selector="#__UNIVERSAL_DATA_FOR_REHYDRATION__"
        )
        out.append(parse_profile(response))
    logger.success(f"scraped {len(out)} profiles from profile pages")
    return out

def parse_search(response: _Response) -> List[Dict]:
    """parse search data from XHR calls"""
    search_data: List[Dict] = []
    for c in response.scrape_result["browser_data"]["xhr_call"]:
        if "/api/search/general/full/" not in c["url"] or not c["response"]["body"]:
            continue
        try:
            data = json.loads(c["response"]["body"])["data"]
            search_data.extend(data)
        except Exception as e:
            logger.error(f"Failed to parse search data from XHR call: {e}")
    parsed: List[Dict] = []
    for item in search_data:
        if item.get("type") == 1:
            result = jmespath.search(
                """{
                id: id,
                desc: desc,
                createTime: createTime,
                video: video,
                author: author,
                stats: stats,
                authorStats: authorStats
                }""",
                item["item"],
            )
            result["type"] = item["type"]
            parsed.append(result)
    return parsed

async def scrape_search(keyword: str) -> List[Dict]:
    """scrape tiktok search data by scrolling the search page"""
    url = f"https://www.tiktok.com/search?q={quote(keyword)}"
    logger.info(f"scraping search page with the URL {url} for search data")
    response = await _render(
        url,
        wait_for_selector="div[data-e2e='search_top-item']",
        auto_scroll=True,
        rendering_wait_ms=15000,
    )
    data = parse_search(response)
    logger.success(f"scraped {len(data)} search results for keyword: {keyword}")
    return data

def parse_channel(response: _Response) -> List[Dict]:
    """parse channel video data from XHR calls"""
    channel_data: List[Dict] = []
    for c in response.scrape_result["browser_data"]["xhr_call"]:
        if "/api/post/item_list/" not in c["url"] or not c["response"]["body"]:
            continue
        try:
            data = json.loads(c["response"]["body"])["itemList"]
            channel_data.extend(data)
        except Exception:
            raise Exception("Post data couldn't load")
    parsed: List[Dict] = []
    for post in channel_data:
        parsed.append(
            jmespath.search(
                """{
                createTime: createTime,
                desc: desc,
                id: id,
                stats: stats,
                contents: contents[].{desc: desc, textExtra: textExtra[].{hashtagName: hashtagName}}
                }""",
                post,
            )
        )
    return parsed

async def scrape_channel(url: str) -> List[Dict]:
    """scrape video data from a channel (profile with videos)"""
    logger.info(f"scraping channel page with the URL {url} for post data")
    response = await _render(url, auto_scroll=True, rendering_wait_ms=15000)
    data = parse_channel(response)
    logger.success(f"scraped {len(data)} posts data")
    return data

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
