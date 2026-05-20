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

from zillow import scrape_properties, scrape_search, to_dict

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

DEFAULT_SEARCH_URL = (
    "https://www.zillow.com/san-francisco-ca/?searchQueryState=%7B%22usersSearchTerm%22%3A%22Nebraska%22"
    "%2C%22mapBounds%22%3A%7B%22north%22%3A37.890669225201904%2C%22east%22%3A-122.26750460986328"
    "%2C%22south%22%3A37.659734343010626%2C%22west%22%3A-122.59915439013672%7D"
    "%2C%22isMapVisible%22%3Atrue%2C%22filterState%22%3A%7B%22sort%22%3A%7B%22value%22%3A%22days%22%7D"
    "%2C%22ah%22%3A%7B%22value%22%3Atrue%7D%7D%2C%22isListVisible%22%3Atrue%2C%22mapZoom%22%3A12"
    "%2C%22regionSelection%22%3A%5B%7B%22regionId%22%3A20330%2C%22regionType%22%3A6%7D%5D"
    "%2C%22pagination%22%3A%7B%7D%7D"
)
DEFAULT_PROPERTY_URL = (
    "https://www.zillow.com/homedetails/661-Lakeview-Ave-San-Francisco-CA-94112/15192198_zpid/"
)

def save_or_print(name: str, payload) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    if os.environ.get("SAVE_TEST_RESULTS", "").lower() == "true":
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out = RESULTS_DIR / f"{name}.json"
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}", file=sys.stderr)
    else:
        print(text)

async def main() -> None:
    search_url = os.environ.get("ZILLOW_SEARCH_URL", DEFAULT_SEARCH_URL)
    property_url = os.environ.get("ZILLOW_PROPERTY_URL", DEFAULT_PROPERTY_URL)

    print(f"== search {search_url[:80]}... ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(search_url, max_scrape_pages=1)))

    print(f"== property {property_url} ==", file=sys.stderr)
    save_or_print("property", to_dict(await scrape_properties([property_url])))

if __name__ == "__main__":
    asyncio.run(main())
