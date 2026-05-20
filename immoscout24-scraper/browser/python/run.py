"""Run the Immoscout24 scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from immoscout24 import scrape_properties, scrape_search, to_dict


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


SAMPLE_PROPERTIES = [
    "https://www.immoscout24.ch/rent/4002086534",
    "https://www.immoscout24.ch/rent/4002937830",
    "https://www.immoscout24.ch/rent/4002784101",
]
SAMPLE_SEARCH = "https://www.immoscout24.ch/en/real-estate/rent/city-bern"


async def main() -> None:
    print("== properties ==", file=sys.stderr)
    save_or_print("properties", to_dict(await scrape_properties(SAMPLE_PROPERTIES)))

    print("== search ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(SAMPLE_SEARCH, scrape_all_pages=False, max_scrape_pages=2)))


if __name__ == "__main__":
    asyncio.run(main())
