"""Run the GoogleAiMode scrape function live and optionally write results/*.json.

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

from google_ai_mode import scrape_ai_response, to_dict


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
    sample_query = os.environ.get("GOOGLE_AI_MODE_SAMPLE_QUERY", "best health trackers under $200")
    print(f"== ai_response {sample_query!r} ==", file=sys.stderr)
    save_or_print("airesponse", to_dict(await scrape_ai_response(sample_query)))


if __name__ == "__main__":
    asyncio.run(main())
