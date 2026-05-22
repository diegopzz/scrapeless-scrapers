# Google Maps — Python surface

Scrape Google Maps place lists and place detail pages using the official
[`scrapeless`](https://pypi.org/project/scrapeless/) Python SDK + Playwright over CDP.

## Setup

```bash
cd browser/python
poetry install
playwright install chromium
```

## Run

```bash
export SCRAPELESS_API_KEY=sk_...

# print to stdout
python run.py

# write results/places.json + results/place.json
SAVE_TEST_RESULTS=true python run.py

# override the sample URLs
GOOGLE_MAPS_SEARCH_QUERY="pizza in New York" SAVE_TEST_RESULTS=true python run.py
```

## Test

```bash
SCRAPELESS_API_KEY=sk_... pytest test.py -v
```

Sample results are in [`results/`](results/). Full field documentation is in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).
