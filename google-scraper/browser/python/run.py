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

from google import scrape_google_map_places, scrape_keywords, scrape_serp, to_dict

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

SAMPLE_QUERY_SERP = "the upstream reference blog web scraping"
SAMPLE_QUERY_KEYWORDS = "web scraping emails"
SAMPLE_PLACES = [
    "https://www.google.com/maps/place/Mus%C3%A9e+d%27Orsay/data=!4m7!3m6!1s0x47e66e2bb630941b:0xd071bd8cb14423d8!8m2!3d48.8599614!4d2.3265614!16zL20vMGYzYjk!19sChIJG5Qwtitu5kcR2CNEsYy9cdA",
    "https://www.google.com/maps/place/The+Centre+Pompidou/data=!4m7!3m6!1s0x47e66e1c09b820a3:0xb7ac6c7e59dc3345!8m2!3d48.860642!4d2.352245!16zL20vMGYzMnA!19sChIJoyC4CRxu5kcRRTPcWX5srLc",
]

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
    print(f"== serp {SAMPLE_QUERY_SERP!r} ==", file=sys.stderr)
    save_or_print("serp", to_dict(await scrape_serp(SAMPLE_QUERY_SERP, max_pages=3)))

    print(f"== keywords {SAMPLE_QUERY_KEYWORDS!r} ==", file=sys.stderr)
    save_or_print("keywords", to_dict(await scrape_keywords(SAMPLE_QUERY_KEYWORDS)))

    print(f"== google_map_places ({len(SAMPLE_PLACES)} urls) ==", file=sys.stderr)
    save_or_print("google_map_places", to_dict(await scrape_google_map_places(SAMPLE_PLACES)))

if __name__ == "__main__":
    asyncio.run(main())
