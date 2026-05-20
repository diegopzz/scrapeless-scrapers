"""Run the scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from walmart import scrape_products, scrape_search, to_dict


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
    product_urls_env = os.environ.get("WALMART_SAMPLE_PRODUCT_URLS")
    if product_urls_env:
        product_urls = [u.strip() for u in product_urls_env.split(",") if u.strip()]
    else:
        product_urls = [
            "https://www.walmart.com/ip/1736740710",
            "https://www.walmart.com/ip/715596133",
        ]
    sample_query = os.environ.get("WALMART_SAMPLE_QUERY", "laptop")

    print(f"== products {product_urls} ==", file=sys.stderr)
    save_or_print("products", to_dict(await scrape_products(product_urls)))

    print(f"== search {sample_query!r} ==", file=sys.stderr)
    save_or_print(
        "search",
        to_dict(await scrape_search(query=sample_query, sort="best_seller", max_pages=3)),
    )


if __name__ == "__main__":
    asyncio.run(main())
