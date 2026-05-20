"""Run the scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from aliexpress import (
    find_aliexpress_products,
    scrape_product,
    scrape_product_reviews,
    scrape_search,
    to_dict,
)


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


DEFAULT_SEARCH_URL = "https://www.aliexpress.com/w/wholesale-drills.html?catId=0&SearchText=drills"
DEFAULT_PRODUCT_URL = "https://www.aliexpress.com/item/3256807619226115.html"
DEFAULT_REVIEW_PRODUCT_ID = "1005006717259012"
DEFAULT_CATEGORY_URL = "https://www.aliexpress.com/category/5090301/cellphones.html"


async def main() -> None:
    search_url = os.environ.get("ALIEXPRESS_SAMPLE_SEARCH_URL", DEFAULT_SEARCH_URL)
    product_url = os.environ.get("ALIEXPRESS_SAMPLE_PRODUCT_URL", DEFAULT_PRODUCT_URL)
    review_pid = os.environ.get("ALIEXPRESS_SAMPLE_REVIEW_PRODUCT_ID", DEFAULT_REVIEW_PRODUCT_ID)
    category_url = os.environ.get("ALIEXPRESS_SAMPLE_CATEGORY_URL", DEFAULT_CATEGORY_URL)

    print(f"== search {search_url!r} ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(search_url, max_pages=2)))

    print(f"== product {product_url!r} ==", file=sys.stderr)
    save_or_print("product", to_dict(await scrape_product(product_url)))

    print(f"== reviews productId={review_pid} ==", file=sys.stderr)
    save_or_print("reviews", to_dict(await scrape_product_reviews(review_pid, max_scrape_pages=3)))

    print(f"== category {category_url!r} ==", file=sys.stderr)
    save_or_print("category_products", to_dict(await find_aliexpress_products(category_url, max_pages=3)))


if __name__ == "__main__":
    asyncio.run(main())
