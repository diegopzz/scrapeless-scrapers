"""Run the Perplexity scrape function live and optionally write results/*.json.

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

from perplexity import scrape_search, to_dict


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
    prompt = os.environ.get(
        "PERPLEXITY_SAMPLE_PROMPT",
        "top 3 smartphones in 2025, compare pricing across US marketplaces",
    )
    print(f"== search {prompt!r} ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(prompt)))


if __name__ == "__main__":
    asyncio.run(main())
