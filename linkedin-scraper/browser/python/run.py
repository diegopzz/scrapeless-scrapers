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

from linkedin import (
    scrape_articles,
    scrape_company,
    scrape_job_search,
    scrape_jobs,
    scrape_profile,
    to_dict,
)


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
    profile_urls = (os.environ.get("LINKEDIN_PROFILE_URLS")
                    or "https://www.linkedin.com/in/williamhgates").split(",")
    company_urls = (os.environ.get("LINKEDIN_COMPANY_URLS")
                    or "https://www.linkedin.com/company/microsoft").split(",")
    job_urls_raw = os.environ.get("LINKEDIN_JOB_URLS")
    job_urls = [u for u in (job_urls_raw or "").split(",") if u.strip()]
    article_urls = (os.environ.get("LINKEDIN_ARTICLE_URLS")
                    or "https://www.linkedin.com/pulse/how-i-learnt-stop-worrying-love-rejection-richard-branson").split(",")
    keyword = os.environ.get("LINKEDIN_JOB_KEYWORD", "Python Developer")
    location = os.environ.get("LINKEDIN_JOB_LOCATION", "United States")

    print("== profile ==", file=sys.stderr)
    save_or_print("profile", to_dict(await scrape_profile(profile_urls)))

    print("== company ==", file=sys.stderr)
    save_or_print("company", to_dict(await scrape_company(company_urls)))

    print("== job_search ==", file=sys.stderr)
    job_search_pages = await scrape_job_search(keyword, location, max_pages=1)
    save_or_print("job_search", to_dict(job_search_pages))

    print("== jobs ==", file=sys.stderr)
    if not job_urls:
        # LinkedIn job ids are ephemeral; pick up to two from the live search.
        first_page = job_search_pages[0] if job_search_pages else {}
        for entry in first_page.get("data", []) if isinstance(first_page, dict) else []:
            u = entry.get("jobUrl")
            if isinstance(u, str) and "/jobs/view/" in u:
                job_urls.append(u)
            if len(job_urls) >= 2:
                break
    save_or_print("jobs", to_dict(await scrape_jobs(job_urls)) if job_urls else [])

    print("== articles ==", file=sys.stderr)
    save_or_print("articles", to_dict(await scrape_articles(article_urls)))


if __name__ == "__main__":
    asyncio.run(main())
