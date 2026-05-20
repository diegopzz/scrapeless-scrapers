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

from indeed import scrape_jobs, scrape_search, to_dict


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
    sample_url = os.environ.get(
        "INDEED_SAMPLE_URL", "https://www.indeed.com/jobs?q=python&l=Texas"
    )
    raw = os.environ.get("INDEED_SAMPLE_JOB_KEYS", "")
    explicit_job_keys = [k.strip() for k in raw.split(",") if k.strip()]

    print(f"== search {sample_url!r} ==", file=sys.stderr)
    search_results = await scrape_search(sample_url, max_results=10)
    save_or_print("search", to_dict(search_results))

    # Indeed `jk` ids are ephemeral; pick fresh ones from the live search above
    # whenever the user hasn't pinned a specific list via INDEED_SAMPLE_JOB_KEYS.
    job_keys = explicit_job_keys
    if not job_keys:
        job_keys = [r.get("jobkey") for r in search_results if isinstance(r, dict) and r.get("jobkey")][:2]

    print(f"== jobs {job_keys!r} ==", file=sys.stderr)
    save_or_print("jobs", to_dict(await scrape_jobs(job_keys)) if job_keys else [])


if __name__ == "__main__":
    asyncio.run(main())
