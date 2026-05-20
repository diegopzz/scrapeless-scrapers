"""Run the scrape functions live and optionally write results/*.json.

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

from craigslist import scrape_listing, scrape_search, to_dict


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
    sample_city = os.environ.get("CRAIGSLIST_SAMPLE_CITY", "newyork")
    sample_category = os.environ.get("CRAIGSLIST_SAMPLE_CATEGORY", "sss")
    sample_query = os.environ.get("CRAIGSLIST_SAMPLE_QUERY", "bicycle")
    sample_listing = os.environ.get("CRAIGSLIST_SAMPLE_LISTING_URL", "")

    print(f"== search {sample_city}/{sample_category} q={sample_query!r} ==", file=sys.stderr)
    search = await scrape_search(sample_city, sample_category, sample_query, 1)
    save_or_print("search", to_dict(search))

    listing_url = sample_listing or (search[0].url if search else "")
    if listing_url:
        print(f"== listing {listing_url} ==", file=sys.stderr)
        save_or_print("listing", to_dict(await scrape_listing(listing_url)))
    else:
        print("no listing URL available, skipping listing fixture", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
