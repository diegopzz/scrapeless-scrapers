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

from allegro import scrape_product, scrape_search, to_dict


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
    query = os.environ.get("ALLEGRO_QUERY", "iphone")
    urls = (os.environ.get("ALLEGRO_PRODUCT_URLS")
            or "https://allegro.pl/produkt/telefon-apple-iphone-17-8-256gb-5g-czarny-ffd22d9a-7e19-4bc3-98ce-d968b0669f01").split(",")

    print(f"== search query={query!r} ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(query, max_pages=1)))

    print(f"== product {urls!r} ==", file=sys.stderr)
    save_or_print("product", to_dict(await scrape_product(urls)))


if __name__ == "__main__":
    asyncio.run(main())
