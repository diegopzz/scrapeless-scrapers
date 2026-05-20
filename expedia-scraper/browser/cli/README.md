# Expedia — CLI surface

Scrape Expedia hotel-search and hotel-detail pages from the command line with the
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

Every scrape is the same set of moves: open a session, warm up at the homepage so the session
carries the cookies Expedia inspects, navigate, wait for a stable marker, run an in-page extractor.
Start with a hotel-search page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name expedia-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# warm up at the homepage so Expedia drops the "Bot or Not?" interstitial
scrapeless-scraping-browser --session-id "$SID" open "https://www.expedia.com/"

# navigate to the search page, then wait for the lodging cards
scrapeless-scraping-browser --session-id "$SID" open "https://www.expedia.com/Hotel-Search?destination=New+York&startDate=2026-06-15&endDate=2026-06-16&rooms=1&adults=2"
scrapeless-scraping-browser --session-id "$SID" wait "div[data-stid='lodging-card-responsive']"

# run the in-page extractor — its JSON comes back in data.result
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for an Expedia /Hotel-Search results page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const decodeHtmlEntities = (s) => {
      if (!s) return s;
      return s
        .replace(/&amp;/g, "&")
        .replace(/&quot;/g, '"')
        .replace(/&#x27;/g, "'")
        .replace(/&#39;/g, "'")
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">");
    };
    const abs = (rel) => {
      if (!rel) return "";
      if (rel.startsWith("http")) return rel;
      return `https://www.expedia.com${rel.startsWith("/") ? "" : "/"}${rel}`;
    };
    const extractHotelId = (url) => {
      if (!url) return "";
      const m = /\.h(\d+)\.Hotel-Information/.exec(url);
      return m ? m[1] : "";
    };

    const out = [];
    document
      .querySelectorAll("div[data-stid='lodging-card-responsive']")
      .forEach((c) => {
        const name = decodeHtmlEntities(
          (c.querySelector("h3.uitk-heading")?.textContent || "").trim() ||
            (c.querySelector("h3")?.textContent || "").trim()
        );
        let href =
          c.querySelector("a.uitk-card-link")?.getAttribute("href") ||
          c
            .querySelector("a[href*='Hotel-Information']")
            ?.getAttribute("href") ||
          "";
        href = decodeHtmlEntities(href);
        const url = abs(href);
        const id = extractHotelId(href);

        let price = null;
        const priceBlock =
          c.querySelector("[data-test-id='price-summary-message-line']")
            ?.textContent || "";
        const pm = priceBlock ? /\$[\d,]+/.exec(priceBlock) : null;
        if (pm) price = pm[0];

        let review = null;
        c.querySelectorAll("[aria-label]").forEach((e) => {
          const a = e.getAttribute("aria-label") || "";
          if (/out of \d+/i.test(a) && !review) review = a;
        });
        const image = c.querySelector("img")?.getAttribute("src") || null;

        if (name && id) {
          out.push({ id, name, url, price, review, image });
        }
      });
    return out;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of `SearchResult`:

```json
[
  {
    "id": "6365",
    "name": "The St. Regis New York",
    "url": "https://www.expedia.com/New-York-Hotels-The-St-Regis-New-York.h6365.Hotel-Information?chkin=2026-06-15&chkout=2026-06-16&...",
    "price": "$1,526",
    "review": null,
    "image": "https://images.trvl-media.com/lodging/1000000/10000/6400/6365/adad701c.jpg?impolicy=resizecrop&ra=fit&rw=455&rh=455"
  }
]
```

## 4. Scrape a hotel page

Reuse the same warmed-up session — `open` a `.Hotel-Information` detail URL (one of the `url`
values from the search result above works) and wait for the title.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.expedia.com/New-York-Hotels-The-St-Regis-New-York.h6365.Hotel-Information"
scrapeless-scraping-browser --session-id "$SID" wait "h1"
# save the hotel extractor (a single expression returning a JSON string)
cat > hotel.js <<'JS'
// In-page extractor for an Expedia hotel detail page.
// Returns a JSON string — a single Hotel (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const decodeHtmlEntities = (s) => {
      if (!s) return s;
      return s
        .replace(/&amp;/g, "&")
        .replace(/&quot;/g, '"')
        .replace(/&#x27;/g, "'")
        .replace(/&#39;/g, "'")
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">");
    };
    const extractHotelId = (url) => {
      if (!url) return "";
      const m = /\.h(\d+)\.Hotel-Information/.exec(url);
      return m ? m[1] : "";
    };
    const txt = (sel) => {
      const n = document.querySelector(sel);
      return n ? n.textContent.trim() : "";
    };

    const url = location.href;
    const name = decodeHtmlEntities(
      txt("h1.uitk-heading") ||
        txt("h1") ||
        document
          .querySelector("meta[property='og:title']")
          ?.getAttribute("content") ||
        ""
    );
    const address =
      txt("[data-stid='content-hotel-address']") ||
      txt("[data-stid='content-hotel-address-link']") ||
      txt("button[aria-label*='address']") ||
      null;
    const description =
      txt("div[data-stid='content-section-section-content']") ||
      txt("section[data-stid='content-section-about-this-property']") ||
      document
        .querySelector("meta[property='og:description']")
        ?.getAttribute("content") ||
      "";
    const amenities = [];
    document
      .querySelectorAll(
        "[data-stid*='amenity'] li, [data-stid='content-amenities-list'] li"
      )
      .forEach((el) => {
        const t = el.textContent.trim();
        if (t) amenities.push(t);
      });
    const images = [];
    document.querySelectorAll("img").forEach((el) => {
      const src = el.getAttribute("src") || el.getAttribute("data-src");
      if (
        src &&
        /\/(media|images|gold|hotels)\//i.test(src) &&
        !images.includes(src)
      ) {
        images.push(src);
      }
    });
    let review = null;
    document.querySelectorAll("[aria-label]").forEach((e) => {
      const a = e.getAttribute("aria-label") || "";
      if (/out of \d+/i.test(a) && !review) review = a;
    });
    const price =
      txt("[data-test-id='price-summary'] span") ||
      txt("[data-stid='price-and-discount']") ||
      null;

    return {
      id: extractHotelId(url),
      url,
      name,
      address,
      description,
      amenities,
      images: images.slice(0, 30),
      review,
      price,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat hotel.js)" --json
```

`data.result` is a single `Hotel`:

```json
{
  "id": "6365",
  "url": "https://www.expedia.com/New-York-Hotels-The-St-Regis-New-York.h6365.Hotel-Information?...",
  "name": "The St. Regis New York",
  "address": "Two East 55th St, New York, NY, 10022",
  "description": "",
  "amenities": [],
  "images": ["https://a.travel-assets.com/media/meso_cm/PAPI/Images/lodging/1000000/30000/23900/23855/c7aeeb04_b.jpg?..."]
}
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/expedia.mjs`](../nodejs/expedia.mjs):

| Extractor | Returns |
| --- | --- |
| `search.js` | list of `SearchResult` |
| `hotel.js` | one `Hotel` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).
