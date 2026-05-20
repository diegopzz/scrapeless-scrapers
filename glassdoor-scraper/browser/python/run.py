"""Run the Glassdoor scrape functions live and optionally write results/*.json.

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

import glassdoor


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
    employer = "eBay"
    employer_id = "7853"

    print("== Glassdoor jobs ==", file=sys.stderr)
    url_jobs = glassdoor.Url.jobs(employer, employer_id, region=glassdoor.Region.UNITED_STATES)
    jobs = await glassdoor.scrape_jobs(url_jobs, max_pages=3)
    save_or_print("jobs", jobs)

    print("== Glassdoor salaries ==", file=sys.stderr)
    url_sal = glassdoor.Url.salaries(employer, employer_id)
    salaries = await glassdoor.scrape_salaries(url_sal, max_pages=3)
    save_or_print("salaries", salaries)

    print("== Glassdoor reviews ==", file=sys.stderr)
    url_rev = glassdoor.Url.reviews(employer, employer_id)
    reviews = await glassdoor.scrape_reviews(url_rev, max_pages=3)
    save_or_print("reviews", reviews)

    print("== Glassdoor company autocomplete ==", file=sys.stderr)
    companies = await glassdoor.find_companies(employer)
    save_or_print("companies", companies)


if __name__ == "__main__":
    asyncio.run(main())
