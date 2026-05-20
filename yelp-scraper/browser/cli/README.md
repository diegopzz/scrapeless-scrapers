# Yelp — CLI surface

Scrape Yelp business profiles, reviews, and search results from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; each surface is extracted in-browser with
the CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
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

## 3. Scrape a business page

Every scrape is the same four moves: open a session, navigate, wait for a stable marker, run an
in-page extractor. Yelp fronts DataDome, so warm up at `https://www.yelp.com/` first — the session
picks up the anti-bot cookies, and the deeper navigation is far less likely to trip the CAPTCHA
interstitial.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name yelp-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# warm up, then navigate to the business profile and wait for its <h1>
scrapeless-scraping-browser --session-id "$SID" open "https://www.yelp.com/"
scrapeless-scraping-browser --session-id "$SID" open "https://www.yelp.com/biz/vons-1000-spirits-seattle-4"
scrapeless-scraping-browser --session-id "$SID" wait "h1"

# run the in-page extractor — its JSON comes back in data.result
# save the business_pages extractor (a single expression returning a JSON string)
cat > business_pages.js <<'JS'
// In-page extractor for a Yelp business profile page.
// Returns a JSON string — a single BusinessPage (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const txt = (node) => (node?.textContent ?? "").trim();

    // open_hours: each weekday <th><p class="...day-of-the-week...">Mon</p>
    // sits two levels up from the matching <td><p>hours</p>.
    const openHours = {};
    document.querySelectorAll("th p").forEach((p) => {
      if (!/day-of-the-week/.test(p.getAttribute("class") || "")) return;
      const name = txt(p);
      const value = txt(
        p.parentElement?.parentElement?.querySelector("td p")
      );
      if (name) openHours[name.toLowerCase()] = value;
    });

    // website: the <p> after a <p> whose text contains "Business website".
    const websiteLabel = Array.from(document.querySelectorAll("p")).find((p) =>
      (p.textContent || "").includes("Business website")
    );
    const website = txt(
      websiteLabel?.nextElementSibling?.querySelector("a")
    );

    // phone: the <p> after a <p> whose text contains "Phone number".
    const phoneLabel = Array.from(document.querySelectorAll("p")).find((p) =>
      (p.textContent || "").includes("Phone number")
    );
    const phone = txt(phoneLabel?.nextElementSibling);

    // address: the <p> sibling after the parent of the "Get Directions" link.
    const dirLink = Array.from(document.querySelectorAll("a")).find((a) =>
      (a.textContent || "").includes("Get Directions")
    );
    let address = "";
    if (dirLink) {
      let sib = dirLink.parentElement?.nextElementSibling;
      while (sib && sib.tagName !== "P") sib = sib.nextElementSibling;
      address = txt(sib);
    }

    // claim_status: a <span> that wraps a <span> whose class mentions "claim".
    let claim_status = "";
    for (const span of document.querySelectorAll("span")) {
      const inner = span.querySelector(":scope > span");
      if (inner && /claim/.test(inner.getAttribute("class") || "")) {
        claim_status = txt(span).toLowerCase();
        break;
      }
    }

    const out = {
      name: txt(document.querySelector("h1")),
      website,
      phone,
      address,
      logo:
        document
          .querySelector('img[class*="businessLogo"]')
          ?.getAttribute("src") || "",
      claim_status,
      open_hours: openHours,
    };

    // JSON-LD fallback — the DOM selectors above are fragile across Yelp's
    // A/B layouts. The Restaurant/LocalBusiness JSON-LD block reliably carries
    // name, telephone, address, logo and openingHoursSpecification.
    const blocks = [];
    document
      .querySelectorAll('script[type="application/ld+json"]')
      .forEach((el) => {
        try {
          const raw = el.textContent;
          if (!raw) return;
          const parsed = JSON.parse(raw);
          if (Array.isArray(parsed)) blocks.push(...parsed);
          else blocks.push(parsed);
        } catch (e) {}
      });
    const types = new Set([
      "Restaurant",
      "LocalBusiness",
      "FoodEstablishment",
      "Bar",
      "CafeOrCoffeeShop",
      "Hotel",
      "Store",
      "Organization",
    ]);
    const isBusiness = (node) => {
      if (!node || typeof node !== "object") return false;
      const t = node["@type"];
      if (typeof t === "string") return types.has(t);
      if (Array.isArray(t)) return t.some((x) => types.has(x));
      return false;
    };
    const business = blocks.find(isBusiness) || null;

    const addressToString = (addr) => {
      if (!addr || typeof addr !== "object")
        return typeof addr === "string" ? addr : "";
      return [
        addr.streetAddress,
        addr.addressLocality,
        addr.addressRegion,
        addr.postalCode,
        addr.addressCountry,
      ]
        .filter((x) => typeof x === "string" && x.trim())
        .join(", ");
    };

    if (business) {
      if (!out.name)
        out.name = (business.name ?? "").toString().replace(/&apos;/g, "'");
      if (!out.phone) out.phone = (business.telephone ?? "").toString();
      if (!out.address) out.address = addressToString(business.address);
      if (!out.website) {
        const same = business.sameAs;
        if (Array.isArray(same) && same.length) out.website = same[0];
        else if (
          typeof business.url === "string" &&
          !business.url.includes("yelp.com")
        )
          out.website = business.url;
      }
      if (!out.logo) {
        const img = business.image;
        if (typeof img === "string") out.logo = img;
        else if (img && typeof img === "object" && typeof img.url === "string")
          out.logo = img.url;
      }
      if (!Object.keys(out.open_hours).length) {
        const oh = {};
        const spec = business.openingHoursSpecification;
        if (Array.isArray(spec)) {
          for (const entry of spec) {
            const days = Array.isArray(entry?.dayOfWeek)
              ? entry.dayOfWeek
              : [entry?.dayOfWeek];
            const opens = entry?.opens ?? "";
            const closes = entry?.closes ?? "";
            const range =
              opens && closes
                ? `${opens}-${closes}`
                : opens || closes || "";
            for (const day of days) {
              if (typeof day !== "string") continue;
              const key = day.split("/").pop().slice(0, 3).toLowerCase();
              oh[key] = range;
            }
          }
        }
        if (Object.keys(oh).length) out.open_hours = oh;
      }
    }
    return out;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat business_pages.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

