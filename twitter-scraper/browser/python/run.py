"""Run the Twitter scrape functions live and optionally write results/*.json.

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

from twitter import scrape_profile, scrape_tweet, to_dict


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
    sample_tweet = os.environ.get(
        "TWITTER_SAMPLE_TWEET", "https://x.com/robinhanson/status/1872047986873885082"
    )
    sample_profile = os.environ.get("TWITTER_SAMPLE_PROFILE", "https://x.com/robinhanson/")

    print(f"== tweet {sample_tweet} ==", file=sys.stderr)
    save_or_print("tweet", to_dict(await scrape_tweet(sample_tweet)))

    print(f"== profile {sample_profile} ==", file=sys.stderr)
    save_or_print("profile", to_dict(await scrape_profile(sample_profile)))


if __name__ == "__main__":
    asyncio.run(main())
