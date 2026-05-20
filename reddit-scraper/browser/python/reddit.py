"""Reddit scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names match verbatim, so downstream code can
Reddit serves two HTML surfaces: `www.reddit.com` (new design, `shreddit-*`
custom elements) and `old.reddit.com` (Listing-of-Things, easy XPaths). The
scraper hits whichever one the upstream reference hits per function.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Literal, Optional

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

class _Response:
    """Minimal stand-in for the upstream reference's ScrapeApiResponse — wraps html + final URL."""

    def __init__(self, html: str, url: str):
        self.selector = Selector(text=html)
        self.context = {"url": url}

async def _fetch(url: str, *, wait_for_selector: Optional[str] = None, warmup: bool = True) -> _Response:
    """Open URL in a Scrapeless cloud browser, return _Response(html, final_url).

    Reddit aggressively challenges fresh sessions (network-security
    interstitial or JS challenge). A homepage warm-up gives Reddit a chance
    to drop a session cookie before the real navigation.
    """
    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=DEFAULT_PROXY_COUNTRY, session_ttl=DEFAULT_SESSION_TTL)
    )
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
        try:
            page = await browser.new_page()
            if warmup:
                try:
                    await page.goto("https://www.reddit.com/", wait_until="domcontentloaded", timeout=45000)
                    await asyncio.sleep(4)
                except Exception:
                    pass
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            if wait_for_selector:
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=15000)
                except Exception as e:
                    logger.warning("wait_for_selector failed: {}", e)
            final_url = page.url
            html = await page.content()
            return _Response(html, final_url)
        finally:
            try:
                await browser.close()
            except Exception:
                pass

def parse_subreddit(response: _Response) -> Dict:
    """parse article data from HTML"""
    selector = response.selector
    url = response.context["url"]
    info: Dict[str, Any] = {}
    info["id"] = url.split("/r")[-1].replace("/", "")
    info["description"] = selector.xpath("//shreddit-subreddit-header/@description").get()
    members_text = selector.xpath(
        "//faceplate-number[following-sibling::text()[contains(., 'members')]]/@number"
    ).get()
    weekly_active = selector.xpath("//shreddit-subreddit-header/@weekly-active-users").get()
    rank = selector.xpath("//strong[@id='position']/text()").get()
    info["rank"] = rank.strip() if rank else None
    info["members"] = (
        int(members_text) if members_text else (int(weekly_active) if weekly_active else None)
    )
    info["bookmarks"] = {}
    for item in selector.xpath("//div[faceplate-tracker[@source='community_menu']]/faceplate-tracker"):
        name = item.xpath(".//a/span/span/span/text()").get()
        link = item.xpath(".//a/@href").get()
        if name and link:
            info["bookmarks"][name] = link
    info["url"] = url
    post_data: List[Dict] = []
    for box in selector.xpath("//article[@data-post-id]"):
        link = box.xpath(".//a/@href").get()
        author = box.xpath(".//shreddit-post/@author").get()
        post_label = box.xpath(".//span[contains(@class, 'bg-tone-4')]/div/text()").get()
        upvotes = box.xpath(".//shreddit-post/@score").get()
        comment_count = box.xpath(".//shreddit-post/@comment-count").get()
        attachment_type = box.xpath(".//shreddit-post/@post-type").get()
        attachment_link: Optional[str] = None
        if attachment_type:
            if attachment_type == "image":
                attachment_link = box.xpath(".//img[contains(@class, 'media-lightbox-img')]/@src").get()
            elif attachment_type == "video":
                attachment_link = box.xpath(".//shreddit-player/@preview").get()
            elif attachment_type == "gallery":
                attachment_link = box.xpath(".//img[contains(@class, 'media-lightbox-img')]/@src").get()
            if not attachment_link:
                attachment_link = box.xpath(".//shreddit-post/@content-href").get()
        post_data.append(
            {
                "authorProfile": "https://www.reddit.com/user/" + author if author else None,
                "authorId": box.xpath(".//shreddit-post/@author-id").get(),
                "title": box.xpath("./@aria-label").get(),
                "link": "https://www.reddit.com" + link if link else None,
                "publishingDate": box.xpath(".//shreddit-post/@created-timestamp").get(),
                "postId": box.xpath(".//shreddit-post/@id").get(),
                "postLabel": post_label.strip() if post_label else None,
                "postUpvotes": int(upvotes) if upvotes else None,
                "commentCount": int(comment_count) if comment_count else None,
                "attachmentType": attachment_type,
                "attachmentLink": attachment_link,
            }
        )
    cursor_id = selector.xpath("//shreddit-post/@more-posts-cursor").get()
    return {"post_data": post_data, "info": info, "cursor": cursor_id}

