# Zara — CLI surface

Scrape Zara product (PDP) and listing (PLP) pages from the command line with the
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
scrapeless-scraping-browser new-session --name zara-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the application/ld+json block to render
scrapeless-scraping-browser --session-id "$SID" open "https://www.zara.com/us/en/zw-collection-fitted-plaid-jacket-p02784381.html"
scrapeless-scraping-browser --session-id "$SID" wait "script[type=application/ld+json]"

# run the in-page extractor — its JSON comes back in data.result
# save the product extractor (a single expression returning a JSON string)
cat > product.js <<'JS'
// In-page extractor for a Zara product (PDP) page.
// Returns a JSON string — a single Product (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const PRODUCT_ID_RE = /-p(\d+)\.html/i;

    const clean = (value) => {
      if (value == null) return null;
      const v = String(value).replace(/\s+/g, " ").trim();
      return v || null;
    };

    const extractProductId = (url) => {
      if (!url) return "";
      const m = url.match(PRODUCT_ID_RE);
      if (m) return m[1];
      try {
        const u = new URL(url);
        return u.pathname
          .replace(/\/$/, "")
          .split("/")
          .pop()
          .replace(/\.html$/i, "");
      } catch (e) {
        return "";
      }
    };

    // Iterate every JSON-LD node, unwrapping @graph.
    const nodes = [];
    document
      .querySelectorAll('script[type="application/ld+json"]')
      .forEach((el) => {
        const raw = el.textContent;
        if (!raw || !raw.trim()) return;
        let data;
        try {
          data = JSON.parse(raw);
        } catch (e) {
          return;
        }
        const arr = Array.isArray(data) ? data : [data];
        for (const node of arr) {
          if (!node || typeof node !== "object") continue;
          if (Array.isArray(node["@graph"])) {
            for (const sub of node["@graph"]) {
              if (sub && typeof sub === "object") nodes.push(sub);
            }
          } else {
            nodes.push(node);
          }
        }
      });

    const typeMatches = (node, wanted) => {
      const t = node["@type"];
      if (typeof t === "string") return t === wanted;
      if (Array.isArray(t)) return t.includes(wanted);
      return false;
    };

    const firstOffer = (node) => {
      const offers = node?.offers;
      if (Array.isArray(offers) && offers.length)
        return typeof offers[0] === "object" ? offers[0] : {};
      if (offers && typeof offers === "object") {
        if (Array.isArray(offers.offers) && offers.offers.length)
          return typeof offers.offers[0] === "object"
            ? offers.offers[0]
            : {};
        return offers;
      }
      return {};
    };

    const attr = (sel, name) =>
      document.querySelector(sel)?.getAttribute(name) ?? null;

    let ld = {};
    for (const node of nodes) {
      if (typeMatches(node, "Product")) {
        ld = node;
        break;
      }
    }

    const offer = firstOffer(ld);
    const url = location.href;

    let images = [];
    if (typeof ld.image === "string") images = [ld.image];
    else if (Array.isArray(ld.image))
      images = ld.image.filter(Boolean).map(String);
    else
      images = Array.from(
        document.querySelectorAll('meta[property="og:image"]')
      )
        .map((el) => el.getAttribute("content"))
        .filter(Boolean);

    const name = ld.name
      ? clean(ld.name)
      : clean(attr('meta[property="og:title"]', "content")) ||
        clean(document.querySelector("h1")?.textContent);

    const description = ld.description
      ? clean(ld.description)
      : clean(attr('meta[name="description"]', "content"));

    const sku = ld.sku || ld.productID || extractProductId(url);

    let brand = "ZARA";
    if (ld.brand) {
      brand =
        typeof ld.brand === "object" ? ld.brand.name || "ZARA" : String(ld.brand);
    }

    let rawPrice =
      offer.price ?? clean(attr('meta[property="product:price:amount"]', "content"));
    let priceValue = null;
    if (rawPrice != null) {
      const n = parseFloat(String(rawPrice).replace(/,/g, ""));
      priceValue = Number.isFinite(n) ? n : null;
    }
    let currency =
      offer.priceCurrency ??
      clean(attr('meta[property="product:price:currency"]', "content"));

    let availability = offer.availability ?? null;
    if (typeof availability === "string" && availability.includes("/")) {
      availability = availability.split("/").pop();
    }

    let color = ld.color ?? null;
    if (!color) {
      color = clean(
        document
          .querySelector('[data-qa-qualifier="product-detail-color"]')
          ?.textContent ||
          document.querySelector("p.product-detail-info__color")?.textContent
      );
    }

    return {
      id: sku ? String(sku) : "",
      url,
      name: clean(name) || "",
      brand: clean(brand) || "ZARA",
      description,
      price: priceValue,
      priceCurrency: currency,
      availability,
      images,
      color: typeof color === "string" ? clean(color) : null,
      category: ld.category ? clean(ld.category) : null,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat product.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `Product` object, lifted from the PDP `application/ld+json` Product block:

```json
{
  "id": "528167692-061-1",
  "url": "https://www.zara.com/us/en/zw-collection-fitted-plaid-jacket-p02784381.html",
  "name": "FITTED PLAID JACKET ZW COLLECTION",
  "brand": "ZARA",
  "price": 149,
  "priceCurrency": "USD",
  "availability": "InStock",
  "images": ["https://static.zara.net/assets/public/.../02784381061-p.jpg"],
  "color": "White / Red",
  "category": null
}
```

the extractor wraps this object in a one-element list so the saved fixture stays shape-identical with the
`scrape_product` output of the other surfaces.

## 4. Scrape a search page

Reuse the same session — just `open` a listing URL and wait for the `application/ld+json` block.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.zara.com/us/en/woman-blazers-l1055.html"
scrapeless-scraping-browser --session-id "$SID" wait "script[type=application/ld+json]"
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a Zara listing (PLP) page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const PRODUCT_ID_RE = /-p(\d+)\.html/i;

    const clean = (value) => {
      if (value == null) return null;
      const v = String(value).replace(/\s+/g, " ").trim();
      return v || null;
    };

    const extractProductId = (url) => {
      if (!url) return "";
      const m = url.match(PRODUCT_ID_RE);
      if (m) return m[1];
      try {
        const u = new URL(url);
        return u.pathname
          .replace(/\/$/, "")
          .split("/")
          .pop()
          .replace(/\.html$/i, "");
      } catch (e) {
        return "";
      }
    };

    const nodes = [];
    document
      .querySelectorAll('script[type="application/ld+json"]')
      .forEach((el) => {
        const raw = el.textContent;
        if (!raw || !raw.trim()) return;
        let data;
        try {
          data = JSON.parse(raw);
        } catch (e) {
          return;
        }
        const arr = Array.isArray(data) ? data : [data];
        for (const node of arr) {
          if (!node || typeof node !== "object") continue;
          if (Array.isArray(node["@graph"])) {
            for (const sub of node["@graph"]) {
              if (sub && typeof sub === "object") nodes.push(sub);
            }
          } else {
            nodes.push(node);
          }
        }
      });

    const typeMatches = (node, wanted) => {
      const t = node["@type"];
      if (typeof t === "string") return t === wanted;
      if (Array.isArray(t)) return t.includes(wanted);
      return false;
    };

    const firstOffer = (node) => {
      const offers = node?.offers;
      if (Array.isArray(offers) && offers.length)
        return typeof offers[0] === "object" ? offers[0] : {};
      if (offers && typeof offers === "object") {
        if (Array.isArray(offers.offers) && offers.offers.length)
          return typeof offers.offers[0] === "object"
            ? offers.offers[0]
            : {};
        return offers;
      }
      return {};
    };

    // Build a name -> product URL map from DOM anchors, since Zara's ItemList
    // JSON-LD omits per-item URLs.
    const urlByName = new Map();
    document
      .querySelectorAll(
        'a[href*="-p0"][href$=".html"], a[href*="-p1"][href$=".html"]'
      )
      .forEach((a) => {
        const href = a.getAttribute("href") || "";
        if (!href) return;
        let absolute = "";
        try {
          absolute = new URL(href, "https://www.zara.com").toString();
        } catch (e) {
          return;
        }
        const label =
          clean(a.getAttribute("aria-label")) || clean(a.textContent);
        if (label && !urlByName.has(label.toUpperCase())) {
          urlByName.set(label.toUpperCase(), absolute);
        }
        const img =
          a.querySelector("img")?.getAttribute("src") ||
          a.querySelector("img")?.getAttribute("data-src");
        if (img) {
          const m = img.match(/\/(\d{8,11})/);
          if (m) {
            const pid8 = m[1].slice(0, 8);
            if (!urlByName.has(`PID:${pid8}`))
              urlByName.set(`PID:${pid8}`, absolute);
          }
        }
      });

    const items = [];

    for (const node of nodes) {
      if (!typeMatches(node, "ItemList")) continue;
      for (const el of node.itemListElement || []) {
        if (!el || typeof el !== "object") continue;
        const item =
          el.item && typeof el.item === "object" ? el.item : el;
        const offer = firstOffer(item);
        const name = clean(item.name) || "";
        let url = offer?.url || item.url || el.url || "";
        let image = item.image;
        if (Array.isArray(image) && image.length) image = String(image[0]);
        else if (typeof image !== "string") image = null;

        if (!url && name) url = urlByName.get(name.toUpperCase()) || "";
        if (!url && image) {
          const m = image.match(/\/(\d{8,11})/);
          if (m) url = urlByName.get(`PID:${m[1].slice(0, 8)}`) || "";
        }

        const sku = item.sku || item.productID || extractProductId(url);
        let priceValue = null;
        if (offer.price != null) {
          const n = parseFloat(String(offer.price).replace(/,/g, ""));
          priceValue = Number.isFinite(n) ? n : null;
        }
        items.push({
          id: sku ? String(sku) : "",
          url,
          name,
          image,
          price: priceValue,
          priceCurrency: offer.priceCurrency ?? null,
        });
      }
      if (items.length) break;
    }

    if (!items.length) {
      const seen = new Set();
      document
        .querySelectorAll('a[href*="-p"][href$=".html"]')
        .forEach((a) => {
          const href = a.getAttribute("href") || "";
          let absolute = "";
          try {
            absolute = new URL(href, "https://www.zara.com").toString();
          } catch (e) {}
          const sku = extractProductId(absolute);
          if (!sku || seen.has(sku)) return;
          seen.add(sku);
          const name = clean(
            a.getAttribute("aria-label") ||
              a.querySelector("h2,h3,span")?.textContent
          );
          const img =
            a.querySelector("img")?.getAttribute("src") ||
            a.querySelector("img")?.getAttribute("data-src") ||
            null;
          items.push({
            id: sku,
            url: absolute,
            name: name || "",
            image: img,
            price: null,
            priceCurrency: null,
          });
        });
    }

    return items;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
```

`data.result` is a list of `SearchResult`, taken from the PLP's `ItemList` JSON-LD with a DOM
fallback that scans anchors matching `-p<digits>.html`:

```json
[
  {
    "id": "02784381",
    "url": "https://www.zara.com/us/en/zw-collection-fitted-plaid-jacket-p02784381.html",
    "name": "FITTED PLAID JACKET ZW COLLECTION",
    "image": "https://static.zara.net/assets/public/.../02784381061-a1.jpg?w=352",
    "price": 149,
    "priceCurrency": "USD"
  }
]
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/zara.mjs`](../nodejs/zara.mjs):

| Extractor | Returns |
| --- | --- |
| `product.js` | one `Product` |
| `search.js` | list of `SearchResult` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
