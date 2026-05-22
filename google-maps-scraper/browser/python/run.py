"""Run the scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from google_maps import scrape_place, scrape_places, to_dict

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

DEFAULT_SEARCH_QUERY = "coffee shops in Austin TX"
DEFAULT_PLACE_URL = (
    "https://www.google.com/maps/place/Epoch+Coffee/@30.3186037,-97.7296551,15z"
    "/data=!4m6!3m5!1s0x8644ca6bc309e81b:0x1f1a903bbb66839!8m2!3d30.3186037!4d-97.7245402!16s%2Fg%2F1v76_180"
)


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
    query = os.environ.get("GOOGLE_MAPS_SEARCH_QUERY", DEFAULT_SEARCH_QUERY)
    place_url = os.environ.get("GOOGLE_MAPS_PLACE_URL", DEFAULT_PLACE_URL)

    print(f"== places query={query!r} ==", file=sys.stderr)
    save_or_print("places", to_dict(await scrape_places(query)))

    print(f"== place {place_url} ==", file=sys.stderr)
    save_or_print("place", to_dict(await scrape_place(place_url)))


if __name__ == "__main__":
    asyncio.run(main())
