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

from etsy import scrape_product, scrape_search, scrape_shop


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
    search_url = os.environ.get(
        "ETSY_SAMPLE_SEARCH_URL", "https://www.etsy.com/search?q=wood+laptop+stand"
    )
    product_urls = os.environ.get(
        "ETSY_SAMPLE_PRODUCT_URLS",
        "https://www.etsy.com/listing/1552627931,"
        "https://www.etsy.com/listing/529765307,"
        "https://www.etsy.com/listing/949905096",
    ).split(",")
    shop_urls = os.environ.get(
        "ETSY_SAMPLE_SHOP_URLS",
        "https://www.etsy.com/shop/FalkelDesign,"
        "https://www.etsy.com/shop/JoshuaHouseCrafts,"
        "https://www.etsy.com/shop/Oakywood",
    ).split(",")

    print(f"== search {search_url!r} ==", file=sys.stderr)
    save_or_print("search", await scrape_search(search_url, max_pages=3))

    print(f"== products ({len(product_urls)}) ==", file=sys.stderr)
    save_or_print("product", await scrape_product([u.strip() for u in product_urls if u.strip()]))

    print(f"== shops ({len(shop_urls)}) ==", file=sys.stderr)
    save_or_print("shop", await scrape_shop([u.strip() for u in shop_urls if u.strip()]))


if __name__ == "__main__":
    asyncio.run(main())
