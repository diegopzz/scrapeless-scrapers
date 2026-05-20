"""Run the scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from trivago import scrape_destination, scrape_search, to_dict


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
        "TRIVAGO_SAMPLE_DESTINATION_URL",
        "https://www.trivago.com/en-US/odr/hotels-new-york-city-new-york-united-states-of-america?search=200-2755",
    )

    print(f"== search {sample_url} ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(sample_url, 1)))

    print(f"== destination {sample_url} ==", file=sys.stderr)
    save_or_print("destination", to_dict(await scrape_destination(sample_url)))


if __name__ == "__main__":
    asyncio.run(main())
