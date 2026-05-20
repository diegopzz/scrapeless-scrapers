"""Run the scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from worten import scrape_category, scrape_product, to_dict


HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

DEFAULT_PRODUCT_URL = (
    "https://www.worten.pt/produtos/iphone-15-pro-max-apple-6-7-256-gb-titanio-branco-7851167"
)
DEFAULT_CATEGORY_URL = "https://www.worten.pt/promocoes/pequenos-eletrodomesticos"


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
    sample_product = os.environ.get("WORTEN_SAMPLE_PRODUCT_URL", DEFAULT_PRODUCT_URL)
    sample_category = os.environ.get("WORTEN_SAMPLE_CATEGORY_URL", DEFAULT_CATEGORY_URL)

    print(f"== product {sample_product} ==", file=sys.stderr)
    save_or_print("product", to_dict(await scrape_product(sample_product)))

    print(f"== category {sample_category} ==", file=sys.stderr)
    save_or_print("category", to_dict(await scrape_category(sample_category)))


if __name__ == "__main__":
    asyncio.run(main())
