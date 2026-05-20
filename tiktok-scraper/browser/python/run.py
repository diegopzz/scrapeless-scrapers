"""Run the TikTok scrape functions live and optionally write results/*.json.

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

from tiktok import (
    scrape_channel,
    scrape_comments,
    scrape_posts,
    scrape_profiles,
    scrape_search,
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
    sample_post = os.environ.get(
        "TIKTOK_SAMPLE_POST", "https://www.tiktok.com/@oddanimalspecimens/video/7198206283571285294"
    )
    sample_profile = os.environ.get(
        "TIKTOK_SAMPLE_PROFILE", "https://www.tiktok.com/@oddanimalspecimens"
    )
    sample_query = os.environ.get("TIKTOK_SAMPLE_QUERY", "whales")

    print("== posts ==", file=sys.stderr)
    save_or_print("posts", to_dict(await scrape_posts(urls=[sample_post])))

    print("== comments ==", file=sys.stderr)
    save_or_print("comments", to_dict(await scrape_comments(post_url=sample_post)))

    print("== profiles ==", file=sys.stderr)
    save_or_print("profiles", to_dict(await scrape_profiles(urls=[sample_profile])))

    print(f"== search {sample_query!r} ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(keyword=sample_query)))

    print(f"== channel {sample_profile} ==", file=sys.stderr)
    save_or_print("channel", to_dict(await scrape_channel(url=sample_profile)))


if __name__ == "__main__":
    asyncio.run(main())
