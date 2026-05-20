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

from rightmove import find_locations, scrape_properties, scrape_search, to_dict

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

DEFAULT_PROPERTY_URLS = [
    "https://www.rightmove.co.uk/properties/149360984#/",
    "https://www.rightmove.co.uk/properties/136408088#/",
    "https://www.rightmove.co.uk/properties/148922639#/",
]
DEFAULT_LOCATION_QUERY = "cornwall"
DEFAULT_LOCATION_NAME = "Cornwall"

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
    property_urls = (
        os.environ["RIGHTMOVE_PROPERTY_URLS"].split(",")
        if os.environ.get("RIGHTMOVE_PROPERTY_URLS") else DEFAULT_PROPERTY_URLS
    )
    location_query = os.environ.get("RIGHTMOVE_LOCATION_QUERY", DEFAULT_LOCATION_QUERY)
    location_name = os.environ.get("RIGHTMOVE_LOCATION_NAME", DEFAULT_LOCATION_NAME)

    print("== properties ==", file=sys.stderr)
    save_or_print("properties", to_dict(await scrape_properties(property_urls)))

    print(f"== find_locations '{location_query}' ==", file=sys.stderr)
    locations = await find_locations(location_query)
    save_or_print("locations", locations)

    if locations:
        print(f"== search {location_name} ({locations[0]}) ==", file=sys.stderr)
        save_or_print(
            "search",
            to_dict(
                await scrape_search(
                    location_name=location_name,
                    location_id=locations[0],
                    scrape_all_properties=False,
                    max_properties=50,
                )
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
