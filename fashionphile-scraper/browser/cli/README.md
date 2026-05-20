# Fashionphile — CLI surface

Scrape Fashionphile product listings from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; each page is extracted in-browser with the
CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

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
in-page extractor. Fashionphile exposes the same JSON the storefront consumes at
`/products/<slug>.json` — point the browser at that endpoint and the page body is raw JSON.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name fashionphile-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate to the /products/<slug>.json endpoint, then wait for the body
scrapeless-scraping-browser --session-id "$SID" open "https://www.fashionphile.com/products/bottega-veneta-nappa-twisted-padded-intrecciato-curve-slide-sandals-36-black-1048096.json"
scrapeless-scraping-browser --session-id "$SID" wait "body"

# run the in-page extractor — its JSON comes back in data.result
# save the products extractor (a single expression returning a JSON string)
cat > products.js <<'JS'
// In-page extractor for a Fashionphile /products/<slug>.json endpoint.
// Returns a JSON string — a single Product (see ../../../DATA_MODEL.md).
// Fashionphile exposes the same JSON the storefront consumes; run.sh rewrites
// the /p/<slug> page URL to /products/<slug>.json before navigating, so the
// page body is raw JSON.
JSON.stringify(
  (function () {
    const body = (document.body?.innerText || "").trim();
    if (!body) return null;
    let data;
    try {
      data = JSON.parse(body);
    } catch (e) {
      return null;
    }
    if (data && typeof data === "object" && data.product) return data.product;
    return data;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat products.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a single `Product`, lifted verbatim from the JSON body:

```json
{
  "id": 10641393582383,
  "title": "Nappa Twisted Padded Intrecciato Curve Slide Sandals 36 Black",
  "handle": "bottega-veneta-nappa-twisted-padded-intrecciato-curve-slide-sandals-36-black-1048096",
  "vendor": "Bottega Veneta",
  "product_type": "Accessories",
  "variants": [
    { "id": 51473136943407, "sku": "253613", "price": "450.00", "compare_at_price": "450.00" }
  ],
  "tags": ""
}
```

## 4. Output shape

The single `eval/*.js` file is a one-line expression that returns a JSON string, kept in lockstep
with the data shape in [`../nodejs/fashionphile.mjs`](../nodejs/fashionphile.mjs):

| Extractor | Returns |
| --- | --- |
| `products.js` | one `Product` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