(the variable above is shorthand for the in-page extractor expression.)

`data.result` is a single-element array of `BusinessPage`:

```json
[
  {
    "name": "Von's 1000 Spirits",
    "website": "vons1000spirits.com",
    "phone": "(206) 621-8667",
    "address": "1225 1st Ave Seattle, WA 98101",
    "logo": "",
    "claim_status": "claimed",
    "open_hours": {
      "mon": "11:00 AM - 12:00 AM (Next day)",
      "fri": "11:00 AM - 1:00 AM (Next day)"
    }
  }
]
```

The extractor reads the visible DOM first (name, website, phone, address, logo, claim_status,
open_hours) and falls back to the page's schema.org `LocalBusiness` / `Restaurant` JSON-LD block —
exactly like `parsePage` in [`../nodejs/yelp.mjs`](../nodejs/yelp.mjs).

## 4. Scrape reviews

Yelp does not render reviews into a DOM list — it serves them from a GraphQL POST to
`https://www.yelp.com/gql/batch`, keyed by the encoded business id in
`meta[name="yelp-biz-id"]` with a base64 "offset" pagination cursor. The reviews extractor runs
that POST **in-page** with `fetch(credentials:'include')` so it carries the session's DataDome
cookies, paginating in steps of 10 just like `scrapeReviews` in `../nodejs/yelp.mjs`. No new `open`
is needed — run it on the business page from step 3.

```bash
scrapeless-scraping-browser --session-id "$SID" wait "meta[name='yelp-biz-id']"
scrapeless-scraping-browser --session-id "$SID" eval "$REVIEWS_JS" --json
```

`data.result` is a list of `Review`:

```json
[
  {
    "encid": "0cZPTelaWUAp_nBJxNsqsA",
    "text": { "full": "This place has it all...", "language": "en" },
    "rating": 5,
    "feedback": { "coolCount": 0, "funnyCount": 0, "usefulCount": 0 },
    "author": { "encid": "zuiH8pETksnCDVNsNUt5vw", "displayName": "Dana D.", "displayLocation": "CA, CA", "reviewCount": 4, "friendCount": 0, "businessPhotoCount": 0 },
    "business": { "encid": "Lw7NmZ3j-WEye97ywEmkXQ", "alias": "vons-1000-spirits-seattle-4", "name": "Von's 1000 Spirits" },
    "createdAt": "2024-..."
  }
]
```

The extractor caps the run at 30 reviews. (`eval` here returns a Promise — the CLI awaits it before
emitting `data.result`.)

## 5. Scrape a search page

Yelp ships the result set inside a `<script data-id="react-root-props">` blob assigned to
`react_root_props`; the extractor splits on that token, parses the JSON, and returns the
`mainContentComponentsListProps` entries that carry a `bizId` + `searchResultBusiness`.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.yelp.com/search?find_desc=plumbers&find_loc=Seattle%2C+WA&start=0"
scrapeless-scraping-browser --session-id "$SID" wait "script[data-id='react-root-props']"
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a Yelp search results page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
//
// Note: Yelp's /search surface trips DataDome aggressively; if the page is the
// anti-bot interstitial the `react-root-props` script is absent and this
// returns []. Matching nodejs/yelp.mjs, results are the raw
// `mainContentComponentsListProps` entries that carry a bizId.
JSON.stringify(
  (function () {
    const script = document.querySelector(
      "script[data-id='react-root-props']"
    )?.textContent;
    if (!script) return [];
    const raw = script.split("react_root_props = ").slice(-1)[0];
    const trimmed = raw.replace(/;\s*$/, "");
    let data;
    try {
      data = JSON.parse(trimmed);
    } catch (e) {
      return [];
    }
    const props =
      data?.legacyProps?.searchAppProps?.searchPageProps ?? {};
    const searchData = [];
    for (const item of props?.mainContentComponentsListProps ?? []) {
      if (item?.bizId && item?.searchResultBusiness != null) {
        searchData.push(item);
      }
    }
    return searchData;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
```

`data.result` is a list of `SearchResult` (raw `mainContentComponentsListProps` items):

```json
[
  { "bizId": "<encoded-biz-id>", "searchResultBusiness": { "name": "...", "alias": "...", "rating": 4.5 } }
]
```

> Yelp's `/search` surface trips DataDome far more aggressively than `/biz` pages — like the
> `nodejs/` reference, this can legitimately come back `[]` (see [`results/search.json`](results/search.json)).
> The business and reviews surfaces are the reliable ones.

## 6. Output shape

Each inline extractor is a single expression that returns a JSON string (the reviews one returns a
Promise of a JSON string), kept in lockstep with the parsers in
[`../nodejs/yelp.mjs`](../nodejs/yelp.mjs):

| Surface | Returns |
| --- | --- |
| `business_pages` | single-element array of `BusinessPage` (DOM + JSON-LD fallback) |
| `reviews` | list of `Review` (in-page GraphQL POST to `/gql/batch`) |
| `search` | list of `SearchResult` (from the `react-root-props` blob) |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).
