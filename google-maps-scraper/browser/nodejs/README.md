# Google Maps — Node.js surface

Scrape Google Maps place lists and place detail pages using the official
[`@scrapeless-ai/sdk`](https://www.npmjs.com/package/@scrapeless-ai/sdk) + puppeteer-core over CDP.

## Setup

```bash
cd browser/nodejs
pnpm install
```

## Run

```bash
export SCRAPELESS_API_KEY=sk_...

# print to stdout
node run.mjs

# write results/places.json + results/place.json
SAVE_TEST_RESULTS=true node run.mjs

# override the sample
GOOGLE_MAPS_SEARCH_QUERY="pizza in New York" SAVE_TEST_RESULTS=true node run.mjs
```

Sample results are in [`results/`](results/). Full field documentation is in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).
