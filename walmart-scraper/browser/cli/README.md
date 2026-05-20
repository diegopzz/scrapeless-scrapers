# Walmart — CLI surface

Scrape Walmart search and product pages from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; each page is extracted in-browser with the
CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

Walmart renders its data into a `__NEXT_DATA__` script blob — there is no DOM scraping. The in-page
extractors parse that blob and apply the same filtering as `parseProduct()` / `parseSearch()` in
[`../nodejs/walmart.mjs`](../nodejs/walmart.mjs). Walmart sits behind PerimeterX, so keep the
session in the `US` proxy country (set below) and expect the occasional "Robot or human?"
interstitial — re-run if `__NEXT_DATA__` is missing.

## 1. Install

```bash
npm install -g scrapeless-scraping-browser
```

`node` is also required — the steps below use it to pull values out of the CLI's JSON envelope
(`jq` works too, if preferred).

## 2. Set your API key

```bash
export SCRAPELESS_API_KEY=sk_...      # sign up at https://app.scrapeless.com
```

## 3. Scrape your first page

Every scrape is the same four moves: open a session, navigate, wait for a stable marker, run an
in-page extractor. Start with a product page. Create the session pinned to a `US` proxy so Walmart
serves US pricing and the React data layer hydrates.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name walmart-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the React data blob to materialise
scrapeless-scraping-browser --session-id "$SID" open "https://www.walmart.com/ip/1736740710"
scrapeless-scraping-browser --session-id "$SID" wait "script#__NEXT_DATA__"

# run the in-page extractor — its JSON comes back in data.result
# save the products extractor (a single expression returning a JSON string)
cat > products.js <<'JS'
// In-page extractor for a Walmart product (/ip/<id>) page.
// Returns a JSON string — a list of Product wrappers (see ../../../DATA_MODEL.md),
// one entry for the current page. Mirrors nextData() + parseProduct() in
// ../nodejs/walmart.mjs: data comes from the __NEXT_DATA__ blob, the product
// object is filtered to WANTED_PRODUCT_KEYS, reviews are passed through raw.
JSON.stringify(
  (function () {
    const WANTED_PRODUCT_KEYS = [
      "availabilityStatus",
      "averageRating",
      "brand",
      "id",
      "imageInfo",
      "manufacturerName",
      "name",
      "orderLimit",
      "orderMinLimit",
      "priceInfo",
      "shortDescription",
      "type",
    ];
    const raw = document.querySelector("script#__NEXT_DATA__")?.textContent;
    if (!raw) return [];
    let data;
    try {
      data = JSON.parse(raw);
    } catch (e) {
      return [];
    }
    let productRaw, reviewsRaw;
    try {
      productRaw = data.props.pageProps.initialData.data.product;
      reviewsRaw = data.props.pageProps.initialData.data.reviews;
    } catch (e) {
      return [];
    }
    if (!productRaw) return [];
    const product = {};
    for (const k of WANTED_PRODUCT_KEYS) {
      if (k in productRaw) product[k] = productRaw[k];
    }
    return [{ product, reviews: reviewsRaw }];
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat products.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `{ product, reviews }` wrapper. `product` is filtered to the
`wanted_product_keys`; `reviews` is the raw `initialData.data.reviews` blob:

```json
{
  "product": {
    "availabilityStatus": "IN_STOCK",
    "averageRating": 4.8,
    "brand": "PlayStation",
    "id": "4S6KN6TWU0A0",
    "imageInfo": { "allImages": [{ "url": "https://i5.walmartimages.com/..." }] },
    "name": "Sony PlayStation 5 Video Game Console",
    "priceInfo": { "currentPrice": { "price": 499.0 } },
    "type": "Video Game Consoles"
  },
  "reviews": { "...": "raw reviews blob" }
}
```

## 4. Scrape a search page

Reuse the same session — just `open` a search URL and wait for the same `__NEXT_DATA__` marker. The
extractor returns `searchResult.itemStacks[0].items` verbatim.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.walmart.com/search?q=laptop&page=1&best_seller=best_seller&affinityOverride=default"
scrapeless-scraping-browser --session-id "$SID" wait "script#__NEXT_DATA__"
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a Walmart search results page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
// Mirrors nextData() + parseSearch() in ../nodejs/walmart.mjs: items come
// verbatim from initialData.searchResult.itemStacks[0].items.
JSON.stringify(
  (function () {
    const raw = document.querySelector("script#__NEXT_DATA__")?.textContent;
    if (!raw) return [];
    let data;
    try {
      data = JSON.parse(raw);
    } catch (e) {
      return [];
    }
    try {
      const stack =
        data.props.pageProps.initialData.searchResult.itemStacks[0];
      return stack.items ?? [];
    } catch (e) {
      return [];
    }
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
```

`data.result` is a list of `SearchResult` (verbatim Walmart item objects — the validator only
enforces a string `id`):

```json
[
  {
    "id": "16ITX152FNYH",
    "usItemId": "19652372462",
    "name": "Apple MacBook Neo 13-inch ...",
    "priceInfo": { "...": "..." },
    "imageInfo": { "...": "..." },
    "canonicalUrl": "/ip/..."
  }
]
```

## 5. Output shape

Each `eval/*.js` expression returns a JSON string, kept in lockstep with the parsers in
[`../nodejs/walmart.mjs`](../nodejs/walmart.mjs):

| Extractor | Returns |
| --- | --- |
| `search.js` | list of `SearchResult` (raw item objects) |
| `product.js` | one `{ product, reviews }` wrapper |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).
