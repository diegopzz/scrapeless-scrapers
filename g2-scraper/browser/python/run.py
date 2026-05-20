"""Run the G2 scrape functions live and optionally write results/*.json.

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

import g2


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
    print("== G2 search ==", file=sys.stderr)
    search = await g2.scrape_search(
        url="https://www.g2.com/search?query=Infrastructure", max_scrape_pages=3
    )
    save_or_print("search", search)

    print("== G2 reviews ==", file=sys.stderr)
    reviews = await g2.scrape_reviews(
        url="https://www.g2.com/products/digitalocean/reviews", max_review_pages=3
    )
    save_or_print("reviews", reviews)

    print("== G2 alternatives ==", file=sys.stderr)
    alternatives = await g2.scrape_alternatives(product="digitalocean")
    save_or_print("alternatives", alternatives)


if __name__ == "__main__":
    asyncio.run(main())
