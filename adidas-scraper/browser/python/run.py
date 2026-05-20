"""Run the scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from adidas import scrape_product, scrape_search, to_dict


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


DEFAULT_PRODUCT_URLS = [
    "https://www.adidas.com/us/samba-og-shoes/B75806.html",
    "https://www.adidas.com/us/gazelle-shoes/BB5476.html",
]
DEFAULT_SEARCH_URL = "https://www.adidas.com/us/men-shoes"


async def main() -> None:
    product_urls_env = os.environ.get("ADIDAS_SAMPLE_PRODUCT_URLS")
    product_urls = [u.strip() for u in product_urls_env.split(",")] if product_urls_env else DEFAULT_PRODUCT_URLS
    search_url = os.environ.get("ADIDAS_SAMPLE_SEARCH_URL", DEFAULT_SEARCH_URL)

    print(f"== product {product_urls} ==", file=sys.stderr)
    save_or_print("product", to_dict(await scrape_product(product_urls)))

    print(f"== search {search_url!r} ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(search_url, max_pages=1)))


if __name__ == "__main__":
    asyncio.run(main())
