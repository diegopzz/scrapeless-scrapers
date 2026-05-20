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

import domaincom


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
    print("running Domain.com.au scrape", file=sys.stderr)

    properties_data = await domaincom.scrape_properties(
        urls=[
            "https://www.domain.com.au/610-399-bourke-street-melbourne-vic-3000-2018835548",
            "https://www.domain.com.au/property-profile/308-9-degraves-street-melbourne-vic-3000",
            "https://www.domain.com.au/1518-474-flinders-street-melbourne-vic-3000-17773317",
        ]
    )
    save_or_print("properties", properties_data)

    search_data = await domaincom.scrape_search(
        url="https://www.domain.com.au/sale/melbourne-vic-3000/",
        max_scrape_pages=1,
    )
    save_or_print("search", search_data)


if __name__ == "__main__":
    asyncio.run(main())
