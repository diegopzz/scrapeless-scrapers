"""Run the scrape functions live and optionally write results/*.json.

Usage:
    SCRAPELESS_API_KEY=sk_... python run.py
    SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true python run.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

# Module file name starts with a digit so we load it explicitly.
_spec = importlib.util.spec_from_file_location("scrapeless_1688", HERE / "1688.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
scrape_product = _mod.scrape_product
scrape_search = _mod.scrape_search
to_dict = _mod.to_dict


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
    sample_id = os.environ.get("SCRAPELESS_1688_SAMPLE_ID", "611499776800")
    # Chinese phrase for "phone case" — 1688 favours zh-CN queries.
    sample_query = os.environ.get("SCRAPELESS_1688_SAMPLE_QUERY", "手机壳")

    print(f"== product {sample_id} ==", file=sys.stderr)
    save_or_print("product", to_dict(await scrape_product(sample_id)))

    print(f"== search {sample_query!r} ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(sample_query, 1)))


if __name__ == "__main__":
    asyncio.run(main())
