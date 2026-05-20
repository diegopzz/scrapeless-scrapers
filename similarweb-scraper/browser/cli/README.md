# Similarweb — CLI surface

Scrape Similarweb website overview, head-to-head compare, and trending category pages from the
command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; each page is extracted in-browser with the
CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

Similarweb is a React SPA. The richest payload lives in `window.__APP_DATA__` — a JSON blob the app
boots from — which is more stable than the rendered DOM, so the website / compare extractors read
that global directly. The trending extractor reads the page's `script#dataset-json-ld` JSON-LD
block.

> The `nodejs/` `scrapeSitemaps` surface is **not** exposed here. It downloads a gzip-compressed
> `.xml.gz` sitemap and gunzips the raw bytes — that cannot run as a simple in-page `eval`, so it is
> intentionally skipped. Use the `nodejs/` or `python/` surface when you need sitemap URLs.

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
in-page extractor. Start with a website overview page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name similarweb-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the SPA to render the site header
scrapeless-scraping-browser --session-id "$SID" open "https://www.similarweb.com/website/google.com/"
scrapeless-scraping-browser --session-id "$SID" wait "[data-test-id=website-name], h1"

# run the in-page extractor — its JSON comes back in data.result
# save the website extractor (a single expression returning a JSON string)
cat > website.js <<'JS'
// In-page extractor for a Similarweb website overview page.
// Returns a JSON string — a list with one Website object (see ../../../DATA_MODEL.md).
//
// Similarweb is a React SPA whose richest payload is assigned to the
// `window.__APP_DATA__` global by an inline script. Read it straight off the
// window — no DOM scraping or regex needed. `scrape_website` returns a list
// (one entry per domain); the CLI opens one domain per run, so this emits a
// single-element list to keep the shape identical.
JSON.stringify(
  (function () {
    const data = window.__APP_DATA__ || null;
    const layoutData = data?.layout?.data ?? {};
    return [layoutData];
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat website.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`$WEBSITE_JS` is the one-line extractor; it returns
`window.__APP_DATA__.layout.data` for the domain. `data.result` is one `Website` object:

```json
{
  "domain": "google.com",
  "overview": { "globalRank": { "value": 1 }, "monthlyVisits": {} },
  "traffic": {},
  "trafficSources": {},
  "ranking": {},
  "demographics": {},
  "geography": {},
  "competitors": {},
  "keywords": {}
}
```

## 4. Compare two domains

Reuse the same session — `open` a `…/website/<a>/vs/<b>/` compare URL and wait for the header.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.similarweb.com/website/google.com/vs/youtube.com/"
scrapeless-scraping-browser --session-id "$SID" wait "[data-test-id=website-name], h1"

# save the website_compare extractor (returns a JSON string — a CompareResult)
cat > website_compare.js <<'JS'
// In-page extractor for a Similarweb compare page.
// Returns a JSON string — a CompareResult { [domainA]: WebsiteSubset, [domainB]: WebsiteSubset }.
// Reads window.__APP_DATA__, lifts layout.data.compareCompetitor (falling back to layout.data),
// and slices the per-domain WebsiteSubset. Domains are recovered from /website/<a>/vs/<b>/.
JSON.stringify(
  (function () {
    function subset(obj) {
      if (!obj) return {};
      return {
        overview: obj.overview,
        traffic: obj.traffic,
        trafficSources: obj.trafficSources,
        ranking: obj.ranking,
        demographics: obj.demographics,
        geography: obj.geography,
      };
    }
    const m = location.pathname.match(/\/website\/([^/]+)\/vs\/([^/]+)\/?/);
    if (!m) throw new Error("similarweb: not a compare URL (/website/<a>/vs/<b>/)");
    const firstDomain = m[1];
    const secondDomain = m[2];
    const data = window.__APP_DATA__ || null;
    const layout = data?.layout?.data ?? {};
    const compare = layout?.compareCompetitor ?? layout;
    return {
      [firstDomain]: subset(compare[firstDomain] ?? compare),
      [secondDomain]: subset(compare[secondDomain] ?? {}),
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat website_compare.js)" --json
```

`data.result` is `{ [firstDomain]: WebsiteSubset, [secondDomain]: WebsiteSubset }` — each subset is
`overview`, `traffic`, `trafficSources`, `ranking`, `demographics`, `geography`:

```json
{
  "google.com": { "overview": {}, "traffic": {}, "trafficSources": {}, "ranking": {}, "demographics": {}, "geography": {} },
  "youtube.com": { "overview": {}, "traffic": {}, "trafficSources": {}, "ranking": {}, "demographics": {}, "geography": {} }
}
```

## 5. Scrape a trending category

Reuse the same session — `open` a `top-websites/<category>/` URL and wait for the JSON-LD block.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.similarweb.com/top-websites/computers-electronics-and-technology/programming-and-developer-software/"
scrapeless-scraping-browser --session-id "$SID" wait "script#dataset-json-ld"
# save the trendings extractor (a single expression returning a JSON string)
cat > trendings.js <<'JS'
// In-page extractor for a Similarweb top-websites category page.
// Returns a JSON string — a single Trending object (see ../../../DATA_MODEL.md).
//
// Mirrors scrapeTrendings in ../nodejs/similarweb.mjs: parse the
// `script#dataset-json-ld` JSON-LD blob, then lift `mainEntity.{name,
// itemListElement}`. `scrape_trendings` returns a list (one per category URL);
// the CLI opens one URL per run, so this emits a single object — wrap it in a
// list yourself if you need the multi-URL shape.
JSON.stringify(
  (function () {
    const raw =
      document.querySelector("script#dataset-json-ld")?.textContent || "{}";
    let doc = {};
    try {
      doc = JSON.parse(raw);
    } catch (_) {}
    const main = doc.mainEntity ?? {};
    return {
      name: main.name ?? "",
      url: location.href,
      list: main.itemListElement ?? [],
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat trendings.js)" --json
```

`data.result` is one `Trending` object:

```json
{
  "name": "Top Programming And Developer Software Websites",
  "url": "https://www.similarweb.com/top-websites/computers-electronics-and-technology/programming-and-developer-software/",
  "list": [{ "@type": "ListItem", "position": 1, "name": "github.com" }]
}
```

## 6. Output shape

Each extractor is a single expression that returns a JSON string, kept in
lockstep with the parsers in [`../nodejs/similarweb.mjs`](../nodejs/similarweb.mjs):

| Extractor | Returns |
| --- | --- |
| `WEBSITE_JS` | one `Website` (`layout.data`) |
| `COMPARE_JS` | `{ [a]: WebsiteSubset, [b]: WebsiteSubset }` |
| `TRENDING_JS` | one `Trending` `{ name, url, list }` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). A live-captured `website` payload is in
[`results/website.json`](results/website.json); `website_compare` and `trendings` are not committed
— run with `--save` to populate them.
