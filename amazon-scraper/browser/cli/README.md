# Amazon — CLI surface

Scrape Amazon search, product, and review pages from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. Each page is driven by its own Scrapeless cloud browser session and extracted in-browser with
the CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

Amazon serves anti-bot interstitials to datacenter IPs, so — exactly like the [`nodejs/`](../nodejs/amazon.mjs)
surface — every session uses a **US residential proxy** (`--proxy-country US`) and **dismisses the
"Continue shopping" interstitial** before extracting. Anti-bot is intermittent: **if an extractor
returns empty fields, the page hit an interstitial — close the session and re-run; a fresh session
usually renders.** Use one fresh session per page (sessions terminate when their connection drops).

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

## 3. Scrape a product page

Open a fresh US-proxied session, navigate, dismiss the interstitial, then wait for the **product
detail table** (`#productDetails_detailBullets_sections1 tr`) — a deep marker that only renders once
the full page, including the ratings widget, has loaded.

```bash
# fresh session with a US residential proxy -> taskId in data.taskId
SID=$(scrapeless-scraping-browser new-session --name amazon-product --ttl 300 --proxy-country US --json \
  | node -pe 'JSON.parse(require("fs").readFileSync(0)).data.taskId')

scrapeless-scraping-browser --session-id "$SID" open "https://www.amazon.com/PlayStation-5-Console-CFI-1215A01X/dp/B0BCNKKZ91/"
# dismiss the "Continue shopping" interstitial if Amazon shows it
scrapeless-scraping-browser --session-id "$SID" eval '[...document.querySelectorAll("button,a,input[type=submit]")].find(b=>/continue shopping/i.test(b.textContent||b.value||""))?.click()'
scrapeless-scraping-browser --session-id "$SID" wait "#productDetails_detailBullets_sections1 tr"

# save the in-page extractor (a single expression returning a JSON string — one Product)
cat > product.js <<'JS'
// In-page extractor for an Amazon product detail page.
// Returns a JSON string — a single Product (see ../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const html = document.documentElement.outerHTML;
    let images = [];
    const colorMatch = html.match(/colorImages':.*'initial':\s*(\[.+?\])\},\n/);
    if (colorMatch) {
      try {
        images = JSON.parse(colorMatch[1]).map((img) => img.large);
      } catch (e) {}
    }
    const galleryMatch = html.match(/imageGalleryData'\s*:\s*(\[.+\]),\n/);
    if (galleryMatch) {
      try {
        images = JSON.parse(galleryMatch[1]).map((img) => img.mainUrl);
      } catch (e) {}
    }

    const txt = (node) => (node?.textContent ?? "").trim();

    const info_table = {};
    document
      .querySelectorAll("#productDetails_detailBullets_sections1 tr")
      .forEach((row) => {
        const label = txt(row.querySelector("th"));
        let value = txt(row.querySelector("td"));
        if (!value) value = txt(row.querySelector("td span"));
        if (label) info_table[label] = value;
      });
    info_table["Customer Reviews"] =
      txt(document.querySelector("td:has(#averageCustomerReviews) span.a-icon-alt")) ||
      null;
    const rankRow = Array.from(
      document.querySelectorAll("#productDetails_detailBullets_sections1 tr, table tr")
    ).find((r) => /Best Sellers Rank/.test(r.querySelector("th")?.textContent || ""));
    info_table["Best Sellers Rank"] = rankRow
      ? txt(rankRow.querySelector("td")).replace(/\s+/g, " ")
      : "";

    return {
      name: txt(document.querySelector("#productTitle")),
      asin: (document.querySelector("input[name=ASIN]")?.value ?? "").trim(),
      style: txt(
        document.querySelector("[id^=inline-twister-expanded-dimension-text]")
      ),
      description: Array.from(
        document.querySelectorAll("#productDescription p span")
      )
        .map((el) => el.textContent)
        .join("\n")
        .trim(),
      stars: txt(document.querySelector("i[data-hook=average-star-rating]")),
      rating_count: txt(
        document.querySelector("span[data-hook=total-review-count]")
      ),
      features: Array.from(document.querySelectorAll("#feature-bullets li"))
        .map((el) => el.textContent.trim())
        .filter(Boolean),
      images,
      info_table,
    };
  })()
)
JS

# run it — its JSON comes back in data.result
scrapeless-scraping-browser --session-id "$SID" eval "$(cat product.js)" --json
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `Product` object:

```json
{
  "name": "PlayStation 5 Console (PS5)",
  "asin": "B0BCNKKZ91",
  "style": "Disc",
  "stars": "4.8 out of 5 stars",
  "rating_count": "9,183 global ratings",
  "features": ["Model Number CFI-1215A01X.", "..."],
  "images": ["https://m.media-amazon.com/images/I/51VHiQ+LrsL.jpg"],
  "info_table": { "Best Sellers Rank": "...", "Customer Reviews": "4.8 out of 5 stars" }
}
```

## 4. Scrape reviews

Reviews live on the product page. Open the product URL in its own session, dismiss the interstitial,
and wait for the review list (`#cm-cr-dp-review-list`). Some products expose no reviews in this block
— an empty `[]` is a valid result.

