"""Run the Booking.com scrape functions live and optionally write results/*.json.

Usage:
    SCRAPELESS_API_KEY=sk_... python run.py
    SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true python run.py
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import sys
from pathlib import Path

from bookingcom import scrape_hotel, scrape_hotel_reviews, scrape_search


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


_today = datetime.date.today()
SAMPLE_QUERY = "Malta"
SAMPLE_CHECKIN = (_today + datetime.timedelta(days=7)).isoformat()
SAMPLE_CHECKOUT = (_today + datetime.timedelta(days=14)).isoformat()
SAMPLE_HOTEL_URL = "https://www.booking.com/hotel/gb/gardencourthotel.en-gb.html"


async def main() -> None:
    # Scrape hotel detail first — search-results is the most heavily defended
    # of the three endpoints, so we try the easiest target before stressing
    # the session.
    print(f"== hotel {SAMPLE_HOTEL_URL} ==", file=sys.stderr)
    save_or_print("hotel", await scrape_hotel(SAMPLE_HOTEL_URL, SAMPLE_CHECKIN, price_n_days=7, proxy_country="GB"))

    print(f"== hotel_review {SAMPLE_HOTEL_URL} ==", file=sys.stderr)
    save_or_print("hotel_review", await scrape_hotel_reviews(SAMPLE_HOTEL_URL, max_pages=3, proxy_country="GB"))

    print(f"== search {SAMPLE_QUERY!r} {SAMPLE_CHECKIN}->{SAMPLE_CHECKOUT} ==", file=sys.stderr)
    save_or_print(
        "search",
        await scrape_search(SAMPLE_QUERY, SAMPLE_CHECKIN, SAMPLE_CHECKOUT, max_pages=2, proxy_country="MT"),
    )


if __name__ == "__main__":
    asyncio.run(main())
