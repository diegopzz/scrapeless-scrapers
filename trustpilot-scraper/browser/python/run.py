"""Run the Trustpilot scrape functions live and optionally write results/*.json.

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

import trustpilot


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
    print("== Trustpilot search ==", file=sys.stderr)
    search = await trustpilot.scrape_search(
        url="https://www.trustpilot.com/categories/electronics_technology", max_pages=3
    )
    save_or_print("search", search)

    print("== Trustpilot company pages ==", file=sys.stderr)
    companies = await trustpilot.scrape_company(
        urls=[
            "https://www.trustpilot.com/review/www.flashbay.com",
            "https://www.trustpilot.com/review/iggm.com",
            "https://www.trustpilot.com/review/www.bhphotovideo.com",
        ]
    )
    save_or_print("companies", companies)

    print("== Trustpilot reviews ==", file=sys.stderr)
    reviews = await trustpilot.scrape_reviews(
        url="https://www.trustpilot.com/review/www.bhphotovideo.com", max_pages=3
    )
    save_or_print("reviews", reviews)


if __name__ == "__main__":
    asyncio.run(main())
