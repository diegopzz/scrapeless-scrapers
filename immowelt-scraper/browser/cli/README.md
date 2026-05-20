# Immowelt — CLI surface

Scrape Immowelt search and property (expose) pages from the command line with the
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
in-page extractor. Start with a search page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name immowelt-cli --ttl 300 --proxy-country DE --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the page body to render
scrapeless-scraping-browser --session-id "$SID" open "https://www.immowelt.de/classified-search?distributionTypes=Buy&estateTypes=Apartment&locations=AD08DE6345"
scrapeless-scraping-browser --session-id "$SID" wait "body"

# run the in-page extractor — its JSON comes back in data.result
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for an Immowelt search results page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
// Reads the `classified-serp-init-data` blob embedded in a script tag. Modern
// Immowelt LZ-String + Base64 encodes the payload; we use the page's own
// window.LZString when present and fall back to the legacy plain path.
JSON.stringify(
  (function () {
    const scripts = Array.from(document.querySelectorAll("script"));
    for (const s of scripts) {
      const txt = s.textContent || "";
      if (!txt.includes("classified-serp-init-data")) continue;
      const m = /JSON\.parse\("(.+?)"\)/s.exec(txt);
      if (!m) continue;
      try {
        const inner = JSON.parse(`"${m[1]}"`);
        let data = JSON.parse(inner);
        let payloadStr = null;
        if (
          data?.data &&
          typeof data.data["classified-serp-init-data"] === "string"
        ) {
          payloadStr = data.data["classified-serp-init-data"];
        } else if (data?.compressed && typeof data.compressed === "string") {
          payloadStr = data.compressed;
        }
        if (payloadStr) {
          let dec = null;
          if (
            window.LZString &&
            typeof window.LZString.decompressFromBase64 === "function"
          ) {
            dec = window.LZString.decompressFromBase64(payloadStr);
          }
          if (dec) data = JSON.parse(dec);
        }
        const classifieds =
          data?.pageProps?.classifiedsData ?? data?.classifiedsData;
        if (classifieds) {
          return Array.isArray(classifieds)
            ? classifieds
            : Object.values(classifieds);
        }
      } catch (e) {}
    }
    return [];
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of `SearchResult` — entries from the `classified-serp-init-data` blob
(`search.js` uses the page's own `window.LZString` to decompress it):

```json
[
  {
    "brand": "immowelt",
    "id": "26PM3RRAK9LU",
    "status": "Published",
    "hasAIEnrichment": true,
    "metadata": { "id": "26PM3RRAK9LU", "creationDate": "2026-05-07T13:37:39.23Z" }
  }
]
```

## 4. Scrape a property listing

Reuse the same session — just `open` an expose URL and wait for the page body.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.immowelt.de/expose/k2ag632"
scrapeless-scraping-browser --session-id "$SID" wait "body"
# save the properties extractor (a single expression returning a JSON string)
cat > properties.js <<'JS'
// In-page extractor for an Immowelt property detail (expose) page.
// Returns a JSON string — a single PropertyResult (see ../../../DATA_MODEL.md).
// Reads the `__UFRN_LIFECYCLE_SERVERREQUEST__` payload embedded in a script tag
// and projects the upstream keys: sections, id, brand, tags, contactSections.
JSON.stringify(
  (function () {
    const SEARCH_KEYS = [
      "sections",
      "id",
      "brand",
      "tags",
      "contactSections",
    ];

    function findListing(node) {
      if (node && typeof node === "object" && !Array.isArray(node)) {
        if ("sections" in node && "id" in node) return node;
        for (const v of Object.values(node)) {
          const found = findListing(v);
          if (found) return found;
        }
      } else if (Array.isArray(node)) {
        for (const v of node) {
          const found = findListing(v);
          if (found) return found;
        }
      }
      return null;
    }

    const scripts = Array.from(document.querySelectorAll("script"));
    for (const s of scripts) {
      const txt = s.textContent || "";
      if (!txt.includes("UFRN_LIFECYCLE_SERVERREQUEST")) continue;
      const m = /JSON\.parse\("(.+?)"\)/s.exec(txt);
      if (!m) continue;
      try {
        const inner = JSON.parse(`"${m[1]}"`);
        const data = JSON.parse(inner);
        const listing = findListing(data);
        if (listing) {
          return Object.fromEntries(
            SEARCH_KEYS.map((k) => [k, listing[k]])
          );
        }
      } catch (e) {}
    }
    return {};
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat properties.js)" --json
```

`data.result` is a single `PropertyResult` — the `sections`, `id`, `brand`, `tags`,
`contactSections` keys projected from the `__UFRN_LIFECYCLE_SERVERREQUEST__` payload:

```json
{
  "sections": {
    "location": {
      "address": { "country": "DE", "city": "München", "zipCode": "81475", "street": "Oberbrunner Straße 20" }
    }
  },
  "id": "...",
  "brand": "immowelt"
}
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
extraction in [`../nodejs/immowelt.mjs`](../nodejs/immowelt.mjs):

| Extractor | Returns |
| --- | --- |
| `search.js` | list of `SearchResult` |
| `properties.js` | one `PropertyResult` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
