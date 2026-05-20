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

from wellfound import scrape_companies, scrape_search, to_dict


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
    role = os.environ.get("WELLFOUND_ROLE", "engineer")
    # Wellfound's `/role/<role>` (no location) returns a 200-but-empty
    # interstitial; `/role/l/<role>/<city>` is the fully-rendered path.
    location = os.environ.get("WELLFOUND_LOCATION", "san-francisco")
    company_urls = (os.environ.get("WELLFOUND_COMPANY_URLS")
                    or "https://wellfound.com/company/openai").split(",")

    print(f"== search role={role!r} location={location!r} ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(role, location, max_pages=1)))

    print(f"== companies {company_urls!r} ==", file=sys.stderr)
    save_or_print("companies", to_dict(await scrape_companies(company_urls)))


if __name__ == "__main__":
    asyncio.run(main())
