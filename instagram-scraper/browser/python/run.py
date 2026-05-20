"""Run the Instagram scrape functions live and optionally write results/*.json.

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

from instagram import (
    scrape_post,
    scrape_post_comments,
    scrape_user,
    scrape_user_posts,
    to_dict,
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
    sample_username = os.environ.get("INSTAGRAM_SAMPLE_USERNAME", "google")
    sample_post = os.environ.get("INSTAGRAM_SAMPLE_POST", "https://www.instagram.com/p/Cs9iEotsiGY/")
    sample_multi_image_post = os.environ.get(
        "INSTAGRAM_SAMPLE_MULTI_IMAGE_POST", "https://www.instagram.com/p/Csthn7EO99u/"
    )

    print(f"== user {sample_username} ==", file=sys.stderr)
    user = to_dict(await scrape_user(sample_username))
    save_or_print("user", user)

    print(f"== video-post {sample_post} ==", file=sys.stderr)
    post_video = to_dict(await scrape_post(sample_post))
    save_or_print("video-post", post_video)

    print(f"== multi-image-post {sample_multi_image_post} ==", file=sys.stderr)
    post_multi = to_dict(await scrape_post(sample_multi_image_post))
    save_or_print("multi-image-post", post_multi)

    print(f"== all-user-posts ({sample_username}) ==", file=sys.stderr)
    all_posts = []
    async for p in scrape_user_posts(sample_username, max_pages=3):
        all_posts.append(p)
    save_or_print("all-user-posts", all_posts)

    print("== post-comments ==", file=sys.stderr)
    comments = to_dict(await scrape_post_comments(post_video["id"], max_comments=100))
    save_or_print("post-comments", comments)


if __name__ == "__main__":
    asyncio.run(main())
