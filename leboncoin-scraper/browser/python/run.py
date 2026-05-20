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

import leboncoin


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
    print("running Leboncoin scrape", file=sys.stderr)

    search_data = await leboncoin.scrape_search(
        url="https://www.leboncoin.fr/recherche?text=coffe",
        max_pages=2,
        scrape_all_pages=False,
    )
    save_or_print("search", search_data)

    ad_urls = [
        "https://www.leboncoin.fr/ad/ventes_immobilieres/2919253293",
        "https://www.leboncoin.fr/ad/ventes_immobilieres/2013383512",
        "https://www.leboncoin.fr/ad/ventes_immobilieres/3027789970",
    ]
    ad_data = []
    for coro in asyncio.as_completed([leboncoin.scrape_ad(u) for u in ad_urls]):
        ad_data.append(await coro)
    save_or_print("ads", ad_data)


if __name__ == "__main__":
    asyncio.run(main())
