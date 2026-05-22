"""Run the Grok scrape functions live and optionally write results/*.json.

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

from grok import scrape_share, to_dict

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

# Live-verified public Grok share URL (rugby collective agreement analysis, 2025).
SAMPLE_SHARE_URL = "https://grok.com/share/bGVnYWN5_d6991719-5568-4608-b613-609cbd3f2842"


def save_or_print(name: str, payload, *, ext: str = "json") -> None:
    if ext == "json":
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    else:
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    if os.environ.get("SAVE_TEST_RESULTS", "").lower() == "true":
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out = RESULTS_DIR / f"{name}.{ext}"
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}", file=sys.stderr)
    else:
        print(text)


async def main() -> None:
    print("== share ==", file=sys.stderr)
    result = await scrape_share(SAMPLE_SHARE_URL)
    save_or_print("share", to_dict(result))


if __name__ == "__main__":
    asyncio.run(main())