```bash
SID=$(scrapeless-scraping-browser new-session --name amazon-reviews --ttl 300 --proxy-country US --json \
  | node -pe 'JSON.parse(require("fs").readFileSync(0)).data.taskId')

scrapeless-scraping-browser --session-id "$SID" open "https://www.amazon.com/PlayStation-5-Console-CFI-1215A01X/dp/B0BCNKKZ91/"
scrapeless-scraping-browser --session-id "$SID" eval '[...document.querySelectorAll("button,a,input[type=submit]")].find(b=>/continue shopping/i.test(b.textContent||b.value||""))?.click()'
scrapeless-scraping-browser --session-id "$SID" wait "#cm-cr-dp-review-list"

# save the reviews extractor (returns a JSON string — a list of Review)
cat > reviews.js <<'JS'
// In-page extractor for the review block on an Amazon product page.
// Returns a JSON string — a list of Review (see ../../DATA_MODEL.md).
JSON.stringify(
  Array.from(
    document.querySelectorAll("#cm-cr-dp-review-list li.review")
  ).map((el) => {
    const ratingText =
      el.querySelector("[data-hook=review-star-rating]")?.textContent ?? "";
    const ratingMatch = ratingText.match(/(\d+\.?\d*) out/);
    return {
      text: (el.querySelector("[data-hook=review-collapsed]")?.textContent ?? "").trim(),
      title:
        el.querySelector("[data-hook=review-title] > span")?.textContent || null,
      location_and_date:
        el.querySelector("span[data-hook=review-date]")?.textContent || null,
      verified: !!el.querySelector("span[data-hook=avp-badge]")?.textContent,
      rating: ratingMatch ? parseFloat(ratingMatch[1]) : null,
    };
  })
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat reviews.js)" --json
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of `Review`:

```json
[
  {
    "title": "Great console",
    "text": "The new controller is awesome! ...",
    "location_and_date": "Reviewed in the United States on ...",
    "verified": true,
    "rating": 5
  }
]
```

## 5. Scrape a search page

```bash
SID=$(scrapeless-scraping-browser new-session --name amazon-search --ttl 300 --proxy-country US --json \
  | node -pe 'JSON.parse(require("fs").readFileSync(0)).data.taskId')

scrapeless-scraping-browser --session-id "$SID" open "https://www.amazon.com/s?k=kindle"
scrapeless-scraping-browser --session-id "$SID" eval '[...document.querySelectorAll("button,a,input[type=submit]")].find(b=>/continue shopping/i.test(b.textContent||b.value||""))?.click()'
scrapeless-scraping-browser --session-id "$SID" wait "div.s-result-item[data-component-type=s-search-result]"

# save the search extractor (returns a JSON string — a list of SearchResult)
cat > search.js <<'JS'
// In-page extractor for an Amazon search results page.
// Returns a JSON string — a list of SearchResult (see ../../DATA_MODEL.md).
JSON.stringify(
  Array.from(
    document.querySelectorAll("div.s-result-item[data-component-type=s-search-result]")
  ).map((el) => {
    const href = el.querySelector("div > a")?.getAttribute("href");
    if (!href) return null;
    let url;
    try {
      url = new URL(href, location.href).toString().split("?")[0];
    } catch (e) {
      return null;
    }
    if (url.includes("/slredirect/")) return null;

    const ratingAria =
      el.querySelector("div[data-cy='reviews-block'] a[aria-label*='out of']")
        ?.getAttribute("aria-label") ?? "";
    const ratingMatch = ratingAria.match(/(\d+\.?\d*) out/);
    const ratingCountAria = el
      .querySelector("div[data-cy='reviews-block'] a[aria-label*='ratings']")
      ?.getAttribute("aria-label");

    return {
      url,
      title: el.querySelector("div > a > h2")?.getAttribute("aria-label") ?? null,
      price:
        el.querySelector(".a-price[data-a-size=xl] .a-offscreen")?.textContent || null,
      real_price:
        Array.from(
          el.querySelectorAll("div[data-cy='secondary-offer-recipe'] span.a-color-base")
        ).find((e) => e.textContent.includes("$"))?.textContent || null,
      rating: ratingMatch ? parseFloat(ratingMatch[1]) : null,
      rating_count: ratingCountAria
        ? parseInt(ratingCountAria.replace(/,/g, "").replace(" ratings", ""), 10)
        : null,
    };
  }).filter(Boolean)
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of `SearchResult`:

```json
[
  {
    "url": "https://www.amazon.com/All-new-Amazon-Kindle-Paperwhite-glare-free/dp/B0CFPJYX7P/",
    "title": "Kindle Paperwhite 16GB (newest model) ...",
    "price": "$159.99",
    "real_price": "$140.79",
    "rating": 4.7,
    "rating_count": 18223
  }
]
```

## 6. Output shape

Each extractor above is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/amazon.mjs`](../nodejs/amazon.mjs):

| Extractor | Returns |
| --- | --- |
| `search.js` | list of `SearchResult` |
| `product.js` | one `Product` |
| `reviews.js` | list of `Review` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
