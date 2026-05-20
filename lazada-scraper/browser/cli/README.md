# Lazada — CLI surface

Scrape Lazada product and search pages from the command line with the
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
in-page extractor. Start with a product (PDP) page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name lazada-cli --ttl 300 --proxy-country SG --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the page body to render
scrapeless-scraping-browser --session-id "$SID" open "https://www.lazada.sg/products/pdp-i3529149697.html"
scrapeless-scraping-browser --session-id "$SID" wait "body"

# run the in-page extractor — its JSON comes back in data.result
# save the product extractor (a single expression returning a JSON string)
cat > product.js <<'JS'
// In-page extractor for a Lazada product detail (PDP) page.
// Returns a JSON string — a single Product (see ../../../DATA_MODEL.md).
// The nodejs/ surface captures the mtop detail XHR live; the CLI can't hook
// network responses, so this reads the inline `window.__moduleData__` blob
// Lazada hydrates the PDP from (falling back to `window.PAGE_DATA` /
// `window.runParams`). Best-effort: if the page only exposes the XHR path,
// use the nodejs/ or python/ surface instead.
JSON.stringify(
  (function () {
    const url = location.href.split("?")[0];

    const idFromUrl = (u) => {
      if (!u) return "";
      const m = u.match(/-i(\d+)(?:-s\d+)?\.html/);
      if (m) return m[1];
      const m2 = u.match(/\/(\d{8,})\.html/);
      if (m2) return m2[1];
      return "";
    };
    const abs = (u) => {
      if (!u) return null;
      if (u.startsWith("//")) return "https:" + u;
      if (u.startsWith("http")) return u;
      return "https://www.lazada.sg" + (u.startsWith("/") ? u : "/" + u);
    };
    const uniq = (arr) => Array.from(new Set(arr.filter(Boolean)));
    const toFloat = (text) => {
      if (text === null || text === undefined) return null;
      if (typeof text === "number")
        return Number.isFinite(text) ? text : null;
      const m = String(text).replace(/[^0-9.]/g, "");
      if (!m) return null;
      const n = parseFloat(m);
      return Number.isNaN(n) ? null : n;
    };
    const toInt = (text) => {
      if (text === null || text === undefined) return null;
      if (typeof text === "number")
        return Number.isFinite(text) ? Math.trunc(text) : null;
      const m = String(text).replace(/[^0-9]/g, "");
      if (!m) return null;
      const n = parseInt(m, 10);
      return Number.isNaN(n) ? null : n;
    };

    // Locate the module blob: __moduleData__, then a couple of known fallbacks.
    let mod = null;
    const candidates = [
      window.__moduleData__,
      window.PAGE_DATA,
      window.runParams && window.runParams.data,
      window.pageData,
    ];
    for (const c of candidates) {
      if (c && typeof c === "object") {
        if (c.product) {
          mod = c;
          break;
        }
        // some builds nest the module a level deeper
        for (const v of Object.values(c)) {
          if (v && typeof v === "object" && v.product) {
            mod = v;
            break;
          }
        }
        if (mod) break;
      }
    }
    if (!mod) {
      return {
        id: String(idFromUrl(url) || ""),
        url,
        title: "",
        brand: null,
        price: null,
        originalPrice: null,
        discount: null,
        currency: null,
        rating: null,
        reviews: null,
        images: [],
        seller: null,
        sellerUrl: null,
        availability: null,
        description: null,
        categories: [],
      };
    }

    const product = mod.product || {};
    const skuInfos = mod.skuInfos || {};
    const skuGalleries = mod.skuGalleries || {};
    const seller = mod.seller || {};
    const review = mod.review || {};
    const Breadcrumb = mod.Breadcrumb || mod.breadcrumb || [];
    const globalConfig = mod.globalConfig || {};

    const ids = Object.keys(skuInfos);
    const preferred =
      skuInfos[(mod.primaryKey || {}).skuId] ||
      skuInfos[ids[ids.length - 1]] ||
      skuInfos["0"] ||
      {};
    const priceObj = preferred.price || {};
    const sale = priceObj.salePrice || {};
    const orig = priceObj.originalPrice || {};

    const imgs = [];
    const galleryKey =
      (mod.primaryKey || {}).skuId || ids[ids.length - 1] || "0";
    for (const g of skuGalleries[galleryKey] || []) {
      const u = g?.src || g?.poster;
      if (u) imgs.push(u.startsWith("//") ? "https:" + u : u);
    }
    for (const u of product.imageUrls || []) imgs.push(u);
    const images = uniq(imgs);

    const categories = (Breadcrumb || [])
      .map((b) => b?.title)
      .filter(Boolean);

    return {
      id: String(
        idFromUrl(url) ||
          product.itemId ||
          (mod.primaryKey || {}).itemId ||
          ""
      ),
      url,
      title: product.title || "",
      brand:
        (product.brand && (product.brand.name || product.brand)) || null,
      price:
        sale.text ||
        (typeof sale.value === "number"
          ? `${sale.sign || ""}${sale.value}`
          : null),
      originalPrice:
        orig.text ||
        (typeof orig.value === "number" ? String(orig.value) : null),
      discount: priceObj.discount || null,
      currency: globalConfig.currencyCode || null,
      rating: toFloat(product.rating?.score ?? review.averageRating),
      reviews: toInt(product.rating?.total ?? review.contentedNum),
      images,
      seller: seller.name || null,
      sellerUrl: abs(seller.url) || null,
      availability: preferred?.operation?.text || null,
      description: product.desc || null,
      categories,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat product.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `Product` object — `product.js` reads the inline `window.__moduleData__`
blob the PDP hydrates from:

```json
{
  "id": "3529149697",
  "url": "https://www.lazada.sg/products/pdp-i3529149697.html",
  "title": "Beats iPhone 17 Case with MagSafe and Camera Control",
  "brand": "Apple",
  "price": "$30.00",
  "originalPrice": "$59.00",
  "discount": "-49%",
  "rating": 4.8,
  "reviews": 35,
  "images": ["https://laz-img-sg.alicdn.com/p/3774d6a66e051ed8e9f1c6941675b324.png"],
  "seller": "Apple Flagship Store"
}
```

## 4. Scrape a search page

Reuse the same session — just `open` a search URL and wait for the product cards.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.lazada.sg/catalog/?q=iphone%20case"
scrapeless-scraping-browser --session-id "$SID" wait "div[data-qa-locator=product-item], div[class*=card]"
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a Lazada search results page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const idFromUrl = (url) => {
      if (!url) return "";
      const m = url.match(/-i(\d+)(?:-s\d+)?\.html/);
      if (m) return m[1];
      const m2 = url.match(/\/(\d{8,})\.html/);
      if (m2) return m2[1];
      return "";
    };
    const toFloat = (text) => {
      if (text === null || text === undefined) return null;
      if (typeof text === "number")
        return Number.isFinite(text) ? text : null;
      const m = String(text).replace(/[^0-9.]/g, "");
      if (!m) return null;
      const n = parseFloat(m);
      return Number.isNaN(n) ? null : n;
    };
    const toInt = (text) => {
      if (text === null || text === undefined) return null;
      if (typeof text === "number")
        return Number.isFinite(text) ? Math.trunc(text) : null;
      const m = String(text).replace(/[^0-9]/g, "");
      if (!m) return null;
      const n = parseInt(m, 10);
      return Number.isNaN(n) ? null : n;
    };
    const text$ = (n) =>
      (n?.textContent || "").replace(/\s+/g, " ").trim() || null;

    const out = [];
    const seen = new Set();
    const cardSelectors = [
      "div[data-qa-locator='product-item']",
      "div[class*='card--']",
      "div[class*='Bm3ON']",
      "div[class*='product-card']",
    ];
    for (const sel of cardSelectors) {
      document.querySelectorAll(sel).forEach((card) => {
        const a = card.querySelector("a[href*='.html']");
        let href = a?.getAttribute("href") || "";
        if (href.startsWith("//")) href = "https:" + href;
        if (!href) return;
        const id = idFromUrl(href);
        if (!id || seen.has(id)) return;
        seen.add(id);

        const title =
          text$(
            card.querySelector(
              "[class*='RfADt'], [class*='title'], [class*='subject'], [class*='card-text-title']"
            )
          ) ||
          a?.getAttribute("title") ||
          text$(a) ||
          "";

        const imgEl = card.querySelector("img");
        const image =
          imgEl?.getAttribute("src") ||
          imgEl?.getAttribute("data-src") ||
          null;
        const price =
          text$(card.querySelector("[class*='price'], [class*='ooOxS']")) ||
          null;
        const originalPrice =
          text$(
            card.querySelector("[class*='WNoq3'], [class*='origPrice']")
          ) || null;
        const discount =
          text$(
            card.querySelector("[class*='IcOsH'], [class*='discount']")
          ) || null;
        const ratingEl = card.querySelector(
          "[class*='qzqFw'], [class*='rating'], [class*='stars']"
        );
        let rating = toFloat(
          ratingEl?.getAttribute("style") || text$(ratingEl)
        );
        if (rating !== null && rating > 5) rating = rating / 10;
        if (rating !== null && rating > 5) rating = null;
        const reviews = toInt(
          text$(
            card.querySelector("[class*='_6uN7R'], span[class*='review']")
          )
        );
        const location =
          text$(
            card.querySelector("[class*='oa6ri'], [class*='location']")
          ) || null;

        out.push({
          id,
          title,
          url: href,
          image:
            image && image.startsWith("//") ? "https:" + image : image,
          price,
          originalPrice,
          discount,
          rating,
          reviews,
          location,
        });
      });
    }
    return out;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
```

`data.result` is a list of `SearchResult`:

```json
[
  {
    "id": "3529149697",
    "title": "Beats iPhone 17 Case with MagSafe and Camera Control",
    "url": "https://www.lazada.sg/products/pdp-i3529149697.html",
    "image": "https://img.lazcdn.com/g/p/fec965e624add82660f06161e15a3cdd.png_200x200q80.png",
    "price": "$30.00",
    "discount": "49% Off",
    "rating": 3.5,
    "reviews": 20635,
    "location": "Singapore"
  }
]
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
parsers in [`../nodejs/lazada.mjs`](../nodejs/lazada.mjs):

| Extractor | Returns |
| --- | --- |
| `product.js` | one `Product` |
| `search.js` | list of `SearchResult` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
