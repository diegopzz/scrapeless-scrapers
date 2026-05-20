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

from goat import scrape_products, scrape_search


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
    product_urls = os.environ.get(
        "GOAT_SAMPLE_PRODUCT_URLS",
        ",".join([
            "https://www.goat.com/sneakers/air-jordan-3-retro-white-cement-reimagined-dn3707-100",
            "https://www.goat.com/sneakers/travis-scott-x-air-jordan-1-retro-high-og-cd4487-100",
            "https://www.goat.com/sneakers/travis-scott-x-wmns-air-jordan-1-low-og-olive-dz4137-106",
        ]),
    ).split(",")
    query = os.environ.get("GOAT_SAMPLE_QUERY", "pumar dark")

    print(f"== products ({len(product_urls)}) ==", file=sys.stderr)
    save_or_print("products", await scrape_products([u.strip() for u in product_urls if u.strip()]))

    print(f"== search {query!r} ==", file=sys.stderr)
    save_or_print("search", await scrape_search(query, max_pages=3))


if __name__ == "__main__":
    asyncio.run(main())
