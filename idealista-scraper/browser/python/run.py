"""Run the Idealista scrape functions live and optionally write results/*.json.

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

from idealista import (
    scrape_properties,
    scrape_provinces,
    scrape_search,
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


SAMPLE_PROPERTIES = (os.environ.get("IDEALISTA_PROPERTIES") or
    "https://www.idealista.com/en/inmueble/111070021/,"
    "https://www.idealista.com/en/inmueble/108649518/").split(",")
SAMPLE_SEARCH = "https://www.idealista.com/en/venta-viviendas/marbella-malaga/con-chalets/"
SAMPLE_PROVINCES = ["https://www.idealista.com/venta-viviendas/almeria-provincia/municipios"]


async def main() -> None:
    print("== properties ==", file=sys.stderr)
    save_or_print("properties", to_dict(await scrape_properties(SAMPLE_PROPERTIES)))

    print("== search ==", file=sys.stderr)
    save_or_print("search", to_dict(await scrape_search(SAMPLE_SEARCH, max_scrape_pages=2)))

    print("== provinces ==", file=sys.stderr)
    save_or_print("provinces", await scrape_provinces(SAMPLE_PROVINCES))


if __name__ == "__main__":
    asyncio.run(main())
