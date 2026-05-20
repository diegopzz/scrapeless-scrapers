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

from depop import scrape_product, scrape_search, scrape_shop, to_dict


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
    sample_url = os.environ.get(
        "DEPOP_SAMPLE_PRODUCT_URL",
        "https://www.depop.com/products/gasbiegzr-levis-jeans-size-25-light-7515/",
    )
    sample_query = os.environ.get("DEPOP_SAMPLE_QUERY", "levi jeans")
    # `depopofficial` is the canonical demo seller; its profile carries the
    # full RSC payload exercising every parser branch.
    sample_shop = os.environ.get("DEPOP_SAMPLE_SHOP", "depopofficial")

    print(f"== product {sample_url} ==", file=sys.stderr)
    save_or_print("product", to_dict(await scrape_product(sample_url)))

    print(f"== search {sample_query!r} ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(sample_query, 1)))

    print(f"== shop {sample_shop!r} ==", file=sys.stderr)
    save_or_print("shop", to_dict(await scrape_shop(sample_shop)))


if __name__ == "__main__":
    asyncio.run(main())
