"""Run the SeLoger scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from seloger import scrape_property, scrape_search, to_dict


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


SAMPLE_SEARCH = "https://www.seloger.com/classified-search?distributionTypes=Buy&estateTypes=Apartment&locations=AD08FR13100"
SAMPLE_PROPERTIES = [
    "https://www.seloger.com/annonces/achat/appartement/bordeaux-33/193612259.htm",
    "https://www.seloger.com/annonces/achat/appartement/bordeaux-33/255197845.htm",
]


async def main() -> None:
    print("== search ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(SAMPLE_SEARCH, max_pages=2)))

    print("== property ==", file=sys.stderr)
    save_or_print("property", to_dict(await scrape_property(SAMPLE_PROPERTIES)))


if __name__ == "__main__":
    asyncio.run(main())
