"""Run the Reddit scrape functions live and optionally write results/*.json.

Usage:
    SCRAPELESS_API_KEY=sk_... python run.py
    SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true python run.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from reddit import (
    scrape_post,
    scrape_subreddit,
    scrape_user_comments,
    scrape_user_posts,
)

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

def save_or_print(name: str, payload) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if os.environ.get("SAVE_TEST_RESULTS", "").lower() == "true":
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out = RESULTS_DIR / f"{name}.json"
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}", file=sys.stderr)
    else:
        print(text)

async def main() -> None:
    sample_subreddit = os.environ.get("REDDIT_SAMPLE_SUBREDDIT", "wallstreetbets")
    sample_post_url = os.environ.get(
        "REDDIT_SAMPLE_POST_URL",
        "https://www.reddit.com/r/wallstreetbets/comments/1c4vwlp/what_are_your_moves_tomorrow_april_16_2024/",
    )
    sample_username = os.environ.get("REDDIT_SAMPLE_USERNAME", "spez")

    print(f"== subreddit r/{sample_subreddit} ==", file=sys.stderr)
    sub = await scrape_subreddit(subreddit_id=sample_subreddit, max_pages=3)
    save_or_print("subreddit", sub)

    print(f"== post {sample_post_url} ==", file=sys.stderr)
    post = await scrape_post(url=sample_post_url, sort="top")
    save_or_print("post", post)

    print(f"== user_posts {sample_username} ==", file=sys.stderr)
    user_posts = await scrape_user_posts(username=sample_username, sort="new", max_pages=3)
    save_or_print("user_posts", user_posts)

    print(f"== user_comments {sample_username} ==", file=sys.stderr)
    user_comments = await scrape_user_comments(username=sample_username, sort="new", max_pages=3)
    save_or_print("user_comments", user_comments)

if __name__ == "__main__":
    asyncio.run(main())
