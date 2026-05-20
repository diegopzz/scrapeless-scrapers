# Vestiaire Collective — CLI surface

Scrape Vestiaire Collective listing pages from the command line with the
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

## 3. Scrape a listing page

Every scrape is the same four moves: open a session, navigate, wait for a stable marker, run an
in-page extractor. Vestiaire hydrates the full product object into `<script id="__NEXT_DATA__">`
under `props.pageProps.product`.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name vestiairecollective-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the Next.js hydration payload
scrapeless-scraping-browser --session-id "$SID" open "https://us.vestiairecollective.com/men-clothing/jackets/louis-vuitton/camel-polyester-louis-vuitton-jacket-66935196.shtml"
scrapeless-scraping-browser --session-id "$SID" wait "script#__NEXT_DATA__"

# run the in-page extractor — its JSON comes back in data.result
# save the products extractor (a single expression returning a JSON string)
cat > products.js <<'JS'
// In-page extractor for a Vestiaire Collective listing (/.../*.shtml) page.
// Returns a JSON string — a list of Product (see ../../../DATA_MODEL.md), one
// entry for the current page. Mirrors findHiddenData() +
// `props.pageProps.product` in ../nodejs/vestiairecollective.mjs.
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
    const product =
      data && data.props && data.props.pageProps && data.props.pageProps.product;
    return product ? [product] : [];
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat products.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `Product` object, read from `__NEXT_DATA__.props.pageProps.product`:

```json
{
  "id": "66935196",
  "name": "Camel Polyester Louis Vuitton Jacket",
  "price": { "currency": "USD", "cents": 350000, "formatted": "$3,500" },
  "description": "...",
  "likeCount": 12,
  "brand": { "id": 50, "type": "brand", "name": "Louis Vuitton" }
}
```

the extractor wraps this object in a one-element list so the saved fixture stays shape-identical with the
`scrape_products` output of the other surfaces.

## 4. Output shape

The the extractor `PRODUCTS_JS` extractor is a single expression that returns a JSON string,
kept in lockstep with `findHiddenData()` / `scrapeProducts()` in
[`../nodejs/vestiairecollective.mjs`](../nodejs/vestiairecollective.mjs):

| Extractor    | Returns |
| ------------ | --- |
| `PRODUCTS_JS` | one `Product` |

The `search` kind (emitted by the `nodejs/` and `python/` surfaces) is built by intercepting the
page's own `POST` to `search.vestiairecollective.com/v1/product/search` and replaying it with
pagination — that requires network capture of the request body + headers, which a synchronous
in-page `eval` cannot retroactively observe. Use the `nodejs/` or `python/` surface
(`scrape_search(url, max_pages)`) for search.

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
