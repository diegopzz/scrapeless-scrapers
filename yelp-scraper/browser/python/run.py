"""Run the Yelp scrape functions live and optionally write results/*.json.

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

import yelp


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
    print("== Yelp business pages ==", file=sys.stderr)
    business_data = await yelp.scrape_pages(
        urls=[
            "https://www.yelp.com/biz/vons-1000-spirits-seattle-4",
            "https://www.yelp.com/biz/ihop-seattle-4",
            "https://www.yelp.com/biz/toulouse-petit-kitchen-and-lounge-seattle",
        ]
    )
    save_or_print("business_pages", business_data)

    print("== Yelp reviews ==", file=sys.stderr)
    reviews_data = await yelp.scrape_reviews(
        url="https://www.yelp.com/biz/vons-1000-spirits-seattle-4",
        max_reviews=28,
    )
    save_or_print("reviews", reviews_data)

    print("== Yelp search ==", file=sys.stderr)
    search_data = await yelp.scrape_search(
        keyword="plumbers", location="Seattle, WA", max_pages=2
    )
    save_or_print("search", search_data)


if __name__ == "__main__":
    asyncio.run(main())
