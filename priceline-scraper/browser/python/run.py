"""Run the scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from priceline import scrape_hotel, scrape_search, to_dict


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
    # Defaults match the Node sample IDs: real Aberdeen, SD city + Fairfield Inn.
    sample_city = os.environ.get("PRICELINE_SAMPLE_CITY_ID", "3000020228")
    sample_checkin = os.environ.get("PRICELINE_SAMPLE_CHECKIN", "2026-06-15")
    sample_checkout = os.environ.get("PRICELINE_SAMPLE_CHECKOUT", "2026-06-16")
    sample_hotel = os.environ.get("PRICELINE_SAMPLE_HOTEL_ID", "97649603")

    print(f"== hotel {sample_hotel} ==", file=sys.stderr)
    save_or_print("hotel", to_dict(await scrape_hotel(sample_hotel, sample_checkin, sample_checkout)))

    print(f"== search city={sample_city} ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(sample_city, sample_checkin, sample_checkout)))


if __name__ == "__main__":
    asyncio.run(main())
