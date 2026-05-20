# Macy's — CLI surface

Scrape Macy's product and category/search pages from the command line with the
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
in-page extractor. Start with a product page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name macys-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the JSON-LD block (or the product heading)
scrapeless-scraping-browser --session-id "$SID" open "https://www.macys.com/shop/product/levis-mens-541-athletic-fit-jean?ID=2061867"
scrapeless-scraping-browser --session-id "$SID" wait "script[type='application/ld+json'], h1"

# run the in-page extractor — its JSON comes back in data.result
# save the product extractor (a single expression returning a JSON string)
cat > product.js <<'JS'
// In-page extractor for a Macy's product detail page.
// Returns a JSON string — a list of Product (see ../../../DATA_MODEL.md). The
// CLI surface scrapes a single PDP URL, so the list holds one entry. Mirrors
// `parseProduct` in ../nodejs/macys.mjs: prefer JSON-LD, fall back to DOM.
//
// Unlike the nodejs surface (which throws + retries on a fresh session when
// JSON-LD is missing), the CLI has no session-rotation loop — so we fall back
// to DOM scraping and return a partial Product rather than aborting. Callers
// can still detect a blocked / delisted page from an empty `name`.
JSON.stringify(
  [(function () {
    const clean = (value) => {
      if (value == null) return null;
      const v = String(value).replace(/\s+/g, " ").trim();
      return v || null;
    };
    const toNumber = (value) => {
      if (value == null) return null;
      const n = parseFloat(String(value).replace(/[^\d.\-]/g, ""));
      return Number.isFinite(n) ? n : null;
    };
    const shortAvailability = (value) => {
      if (typeof value !== "string") return null;
      return value.includes("/") ? value.split("/").pop() : value;
    };
    const extractProductId = (url) => {
      if (!url) return "";
      try {
        const u = new URL(url, "https://www.macys.com");
        const id = u.searchParams.get("ID");
        if (id) return id;
      } catch (e) {}
      const m = String(url).match(/[?&]ID=(\d+)/i);
      return m ? m[1] : "";
    };
    const typeMatches = (node, wanted) => {
      const t = node["@type"];
      if (typeof t === "string") return t === wanted;
      if (Array.isArray(t)) return t.includes(wanted);
      return false;
    };
    const txt = (sel) => document.querySelector(sel)?.textContent ?? "";

    // Walk every JSON-LD block, descending into @graph arrays.
    const nodes = [];
    document
      .querySelectorAll('script[type="application/ld+json"]')
      .forEach((el) => {
        const raw = el.textContent || "";
        if (!raw.trim()) return;
        let data;
        try {
          data = JSON.parse(raw);
        } catch (e) {
          return;
        }
        const stack = Array.isArray(data) ? [...data] : [data];
        while (stack.length) {
          const node = stack.shift();
          if (!node || typeof node !== "object") continue;
          if (Array.isArray(node["@graph"])) {
            for (const s of node["@graph"]) stack.push(s);
          } else {
            nodes.push(node);
          }
        }
      });

    const url = location.href;
    let ld = null;
    for (const node of nodes) {
      if (typeMatches(node, "Product")) {
        ld = node;
        break;
      }
    }

    // JSON-LD path.
    if (ld) {
      const offers = ld.offers;
      let offer = {};
      if (Array.isArray(offers) && offers.length)
        offer = typeof offers[0] === "object" ? offers[0] : {};
      else if (offers && typeof offers === "object") offer = offers;

      const rating =
        ld.aggregateRating && typeof ld.aggregateRating === "object"
          ? ld.aggregateRating
          : {};

      let images = [];
      const imgRaw = ld.image;
      if (typeof imgRaw === "string") images = [imgRaw];
      else if (Array.isArray(imgRaw)) images = imgRaw.filter(Boolean).map(String);
      if (!images.length) {
        images = Array.from(document.querySelectorAll('meta[property="og:image"]'))
          .map((el) => el.getAttribute("content"))
          .filter(Boolean);
      }

      let brand = null;
      if (ld.brand && typeof ld.brand === "object") brand = ld.brand.name ?? null;
      else if (typeof ld.brand === "string") brand = ld.brand;

      const id = ld.productID ? String(ld.productID) : extractProductId(url);

      return {
        id: String(id || ""),
        url,
        name:
          clean(ld.name) ||
          clean(txt("h1")) ||
          clean(txt('[data-auto="product-name"]')) ||
          "",
        brand: clean(brand),
        description:
          clean(ld.description) ||
          clean(document.querySelector('meta[name="description"]')?.getAttribute("content")),
        price: toNumber(offer.price),
        priceCurrency: offer.priceCurrency ?? null,
        availability: shortAvailability(offer.availability),
        images,
        rating: rating.ratingValue != null ? Number(rating.ratingValue) : null,
        reviewCount:
          rating.reviewCount != null ? parseInt(rating.reviewCount, 10) : null,
        sku: ld.sku ? String(ld.sku) : null,
      };
    }

    // DOM-only fallback: emit Product-shaped record even when JSON-LD is gone
    // (delisted page, Akamai interstitial, or post-Nuxt-hydration race).
    const images = Array.from(document.querySelectorAll('meta[property="og:image"]'))
      .map((el) => el.getAttribute("content"))
      .filter(Boolean);
    const priceText = clean(
      txt('[data-auto="product-price"]') ||
        txt('[data-testid="product-price"]') ||
        txt(".price-reg") ||
        txt(".pricing")
    );
    return {
      id: String(extractProductId(url) || ""),
      url,
      name:
        clean(txt("h1")) ||
        clean(txt('[data-auto="product-name"]')) ||
        "",
      brand:
        clean(txt('[data-auto="product-brand"]')) ||
        clean(txt('[data-testid="product-brand"]')) ||
        clean(txt(".product-brand")) ||
        null,
      description: clean(
        document.querySelector('meta[name="description"]')?.getAttribute("content")
      ),
      price: toNumber(priceText),
      priceCurrency: priceText && priceText.includes("$") ? "USD" : null,
      availability: null,
      images,
      rating: null,
      reviewCount: null,
      sku: null,
    };
  })()]
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat product.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a one-element list of `Product` — the extractor prefers the JSON-LD `Product` block
and falls back to DOM selectors:

```json
[
  {
    "id": "2061867",
    "url": "https://www.macys.com/shop/product/levis-mens-541-athletic-fit-jean?ID=2061867",
    "name": "Levi's Men's 541 Athletic Fit Jeans",
    "brand": "Levi's",
    "price": 69.5,
    "priceCurrency": "USD",
    "availability": "InStock",
    "images": ["https://slimages.macysassets.com/is/image/MCY/products/..."]
  }
]
```

## 4. Scrape a category / search page

Reuse the same session — just `open` a category URL and wait for the product anchors.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.macys.com/shop/mens-clothing/mens-jeans?id=17979"
scrapeless-scraping-browser --session-id "$SID" wait "a[href*='ID=']"
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a Macy's category / search results page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
// Mirrors `parseSearch` in ../nodejs/macys.mjs.
JSON.stringify(
  (function () {
    const clean = (value) => {
      if (value == null) return null;
      const v = String(value).replace(/\s+/g, " ").trim();
      return v || null;
    };
    const toNumber = (value) => {
      if (value == null) return null;
      const n = parseFloat(String(value).replace(/[^\d.\-]/g, ""));
      return Number.isFinite(n) ? n : null;
    };
    const extractProductId = (url) => {
      if (!url) return "";
      try {
        const u = new URL(url, "https://www.macys.com");
        const id = u.searchParams.get("ID");
        if (id) return id;
      } catch (e) {}
      const m = String(url).match(/[?&]ID=(\d+)/i);
      return m ? m[1] : "";
    };

    const items = [];
    const seen = new Set();

    document.querySelectorAll('a[href*="ID="]').forEach((a) => {
      const href = a.getAttribute("href") || "";
      if (!/\/shop\/product\//i.test(href)) return;
      const abs = href.startsWith("http")
        ? href
        : "https://www.macys.com" + href;
      const id = extractProductId(abs);
      if (!id || seen.has(id)) return;
      seen.add(id);

      const card = a.closest(
        '[data-testid="product-tile"], [data-auto="product-tile"], .product-thumbnail-container, li, div'
      );
      const ctx = card || a;

      const txt = (sel) => ctx.querySelector(sel)?.textContent ?? "";
      const name =
        clean(
          txt(
            '[data-auto="product-title"], [data-testid="product-title"], .product-description, h3, h2'
          ) ||
            a.getAttribute("aria-label") ||
            ctx.querySelector("img")?.getAttribute("alt")
        ) || "";

      const brand = clean(
        txt(
          '[data-auto="product-brand"], [data-testid="product-brand"], .product-brand'
        )
      );

      const priceText = clean(
        txt(
          '[data-auto="product-price"], [data-testid="product-price"], .price-reg, .pricing'
        )
      );
      const price = toNumber(priceText);

      const img = ctx.querySelector("img");
      const image =
        img?.getAttribute("src") || img?.getAttribute("data-src") || null;

      items.push({
        id: String(id),
        url: abs,
        name,
        brand,
        image: image || null,
        price,
        priceCurrency: priceText && priceText.includes("$") ? "USD" : null,
      });
    });

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
    "id": "2061867",
    "url": "https://www.macys.com/shop/product/...?ID=2061867",
    "name": "Levi's Men's 541 Athletic Fit Jeans",
    "brand": "Levi's",
    "image": "https://slimages.macysassets.com/is/image/MCY/products/...",
    "price": 69.5,
    "priceCurrency": "USD"
  }
]
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/macys.mjs`](../nodejs/macys.mjs):

| Extractor | Returns |
| --- | --- |
| `product.js` | one-element list of `Product` |
| `search.js` | list of `SearchResult` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
