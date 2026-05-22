# Flipkart — CLI surface

Scrape Flipkart product and search pages from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; each page is extracted in-browser with the
CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

## 1. Install

```bash
npm install -g scrapeless-scraping-browser
```

`node` is also required for pulling values out of the CLI's JSON envelope.

## 2. Set your API key

```bash
export SCRAPELESS_API_KEY=sk_...      # sign up at https://app.scrapeless.com
```

## 3. Scrape a product page

```bash
# open a cloud browser session — IN proxy for Flipkart India prices
scrapeless-scraping-browser new-session --name fk-cli --ttl 300 --proxy-country IN --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate and wait for JS hydration (~12 s needed for ld+json injection)
scrapeless-scraping-browser --session-id "$SID" open \
  "https://www.flipkart.com/apple-iphone-16-white-128-gb/p/itm7c0281cd247be" \
  --wait-until load

# wait for content to settle (Flipkart requires ~12 s)
scrapeless-scraping-browser --session-id "$SID" wait 12000

# run the in-page extractor
scrapeless-scraping-browser --session-id "$SID" eval "$(cat product.js)" --json

# release the session
scrapeless-scraping-browser --session-id "$SID" close
```

Save the following as `product.js`:

```js
// In-page extractor for a Flipkart product page (www.flipkart.com/<slug>/p/<id>).
// Returns a JSON string — a single Product (see ../../../DATA_MODEL.md).
// Parses the schema.org Product ld+json array (dynamically injected after JS hydration).
JSON.stringify(
  (function () {
    const url = location.href;
    const blocks = [];
    document.querySelectorAll('script[type="application/ld+json"]').forEach(el => {
      try {
        const parsed = JSON.parse(el.textContent);
        // Flipkart wraps the Product in a top-level array
        if (Array.isArray(parsed)) blocks.push(...parsed);
        else blocks.push(parsed);
      } catch (e) {}
    });

    const prod = blocks.find(b => String((b && b["@type"]) || "").toLowerCase() === "product");
    if (!prod) throw new Error("Product ld+json not found — page may not have fully hydrated");

    const offer = Array.isArray(prod.offers) ? prod.offers[0] : (prod.offers || {});
    const rating = prod.aggregateRating || {};
    let image = prod.image;
    if (Array.isArray(image)) image = image[0] || null;

    const brand = prod.brand && typeof prod.brand === "object"
      ? prod.brand.name
      : (prod.brand || null);

    return {
      id: String(prod.sku || ""),
      name: prod.name || "",
      brand,
      description: prod.description || null,
      image,
      price: offer.price != null ? Number(offer.price) : null,
      priceCurrency: offer.priceCurrency || "INR",
      availability: offer.availability || null,
      ratingValue: rating.ratingValue != null ? Number(rating.ratingValue) : null,
      reviewCount: rating.reviewCount != null ? Number(rating.reviewCount) : null,
      url,
      breadcrumb: [],
    };
  })()
)
```

## 4. Scrape a search/listing page

```bash
# Reuse the same session or open a new one
scrapeless-scraping-browser --session-id "$SID" open \
  "https://www.flipkart.com/search?q=iphone+16&marketplace=FLIPKART" \
  --wait-until load
scrapeless-scraping-browser --session-id "$SID" wait 6000
scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
scrapeless-scraping-browser --session-id "$SID" close
```

Save the following as `search.js`:

```js
// In-page extractor for a Flipkart search page (www.flipkart.com/search?q=<query>).
// Returns a JSON string — an array of SearchResult objects (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    function parsePriceText(text) {
      if (!text) return null;
      const m = text.match(/[\d,]+/);
      if (!m) return null;
      const n = parseInt(m[0].replace(/,/g, ""), 10);
      return Number.isFinite(n) ? n : null;
    }

    const items = [];
    document.querySelectorAll("[data-id]").forEach(el => {
      const id = el.dataset.id || "";

      const link = el.querySelector('a[href*="/p/"]');
      const href = link ? link.getAttribute("href") : "";
      const url = href ? ("https://www.flipkart.com" + href.split("?")[0]) : null;

      const nameEl = el.querySelector(".RG5Slk");
      const imgEl = el.querySelector("img");
      const name = (nameEl ? nameEl.textContent : (imgEl ? imgEl.alt : "")).trim();

      const image = imgEl ? imgEl.src || null : null;

      const priceEl = el.querySelector(".hZ3P6w");
      const price = parsePriceText(priceEl ? priceEl.textContent : "");

      const ratingEl = el.querySelector(".MKiFS6");
      const ratingValue = ratingEl ? parseFloat(ratingEl.textContent.trim()) : null;

      if (id && (name || url)) {
        items.push({ id, name, url, image, price, priceCurrency: "INR", ratingValue });
      }
    });

    return items;
  })()
)
```

## 5. Output shape

| Extractor   | Returns                    |
| ----------- | -------------------------- |
| `product.js` | one `Product`             |
| `search.js`  | array of `SearchResult`   |

Full field tables are in [`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
