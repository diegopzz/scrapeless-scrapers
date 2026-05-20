"""Run the scrape functions live and optionally write results/*.json."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from similarweb import (
    scrape_sitemaps,
    scrape_trendings,
    scrape_website,
    scrape_website_compare,
    to_dict,
)


HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

SAMPLE_DOMAINS = ["google.com", "twitter.com", "youtube.com", "instagram.com"]
SAMPLE_COMPARE = ("google.com", "youtube.com")
SAMPLE_SITEMAP = "https://www.similarweb.com/sitemaps/top-websites/top-websites-001.xml.gz"
SAMPLE_TRENDING_URLS = [
    "https://www.similarweb.com/top-websites/computers-electronics-and-technology/programming-and-developer-software/",
    "https://www.similarweb.com/top-websites/computers-electronics-and-technology/social-networks-and-online-communities/",
    "https://www.similarweb.com/top-websites/finance/investing/",
]


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
    print(f"== website ({len(SAMPLE_DOMAINS)} domains) ==", file=sys.stderr)
    save_or_print("website", to_dict(await scrape_website(SAMPLE_DOMAINS)))

    print(f"== website_compare {SAMPLE_COMPARE} ==", file=sys.stderr)
    save_or_print("website_compare", to_dict(await scrape_website_compare(*SAMPLE_COMPARE)))

    print(f"== sitemaps {SAMPLE_SITEMAP} ==", file=sys.stderr)
    save_or_print("sitemaps", await scrape_sitemaps(SAMPLE_SITEMAP))

    print(f"== trendings ({len(SAMPLE_TRENDING_URLS)} urls) ==", file=sys.stderr)
    save_or_print("trendings", to_dict(await scrape_trendings(SAMPLE_TRENDING_URLS)))


if __name__ == "__main__":
    asyncio.run(main())
