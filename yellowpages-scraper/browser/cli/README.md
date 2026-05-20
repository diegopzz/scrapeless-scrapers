# YellowPages — CLI surface

Scrape YellowPages search and business detail pages from the command line with the
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
in-page extractor. Start with a search page. The search URL is built from a query + location, the
same way `nodejs/yellowpages.mjs` does it.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name yellowpages-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the result list
scrapeless-scraping-browser --session-id "$SID" open "https://www.yellowpages.com/search?search_terms=Plumber&geo_location_terms=San%20Francisco%2C%20CA&page=1"
scrapeless-scraping-browser --session-id "$SID" wait ".search-results"

# run the in-page extractor — its JSON comes back in data.result
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a YellowPages search results page.
// Returns a JSON string — one SearchPage object { data, total_pages }
// (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const data = [];
    // YellowPages emits the listings as a bare JSON-LD array of LocalBusiness
    // objects (second <script type=application/ld+json> block). Older variants
    // used an ItemList with `itemListElement[].item`; support both.
    document
      .querySelectorAll('script[type="application/ld+json"]')
      .forEach((el) => {
        let payload;
        try {
          payload = JSON.parse(el.textContent || "");
        } catch (e) {
          return;
        }
        const candidates = Array.isArray(payload) ? payload : [payload];
        for (const node of candidates) {
          if (!node || typeof node !== "object") continue;
          if (node["@type"] === "LocalBusiness") {
            data.push(node);
            continue;
          }
          if (Array.isArray(node.itemListElement)) {
            for (const entry of node.itemListElement) {
              if (
                entry &&
                typeof entry === "object" &&
                entry.item &&
                typeof entry.item === "object"
              ) {
                data.push(entry.item);
              }
            }
          }
        }
      });

    let total_pages = null;
    const pageText =
      document.querySelector(".pagination > span")?.textContent ?? "";
    // YellowPages currently prints "Showing X-Y of Z" — Z is the total result
    // count, not the page count. Compute total pages from the page size (30).
    const m = pageText.match(/of\s+([\d,]+)/);
    if (m) {
      const total = parseInt(m[1].replace(/,/g, ""), 10);
      if (Number.isFinite(total)) {
        total_pages = Math.max(1, Math.ceil(total / 30));
      }
    }
    return { data, total_pages };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is one `SearchPage` object — `data` is the page's JSON-LD `LocalBusiness` list,
`total_pages` from the pagination footer:

```json
{
  "data": [
    {
      "@type": "LocalBusiness",
      "name": "Atlas Plumbing",
      "url": "https://www.yellowpages.com/san-francisco-ca/mip/atlas-plumbing-561373897?lid=...",
      "telephone": "(415) 852-3803",
      "openingHours": ["Mo-Fr 07:30-22:00", "Sa 08:00-17:00"]
    }
  ],
  "total_pages": 1
}
```

the extractor wraps this object in a one-element list so the saved fixture stays shape-identical with the
`scrape_search` output of the other surfaces.

## 4. Scrape a business page

Reuse the same session — just `open` a business detail URL and wait for the business name.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.yellowpages.com/san-francisco-ca/mip/atlas-plumbing-561373897"
scrapeless-scraping-browser --session-id "$SID" wait "h1.business-name"
# save the pages extractor (a single expression returning a JSON string)
cat > pages.js <<'JS'
// In-page extractor for a YellowPages business detail page.
// Returns a JSON string — a single BusinessPage (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const txt = (node) => (node?.textContent ?? "").trim();

    const ratingClass =
      document.querySelector(".ratings div")?.getAttribute("class") ?? "";
    let rating = "";
    const rm = ratingClass.match(/result\s+([a-z\s]+?)(?=$|\s\w+$)/);
    if (rm) rating = rm[1].trim();

    const workingHours = {};
    document.querySelectorAll(".open-details tr").forEach((row) => {
      const day = txt(row.querySelector("th"));
      const hours = row.querySelector("time")?.getAttribute("datetime");
      if (day && hours) workingHours[day] = hours.trim();
    });

    const phoneHref =
      document.querySelector(".phone")?.getAttribute("href") ?? "";
    const phone = phoneHref.replace(/^tel:/, "");

    const out = {
      name: txt(document.querySelector("h1.business-name")),
      categories: Array.from(document.querySelectorAll(".categories > a"))
        .map((el) => txt(el))
        .filter(Boolean),
      rating,
      ratingCount: txt(document.querySelector(".ratings .count")),
      phone,
      website:
        document.querySelector(".website-link")?.getAttribute("href") ?? "",
      address: txt(document.querySelector(".address")),
      workingHours,
    };

    // JSON-LD fallback for the (rare) layout variants that drop these selectors.
    let ld = null;
    const blocks = document.querySelectorAll(
      'script[type="application/ld+json"]'
    );
    for (const el of blocks) {
      let parsed;
      try {
        parsed = JSON.parse(el.textContent || "");
      } catch (e) {
        continue;
      }
      const candidates = Array.isArray(parsed) ? parsed : [parsed];
      for (const c of candidates) {
        if (!c || typeof c !== "object") continue;
        const t = c["@type"];
        if (
          typeof t === "string" &&
          /(LocalBusiness|Plumber|Restaurant|Store|Organization|Service)/.test(t)
        ) {
          ld = c;
          break;
        }
      }
      if (ld) break;
    }
    if (ld) {
      if (!out.name && typeof ld.name === "string") out.name = ld.name;
      if (!out.phone && typeof ld.telephone === "string")
        out.phone = ld.telephone;
      if (!out.address && ld.address && typeof ld.address === "object") {
        const a = ld.address;
        out.address = [
          a.streetAddress,
          a.addressLocality,
          a.addressRegion,
          a.postalCode,
        ]
          .filter((x) => typeof x === "string" && x.trim())
          .join(", ");
      }
      if (
        !Object.keys(out.workingHours).length &&
        Array.isArray(ld.openingHours)
      ) {
        for (const spec of ld.openingHours) {
          if (typeof spec !== "string") continue;
          const m = spec.match(/^([A-Za-z-]+)\s+(\d{2}:\d{2}-\d{2}:\d{2})$/);
          if (m) out.workingHours[m[1]] = m[2];
          else out.workingHours[spec] = spec;
        }
      }
    }
    return out;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat pages.js)" --json
```

`data.result` is one `BusinessPage` object:

```json
{
  "name": "Atlas Plumbing",
  "categories": ["Plumbers", "Plumbing-Drain & Sewer Cleaning", "Water Heater Repair"],
  "rating": "",
  "ratingCount": "",
  "phone": "(415) 852-3803",
  "website": "http://www.atlasplumber.com",
  "address": "3311 Mission StSan Francisco, CA 94110",
  "workingHours": { "Mon - Fri:": "Mo-Fr 07:30-22:00", "Sat:": "Sa 08:00-17:00" }
}
```

the extractor wraps this object in a one-element list so the saved fixture stays shape-identical with the
`scrape_pages` output of the other surfaces.

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/yellowpages.mjs`](../nodejs/yellowpages.mjs):

| Extractor | Returns |
| --- | --- |
| `search.js` | one `SearchPage` (`{ data, total_pages }`) |
| `pages.js` | one `BusinessPage` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
