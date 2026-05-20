"""Run the Threads scrape functions live and optionally write results/*.json.

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

from threads import scrape_profile, scrape_thread, to_dict


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
    sample_thread = os.environ.get("THREADS_SAMPLE_THREAD", "https://www.threads.net/t/C8CTu0iswgv")
    sample_profile = os.environ.get("THREADS_SAMPLE_PROFILE", "https://www.threads.net/@natgeo")

    print(f"== thread {sample_thread} ==", file=sys.stderr)
    save_or_print("thread", to_dict(await scrape_thread(sample_thread)))

    print(f"== profile {sample_profile} ==", file=sys.stderr)
    save_or_print("profile", to_dict(await scrape_profile(sample_profile)))


if __name__ == "__main__":
    asyncio.run(main())
