"""Run the scrape functions live and optionally write results/*.json.

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

from yellowpages import scrape_pages, scrape_search, to_dict


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
    query = os.environ.get("YELLOWPAGES_QUERY", "Plumber")
    location = os.environ.get("YELLOWPAGES_LOCATION", "San Francisco, CA")
    urls = (os.environ.get("YELLOWPAGES_URLS")
            or "https://www.yellowpages.com/san-francisco-ca/mip/abc-plumbing").split(",")

    print(f"== search query={query!r} location={location!r} ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(query, location, max_pages=1)))

    print(f"== pages {urls!r} ==", file=sys.stderr)
    save_or_print("pages", to_dict(await scrape_pages(urls)))


if __name__ == "__main__":
    asyncio.run(main())
