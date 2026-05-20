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

from stockx import scrape_product, scrape_search


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
    product_url = os.environ.get(
        "STOCKX_SAMPLE_PRODUCT_URL", "https://stockx.com/nike-x-stussy-bucket-hat-black"
    )
    search_url = os.environ.get("STOCKX_SAMPLE_SEARCH_URL", "https://stockx.com/search?s=nike")

    print(f"== product {product_url} ==", file=sys.stderr)
    save_or_print("product", await scrape_product(product_url))

    print(f"== search {search_url!r} ==", file=sys.stderr)
    save_or_print("search", await scrape_search(search_url, max_pages=2))


if __name__ == "__main__":
    asyncio.run(main())
