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

from fashionphile import scrape_products, scrape_search


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
        "FASHIONPHILE_SAMPLE_PRODUCT_URLS",
        ",".join([
            "https://www.fashionphile.com/p/bottega-veneta-nappa-twisted-padded-intrecciato-curve-slide-sandals-36-black-1048096",
            "https://www.fashionphile.com/p/louis-vuitton-ostrich-lizard-majestueux-tote-mm-navy-1247825",
            "https://www.fashionphile.com/p/louis-vuitton-monogram-multicolor-lodge-gm-black-1242632",
        ]),
    ).split(",")
    search_url = os.environ.get(
        "FASHIONPHILE_SAMPLE_SEARCH_URL", "https://www.fashionphile.com/shop/discounted/all"
    )

    print(f"== products ({len(product_urls)}) ==", file=sys.stderr)
    save_or_print("products", await scrape_products([u.strip() for u in product_urls if u.strip()]))

    print(f"== search {search_url!r} ==", file=sys.stderr)
    save_or_print("search", await scrape_search(search_url, max_pages=3))


if __name__ == "__main__":
    asyncio.run(main())
