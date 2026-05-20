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

import nordstorm


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
    print("running Nordstrom scrape", file=sys.stderr)

    products_data = await nordstorm.scrape_products(
        urls=[
            "https://www.nordstrom.com/s/nike-air-max-90-sneaker-men/6549520",
            "https://www.nordstrom.com/s/hank-kent-performance-twill-dress-shirt-regular-big/7783670",
            "https://www.nordstrom.com/s/bp-fleece-hoodie/7786657",
        ]
    )
    save_or_print("products", products_data)

    search_data = await nordstorm.scrape_search(
        url="https://www.nordstrom.com/sr?origin=keywordsearch&keyword=indigo",
        max_pages=2,
    )
    save_or_print("search", search_data)


if __name__ == "__main__":
    asyncio.run(main())
