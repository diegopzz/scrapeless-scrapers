# Flipkart — Python surface

Scrape Flipkart product and search pages using the official
[Scrapeless Python SDK](https://pypi.org/project/scrapeless/) + Playwright over CDP.

## 1. Install

```bash
pip install poetry
cd browser/python
poetry install
playwright install chromium
```

## 2. Set your API key

```bash
export SCRAPELESS_API_KEY=sk_...      # sign up at https://app.scrapeless.com
```

## 3. Run

```bash
# print JSON to stdout
poetry run python run.py

# write results/*.json
SAVE_TEST_RESULTS=true poetry run python run.py

# custom URLs
FK_SAMPLE_PRODUCT_URL=https://www.flipkart.com/samsung-galaxy-s24/p/itm... \
FK_SAMPLE_SEARCH_URL=https://www.flipkart.com/search?q=samsung+galaxy+s24 \
  poetry run python run.py
```

## 4. Test

```bash
poetry run pytest test.py -v
```

## 5. API

```python
from flipkart import scrape_product, scrape_search

product = await scrape_product("https://www.flipkart.com/apple-iphone-16-white-128-gb/p/itm7c0281cd247be")
results = await scrape_search("https://www.flipkart.com/search?q=iphone+16&marketplace=FLIPKART")
```

See [`../../DATA_MODEL.md`](../../DATA_MODEL.md) for field definitions. Sample payloads are in [`results/`](results/).
