# Rightmove — CLI surface

Scrape Rightmove property pages, location lookups, and property searches from the command line with
the [`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. Each page is driven by its own Scrapeless cloud browser session and extracted in-browser with
the CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

Rightmove is geo-locked to GB, so — like the [`nodejs/`](../nodejs/rightmove.mjs) surface — every
session uses a **GB residential proxy** (`--proxy-country GB`). Anti-bot is intermittent: **if an
extractor returns `null` / `[]`, the page didn't render — close the session and re-run.** Use one
fresh session per page (sessions terminate when their connection drops).

## 1. Install

```bash
npm install -g scrapeless-scraping-browser
```

`node` is also required — the steps below use it to pull values out of the CLI's JSON envelope
(`jq` works too, if preferred).

## 2. Set your API key

```bash
export SCRAPELESS_API_KEY=sk_...      # the only env var this CLI reads — sign up at https://app.scrapeless.com
```

## 3. Scrape a property page

Open a fresh GB-proxied session, navigate, and wait for the property header. The extractor reads
`window.PAGE_MODEL.propertyData` off the page, revives the Devalue-encoded flat array, then reduces
it with the same field map as `parseProperty()` in [`../nodejs/rightmove.mjs`](../nodejs/rightmove.mjs).

```bash
SID=$(scrapeless-scraping-browser new-session --name rightmove-property --ttl 300 --proxy-country GB --json \
  | node -pe 'JSON.parse(require("fs").readFileSync(0)).data.taskId')

scrapeless-scraping-browser --session-id "$SID" open "https://www.rightmove.co.uk/properties/149360984"
scrapeless-scraping-browser --session-id "$SID" wait "#propertyHeader, [data-test='property-header']"

# save the property extractor (a single expression returning a JSON string — one Property)
cat > property.js <<'JS'
// In-page extractor for a Rightmove property detail page.
// Returns a JSON string — a single Property (see ../../DATA_MODEL.md).
// Rightmove embeds the cache in `window.PAGE_MODEL = { propertyData: {...} }`,
// Devalue-encoded ({ data: "<stringified array>", encoding }), so the array is
// revived before the propertyData is reachable.
JSON.stringify(
  (function () {
    function* findJsonObjects(text) {
      let pos = 0;
      while (true) {
        const match = text.indexOf("{", pos);
        if (match === -1) break;
        let depth = 0, inString = false, escape = false, end = -1;
        for (let i = match; i < text.length; i++) {
          const c = text[i];
          if (escape) { escape = false; continue; }
          if (c === "\\") { escape = true; continue; }
          if (c === '"') { inString = !inString; continue; }
          if (inString) continue;
          if (c === "{") depth++;
          else if (c === "}") {
            depth--;
            if (depth === 0) { end = i + 1; break; }
          }
        }
        if (end === -1) break;
        try {
          yield JSON.parse(text.slice(match, end));
          pos = end;
        } catch (e) {
          pos = match + 1;
        }
      }
    }

    function reviveDevalue(arr) {
      const seen = new Map();
      const r = (i) => {
        if (typeof i !== "number") return i;
        if (seen.has(i)) return seen.get(i);
        const v = arr[i];
        if (v === undefined) return undefined;
        if (v === null || typeof v !== "object") { seen.set(i, v); return v; }
        if (Array.isArray(v)) {
          const out = [];
          seen.set(i, out);
          for (const e of v) out.push(typeof e === "number" ? r(e) : e);
          return out;
        }
        const out = {};
        seen.set(i, out);
        for (const [k, val] of Object.entries(v)) {
          out[k] = typeof val === "number" ? r(val) : val;
        }
        return out;
      };
      return r(0);
    }

    const dig = (obj, path) => {
      let cur = obj;
      for (const key of path.split(".")) {
        cur = cur == null ? cur : cur[key];
      }
      return cur === undefined ? null : cur;
    };

    let script = null;
    document.querySelectorAll("script").forEach((el) => {
      const t = el.textContent ?? "";
      if (script === null && t.includes("PAGE_MODEL = ")) script = t;
    });
    if (!script) return null;

    let data = null;
    for (const obj of findJsonObjects(script)) {
      if (!obj) continue;
      if (typeof obj.data === "string" && Object.prototype.hasOwnProperty.call(obj, "encoding")) {
        try {
          const arr = JSON.parse(obj.data);
          if (Array.isArray(arr) && arr.length > 0) {
            const root = reviveDevalue(arr);
            if (root && root.propertyData) { data = root.propertyData; break; }
          }
        } catch (e) {}
      }
      if (obj.propertyData && typeof obj.propertyData === "object") {
        data = obj.propertyData;
        break;
      }
    }
    if (!data) return null;

    const arr = (path) => {
      const v = dig(data, path);
      return Array.isArray(v) ? v : [];
    };
    const customer = data.customer ?? null;

    return {
      id: dig(data, "id"),
      available: dig(data, "status.published"),
      archived: dig(data, "status.archived"),
      phone: dig(data, "contactInfo.telephoneNumbers.localNumber"),
      bedrooms: dig(data, "bedrooms"),
      bathrooms: dig(data, "bathrooms"),
      type: dig(data, "transactionType"),
      property_type: dig(data, "propertySubType"),
      tags: dig(data, "tags"),
      description: dig(data, "text.description"),
      title: dig(data, "text.pageTitle"),
      subtitle: dig(data, "text.propertyPhrase"),
      price: dig(data, "prices.primaryPrice"),
      price_sqft: dig(data, "prices.pricePerSqFt"),
      address: dig(data, "address"),
      latitude: dig(data, "location.latitude"),
      longitude: dig(data, "location.longitude"),
      features: dig(data, "keyFeatures"),
      history: dig(data, "listingHistory"),
      photos: arr("images").map((x) => ({ url: x?.url ?? null, caption: x?.caption ?? null })),
      floorplans: arr("floorplans").map((x) => ({ url: x?.url ?? null, caption: x?.caption ?? null })),
      agency: customer
        ? {
            id: customer.branchId ?? null,
            branch: customer.branchName ?? null,
            company: customer.companyName ?? null,
            address: customer.displayAddress ?? null,
            commercial: customer.commercial ?? null,
            buildToRent: customer.buildToRent ?? null,
            isNew: customer.isNewHomeDeveloper ?? null,
          }
        : null,
      industryAffiliations: arr("industryAffiliations").map((x) => x?.name ?? null),
      nearest_airports: arr("nearestAirports").map((x) => ({ name: x?.name ?? null, distance: x?.distance ?? null })),
      nearest_stations: arr("nearestStations").map((x) => ({ name: x?.name ?? null, distance: x?.distance ?? null })),
      sizings: arr("sizings").map((x) => ({ unit: x?.unit ?? null, min: x?.minimumSize ?? null, max: x?.maximumSize ?? null })),
      brochures: dig(data, "brochures"),
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat property.js)" --json
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `Property`:

```json
{
  "id": "149360984",
  "type": "BUY",
  "property_type": "Detached",
  "price": "£1,500,000",
  "bedrooms": 4,
  "bathrooms": 2,
  "address": { "displayAddress": "..." },
  "features": ["..."],
  "photos": [{ "url": "https://media.rightmove.co.uk/.../photo.jpg", "caption": "Picture No. 32" }],
  "agency": { "id": 213371, "branch": "Plymouth", "company": "Pilkington Estates", "isNew": false },
  "nearest_stations": [{ "name": "Truro Station", "distance": 5.08 }]
}
```

## 4. Look up locations

The location lookup hits the `los.rightmove.co.uk/typeahead` JSON endpoint. Navigate straight to the
API URL and read the rendered `<body>` text — the extractor parses it and maps each match to a
`"<type>^<id>"` string.

```bash
SID=$(scrapeless-scraping-browser new-session --name rightmove-locations --ttl 300 --proxy-country GB --json \
  | node -pe 'JSON.parse(require("fs").readFileSync(0)).data.taskId')

scrapeless-scraping-browser --session-id "$SID" open "https://los.rightmove.co.uk/typeahead?query=cornwall&limit=10&exclude=STREET"
scrapeless-scraping-browser --session-id "$SID" wait "body"

# save the locations extractor (returns a JSON string — a list of "<type>^<id>" strings)
cat > locations.js <<'JS'
// In-page extractor for the Rightmove typeahead (location-search) endpoint.
// The endpoint returns XML (<TypeaheadDTO><matches><matches><id>..</id>
// <type>..</type>..</matches></matches>), rendered as an XML document. Returns a
// JSON string — a list of LocationMatch strings "<type>^<id>" (see ../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const items = Array.from(document.querySelectorAll("matches"))
      .map((m) => {
        const id = m.querySelector("id")?.textContent?.trim();
        const type = m.querySelector("type")?.textContent?.trim();
        return id && type ? `${type}^${id}` : null;
      })
      .filter(Boolean);
    return items.filter((v, i) => items.indexOf(v) === i);
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat locations.js)" --json
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of `LocationMatch` strings — e.g. `["REGION^61294", "TOWN^..."]`. Use the
first one as the `locationIdentifier` for the search step.

## 5. Scrape a search

The search side calls the clean `/api/property-search/listing/search` JSON endpoint. Navigate to the
API URL (built with `searchLocation` + the `locationIdentifier` from step 4 — `^` URL-encodes to
`%5E`) and read the `<body>` text — the extractor returns its `properties` array.

```bash
SID=$(scrapeless-scraping-browser new-session --name rightmove-search --ttl 300 --proxy-country GB --json \
  | node -pe 'JSON.parse(require("fs").readFileSync(0)).data.taskId')

scrapeless-scraping-browser --session-id "$SID" open "https://www.rightmove.co.uk/api/property-search/listing/search?searchLocation=Cornwall&useLocationIdentifier=true&locationIdentifier=REGION%5E61294&radius=0.0&_includeSSTC=true&index=0&sortType=2&channel=BUY&transactionType=BUY"
scrapeless-scraping-browser --session-id "$SID" wait "body"

# save the search extractor (returns a JSON string — a list of SearchResult)
cat > search.js <<'JS'
// In-page extractor for the Rightmove `/api/property-search/listing/search`
// endpoint. The page body is the clean JSON response; hand back its
// `properties` array. Returns a JSON string — a list of SearchResult (see
// ../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const body = (document.body ? document.body.innerText : "").trim();
    if (!body || !body.startsWith("{")) return [];
    let data;
    try {
      data = JSON.parse(body);
    } catch (e) {
      return [];
    }
    return data.properties ?? [];
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of `SearchResult` (the search API's `properties` entries):

```json
[
  { "id": 123456789, "bedrooms": 3, "displayAddress": "...", "price": { "amount": 450000, "currencyCode": "GBP" }, "propertyUrl": "/properties/123456789" }
]
```

(The SDK surface paginates this endpoint; the CLI surface fetches the first page.)

## 6. Output shape

Each extractor above is a single expression that returns a JSON string, kept in lockstep with the
selectors / field map in [`../nodejs/rightmove.mjs`](../nodejs/rightmove.mjs):

| Extractor | Returns |
| --- | --- |
| `property.js` | one `Property` (from `window.PAGE_MODEL.propertyData`) |
| `locations.js` | list of `LocationMatch` `"<type>^<id>"` strings |
| `search.js` | list of `SearchResult` (search API `properties`) |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
