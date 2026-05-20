# Redfin — CLI surface

Scrape Redfin search results and "for sale" listings from the command line with the
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
in-page extractor. Start with a search. Redfin's search data comes from the `stingray/api/gis`
JSONP endpoint — the browser renders it as a plain `<body>` text blob prefixed with `{}&&`, which
`search.js` strips before parsing.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name redfin-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate to the stingray gis endpoint, then wait for the body to render
scrapeless-scraping-browser --session-id "$SID" open "https://www.redfin.com/stingray/api/gis?al=1&include_nearby_homes=true&market=seattle&num_homes=350&ord=redfin-recommended-asc&page_number=1&poly=-122.54472%2047.44109%2C-122.11144%2047.44109%2C-122.11144%2047.78363%2C-122.54472%2047.78363%2C-122.54472%2047.44109&sf=1,2,3,5,6,7&start=0&status=1&uipt=1,2,3,4,5,6,7,8&v=8&zoomLevel=11"
scrapeless-scraping-browser --session-id "$SID" wait "body"

# run the in-page extractor — its JSON comes back in data.result
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a Redfin stingray `gis` search response.
// The page body is JSONP prefixed with `{}&&`; once stripped it is
// `{ payload: { homes: [...] } }`. Returns a JSON string — a list of
// SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const body = document.body ? document.body.innerText : "";
    if (!body) return [];
    try {
      return JSON.parse(body.replace("{}&&", "")).payload.homes;
    } catch (e) {
      return [];
    }
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of `SearchResult` (Redfin's `payload.homes` entries):

```json
[
  {
    "mlsId": { "label": "MLS#", "value": "2513723" },
    "price": { "value": 1585000, "level": 1 },
    "beds": 5,
    "baths": 2.5,
    "sqFt": { "value": 3650, "level": 1 },
    "streetLine": { "value": "621 NE 77th St", "level": 1 },
    "latLong": { "value": { "latitude": 47.6844012, "longitude": -122.3205871 } }
  }
]
```

## 4. Scrape a property for sale

Listing pages have no clean JSON, so `property_for_sale.js` parses the visible DOM. Reuse the same
session — just `open` a listing URL and wait for the price / address markers.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.redfin.com/WA/Seattle/506-E-Howell-St-98122/unit-W303/home/46456"
scrapeless-scraping-browser --session-id "$SID" wait "div[data-rf-test-id='abp-price'], [class*='street-address']"
# save the property_for_sale extractor (a single expression returning a JSON string)
cat > property_for_sale.js <<'JS'
// In-page extractor for a Redfin "for sale" listing page.
// Returns a JSON string — a single PropertyForSale (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const txt = (node) => (node?.textContent ?? "");
    const joinText = (sel) =>
      Array.from(document.querySelectorAll(sel)).map((el) => el.textContent).join("");

    const price =
      txt(document.querySelector("div[data-rf-test-id='abp-price'] > div")) || null;
    const estimatedMonthlyPrice = joinText("span.est-monthly-payment");
    const address = (
      joinText("div[class*='street-address']") +
      " " +
      joinText("div[class*='cityStateZip']")
    ).trim();
    const description =
      txt(document.querySelector("div#marketing-remarks-scroll p span")) || null;
    const attachments = Array.from(
      document.querySelectorAll("img[class*='widenPhoto']")
    ).map((el) => el.getAttribute("src") ?? "");
    const details = Array.from(
      document.querySelectorAll("div .keyDetails-value")
    ).map((el) => el.textContent);

    const features = {};
    document.querySelectorAll(".amenity-group ul div.title").forEach((el) => {
      const label = el.textContent;
      const items = [];
      let sib = el.nextElementSibling;
      while (sib) {
        if (sib.tagName === "LI") {
          sib.querySelectorAll("span").forEach((span) => {
            const t = (span.textContent ?? "").trim();
            items.push(t);
          });
        }
        sib = sib.nextElementSibling;
      }
      features[label] = items;
    });

    return {
      address,
      description,
      price,
      estimatedMonthlyPrice,
      propertyUrl: location.href,
      attachments,
      details,
      features,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat property_for_sale.js)" --json
```

`data.result` is one `PropertyForSale`:

```json
{
  "address": "506 E Howell St Unit W303, Seattle, WA 98122",
  "description": "Welcome home to this stunning light-filled unit ...",
  "price": "$321,718",
  "estimatedMonthlyPrice": "Est. refi payment",
  "propertyUrl": "https://www.redfin.com/WA/Seattle/506-E-Howell-St-98122/unit-W303/home/46456",
  "attachments": ["https://ssl.cdn-redfin.com/..."],
  "details": ["..."],
  "features": { "Interior": ["..."] }
}
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/redfin.mjs`](../nodejs/redfin.mjs):

| Extractor | Returns |
| --- | --- |
| `search.js` | list of `SearchResult` (from the stingray `gis` JSONP endpoint) |
| `property_for_sale.js` | one `PropertyForSale` (parsed from the listing DOM) |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
