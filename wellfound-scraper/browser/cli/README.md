# Wellfound — CLI surface

Scrape Wellfound (formerly AngelList) search and company-profile pages from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; each page is extracted in-browser with the
CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

Wellfound is a Next.js/Apollo app: public company and search data is hydrated into
`<script id="__NEXT_DATA__">` under `props.pageProps.apolloState.data`. The extractor walks that
Apollo graph, resolves `__ref` pointers, and emits every `Startup` / `StartupResult` node verbatim —
same keys, same casing (including the upstream `remtoe` typo on job listings).

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
in-page extractor. Start with a company profile.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name wellfound-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the Next.js data script to render
scrapeless-scraping-browser --session-id "$SID" open "https://wellfound.com/company/openai"
scrapeless-scraping-browser --session-id "$SID" wait "script#__NEXT_DATA__"

# run the in-page extractor — its JSON comes back in data.result
# save the companies extractor (a single expression returning a JSON string)
cat > companies.js <<'JS'
// In-page extractor for a Wellfound company page (/company/<slug>).
// Returns a JSON string — a list of CompanyData (see ../../../DATA_MODEL.md).
// Mirrors extractApolloState() + parseCompany() in ../nodejs/wellfound.mjs:
// walks the Apollo cache under props.pageProps.apolloState.data, resolving
// __ref pointers, and emits every Startup / StartupResult node.
JSON.stringify(
  (function () {
    const raw = document.querySelector("script#__NEXT_DATA__")?.textContent;
    if (!raw) return [];
    let graph;
    try {
      const data = JSON.parse(raw);
      graph =
        (data &&
          data.props &&
          data.props.pageProps &&
          data.props.pageProps.apolloState &&
          data.props.pageProps.apolloState.data) ||
        {};
    } catch (e) {
      return [];
    }

    const isRef = (v) =>
      v &&
      typeof v === "object" &&
      !Array.isArray(v) &&
      Object.keys(v).length === 1 &&
      "__ref" in v;
    const resolve = (value) => {
      if (isRef(value)) return resolve(graph[value.__ref] ?? {});
      if (Array.isArray(value)) return value.map((v) => resolve(v));
      if (value && typeof value === "object") {
        const out = {};
        for (const [k, v] of Object.entries(value)) out[k] = resolve(v);
        return out;
      }
      return value;
    };

    const out = [];
    for (const [key, node] of Object.entries(graph)) {
      if (typeof node !== "object" || node === null) continue;
      if (!key.startsWith("Startup:") && !key.startsWith("StartupResult:"))
        continue;
      out.push(resolve(node));
    }
    return out;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat companies.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

Both surfaces share one extractor (`$COMPANY_JS` — the `parseCompany` port that walks the Apollo
graph), so `eval` is run with the same JS on either page type. `data.result` is a list of
`CompanyData`. On a company profile it holds the single `Startup` node (plus any related companies
Apollo cached):

```json
[
  {
    "__typename": "Startup",
    "id": "943259",
    "name": "OpenAI",
    "slug": "openai",
    "companySize": "SIZE_501_1000",
    "highConcept": "Discovering and enacting the path to safe artificial general intelligence",
    "logoUrl": "https://photos.wellfound.com/startups/i/943259-...-thumb_jpg.jpg",
    "badges": [{ "__typename": "Badge", "label": "Actively Hiring" }],
    "highlightedJobListings": [{ "id": "...", "title": "...", "slug": "...", "remtoe": false }]
  }
]
```

## 4. Scrape a search page

Reuse the same session — `open` a `/role/l/<role>/<city>` URL and wait for the same Next.js data
script, then run the **same** extractor.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://wellfound.com/role/l/engineer/san-francisco"
scrapeless-scraping-browser --session-id "$SID" wait "script#__NEXT_DATA__"
scrapeless-scraping-browser --session-id "$SID" eval "$(cat companies.js)" --json
```

`data.result` is a list of `CompanyData` — one `StartupResult` node per result card:

```json
[
  {
    "__typename": "StartupResult",
    "id": "1073841",
    "name": "...",
    "slug": "...",
    "companySize": "...",
    "highConcept": "...",
    "logoUrl": "...",
    "badges": [{ "__typename": "Badge", "label": "Actively Hiring" }],
    "highlightedJobListings": []
  }
]
```

> `/role/<role>` without a city returns a 200-but-empty interstitial; always use
> `/role/l/<role>/<city>` for fully-rendered search results.

## 5. Output shape

A single in-page extractor (`$COMPANY_JS`) is used for both surfaces. It is a single expression that
returns a JSON string, kept in lockstep with `extractApolloState` + `parseCompany` + `resolve` in
[`../nodejs/wellfound.mjs`](../nodejs/wellfound.mjs):

| Surface (page) | Extractor | Returns |
| --- | --- | --- |
| `/company/<slug>` | `parseCompany` (shared) | list of `CompanyData` (one `Startup` node + related) |
| `/role/l/<role>/<city>` | `parseCompany` (shared) | list of `CompanyData` (one `StartupResult` per card) |

Apollo surfaces additional fields verbatim when present. Full field tables — types, which are
required, where each comes from — are in [`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads
are in [`results/`](results/).
