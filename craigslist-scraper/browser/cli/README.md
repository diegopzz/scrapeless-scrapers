# Craigslist — CLI surface

Scrape Craigslist search and listing pages from the command line with the
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
in-page extractor. Start with a city/category search page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name craigslist-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the result cards to render
scrapeless-scraping-browser --session-id "$SID" open "https://newyork.craigslist.org/search/sss?query=bicycle"
scrapeless-scraping-browser --session-id "$SID" wait ".cl-search-result"

# run the in-page extractor — its JSON comes back in data.result
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a Craigslist city/category search page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  Array.from(document.querySelectorAll(".cl-search-result"))
    .map((el) => {
      const id = el.getAttribute("data-pid") || "";
      if (!id) return null;
      const title =
        el
          .querySelector("a.posting-title span.label")
          ?.textContent.trim() ||
        el.getAttribute("title") ||
        "";
      const href =
        el.querySelector("a.posting-title")?.getAttribute("href") ||
        el.querySelector("a.main")?.getAttribute("href") ||
        "";
      let url = "";
      if (href) {
        try {
          url = new URL(href, location.href).toString();
        } catch (e) {
          url = href;
        }
      }
      const price =
        el.querySelector("span.priceinfo")?.textContent.trim() || null;
      const locationText =
        el.querySelector("span.result-location")?.textContent.trim() || null;
      const postedAt =
        el
          .querySelector("span.result-posted-date")
          ?.textContent.trim() || null;
      const image =
        el.querySelector("div.swipe img")?.getAttribute("src") || null;
      if (!id || !title) return null;
      return { id, title, url, price, location: locationText, postedAt, image };
    })
    .filter(Boolean)
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
    "id": "7931721992",
    "title": "Giant Enchant LIV  XS Women's Mountain Bike",
    "url": "https://newyork.craigslist.org/lgi/bik/d/glen-cove-giant-enchant-liv-xs-womens/7931721992.html",
    "price": "$195",
    "location": "Glen Cove",
    "postedAt": "1 min ago",
    "image": "https://images.craigslist.org/d/7931721992/00a0a_gqn8AIhXluO_0CI0t2_300x300.jpg"
  }
]
```

## 4. Scrape a listing page

Reuse the same session — `open` a listing detail URL (one of the `url` values from the search
result above works) and wait for the title.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://newyork.craigslist.org/lgi/bik/d/glen-cove-giant-enchant-liv-xs-womens/7931721992.html"
scrapeless-scraping-browser --session-id "$SID" wait "#titletextonly"
# save the listing extractor (a single expression returning a JSON string)
cat > listing.js <<'JS'
// In-page extractor for a Craigslist listing detail page.
// Returns a JSON string — a single Listing (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const url = location.href.split("?")[0].split("#")[0];
    const idMatch = /\/(\d+)\.html/.exec(url);
    const id = idMatch ? idMatch[1] : "";

    const title =
      document.querySelector("#titletextonly")?.textContent.trim() || "";
    const price =
      document
        .querySelector("h1.postingtitle span.price, span.price")
        ?.textContent.trim() || null;

    // Location: parenthetical inside the postingtitle, e.g. " (Lower East Side)".
    const titleHtml = document.querySelector("h1.postingtitle")?.innerHTML || "";
    const locMatch = /\(([^()]+)\)\s*</.exec(titleHtml);
    const locationText = locMatch ? locMatch[1].trim() : null;

    const postedAt =
      document
        .querySelector("time.date.timeago")
        ?.getAttribute("datetime") || null;

    // Strip the QR/print scaffolding from the body, take the first meaningful text.
    let description = "";
    const bodyEl = document.querySelector("#postingbody");
    if (bodyEl) {
      const clone = bodyEl.cloneNode(true);
      clone
        .querySelectorAll("div.print-information, div.notices, .reply-button-row")
        .forEach((n) => n.remove());
      description = (clone.textContent || "")
        .replace(/^\s*QR Code Link to This Post\s*/i, "")
        .trim();
    }

    const attributes = [];
    document.querySelectorAll("p.attrgroup span").forEach((el) => {
      const t = el.textContent.trim();
      if (t) attributes.push(t);
    });

    let images = [];
    document.querySelectorAll("#thumbs a").forEach((el) => {
      const href = el.getAttribute("href");
      if (href) images.push(href);
    });
    if (!images.length) {
      document
        .querySelectorAll("div.slide.first img, div.slide img")
        .forEach((el) => {
          const src = el.getAttribute("src");
          if (src) images.push(src);
        });
    }

    const mapEl = document.querySelector("div#map");
    const latitude = mapEl?.getAttribute("data-latitude") || null;
    const longitude = mapEl?.getAttribute("data-longitude") || null;

    const crumbs = Array.from(
      document.querySelectorAll("ul.breadcrumbs li")
    ).map((el) => el.textContent.trim());
    const section = crumbs.length >= 2 ? crumbs[1] : null;
    const category = crumbs.length >= 3 ? crumbs[2] : null;

    return {
      id,
      url,
      title,
      price,
      location: locationText,
      postedAt,
      description,
      attributes,
      images,
      latitude,
      longitude,
      section,
      category,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat listing.js)" --json
```

`data.result` is a single `Listing`:

```json
{
  "id": "7931721992",
  "url": "https://newyork.craigslist.org/lgi/bik/d/glen-cove-giant-enchant-liv-xs-womens/7931721992.html",
  "title": "Giant Enchant LIV  XS Women's Mountain Bike",
  "price": "$195",
  "location": "Glen Cove",
  "postedAt": "2026-05-02T16:02:56-0400",
  "description": "Serious buyers please include your phone number ...",
  "attributes": [],
  "images": ["https://images.craigslist.org/00a0a_gqn8AIhXluO_0CI0t2_600x450.jpg"]
}
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/craigslist.mjs`](../nodejs/craigslist.mjs):

| Extractor | Returns |
| --- | --- |
| `search.js` | list of `SearchResult` |
| `listing.js` | one `Listing` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).
