"""Run the scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from bing import scrape_keywords, scrape_search, to_dict


HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

SAMPLE_QUERY = "web scraping emails"


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
    print(f"== search {SAMPLE_QUERY!r} ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(SAMPLE_QUERY, max_pages=3)))

    print(f"== keywords {SAMPLE_QUERY!r} ==", file=sys.stderr)
    save_or_print("keywords", to_dict(await scrape_keywords(SAMPLE_QUERY)))


if __name__ == "__main__":
    asyncio.run(main())
