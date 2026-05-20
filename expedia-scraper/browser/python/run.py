"""Run the scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from expedia import scrape_hotel, scrape_search, to_dict


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
    destination = os.environ.get("EXPEDIA_SAMPLE_DESTINATION", "New York")
    checkin = os.environ.get("EXPEDIA_SAMPLE_CHECKIN", "2026-06-15")
    checkout = os.environ.get("EXPEDIA_SAMPLE_CHECKOUT", "2026-06-16")

    print(f"== search {destination!r} {checkin}..{checkout} ==", file=sys.stderr)
    search = await scrape_search(destination, checkin, checkout, 1)
    save_or_print("search", to_dict(search))

    hotel_url = os.environ.get("EXPEDIA_SAMPLE_HOTEL_URL") or (search[0].url if search else "")
    if hotel_url:
        print(f"== hotel {hotel_url} ==", file=sys.stderr)
        save_or_print("hotel", to_dict(await scrape_hotel(hotel_url)))
    else:
        print("no hotel URL available, skipping hotel fixture", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
