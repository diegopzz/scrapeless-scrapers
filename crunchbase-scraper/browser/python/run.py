"""Run the scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from crunchbase import scrape_company, scrape_person, to_dict


HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

SAMPLE_COMPANY_URL = "https://www.crunchbase.com/organization/tesla-motors/people"
SAMPLE_PERSON_URL = "https://www.crunchbase.com/person/elon-musk"


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
    print(f"== company {SAMPLE_COMPANY_URL} ==", file=sys.stderr)
    save_or_print("company", to_dict(await scrape_company(SAMPLE_COMPANY_URL)))

    print(f"== person {SAMPLE_PERSON_URL} ==", file=sys.stderr)
    save_or_print("person", to_dict(await scrape_person(SAMPLE_PERSON_URL)))


if __name__ == "__main__":
    asyncio.run(main())
