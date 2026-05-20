# Ebay — Python surface

Async Ebay scraper built on the official [`scrapeless`](https://pypi.org/project/scrapeless/) Python SDK + Playwright over CDP.

## Install

```bash
poetry install
poetry run playwright install chromium
```

## Run

```bash
export SCRAPELESS_API_KEY=sk_...
python run.py                              # print to stdout
SAVE_TEST_RESULTS=true python run.py       # write to results/*.json
```

## Test

```bash
SCRAPELESS_API_KEY=sk_... poetry run pytest -v
```

Validates output against [`../../DATA_MODEL.md`](../../DATA_MODEL.md) via cerberus.