async def scrape_subreddit(subreddit_id: str, max_pages: Optional[int] = None) -> Dict:
    """scrape articles on a subreddit"""
    base_url = f"https://www.reddit.com/r/{subreddit_id}/"
    response = await _fetch(base_url, wait_for_selector="shreddit-post")
    subreddit_data: Dict[str, Any] = {}
    data = parse_subreddit(response)
    subreddit_data["info"] = data["info"]
    subreddit_data["posts"] = data["post_data"]
    cursor = data["cursor"]

    def make_pagination_url(cursor_id: str) -> str:
        return (
            f"https://www.reddit.com/svc/shreddit/community-more-posts/hot/?after={cursor_id}%3D%3D"
            f"&t=DAY&name={subreddit_id}&feedLength=3"
        )

    while cursor and (max_pages is None or max_pages > 0):
        url = make_pagination_url(cursor)
        response = await _fetch(url)
        data = parse_subreddit(response)
        cursor = data["cursor"]
        subreddit_data["posts"].extend(data["post_data"])
        if max_pages is not None:
            max_pages -= 1
    logger.success(f"scraped {len(subreddit_data['posts'])} posts from the rubreddit: r/{subreddit_id}")
    return subreddit_data

def parse_post_info(response: _Response) -> Dict:
    """parse post data from a subreddit post"""
    selector = response.selector
    info: Dict[str, Any] = {}
    label = selector.xpath("//faceplate-tracker[@source='post']/a/span/div/text()").get()
    comments = selector.xpath("//shreddit-post/@comment-count").get()
    upvotes = selector.xpath("//shreddit-post/@score").get()
    info["authorId"] = selector.xpath("//shreddit-post/@author-id").get()
    info["author"] = selector.xpath("//shreddit-post/@author").get()
    info["authorProfile"] = (
        "https://www.reddit.com/user/" + info["author"] if info["author"] else None
    )
    subreddit_pn = selector.xpath("//shreddit-post/@subreddit-prefixed-name").get() or ""
    info["subreddit"] = subreddit_pn.replace("r/", "")
    info["postId"] = selector.xpath("//shreddit-post/@id").get()
    info["postLabel"] = label.strip() if label else None
    info["publishingDate"] = selector.xpath("//shreddit-post/@created-timestamp").get()
    info["postTitle"] = selector.xpath("//shreddit-post/@post-title").get()
    info["postLink"] = selector.xpath("//shreddit-canonical-url-updater/@value").get()
    info["commentCount"] = int(comments) if comments else None
    info["upvoteCount"] = int(upvotes) if upvotes else None
    info["attachmentType"] = selector.xpath("//shreddit-post/@post-type").get()
    info["attachmentLink"] = selector.xpath("//shreddit-post/@content-href").get()
    return info

def parse_post_comments(response: _Response) -> List[Dict]:
    """parse post comments (old.reddit nested listing)"""

    def parse_comment(parent_selector) -> Dict:
        author = parent_selector.xpath("./@data-author").get()
        link = parent_selector.xpath("./@data-permalink").get()
        dislikes = parent_selector.xpath(".//span[contains(@class, 'dislikes')]/@title").get()
        upvotes = parent_selector.xpath(".//span[contains(@class, 'likes')]/@title").get()
        downvotes = parent_selector.xpath(".//span[contains(@class, 'unvoted')]/@title").get()
        return {
            "authorId": parent_selector.xpath("./@data-author-fullname").get(),
            "author": author,
            "authorProfile": "https://www.reddit.com/user/" + author if author else None,
            "commentId": parent_selector.xpath("./@data-fullname").get(),
            "link": "https://www.reddit.com" + link if link else None,
            "publishingDate": parent_selector.xpath(".//time/@datetime").get(),
            "commentBody": parent_selector.xpath(".//div[@class='md']/p/text()").get(),
            "upvotes": int(upvotes) if upvotes else None,
            "dislikes": int(dislikes) if dislikes else None,
            "downvotes": int(downvotes) if downvotes else None,
        }

    def parse_replies(what) -> List[Dict]:
        replies = []
        for reply_box in what.xpath(".//div[@data-type='comment']"):
            reply_comment = parse_comment(reply_box)
            child_replies = parse_replies(reply_box)
            if child_replies:
                reply_comment["replies"] = child_replies
            replies.append(reply_comment)
        return replies

    selector = response.selector
    data: List[Dict] = []
    for item in selector.xpath("//div[@class='sitetable nestedlisting']/div[@data-type='comment']"):
        comment_data = parse_comment(item)
        replies = parse_replies(item)
        if replies:
            comment_data["replies"] = replies
        data.append(comment_data)
    return data

async def scrape_post(url: str, sort: Literal["old", "new", "top"]) -> Dict:
    """scrape subreddit post and comment data"""
    response = await _fetch(url, wait_for_selector="shreddit-post")
    post_data: Dict[str, Any] = {}
    post_data["info"] = parse_post_info(response)
    post_link = post_data["info"]["postLink"] or post_data["info"]["attachmentLink"]
    bulk_comments_page_url = post_link.replace("www", "old") + f"?sort={sort}&limit=500"
    response = await _fetch(bulk_comments_page_url)
    post_data["comments"] = parse_post_comments(response)
    logger.success(f"scraped {len(post_data['comments'])} comments from the post {url}")
    return post_data

