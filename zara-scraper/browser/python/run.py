"""Run the scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from zara import scrape_product, scrape_search, to_dict


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
    "https://www.zara.com/us/en/zw-collection-fitted-plaid-jacket-p02784381.html",
]
DEFAULT_SEARCH_URL = "https://www.zara.com/us/en/woman-blazers-l1055.html"


async def main() -> None:
    product_urls_env = os.environ.get("ZARA_SAMPLE_PRODUCT_URLS")
    product_urls = [u.strip() for u in product_urls_env.split(",")] if product_urls_env else DEFAULT_PRODUCT_URLS
    search_url = os.environ.get("ZARA_SAMPLE_SEARCH_URL", DEFAULT_SEARCH_URL)

    print(f"== product {product_urls} ==", file=sys.stderr)
    save_or_print("product", to_dict(await scrape_product(product_urls)))

    print(f"== search {search_url!r} ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(search_url, max_pages=1)))


if __name__ == "__main__":
    asyncio.run(main())
