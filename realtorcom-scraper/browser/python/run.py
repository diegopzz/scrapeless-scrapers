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

from realtorcom import scrape_feed, scrape_property, scrape_search, to_dict

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

DEFAULT_PROPERTY_URL = (
    "https://www.realtor.com/realestateandhomes-detail/"
    "12355-Attlee-Dr_Houston_TX_77077_M70330-35605"
)
DEFAULT_STATE = "CA"
DEFAULT_CITY = "San-Francisco"
DEFAULT_FEED_URL = "https://cdn.realtor.ca/sitemap/realtorsitemap/sitemap.xml"

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
    property_url = os.environ.get("REALTORCOM_PROPERTY_URL", DEFAULT_PROPERTY_URL)
    state = os.environ.get("REALTORCOM_STATE", DEFAULT_STATE)
    city = os.environ.get("REALTORCOM_CITY", DEFAULT_CITY)
    feed_url = os.environ.get("REALTORCOM_FEED_URL", DEFAULT_FEED_URL)

    print(f"== feed {feed_url} ==", file=sys.stderr)
    try:
        save_or_print("feed", to_dict(await scrape_feed(feed_url)))
    except Exception as e:
        print(f"feed failed: {e}", file=sys.stderr)

    print(f"== search {city},{state} ==", file=sys.stderr)
    try:
        save_or_print("search", to_dict(await scrape_search(state, city, max_pages=2)))
    except Exception as e:
        print(f"search failed: {e}", file=sys.stderr)

    print(f"== property {property_url} ==", file=sys.stderr)
    try:
        save_or_print("property", to_dict(await scrape_property(property_url)))
    except Exception as e:
        print(f"property failed: {e}", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(main())
