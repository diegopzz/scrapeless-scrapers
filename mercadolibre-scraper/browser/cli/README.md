# MercadoLibre — CLI surface

Scrape MercadoLibre product and search pages from the command line with the
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
# open a cloud browser session — MX proxy for mercadolibre.com.mx
scrapeless-scraping-browser new-session --name ml-cli --ttl 300 --proxy-country MX --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate; use --wait-until load so ML's micro-landing redirect resolves
scrapeless-scraping-browser --session-id "$SID" open "https://articulo.mercadolibre.com.mx/MLM-4493249540-tenis-adidas-casual-run-60s-40-hombre-negro-jr6622-_JM" --wait-until load

# wait for content to settle
scrapeless-scraping-browser --session-id "$SID" wait 5000

# run the in-page extractor
scrapeless-scraping-browser --session-id "$SID" eval "$(cat product.js)" --json

# release the session
scrapeless-scraping-browser --session-id "$SID" close
```

Save the following as `product.js`:

```js
// In-page extractor for a MercadoLibre product page (articulo.mercadolibre.com.mx/MLM-<id>).
// Returns a JSON string — a single Product (see ../../../DATA_MODEL.md).
// Parses the schema.org Product + BreadcrumbList ld+json blocks.
JSON.stringify(
  (function () {
    const url = location.href;
    const blocks = [];
    document.querySelectorAll('script[type="application/ld+json"]').forEach(el => {
      try { blocks.push(JSON.parse(el.textContent)); } catch (e) {}
    });

    const prod = blocks.find(b => String((b && b["@type"]) || "").toLowerCase() === "product");
    if (!prod) throw new Error("Product ld+json not found");

    const bcLd = blocks.find(b => b && b["@type"] === "BreadcrumbList");
    const breadcrumb = ((bcLd && bcLd.itemListElement) || []).map(b => {
      // ML uses item.name + item["@id"] (not top-level name/item)
      const item = (b && b.item && typeof b.item === "object") ? b.item : null;
      return {
        name: item ? item.name : (b && b.name),
        url: item ? item["@id"] : (b && typeof b.item === "string" ? b.item : null),
        position: b && b.position,
      };
    });

    const offer = Array.isArray(prod.offers) ? prod.offers[0] : (prod.offers || {});
    const rating = prod.aggregateRating || {};
    let image = prod.image;
    if (Array.isArray(image)) image = image[0] || null;

    return {
      id: String(prod.sku || ""),
      name: prod.name || "",
      brand: prod.brand ? String(prod.brand) : null,
      description: prod.description || null,
      image,
      price: offer.price != null ? Number(offer.price) : null,
      priceCurrency: offer.priceCurrency || null,
      availability: offer.availability || null,
      ratingValue: rating.ratingValue != null ? Number(rating.ratingValue) : null,
      reviewCount: rating.reviewCount != null ? Number(rating.reviewCount) : null,
      url: prod.url || url,
      breadcrumb,
    };
  })()
)
```

## 4. Scrape a search/listing page

```bash
# Reuse the same session or open a new one
scrapeless-scraping-browser --session-id "$SID" open "https://listado.mercadolibre.com.mx/tenis" --wait-until load
scrapeless-scraping-browser --session-id "$SID" wait 5000
scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
scrapeless-scraping-browser --session-id "$SID" close
```

Save the following as `search.js`:

```js
// In-page extractor for a MercadoLibre listing/search page (listado.mercadolibre.com.mx/<query>).
// Returns a JSON string — an array of SearchResult objects (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const MLM_ID_RE = /\/(MLM[\d]+)/i;

    function parsePrice(text) {
      if (!text) return null;
      const m = text.match(/[\d,]+/);
      if (!m) return null;
      const n = parseFloat(m[0].replace(/,/g, ""));
      return Number.isFinite(n) ? n : null;
    }

    const items = [];
    document.querySelectorAll('li[class*="ui-search-layout__item"]').forEach(el => {
      const titleEl = el.querySelector('[class*="poly-component__title"]') || el.querySelector("h2");
      const name = (titleEl && titleEl.textContent || "").trim();

      const anchor = el.querySelector('a[href*="/MLM-"]');
      const rawLink = anchor ? anchor.href : "";
      const url = rawLink ? rawLink.split("?")[0] : null;
      const idMatch = url && url.match(MLM_ID_RE);
      const id = idMatch ? idMatch[1] : "";

      const img = el.querySelector("img");
      const image = img ? (img.src || img.dataset.src || null) : null;

      const priceEl = el.querySelector('[class*="price__fraction"]') ||
                      el.querySelector('[class*="andes-money-amount__fraction"]');
      const price = parsePrice(priceEl && priceEl.textContent);

      if (name || url) {
        items.push({ id, name, url, image, price, priceCurrency: "MXN" });
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