def parse_user_posts(response: _Response) -> Dict:
    """Parse user posts from the new www.reddit.com user profile.

    Each post is wrapped in a `<shreddit-post>` custom element with metadata
    on attributes (author, score, comment-count, post-type, content-href, etc.).
    """
    selector = response.selector
    data: List[Dict] = []
    for sp in selector.xpath("//shreddit-post"):
        author = sp.xpath("./@author").get()
        permalink = sp.xpath("./@permalink").get()
        comment_count = sp.xpath("./@comment-count").get()
        post_score = sp.xpath("./@score").get()
        attachment_link = sp.xpath("./@content-href").get()
        if attachment_link and attachment_link.startswith("/"):
            attachment_link = "https://www.reddit.com" + attachment_link
        data.append(
            {
                "authorId": sp.xpath("./@author-id").get(),
                "author": author,
                "authorProfile": "https://www.reddit.com/user/" + author if author else None,
                "postId": sp.xpath("./@id").get(),
                "postLink": "https://www.reddit.com" + permalink if permalink else None,
                "postTitle": sp.xpath("./@post-title").get(),
                "postSubreddit": sp.xpath("./@subreddit-prefixed-name").get(),
                "publishingDate": sp.xpath("./@created-timestamp").get(),
                "commentCount": int(comment_count) if comment_count else None,
                "postScore": int(post_score) if post_score else None,
                "attachmentType": sp.xpath("./@post-type").get(),
                "attachmentLink": attachment_link,
            }
        )
    return {"data": data, "url": None}

async def scrape_user_posts(
    username: str,
    sort: Literal["new", "top", "controversial"],
    max_pages: Optional[int] = None,
) -> List[Dict]:
    """scrape user posts (modern www.reddit.com user profile)"""
    url = f"https://www.reddit.com/user/{username}/submitted/?sort={sort}"
    response = await _fetch(url, wait_for_selector="shreddit-post")
    post_data = parse_user_posts(response)["data"]
    logger.success(f"scraped {len(post_data)} posts from the {username} reddit profile")
    return post_data

def parse_user_comments(response: _Response) -> Dict:
    """Parse user comments from the new www.reddit.com user profile.

    Each comment is wrapped in `<shreddit-profile-comment>` with metadata on
    attributes and a thread context in the comment's `aria-label`
    ("Thread for <user>'s comment on <post title>").
    """
    import re as _re
    selector = response.selector
    data: List[Dict] = []
    for c in selector.xpath("//shreddit-profile-comment"):
        comment_id = c.xpath("./@comment-id").get()
        href = c.xpath("./@href").get()  # /r/<sub>/comments/<post>/comment/<id>/
        # Thread title sits in the inner anchor's aria-label.
        aria = c.xpath(".//a[contains(@aria-label, 'comment on')]/@aria-label").get() or ""
        post_title: Optional[str] = None
        post_author: Optional[str] = None
        m = _re.match(r"Thread for ([^']+)'s comment on (.+)", aria.strip())
        if m:
            post_author, post_title = m.group(1), m.group(2)
        # Comment body text.
        body = "".join(
            c.xpath(".//div[@id and starts-with(@id, 'comment') and @slot='comment']//text()").getall()
        ).strip()
        if not body:
            # Fallback: just pick the first paragraph.
            body = "".join(c.xpath(".//div[contains(@class, 'md')]//text()").getall()).strip()
        attached = [
            u for u in c.xpath(".//a[starts-with(@href, 'http')]/@href").getall()
            if u and "reddit.com" not in u
        ]
        # Parent subreddit + post link derived from `href` prefix.
        post_subreddit: Optional[str] = None
        post_link: Optional[str] = None
        if href:
            sm = _re.match(r"/r/([^/]+)/", href)
            if sm:
                post_subreddit = "r/" + sm.group(1)
            post_link = "https://www.reddit.com" + href.split("/comment/")[0] + "/"
        publishing_date = c.xpath(".//faceplate-timeago//time/@datetime").get() or c.xpath(".//time/@datetime").get()
        data.append(
            {
                "authorId": None,
                "author": None,  # backfilled by caller from `username`
                "authorProfile": None,
                "commentId": comment_id,
                "commentLink": "https://www.reddit.com" + href if href else None,
                "commentBody": body,
                "attachedCommentLinks": attached,
                "publishingDate": publishing_date,
                "dislikes": None,
                "upvotes": None,
                "downvotes": None,
                "replyTo": {
                    "postTitle": post_title,
                    "postLink": post_link,
                    "postAuthor": post_author,
                    "postSubreddit": post_subreddit,
                },
            }
        )
    return {"data": data, "url": None}

async def scrape_user_comments(
    username: str,
    sort: Literal["new", "top", "controversial"],
    max_pages: Optional[int] = None,
) -> List[Dict]:
    """scrape user comments (modern www.reddit.com user profile)"""
    url = f"https://www.reddit.com/user/{username}/comments/?sort={sort}"
    response = await _fetch(url, wait_for_selector="shreddit-profile-comment")
    post_data = parse_user_comments(response)["data"]
    for c in post_data:
        c["author"] = username
        c["authorProfile"] = f"https://www.reddit.com/user/{username}"
    logger.success(f"scraped {len(post_data)} comments from the {username} reddit profile")
    return post_data

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
