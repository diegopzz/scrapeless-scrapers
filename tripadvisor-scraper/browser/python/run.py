"""Run the TripAdvisor scrape functions live and optionally write results/*.json.

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

import tripadvisor


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
    print("== TripAdvisor location autocomplete ==", file=sys.stderr)
    location = await tripadvisor.scrape_location_data(query="Malta")
    save_or_print("location", location)

    print("== TripAdvisor search ==", file=sys.stderr)
    search = await tripadvisor.scrape_search(
        search_url="https://www.tripadvisor.com/Hotels-g60763-oa30-New_York_City_New_York-Hotels.html",
        max_pages=2,
    )
    save_or_print("search", search)

    print("== TripAdvisor hotel ==", file=sys.stderr)
    hotel = await tripadvisor.scrape_hotel(
        "https://www.tripadvisor.com/Hotel_Review-g190327-d264936-Reviews-1926_Hotel_Spa-Sliema_Island_of_Malta.html",
        max_review_pages=3,
    )
    save_or_print("hotels", hotel)


if __name__ == "__main__":
    asyncio.run(main())
