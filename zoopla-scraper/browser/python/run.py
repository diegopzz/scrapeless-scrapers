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

from zoopla import scrape_properties, scrape_search, to_dict

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

DEFAULT_PROPERTY_URLS = [
    "https://www.zoopla.co.uk/new-homes/details/70337559/",
    "https://www.zoopla.co.uk/new-homes/details/71411815/",
    "https://www.zoopla.co.uk/new-homes/details/71669525/",
]
DEFAULT_LOCATION_SLUG = "london/islington"
DEFAULT_QUERY_TYPE = "to-rent"

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
        os.environ["ZOOPLA_PROPERTY_URLS"].split(",")
        if os.environ.get("ZOOPLA_PROPERTY_URLS") else DEFAULT_PROPERTY_URLS
    )
    location_slug = os.environ.get("ZOOPLA_LOCATION_SLUG", DEFAULT_LOCATION_SLUG)
    query_type = os.environ.get("ZOOPLA_QUERY_TYPE", DEFAULT_QUERY_TYPE)

    print("== properties ==", file=sys.stderr)
    save_or_print("properties", to_dict(await scrape_properties(property_urls)))

    print(f"== search {query_type}/{location_slug} ==", file=sys.stderr)
    save_or_print(
        "search",
        to_dict(
            await scrape_search(
                scrape_all_pages=False,
                location_slug=location_slug,
                max_scrape_pages=2,
                query_type=query_type,
            )
        ),
    )

if __name__ == "__main__":
    asyncio.run(main())
