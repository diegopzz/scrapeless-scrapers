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

from redfin import (
    scrape_property_for_rent,
    scrape_property_for_sale,
    scrape_search,
    to_dict,
)

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

DEFAULT_SEARCH_URL = (
    "https://www.redfin.com/stingray/api/gis?al=1&include_nearby_homes=true"
    "&market=seattle&num_homes=350&ord=redfin-recommended-asc&page_number=1"
    "&poly=-122.54472%2047.44109%2C-122.11144%2047.44109%2C-122.11144%2047.78363"
    "%2C-122.54472%2047.78363%2C-122.54472%2047.44109&sf=1,2,3,5,6,7&start=0"
    "&status=1&uipt=1,2,3,4,5,6,7,8&v=8&zoomLevel=11"
)
DEFAULT_SALE_URLS = [
    "https://www.redfin.com/WA/Seattle/506-E-Howell-St-98122/unit-W303/home/46456",
    "https://www.redfin.com/WA/Seattle/1105-Spring-St-98104/unit-405/home/12305595",
    "https://www.redfin.com/WA/Seattle/10116-Myers-Way-S-98168/home/186647",
]
DEFAULT_RENT_URLS = [
    "https://www.redfin.com/WA/Seattle/Onni-South-Lake-Union/apartment/147020546",
    "https://www.redfin.com/WA/Seattle/The-Ivey-on-Boren/apartment/146904423",
    "https://www.redfin.com/WA/Seattle/Broadstone-Strata/apartment/178439949",
]

def save_or_print(name: str, payload) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    if os.environ.get("SAVE_TEST_RESULTS", "").lower() == "true":
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out = RESULTS_DIR / f"{name}.json"
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}", file=sys.stderr)
    else:
        print(text)

async def main() -> None:
    search_url = os.environ.get("REDFIN_SEARCH_URL", DEFAULT_SEARCH_URL)
    sale_urls = (
        os.environ["REDFIN_SALE_URLS"].split(",")
        if os.environ.get("REDFIN_SALE_URLS") else DEFAULT_SALE_URLS
    )
    rent_urls = (
        os.environ["REDFIN_RENT_URLS"].split(",")
        if os.environ.get("REDFIN_RENT_URLS") else DEFAULT_RENT_URLS
    )

    print("== search ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(search_url)))

    print("== property_for_sale ==", file=sys.stderr)
    save_or_print("property_for_sale", to_dict(await scrape_property_for_sale(sale_urls)))

    print("== property_for_rent ==", file=sys.stderr)
    save_or_print("property_for_rent", to_dict(await scrape_property_for_rent(rent_urls)))

if __name__ == "__main__":
    asyncio.run(main())
