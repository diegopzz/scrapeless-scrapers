"""Run the scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from trip import scrape_hotel, scrape_search, to_dict


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
    sample_city = os.environ.get("TRIP_SAMPLE_CITY_ID", "53")
    sample_checkin = os.environ.get("TRIP_SAMPLE_CHECKIN", "2026/06/15")
    sample_checkout = os.environ.get("TRIP_SAMPLE_CHECKOUT", "2026/06/16")

    print(f"== search city={sample_city} {sample_checkin}..{sample_checkout} ==", file=sys.stderr)
    search = await scrape_search(sample_city, sample_checkin, sample_checkout, 1)
    save_or_print("search", to_dict(search))

    hotel_id = os.environ.get("TRIP_SAMPLE_HOTEL_ID") or (search[0].id if search else "")
    if hotel_id:
        print(f"== hotel {hotel_id} ==", file=sys.stderr)
        save_or_print("hotel", to_dict(await scrape_hotel(hotel_id, sample_checkin, sample_checkout)))
    else:
        print("no hotel id available, skipping hotel fixture", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
