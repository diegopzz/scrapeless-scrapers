# Zillow — CLI surface

Scrape Zillow property detail and search pages from the command line with the
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

Zillow is DataDome-protected and US-geo-fenced. The `nodejs/` and `python/` surfaces pin a US
residential proxy at session creation — create your Scrapeless cloud session in a US region for
parity (per-call identity flags are ignored server-side).

## 3. Scrape a property page

Every scrape is the same four moves: open a session, navigate, wait for a stable marker, run an
in-page extractor. Start with a property detail page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name zillow-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the embedded Next.js data
scrapeless-scraping-browser --session-id "$SID" open "https://www.zillow.com/homedetails/661-Lakeview-Ave-San-Francisco-CA-94112/15192198_zpid/"
scrapeless-scraping-browser --session-id "$SID" wait "script#__NEXT_DATA__"

# run the in-page extractor — its JSON comes back in data.result
# save the property extractor (a single expression returning a JSON string)
cat > property.js <<'JS'
// In-page extractor for a Zillow property (homedetails) page.
// Returns a JSON string — a single Property (see ../../../DATA_MODEL.md).
//
// Mirrors parseProperty() in ../nodejs/zillow.mjs: modern listings embed
// `__NEXT_DATA__` containing a `gdpClientCache` blob; legacy ones embed
// `hdpApolloPreloadedData`. Both unwrap to the same `property` object.
JSON.stringify(
  (function () {
    const nextText = document
      .querySelector("script#__NEXT_DATA__")
      ?.textContent;
    if (nextText) {
      const data = JSON.parse(nextText);
      const cache = JSON.parse(
        data.props.pageProps.componentProps.gdpClientCache
      );
      const firstKey = Object.keys(cache)[0];
      return cache[firstKey].property;
    }
    const apolloText = document
      .querySelector("script#hdpApolloPreloadedData")
      ?.textContent;
    if (!apolloText) throw new Error("no property JSON found on page");
    const apollo = JSON.parse(JSON.parse(apolloText).apiCache);
    for (const k of Object.keys(apollo)) {
      if (k.includes("ForSale")) return apollo[k].property;
    }
    throw new Error("no ForSale entry in hdpApolloPreloadedData");
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat property.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `Property` object — modern listings embed it in `__NEXT_DATA__` under
`props.pageProps.componentProps.gdpClientCache` (legacy listings use `hdpApolloPreloadedData`):

```json
{
  "zpid": 15192198,
  "streetAddress": "661 Lakeview Ave",
  "city": "San Francisco",
  "state": "CA",
  "zipcode": "94112",
  "homeStatus": "FOR_SALE",
  "bedrooms": 3,
  "bathrooms": 2,
  "price": 1295000
}
```

the extractor wraps this object in a one-element list so the saved fixture stays shape-identical with the
`scrape_properties` output of the other surfaces.

## 4. Scrape a search page

Reuse the same session. Zillow's SERP seeds a `queryState` into `__NEXT_DATA__`; the extractor reads
it, then re-issues it as a `PUT` to `/async-create-search-page-state` **from inside the page** (so
the session's TLS + DataDome cookies stay sticky) and returns the first page's `listResults`.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.zillow.com/san-francisco-ca/?searchQueryState=%7B%22pagination%22%3A%7B%7D%7D"
scrapeless-scraping-browser --session-id "$SID" wait "script#__NEXT_DATA__"
scrapeless-scraping-browser --session-id "$SID" eval "<contents of the SEARCH_JS extractor>" --json
```

`data.result` is a list of `SearchResult` (one entry per `cat1.searchResults.listResults` item):

```json
[
  {
    "zpid": "15192198",
    "detailUrl": "/homedetails/661-Lakeview-Ave-San-Francisco-CA-94112/15192198_zpid/",
    "statusType": "FOR_SALE",
    "price": "$1,295,000",
    "address": "661 Lakeview Ave, San Francisco, CA 94112"
  }
]
```

## 5. Output shape

Each extractor is a single expression that returns a JSON string, kept in
lockstep with the selectors in [`../nodejs/zillow.mjs`](../nodejs/zillow.mjs):

| Extractor    | Returns |
| ------------ | --- |
| `PROPERTIES_JS` | one `Property` |
| `SEARCH_JS`     | list of `SearchResult` |

The `search` extractor is async — it returns a Promise resolving to the JSON string, which the CLI's
`eval` awaits. Multi-page search pagination is implemented on the `nodejs/` and `python/` surfaces
(`scrape_search(url, max_pages)`); the CLI surface emits the first page.

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
