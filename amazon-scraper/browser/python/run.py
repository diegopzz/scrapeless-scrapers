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

from amazon import scrape_product, scrape_reviews, scrape_search, to_dict


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
    sample_search = os.environ.get("AMAZON_SAMPLE_SEARCH_URL", "https://www.amazon.com/s?k=kindle")
    sample_product = os.environ.get(
        "AMAZON_SAMPLE_PRODUCT_URL",
        "https://www.amazon.com/PlayStation-5-Console-CFI-1215A01X/dp/B0BCNKKZ91/",
    )

    print(f"== search {sample_search!r} ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(sample_search, max_pages=2)))

    print(f"== product {sample_product!r} ==", file=sys.stderr)
    save_or_print("product", to_dict(await scrape_product(sample_product)))

    print(f"== reviews {sample_product!r} ==", file=sys.stderr)
    save_or_print("reviews", to_dict(await scrape_reviews(sample_product)))


if __name__ == "__main__":
    asyncio.run(main())
