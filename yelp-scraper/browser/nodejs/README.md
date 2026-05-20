# Yelp — Node.js surface

ESM Yelp scraper built on the official [`@scrapeless-ai/sdk`](https://www.npmjs.com/package/@scrapeless-ai/sdk) + puppeteer-core over CDP.

## Install

```bash
npm install
```

## Run

```bash
export SCRAPELESS_API_KEY=sk_...
node run.mjs                                # print to stdout
SAVE_TEST_RESULTS=true node run.mjs         # write to results/*.json
```

## Test

```bash
SCRAPELESS_API_KEY=sk_... npm test
```

Validates output against [`../../DATA_MODEL.md`](../../DATA_MODEL.md) via zod.
