# SeLoger — CLI surface

Scrape SeLoger search-results and property-detail pages from the command line with the
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

SeLoger is a French real estate portal — create the session with an `FR` proxy country if your
account supports it.

## 3. Scrape your first page

Every scrape is the same four moves: open a session, navigate, wait for a stable marker, run an
in-page extractor. Start with a search-results page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name seloger-cli --ttl 300 --proxy-country FR --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the result cards to render
scrapeless-scraping-browser --session-id "$SID" open "https://www.seloger.com/classified-search?distributionTypes=Buy&estateTypes=Apartment&locations=AD08FR13100"
scrapeless-scraping-browser --session-id "$SID" wait "div[data-testid='serp-core-classified-card-testid']"

# run the in-page extractor — pass the SEARCH_JS expression as the eval arg
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a SeLoger search results page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  Array.from(
    document.querySelectorAll("div[data-testid='serp-core-classified-card-testid']")
  ).map((card) => {
    const linkEl = card.querySelector("a[data-testid='card-mfe-covering-link-testid']");
    const link = linkEl?.getAttribute("href") || "";
    const title = linkEl?.getAttribute("title") || "";

    const priceEl = card.querySelector("div[data-testid*='cardmfe-price']");
    const price = (priceEl?.getAttribute("aria-label") || priceEl?.textContent || "").trim();

    const pricePerM2El = card.querySelector("div[data-testid*='price-per-m2']");
    const pricePerM2 = pricePerM2El ? pricePerM2El.textContent.trim() : null;

    const property_facts = [];
    const descEl = card.querySelector("div[data-testid*='description']");
    if (descEl) {
      descEl.childNodes.forEach((n) => {
        if (n.nodeType === 3 && n.textContent && n.textContent.trim()) {
          property_facts.push(n.textContent.trim());
        }
      });
    }

    const address = (card.querySelector("div[data-testid*='address']")?.textContent || "").trim();
    const agencyEl = card.querySelector("div[data-testid*='agency']");
    const agency = agencyEl ? agencyEl.textContent.trim() : null;

    const images = [];
    card.querySelectorAll("img").forEach((img) => {
      const src = img.getAttribute("src");
      if (src) images.push(src);
    });

    let url = link;
    try {
      url = new URL(link, location.href).toString();
    } catch (e) {}

    return {
      title,
      url,
      images,
      price,
      price_per_m2: pricePerM2,
      property_facts,
      address,
      agency,
    };
  })
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of `SearchResult`, parsed from the `data-testid` card markup:

```json
[
  {
    "title": "Appartement 3 pièces 65 m²",
    "url": "https://www.seloger.com/annonces/achat/appartement/bordeaux-33/193612259.htm",
    "images": ["https://v.seloger.com/.../photo.jpg"],
    "price": "245 000 EUR",
    "price_per_m2": "3 769 EUR/m²",
    "property_facts": ["3 pièces", "65 m²"],
    "address": "Bordeaux (33000)",
    "agency": "Agence Bordeaux Centre"
  }
]
```

## 4. Scrape a property

Reuse the same session — `open` a property URL, wait for the page body, then run the property
extractor. The detail data lives in the page's `window.__UFRN_LIFECYCLE_SERVERREQUEST__` bootstrap
state, so the extractor decodes that and returns the `app_cldp.data.classified` blob.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.seloger.com/annonces/achat/appartement/bordeaux-33/193612259.htm"
scrapeless-scraping-browser --session-id "$SID" wait "body"
# save the property extractor (a single expression returning a JSON string)
cat > property.js <<'JS'
// In-page extractor for a SeLoger property detail page.
// Returns a JSON string — a PropertyResult ({ classified } or {}) — see
// ../../../DATA_MODEL.md. The payload is the decoded bootstrap state from the
// page's `window.__UFRN_LIFECYCLE_SERVERREQUEST__` script.
JSON.stringify(
  (function () {
    let payload = {};
    const scripts = Array.from(document.querySelectorAll("body script"));
    for (const el of scripts) {
      const txt = el.textContent || "";
      if (!txt.includes("__UFRN_LIFECYCLE_SERVERREQUEST__")) continue;
      const m = /JSON\.parse\("(.+)"\)/s.exec(txt);
      if (!m) continue;
      try {
        const decoded = JSON.parse(`"${m[1]}"`);
        const data = JSON.parse(decoded);
        const classified = data?.app_cldp?.data?.classified;
        if (classified) {
          payload = { classified };
          break;
        }
      } catch (e) {}
    }
    return payload;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat property.js)" --json
```

`data.result` is a `PropertyResult` — `{ classified }` wrapping the decoded state object (treat it as
opaque JSON). the extractor wraps it in a one-element list so the saved fixture stays shape-identical with
the `scrape_property` output of the other surfaces.

```json
{
  "classified": {
    "id": 193612259,
    "title": "...",
    "price": { "value": 245000, "currency": "EUR" }
  }
}
```

## 5. Output shape

Each in-page extractor is a single expression
that returns a JSON string, kept in lockstep with the selectors in
[`../nodejs/seloger.mjs`](../nodejs/seloger.mjs):

| Extractor | Returns |
| --- | --- |
| `SEARCH_JS` | list of `SearchResult` |
| `PROPERTY_JS` | one `PropertyResult` (`{ classified }`) |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).
