"""Run the ChatGPT scrape functions live and optionally write results/*.json.

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

from chatgpt import scrape_conversation, scrape_conversations


HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"


def save_or_print(name: str, payload, *, ext: str = "json") -> None:
    if ext == "json":
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    else:
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    if os.environ.get("SAVE_TEST_RESULTS", "").lower() == "true":
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out = RESULTS_DIR / f"{name}.{ext}"
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}", file=sys.stderr)
    else:
        print(text)


SAMPLE_PROMPT = "What's the capital of France? with Brief History of the city."
SAMPLE_MULTI = [
    "what is the best web scraping service in 2026?",
    "Base on the previous answer, what is the best web scraping service you expext in 2027",
    "summarize the previous answer in 200 words",
]


async def main() -> None:
    print("== conversation ==", file=sys.stderr)
    save_or_print("conversation", await scrape_conversation(SAMPLE_PROMPT), ext="md")

    print("== conversations ==", file=sys.stderr)
    save_or_print("conversations", await scrape_conversations(SAMPLE_MULTI))


if __name__ == "__main__":
    asyncio.run(main())
