"""Run the Immowelt scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from immowelt import scrape_properties, scrape_search, to_dict


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


SAMPLE_SEARCH = "https://www.immowelt.de/classified-search?distributionTypes=Buy&estateTypes=Apartment&locations=AD08DE6345"
SAMPLE_PROPERTIES = [
    "https://www.immowelt.de/expose/k2ag632",
    "https://www.immowelt.de/expose/k2bw932",
]


async def main() -> None:
    print("== search ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(SAMPLE_SEARCH, max_scrape_pages=3)))

    print("== properties ==", file=sys.stderr)
    save_or_print("properties", to_dict(await scrape_properties(SAMPLE_PROPERTIES)))


if __name__ == "__main__":
    asyncio.run(main())
