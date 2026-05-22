"""Run the scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from google_jobs import scrape_jobs, to_dict

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

DEFAULT_QUERY = "software engineer jobs austin tx"


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
    query = os.environ.get("GOOGLE_JOBS_QUERY", DEFAULT_QUERY)
    print(f"== jobs query={query!r} ==", file=sys.stderr)
    save_or_print("jobs", to_dict(await scrape_jobs(query)))


if __name__ == "__main__":
    asyncio.run(main())
