"""Run the YouTube scrape functions live and optionally write results/*.json.

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

from youtube import (
    scrape_channel,
    scrape_channel_videos,
    scrape_comments,
    scrape_search,
    scrape_shorts,
    scrape_video,
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

SAMPLE_VIDEO_IDS = ["1Y-XvvWlyzk", "muo6I9XY8K4", "y7FbFJ4jOW8"]
SAMPLE_COMMENTS_VIDEO = "FgakZw6K1QQ"
SAMPLE_CHANNEL_HANDLE = "the upstream reference"
SAMPLE_CHANNEL_VIDEOS = "statquest"
SAMPLE_SEARCH_QUERY = "python"
SAMPLE_SEARCH_PARAMS = "EgQIAxAB"  # video-only filter
SAMPLE_SHORT_IDS = ["rZ2qqtNPSBk"]

async def main() -> None:
    print("== video ==", file=sys.stderr)
    save_or_print("video", await scrape_video(SAMPLE_VIDEO_IDS))

    print("== comments ==", file=sys.stderr)
    save_or_print("comments", await scrape_comments(SAMPLE_COMMENTS_VIDEO, max_scrape_pages=3))

    print("== channel ==", file=sys.stderr)
    save_or_print("channel", await scrape_channel([SAMPLE_CHANNEL_HANDLE]))

    print("== channel_videos ==", file=sys.stderr)
    save_or_print(
        "channel_videos",
        await scrape_channel_videos(SAMPLE_CHANNEL_VIDEOS, sort_by="Latest", max_scrape_pages=2),
    )

    print("== search ==", file=sys.stderr)
    save_or_print(
        "search",
        await scrape_search(SAMPLE_SEARCH_QUERY, max_scrape_pages=2, search_params=SAMPLE_SEARCH_PARAMS),
    )

    print("== shorts ==", file=sys.stderr)
    save_or_print("shorts", await scrape_shorts(SAMPLE_SHORT_IDS))

if __name__ == "__main__":
    asyncio.run(main())
