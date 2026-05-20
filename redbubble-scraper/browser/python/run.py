"""Run the scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from redbubble import scrape_product, scrape_search, to_dict


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
    "https://www.redbubble.com/i/sticker/Everything-s-good-cat-by-blah707/43977882/7sgk",
    "https://www.redbubble.com/i/sticker/Black-cat-by-Flora22/110162644/7sgk",
]
DEFAULT_QUERY = "cat"


async def main() -> None:
    product_env = os.environ.get("REDBUBBLE_SAMPLE_PRODUCT_URLS")
    product_urls = [u.strip() for u in product_env.split(",")] if product_env else DEFAULT_PRODUCT_URLS
    query = os.environ.get("REDBUBBLE_SAMPLE_QUERY", DEFAULT_QUERY)

    print(f"== product {product_urls} ==", file=sys.stderr)
    save_or_print("product", to_dict(await scrape_product(product_urls)))

    print(f"== search {query!r} ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(query, max_pages=1)))


if __name__ == "__main__":
    asyncio.run(main())
