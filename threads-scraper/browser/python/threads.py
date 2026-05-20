"""Threads.net scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names match verbatim, so downstream code can
Public data only. Threads gates non-public surfaces (follows, DMs, settings)
behind login — out of scope, matching Under the hood: Threads embeds its server-rendered data in
`<script type="application/json" data-sjs>` tags. We render the page in a
Scrapeless cloud browser, then read the relevant scripts and walk them for
`thread_items` / `user` blobs the same way the upstream reference does.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, Optional

import jmespath
from loguru import logger
from nested_lookup import nested_lookup
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"  # Threads is not available in Europe
DEFAULT_SESSION_TTL = 180

def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError(
            "SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com"
        )
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()

async def _fetch_rendered(url: str, *, auto_scroll: bool = False, retries: int = 3):
    """Open `url` in a Scrapeless cloud browser, return (final_url, html)."""
    last_error: Optional[Exception] = None
    for _ in range(retries):
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=DEFAULT_PROXY_COUNTRY, session_ttl=DEFAULT_SESSION_TTL)
        )
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                if auto_scroll:
                    for _ in range(5):
                        await page.evaluate("window.scrollBy(0, window.innerHeight)")
                        await asyncio.sleep(1.0)
                final_url = page.url
                html = await page.content()
                if "/accounts/login" not in final_url:
                    return final_url, html
                last_error = RuntimeError(f"login wall: {final_url}")
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("threads fetch failed: {}", e)
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
    raise RuntimeError(f"encountered endless login requirement redirect loop - does the URL exist? {last_error}")

def parse_thread(data: Dict) -> Dict:
    """Parse Threads thread JSON dataset for the most important fields"""
    result = jmespath.search(
        """{
        text: post.caption.text,
        published_on: post.taken_at,
        id: post.id,
        pk: post.pk,
        code: post.code,
        username: post.user.username,
        user_pic: post.user.profile_pic_url,
        user_verified: post.user.is_verified,
        user_pk: post.user.pk,
        user_id: post.user.id,
        has_audio: post.has_audio,
        reply_count: post.text_post_app_info.direct_reply_count,
        like_count: post.like_count,
        images: post.carousel_media[].image_versions2.candidates[1].url,
        image_count: post.carousel_media_count,
        videos: post.video_versions[].url
    }""",
        data,
    )
    result["videos"] = list(set(result.get("videos") or []))
    result["url"] = f"https://www.threads.net/@{result['username']}/post/{result['code']}"
    result["image_count"] = len(result.get("images") or "")
    return result

def parse_profile(data: Dict) -> Dict:
    """Parse Threads profile JSON dataset for the most important fields"""
    result = jmespath.search(
        """{
        is_private: text_post_app_is_private,
        is_verified: is_verified,
        profile_pic: hd_profile_pic_versions[-1].url,
        username: username,
        full_name: full_name,
        bio: biography,
        bio_links: bio_links[].url,
        followers: follower_count
    }""",
        data,
    )
    result["url"] = f"https://www.threads.net/@{result['username']}"
    return result

async def scrape_thread(url: str) -> Dict:
    """
    Scrape a single thread page e.g.:
    https://www.threads.net/t/CuVdfsNtmvh/
    Returns parent thread and reply threads.
    """
    logger.info("scraping thread: {}", url)
    final_url, html = await _fetch_rendered(url)
    if "error=invalid_post" in final_url:
        logger.debug("post not found or deleted: {}", url)
        return {}

    selector = Selector(text=html)
    hidden_datasets = selector.css('script[type="application/json"][data-sjs]::text').getall()
    thread_hidden_data = [
        d for d in hidden_datasets if '"ScheduledServerJS"' in d and "thread_items" in d
    ]
    if not thread_hidden_data:
        raise ValueError("could not find thread data in page")
    data = json.loads(thread_hidden_data[-1])
    thread_items = nested_lookup("thread_items", data)
    threads = [parse_thread(t) for thread in thread_items for t in thread]
    return {"thread": threads[0], "replies": threads[1:]}

async def scrape_profile(url: str) -> Dict:
    """
    Scrapes a Threads user profile page e.g.:
    https://www.threads.net/@zuck
    returns user data and latest threads.
    """
    logger.info("scraping profile: {}", url)
    _final_url, html = await _fetch_rendered(url, auto_scroll=True)
    parsed: Dict[str, Any] = {"user": {}, "threads": []}
    selector = Selector(text=html)
    hidden_datasets = selector.css('script[type="application/json"][data-sjs]::text').getall()
    for hidden_dataset in hidden_datasets:
        if '"ScheduledServerJS"' not in hidden_dataset:
            continue
        is_profile = "follower_count" in hidden_dataset
        is_threads = "thread_items" in hidden_dataset
        if not is_profile and not is_threads:
            continue
        data = json.loads(hidden_dataset)
        if is_profile:
            user_data = nested_lookup("user", data)
            if user_data:
                parsed["user"] = parse_profile(user_data[0])
        if is_threads:
            thread_items = nested_lookup("thread_items", data)
            parsed["threads"].extend(
                parse_thread(t) for thread in thread_items for t in thread
            )
    return parsed

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
