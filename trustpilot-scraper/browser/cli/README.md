# Trustpilot — CLI surface

Scrape Trustpilot category and company pages from the command line with the
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
in-page extractor. Start with a category page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name trustpilot-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the Next.js hydration payload
scrapeless-scraping-browser --session-id "$SID" open "https://www.trustpilot.com/categories/electronics_technology"
scrapeless-scraping-browser --session-id "$SID" wait "script#__NEXT_DATA__"

# run the in-page extractor — its JSON comes back in data.result
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a Trustpilot category (/categories/<slug>) page.
// Returns a JSON string — a list of SearchResult / Business
// (see ../../../DATA_MODEL.md). Mirrors parseHiddenData() +
// `pageProps.businessUnits.businesses` in ../nodejs/trustpilot.mjs.
JSON.stringify(
  (function () {
    const script = document.querySelector("script#__NEXT_DATA__")?.textContent;
    if (!script) return [];
    let data;
    try {
      data = JSON.parse(script);
    } catch (e) {
      return [];
    }
    const businessUnits =
      (data &&
        data.props &&
        data.props.pageProps &&
        data.props.pageProps.businessUnits) ||
      {};
    return businessUnits.businesses ?? [];
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of `SearchResult` (Business), straight from
`props.pageProps.businessUnits.businesses`:

```json
[
  {
    "businessUnitId": "4bdc9828000064000505dc60",
    "stars": 5,
    "identifyingName": "www.flashbay.com",
    "displayName": "Flashbay",
    "numberOfReviews": 19236,
    "trustScore": 5,
    "location": { "address": "Flashbay Inc. ...", "country": "United States" }
  }
]
```

## 4. Scrape a company page

Reuse the same session — `open` a `/review/<domain>` URL and wait for the same hydration payload.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.trustpilot.com/review/www.flashbay.com"
scrapeless-scraping-browser --session-id "$SID" wait "script#__NEXT_DATA__"
# save the companies extractor (a single expression returning a JSON string)
cat > companies.js <<'JS'
// In-page extractor for a Trustpilot company (/review/<domain>) page.
// Returns a JSON string — a list of Company (see ../../../DATA_MODEL.md),
// one entry for the current page. Mirrors parseHiddenData() + parseCompanyData()
// in ../nodejs/trustpilot.mjs.
JSON.stringify(
  (function () {
    const script = document.querySelector("script#__NEXT_DATA__")?.textContent;
    if (!script) return [];
    let data;
    try {
      data = JSON.parse(script);
    } catch (e) {
      return [];
    }
    const pp = (data && data.props && data.props.pageProps) || {};
    return [
      {
        pageUrl: pp.pageUrl ?? null,
        companyDetails: pp.businessUnit ?? null,
        reviews: pp.reviews ?? [],
      },
    ];
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat companies.js)" --json
```

`data.result` is a list of `Company` — one entry for the open page:

```json
[
  {
    "pageUrl": "https://www.trustpilot.com/review/www.flashbay.com",
    "companyDetails": {
      "id": "4bdc9828000064000505dc60",
      "displayName": "Flashbay",
      "identifyingName": "www.flashbay.com",
      "numberOfReviews": 19236,
      "trustScore": 5,
      "stars": 5
    },
    "reviews": []
  }
]
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/trustpilot.mjs`](../nodejs/trustpilot.mjs). Both extractors read
Trustpilot's Next.js hydration payload (`<script id="__NEXT_DATA__">`):

| Extractor | Returns |
| --- | --- |
| `search.js` | list of `SearchResult` (Business) |
| `companies.js` | list of `Company` (the open page) |

`scrape_reviews` is **not** exposed on this surface — it depends on a second pass against
Trustpilot's `/_next/data/<buildId>/review/<host>.json` API, which the in-page `eval` flow doesn't
drive. Use the `nodejs/` or `python/` surface for paginated reviews.

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
