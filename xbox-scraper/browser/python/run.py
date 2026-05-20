"""Run the scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from xbox import scrape_product, scrape_search, to_dict


HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

DEFAULT_PRODUCT_URL = "https://www.xbox.com/en-us/games/store/marvel-rivals/9N8PMW7QMD3D"
DEFAULT_QUERY = "all"


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
    sample_product = os.environ.get("XBOX_SAMPLE_PRODUCT_URL", DEFAULT_PRODUCT_URL)
    sample_query = os.environ.get("XBOX_SAMPLE_QUERY", DEFAULT_QUERY)

    print(f"== product {sample_product} ==", file=sys.stderr)
    save_or_print("product", to_dict(await scrape_product(sample_product)))

    print(f"== search {sample_query!r} ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(sample_query, 1)))


if __name__ == "__main__":
    asyncio.run(main())
