# Adidas — CLI surface

Scrape adidas.com search (PLP) and product (PDP) pages from the command line with the
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
in-page extractor. adidas embeds its product/listing data in `application/ld+json` blocks, so the
stable marker is the JSON-LD `<script>` itself. Start with a product page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name adidas-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the JSON-LD block to render
scrapeless-scraping-browser --session-id "$SID" open "https://www.adidas.com/us/samba-og-shoes/B75806.html"
scrapeless-scraping-browser --session-id "$SID" wait "script[type=application/ld+json]"

# run the in-page extractor — its JSON comes back in data.result.
# The extractor JS is the PRODUCT_JS heredoc: it reads the ld+json
# Product node (DOM fallback for name/description/images) and returns one Product.
# save the product extractor (a single expression returning a JSON string)
cat > product.js <<'JS'
// In-page extractor for an Adidas product detail page.
// Returns a JSON string — a single Product (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const url = location.href;

    function* iterJsonldNodes() {
      const blocks = Array.from(
        document.querySelectorAll('script[type="application/ld+json"]')
      ).map((el) => el.textContent);
      for (const raw of blocks) {
        if (!raw || !raw.trim()) continue;
        let data;
        try {
          data = JSON.parse(raw);
        } catch (e) {
          continue;
        }
        const nodes = Array.isArray(data) ? data : [data];
        for (const node of nodes) {
          if (!node || typeof node !== "object") continue;
          if (Array.isArray(node["@graph"])) {
            for (const sub of node["@graph"]) {
              if (sub && typeof sub === "object") yield sub;
            }
          } else {
            yield node;
          }
        }
      }
    }

    function typeMatches(node, wanted) {
      const t = node["@type"];
      if (typeof t === "string") return t === wanted;
      if (Array.isArray(t)) return t.includes(wanted);
      return false;
    }

    function firstOffer(node) {
      const offers = node?.offers;
      if (Array.isArray(offers) && offers.length) {
        return typeof offers[0] === "object" ? offers[0] : {};
      }
      if (offers && typeof offers === "object") {
        if (Array.isArray(offers.offers) && offers.offers.length) {
          return typeof offers.offers[0] === "object" ? offers.offers[0] : {};
        }
        return offers;
      }
      return {};
    }

    function aggregateRating(node) {
      const ar = node?.aggregateRating;
      return ar && typeof ar === "object" ? ar : {};
    }

    const PRODUCT_ID_RE =
      /\/([A-Z]{2}\d{4}|[A-Z]{3}\d{2}|[A-Z]{2}\d{3}[A-Z]?|[A-Z]{1,3}\d{3,4})\.html/i;

    function extractProductId(u) {
      if (!u) return "";
      const m = u.match(PRODUCT_ID_RE);
      if (m) return m[1].toUpperCase();
      try {
        const parsed = new URL(u);
        const last =
          parsed.pathname.replace(/\/$/, "").split("/").pop() || "";
        return last.replace(/\.html$/i, "");
      } catch (e) {
        return "";
      }
    }

    function clean(value) {
      if (value == null) return null;
      const v = String(value).replace(/\s+/g, " ").trim();
      return v || null;
    }

    let ld = {};
    for (const node of iterJsonldNodes()) {
      if (typeMatches(node, "Product")) {
        ld = node;
        break;
      }
    }

    const offer = firstOffer(ld);
    const rating = aggregateRating(ld);

    let images = [];
    if (typeof ld.image === "string") images = [ld.image];
    else if (Array.isArray(ld.image))
      images = ld.image.filter(Boolean).map(String);
    else {
      images = Array.from(
        document.querySelectorAll('meta[property="og:image"]')
      )
        .map((el) => el.getAttribute("content"))
        .filter(Boolean);
    }

    const name = ld.name
      ? clean(ld.name)
      : clean(document.querySelector("h1")?.textContent);
    const description = ld.description
      ? clean(ld.description)
      : clean(
          document
            .querySelector('meta[name="description"]')
            ?.getAttribute("content")
        );

    const sku = ld.sku || ld.productID || extractProductId(url);

    let brand = "adidas";
    if (ld.brand) {
      brand =
        typeof ld.brand === "object"
          ? ld.brand.name || "adidas"
          : String(ld.brand);
    }

    let priceValue = null;
    if (offer.price != null) {
      const n = parseFloat(String(offer.price).replace(/,/g, ""));
      priceValue = Number.isFinite(n) ? n : null;
    }

    let availability = offer.availability ?? null;
    if (typeof availability === "string" && availability.includes("/")) {
      availability = availability.split("/").pop();
    }

    return {
      id: String(sku || ""),
      url,
      name: name || "",
      brand: clean(brand) || "adidas",
      description,
      price: priceValue,
      priceCurrency: offer.priceCurrency ?? null,
      availability,
      images,
      rating: rating.ratingValue != null ? parseFloat(rating.ratingValue) : null,
      reviewCount:
        rating.reviewCount != null ? parseInt(rating.reviewCount, 10) : null,
      category: ld.category ? clean(ld.category) : null,
      color: ld.color ? clean(ld.color) : null,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat product.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `Product` object:

```json
{
  "id": "B75806",
  "url": "https://www.adidas.com/us/samba-og-shoes/B75806.html",
  "name": "Samba OG Shoes",
  "brand": "adidas",
  "description": "Born on the pitch, the Samba is a timeless icon of street style. ...",
  "price": 100,
  "priceCurrency": "USD",
  "availability": "InStock",
  "images": ["https://assets.adidas.com/images/.../Samba_OG_Shoes_White_B75806_01_00_standard.jpg"],
  "rating": 4.8,
  "reviewCount": 1612,
  "category": "Shoes",
  "color": "Cloud White / Core Black / gum"
}
```

## 4. Scrape a search page

Reuse the same session — just `open` a category/search URL and wait for the JSON-LD block. The PLP
exposes an `ItemList` JSON-LD block (DOM fallback to `[data-testid="plp-product-card"]`).

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.adidas.com/us/men-shoes"
scrapeless-scraping-browser --session-id "$SID" wait "script[type=application/ld+json]"
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for an Adidas search / product-listing page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    function* iterJsonldNodes() {
      const blocks = Array.from(
        document.querySelectorAll('script[type="application/ld+json"]')
      ).map((el) => el.textContent);
      for (const raw of blocks) {
        if (!raw || !raw.trim()) continue;
        let data;
        try {
          data = JSON.parse(raw);
        } catch (e) {
          continue;
        }
        const nodes = Array.isArray(data) ? data : [data];
        for (const node of nodes) {
          if (!node || typeof node !== "object") continue;
          if (Array.isArray(node["@graph"])) {
            for (const sub of node["@graph"]) {
              if (sub && typeof sub === "object") yield sub;
            }
          } else {
            yield node;
          }
        }
      }
    }

    function typeMatches(node, wanted) {
      const t = node["@type"];
      if (typeof t === "string") return t === wanted;
      if (Array.isArray(t)) return t.includes(wanted);
      return false;
    }

    function firstOffer(node) {
      const offers = node?.offers;
      if (Array.isArray(offers) && offers.length) {
        return typeof offers[0] === "object" ? offers[0] : {};
      }
      if (offers && typeof offers === "object") {
        if (Array.isArray(offers.offers) && offers.offers.length) {
          return typeof offers.offers[0] === "object" ? offers.offers[0] : {};
        }
        return offers;
      }
      return {};
    }

    const PRODUCT_ID_RE =
      /\/([A-Z]{2}\d{4}|[A-Z]{3}\d{2}|[A-Z]{2}\d{3}[A-Z]?|[A-Z]{1,3}\d{3,4})\.html/i;

    function extractProductId(u) {
      if (!u) return "";
      const m = u.match(PRODUCT_ID_RE);
      if (m) return m[1].toUpperCase();
      try {
        const parsed = new URL(u);
        const last =
          parsed.pathname.replace(/\/$/, "").split("/").pop() || "";
        return last.replace(/\.html$/i, "");
      } catch (e) {
        return "";
      }
    }

    function clean(value) {
      if (value == null) return null;
      const v = String(value).replace(/\s+/g, " ").trim();
      return v || null;
    }

    const items = [];

    for (const node of iterJsonldNodes()) {
      if (!typeMatches(node, "ItemList")) continue;
      for (const el of node.itemListElement || []) {
        if (!el || typeof el !== "object") continue;
        const item =
          el.item && typeof el.item === "object" ? el.item : el;
        const offer = firstOffer(item);
        const url = item.url || el.url || "";
        const sku = item.sku || item.productID || extractProductId(url);
        let priceValue = null;
        if (offer.price != null) {
          const n = parseFloat(String(offer.price).replace(/,/g, ""));
          priceValue = Number.isFinite(n) ? n : null;
        }
        let img = null;
        if (typeof item.image === "string") img = item.image;
        else if (Array.isArray(item.image) && item.image.length)
          img = String(item.image[0]);
        items.push({
          id: sku ? String(sku) : "",
          url,
          name: item.name || "",
          image: img,
          price: priceValue,
          priceCurrency: offer.priceCurrency ?? null,
        });
      }
      if (items.length) break;
    }

    if (!items.length) {
      document
        .querySelectorAll(
          '[data-testid="plp-product-card"], article[data-testid="product-card"]'
        )
        .forEach((card) => {
          const link = card.querySelector("a")?.getAttribute("href") || "";
          let absolute = "";
          try {
            absolute = link
              ? new URL(link, "https://www.adidas.com").toString()
              : "";
          } catch (e) {}
          const sku = absolute
            ? extractProductId(absolute)
            : card.getAttribute("data-grid-id") || "";
          const name = clean(
            card.querySelector('[data-testid="product-card-title"]')
              ?.textContent ||
              card.querySelector("p")?.textContent
          );
          const priceText = clean(
            card.querySelector('[data-testid="primary-price"]')?.textContent ||
              card.querySelector('div[class*="price"]')?.textContent
          );
          let priceValue = null;
          if (priceText) {
            const m = priceText.match(/[\d,.]+/);
            if (m) {
              const n = parseFloat(m[0].replace(/,/g, ""));
              priceValue = Number.isFinite(n) ? n : null;
            }
          }
          const img =
            card.querySelector("img")?.getAttribute("src") ||
            card.querySelector("img")?.getAttribute("data-src") ||
            null;
          items.push({
            id: sku || "",
            url: absolute,
            name: name || "",
            image: img,
            price: priceValue,
            priceCurrency:
              priceText && priceText.includes("$") ? "USD" : null,
          });
        });
    }

    return items;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
```

`data.result` is a list of `SearchResult`:

```json
[
  {
    "id": "ID8757",
    "url": "https://www.adidas.com/us/galaxy-7-running-shoes/ID8757.html",
    "name": "Galaxy 7 Running Shoes",
    "image": "https://assets.adidas.com/images/.../Galaxy_7_Running_Shoes_Black_ID8757_HM1.jpg",
    "price": 36,
    "priceCurrency": "USD"
  }
]
```

## 5. Output shape

Each extractor is a single expression that returns a JSON string, kept in lockstep with the parsers
in [`../nodejs/adidas.mjs`](../nodejs/adidas.mjs):

| Extractor (heredoc) | Returns |
| --- | --- |
| `SEARCH_JS` | list of `SearchResult` |
| `PRODUCT_JS` | one `Product` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## Notes

- Set `proxyCountry` to `US` at session creation for USD pricing and US inventory — adidas localizes
  price, currency, and availability by region.
- adidas.com is fronted by Akamai; if a page returns no JSON-LD, retry on a fresh session.
