# Nordstrom — CLI surface

Scrape Nordstrom product and search pages from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; each page is extracted in-browser with the
CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

Nordstrom is a React/Apollo app that ships its product and search data as a JSON blob assigned to
`window.__INITIAL_CONFIG__` inside a `<script>` tag. The extractors below read that blob (rather than
DOM selectors), mirroring `findHiddenData` + `nestedLookup` + `parseProduct` in
[`../nodejs/nordstorm.mjs`](../nodejs/nordstorm.mjs). (The folder keeps upstream's `nordstorm` typo —
the site itself is nordstrom.com.)

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

Every scrape is the same four moves: open a session, navigate, wait for the page to render, run an
in-page extractor. Start with a product page. Because the data lives in `__INITIAL_CONFIG__` (present
once the page hydrates), wait for `body` and give the SPA a moment to settle.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name nordstorm-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then let the React app hydrate the __INITIAL_CONFIG__ blob
scrapeless-scraping-browser --session-id "$SID" open "https://www.nordstrom.com/s/nike-air-max-90-sneaker-men/6549520"
scrapeless-scraping-browser --session-id "$SID" wait body
scrapeless-scraping-browser --session-id "$SID" wait 2500

# run the in-page extractor — its JSON comes back in data.result
# save the products extractor (a single expression returning a JSON string)
cat > products.js <<'JS'
// In-page extractor for a Nordstrom product page.
// Returns a JSON string — a list of Product (see ../../../DATA_MODEL.md). The
// CLI surface scrapes a single product URL, so the list holds one entry.
// Nordstrom ships its data inside an inline `__INITIAL_CONFIG__` script blob;
// this mirrors `findHiddenData` + `parseProduct` in ../nodejs/nordstorm.mjs.
// (Folder name keeps the upstream typo "nordstorm" — the site is nordstrom.com.)
JSON.stringify(
  [(function () {
    // findHiddenData: locate the <script> carrying __INITIAL_CONFIG__ and
    // parse the JSON assigned after the first `=`.
    let raw = "";
    document.querySelectorAll("script").forEach((el) => {
      const t = el.textContent || "";
      if (t.includes("__INITIAL_CONFIG__")) raw = t;
    });
    if (!raw) throw new Error("__INITIAL_CONFIG__ script not found");
    const after = raw.split("=").slice(1).join("=").trim().replace(/;$/, "");
    const data = JSON.parse(after);

    // nestedLookup: collect every value stored under `key` anywhere in the tree.
    const nestedLookup = (key, obj, out) => {
      out = out || [];
      if (obj && typeof obj === "object") {
        for (const k of Object.keys(obj)) {
          if (k === key) out.push(obj[k]);
          nestedLookup(key, obj[k], out);
        }
      }
      return out;
    };

    const stylesById = nestedLookup("stylesById", data);
    const product = Object.values(stylesById[0])[0];

    // parseProduct
    const parsed = {
      id: product.id ?? null,
      title: product.productTitle ?? null,
      type: product.productTypeName ?? null,
      typeParent: product.productTypeParentName ?? null,
      ageGroups: product.ageGroups ?? null,
      reviewAverageRating: product.reviewAverageRating ?? null,
      numberOfReviews: product.numberOfReviews ?? null,
      brand: product.brand ?? null,
      description: product.sellingStatement ?? null,
      features: product.features ?? null,
      gender: product.gender ?? null,
      isAvailable: product.isAvailable ?? null,
    };
    const pricesBySku = product.price ? product.price.bySkuId : null;
    const colorsById = product.filters.color.byId;
    parsed.media = [];
    for (const item of product.mediaExperiences.carouselsByColor) {
      parsed.media.push({
        colorCode: item.colorCode ?? null,
        colorName: item.colorName ?? null,
        urls: item.orderedShots.map((i) => i.url),
      });
    }
    parsed.variants = {};
    for (const [sku, skuData] of Object.entries(product.skus.byId)) {
      const v = {
        id: skuData.id ?? null,
        sizeId: skuData.sizeId ?? null,
        colorId: skuData.colorId ?? null,
        totalQuantityAvailable: skuData.totalQuantityAvailable ?? null,
      };
      v.price = pricesBySku ? pricesBySku[sku]?.regular?.price ?? null : null;
      const color = colorsById[v.colorId];
      v.color = color
        ? {
            id: color.id ?? null,
            value: color.value ?? null,
            sizes: color.isAvailableWith ?? null,
            mediaIds: color.styleMediaIds ?? null,
            swatch: color.swatchMedia?.desktop ?? null,
          }
        : null;
      parsed.variants[sku] = v;
    }
    return parsed;
  })()]
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat products.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `Product` object:

```json
{
  "id": "7786657",
  "title": "BP. Fleece Hoodie",
  "type": "Sweatshirt/Hoody/Zipfront",
  "typeParent": "Tops",
  "ageGroups": ["ADULT"],
  "brand": { "brandName": "BP.", "imsBrandId": 2601 },
  "description": "Soften your vibe in this sporty hoodie ...",
  "features": ["Ribbed cuffs and hem", "..."],
  "gender": "Male",
  "isAvailable": true,
  "media": [{ "colorCode": "001", "colorName": "BLACK FADED", "urls": ["https://n.nordstrommedia.com/it/..."] }],
  "variants": { "<sku>": { "id": "...", "sizeId": "...", "colorId": "...", "totalQuantityAvailable": 3, "price": "...", "color": { "id": "...", "value": "...", "sizes": [], "mediaIds": [], "swatch": "..." } } }
}
```

## 4. Scrape a search page

Reuse the same session — `open` a keyword search URL, wait for it to render, and run the search
extractor. Nordstrom returns the raw `productResults.productsById` values, so every key the site
ships is preserved (no projection).

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.nordstrom.com/sr?origin=keywordsearch&keyword=indigo"
scrapeless-scraping-browser --session-id "$SID" wait body
scrapeless-scraping-browser --session-id "$SID" wait 2500
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a Nordstrom search / category results page.
// Returns a JSON string — a list of SearchProduct (see ../../../DATA_MODEL.md).
// Nordstrom ships its data inside an inline `__INITIAL_CONFIG__` script blob;
// this mirrors `findHiddenData` + the search half of ../nodejs/nordstorm.mjs.
// (Folder name keeps the upstream typo "nordstorm" — the site is nordstrom.com.)
JSON.stringify(
  (function () {
    // findHiddenData: locate the <script> carrying __INITIAL_CONFIG__ and
    // parse the JSON assigned after the first `=`.
    let raw = "";
    document.querySelectorAll("script").forEach((el) => {
      const t = el.textContent || "";
      if (t.includes("__INITIAL_CONFIG__")) raw = t;
    });
    if (!raw) return [];
    const after = raw.split("=").slice(1).join("=").trim().replace(/;$/, "");
    let data;
    try {
      data = JSON.parse(after);
    } catch (e) {
      return [];
    }

    // nestedLookup: collect every value stored under `key` anywhere in the tree.
    const nestedLookup = (key, obj, out) => {
      out = out || [];
      if (obj && typeof obj === "object") {
        for (const k of Object.keys(obj)) {
          if (k === key) out.push(obj[k]);
          nestedLookup(key, obj[k], out);
        }
      }
      return out;
    };

    const results = nestedLookup("productResults", data)[0];
    if (!results || !results.productsById) return [];
    // Raw pass-through to match the python/nodejs surface (see DATA_MODEL.md).
    return Object.values(results.productsById);
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
```

`data.result` is a list of `SearchProduct` (raw, unprojected):

```json
[
  {
    "id": 7786657,
    "productName": "Fleece Hoodie",
    "brandName": "BP.",
    "price": { "...": "..." },
    "rmsImage": { "...": "..." },
    "productPageUrl": "/s/bp-fleece-hoodie/7786657"
  }
]
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
parsers in [`../nodejs/nordstorm.mjs`](../nodejs/nordstorm.mjs):

| Extractor | Returns |
| --- | --- |
| `product.js` | one `Product` (projected through `parseProduct`) |
| `search.js` | list of `SearchProduct` (raw `productsById` values) |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). A live-verified `Product` sample is in
[`results/product.json`](results/); capture the `search` payload by running the search extractor yourself.
