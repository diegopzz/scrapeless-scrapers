# Trivago — CLI surface

Scrape Trivago destination pages — both the accommodation result list and the destination summary —
from the command line with the
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
in-page extractor. Start with the result list on a destination page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name trivago-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the server-rendered JSON-LD block
scrapeless-scraping-browser --session-id "$SID" open "https://www.trivago.com/en-US/odr/hotels-new-york-city-new-york-united-states-of-america?search=200-2755"
scrapeless-scraping-browser --session-id "$SID" wait "script[type='application/ld+json']"

# run the in-page extractor — its JSON comes back in data.result
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a Trivago destination/search results page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
// Reads the server-rendered JSON-LD `ItemList` block, mirroring
// parseSearch() in ../nodejs/trivago.mjs.
JSON.stringify(
  (function () {
    const safeJsonParse = (s) => {
      try {
        return JSON.parse(s);
      } catch (e) {
        return null;
      }
    };
    const toNumberOrNull = (v) => {
      if (v === null || v === undefined || v === "") return null;
      const n = typeof v === "number" ? v : parseFloat(v);
      return Number.isFinite(n) ? n : null;
    };
    const toIntOrNull = (v) => {
      if (v === null || v === undefined || v === "") return null;
      const n =
        typeof v === "number"
          ? Math.round(v)
          : parseInt(String(v).replace(/,/g, ""), 10);
      return Number.isFinite(n) ? n : null;
    };

    const blocks = [];
    document
      .querySelectorAll("script[type='application/ld+json']")
      .forEach((el) => {
        const raw = el.textContent;
        if (!raw) return;
        const parsed = safeJsonParse(raw);
        if (parsed) blocks.push(parsed);
      });

    let list = null;
    for (const b of blocks) {
      if (b && b["@type"] === "ItemList" && Array.isArray(b.itemListElement)) {
        list = b;
        break;
      }
    }
    if (!list) return [];

    const mapHotelItem = (el) => {
      const item = (el && el.item) || el || {};
      const rating = item.aggregateRating || {};
      return {
        position: toIntOrNull(el && el.position) ?? 0,
        name: item.name || "",
        url: item.url || "",
        address: item.address || null,
        image: item.image || null,
        description: item.description || null,
        priceRange: item.priceRange || null,
        ratingValue: toNumberOrNull(rating.ratingValue),
        reviewCount: toIntOrNull(rating.reviewCount),
        bestRating: toNumberOrNull(rating.bestRating),
        worstRating: toNumberOrNull(rating.worstRating),
      };
    };

    return list.itemListElement
      .filter((el) => el && el.item && el.item["@type"] === "Hotel")
      .map(mapHotelItem)
      .filter((h) => h.name);
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of `SearchResult` (one per `ItemList` hotel):

```json
[
  {
    "position": 1,
    "name": "Ferienwohnung Matthias Lang",
    "url": "https://www.trivago.com/en-US/oar/entire-house-apartment-ferienwohnung-matthias-lang-rugendorf?search=100-45227564",
    "address": "1.2 miles to City center",
    "image": "https://imgcy.trivago.com/.../be27dd5ad5df8b518ac4596ec949b4680a8b78e93546099e21b2647ee578.jpeg",
    "description": null,
    "priceRange": null,
    "ratingValue": 9.4,
    "reviewCount": 5,
    "bestRating": 10,
    "worstRating": 0
  }
]
```

## 4. Scrape the destination summary

The destination's breadcrumb and FAQ context render on the *same* page — no new `open` needed. With
the destination page already loaded (step 3), run the destination extractor.

```bash
# save the destination extractor (a single expression returning a JSON string)
cat > destination.js <<'JS'
// In-page extractor for a Trivago destination page.
// Returns a JSON string — a single Destination (see ../../../DATA_MODEL.md).
// Mirrors parseDestination() in ../nodejs/trivago.mjs: breadcrumb + FAQ context
// from the server-rendered JSON-LD blocks, plus the top hotels from the ItemList.
JSON.stringify(
  (function () {
    const url = location.href;
    const safeJsonParse = (s) => {
      try {
        return JSON.parse(s);
      } catch (e) {
        return null;
      }
    };
    const toNumberOrNull = (v) => {
      if (v === null || v === undefined || v === "") return null;
      const n = typeof v === "number" ? v : parseFloat(v);
      return Number.isFinite(n) ? n : null;
    };
    const toIntOrNull = (v) => {
      if (v === null || v === undefined || v === "") return null;
      const n =
        typeof v === "number"
          ? Math.round(v)
          : parseInt(String(v).replace(/,/g, ""), 10);
      return Number.isFinite(n) ? n : null;
    };

    const blocks = [];
    document
      .querySelectorAll("script[type='application/ld+json']")
      .forEach((el) => {
        const raw = el.textContent;
        if (!raw) return;
        const parsed = safeJsonParse(raw);
        if (parsed) blocks.push(parsed);
      });

    let list = null;
    for (const b of blocks) {
      if (b && b["@type"] === "ItemList" && Array.isArray(b.itemListElement)) {
        list = b;
        break;
      }
    }

    let breadcrumbs = [];
    for (const b of blocks) {
      if (
        b &&
        b["@type"] === "BreadcrumbList" &&
        Array.isArray(b.itemListElement)
      ) {
        breadcrumbs = b.itemListElement
          .map((li) => (li && li.item && li.item.name) || null)
          .filter((x) => !!x);
        break;
      }
    }

    let faq = [];
    for (const b of blocks) {
      if (b && b["@type"] === "FAQPage" && Array.isArray(b.mainEntity)) {
        faq = b.mainEntity
          .map((q) => ({
            question: (q && q.name) ?? null,
            answer: (q && q.acceptedAnswer && q.acceptedAnswer.text) ?? null,
          }))
          .filter((q) => q.question);
        break;
      }
    }

    const titleText =
      (document.querySelector("title")?.textContent ?? "").trim() || "";
    let name = breadcrumbs.length ? breadcrumbs[breadcrumbs.length - 1] : "";
    if (!name) {
      name =
        (document.querySelector("h1")?.textContent ?? "").trim() ||
        titleText.split("|")[0].trim();
    }

    const totalHotels = list
      ? toIntOrNull(list.numberOfItems) ?? list.itemListElement.length
      : null;

    const mapHotelItem = (el) => {
      const item = (el && el.item) || el || {};
      const rating = item.aggregateRating || {};
      return {
        position: toIntOrNull(el && el.position) ?? 0,
        name: item.name || "",
        url: item.url || "",
        address: item.address || null,
        image: item.image || null,
        description: item.description || null,
        priceRange: item.priceRange || null,
        ratingValue: toNumberOrNull(rating.ratingValue),
        reviewCount: toIntOrNull(rating.reviewCount),
        bestRating: toNumberOrNull(rating.bestRating),
        worstRating: toNumberOrNull(rating.worstRating),
      };
    };

    const topHotels = list
      ? list.itemListElement
          .filter((el) => el && el.item && el.item["@type"] === "Hotel")
          .map(mapHotelItem)
          .filter((h) => h.name)
      : [];

    return { url, name, breadcrumbs, totalHotels, faq, topHotels };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat destination.js)" --json
```

`data.result` is a single `Destination`:

```json
{
  "url": "https://www.trivago.com/en-US/odr/hotels-new-york-city-new-york-united-states-of-america?search=200-2755",
  "name": "Rugendorf",
  "breadcrumbs": ["Hotel search", "Europe", "Germany", "Bavaria", "Rugendorf"],
  "totalHotels": 35,
  "faq": [{ "question": "What are the best hotels in Rugendorf?", "answer": "..." }],
  "topHotels": [{ "position": 1, "name": "Ferienwohnung Matthias Lang", "ratingValue": 9.4 }]
}
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/trivago.mjs`](../nodejs/trivago.mjs). Both extractors read the
server-rendered JSON-LD blocks Trivago ships on every destination page, so a single `open` covers
both kinds:

| Extractor | Returns |
| --- | --- |
| `search.js` | list of `SearchResult` |
| `destination.js` | one `Destination` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
