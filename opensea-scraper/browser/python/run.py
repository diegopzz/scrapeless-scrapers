"""Run the OpenSea scrape functions live and optionally write results/*.json.

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

from opensea import scrape_collection, scrape_asset, to_dict


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
    slug = os.environ.get("OPENSEA_SAMPLE_SLUG", "boredapeyachtclub")
    chain = os.environ.get("OPENSEA_SAMPLE_CHAIN", "ethereum")
    contract = os.environ.get("OPENSEA_SAMPLE_CONTRACT", "0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d")
    token_id = os.environ.get("OPENSEA_SAMPLE_TOKEN_ID", "1")

    print(f"== collection {slug!r} ==", file=sys.stderr)
    save_or_print("collection", to_dict(await scrape_collection(slug)))

    print(f"== asset {chain}/{contract}/{token_id} ==", file=sys.stderr)
    save_or_print("asset", to_dict(await scrape_asset(chain, contract, token_id)))


if __name__ == "__main__":
    asyncio.run(main())
