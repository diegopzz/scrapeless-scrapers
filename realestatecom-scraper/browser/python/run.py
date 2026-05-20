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

import realestatecom


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
    print("running Realestate.com.au scrape", file=sys.stderr)

    properties_data = await realestatecom.scrape_properties(
        urls=[
            "https://www.realestate.com.au/property-house-vic-tarneit-143160680",
            "https://www.realestate.com.au/property-house-vic-bundoora-141557712",
            "https://www.realestate.com.au/property-townhouse-vic-glenroy-143556608",
        ]
    )
    save_or_print("properties", properties_data)

    search_data = await realestatecom.scrape_search(
        url="https://www.realestate.com.au/buy/in-melbourne+-+northern+region,+vic/list-1",
        max_scrape_pages=3,
    )
    save_or_print("search", search_data)


if __name__ == "__main__":
    asyncio.run(main())
